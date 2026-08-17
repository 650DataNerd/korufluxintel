"""
KoruFlux Intelligence System
==============================
visualization/dashboard_builder.py

Builds a rich, self-contained interactive HTML dashboard using
Chart.js (loaded from CDN) — no Plotly dependency needed.

Features:
  - Animated opportunity leaderboard bar chart
  - Sector heatmap table (colour-coded)
  - Theme cluster doughnut chart
  - Sentiment momentum bar chart
  - Client intelligence brief cards
  - KoruFlux context panel (services, pricing, markets)
  - Risk flags panel
  - Watch list panel
  - Fully self-contained single HTML file (shareable to clients)

Run standalone:  python visualization/dashboard_builder.py
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("koruflux.dashboard")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

REPORTS_DIR   = Path("data/reports")
PROCESSED_DIR = Path("data/processed")


def _load_latest(pattern: str) -> dict:
    files = sorted(REPORTS_DIR.glob(pattern), reverse=True)
    if not files:
        return {}
    with open(files[0]) as f:
        return json.load(f)


def _load_context() -> dict:
    ctx_path = PROCESSED_DIR / "koruflux_context.json"
    if ctx_path.exists():
        with open(ctx_path) as f:
            return json.load(f)
    return {}


def _build_leaderboard_rows(opp: list) -> str:
    rows = ""
    for i, o in enumerate(opp):
        sc = o["opportunity_score"]
        score_color = "#2EC4B6" if sc >= 75 else "#F4A261" if sc >= 55 else "#E63946"
        tier = o["tier"]
        badge_bg = "#2EC4B6" if "HIGH OPPORTUNITY" in tier and "MODERATE" not in tier else "#F4A261" if "MODERATE" in tier else "#FFB703" if "EMERGING" in tier else "#E63946"
        tier_label = tier.split(" ", 1)[1] if " " in tier else tier
        sentiment = o.get("sentiment") or {}
        momentum = sentiment.get("momentum", "—")
        dims = o.get("dimensions") or {}
        rows += f"""
        <tr>
          <td style="color:#6B7280">{i+1}</td>
          <td><strong>{o['sector']}</strong></td>
          <td style="font-weight:800;font-size:16px;color:{score_color}">{sc}</td>
          <td><span class="badge" style="background:{badge_bg}">{tier_label}</span></td>
          <td>{momentum}</td>
          <td style="text-align:center">{o['mention_count']}</td>
          <td style="text-align:center">{dims.get('market_size','—')}</td>
          <td style="text-align:center">{dims.get('growth_rate','—')}</td>
          <td style="text-align:center">{dims.get('regulatory_clarity','—')}</td>
        </tr>"""
    return rows


def build_dashboard() -> Path:
    report  = _load_latest("intelligence_report_*.json")
    context = _load_context()

    if not report:
        logger.error("No intelligence report found. Run analyzer first.")
        return None

    meta    = report.get("report_metadata", {})
    opp     = report.get("opportunity_leaderboard", [])
    themes  = report.get("theme_clusters", {})
    risks   = report.get("risk_flags", [])
    watch   = report.get("strategic_watch_list", [])
    ci      = report.get("client_insights", {})
    summary = report.get("market_summary", {})

    # ── Chart.js data ─────────────────────────────────────────
    sectors      = [o["sector"] for o in opp]
    scores       = [o["opportunity_score"] for o in opp]
    sentiments   = [round(o.get("sentiment", {}).get("score", 0) * 100, 1) for o in opp]
    tier_colors  = []
    for o in opp:
        t = o["tier"]
        if "HIGH OPPORTUNITY" in t and "MODERATE" not in t:
            tier_colors.append("rgba(46,196,182,0.85)")
        elif "MODERATE" in t:
            tier_colors.append("rgba(244,162,97,0.85)")
        elif "EMERGING" in t:
            tier_colors.append("rgba(255,183,3,0.85)")
        else:
            tier_colors.append("rgba(230,57,70,0.85)")

    theme_names  = list(themes.keys())
    theme_scores = [v["theme_score"] for v in themes.values()]
    theme_colors = [
        "rgba(46,196,182,0.8)", "rgba(0,180,216,0.8)", "rgba(90,224,239,0.8)",
        "rgba(244,162,97,0.8)", "rgba(10,46,54,0.8)"
    ]

    # ── Heatmap HTML ──────────────────────────────────────────
    dims = ["market_size", "growth_rate", "regulatory_clarity",
            "ecosystem_maturity", "competitive_gap", "tech_readiness"]
    dim_labels = ["Market Size", "Growth Rate", "Reg. Clarity",
                  "Ecosystem", "Comp. Gap", "Tech Ready"]

    def heat_color(val):
        if val >= 75: return "#2EC4B6"
        if val >= 60: return "#90E0EF"
        if val >= 45: return "#FFB703"
        if val >= 30: return "#F4A261"
        return "#E63946"

    heatmap_header = "".join(f"<th>{d}</th>" for d in dim_labels)
    heatmap_rows = ""
    for o in opp:
        d = o.get("dimensions", {})
        cells = ""
        for dim in dims:
            val = d.get(dim, 0)
            bg = heat_color(val)
            txt = "white" if val >= 60 or val < 30 else "#333"
            cells += f'<td style="background:{bg};color:{txt};font-weight:600;text-align:center">{val}</td>'
        heatmap_rows += f"<tr><td><strong>{o['sector']}</strong></td>{cells}</tr>"

    # ── Risk rows ─────────────────────────────────────────────
    risk_rows = ""
    for r in risks[:8]:
        sev = r.get("severity", "MEDIUM")
        sc = "#E63946" if sev == "HIGH" else "#F4A261"
        risk_rows += f"""
        <tr>
          <td><strong>{r['risk_keyword']}</strong></td>
          <td style="color:#666">{r.get('source','—')}</td>
          <td style="color:#666">{r.get('category','—')}</td>
          <td><span class="badge" style="background:{sc}">{sev}</span></td>
        </tr>"""
    if not risk_rows:
        risk_rows = '<tr><td colspan="4" style="text-align:center;color:#aaa;padding:18px"> No significant risk signals detected in current data</td></tr>'

    # ── Watch list rows ───────────────────────────────────────
    watch_rows = ""
    for w in watch:
        watch_rows += f"""
        <tr>
          <td><strong>{w['sector']}</strong></td>
          <td style="text-align:center;font-weight:700;color:#F4A261">{w['score']}</td>
          <td style="color:#555;font-size:13px">{w['reason']}</td>
        </tr>"""
    if not watch_rows:
        watch_rows = '<tr><td colspan="3" style="text-align:center;color:#aaa;padding:16px">No watch-list items at this time</td></tr>'

    # ── Client briefs ─────────────────────────────────────────
    def build_brief_html(profile_key: str) -> str:
        brief = ci.get(profile_key, {})
        recs  = brief.get("recommendations", [])
        html  = ""
        for rec in recs:
            score = rec["score"]
            tier  = rec["tier"]
            if "HIGH OPPORTUNITY" in tier and "MODERATE" not in tier: badge_color = "#2EC4B6"
            elif "MODERATE" in tier: badge_color = "#F4A261"
            elif "EMERGING" in tier: badge_color = "#FFB703"
            else:                   badge_color = "#E63946"

            actions = "".join(f"<li>{a}</li>" for a in rec.get("action_items", []))
            html += f"""
            <div class="brief-card">
              <div class="brief-header">
                <div>
                  <span class="brief-sector">{rec['sector']}</span>
                  <span class="badge" style="background:{badge_color};margin-left:8px">{tier}</span>
                </div>
                <div class="brief-score" style="color:{badge_color}">{score}</div>
              </div>
              <p class="brief-rec">{rec['recommendation']}</p>
              <div class="brief-actions">
                <strong>Action Items:</strong>
                <ul>{actions}</ul>
              </div>
            </div>"""
        return html

    brief_web3  = build_brief_html("web3_startup_kenya")
    brief_ai    = build_brief_html("ai_fintech_ea")
    brief_intl  = build_brief_html("intl_corp_africa_entry")
    brief_hub   = build_brief_html("web3_hub_expansion")

    # ── Trend data ────────────────────────────────────────────
    from analysis.history_tracker import load_history, get_trend_summary
    history  = load_history()
    trend    = get_trend_summary(history)
    t_dates  = trend.get("dates", [])
    t_sectors = trend.get("sectors", {})
    t_changes = trend.get("changes", {})

    # Build movers table rows
    movers_rows = ""
    for sector, ch in sorted(t_changes.items(), key=lambda x: x[1]["delta"], reverse=True):
        delta = ch["delta"]
        if delta > 0:   arrow, color = "↑", "#2EC4B6"
        elif delta < 0: arrow, color = "↓", "#E63946"
        else:           arrow, color = "→", "#8D99AE"
        movers_rows += f"""
        <tr>
          <td><strong>{sector}</strong></td>
          <td style="text-align:center">{ch["previous"]}</td>
          <td style="text-align:center;font-weight:700">{ch["current"]}</td>
          <td style="text-align:center;font-weight:700;color:{color}">{delta:+.1f}</td>
          <td style="text-align:center;font-size:18px;color:{color}">{arrow}</td>
        </tr>"""
    if not movers_rows:
        movers_rows = "<tr><td colspan=5 style='text-align:center;color:#aaa;padding:16px'>Run pipeline on 2+ different days to see movement</td></tr>"

    # Trend chart JS data
    trend_labels = str(t_dates)
    trend_datasets = []
    TREND_COLORS = ["#2EC4B6","#00B4D8","#F4A261","#E63946","#90E0EF","#FFB703","#8D99AE","#0A2E36","#2DC653"]
    top_sectors_for_trend = sorted(
        [(s, vals[-1] or 0) for s, vals in t_sectors.items() if vals],
        key=lambda x: x[1], reverse=True
    )[:6]
    for i, (sec, _) in enumerate(top_sectors_for_trend):
        vals = t_sectors.get(sec, [])
        color = TREND_COLORS[i % len(TREND_COLORS)]
        trend_datasets.append({"label": sec, "data": vals, "borderColor": color,
                                "backgroundColor": color + "20", "tension": 0.3,
                                "pointRadius": 5, "borderWidth": 2, "fill": False})

    # ── Global market cards ────────────────────────────────────
    MARKET_INFO = {
        "Kenya / Nairobi":  {"flag": "KE", "desc": "Primary Africa HQ · CMA · CBK · M-Pesa ecosystem", "color": "#2EC4B6"},
        "East Africa":      {"flag": "EA", "desc": "EA bloc: Kenya, Tanzania, Uganda, Rwanda, Ethiopia", "color": "#00B4D8"},
        "Nigeria":          {"flag": "NG", "desc": "Largest Africa economy · Scale market", "color": "#90E0EF"},
        "United States":    {"flag": "US", "desc": "SEC · CFTC · largest Web3 capital market", "color": "#F4A261"},
        "European Union":   {"flag": "EU", "desc": "MiCA regulation · institutional DeFi", "color": "#FFB703"},
        "United Kingdom":   {"flag": "GB", "desc": "FCA framework · London fintech hub", "color": "#8D99AE"},
        "Singapore":        {"flag": "SG", "desc": "MAS · Project Guardian · Asia gateway", "color": "#E63946"},
        "UAE / Dubai":      {"flag": "AE", "desc": "VARA · DIFC · ADGM · MENA hub", "color": "#A855F7"},
    }
    market_cards = ""
    for mkt, info in MARKET_INFO.items():
        market_cards += f"""
        <div style="background:rgba(255,255,255,0.12);border-radius:10px;padding:14px;border-left:4px solid {info["color"]}">
          <div style="font-size:11px;font-weight:800;letter-spacing:1px;color:rgba(255,255,255,0.5);background:rgba(255,255,255,0.1);padding:2px 6px;border-radius:4px;display:inline-block">{info["flag"]}</div>
          <div style="font-weight:700;margin-top:6px;font-size:14px">{mkt}</div>
          <div style="font-size:11px;opacity:0.8;margin-top:4px">{info["desc"]}</div>
        </div>"""

    # ── Context panel ─────────────────────────────────────────
    eng_rows = ""
    for e in context.get("engagement_types", []):
        eng_rows += f"""
        <tr>
          <td><strong>{e['type']}</strong></td>
          <td>{e['duration']}</td>
          <td style="color:#00B4D8;font-weight:600">{e['price']}</td>
        </tr>"""

    top_markets = list(context.get("target_markets", {}).keys())[:8]
    mkt_tags = "".join(f'<span class="tag">{m}</span>' for m in top_markets)

    top_techs = list(context.get("core_technologies", {}).keys())[:10]
    tech_tags = "".join(f'<span class="tag teal">{t}</span>' for t in top_techs)

    adv_items = "".join(
        f'<li> {a}</li>' for a in context.get("unique_advantages", [])
    )

    # ── Summary stat cards ────────────────────────────────────
    top_3 = opp[:3]
    high_count = len([o for o in opp if o["opportunity_score"] >= 75])
    mod_count  = len([o for o in opp if 55 <= o["opportunity_score"] < 75])
    records_n  = meta.get("records_analyzed", 0)

    # ── Serialise trend data for JS ──────────────────────────
    import json as _json
    json_trend_datasets = _json.dumps(trend_datasets)

    # ── Build full HTML ───────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KoruFlux · Intelligence Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --primary: #0A2E36;
    --secondary: #00B4D8;
    --accent: #90E0EF;
    --highlight: #F4A261;
    --success: #2EC4B6;
    --danger: #E63946;
    --neutral: #8D99AE;
    --bg: #F0F4F8;
    --card: #FFFFFF;
    --text: #1A1A2E;
    --muted: #6B7280;
  }}
  * {{ box-sizing:border-box; margin:0; padding:0 }}
  body {{ font-family:'Segoe UI',system-ui,Arial,sans-serif; background:var(--bg); color:var(--text); line-height:1.5 }}

  /* Header */
  .header {{ background:linear-gradient(135deg,#0A2E36 0%,#003D4F 50%,#005F73 100%); color:white; padding:36px 48px 28px }}
  .header-inner {{ max-width:1200px; margin:0 auto }}
  .header h1 {{ font-size:30px; font-weight:800; letter-spacing:0.5px }}
  .header .sub {{ opacity:0.8; margin-top:5px; font-size:15px }}
  .header .meta-bar {{ margin-top:14px; display:flex; gap:24px; font-size:12px; opacity:0.65 }}
  .meta-bar span {{ background:rgba(255,255,255,0.1); padding:3px 10px; border-radius:20px }}

  /* Nav tabs */
  .nav {{ background:var(--primary); border-bottom:1px solid rgba(255,255,255,0.1) }}
  .nav-inner {{ max-width:1200px; margin:0 auto; display:flex; gap:4px; padding:0 48px }}
  .tab {{ padding:12px 20px; color:rgba(255,255,255,0.6); cursor:pointer; font-size:14px; font-weight:500;
           border-bottom:3px solid transparent; transition:all 0.2s }}
  .tab:hover {{ color:white }}
  .tab.active {{ color:white; border-bottom-color:var(--secondary) }}

  /* Layout */
  .container {{ max-width:1200px; margin:28px auto; padding:0 24px }}
  .grid-2 {{ display:grid; grid-template-columns:1fr 1fr; gap:20px }}
  .grid-3 {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:20px }}
  .grid-4 {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px }}

  /* Cards */
  .card {{ background:var(--card); border-radius:12px; padding:22px; box-shadow:0 1px 8px rgba(0,0,0,0.07) }}
  .card h2 {{ font-size:16px; font-weight:700; color:var(--primary); margin-bottom:16px;
               padding-bottom:10px; border-bottom:2px solid var(--secondary) }}
  .card h3 {{ font-size:14px; font-weight:600; color:var(--primary); margin-bottom:10px }}

  /* Stat cards */
  .stat-card {{ background:var(--card); border-radius:12px; padding:20px; text-align:center;
                box-shadow:0 1px 8px rgba(0,0,0,0.07); border-top:4px solid var(--secondary) }}
  .stat-val {{ font-size:32px; font-weight:800; color:var(--secondary) }}
  .stat-lbl {{ font-size:13px; color:var(--muted); margin-top:4px }}

  /* Tables */
  table {{ width:100%; border-collapse:collapse; font-size:13px }}
  th {{ background:var(--primary); color:white; padding:10px 12px; text-align:left; font-weight:600 }}
  td {{ padding:9px 12px; border-bottom:1px solid #F0F0F0 }}
  tr:last-child td {{ border-bottom:none }}
  tr:hover td {{ background:#F8FBFC }}

  /* Badges */
  .badge {{ display:inline-block; padding:3px 9px; border-radius:20px; font-size:11px;
             font-weight:700; color:white; white-space:nowrap }}

  /* Tags */
  .tag {{ display:inline-block; background:#EEF2FF; color:#3730A3; border-radius:20px;
           padding:3px 10px; font-size:12px; margin:3px }}
  .tag.teal {{ background:#ECFDF5; color:#065F46 }}

  /* Brief cards */
  .brief-card {{ background:#F8FBFC; border-left:4px solid var(--secondary); border-radius:8px;
                  padding:16px; margin-bottom:14px }}
  .brief-header {{ display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px }}
  .brief-sector {{ font-size:16px; font-weight:700; color:var(--primary) }}
  .brief-score {{ font-size:28px; font-weight:800 }}
  .brief-rec {{ color:#444; font-size:13px; margin-bottom:10px; line-height:1.6 }}
  .brief-actions {{ font-size:13px }}
  .brief-actions ul {{ margin:6px 0 0 18px; color:#555 }}
  .brief-actions li {{ margin-bottom:3px }}

  /* Page sections */
  .page {{ display:none }}
  .page.active {{ display:block }}

  /* Chart containers */
  .chart-wrap {{ position:relative; width:100%; }}

  /* Context list */
  .adv-list {{ list-style:none; padding:0 }}
  .adv-list li {{ padding:6px 0; border-bottom:1px solid #F0F0F0; font-size:13px; color:#444 }}
  .adv-list li:last-child {{ border-bottom:none }}

  @media(max-width:768px) {{
    .grid-2,.grid-3,.grid-4 {{ grid-template-columns:1fr }}
    .header {{ padding:20px }}
    .container {{ padding:0 12px }}
  }}
</style>
</head>
<body>

<!-- Header -->
<div class="header">
  <div class="header-inner">
    <h1>KoruFlux Intelligence Dashboard</h1>
    <div class="sub">Web3 · AI · Data · East Africa Market Entry</div>
    <div class="meta-bar">
      <span>{meta.get('generated_at','')[:10]}</span>
      <span>{records_n} records analysed</span>
      <span>️ {len(meta.get('sources_included',[]))} sources</span>
      <span>{len(opp)} sectors scored</span>
      <span>8 markets: Kenya · EA · US · EU · UK · Singapore · UAE · Africa</span>
    </div>
  </div>
</div>

<!-- Nav -->
<div class="nav">
  <div class="nav-inner">
    <div class="tab active" onclick="showPage('overview',this)">Overview</div>
    <div class="tab" onclick="showPage('leaderboard',this)"> Leaderboard</div>
    <div class="tab" onclick="showPage('heatmap',this)">️ Heatmap</div>
    <div class="tab" onclick="showPage('clients',this)"> Client Briefs</div>
    <div class="tab" onclick="showPage('context',this)"> KoruFlux</div>
    <div class="tab" onclick="showPage('risks',this)">️ Risks</div>
    <div class="tab" onclick="showPage('trends',this)"> Trends</div>
    <div class="tab" onclick="showPage('global',this)"> Global Markets</div>
  </div>
</div>

<div class="container">

<!-- ══ PAGE: OVERVIEW ══════════════════════════════════════ -->
<div id="page-overview" class="page active">

  <!-- Stat cards -->
  <div class="grid-4" style="margin-bottom:20px">
    <div class="stat-card">
      <div class="stat-val">{opp[0]['opportunity_score'] if opp else '—'}</div>
      <div class="stat-lbl">Top Score<br><small>{opp[0]['sector'] if opp else ''}</small></div>
    </div>
    <div class="stat-card" style="border-top-color:#2EC4B6">
      <div class="stat-val" style="color:#2EC4B6">{high_count}</div>
      <div class="stat-lbl">High Opportunity<br>Sectors</div>
    </div>
    <div class="stat-card" style="border-top-color:#F4A261">
      <div class="stat-val" style="color:#F4A261">{mod_count}</div>
      <div class="stat-lbl">Moderate<br>Opportunity</div>
    </div>
    <div class="stat-card" style="border-top-color:#E63946">
      <div class="stat-val" style="color:#E63946">{len(risks)}</div>
      <div class="stat-lbl">Risk Signals<br>Detected</div>
    </div>
  </div>

  <div class="grid-2" style="margin-bottom:20px">
    <div class="card">
      <h2>Opportunity Scores</h2>
      <div class="chart-wrap" style="height:300px">
        <canvas id="chartOverviewBar"></canvas>
      </div>
    </div>
    <div class="card">
      <h2>Strategic Theme Clusters</h2>
      <div class="chart-wrap" style="height:300px">
        <canvas id="chartTheme"></canvas>
      </div>
    </div>
  </div>

  <div class="grid-2">
    <div class="card">
      <h2>Sentiment Momentum</h2>
      <div class="chart-wrap" style="height:260px">
        <canvas id="chartSentiment"></canvas>
      </div>
    </div>
    <div class="card">
      <h2>Strategic Watch List</h2>
      <table>
        <thead><tr><th>Sector</th><th>Score</th><th>Why Watch</th></tr></thead>
        <tbody>{watch_rows}</tbody>
      </table>
    </div>
  </div>
</div>

<!-- ══ PAGE: LEADERBOARD ═══════════════════════════════════ -->
<div id="page-leaderboard" class="page">
  <div class="card">
    <h2>Opportunity Leaderboard — Kenya & East Africa</h2>
    <div class="chart-wrap" style="height:420px;margin-bottom:24px">
      <canvas id="chartLeaderboard"></canvas>
    </div>
    <table>
      <thead>
        <tr>
          <th>#</th><th>Sector</th><th>Score</th><th>Tier</th>
          <th>Sentiment</th><th>Mentions</th><th>Market Size</th><th>Growth Rate</th><th>Reg. Clarity</th>
        </tr>
      </thead>
      <tbody>
        {_build_leaderboard_rows(opp)}
      </tbody>
    </table>
  </div>
</div>

<!-- ══ PAGE: HEATMAP ═══════════════════════════════════════ -->
<div id="page-heatmap" class="page">
  <div class="card">
    <h2>Sector Intelligence Heatmap</h2>
    <p style="font-size:13px;color:var(--muted);margin-bottom:16px">
      Each cell shows the raw dimension score (0–100).
      Teal = strong &nbsp;·&nbsp; Light blue = good &nbsp;·&nbsp; Amber = moderate &nbsp;·&nbsp; Red = weak
    </p>
    <div style="overflow-x:auto">
      <table>
        <thead><tr><th>Sector</th>{heatmap_header}</tr></thead>
        <tbody>{heatmap_rows}</tbody>
      </table>
    </div>
    <div style="margin-top:20px">
      <h3>Dimension Definitions</h3>
      <div class="grid-3" style="margin-top:12px;gap:12px">
        <div style="font-size:12px;color:#555"><strong>Market Size</strong> — Total addressable market volume in East Africa</div>
        <div style="font-size:12px;color:#555"><strong>Growth Rate</strong> — YoY expansion momentum of this sector</div>
        <div style="font-size:12px;color:#555"><strong>Reg. Clarity</strong> — Clarity of regulatory environment in Kenya/EA</div>
        <div style="font-size:12px;color:#555"><strong>Ecosystem</strong> — Maturity of local developer and business ecosystem</div>
        <div style="font-size:12px;color:#555"><strong>Comp. Gap</strong> — Gap in incumbent competition (higher = more open)</div>
        <div style="font-size:12px;color:#555"><strong>Tech Ready</strong> — Local tech infrastructure and talent readiness</div>
      </div>
    </div>
  </div>
</div>

<!-- ══ PAGE: CLIENT BRIEFS ════════════════════════════════ -->
<div id="page-clients" class="page">
  <div class="grid-2">
    <div class="card">
      <h2>Web3 Startup — Kenya Entry</h2>
      <p style="font-size:13px;color:var(--muted);margin-bottom:16px">
        For Web3 protocols, DeFi platforms, and crypto-native companies planning Kenya/EA market entry.
      </p>
      {brief_web3}
    </div>
    <div class="card">
      <h2>AI Fintech — East Africa</h2>
      <p style="font-size:13px;color:var(--muted);margin-bottom:16px">
        For AI-first fintech companies targeting East Africa's unbanked and underbanked populations.
      </p>
      {brief_ai}
    </div>
  </div>
</div>

<!-- ══ PAGE: KORUFLUX CONTEXT ═════════════════════════════ -->
<div id="page-context" class="page">
  <div class="grid-2" style="margin-bottom:20px">
    <div class="card">
      <h2>About KoruFlux</h2>
      <div style="font-size:13px;color:#444;line-height:1.8">
        <p><strong>Build. Transition. Strategize. Land.</strong></p>
        <p style="margin-top:8px">Nairobi-based technology and strategy consultancy at the intersection of Web3, AI, Data Analytics, and African market entry. Helping businesses build, grow, and enter markets — powered by data, not guesswork.</p>
        <p style="margin-top:12px"><strong>HQ:</strong> Nairobi, Kenya &nbsp;|&nbsp; <strong>Founded:</strong> 2026</p>
        <p><strong>Contact:</strong> hello@koruflux.io</p>
      </div>
      <h3 style="margin-top:18px">Competitive Advantages</h3>
      <ul class="adv-list">{adv_items}</ul>
    </div>
    <div class="card">
      <h2>Engagement Packages</h2>
      <table>
        <thead><tr><th>Type</th><th>Duration</th><th>Investment</th></tr></thead>
        <tbody>{eng_rows}</tbody>
      </table>
    </div>
  </div>
  <div class="grid-2">
    <div class="card">
      <h2>Target Markets</h2>
      <div style="padding:8px 0">{mkt_tags}</div>
    </div>
    <div class="card">
      <h2>Core Technologies</h2>
      <div style="padding:8px 0">{tech_tags}</div>
    </div>
  </div>
</div>

<!-- ══ PAGE: RISKS ═════════════════════════════════════════ -->
<div id="page-risks" class="page">
  <div class="card" style="margin-bottom:20px">
    <h2>Risk Signals</h2>
    <p style="font-size:13px;color:var(--muted);margin-bottom:14px">
      Risk keywords detected across all ingested data sources. HIGH = direct threat signals; MEDIUM = watch items.
    </p>
    <table>
      <thead><tr><th>Signal</th><th>Source</th><th>Category</th><th>Severity</th></tr></thead>
      <tbody>{risk_rows}</tbody>
    </table>
  </div>
  <div class="card">
    <h2>Strategic Watch List</h2>
    <p style="font-size:13px;color:var(--muted);margin-bottom:14px">
      Sectors not yet at "High Opportunity" but with strong growth indicators — monitor for entry timing.
    </p>
    <table>
      <thead><tr><th>Sector</th><th>Score</th><th>Rationale</th></tr></thead>
      <tbody>{watch_rows}</tbody>
    </table>
  </div>
</div>

<!-- ══ PAGE: TRENDS ════════════════════════════════════════ -->
<div id="page-trends" class="page">
  <div class="card" style="margin-bottom:20px">
    <h2>Sector Score Trends</h2>
    <p style="font-size:13px;color:var(--muted);margin-bottom:16px">
      Opportunity scores tracked over time. Updates each time the pipeline runs with new data.
      Scores increase when positive signals (funding, launches, regulatory clarity) appear in scraped sources.
    </p>
    <div class="chart-wrap" style="height:360px">
      <canvas id="chartTrend"></canvas>
    </div>
  </div>
  <div class="card">
    <h2>Week-over-Week Movement</h2>
    <p style="font-size:13px;color:var(--muted);margin-bottom:14px">
      Score changes between the two most recent pipeline runs.
    </p>
    <table>
      <thead><tr><th>Sector</th><th>Previous</th><th>Current</th><th>Change</th><th>Direction</th></tr></thead>
      <tbody>{movers_rows}</tbody>
    </table>
  </div>
</div>

<!-- ══ PAGE: GLOBAL MARKETS ═══════════════════════════════ -->
<div id="page-global" class="page">

  <!-- Market coverage banner -->
  <div class="card" style="margin-bottom:20px;background:linear-gradient(135deg,#0A2E36,#005F73);color:white">
    <h2 style="color:white;border-bottom-color:rgba(255,255,255,0.3)">KoruFlux — Global Market Coverage</h2>
    <p style="font-size:13px;opacity:0.85;margin-bottom:16px">
      Intelligence and market entry support across all 8 target markets.
    </p>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px">
      {market_cards}
    </div>
  </div>

  <!-- 4 Client Profile Briefs -->
  <div class="grid-2">
    <div class="card">
      <h2>Web3 Startup → Kenya</h2>
      <div style="font-size:12px;color:#00B4D8;margin-bottom:12px">Markets: Kenya · East Africa</div>
      {brief_web3}
    </div>
    <div class="card">
      <h2>AI Fintech → East Africa</h2>
      <div style="font-size:12px;color:#00B4D8;margin-bottom:12px">Markets: Kenya · East Africa · Nigeria</div>
      {brief_ai}
    </div>
    <div class="card">
      <h2>International Corp → Africa</h2>
      <div style="font-size:12px;color:#00B4D8;margin-bottom:12px">Markets: US · EU · UK → Kenya · East Africa</div>
      {brief_intl}
    </div>
    <div class="card">
      <h2>Web3 Protocol → Singapore / UAE</h2>
      <div style="font-size:12px;color:#00B4D8;margin-bottom:12px">Markets: Singapore · UAE · United States</div>
      {brief_hub}
    </div>
  </div>
</div>

</div><!-- /container -->

<footer style="text-align:center;padding:24px;color:var(--muted);font-size:12px;border-top:1px solid #E5E7EB;margin-top:20px">
  KoruFlux Intelligence System · Build. Transition. Strategize. Land. ·
  <a href="mailto:hello@koruflux.io" style="color:var(--secondary)">hello@koruflux.io</a> ·
  Generated {meta.get('generated_at','')[:19].replace('T',' ')} UTC
</footer>

<script>
// ── Tab navigation ────────────────────────────────────────
function showPage(name, el) {{
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  el.classList.add('active');
  // Trigger chart resize
  setTimeout(() => window.dispatchEvent(new Event('resize')), 50);
}}

// ── Chart defaults ────────────────────────────────────────
Chart.defaults.font.family = "'Segoe UI', system-ui, Arial, sans-serif";
Chart.defaults.color = '#6B7280';

const sectors    = {json.dumps(sectors)};
const scores     = {json.dumps(scores)};
const sentiments = {json.dumps(sentiments)};
const tierColors = {json.dumps(tier_colors)};
const themeNames  = {json.dumps(theme_names)};
const themeScores = {json.dumps(theme_scores)};
const themeColors = {json.dumps(theme_colors)};

// ── Overview bar ──────────────────────────────────────────
new Chart(document.getElementById('chartOverviewBar'), {{
  type: 'bar',
  data: {{ labels: sectors, datasets: [{{
    label: 'Opportunity Score',
    data: scores,
    backgroundColor: tierColors,
    borderRadius: 6
  }}]}},
  options: {{
    indexAxis: 'y',
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ min: 0, max: 100, grid: {{ color: '#F0F4F8' }} }},
      y: {{ grid: {{ display: false }} }}
    }}
  }}
}});

// ── Theme doughnut ────────────────────────────────────────
new Chart(document.getElementById('chartTheme'), {{
  type: 'doughnut',
  data: {{ labels: themeNames, datasets: [{{
    data: themeScores,
    backgroundColor: themeColors,
    borderWidth: 2,
    borderColor: '#fff'
  }}]}},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      legend: {{ position: 'bottom', labels: {{ boxWidth: 12, font: {{ size: 11 }} }} }}
    }}
  }}
}});

// ── Sentiment chart ───────────────────────────────────────
const sentColors = sentiments.map(s => s > 15 ? 'rgba(46,196,182,0.8)' : s < -15 ? 'rgba(230,57,70,0.8)' : 'rgba(141,153,174,0.7)');
new Chart(document.getElementById('chartSentiment'), {{
  type: 'bar',
  data: {{ labels: sectors, datasets: [{{
    label: 'Sentiment Score',
    data: sentiments,
    backgroundColor: sentColors,
    borderRadius: 4
  }}]}},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      y: {{ min: -100, max: 100, grid: {{ color: '#F0F4F8' }} }},
      x: {{ ticks: {{ maxRotation: 40 }}, grid: {{ display: false }} }}
    }}
  }}
}});

// ── Leaderboard bar ───────────────────────────────────────
new Chart(document.getElementById('chartLeaderboard'), {{
  type: 'bar',
  data: {{ labels: sectors, datasets: [{{
    label: 'Opportunity Score',
    data: scores,
    backgroundColor: tierColors,
    borderRadius: 6
  }}]}},
  options: {{
    indexAxis: 'y',
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{
        callbacks: {{
          label: ctx => ` Score: ${{ctx.raw}}/100`
        }}
      }}
    }},
    scales: {{
      x: {{ min: 0, max: 100, grid: {{ color: '#F0F4F8' }} }},
      y: {{ grid: {{ display: false }} }}
    }}
  }}
}});

// ── Trend line chart ──────────────────────────────────────
const trendDates    = {trend_labels};
const trendDatasets = {json_trend_datasets};

if (trendDates.length >= 2) {{
  new Chart(document.getElementById('chartTrend'), {{
    type: 'line',
    data: {{ labels: trendDates, datasets: trendDatasets }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{
        legend: {{ position: 'bottom', labels: {{ boxWidth: 12, font: {{ size: 11 }} }} }}
      }},
      scales: {{
        y: {{ min: 0, max: 100, grid: {{ color: '#F0F4F8' }} }},
        x: {{ grid: {{ display: false }} }}
      }}
    }}
  }});
}} else {{
  const ctx = document.getElementById('chartTrend');
  if (ctx) {{
    ctx.parentElement.innerHTML = '<div style="text-align:center;padding:60px;color:#8D99AE">Run on 2+ different days to see trends</div>';
  }}
}}
</script>
</body>
</html>"""

    outfile = REPORTS_DIR / "dashboard_v2.html"
    with open(outfile, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f" Dashboard v2 saved → {outfile}")
    return outfile


if __name__ == "__main__":
    build_dashboard()
