"""Builds the exported HTML audit report in the reqless design co. style."""
import html
from datetime import datetime
from urllib.parse import urlparse

import insights
from theme import DEAD_AIR, NOISE, SNOW, GLITCH, CARRIER, PHOSPHOR, LIVE

FONTS_URL = ("https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700"
             "&family=Space+Mono:wght@400;700&family=Unbounded:wght@700;900&display=swap")


def esc(value):
    return html.escape("" if value is None else str(value), quote=True)


def site_name(url):
    """'https://www.Website.com/page' -> 'website.com'"""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    host = (urlparse(url).hostname or url).lower()
    return host[4:] if host.startswith("www.") else host


def pill(level):
    return f'<span class="pill pill-{esc(level)}">{esc(insights.LEVEL_LABELS.get(level, level))}</span>'


def render_item(it):
    guide = f'<p class="guide"><span>what good looks like</span>{esc(it["guide"])}</p>' if it.get("guide") else ""
    why = f'<p class="why">{esc(it["why"])}</p>' if it.get("why") else ""
    verdict = f'<p class="verdict">{esc(it["verdict"])}</p>' if it.get("verdict") else ""
    kind = "text" if it.get("kind") == "text" else "score"
    return f"""
        <div class="metric level-{esc(it['level'])}">
          <div class="metric-head"><h4>{esc(it['label'])}</h4>{pill(it['level'])}</div>
          <p class="metric-value value-{kind}">{esc(it['value'])}</p>
          {verdict}{guide}{why}
        </div>"""


def render_section(section, index):
    parts = [f"""
    <section class="panel" id="{esc(section['key'])}">
      <p class="kicker"><span class="num">{index:02d}</span> ( {esc(section['kicker'])} )</p>
      <h2>{esc(section['title'])}</h2>
      <p class="intro">{esc(section['intro'])}</p>"""]

    if section["items"]:
        parts.append('<div class="metrics">' + "".join(render_item(i) for i in section["items"]) + "</div>")

    for group in section["groups"]:
        if not group["items"] and not group.get("note"):
            continue
        parts.append(f'<h3>{esc(group["title"])}</h3>')
        if group.get("note"):
            parts.append(f'<p class="note">{esc(group["note"])}</p>')
        if group["items"]:
            parts.append('<div class="metrics">' + "".join(render_item(i) for i in group["items"]) + "</div>")

    if section.get("list"):
        items = "".join(f"<li>{esc(entry)}</li>" for entry in section["list"])
        parts.append(f'<h3>{esc(section["list_title"])}</h3><p class="note">{esc(section["list_note"])}</p><ol class="plain-list">{items}</ol>')

    parts.append("</section>")
    return "".join(parts)


def build_report_html(project_name, report, generated=None):
    generated = generated or datetime.now()
    url = report.get("target_url", "")
    name = site_name(url)
    sections = insights.build_sections(report)
    summary = insights.summary(report, sections)
    counts = summary["counts"]

    # Size the site name to fit its length on one line: Unbounded 900 is roughly 0.9em per character,
    # and the content column is at most ~990px wide. Long names may still break, but only at dots.
    chars = max(len(name), 6)
    name_vw = min(10.5, 84 / (0.9 * chars))
    name_px = min(128, 990 / (0.9 * chars))
    name_style = f"font-size: max(28px, min({name_vw:.2f}vw, {name_px:.0f}px));"
    name_html = esc(name).replace(".", ".<wbr>")

    prepared_for = ""
    if project_name and project_name.lower() != name:
        prepared_for = f'<p class="prepared">workspace: {esc(project_name)}</p>'

    tiles = "".join(f"""
        <div class="tile level-{esc(t['level'])}">
          <p class="tile-label">{esc(t['label'])}</p>
          <p class="tile-value">{esc(t['value'])}</p>
          {pill(t['level'])}
        </div>""" for t in summary["tiles"])

    if summary["priorities"]:
        priorities = "".join(f"""
          <li class="level-{esc(p['level'])}">
            {pill(p['level'])}
            <div><strong>{esc(p['label'])}</strong> <span class="pri-value">{esc(p['value'])}</span>
            <p>{esc(p['verdict'])}</p></div>
          </li>""" for p in summary["priorities"])
        priorities_html = f"""
      <section class="panel priorities">
        <p class="kicker">( priorities )</p>
        <h2>fix these first</h2>
        <p class="intro">The weakest results, worst first. Each one is explained in full further down.</p>
        <ol>{priorities}</ol>
      </section>"""
    else:
        priorities_html = """
      <section class="panel priorities">
        <p class="kicker">( priorities )</p>
        <h2>Nothing urgent</h2>
        <p class="intro">Every graded check passed. Keep an eye on speed and backlinks over time.</p>
      </section>"""

    nav = "".join(f'<a href="#{esc(s["key"])}">{esc(s["kicker"])}</a>' for s in sections)
    body_sections = "".join(render_section(s, i + 1) for i, s in enumerate(sections))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(name)} · site audit · reqless design co.</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS_URL}">
