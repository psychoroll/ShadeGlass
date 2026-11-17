"""
Turns a raw audit report into plain-language verdicts.

Every metric becomes an item with:
  label    what was measured
  value    what this site scored
  level    "good" | "warn" | "poor" | "info" | "na"
  verdict  one sentence about this site's result
  guide    what good and bad look like, e.g. "Good: under 2.5 s · Poor: over 4 s"
  why      why it matters, in client-friendly language

Both the app panels and the exported HTML report are built from this, so they always agree.
"""
import re

LEVEL_LABELS = {
    "good": "Good",
    "warn": "Needs work",
    "poor": "Poor",
    "info": "Info",
    "na": "Unavailable",
}


def fmt_num(value):
    """1234567 -> '1,234,567'; anything that isn't a number is shown as-is."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    if isinstance(value, str) and value.isdigit():
        return f"{int(value):,}"
    return "N/A" if value is None else str(value)


def _number(value):
    """Best-effort number from 2.7, '2.7 s', '1,040 ms', '88/100' or '62'. Returns None if not numeric."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d[\d,]*\.?\d*", str(value))
    return float(match.group(0).replace(",", "")) if match else None


def _seconds(text):
    """'2.7 s' -> 2.7, '350 ms' -> 0.35 (PageSpeed uses a non-breaking space)."""
    number = _number(text)
    if number is None:
        return None
    return number / 1000 if re.search(r"\bms\b", str(text).replace("\xa0", " ")) else number


def _score(text):
    """'88/100' -> 88; 'Not Configured' -> None."""
    match = re.match(r"^\s*(\d+)\s*/\s*100\s*$", str(text))
    return int(match.group(1)) if match else None


def _band(value, good_max, warn_max, lower_is_better=True):
    """Grades a number against two cut-offs."""
    if value is None:
        return "na"
    if lower_is_better:
        return "good" if value <= good_max else "warn" if value <= warn_max else "poor"
    return "good" if value >= good_max else "warn" if value >= warn_max else "poor"


def item(label, value, level, verdict="", guide="", why="", kind="score"):
    """kind: "score" for measured results, "text" for quoted page content such as the title."""
    return {"label": label, "value": value, "level": level, "verdict": verdict, "guide": guide, "why": why, "kind": kind}


# --------------------------------------------------------------------------- performance

def _speed_score_item(label, raw, device):
    score = _score(raw)
    level = _band(score, 90, 50, lower_is_better=False)
    verdicts = {
        "good": f"Fast on {device}. Visitors get content quickly.",
        "warn": f"Average on {device}. Some visitors will notice the wait.",
        "poor": f"Slow on {device}. Expect visitors to give up before the page loads.",
        "na": f"No {device} score: {raw}.",
    }
    return item(label, str(raw), level, verdicts[level],
                "Good: 90–100 · Needs work: 50–89 · Poor: under 50",
                "Google's overall speed grade for the page. Google ranks sites on their mobile version, so the mobile score matters most."
                if device == "mobile" else "Shown for comparison. Desktop is usually faster than mobile.")


LAB_METRICS = [
    # key, label, unit, good_max, warn_max, guide, why
    ("lcp", "Largest Contentful Paint", "s", 2.5, 4.0,
     "Good: 2.5 s or less · Needs work: up to 4 s · Poor: over 4 s",
     "How long until the main content (usually the hero image or headline) appears. The biggest factor in whether a page feels fast."),
    ("cls", "Cumulative Layout Shift", "", 0.1, 0.25,
     "Good: 0.1 or less · Needs work: up to 0.25 · Poor: over 0.25",
     "How much the page jumps around while loading. High numbers mean people tap the wrong thing."),
    ("fcp", "First Contentful Paint", "s", 1.8, 3.0,
     "Good: 1.8 s or less · Needs work: up to 3 s · Poor: over 3 s",
     "How long until anything at all appears. Until then, visitors stare at a blank screen."),
    ("tbt", "Total Blocking Time", "s", 0.2, 0.6,
     "Good: 200 ms or less · Needs work: up to 600 ms · Poor: over 600 ms",
     "How long the page is frozen and ignores taps and clicks while scripts run."),
    ("speed_index", "Speed Index", "s", 3.4, 5.8,
     "Good: 3.4 s or less · Needs work: up to 5.8 s · Poor: over 5.8 s",
     "How quickly the visible part of the page fills in overall."),
]

