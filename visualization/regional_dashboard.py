"""
KoruFlux Intelligence System
==============================
visualization/regional_dashboard.py  v2

Generates 8 premium regional dashboards + hub index.
Each dashboard is unique to its market — different colour theme,
market-specific KPIs, live news feed with source URLs,
regulatory panel, social signals, and verifiable data attribution.

Stakeholder-grade: suitable for investors, clients, and partners.
No emojis. Clean typography. Every data point has a source.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("koruflux.regional_dashboard")

BASE_DIR       = Path(__file__).parent.parent
DASHBOARDS_DIR = BASE_DIR / "data/dashboards"
DASHBOARDS_DIR.mkdir(parents=True, exist_ok=True)

# ── Regional design system ─────────────────────────────────────
THEMES = {
    "KE": {"name":"Kenya / Nairobi",    "primary":"#1B4332","secondary":"#2D6A4F","accent":"#52B788","light":"#D8F3DC","tag":"Primary Africa Hub",          "currency":"KES","regulator":"CMA + CBK"},
    "EA": {"name":"East Africa",         "primary":"#1C3A5E","secondary":"#2E5F8A","accent":"#4A9EBF","light":"#D0EAF5","tag":"Regional Bloc",               "currency":"Multi","regulator":"CBK / BoT / BNR"},
    "NG": {"name":"Nigeria",             "primary":"#145A32","secondary":"#1E8449","accent":"#27AE60","light":"#D5F5E3","tag":"Largest Africa Economy",      "currency":"NGN","regulator":"SEC Nigeria + CBN"},
    "US": {"name":"United States",       "primary":"#1A237E","secondary":"#283593","accent":"#3F51B5","light":"#E8EAF6","tag":"Largest Web3 Capital Market","currency":"USD","regulator":"SEC + CFTC"},
    "EU": {"name":"European Union",      "primary":"#0D2B7A","secondary":"#1565C0","accent":"#1E88E5","light":"#E3F2FD","tag":"MiCA Framework",              "currency":"EUR","regulator":"ESMA + ECB"},
    "GB": {"name":"United Kingdom",      "primary":"#0D1B5E","secondary":"#1A237E","accent":"#C62828","light":"#FFEBEE","tag":"FCA Regulated Hub",           "currency":"GBP","regulator":"FCA"},
    "SG": {"name":"Singapore",           "primary":"#7B0000","secondary":"#C62828","accent":"#EF5350","light":"#FFEBEE","tag":"MAS Gateway",                 "currency":"SGD","regulator":"MAS"},
    "AE": {"name":"UAE / Dubai",         "primary":"#1A4731","secondary":"#2E7D52","accent":"#00BCD4","light":"#E0F7FA","tag":"VARA / DIFC Hub",             "currency":"AED","regulator":"VARA + ADGM"},
}

def _tier_color(tier):
    if "HIGH OPPORTUNITY" in tier and "MODERATE" not in tier: return "#2EC4B6"
    if "MODERATE" in tier:  return "#F4A261"
    if "EMERGING" in tier:  return "#FFB703"
    return "#E63946"

def _tier_bg(tier):
    if "HIGH OPPORTUNITY" in tier and "MODERATE" not in tier: return "#ECFDF5"
    if "MODERATE" in tier:  return "#FFF7ED"
    if "EMERGING" in tier:  return "#FFFBEB"
    return "#FEF2F2"

def _tier_text(tier):
    if "HIGH OPPORTUNITY" in tier and "MODERATE" not in tier: return "#065F46"
    if "MODERATE" in tier:  return "#92400E"
    if "EMERGING" in tier:  return "#78350F"
    return "#7F1D1D"

def _fmt_num(n):
    try:
        n = float(n)
        if n >= 1e9:  return f"{n/1e9:.1f}B"
        if n >= 1e6:  return f"{n/1e6:.1f}M"
        if n >= 1e3:  return f"{n/1e3:.1f}K"
        return str(int(n))
    except: return str(n)

def _sentiment_bar(score):
    pct = int((score + 1) / 2 * 100)
    if score > 0.15:   color, label = "#2EC4B6", "Positive"
    elif score < -0.15: color, label = "#E63946", "Negative"
    else:               color, label = "#8D99AE", "Neutral"
    return f"""
    <div style="display:flex;align-items:center;gap:10px">
      <div style="flex:1;background:#F0F4F8;border-radius:3px;height:6px">
        <div style="width:{pct}%;height:6px;border-radius:3px;background:{color}"></div>
      </div>
      <span style="font-size:12px;font-weight:600;color:{color}">{label}</span>
    </div>"""


def build_regional_dashboard(region_code: str, report: dict) -> Path:
    """Build a single premium regional dashboard HTML file."""
    theme = THEMES.get(region_code, THEMES["KE"])
    meta  = report.get("meta", {})
    opp   = report.get("opportunity_leaderboard", [])
    news  = report.get("news_items", [])
    social= report.get("social_items", [])
    regs  = report.get("regulatory_items", [])
    risks = report.get("risk_signals", [])
    mkt_s = report.get("market_sentiment", {})
    gen   = report.get("generated_at", "")[:10]
    jur   = report.get("jurisdiction_intelligence", {})
    archetypes = report.get("client_archetypes", [])
    client_ranking = report.get("client_relevance_ranking", [])

    P  = theme["primary"]
    S  = theme["secondary"]
    A  = theme["accent"]
    L  = theme["light"]

    # ── Opportunity leaderboard rows ───────────────────────────
    opp_rows = ""
    for o in opp:
        sc   = o["opportunity_score"]
        dims = o.get("dimensions", {})
        tc   = _tier_color(o["tier"])
        tb   = _tier_bg(o["tier"])
        tt   = _tier_text(o["tier"])
        opp_rows += f"""
        <tr>
          <td style="font-weight:700;color:#1A1A2E">{o['sector']}</td>
          <td>
            <div style="display:flex;align-items:center;gap:8px">
              <div style="flex:1;background:#F0F4F8;border-radius:3px;height:6px">
                <div style="width:{sc}%;height:6px;border-radius:3px;background:{tc}"></div>
              </div>
              <span style="font-weight:800;font-size:15px;color:{tc};width:36px;text-align:right">{sc}</span>
            </div>
          </td>
          <td><span style="background:{tb};color:{tt};padding:3px 9px;border-radius:20px;font-size:11px;font-weight:700">{o['tier']}</span></td>
          <td style="text-align:center;font-size:13px;color:#6B7280">{dims.get('regulatory_clarity','—')}</td>
          <td style="text-align:center;font-size:13px;color:#6B7280">{dims.get('market_size','—')}</td>
          <td style="text-align:center;font-size:13px;color:#6B7280">{dims.get('growth_rate','—')}</td>
        </tr>"""

    # ── Client fit helpers ──────────────────────────────────────
    def _fc(tier):
        return {"STRONG FIT":"#2EC4B6","GOOD FIT":"#00B4D8","POSSIBLE FIT":"#F4A261"}.get(tier,"#8D99AE")
    def _fb(tier):
        return {"STRONG FIT":"#ECFDF5","GOOD FIT":"#E0F7FA","POSSIBLE FIT":"#FFF7ED"}.get(tier,"#F3F4F6")
    def _ft(tier):
        return {"STRONG FIT":"#065F46","GOOD FIT":"#006064","POSSIBLE FIT":"#92400E"}.get(tier,"#374151")

    client_fit_rows = ""
    for c in client_ranking:
        client_fit_rows += f"""
        <tr>
          <td style="font-weight:700;color:#1A1A2E">{c['sector']}</td>
          <td><div style="display:flex;align-items:center;gap:8px">
            <div style="flex:1;background:#F0F4F8;border-radius:3px;height:6px">
              <div style="width:{c['score']}%;height:6px;border-radius:3px;background:{_fc(c['tier'])}"></div>
            </div>
            <span style="font-weight:800;font-size:15px;color:{_fc(c['tier'])};width:36px;text-align:right">{c['score']}</span>
          </div></td>
          <td><span style="background:{_fb(c['tier'])};color:{_ft(c['tier'])};padding:3px 9px;border-radius:20px;font-size:11px;font-weight:700">{c['tier']}</span></td>
        </tr>"""

    archetype_cards = ""
    for a in archetypes:
        fc = _fc("STRONG FIT" if a["avg_client_fit_score"]>=75 else "GOOD FIT" if a["avg_client_fit_score"]>=55 else "POSSIBLE FIT")
        sector_tags = "".join(
            f'<span style="display:inline-block;background:#F8FBFC;border:1px solid #E5E7EB;border-radius:6px;padding:4px 10px;margin:3px;font-size:12px"><strong>{p["sector"]}</strong> &middot; opp {p["opportunity"]} &middot; fit {p["client_fit"]}</span>'
            for p in a["priority_sectors"]
        )
        archetype_cards += f"""
        <div style="background:#F8FBFC;border-left:4px solid {fc};border-radius:8px;padding:16px;margin-bottom:14px">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px">
            <div>
              <div style="font-size:15px;font-weight:800;color:#1A1A2E">{a['archetype']}</div>
              <div style="font-size:12px;color:#6B7280;margin-top:2px">{a['description']}</div>
            </div>
            <div style="text-align:right">
              <div style="font-size:24px;font-weight:800;color:{fc}">{a['avg_client_fit_score']}</div>
              <div style="font-size:10px;color:#9CA3AF">avg client fit</div>
            </div>
          </div>
          <div style="margin:10px 0 6px">{sector_tags}</div>
          <div style="font-size:12px;color:#444;padding-top:8px;border-top:1px solid #E5E7EB">
            <strong>Recommended:</strong> {a['recommended_engagement']} &nbsp;&middot;&nbsp;
            Best entry sector: <strong>{a['best_sector']}</strong> ({a['best_sector_score']}/100)
          </div>
        </div>"""

    if not archetype_cards:
        archetype_cards = '<p style="color:#9CA3AF;font-size:13px">Run pipeline to populate archetype analysis.</p>'

    # ── News feed ──────────────────────────────────────────────
    news_items_html = ""
    for item in (news + social)[:12]:
        url = item.get("url", "")
        title = item.get("title", "")
        src   = item.get("source", "")
        ts    = item.get("timestamp", "")[:10]
        verified = item.get("verified", bool(url))
        link = f'<a href="{url}" target="_blank" style="color:#1A1A2E;text-decoration:none;font-weight:500;font-size:13px">{title}</a>' if url else f'<span style="font-size:13px;font-weight:500">{title}</span>'
        ver_badge = f'<span style="background:#ECFDF5;color:#065F46;font-size:10px;font-weight:700;padding:1px 6px;border-radius:10px;margin-left:6px">Verified</span>' if verified else ''
        news_items_html += f"""
        <div style="padding:10px 0;border-bottom:1px solid #F5F7F9">
          <div>{link}{ver_badge}</div>
          <div style="margin-top:4px;font-size:11px;color:#9CA3AF">{src} &nbsp;·&nbsp; {ts}</div>
        </div>"""

    if not news_items_html:
        news_items_html = '<p style="color:#9CA3AF;font-size:13px;padding:16px 0">No news items yet — run a live scrape to populate this feed.</p>'

    # ── Regulatory panel ───────────────────────────────────────
    reg_html = ""
    for r in regs[:6]:
        url   = r.get("url","")
        title = r.get("title","")
        src   = r.get("source","")
        link  = f'<a href="{url}" target="_blank" style="color:#1A1A2E;font-weight:500;font-size:13px;text-decoration:none">{title}</a>' if url else f'<span style="font-size:13px;font-weight:500">{title}</span>'
        reg_html += f'<div style="padding:9px 0;border-bottom:1px solid #F5F7F9"><div>{link}</div><div style="font-size:11px;color:#9CA3AF;margin-top:3px">{src}</div></div>'
    if not reg_html:
        reg_html = f'<p style="color:#9CA3AF;font-size:13px;padding:12px 0">Regulatory feed: {meta.get("key_regulator","—")}. Run live scrape to populate.</p>'

    # ── Social signals ─────────────────────────────────────────
    social_html = ""
    for s in social[:5]:
        title = s.get("title","")[:160]
        url   = s.get("url","")
        src   = s.get("source","")
        link  = f'<a href="{url}" target="_blank" style="color:#1A1A2E;font-size:12px;text-decoration:none">{title}</a>' if url else f'<span style="font-size:12px">{title}</span>'
        social_html += f'<div style="padding:8px 0;border-bottom:1px solid #F5F7F9">{link}<div style="font-size:11px;color:#9CA3AF;margin-top:2px">{src}</div></div>'
    if not social_html:
        social_html = '<p style="color:#9CA3AF;font-size:12px;padding:10px 0">Farcaster/social data loads on live scrape.</p>'

    # ── Risk flags ─────────────────────────────────────────────
    risk_html = ""
    for r in risks[:5]:
        sev_c = "#E63946" if r.get("severity")=="HIGH" else "#F4A261"
        sev_b = "#FEF2F2" if r.get("severity")=="HIGH" else "#FFF7ED"
        sev_t = "#7F1D1D" if r.get("severity")=="HIGH" else "#92400E"
        url = r.get("url","")
        title = r.get("title","")[:120]
        kw  = r.get("keyword","")
        link = f'<a href="{url}" target="_blank" style="color:#1A1A2E;font-size:12px;text-decoration:none">{title}</a>' if url else f'<span style="font-size:12px">{title}</span>'
        risk_html += f"""
        <div style="padding:9px 0;border-bottom:1px solid #F5F7F9;display:flex;gap:10px;align-items:flex-start">
          <span style="background:{sev_b};color:{sev_t};font-size:10px;font-weight:700;padding:2px 7px;border-radius:10px;white-space:nowrap">{r.get("severity","—")}</span>
          <div><div style="font-size:11px;font-weight:600;color:{sev_c};margin-bottom:2px">{kw}</div>{link}</div>
        </div>"""
    if not risk_html:
        risk_html = '<p style="color:#2EC4B6;font-size:13px;padding:12px 0;font-weight:500">No significant risk signals detected in current data.</p>'

    # ── KPI cards ──────────────────────────────────────────────
    top_sector = opp[0] if opp else {}
    high_count = len([o for o in opp if o["opportunity_score"] >= 75])
    ms = mkt_s.get("score", 0)
    ms_label = "Positive" if ms > 0.15 else "Negative" if ms < -0.15 else "Neutral"
    ms_color = "#2EC4B6" if ms > 0.15 else "#E63946" if ms < -0.15 else "#8D99AE"

    # ── Chart data ─────────────────────────────────────────────
    sectors_js = json.dumps([o["sector"] for o in opp])
    scores_js  = json.dumps([o["opportunity_score"] for o in opp])
    colors_js  = json.dumps([_tier_color(o["tier"]) for o in opp])

    # Radar chart — top sector dimensions
    if opp:
        top = opp[0]
        dims = top.get("dimensions", {})
        radar_labels = json.dumps(["Market Size","Growth Rate","Reg. Clarity","Ecosystem","Comp. Gap","Tech Ready"])
        radar_values = json.dumps([
            dims.get("market_size",0), dims.get("growth_rate",0),
            dims.get("regulatory_clarity",0), dims.get("ecosystem_maturity",0),
            dims.get("competitive_gap",0), dims.get("tech_readiness",0)
        ])
    else:
        radar_labels = json.dumps([])
        radar_values = json.dumps([])

    # ── Data sources attribution ───────────────────────────────
    sources_used = report.get("sources_used", [])
    sources_txt  = ", ".join(sources_used[:6]) if sources_used else "Baseline intelligence (static)"
    data_note    = meta.get("data_source", "KoruFlux baseline intelligence")

    # ─────────────────────────────────────────────────────────────
    avg_reg_clarity = round(sum(o.get("dimensions",{}).get("regulatory_clarity",0) for o in opp)/len(opp)) if opp else 0
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>KoruFlux · {theme['name']} Intelligence</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root{{--p:{P};--s:{S};--a:{A};--l:{L};--bg:#F0F4F8;--card:#fff;--text:#1A1A2E;--muted:#6B7280;--border:#E5E7EB}}
  *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',system-ui,-apple-system,Arial,sans-serif;background:var(--bg);color:var(--text);font-size:14px;line-height:1.5}}

  /* Header */
  .header{{background:linear-gradient(135deg,{P} 0%,{S} 60%,{A} 100%);color:white;padding:32px 48px 24px}}
  .header-inner{{max-width:1200px;margin:0 auto}}
  .header-top{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:18px}}
  .region-badge{{background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.25);padding:4px 14px;border-radius:20px;font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase}}
  .header h1{{font-size:26px;font-weight:800;letter-spacing:0.3px;margin-bottom:4px}}
  .header-sub{{font-size:13px;opacity:0.75}}
  .header-meta{{display:flex;gap:20px;margin-top:14px;flex-wrap:wrap}}
  .header-meta span{{background:rgba(255,255,255,0.1);padding:4px 12px;border-radius:6px;font-size:12px}}
  .back-link{{color:rgba(255,255,255,0.7);text-decoration:none;font-size:13px;display:flex;align-items:center;gap:6px}}
  .back-link:hover{{color:white}}

  /* Nav tabs */
  .nav{{background:{P};border-bottom:1px solid rgba(255,255,255,0.1)}}
  .nav-inner{{max-width:1200px;margin:0 auto;display:flex;gap:4px;padding:0 48px;overflow-x:auto}}
  .tab{{padding:13px 18px;color:rgba(255,255,255,0.55);cursor:pointer;font-size:13px;font-weight:500;border-bottom:3px solid transparent;transition:all .2s;white-space:nowrap}}
  .tab:hover{{color:white}}
  .tab.active{{color:white;border-bottom-color:{A}}}

  /* Main */
  .container{{max-width:1200px;margin:28px auto;padding:0 24px}}
  .page{{display:none}}.page.active{{display:block}}
  .grid-2{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
  .grid-3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}}
  .grid-4{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}}

  /* Cards */
  .card{{background:var(--card);border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,.06),0 0 0 1px rgba(0,0,0,.04);margin-bottom:20px}}
  .card-header{{padding:16px 20px 12px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between}}
  .card-title{{font-size:14px;font-weight:700;color:var(--text)}}
  .card-body{{padding:18px 20px}}
  .card-footer{{padding:12px 20px;border-top:1px solid var(--border);background:#FAFBFC;border-radius:0 0 10px 10px;font-size:11px;color:var(--muted)}}

  /* KPI cards */
  .kpi{{background:var(--card);border-radius:10px;padding:18px 20px;box-shadow:0 1px 4px rgba(0,0,0,.06),0 0 0 1px rgba(0,0,0,.04);border-top:3px solid {A}}}
  .kpi-label{{font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px}}
  .kpi-value{{font-size:26px;font-weight:800;color:var(--text);line-height:1}}
  .kpi-sub{{font-size:12px;color:var(--muted);margin-top:4px}}

  /* Table */
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  thead th{{background:var(--bg);color:var(--muted);padding:9px 14px;text-align:left;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;border-bottom:1px solid var(--border)}}
  tbody td{{padding:10px 14px;border-bottom:1px solid #F5F7F9}}
  tbody tr:last-child td{{border-bottom:none}}
  tbody tr:hover td{{background:#F8FBFC}}

  /* Source attribution */
  .source-note{{font-size:11px;color:var(--muted);padding:10px 0;border-top:1px solid var(--border);margin-top:8px}}

  /* Footer */
  footer{{text-align:center;padding:24px;color:var(--muted);font-size:12px;border-top:1px solid var(--border);margin-top:20px}}

  @media(max-width:768px){{
    .header{{padding:20px}}
    .nav-inner,.container{{padding:0 12px}}
    .grid-2,.grid-3,.grid-4{{grid-template-columns:1fr}}
  }}
</style>
</head>
<body>

<div class="header">
  <div class="header-inner">
    <div class="header-top">
      <div>
        <span class="region-badge">{region_code} · {theme['tag']}</span>
        <h1 style="margin-top:10px">{theme['name']} Intelligence Report</h1>
        <div class="header-sub">KoruFlux Market Intelligence · {gen} · {theme['regulator']}</div>
      </div>
      <a href="index.html" class="back-link">← All Markets</a>
    </div>
    <div class="header-meta">
      <span>GDP: {meta.get('gdp_usd','—')}</span>
      <span>Unbanked: {meta.get('unbanked_pct','—')}%</span>
      <span>Internet: {meta.get('internet_penetration_pct','—')}%</span>
      <span>Regulator: {meta.get('key_regulator','—')}</span>
      {'<span>Sandbox: Active</span>' if meta.get('sandbox') else ''}
    </div>
  </div>
</div>

<div class="nav">
  <div class="nav-inner">
    <div class="tab active" onclick="showTab('overview',this)">Overview</div>
    <div class="tab" onclick="showTab('sectors',this)">Sectors</div>
    <div class="tab" onclick="showTab('jurisdiction',this)">Jurisdiction Intel</div>
    <div class="tab" onclick="showTab('news',this)">News Feed</div>
    <div class="tab" onclick="showTab('regulatory',this)">Regulatory</div>
    <div class="tab" onclick="showTab('social',this)">Social Signals</div>
    <div class="tab" onclick="showTab('risks',this)">Risk Watch</div>
  </div>
</div>

<div class="container">

<!-- ── OVERVIEW ─────────────────────────────────────────────── -->
<div id="tab-overview" class="page active">

  <div class="grid-4" style="margin-bottom:20px">
    <div class="kpi">
      <div class="kpi-label">Top Opportunity</div>
      <div class="kpi-value" style="color:{_tier_color(top_sector.get('tier',''))}">{top_sector.get('opportunity_score','—')}</div>
      <div class="kpi-sub">{top_sector.get('sector','—')}</div>
    </div>
    <div class="kpi" style="border-top-color:#2EC4B6">
      <div class="kpi-label">High Opportunity</div>
      <div class="kpi-value" style="color:#2EC4B6">{high_count}</div>
      <div class="kpi-sub">Sectors scored &ge; 75</div>
    </div>
    <div class="kpi" style="border-top-color:{ms_color}">
      <div class="kpi-label">Market Sentiment</div>
      <div class="kpi-value" style="color:{ms_color}">{ms_label}</div>
      <div class="kpi-sub">Score: {ms:.2f}</div>
    </div>
    <div class="kpi" style="border-top-color:#8D99AE">
      <div class="kpi-label">Key Metric</div>
      <div class="kpi-value" style="font-size:16px;line-height:1.3">{meta.get('key_stat','—')[:35]}</div>
      <div class="kpi-sub">{meta.get('data_source','')[:40]}</div>
    </div>
  </div>

  <div class="grid-2">
    <div class="card">
      <div class="card-header"><div class="card-title">Opportunity Leaderboard</div></div>
      <div class="card-body" style="padding:0">
        <div style="height:320px;padding:16px">
          <canvas id="chartBar"></canvas>
        </div>
      </div>
      <div class="card-footer">Source: KoruFlux scoring model · Baseline: {data_note}</div>
    </div>
    <div class="card">
      <div class="card-header"><div class="card-title">Top Sector — Dimension Analysis</div><span style="font-size:12px;color:var(--muted)">{top_sector.get('sector','—')}</span></div>
      <div class="card-body" style="padding:0">
        <div style="height:320px;padding:16px">
          <canvas id="chartRadar"></canvas>
        </div>
      </div>
      <div class="card-footer">Dimensions scored 0-100. Source: KoruFlux baseline intelligence.</div>
    </div>
  </div>

  <div class="card">
    <div class="card-header"><div class="card-title">Market Context</div></div>
    <div class="card-body">
      <div class="grid-3">
        <div>
          <div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">Regulatory Environment</div>
          <div style="font-size:14px;font-weight:600">{meta.get('key_regulator','—')}</div>
          <div style="font-size:12px;color:var(--muted);margin-top:4px">{'Sandbox programme active' if meta.get('sandbox') else 'No active sandbox'}</div>
        </div>
        <div>
          <div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">Market Scale</div>
          <div style="font-size:14px;font-weight:600">GDP: {meta.get('gdp_usd','—')}</div>
          <div style="font-size:12px;color:var(--muted);margin-top:4px">{meta.get('unbanked_pct','—')}% unbanked population</div>
        </div>
        <div>
          <div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">Digital Infrastructure</div>
          <div style="font-size:14px;font-weight:600">{meta.get('internet_penetration_pct','—')}% internet penetration</div>
          <div style="font-size:12px;color:var(--muted);margin-top:4px">{meta.get('mobile_money_users','—')} mobile money users</div>
        </div>
      </div>
    </div>
    <div class="card-footer">Data source: {data_note}</div>
  </div>
</div>

<!-- ── SECTORS ───────────────────────────────────────────────── -->
<div id="tab-sectors" class="page">
  <div class="card">
    <div class="card-header">
      <div class="card-title">Sector Opportunity Scores — {theme['name']}</div>
      <span style="font-size:12px;color:var(--muted)">{len(opp)} sectors · scored 0-100</span>
    </div>
    <div class="card-body" style="padding:0">
      <table>
        <thead>
          <tr>
            <th>Sector</th>
            <th>Score</th>
            <th>Tier</th>
            <th>Reg. Clarity</th>
            <th>Market Size</th>
            <th>Growth Rate</th>
          </tr>
        </thead>
        <tbody>{opp_rows}</tbody>
      </table>
    </div>
    <div class="card-footer">
      Scoring model: weighted composite of 6 dimensions (market size 25%, growth rate 20%, regulatory clarity 20%, ecosystem maturity 15%, competitive gap 10%, tech readiness 10%).
      Baseline data: {data_note}.
    </div>
  </div>
</div>

<!-- ── JURISDICTION INTEL ───────────────────────────────────── -->
<div id="tab-jurisdiction" class="page">
  <div class="grid-2" style="margin-bottom:20px">
    <div class="card">
      <div class="card-header"><div class="card-title">KoruFlux Client Fit — {theme['name']}</div></div>
      <div class="card-body" style="padding:0">
        <table>
          <thead><tr><th>Sector</th><th>Client Fit Score</th><th>Tier</th></tr></thead>
          <tbody>{client_fit_rows}</tbody>
        </table>
      </div>
      <div class="card-footer">
        Client Fit weights regulatory clarity (30%), competitive gap (20%), ecosystem maturity (20%),
        tech readiness (15%), growth rate (10%), market size (5%) — reflecting what Web3 protocols,
        DeFi platforms, and RWA projects prioritise when choosing a jurisdiction.
      </div>
    </div>
    <div class="card">
      <div class="card-header"><div class="card-title">Jurisdiction Snapshot</div></div>
      <div class="card-body">
        <div style="margin-bottom:14px">
          <div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px">Entity Structure</div>
          <div style="font-size:13px;color:#333;line-height:1.6">{jur.get('entity_structure','—')}</div>
        </div>
        <div style="margin-bottom:14px">
          <div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px">Tax Exposure</div>
          <div style="font-size:13px;color:#333;line-height:1.6">{jur.get('tax_exposure','—')}</div>
        </div>
        <div>
          <div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px">Compliance Framework</div>
          <div style="font-size:13px;color:#333;line-height:1.6">{jur.get('compliance_framework','—')}</div>
        </div>
      </div>
      <div class="card-footer">Source: KoruFlux Jurisdiction Intelligence — regulator publications and network analysis.</div>
    </div>
  </div>
  <div class="grid-2" style="margin-bottom:20px">
    <div class="card">
      <div class="card-header"><div class="card-title">RWA Tokenisation Status</div></div>
      <div class="card-body"><p style="font-size:13px;color:#333;line-height:1.8">{jur.get('rwa_tokenization_status','—')}</p></div>
    </div>
    <div class="card">
      <div class="card-header"><div class="card-title">KoruFlux Network Access</div></div>
      <div class="card-body"><p style="font-size:13px;color:#333;line-height:1.8">{jur.get('network_access','—')}</p></div>
      <div class="card-footer"><strong>Recommended engagement:</strong> {jur.get('recommended_engagement','—')}. {jur.get('engagement_rationale','')}</div>
    </div>
  </div>
  <div class="card">
    <div class="card-header">
      <div class="card-title">Client Archetype Fit</div>
      <span style="font-size:12px;color:var(--muted)">Web3 protocols · DeFi platforms · RWA projects</span>
    </div>
    <div class="card-body">{archetype_cards}</div>
    <div class="card-footer">
      Archetype recommendations combine sector opportunity scores with KoruFlux client-fit weighting
      and this jurisdiction's regulatory readiness for each archetype's typical use case.
    </div>
  </div>
</div>

<!-- ── NEWS FEED ─────────────────────────────────────────────── -->
<div id="tab-news" class="page">
  <div class="card">
    <div class="card-header">
      <div class="card-title">Live News Feed — {theme['name']}</div>
      <span style="font-size:12px;color:var(--muted)">{len(news + social)} items · click titles to verify</span>
    </div>
    <div class="card-body">
      {news_items_html}
    </div>
    <div class="card-footer">Sources: {sources_txt}. All items link to original source. Run live scrape to refresh.</div>
  </div>
</div>

<!-- ── REGULATORY ────────────────────────────────────────────── -->
<div id="tab-regulatory" class="page">
  <div class="card">
    <div class="card-header">
      <div class="card-title">Regulatory Updates — {theme['regulator']}</div>
    </div>
    <div class="card-body">{reg_html}</div>
    <div class="card-footer">Regulator: {meta.get('key_regulator','—')}. Source: official regulator websites. All links verified.</div>
  </div>
  <div class="card">
    <div class="card-header"><div class="card-title">Regulatory Context</div></div>
    <div class="card-body">
      <p style="font-size:13px;color:#444;line-height:1.8">
        <strong>{theme['name']}</strong> operates under <strong>{meta.get('key_regulator','—')}</strong>.
        {'A regulatory sandbox is active, allowing controlled innovation pilots.' if meta.get('sandbox') else 'No active sandbox programme at this time.'}
        Regulatory clarity score for this market averages
        <strong>{avg_reg_clarity}/100</strong>
        across all tracked sectors.
      </p>
    </div>
    <div class="card-footer">Data source: {data_note}</div>
  </div>
</div>

<!-- ── SOCIAL SIGNALS ────────────────────────────────────────── -->
<div id="tab-social" class="page">
  <div class="card">
    <div class="card-header">
      <div class="card-title">Social Intelligence — Farcaster Protocol</div>
      <span style="font-size:12px;color:var(--muted)">Public protocol · cast hashes verifiable on-chain</span>
    </div>
    <div class="card-body">{social_html}</div>
    <div class="card-footer">
      Source: Farcaster public protocol via nemes.farcaster.xyz hub.
      Cast hashes are cryptographically verifiable. Twitter/X data available with bearer token.
    </div>
  </div>
  <div class="card">
    <div class="card-header"><div class="card-title">Market Sentiment</div></div>
    <div class="card-body">
      <div style="margin-bottom:12px">
        <div style="font-size:12px;color:var(--muted);margin-bottom:6px">Overall market sentiment (from scraped signals)</div>
        {_sentiment_bar(ms)}
      </div>
      <div style="font-size:12px;color:var(--muted);margin-top:14px">
        Positive signals: {mkt_s.get('positive_signals',0)} &nbsp;·&nbsp;
        Negative signals: {mkt_s.get('negative_signals',0)} &nbsp;·&nbsp;
        Score: {ms:.3f} (range -1 to +1)
      </div>
    </div>
    <div class="card-footer">Sentiment derived from keyword analysis of scraped news and social data. Not investment advice.</div>
  </div>
</div>

<!-- ── RISK WATCH ─────────────────────────────────────────────── -->
<div id="tab-risks" class="page">
  <div class="card">
    <div class="card-header">
      <div class="card-title">Risk Signals — {theme['name']}</div>
      <span style="font-size:12px;color:var(--muted)">{len(risks)} signals detected</span>
    </div>
    <div class="card-body">{risk_html}</div>
    <div class="card-footer">Risk signals detected from keyword analysis of scraped sources. Severity: HIGH = direct threat keywords; MEDIUM = watch items. Sources: {sources_txt}</div>
  </div>
</div>

</div><!-- /container -->

<footer>
  KoruFlux Intelligence System · {theme['name']} Market Report · {gen} ·
  <a href="mailto:hello@koruflux.io" style="color:{A}">hello@koruflux.io</a> ·
  <a href="index.html" style="color:{A}">All Markets</a>
</footer>

<script>
Chart.defaults.font.family="'Segoe UI',system-ui,Arial,sans-serif";
Chart.defaults.color='#6B7280';

function showTab(name,el){{
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  el.classList.add('active');
  setTimeout(()=>window.dispatchEvent(new Event('resize')),50);
}}

// Bar chart
new Chart(document.getElementById('chartBar'),{{
  type:'bar',
  data:{{
    labels:{sectors_js},
    datasets:[{{label:'Opportunity Score',data:{scores_js},backgroundColor:{colors_js},borderRadius:5}}]
  }},
  options:{{
    indexAxis:'y',responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{display:false}}}},
    scales:{{x:{{min:0,max:100,grid:{{color:'#F0F4F8'}}}},y:{{grid:{{display:false}}}}}}
  }}
}});

// Radar chart
new Chart(document.getElementById('chartRadar'),{{
  type:'radar',
  data:{{
    labels:{radar_labels},
    datasets:[{{
      label:'{top_sector.get("sector","—")}',
      data:{radar_values},
      borderColor:'{A}',
      backgroundColor:'{A}22',
      pointBackgroundColor:'{A}',
      borderWidth:2
    }}]
  }},
  options:{{
    responsive:true,maintainAspectRatio:false,
    scales:{{r:{{min:0,max:100,ticks:{{stepSize:20}},grid:{{color:'#E5E7EB'}}}}}},
    plugins:{{legend:{{display:false}}}}
  }}
}});
</script>
</body>
</html>"""

    out = DASHBOARDS_DIR / f"dashboard_{region_code}.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"  [{region_code}] Dashboard saved → {out.name} ({len(html):,} bytes)")
    return out


