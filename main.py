"""
KoruFlux Intelligence System v6
================================
main.py — Master Pipeline Runner

Runs the complete intelligence pipeline:
  1. Ingest  → docs + web scraping
  2. Parse   → normalise + tag
  3. Analyze → global scoring (all markets combined)
  4. History → trend tracking
  5. Regional → per-market analysis (8 regions)
  6. Visualize → global dashboard + 8 regional dashboards + hub
  7. Export  → Excel + Markdown

Usage:
  python main.py                  # Full live pipeline
  python main.py --skip-scrape    # Use cached data
  python main.py --only-regional  # Regional pipeline only
  python main.py --only-viz       # Rebuild visuals only
  python main.py --health-check   # Test source connectivity
"""

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s"
)
logger = logging.getLogger("koruflux.main")
sys.path.insert(0, str(Path(__file__).parent))


def run_pipeline(skip_scrape=False, only_viz=False, only_regional=False):
    logger.info("=" * 60)
    logger.info("  KoruFlux Intelligence System v6")
    logger.info(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    logger.info("=" * 60)

    report    = None
    processed = []

    # ── STEP 1: Ingest ────────────────────────────────────────
    if not only_viz and not only_regional:
        raw_records = []

        logger.info("\n[1/7] Ingesting documents...")
        from ingestion.doc_ingestor import ingest_documents
        doc_records, ctx = ingest_documents(Path("docs"))
        raw_records += doc_records
        logger.info(f"       {len(doc_records)} documents")

        if not skip_scrape:
            logger.info("       Scraping live sources...")
            from ingestion.scraper import run_all_scrapers
            web_records = run_all_scrapers()
            raw_records += web_records
            logger.info(f"       {len(web_records)} web records")
        else:
            logger.info("       Scraping skipped — using cached data")

        # ── STEP 2: Parse ──────────────────────────────────────
        logger.info("\n[2/7] Parsing & normalising...")
        from processing.parser import process_all
        processed = process_all(raw_records if raw_records else None)
        logger.info(f"       {len(processed)} records")

        # ── STEP 3: Global analysis ────────────────────────────
        logger.info("\n[3/7] Global analysis...")
        from analysis.analyzer import run_analysis
        report = run_analysis(processed)

        print("\n" + "─" * 55)
        print("  GLOBAL OPPORTUNITY LEADERBOARD")
        print("─" * 55)
        for o in report["opportunity_leaderboard"][:8]:
            bar = "█" * int(o["opportunity_score"] / 5)
            print(f"  {o['sector']:<20} {o['opportunity_score']:5.1f}  {bar}")
        print("─" * 55)

        # ── STEP 4: History ────────────────────────────────────
        logger.info("\n[4/7] Updating trend history...")
        from analysis.history_tracker import (
            save_scores, plot_trend_timeline, print_movers_summary
        )
        history = save_scores(report)
        print_movers_summary(history)
        plot_trend_timeline(history)

    # ── STEP 5: Regional pipeline ──────────────────────────────
    logger.info("\n[5/7] Regional intelligence pipeline...")

    regional_raw = {}
    if not skip_scrape and not only_viz:
        logger.info("       Scraping regional sources...")
        from ingestion.regional.regional_scraper import scrape_all_regions
        regional_raw = scrape_all_regions()
        total = sum(len(v) for v in regional_raw.values())
        logger.info(f"       {total} regional records collected")

    from analysis.regional.regional_analyzer import analyze_all_regions
    regional_reports = analyze_all_regions(regional_raw if regional_raw else None)

    print("\n" + "─" * 55)
    print("  REGIONAL OPPORTUNITY SUMMARY")
    print("─" * 55)
    for code, r in regional_reports.items():
        top = r.get("top_sector", {})
        print(f"  {code:<4} {r['region_name']:<22} "
              f"{top.get('sector','?'):<18} {top.get('opportunity_score','?')}")
    print("─" * 55)

    # ── STEP 6: Visualise ──────────────────────────────────────
    logger.info("\n[6/7] Building dashboards...")

    from visualization.visualizer import run_visualizer
    from visualization.dashboard_builder import build_dashboard
    from visualization.regional_dashboard import build_all_regional_dashboards

    if not only_regional:
        run_visualizer(report)
        global_dash = build_dashboard()
        logger.info(f"       Global dashboard built")

    regional_outputs = build_all_regional_dashboards(regional_reports)
    hub = regional_outputs.get("hub")
    logger.info(f"       {len(regional_outputs)-1} regional dashboards + hub")

    # ── STEP 7: Export ─────────────────────────────────────────
    if not only_regional:
        logger.info("\n[7/7] Generating exports...")
        from visualization.exporter import export_all
        exports = export_all(report)
        for fmt, path in exports.items():
            logger.info(f"       {fmt}: {path}")

    # ── Summary ────────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("  PIPELINE COMPLETE")
    if not only_regional and report:
        logger.info(f"  Global dashboard  → data/reports/dashboard_v2.html")
    logger.info(f"  Regional hub      → {hub}")
    logger.info(f"  Regional markets  → data/dashboards/")
    if not only_regional:
        logger.info(f"  Exports           → data/exports/")
    logger.info("=" * 60)
    return report, regional_reports


def run_regional_pipeline(skip_scrape=False):
    """Convenience wrapper — regional pipeline only."""
    _, rr = run_pipeline(skip_scrape=skip_scrape, only_regional=True)
    return rr


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KoruFlux Intelligence Pipeline v6")
    parser.add_argument("--skip-scrape",   action="store_true", help="Use cached data")
    parser.add_argument("--only-viz",      action="store_true", help="Rebuild visuals only")
    parser.add_argument("--only-regional", action="store_true", help="Regional pipeline only")
    parser.add_argument("--health-check",  action="store_true", help="Test source connectivity")
    args = parser.parse_args()

    for d in ["data", "data/raw", "data/processed", "data/reports",
              "data/reports/charts", "data/exports", "data/history",
              "data/dashboards", "data/ai_narratives"]:
        Path(d).mkdir(parents=True, exist_ok=True)

    if args.health_check:
        from ingestion.scraper_patch import run_health_check
        run_health_check()
        sys.exit(0)

    run_pipeline(
        skip_scrape=args.skip_scrape,
        only_viz=args.only_viz,
        only_regional=args.only_regional
    )