LAB_VERDICTS = {"good": "Within Google's target.", "warn": "Slower than Google's target.",
                "poor": "Well outside Google's target.", "na": "Not measured."}

FIELD_LEVELS = {"FAST": "good", "AVERAGE": "warn", "SLOW": "poor"}


def performance_section(report):
    perf = report.get("performance") or {}
    items = [
        _speed_score_item("Mobile speed score", perf.get("score", "N/A"), "mobile"),
        _speed_score_item("Desktop speed score", perf.get("desktop_score", "N/A"), "desktop"),
    ]

    lab = []
    for key, label, unit, good_max, warn_max, guide, why in LAB_METRICS:
        if key not in perf:
            continue
        raw = perf.get(key)
        value = _seconds(raw) if unit == "s" else _number(raw)
        level = _band(value, good_max, warn_max)
        lab.append(item(label, str(raw), level, LAB_VERDICTS[level], guide, why))

    field_items, field_note = [], ""
    field = perf.get("field_data")
    if field and field.get("metrics"):
        for label, metric in field["metrics"].items():
            level = FIELD_LEVELS.get(metric.get("rating"), "info")
            field_items.append(item(label, metric.get("value", "N/A"), level,
                                    {"good": "Real visitors get a good experience.",
                                     "warn": "Real visitors get a mixed experience.",
                                     "poor": "Real visitors get a poor experience."}.get(level, "")))
        field_note = (f"Measured on real Chrome visitors to the {field.get('source', 'site')} over the last 28 days. "
                      "This is the data Google actually uses for its page experience ranking signal.")
    elif "field_data" in perf:
        field_note = "Not enough Chrome traffic for Google to report real-visitor data yet. The lab test above is the best guide for now."

    return {
        "key": "performance",
        "title": "Speed & experience",
        "kicker": "performance",
        "intro": "Tested by Google PageSpeed on a simulated mid-range phone, plus desktop for comparison.",
        "items": items,
        "groups": [
            {"title": "Lab test (mobile)", "items": lab, "note": ""},
            {"title": "Real visitors", "items": field_items, "note": field_note},
        ],
        "list_title": "Top fixes Google suggests",
        "list_note": "Ordered by estimated loading-time savings, biggest first.",
        "list": [f"{f['title']}" + (f" — {f['detail']}" if f.get("detail") else "") for f in perf.get("fixes") or []],
        "status": perf.get("api_status_log", ""),
    }


# --------------------------------------------------------------------------- on-page

