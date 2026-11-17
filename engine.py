import json
import os
import re
import requests
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# Import database hooks
from database import initialize_database, save_new_audit

CONFIG_FILE = "config.json"

def load_api_keys():
    """Reads hidden developer configuration file safely from the local drive."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

PSI_LAB_METRICS = {
    "lcp": "largest-contentful-paint",
    "cls": "cumulative-layout-shift",
    "fcp": "first-contentful-paint",
    "tbt": "total-blocking-time",
    "speed_index": "speed-index",
}

# Real-visitor (Chrome UX Report) metrics as PageSpeed names them -> (label, formatter)
PSI_FIELD_METRICS = {
    "LARGEST_CONTENTFUL_PAINT_MS": ("Largest Contentful Paint", lambda v: f"{v / 1000:.1f} s"),
    "INTERACTION_TO_NEXT_PAINT": ("Interaction to Next Paint", lambda v: f"{v} ms"),
    "CUMULATIVE_LAYOUT_SHIFT_SCORE": ("Cumulative Layout Shift", lambda v: f"{v / 100:.2f}"),
    "FIRST_CONTENTFUL_PAINT_MS": ("First Contentful Paint", lambda v: f"{v / 1000:.1f} s"),
    "EXPERIMENTAL_TIME_TO_FIRST_BYTE": ("Time to First Byte", lambda v: f"{v / 1000:.2f} s"),
}

def _parse_field_data(data):
    """Real Chrome-user measurements, if Google has enough traffic data for this page or site."""
    for key, source in (("loadingExperience", "this page"), ("originLoadingExperience", "whole site")):
        experience = data.get(key) or {}
        metrics = experience.get("metrics") or {}
        if not metrics:
            continue
        if key == "loadingExperience" and experience.get("origin_fallback"):
            source = "whole site"
        parsed = {}
        for api_name, (label, fmt) in PSI_FIELD_METRICS.items():
            metric = metrics.get(api_name)
            if metric and metric.get("percentile") is not None:
                parsed[label] = {"value": fmt(metric["percentile"]), "rating": metric.get("category", "N/A")}
        return {"source": source, "overall": experience.get("overall_category", "N/A"), "metrics": parsed}
    return None

def _parse_fixes(audits, limit=5):
    """Google's own suggested fixes that are failing, biggest estimated time savings first."""
    fixes = []
    for audit in audits.values():
        if audit.get("scoreDisplayMode") != "metricSavings":
            continue
        score = audit.get("score")
        if score is None or score >= 0.9:
            continue
        savings_ms = sum(v for v in (audit.get("metricSavings") or {}).values() if isinstance(v, (int, float)))
        detail = audit.get("displayValue", "")
        if savings_ms == 0 and re.search(r"\b0\s*(KiB|ms)$", detail):
            continue  # "Est savings of 0 KiB" is noise, not a fix
        fixes.append({"title": audit.get("title", ""), "detail": audit.get("displayValue", ""), "savings_ms": savings_ms})
    fixes.sort(key=lambda f: f["savings_ms"], reverse=True)
    return fixes[:limit]

def fetch_google_pagespeed(target_url, api_key, strategy="mobile", timeout=90):
    """Queries Google PageSpeed for one device type ("mobile" or "desktop")."""
    # Ensure a clean tracking URL schema for external cloud request loops
    if not target_url.startswith(('http://', 'https://')):
        target_url = 'https://' + target_url

    # Pass the key and target via params so they are URL-encoded, and so the key
    # never appears in a hand-built URL that requests would echo into error messages.
    endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params = {"url": target_url, "key": api_key, "category": "performance", "strategy": strategy}

    def scrub(text):
        return text.replace(api_key, "***") if api_key else text

    try:
        # Mobile tests of heavy pages regularly take over a minute, hence the long timeout.
        response = requests.get(endpoint, params=params, timeout=timeout)
        data = response.json() if response.content else {}
        if response.status_code != 200:
            reason = (data.get("error") or {}).get("message", "") if isinstance(data, dict) else ""
            return {"score": "Error", "lcp": "Error", "msg": scrub(f"PageSpeed error {response.status_code}: {reason}".rstrip(": "))}

        lighthouse = data.get('lighthouseResult', {})
        audits = lighthouse.get('audits', {})
        raw_score = lighthouse.get('categories', {}).get('performance', {}).get('score')

        result = {
            "score": int(round(raw_score * 100)) if raw_score is not None else "N/A",
            "field_data": _parse_field_data(data),
            "fixes": _parse_fixes(audits),
            "msg": "Successfully retrieved cloud metrics.",
        }
        for name, audit_id in PSI_LAB_METRICS.items():
            result[name] = audits.get(audit_id, {}).get('displayValue', 'N/A')
        return result
    except Exception as e:
        # Never store the raw exception text: it can contain the request URL, including the key.
        return {"score": "Offline", "lcp": "Offline", "msg": scrub(f"API Connection Failed ({type(e).__name__}): {e}")}

def format_score(score):
    return f"{score}/100" if isinstance(score, int) else str(score)