<style>
  :root {{
    --dead-air: {DEAD_AIR}; --noise: {NOISE}; --snow: {SNOW};
    --glitch: {GLITCH}; --carrier: {CARRIER}; --phosphor: {PHOSPHOR}; --live: {LIVE};
    --line: color-mix(in srgb, var(--snow) 12%, transparent);
    --line-strong: color-mix(in srgb, var(--snow) 22%, transparent);
    --muted: color-mix(in srgb, var(--snow) 72%, transparent);
    --faint: color-mix(in srgb, var(--snow) 58%, transparent);
    --font-display: "apotek-extrawide", "Unbounded", "Arial Black", sans-serif;
    --font-body: "aktiv-grotesk", "Instrument Sans", "Helvetica Neue", Arial, sans-serif;
    --font-mono: "Space Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
    --gutter: clamp(16px, 4vw, 64px);
    --radius-card: 20px; --radius-panel: 28px;
    --good: var(--phosphor); --warn: var(--live); --poor: var(--glitch); --info: var(--muted); --na: var(--faint);
    color-scheme: dark;
  }}
  * {{ box-sizing: border-box; }}
  html {{ scroll-behavior: smooth; }}
  body {{ margin: 0; background: var(--dead-air); color: var(--snow); font-family: var(--font-body);
         font-size: 17px; line-height: 1.55; -webkit-font-smoothing: antialiased; }}
  body::before {{ content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 10;
                  background: linear-gradient(#00000038 0 1px, #0000 1px 3px); opacity: .35; }}
  a {{ color: inherit; }}
  .wrap {{ max-width: 1120px; margin: 0 auto; padding: 0 var(--gutter); }}
  .mono, .kicker, .topbar, .tile-label, .pill, .guide span, nav a, footer {{
    font-family: var(--font-mono); text-transform: uppercase; letter-spacing: .08em; }}

  /* top bar */
  .topbar {{ display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap; font-size: 12px;
             color: var(--faint); padding: 24px 0; border-bottom: 1px solid var(--line); }}
  .brand {{ color: var(--snow); text-transform: lowercase; letter-spacing: .02em; font-size: 14px; }}
  .brand b {{ color: var(--glitch); font-weight: 400; }}

  /* hero */
  .hero {{ padding: clamp(48px, 9vw, 120px) 0 clamp(32px, 6vw, 72px); position: relative; }}
  .hero .kicker {{ color: var(--glitch); font-size: 13px; margin: 0 0 18px; }}
  .site-name {{ font-family: var(--font-display); font-weight: 900; font-feature-settings: "ss02";
                font-size: clamp(40px, 10.5vw, 128px); line-height: .92; letter-spacing: -.02em;
                margin: 0; text-transform: lowercase; overflow-wrap: normal; word-break: normal;
                text-shadow: 3px 0 var(--carrier), -3px 0 var(--phosphor); }}
  .hero-meta {{ display: flex; flex-wrap: wrap; gap: 12px 28px; margin-top: 28px; align-items: center; }}
  .hero-meta a {{ font-family: var(--font-mono); font-size: 14px; color: var(--muted); text-decoration: none;
                  border-bottom: 1px solid var(--line-strong); padding-bottom: 2px; overflow-wrap: anywhere; }}
  .hero-meta a:hover {{ color: var(--snow); border-color: var(--glitch); }}
  .prepared {{ margin: 0; font-family: var(--font-mono); font-size: 13px; color: var(--faint); text-transform: lowercase; }}
  .coords {{ position: absolute; right: 0; top: clamp(48px, 9vw, 120px); font-family: var(--font-mono);
             font-size: 11px; color: var(--faint); letter-spacing: .08em; text-align: right; }}

  /* summary */
  .counts {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 0 0 20px; }}
  .tiles {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }}
  .tile {{ background: var(--noise); border-radius: var(--radius-card); padding: 24px; display: flex;
           flex-direction: column; gap: 10px; border-top: 3px solid var(--tone, var(--line-strong)); }}
  .tile-label {{ margin: 0; font-size: 12px; color: var(--muted); }}
  .tile-value {{ margin: 0; font-family: var(--font-display); font-weight: 700; font-size: clamp(22px, 2.4vw, 30px);
                 line-height: 1.1; color: var(--tone, var(--snow)); overflow-wrap: anywhere; }}
  .tile .pill {{ align-self: flex-start; }}

  nav.jump {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 40px 0 0; }}
  nav.jump a {{ font-size: 12px; text-decoration: none; border: 1px solid var(--line-strong); border-radius: 999px;
                padding: 6px 14px; color: var(--snow); transition: border-color .15s, background .15s; }}
  nav.jump a:hover {{ border-color: var(--glitch); background: color-mix(in srgb, var(--glitch) 14%, transparent); }}

  /* panels */
  .panel {{ background: var(--noise); border-radius: var(--radius-panel); padding: clamp(24px, 4vw, 48px); margin-top: 24px; }}
  .panel .kicker {{ color: var(--glitch); font-size: 13px; margin: 0 0 10px; }}
  .panel .num {{ color: var(--faint); margin-right: 6px; }}
  .panel h2 {{ font-family: var(--font-display); font-weight: 900; font-size: clamp(26px, 3.4vw, 44px);
               line-height: 1.05; margin: 0 0 10px; text-transform: lowercase; letter-spacing: -.01em; }}
  .panel h3 {{ font-family: var(--font-mono); font-weight: 700; font-size: 13px; text-transform: uppercase;
               letter-spacing: .08em; color: var(--muted); margin: 36px 0 12px; padding-top: 24px;
               border-top: 1px solid var(--line); }}
  .intro {{ color: var(--muted); margin: 0 0 24px; max-width: 62ch; }}
  .note {{ color: var(--muted); font-size: 15px; margin: 0 0 14px; max-width: 70ch; }}

  .metrics {{ display: grid; gap: 12px; }}
  .metric {{ background: var(--dead-air); border-radius: 16px; padding: 20px 22px; border-left: 4px solid var(--tone, var(--line-strong)); }}
  .metric-head {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
  .metric h4 {{ margin: 0; font-size: 17px; font-weight: 600; }}
  .metric-value {{ margin: 6px 0 0; overflow-wrap: anywhere; }}
  .value-score {{ font-size: 20px; font-weight: 700; color: var(--snow); line-height: 1.3; }}
  .value-text {{ font-size: 17px; font-weight: 400; color: var(--muted); }}
  .verdict {{ margin: 10px 0 0; color: var(--snow); font-size: 18.5px; letter-spacing: .012em; }}
  .guide {{ margin: 10px 0 0; font-size: 14px; color: var(--snow); }}
  .guide span {{ display: block; font-size: 11px; color: var(--faint); margin-bottom: 2px; }}
  .why {{ margin: 8px 0 0; font-size: 14px; color: var(--muted); }}

  .pill {{ display: inline-block; font-size: 11px; padding: 4px 10px; border-radius: 999px; white-space: nowrap;
           color: var(--tone, var(--snow)); border: 1px solid var(--tone, var(--line-strong));
           background: color-mix(in srgb, var(--tone, transparent) 14%, transparent); }}
  .level-good, .pill-good {{ --tone: var(--good); }}
  .level-warn, .pill-warn {{ --tone: var(--warn); }}
  .level-poor, .pill-poor {{ --tone: var(--poor); }}
  .level-info, .pill-info {{ --tone: var(--info); }}
  .level-na, .pill-na {{ --tone: var(--na); }}
  .metric.level-poor {{ box-shadow: 0 0 0 1px color-mix(in srgb, var(--glitch) 35%, transparent), 0 10px 40px -18px color-mix(in srgb, var(--glitch) 70%, transparent); }}

  .priorities ol {{ list-style: none; padding: 0; margin: 0; display: grid; gap: 12px; }}
  .priorities li {{ display: grid; grid-template-columns: 110px 1fr; gap: 16px; align-items: start;
                    background: var(--dead-air); border-radius: 16px; padding: 18px 20px; }}
  .priorities li .pill {{ justify-self: start; margin-top: 3px; }}
  .priorities li p {{ margin: 4px 0 0; color: var(--muted); font-size: 15px; }}
  .pri-value {{ font-family: var(--font-mono); font-size: 13px; color: var(--faint); margin-left: 6px; }}

  .plain-list {{ margin: 0; padding: 0; list-style: none; display: grid; gap: 6px; counter-reset: n; }}
  .plain-list li {{ font-family: var(--font-mono); font-size: 14px; background: var(--dead-air); border-radius: 10px;
                    padding: 10px 14px; overflow-wrap: anywhere; }}

  .legend {{ display: flex; flex-wrap: wrap; gap: 8px 18px; font-size: 13px; color: var(--muted); margin-top: 16px; }}
  .legend span {{ display: inline-flex; align-items: center; gap: 8px; }}
  .legend i {{ width: 10px; height: 10px; border-radius: 50%; background: var(--tone); box-shadow: 0 0 10px var(--tone); }}

  footer {{ margin: 64px 0 0; padding: 32px 0 48px; border-top: 1px solid var(--line); font-size: 12px;
            color: var(--faint); display: flex; justify-content: space-between; flex-wrap: wrap; gap: 12px; }}
  footer b {{ color: var(--glitch); font-weight: 400; }}

  @media (max-width: 820px) {{
    .tiles {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .coords {{ display: none; }}
  }}
  @media (max-width: 480px) {{
    .tiles {{ grid-template-columns: 1fr; }}
    .priorities li {{ grid-template-columns: 1fr; gap: 8px; }}
  }}
  @media print {{
    body {{ background: #fff; color: #141419; font-size: 12pt; }}
    body::before, nav.jump, .coords {{ display: none; }}
    :root {{ --snow: #141419; --muted: #4a4a55; --faint: #6a6a75; --line: #ddd; --line-strong: #ccc; --noise: #f3f3f6; --dead-air: #fff; }}
    .site-name {{ text-shadow: none; }}
    .panel, .metric, .tile, .priorities li {{ break-inside: avoid; }}
  }}
</style>
</head>
<body>
  <div class="wrap">
    <header class="topbar">
      <span class="brand">reqless <b>(</b> design <b>)</b> co.</span>
      <span>shadeglass site audit // {esc(generated.strftime('%d %b %Y'))}</span>
    </header>

    <section class="hero">
      <p class="kicker">// site audit for</p>
      <h1 class="site-name" style="{name_style}">{name_html}</h1>
      <div class="hero-meta">
        <a href="{esc(url)}" target="_blank" rel="noopener">{esc(url)} ↗</a>
        {prepared_for}
      </div>
      <div class="coords">x:{len(name):04d} y:{generated.year:04d}<br>( signal ↓ )</div>
    </section>

    <div class="counts">
      <span class="pill pill-good">{counts['good']} good</span>
      <span class="pill pill-warn">{counts['warn']} need work</span>
      <span class="pill pill-poor">{counts['poor']} poor</span>
    </div>
    <div class="tiles">{tiles}</div>
    <div class="legend">
      <span class="level-good"><i></i>Good: meets the target</span>
      <span class="level-warn"><i></i>Needs work: room to improve</span>
      <span class="level-poor"><i></i>Poor: fix this first</span>
      <span class="level-info"><i></i>Info: for context, not graded</span>
    </div>

    {priorities_html}

    <nav class="jump">{nav}</nav>

    {body_sections}

    <footer>
      <span>built with shadeglass · reqless <b>(</b> design <b>)</b> co.</span>
      <span>time to get reqless →</span>
    </footer>
  </div>
</body>
</html>
"""