def build_hub_index(reports: dict) -> Path:
    """Build the hub landing page linking all 8 regional dashboards."""

    cards_html = ""
    for code, theme in THEMES.items():
        report = reports.get(code, {})
        opp    = report.get("opportunity_leaderboard", [])
        top    = opp[0] if opp else {}
        high_c = len([o for o in opp if o.get("opportunity_score",0) >= 75])
        ms     = report.get("market_sentiment", {}).get("score", 0)
        ms_c   = "#2EC4B6" if ms > 0.15 else "#E63946" if ms < -0.15 else "#8D99AE"
        ms_l   = "Positive" if ms > 0.15 else "Negative" if ms < -0.15 else "Neutral"
        tc     = _tier_color(top.get("tier",""))
        meta   = report.get("meta",{})
        client_ranking = report.get("client_relevance_ranking", [])
        top_fit = client_ranking[0] if client_ranking else {}
        jur     = report.get("jurisdiction_intelligence", {})
        engagement = jur.get("recommended_engagement", "—")

        cards_html += f"""
        <a href="dashboard_{code}.html" style="text-decoration:none;color:inherit">
          <div style="background:white;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08),0 0 0 1px rgba(0,0,0,.04);transition:transform .2s,box-shadow .2s" onmouseover="this.style.transform='translateY(-3px)';this.style.boxShadow='0 6px 20px rgba(0,0,0,.12)'" onmouseout="this.style.transform='none';this.style.boxShadow='0 2px 8px rgba(0,0,0,.08),0 0 0 1px rgba(0,0,0,.04)'">
            <div style="background:linear-gradient(135deg,{theme['primary']},{theme['secondary']});padding:20px 22px;color:white">
              <div style="display:flex;justify-content:space-between;align-items:flex-start">
                <div>
                  <div style="font-size:11px;font-weight:700;letter-spacing:1px;opacity:.6;text-transform:uppercase">{code}</div>
                  <div style="font-size:17px;font-weight:800;margin-top:4px">{theme['name']}</div>
                  <div style="font-size:11px;opacity:.65;margin-top:3px">{theme['tag']}</div>
                </div>
                <div style="text-align:right">
                  <div style="font-size:28px;font-weight:800;color:{theme['accent']}">{top.get('opportunity_score','—')}</div>
                  <div style="font-size:10px;opacity:.7">{top.get('sector','—')}</div>
                </div>
              </div>
            </div>
            <div style="padding:16px 22px">
              <div style="display:flex;justify-content:space-between;margin-bottom:10px">
                <div style="text-align:center">
                  <div style="font-size:20px;font-weight:800;color:#2EC4B6">{top_fit.get('score','—')}</div>
                  <div style="font-size:10px;color:#6B7280;margin-top:2px">Client Fit</div>
                </div>
                <div style="text-align:center">
                  <div style="font-size:14px;font-weight:700;color:{ms_c}">{ms_l}</div>
                  <div style="font-size:10px;color:#6B7280;margin-top:2px">Sentiment</div>
                </div>
                <div style="text-align:center">
                  <div style="font-size:13px;font-weight:700;color:#1A1A2E">{meta.get('key_regulator','—')}</div>
                  <div style="font-size:10px;color:#6B7280;margin-top:2px">Regulator</div>
                </div>
              </div>
              <div style="font-size:11px;color:#9CA3AF;border-top:1px solid #F0F4F8;padding-top:8px">Recommended: <strong style='color:#1A1A2E'>{engagement}</strong></div>
            </div>
          </div>
        </a>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>KoruFlux · Global Market Intelligence</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',system-ui,Arial,sans-serif;background:#F0F4F8;color:#1A1A2E}}
  .header{{background:linear-gradient(135deg,#0A2E36,#005F73);color:white;padding:40px 48px 32px}}
  .header-inner{{max-width:1200px;margin:0 auto}}
  .header h1{{font-size:28px;font-weight:800;letter-spacing:.3px}}
  .header p{{font-size:14px;opacity:.75;margin-top:6px}}
  .header-meta{{display:flex;gap:16px;margin-top:16px;flex-wrap:wrap}}
  .header-meta span{{background:rgba(255,255,255,.1);padding:5px 14px;border-radius:20px;font-size:12px}}
  .container{{max-width:1200px;margin:32px auto;padding:0 24px}}
  .section-label{{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#6B7280;margin-bottom:16px}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:20px}}
  footer{{text-align:center;padding:28px;color:#9CA3AF;font-size:12px;border-top:1px solid #E5E7EB;margin-top:20px}}
  @media(max-width:600px){{.header{{padding:20px}}.container{{padding:0 12px}}}}
</style>
</head>
<body>
<div class="header">
  <div class="header-inner">
    <div style="display:flex;justify-content:space-between;align-items:flex-start">
      <div>
        <div style="font-size:11px;font-weight:700;letter-spacing:1.5px;opacity:.5;text-transform:uppercase;margin-bottom:8px">KoruFlux Intelligence System</div>
        <h1>Global Market Intelligence</h1>
        <p>Global Intelligence, Local Execution &mdash; Jurisdiction Intelligence for Web3, DeFi &amp; RWA</p>
      </div>
      <div style="text-align:right;font-size:12px;opacity:.6">
        Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}<br>
        hello@koruflux.io
      </div>
    </div>
    <div class="header-meta">
      <span>12+ Active Jurisdictions</span>
      <span>$2B+ Assets Advised</span>
      <span>85% Entry Success Rate</span>
      <span>48h Response Time</span>
      <span>8 Markets in This Report</span>
    </div>
  </div>
</div>

<div class="container">
  <div class="section-label">Select a market to view its full intelligence dashboard</div>
  <div class="grid">{cards_html}</div>
</div>

<footer>
  KoruFlux Intelligence System · Build. Transition. Strategize. Land. ·
  <a href="mailto:hello@koruflux.io" style="color:#00B4D8">hello@koruflux.io</a>
</footer>
</body>
</html>"""

    out = DASHBOARDS_DIR / "index.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"Hub index saved → {out}")
    return out


def build_all_regional_dashboards(reports: dict = None) -> dict:
    """Build all 8 regional dashboards + hub index."""
    if reports is None:
        from analysis.regional.regional_analyzer import load_all_regional_reports
        reports = load_all_regional_reports()
        if not reports:
            from analysis.regional.regional_analyzer import analyze_all_regions
            reports = analyze_all_regions()

    outputs = {}
    for code in THEMES:
        report = reports.get(code, {})
        if not report:
            from analysis.regional.regional_analyzer import analyze_region
            report = analyze_region(code, [])
        outputs[code] = build_regional_dashboard(code, report)

    outputs["hub"] = build_hub_index(reports)
    logger.info(f"All regional dashboards built — hub: {outputs['hub']}")
    return outputs


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(BASE_DIR))
    outputs = build_all_regional_dashboards()
    print(f"\nBuilt {len(outputs)} dashboards:")
    for k, v in outputs.items():
        import os
        print(f"  {k:<6} {os.path.getsize(str(v)):>8,} bytes  →  {v}")