def audit_url(url):
    """Scrapes a target website from the outside and appends background API data."""
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to reach target URL: {str(e)}"}

    soup = BeautifulSoup(response.text, 'html.parser')
    domain = urlparse(url).netloc

    # --- 1. Scrape On-Page Tags ---
    title_tag = soup.find('title')
    title = title_tag.text.strip() if title_tag else None

    meta_desc_tag = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
    # A meta tag can exist without a content attribute; treat that as missing.
    meta_description = (meta_desc_tag.get('content') or '').strip() if meta_desc_tag else ''
    meta_description = meta_description or None

    # --- 2. Heading Tag Hierarchy ---
    headings = {}
    for i in range(1, 7):
        tags = soup.find_all(f'h{i}')
        headings[f'h{i}'] = [t.text.strip() for t in tags if t.text.strip()]

    # --- 3. Image Optimization ---
    images = soup.find_all('img')
    # alt="" is the correct markup for decorative images, so only a missing alt attribute counts.
    missing_alt = sum(1 for img in images if img.get('alt') is None)

    # --- 4. Link Density Mapping ---
    links = soup.find_all('a', href=True)
    internal_links = 0
    external_links = 0
    for link in links:
        href = link['href']
        if href.startswith('/') or domain in href:
            internal_links += 1
        elif href.startswith('http'):
            external_links += 1

    # --- 5. Integrated Conditional API Hook System ---
    performance = {
        "strategy": "mobile",
        "score": "Not Configured",
        "desktop_score": "Not Configured",
        "lcp": "Not Configured",
        "api_status_log": "Skipped - No active credentials located in file manager.",
    }

    keys = load_api_keys()
    google_key = keys.get("google_pagespeed_key", "").strip()

    if google_key:
        # Google ranks sites on their mobile version, so mobile is the headline result.
        # Desktop runs at the same time for comparison only.
        with ThreadPoolExecutor(max_workers=2) as pool:
            mobile_job = pool.submit(fetch_google_pagespeed, url, google_key, "mobile")
            desktop_job = pool.submit(fetch_google_pagespeed, url, google_key, "desktop")
            mobile, desktop = mobile_job.result(), desktop_job.result()

        performance.update({
            "score": format_score(mobile["score"]),
            "desktop_score": format_score(desktop["score"]),
            "lcp": mobile.get("lcp", "N/A"),
            "api_status_log": mobile["msg"],
        })
        for name in ("cls", "fcp", "tbt", "speed_index"):
            performance[name] = mobile.get(name, "N/A")
        performance["field_data"] = mobile.get("field_data")
        performance["fixes"] = mobile.get("fixes", [])

    # --- 6. Unified JSON Report Payload ---
    report = {
        "target_url": url,
        "meta": {
            "title": title,
            "title_length": len(title) if title else 0,
            "description": meta_description,
            "description_length": len(meta_description) if meta_description else 0
        },
        "headings": headings,
        "images": {
            "total_count": len(images),
            "missing_alt_count": missing_alt
        },
        "links": {
            "internal_count": internal_links,
            "external_count": external_links
        },
        "performance": performance
    }

    return report



if __name__ == "__main__":
    initialize_database()
    proj_name = input("Enter a Project Name: ").strip()
    target_url = input("Enter the Website URL: ").strip()
    
    if proj_name and target_url:
        audit_result = audit_url(target_url)
        if "error" not in audit_result:
            save_new_audit(proj_name, target_url, audit_result)
            print("\nAnalysis Saved Successfully!")

def fetch_open_pagerank(domain, config_path="config.json"):
    """
    Fetches free domain authority and ranking metrics from the OpenPageRank API.
    """
    # 1. Load keys securely from your local config vault
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
    else:
        config = {}

    api_key = config.get("open_pagerank_key", "")

    if not api_key:
        return {"status": "skipped", "error": "No OpenPageRank API Key configured."}

    # 2. Query OpenPageRank endpoint
    url = f"https://openpagerank.com/api/v1.0/getPageRank?domains[]={domain}"
    headers = {"API-OPR": api_key}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            # Extract domain parameters safely from the payload response array
            if data.get("status_code") == 200:
                results = data.get("response", [])
                if results:
                    domain_info = results[0]
                    return {
                        "status": "success",
                        "page_rank_integer": domain_info.get("page_rank_integer", "N/A"),
                        "page_rank_decimal": domain_info.get("page_rank_decimal", "N/A"),
                        "rank": domain_info.get("rank", "N/A")
                    }
            return {"status": "error", "error": "Invalid API data format structure."}
        else:
            return {"status": "error", "error": f"HTTP Error: {response.status_code}"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "error": f"Connection Timed Out: {str(e)}"}

def fetch_dataforseo(self, domain, api_login, api_password):
    """
    Fetches Domain Rank and Spam Score using DataForSEO v3 API.
    """
    import requests
    import base64

    # The correct v3 endpoint for rank and spam score
    url = "https://api.dataforseo.com/v3/backlinks/summary/live"
    
    # DataForSEO requires Base64 encoded credentials
    credentials = f"{api_login}:{api_password}"
    encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
    
    headers = {
        'Authorization': f'Basic {encoded_credentials}',
        'Content-Type': 'application/json'
    }
    
    # Payload targeting the specific domain
    payload = [{
        "target": domain,
        "internal_list_limit": 1
    }]
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        
        # 20000 is DataForSEO's internal success code
        if response.status_code == 200 and data.get('status_code') == 20000:
            # Safely navigate their complex JSON response structure
            try:
                result = data['tasks'][0]['result'][0]
                return {
                    "rank": result.get("rank", "N/A"),
                    "spam_score": result.get("spam_score", "N/A"),
                    "status": "Success",
                    "error": ""
                }
            except (IndexError, KeyError):
                return {
                    "rank": "N/A", 
                    "spam_score": "N/A", 
                    "status": "No Data", 
                    "error": "Domain not found in index."
                }
        else:
            return {
                "rank": "N/A", 
                "spam_score": "N/A", 
                "status": f"API Error ({data.get('status_code')})",
                "error": data.get('status_message', 'Unknown Error')
            }
            
    except Exception as e:
        return {
            "rank": "N/A", 
            "spam_score": "N/A", 
            "status": "Request Failed", 
            "error": str(e)
        }
# Inside your main core auditing orchestrator function where the pipeline triggers:
# (Update your returned JSON structure layout block to merge this dynamic payload)