def onpage_section(report):
    meta = report.get("meta") or {}
    headings = report.get("headings") or {}
    images = report.get("images") or {}

    title = meta.get("title")
    title_len = meta.get("title_length", 0) or 0
    if not title:
        level, verdict = "poor", "No title tag. Google will make one up, and it is rarely a good one."
    elif 30 <= title_len <= 60:
        level, verdict = "good", "A good length. It should show in full in search results."
    elif title_len > 70:
        level, verdict = "poor", "Too long. Search results will cut it off mid-sentence."
    elif title_len > 60:
        level, verdict = "warn", "A little long. The end may be cut off in search results."
    else:
        level, verdict = "warn", "Short. There is room to add the main keyword or a reason to click."
    title_item = item("Page title", title or "Missing", level, f"{title_len} characters. {verdict}",
                      "Good: 30–60 characters · Needs work: under 30 or 61–70 · Poor: missing or over 70",
                      "The clickable headline in Google results and the browser tab. The single most important on-page SEO element.", kind="text")

    desc = meta.get("description")
    desc_len = meta.get("description_length", 0) or 0
    if not desc:
        level, verdict = "poor", "No description. Google will pull random text from the page instead."
    elif 70 <= desc_len <= 160:
        level, verdict = "good", "A good length for search results."
    elif desc_len > 200:
        level, verdict = "poor", "Far too long. Most of it will be cut off."
    elif desc_len > 160:
        level, verdict = "warn", "A little long. The end will be cut off in search results."
    else:
        level, verdict = "warn", "Short. It may not give people enough reason to click."
    desc_item = item("Meta description", desc or "Missing", level, f"{desc_len} characters. {verdict}",
                     "Good: 70–160 characters · Needs work: under 70 or 161–200 · Poor: missing or over 200",
                     "The two lines of text under the title in Google. It doesn't change rankings directly, but it is the ad copy that earns the click.", kind="text")

    h1s = headings.get("h1") or []
    if len(h1s) == 1:
        level, verdict = "good", "Exactly one main heading, as it should be."
    elif not h1s:
        level, verdict = "poor", "No main heading. Search engines can't tell what the page is about at a glance."
    else:
        level, verdict = "warn", f"{len(h1s)} main headings. One clear H1 is easier for search engines to read."
    h1_item = item("Main heading (H1)", f"{len(h1s)} found", level, verdict,
                   "Good: exactly 1 · Needs work: 2 or more · Poor: none",
                   "The page's headline in the code. It tells search engines the topic of the page and should contain the main keyword.")

    total = images.get("total_count", 0) or 0
    missing = images.get("missing_alt_count", 0) or 0
    if total == 0:
        alt_item = item("Image alt text", "No images", "info", "There are no images on the page to check.")
    else:
        share = missing / total
        level = "good" if missing == 0 else "warn" if share <= 0.2 else "poor"
        verdict = {"good": "Every image has alt text.",
                   "warn": "A few images have no alt text.",
                   "poor": "Many images have no alt text."}[level]
        alt_item = item("Image alt text", f"{missing} of {total} missing", level, verdict,
                        "Good: none missing · Needs work: up to 20% missing · Poor: more than 20% missing",
                        "Search engines and screen readers can't see images; they read the alt text. Missing alt text loses image search traffic and hurts accessibility.")

    outline = []
    for tag in ("h1", "h2", "h3"):
        for text in (headings.get(tag) or [])[:8]:
            outline.append(f"{tag.upper()}  {text}")

    return {
        "key": "onpage",
        "title": "On-page SEO",
        "kicker": "on-page",
        "intro": "What search engines read when they visit this page.",
        "items": [title_item, desc_item, h1_item, alt_item],
        "groups": [],
        "list_title": "Heading outline",
        "list_note": "The page's structure as search engines see it (first 8 of each level).",
        "list": outline,
        "status": "",
    }


# --------------------------------------------------------------------------- links & backlinks

