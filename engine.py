import json
import os
import requests
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

def fetch_google_pagespeed(target_url, api_key):
    """Queries official Google PageSpeed cloud APIs for speed scores and Web Vitals."""
    # Ensure a clean tracking URL schema for external cloud request loops
    if not target_url.startswith(('http://', 'https://')):
        target_url = 'https://' + target_url
        
    endpoint = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={target_url}&key={api_key}&category=performance"
    
    try:
        response = requests.get(endpoint, timeout=45)
        if response.status_code == 200:
            data = response.json()
            # Parse metrics from the cloud response payload
            lighthouse = data.get('lighthouseResult', {})
            score = lighthouse.get('categories', {}).get('performance', {}).get('score', 0) * 100
            
            # Extract Core Web Vital: Largest Contentful Paint (LCP)
            lcp_display = lighthouse.get('audits', {}).get('largest-contentful-paint', {}).get('displayValue', 'N/A')
            
            return {"score": int(score), "lcp": lcp_display, "msg": "Successfully retrieved cloud metrics."}
        else:
            return {"score": "Error", "lcp": "Error", "msg": f"API Rejected Key (Code {response.status_code})"}
    except Exception as e:
        return {"score": "Offline", "lcp": "Offline", "msg": f"API Connection Timed Out: {str(e)}"}

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
    meta_description = meta_desc_tag['content'].strip() if meta_desc_tag else None

    # --- 2. Heading Tag Hierarchy ---
    headings = {}
    for i in range(1, 7):
        tags = soup.find_all(f'h{i}')
        headings[f'h{i}'] = [t.text.strip() for t in tags if t.text.strip()]

    # --- 3. Image Optimization ---
    images = soup.find_all('img')
    missing_alt = sum(1 for img in images if not img.get('alt') or not img.get('alt').strip())

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
    performance_score = "Not Configured"
    lcp_metric = "Not Configured"
    api_status = "Skipped - No active credentials located in file manager."
    
    keys = load_api_keys()
    google_key = keys.get("google_pagespeed", "").strip()
    
    if google_key:
        api_status = "Connecting to Google Cloud Engines..."
        speed_report = fetch_google_pagespeed(url, google_key)
        performance_score = f"{speed_report['score']}/100"
        lcp_metric = speed_report['lcp']
        api_status = speed_report['msg']

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
        "performance": {
            "score": performance_score,
            "lcp": lcp_metric,
            "api_status_log": api_status
        }
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