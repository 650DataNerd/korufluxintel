"""
KoruFlux Intelligence System
==============================
visualization/visualizer.py

Generates publication-ready charts and dashboards:
  1. Opportunity Leaderboard (horizontal bar chart)
  2. Sector × Dimension Heatmap
  3. Sentiment Momentum Chart
  4. Theme Cluster Radar / Spider Chart
  5. Region Activity Map (bar)
  6. HTML Dashboard Summary

Run standalone:  python visualization/visualizer.py
Or import:       from visualization.visualizer import run_visualizer
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("koruflux.visualizer")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

REPORTS_DIR = Path("data/reports")
VIZ_DIR = Path("data/reports/charts")
VIZ_DIR.mkdir(parents=True, exist_ok=True)


# ── Colour palette (KoruFlux brand-adjacent) ──────────────────
COLORS = {
    "primary":    "#0A2E36",   # Deep teal
    "secondary":  "#00B4D8",   # Bright blue
    "accent":     "#90E0EF",   # Light blue
    "highlight":  "#F4A261",   # Amber/gold
    "success":    "#2EC4B6",   # Teal green
    "danger":     "#E63946",   # Red
    "neutral":    "#8D99AE",   # Gray
    "bg":         "#F8F9FA",   # Light background
    "text":       "#1A1A2E"    # Dark text
}

TIER_COLORS = {
    "HIGH OPPORTUNITY":     "#2EC4B6",
    "MODERATE OPPORTUNITY": "#F4A261",
    "EMERGING / MONITOR":   "#FFB703",
    "HIGH RISK / LOW PRIORITY": "#E63946"
}


def _load_latest_report() -> dict:
    reports = sorted(REPORTS_DIR.glob("intelligence_report_*.json"), reverse=True)
    if not reports:
        raise FileNotFoundError("No intelligence report found. Run analyzer first.")
    with open(reports[0]) as f:
        return json.load(f)


def plot_opportunity_leaderboard(report: dict):
    """Horizontal bar chart of all sector opportunity scores."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        logger.error("matplotlib not installed. Run: pip install matplotlib")
        return

    opp = report["opportunity_leaderboard"]
    sectors = [o["sector"] for o in opp]
    scores = [o["opportunity_score"] for o in opp]
    tiers = [o["tier"] for o in opp]
    bar_colors = [TIER_COLORS.get(t, COLORS["neutral"]) for t in tiers]

    fig, ax = plt.subplots(figsize=(12, 7))
    fig.patch.set_facecolor(COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])

    bars = ax.barh(sectors, scores, color=bar_colors, height=0.65, edgecolor="white", linewidth=0.5)

    # Score labels
    for bar, score in zip(bars, scores):
        ax.text(score + 0.8, bar.get_y() + bar.get_height() / 2,
                f"{score}", va="center", ha="left",
                fontsize=10, fontweight="bold", color=COLORS["text"])

    # Reference lines
    ax.axvline(x=75, color=COLORS["success"], linewidth=1.2, linestyle="--", alpha=0.7, label="High threshold (75)")
    ax.axvline(x=55, color=COLORS["highlight"], linewidth=1.2, linestyle="--", alpha=0.7, label="Moderate threshold (55)")

    # Legend
    patches = [
        mpatches.Patch(color=TIER_COLORS["HIGH OPPORTUNITY"], label="High Opportunity"),
        mpatches.Patch(color=TIER_COLORS["MODERATE OPPORTUNITY"], label="Moderate Opportunity"),
        mpatches.Patch(color=TIER_COLORS["EMERGING / MONITOR"], label="Emerging / Monitor"),
        mpatches.Patch(color=TIER_COLORS["HIGH RISK / LOW PRIORITY"], label="High Risk"),
    ]
    ax.legend(handles=patches, loc="lower right", fontsize=9,
              facecolor=COLORS["bg"], edgecolor=COLORS["neutral"])

    ax.set_xlim(0, 108)
    ax.set_xlabel("Opportunity Score (0–100)", fontsize=11, color=COLORS["text"])
    ax.set_title("KoruFlux · Sector Opportunity Leaderboard\nKenya & East Africa",
                 fontsize=14, fontweight="bold", color=COLORS["primary"], pad=15)
    ax.tick_params(colors=COLORS["text"])
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(COLORS["neutral"])

    plt.tight_layout()
    outfile = VIZ_DIR / "opportunity_leaderboard.png"
    plt.savefig(outfile, dpi=150, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close()
    logger.info(f"  📊 Saved: {outfile.name}")


def plot_sector_heatmap(report: dict):
    """Heatmap of sector × dimension scores."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        logger.error("matplotlib/numpy not installed")
        return

    opp = report["opportunity_leaderboard"]
    dims = ["market_size", "growth_rate", "regulatory_clarity",
            "ecosystem_maturity", "competitive_gap", "tech_readiness"]
    dim_labels = ["Market Size", "Growth Rate", "Reg. Clarity",
                  "Ecosystem", "Comp. Gap", "Tech Ready"]

    # Build matrix
    sectors = [o["sector"] for o in opp]
    matrix = []
    for o in opp:
        row = [o["dimensions"].get(d, 50) for d in dims]
        matrix.append(row)

    import numpy as np
    data = np.array(matrix)

    fig, ax = plt.subplots(figsize=(12, len(sectors) * 0.55 + 2))
    fig.patch.set_facecolor(COLORS["bg"])

    im = ax.imshow(data, cmap="YlOrRd", aspect="auto", vmin=0, vmax=100)

    # Labels
    ax.set_xticks(range(len(dim_labels)))
    ax.set_xticklabels(dim_labels, rotation=35, ha="right", fontsize=10)
    ax.set_yticks(range(len(sectors)))
    ax.set_yticklabels(sectors, fontsize=10)

    # Annotate cells
    for i in range(len(sectors)):
        for j in range(len(dims)):
            val = data[i, j]
            text_color = "white" if val > 70 else COLORS["text"]
            ax.text(j, i, str(int(val)), ha="center", va="center",
                    fontsize=9, fontweight="bold", color=text_color)

    plt.colorbar(im, ax=ax, label="Score (0–100)", shrink=0.8)
    ax.set_title("KoruFlux · Sector Intelligence Heatmap\n(higher = more favourable dimension)",
                 fontsize=13, fontweight="bold", color=COLORS["primary"], pad=12)

    plt.tight_layout()
    outfile = VIZ_DIR / "sector_heatmap.png"
    plt.savefig(outfile, dpi=150, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close()
    logger.info(f"  🗺️  Saved: {outfile.name}")


def plot_sentiment_chart(report: dict):
    """Bar chart showing sentiment score per sector."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    opp = report["opportunity_leaderboard"]
    sectors = [o["sector"] for o in opp]
    sentiments = [o.get("sentiment", {}).get("score", 0) for o in opp]
    bar_colors = [
        COLORS["success"] if s > 0.15 else COLORS["danger"] if s < -0.15 else COLORS["neutral"]
        for s in sentiments
    ]

    fig, ax = plt.subplots(figsize=(12, 5))
    fig.patch.set_facecolor(COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])

    bars = ax.bar(sectors, sentiments, color=bar_colors, edgecolor="white", linewidth=0.5)
    ax.axhline(y=0, color=COLORS["text"], linewidth=0.8)
    ax.axhline(y=0.15, color=COLORS["success"], linewidth=0.8, linestyle="--", alpha=0.6)
    ax.axhline(y=-0.15, color=COLORS["danger"], linewidth=0.8, linestyle="--", alpha=0.6)

    ax.set_ylabel("Sentiment Score (-1 to +1)", fontsize=10, color=COLORS["text"])
    ax.set_title("KoruFlux · Sector Sentiment Momentum\n(from live scraped data)",
                 fontsize=13, fontweight="bold", color=COLORS["primary"])
    ax.set_xticklabels(sectors, rotation=40, ha="right", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    outfile = VIZ_DIR / "sentiment_momentum.png"
    plt.savefig(outfile, dpi=150, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close()
    logger.info(f"  📈 Saved: {outfile.name}")


def plot_theme_clusters(report: dict):
    """Horizontal bar chart of theme cluster scores."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    themes = report["theme_clusters"]
    names = list(themes.keys())
    scores = [v["theme_score"] for v in themes.values()]
    signals = [v["signal"] for v in themes.values()]

    bar_colors = [
        COLORS["success"] if s >= 65 else COLORS["highlight"] if s >= 45 else COLORS["neutral"]
        for s in scores
    ]

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor(COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])

    bars = ax.barh(names, scores, color=bar_colors, height=0.5)
    for bar, score, sig in zip(bars, scores, signals):
        ax.text(score + 0.5, bar.get_y() + bar.get_height() / 2,
                f"{score}  {sig}", va="center", ha="left", fontsize=10, color=COLORS["text"])

    ax.set_xlim(0, 115)
    ax.set_xlabel("Theme Score (0–100)", fontsize=10)
    ax.set_title("KoruFlux · Strategic Theme Clusters",
                 fontsize=13, fontweight="bold", color=COLORS["primary"])
    ax.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    outfile = VIZ_DIR / "theme_clusters.png"
    plt.savefig(outfile, dpi=150, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close()
    logger.info(f"  🎯 Saved: {outfile.name}")


def generate_html_dashboard(report: dict):
    """Generate a self-contained HTML intelligence dashboard."""
    meta = report["report_metadata"]
    opp = report["opportunity_leaderboard"]
    themes = report["theme_clusters"]
    risks = report["risk_flags"]
    summary = report["market_summary"]

    def tier_badge(tier: str) -> str:
        colors = {
            "HIGH OPPORTUNITY": "#2EC4B6",
            "MODERATE OPPORTUNITY": "#F4A261",
            "EMERGING / MONITOR": "#FFB703",
            "HIGH RISK / LOW PRIORITY": "#E63946"
        }
        color = colors.get(tier, "#8D99AE")
        return f'<span style="background:{color};color:white;padding:3px 8px;border-radius:12px;font-size:12px;font-weight:600">{tier}</span>'

    opp_rows = ""
    for o in opp:
        dims = o.get("dimensions", {})
        opp_rows += f"""
        <tr>
          <td><strong>{o['sector']}</strong></td>
          <td style="text-align:center;font-weight:bold;font-size:16px">{o['opportunity_score']}</td>
          <td>{tier_badge(o['tier'])}</td>
          <td style="text-align:center">{o['mention_count']}</td>
          <td style="text-align:center">{o.get('sentiment',{}).get('momentum','→ stable')}</td>
          <td style="text-align:center">{dims.get('market_size','-')}</td>
          <td style="text-align:center">{dims.get('regulatory_clarity','-')}</td>
        </tr>"""

    theme_cards = ""
    for name, data in themes.items():
        score = data["theme_score"]
        sig = data["signal"]
        sec_list = ", ".join([s["sector"] for s in data["sectors"]])
        color = "#2EC4B6" if score >= 65 else "#F4A261" if score >= 45 else "#8D99AE"
        theme_cards += f"""
        <div style="background:white;border-left:5px solid {color};padding:16px;border-radius:8px;margin-bottom:12px;box-shadow:0 2px 6px rgba(0,0,0,0.06)">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <h4 style="margin:0;color:#0A2E36">{name}</h4>
            <span style="font-size:22px;font-weight:800;color:{color}">{score}</span>
          </div>
          <div style="color:#8D99AE;font-size:13px;margin-top:4px">{sig} · {sec_list}</div>
        </div>"""

    risk_rows = ""
    for r in risks[:6]:
        sev_color = "#E63946" if r["severity"] == "HIGH" else "#F4A261"
        risk_rows += f"""
        <tr>
          <td><strong>{r['risk_keyword']}</strong></td>
          <td>{r.get('source','—')}</td>
          <td><span style="background:{sev_color};color:white;padding:2px 8px;border-radius:8px;font-size:12px">{r['severity']}</span></td>
        </tr>"""

    # Client recs
    def rec_section(title, recs):
        html = f"<h3 style='color:#0A2E36;margin-top:28px'>{title}</h3>"
        for rec in recs:
            html += f"""
            <div style="background:white;padding:16px;border-radius:10px;margin-bottom:12px;box-shadow:0 2px 8px rgba(0,0,0,0.07)">
              <div style="display:flex;justify-content:space-between;align-items:flex-start">
                <div>
                  <strong style="font-size:16px;color:#0A2E36">{rec['sector']}</strong>
                  {tier_badge(rec['tier'])}
                </div>
                <div style="font-size:24px;font-weight:800;color:#00B4D8">{rec['score']}</div>
              </div>
              <p style="color:#444;margin:10px 0 8px 0;font-size:14px">{rec['recommendation']}</p>
              <div style="font-size:13px;color:#555">
                <strong>Action items:</strong>
                <ul style="margin:6px 0 0 0;padding-left:18px">
                  {''.join(f"<li>{a}</li>" for a in rec['action_items'])}
                </ul>
              </div>
            </div>"""
        return html

    ci = report["client_insights"]
    client_html = (
        rec_section("🚀 Web3 Startup Entering Kenya", ci["web3_startup_kenya"]["recommendations"]) +
        rec_section("🤖 AI Fintech Opportunity in East Africa", ci["ai_fintech_ea"]["recommendations"])
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KoruFlux · Intelligence Dashboard</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0 }}
  body {{ font-family:'Segoe UI',Arial,sans-serif; background:#F8F9FA; color:#1A1A2E }}
  .header {{ background:linear-gradient(135deg,#0A2E36,#00B4D8); color:white; padding:32px 40px }}
  .header h1 {{ font-size:28px; font-weight:800; letter-spacing:1px }}
  .header p {{ opacity:0.85; margin-top:6px; font-size:15px }}
  .meta {{ font-size:12px; opacity:0.7; margin-top:10px }}
  .container {{ max-width:1100px; margin:32px auto; padding:0 24px }}
  .section {{ background:white; border-radius:12px; padding:24px; margin-bottom:28px; box-shadow:0 2px 10px rgba(0,0,0,0.06) }}
  h2 {{ color:#0A2E36; font-size:19px; margin-bottom:18px; border-bottom:2px solid #00B4D8; padding-bottom:8px }}
  table {{ width:100%; border-collapse:collapse; font-size:14px }}
  th {{ background:#0A2E36; color:white; padding:10px 12px; text-align:left }}
  td {{ padding:9px 12px; border-bottom:1px solid #eee }}
  tr:hover td {{ background:#f0f9ff }}
  .stat-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:16px; margin-bottom:8px }}
  .stat {{ background:#F8F9FA; border-radius:10px; padding:16px; text-align:center; border:1px solid #e0e0e0 }}
  .stat .val {{ font-size:26px; font-weight:800; color:#00B4D8 }}
  .stat .lbl {{ font-size:13px; color:#8D99AE; margin-top:4px }}
  footer {{ text-align:center; color:#8D99AE; font-size:12px; padding:24px 0 }}
</style>
</head>
<body>
<div class="header">
  <h1>🌍 KoruFlux Intelligence Dashboard</h1>
  <p>Web3 · AI · Data · East Africa Market Entry</p>
  <div class="meta">Generated: {meta['generated_at'][:19].replace('T',' ')} UTC &nbsp;|&nbsp;
  Records analysed: {meta['records_analyzed']} &nbsp;|&nbsp;
  Sources: {len(meta['sources_included'])}</div>
</div>

<div class="container">

  <!-- Summary Stats -->
  <div class="section">
    <h2>📊 Market Summary</h2>
    <div class="stat-grid">
      <div class="stat"><div class="val">{len(opp)}</div><div class="lbl">Sectors Scored</div></div>
      <div class="stat"><div class="val">{opp[0]['opportunity_score']}</div><div class="lbl">Top Score: {opp[0]['sector']}</div></div>
      <div class="stat"><div class="val">{len([o for o in opp if o['opportunity_score']>=75])}</div><div class="lbl">High Opportunity Sectors</div></div>
      <div class="stat"><div class="val">{len(risks)}</div><div class="lbl">Risk Signals Detected</div></div>
    </div>
  </div>

  <!-- Opportunity Leaderboard -->
  <div class="section">
    <h2>🏆 Opportunity Leaderboard</h2>
    <table>
      <thead>
        <tr>
          <th>Sector</th><th>Score</th><th>Tier</th>
          <th>Mentions</th><th>Momentum</th>
          <th>Market Size</th><th>Reg. Clarity</th>
        </tr>
      </thead>
      <tbody>{opp_rows}</tbody>
    </table>
  </div>

  <!-- Theme Clusters -->
  <div class="section">
    <h2>🎯 Strategic Theme Clusters</h2>
    {theme_cards}
  </div>

  <!-- Client Insights -->
  <div class="section">
    <h2>💡 Client Intelligence Briefs</h2>
    {client_html}
  </div>

  <!-- Risk Flags -->
  <div class="section">
    <h2>⚠️ Risk Signals</h2>
    <table>
      <thead><tr><th>Signal</th><th>Source</th><th>Severity</th></tr></thead>
      <tbody>{risk_rows}</tbody>
    </table>
  </div>

</div>
<footer>KoruFlux Intelligence System · Build. Transition. Strategize. Land. · hello@koruflux.io</footer>
</body>
</html>"""

    outfile = REPORTS_DIR / "dashboard.html"
    with open(outfile, "w") as f:
        f.write(html)
    logger.info(f"  🌐 Dashboard saved → {outfile.name}")
    return outfile


def run_visualizer(report: dict = None):
    """Generate all charts and the HTML dashboard."""
    if report is None:
        report = _load_latest_report()

    logger.info("🎨 Generating visualisations...")

    plot_opportunity_leaderboard(report)
    plot_sector_heatmap(report)
    plot_sentiment_chart(report)
    plot_theme_clusters(report)
    dash = generate_html_dashboard(report)

    logger.info(f"\n✅ All visualisations complete. Open: {dash}")
    return dash


if __name__ == "__main__":
    run_visualizer()