def links_section(report):
    links = report.get("links") or {}
    dfs = report.get("dataforseo") or {}

    internal = links.get("internal_count", 0) or 0
    level = "good" if internal >= 5 else "warn" if internal >= 1 else "poor"
    items = [
        item("Internal links", str(internal), level,
             {"good": "The page links well to the rest of the site.",
              "warn": "Only a few links to other pages on the site.",
              "poor": "No links to other pages on the site."}[level],
             "Good: 5 or more · Needs work: 1–4 · Poor: none",
             "Links to your own pages help visitors keep going and help search engines find and rank your other pages."),
        item("External links", str(links.get("external_count", 0) or 0), "info",
             "Links out to other websites. Neither good nor bad on their own.",
             "", "Linking to trusted sources is fine; there's no target number."),
    ]

    groups = []
    if dfs.get("status") == "success":
        ref = _number(dfs.get("referring_domains"))
        ref_level = _band(ref, 100, 20, lower_is_better=False)
        broken = _number(dfs.get("broken_backlinks"))
        broken_level = "good" if broken == 0 else "warn" if broken is not None else "na"
        groups.append({"title": "Backlink profile (other sites linking here)", "note": "", "items": [
            item("Referring domains", f"{fmt_num(dfs.get('referring_domains'))} ({fmt_num(dfs.get('referring_domains_nofollow'))} nofollow)",
                 ref_level,
                 {"good": "A strong spread of sites link here.",
                  "warn": "A modest number of sites link here. More would help.",
                  "poor": "Very few sites link here. This limits how well the site can rank.",
                  "na": ""}[ref_level],
                 "Strong: 100+ · Average: 20–99 · Weak: under 20 (rough guide for small businesses)",
                 "How many different websites link to this one. One of the strongest ranking signals there is."),
            item("Total backlinks", fmt_num(dfs.get("backlinks")), "info",
                 "All individual links, including several from the same site."),
            item("Broken backlinks", fmt_num(dfs.get("broken_backlinks")), broken_level,
                 "None. Every incoming link reaches a live page." if broken_level == "good"
                 else "Some sites link to pages that no longer exist. Redirecting those pages wins the value back.",
                 "Good: 0 · Needs work: any",
                 "Links pointing at deleted or moved pages waste the authority they would pass on."),
            item("First seen", dfs.get("first_seen") or "N/A", "info", "When DataForSEO first found this domain."),
        ]})
    else:
        groups.append({"title": "Backlink profile", "items": [],
                       "note": f"DataForSEO: {dfs.get('error', 'not configured')}."})

    return {
        "key": "links",
        "title": "Links & backlinks",
        "kicker": "links",
        "intro": "Links on this page, and links from other websites to this domain.",
        "items": items,
        "groups": groups,
        "list_title": "", "list_note": "", "list": [], "status": "",
    }


# --------------------------------------------------------------------------- authority & trust

def _trend_item(trend):
    if not trend:
        return item("Score trend", "Not enough history", "info", "OpenPageRank needs at least two months of data.")
    change = trend["change"]
    level = "good" if change > 0 else "warn" if change < 0 else "info"
    direction = "Up" if change > 0 else "Down" if change < 0 else "Flat"
    return item("Score trend", f"{direction} {abs(change):.2f}", level,
                f"From {trend['from']} in {trend['from_date'][:7]} to {trend['to']} in {trend['to_date'][:7]}.",
                "Good: rising · Needs work: falling",
                "Whether the site is gaining or losing authority over time (up to the last 12 months).")


