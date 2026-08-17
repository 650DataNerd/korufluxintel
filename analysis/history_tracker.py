"""
KoruFlux Intelligence System
==============================
analysis/history_tracker.py

Records opportunity scores after every pipeline run and
builds trend timelines showing how sectors move over time.

Storage: data/history/scores.json
  {
    "2026-05-10": {"Payments": 76.0, "AI_Fintech": 70.5, ...},
    "2026-05-17": {"Payments": 87.4, "AI_Fintech": 82.7, ...},
    ...
  }

Outputs:
  - Trend line chart (PNG)
  - Trend data JSON (for dashboard)
  - Week-over-week change summary
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("koruflux.history")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

HISTORY_DIR  = Path("data/history")
HISTORY_FILE = HISTORY_DIR / "scores.json"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════
# Read / Write
# ══════════════════════════════════════════════════════════════

def load_history() -> dict:
    if not HISTORY_FILE.exists():
        return {}
    try:
        with open(HISTORY_FILE) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load history: {e}")
        return {}


def save_scores(report: dict, date_key: str = None) -> dict:
    """
    Extract opportunity scores from a report and append to history.
    date_key defaults to today's ISO date (YYYY-MM-DD).
    """
    if date_key is None:
        date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    scores = {
        o["sector"]: o["opportunity_score"]
        for o in report.get("opportunity_leaderboard", [])
    }

    history = load_history()
    history[date_key] = scores

    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

    logger.info(f"📅 History updated — {date_key}: {len(scores)} sectors saved")
    return history


# ══════════════════════════════════════════════════════════════
# Analysis
# ══════════════════════════════════════════════════════════════

def get_trend_summary(history: dict = None) -> dict:
    """
    Compute week-over-week changes for all sectors.
    Returns a dict with trend data suitable for charts.
    """
    if history is None:
        history = load_history()

    if len(history) < 2:
        logger.info("Not enough history for trends (need at least 2 data points)")
        return {"dates": [], "sectors": {}, "changes": {}}

    # Sort dates
    dates = sorted(history.keys())
    all_sectors = set()
    for scores in history.values():
        all_sectors.update(scores.keys())
    all_sectors = sorted(all_sectors)

    # Build series per sector
    sector_series = {}
    for sector in all_sectors:
        series = [history[d].get(sector) for d in dates]
        sector_series[sector] = series

    # Week-over-week change (latest vs previous)
    changes = {}
    if len(dates) >= 2:
        latest   = history[dates[-1]]
        previous = history[dates[-2]]
        for sector in all_sectors:
            cur  = latest.get(sector, 0)
            prev = previous.get(sector, 0)
            delta = round(cur - prev, 1)
            changes[sector] = {
                "current": cur,
                "previous": prev,
                "delta": delta,
                "direction": "↑" if delta > 0 else "↓" if delta < 0 else "→"
            }

    return {
        "dates": dates,
        "sectors": sector_series,
        "changes": changes,
        "data_points": len(dates)
    }


def get_top_movers(history: dict = None, n: int = 5) -> dict:
    """Return the biggest gainers and losers since last run."""
    trend = get_trend_summary(history)
    changes = trend.get("changes", {})

    sorted_changes = sorted(
        changes.items(),
        key=lambda x: x[1]["delta"],
        reverse=True
    )

    return {
        "gainers": [
            {"sector": s, **d} for s, d in sorted_changes if d["delta"] > 0
        ][:n],
        "losers": [
            {"sector": s, **d} for s, d in sorted_changes if d["delta"] < 0
        ][:n],
        "stable": [
            {"sector": s, **d} for s, d in sorted_changes if d["delta"] == 0
        ]
    }


# ══════════════════════════════════════════════════════════════
# Visualisation
# ══════════════════════════════════════════════════════════════

def plot_trend_timeline(history: dict = None, sectors_to_plot: list = None):
    """
    Line chart showing score trajectories over time.
    Saves to data/reports/charts/trend_timeline.png
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from datetime import datetime as dt
    except ImportError:
        logger.error("matplotlib not installed")
        return

    if history is None:
        history = load_history()

    if len(history) < 2:
        logger.info("⏭️  Need 2+ data points for trend chart. Run pipeline again tomorrow.")
        _generate_placeholder_chart()
        return

    trend = get_trend_summary(history)
    dates_str = trend["dates"]
    dates_dt  = [dt.strptime(d, "%Y-%m-%d") for d in dates_str]

    # Default: plot top 6 sectors by latest score
    if sectors_to_plot is None:
        latest = history[dates_str[-1]]
        sectors_to_plot = sorted(latest, key=latest.get, reverse=True)[:6]

    COLORS = ["#2EC4B6", "#00B4D8", "#F4A261", "#E63946", "#90E0EF", "#FFB703", "#8D99AE", "#0A2E36"]
    BG = "#F8F9FA"

    fig, ax = plt.subplots(figsize=(13, 6))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    for i, sector in enumerate(sectors_to_plot):
        series = trend["sectors"].get(sector, [])
        valid_dates = [d for d, s in zip(dates_dt, series) if s is not None]
        valid_scores = [s for s in series if s is not None]
        if len(valid_scores) < 1:
            continue
        color = COLORS[i % len(COLORS)]
        ax.plot(valid_dates, valid_scores, marker="o", linewidth=2.5,
                markersize=6, color=color, label=sector)
        # Label latest value
        if valid_scores:
            ax.annotate(
                f"{valid_scores[-1]:.0f}",
                xy=(valid_dates[-1], valid_scores[-1]),
                xytext=(5, 3), textcoords="offset points",
                fontsize=9, color=color, fontweight="bold"
            )

    # Reference lines
    ax.axhline(y=75, color="#2EC4B6", linewidth=1, linestyle="--", alpha=0.5, label="High threshold")
    ax.axhline(y=55, color="#F4A261", linewidth=1, linestyle="--", alpha=0.5, label="Moderate threshold")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator())
    plt.xticks(rotation=30)

    ax.set_ylim(0, 105)
    ax.set_ylabel("Opportunity Score", fontsize=11, color="#1A1A2E")
    ax.set_title("KoruFlux · Sector Score Trends Over Time",
                 fontsize=14, fontweight="bold", color="#0A2E36", pad=15)
    ax.legend(loc="upper left", fontsize=9, facecolor=BG, framealpha=0.9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#E0E0E0", linewidth=0.7)

    plt.tight_layout()

    out = Path("data/reports/charts/trend_timeline.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close()
    logger.info(f"  📈 Trend chart saved → {out.name}")
    return out


def _generate_placeholder_chart():
    """Generate a 'more data needed' placeholder chart."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    fig, ax = plt.subplots(figsize=(13, 6))
    fig.patch.set_facecolor("#F8F9FA")
    ax.set_facecolor("#F8F9FA")
    ax.text(0.5, 0.5,
            "📅  Trend data builds over time\n\nRun the pipeline daily to see score trajectories\nAppear after 2+ data points",
            ha="center", va="center", fontsize=14, color="#8D99AE",
            transform=ax.transAxes, linespacing=2)
    ax.set_title("KoruFlux · Sector Score Trends", fontsize=14,
                 fontweight="bold", color="#0A2E36")
    ax.axis("off")

    out = Path("data/reports/charts/trend_timeline.png")
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor="#F8F9FA")
    plt.close()
    logger.info(f"  📋 Trend placeholder saved → {out.name}")


def print_movers_summary(history: dict = None):
    """Print a readable week-over-week summary to the terminal."""
    movers = get_top_movers(history)

    print("\n📊 WEEK-OVER-WEEK SECTOR MOVEMENT")
    print("─" * 45)

    if movers["gainers"]:
        print("  🟢 TOP GAINERS")
        for g in movers["gainers"]:
            print(f"     {g['sector']:<20} {g['previous']} → {g['current']}  (+{g['delta']})")

    if movers["losers"]:
        print("  🔴 DECLINING")
        for l in movers["losers"]:
            print(f"     {l['sector']:<20} {l['previous']} → {l['current']}  ({l['delta']})")

    if movers["stable"]:
        print("  → STABLE")
        for s in movers["stable"]:
            print(f"     {s['sector']:<20} {s['current']} (no change)")

    print("─" * 45)


if __name__ == "__main__":
    # Seed with the two baseline snapshots to bootstrap history
    history = load_history()

    if not history:
        print("📅 Seeding history with Part 1 & Part 2 baseline scores...")
        history["2026-05-10"] = {
            "Payments": 76.0, "AI_Fintech": 70.5, "DeFi": 65.8,
            "Infrastructure": 58.5, "RWA": 62.8, "AgriTech": 61.5,
            "Regulatory": 55.0, "NFT": 45.0, "DAO": 40.0
        }
        history["2026-05-17"] = {
            "Payments": 87.4, "AI_Fintech": 82.7, "DeFi": 77.7,
            "Infrastructure": 77.0, "RWA": 73.6, "AgriTech": 71.7,
            "Regulatory": 69.4, "NFT": 64.2, "DAO": 51.7
        }
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
        print(f"✅ Saved to {HISTORY_FILE}")

    print_movers_summary(history)
    plot_trend_timeline(history)
    print("\n✅ History tracker ready")