def authority_section(report):
    dfs = report.get("dataforseo") or {}
    opr = report.get("open_pagerank") or {}
    groups = []

    if dfs.get("status") == "success":
        rank = _number(dfs.get("rank"))
        rank_level = _band(rank, 200, 50, lower_is_better=False)
        spam = _number(dfs.get("backlinks_spam_score"))
        spam_level = _band(spam, 30, 60)
        site_spam = _number(dfs.get("target_spam_score"))
        site_spam_level = _band(site_spam, 30, 60)
        groups.append({"title": "DataForSEO", "note": "", "items": [
            item("Domain rank", f"{fmt_num(dfs.get('rank'))} / 1000", rank_level,
                 {"good": "A strong link profile.", "warn": "An average link profile.",
                  "poor": "A weak link profile. Earning links from reputable sites is the fix.", "na": ""}[rank_level],
                 "Strong: 200+ · Average: 50–199 · Weak: under 50 (higher is better)",
                 "DataForSEO's 0–1000 measure of how strong the domain's backlinks are."),
            item("Backlink spam score", f"{fmt_num(dfs.get('backlinks_spam_score'))} / 100", spam_level,
                 {"good": "The sites linking here look trustworthy.",
                  "warn": "A noticeable share of linking sites look spammy. Worth reviewing.",
                  "poor": "Many linking sites look spammy. Review them and consider disavowing the worst.", "na": ""}[spam_level],
                 "Good: 0–30 · Needs work: 31–60 · Poor: over 60 (lower is better)",
                 "The average spamminess of the sites linking here. Toxic links can drag rankings down."),
            item("Site spam score", f"{fmt_num(dfs.get('target_spam_score'))} / 100", site_spam_level,
                 {"good": "The domain itself looks trustworthy.",
                  "warn": "The domain shows some spam signals.",
                  "poor": "The domain itself shows strong spam signals.", "na": ""}[site_spam_level],
                 "Good: 0–30 · Needs work: 31–60 · Poor: over 60 (lower is better)",
                 "How spammy this domain looks on its own."),
        ]})
    else:
        groups.append({"title": "DataForSEO", "items": [], "note": f"{dfs.get('error', 'Not configured')}."})

    if opr.get("status") == "success":
        score = _number(opr.get("score"))
        score_level = _band(score, 5, 3, lower_is_better=False)
        groups.append({"title": "OpenPageRank", "note": "", "items": [
            item("PageRank score", f"{opr.get('score')} / 10", score_level,
                 {"good": "Strong authority.", "warn": "Average authority for a business site.",
                  "poor": "Low authority. Common for new or small sites; links from other sites raise it.", "na": ""}[score_level],
                 "Strong: 5+ · Average: 3–4.9 · Weak: under 3 (higher is better)",
                 "A 0–10 authority score based on links from across the web."),
            item("Global position", f"#{fmt_num(opr.get('rank'))}", "info",
                 "Where the domain sits among every site OpenPageRank tracks (lower is better)."),
            item("Referring domains", fmt_num(opr.get("referring_domains")), "info",
                 "OpenPageRank's own count. It crawls less than DataForSEO, so it is often lower."),
            _trend_item(opr.get("trend")),
        ]})
    else:
        groups.append({"title": "OpenPageRank", "items": [], "note": f"{opr.get('error', 'Not configured')}."})

    return {
        "key": "authority",
        "title": "Authority & trust",
        "kicker": "authority",
        "intro": "How much search engines are likely to trust this domain, based on who links to it.",
        "items": [],
        "groups": groups,
        "list_title": "", "list_note": "", "list": [], "status": "",
    }


# --------------------------------------------------------------------------- summary

def all_items(section):
    found = list(section["items"])
    for group in section["groups"]:
        found.extend(group["items"])
    return found


def build_sections(report):
    return [onpage_section(report), performance_section(report), links_section(report), authority_section(report)]


def summary(report, sections=None):
    """Headline numbers and the most important things to fix."""
    sections = sections or build_sections(report)
    graded = [i for s in sections for i in all_items(s) if i["level"] in ("good", "warn", "poor")]
    counts = {lvl: sum(1 for i in graded if i["level"] == lvl) for lvl in ("good", "warn", "poor")}

    by_key = {s["key"]: s for s in sections}
    onpage = [i for i in all_items(by_key["onpage"]) if i["level"] in ("good", "warn", "poor")]
    onpage_passed = sum(1 for i in onpage if i["level"] == "good")
    onpage_level = "good" if onpage and onpage_passed == len(onpage) else "poor" if onpage_passed <= len(onpage) / 2 else "warn"

    perf_item = by_key["performance"]["items"][0]
    authority_items = {i["label"]: i for i in all_items(by_key["authority"])}
    authority = authority_items.get("PageRank score") or authority_items.get("Domain rank")
    spam = authority_items.get("Backlink spam score")

    tiles = [
        {"label": "Mobile speed", "value": perf_item["value"], "level": perf_item["level"]},
        {"label": "On-page checks passed", "value": f"{onpage_passed} / {len(onpage)}", "level": onpage_level if onpage else "na"},
        {"label": authority["label"] if authority else "Authority",
         "value": authority["value"] if authority else "Unavailable", "level": authority["level"] if authority else "na"},
        {"label": "Backlink spam", "value": spam["value"] if spam else "Unavailable", "level": spam["level"] if spam else "na"},
    ]

    priorities = sorted((i for i in graded if i["level"] in ("poor", "warn")),
                        key=lambda i: 0 if i["level"] == "poor" else 1)[:6]
    return {"counts": counts, "tiles": tiles, "priorities": priorities}
