"""
KoruFlux Intelligence System
==============================
webui/app.py  —  Local Web UI (Flask) v6
"""

import json
import logging
import sys
import threading
import time
import yaml
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue, Empty

from flask import (Flask, render_template, jsonify, request,
                   redirect, url_for, Response, send_file)

# ── Path setup ────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "koruflux-intel-2026"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("koruflux.webui")

pipeline_state = {
    "running": False,
    "last_run": None,
    "last_status": "never run",
    "log_queue": Queue()
}


# ══════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════

def load_config():
    for path in [
        BASE_DIR / "config/config.yaml",
        Path("config/config.yaml"),
    ]:
        if path.exists():
            with open(path) as f:
                return yaml.safe_load(f)
    return {}


def save_config(cfg):
    path = BASE_DIR / "config/config.yaml"
    with open(path, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)


def load_latest_report():
    reports = sorted(
        (BASE_DIR / "data/reports").glob("intelligence_report_*.json"),
        reverse=True
    )
    if not reports:
        return {}
    with open(reports[0]) as f:
        return json.load(f)


def load_history():
    h = BASE_DIR / "data/history/scores.json"
    if not h.exists():
        return {}
    with open(h) as f:
        return json.load(f)


def list_exports():
    d = BASE_DIR / "data/exports"
    if not d.exists():
        return []
    return [
        {
            "name": f.name,
            "size": f"{f.stat().st_size/1024:.1f} KB",
            "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
        }
        for f in sorted(d.iterdir(), reverse=True)
        if f.is_file()
    ]


def list_reports():
    return [
        {
            "name": f.name,
            "size": f"{f.stat().st_size/1024:.1f} KB",
            "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
        }
        for f in sorted(
            (BASE_DIR / "data/reports").glob("*.json"), reverse=True
        )[:10]
    ]


# ══════════════════════════════════════════════════════════════
# Pipeline runner
# ══════════════════════════════════════════════════════════════

def _run_pipeline_thread(skip_scrape: bool):
    q = pipeline_state["log_queue"]
    pipeline_state["running"] = True
    pipeline_state["last_run"] = datetime.now(timezone.utc).isoformat()

    def emit(msg):
        q.put(msg)
        logger.info(msg)

    try:
        emit("KoruFlux pipeline starting...")
        from ingestion.doc_ingestor import ingest_documents
        doc_records, ctx = ingest_documents(BASE_DIR / "docs")
        raw_records = list(doc_records)
        emit(f"  {len(doc_records)} documents ingested")

        if not skip_scrape:
            emit("  Scraping live sources...")
            from ingestion.scraper import run_all_scrapers
            web = run_all_scrapers()
            raw_records += web
            emit(f"  {len(web)} web records fetched")

        emit("Parsing records...")
        from processing.parser import process_all
        processed = process_all(raw_records if raw_records else None)
        emit(f"  {len(processed)} records processed")

        emit("Running analysis...")
        from analysis.analyzer import run_analysis
        report = run_analysis(processed)
        top = report["opportunity_leaderboard"][0]
        emit(f"  Top: {top['sector']} ({top['opportunity_score']})")

        emit("Updating history...")
        from analysis.history_tracker import save_scores, plot_trend_timeline
        history = save_scores(report)
        plot_trend_timeline(history)

        emit("Running regional analysis...")
        from analysis.regional.regional_analyzer import analyze_all_regions
        regional_reports = analyze_all_regions()
        emit(f"  {len(regional_reports)} regions scored")

        emit("Building dashboards...")
        from visualization.visualizer import run_visualizer
        from visualization.dashboard_builder import build_dashboard
        from visualization.regional_dashboard import build_all_regional_dashboards
        run_visualizer(report)
        build_dashboard()
        build_all_regional_dashboards(regional_reports)
        emit("  All dashboards built")

        emit("Generating exports...")
        from visualization.exporter import export_all
        export_all(report)

        emit("Pipeline complete!")
        pipeline_state["last_status"] = "success"

    except Exception as e:
        emit(f"ERROR: {e}")
        pipeline_state["last_status"] = "error"
        import traceback
        emit(traceback.format_exc())
    finally:
        pipeline_state["running"] = False
        q.put("__DONE__")


# ══════════════════════════════════════════════════════════════
# Routes — Main
# ══════════════════════════════════════════════════════════════

@app.route("/")
def index():
    report  = load_latest_report()
    history = load_history()
    cfg     = load_config()
    opp     = report.get("opportunity_leaderboard", [])
    meta    = report.get("report_metadata", {})
    stats = {
        "top_sector":     opp[0]["sector"] if opp else "—",
        "top_score":      opp[0]["opportunity_score"] if opp else "—",
        "high_opps":      len([o for o in opp if o.get("opportunity_score",0) >= 75]),
        "records":        meta.get("records_analyzed", 0),
        "last_run":       meta.get("generated_at", "Never")[:19].replace("T", " ") if meta else "Never",
        "sources_ok":     len([t for t in cfg.get("scrape_targets", []) if t.get("enabled")]),
        "history_points": len(history),
        "markets":        meta.get("markets_covered", [])
    }
    return render_template("index.html",
                           active="home",
                           stats=stats,
                           opp=opp[:9],
                           pipeline=pipeline_state,
                           exports=list_exports(),
                           reports=list_reports())


@app.route("/run-page")
def run_page():
    return redirect(url_for("index"))


@app.route("/run", methods=["POST"])
def trigger_run():
    if pipeline_state["running"]:
        return jsonify({"error": "Pipeline already running"}), 409
    skip = request.form.get("skip_scrape") == "true"
    while not pipeline_state["log_queue"].empty():
        try:
            pipeline_state["log_queue"].get_nowait()
        except Empty:
            break
    threading.Thread(
        target=_run_pipeline_thread, args=(skip,), daemon=True
    ).start()
    return jsonify({"status": "started", "skip_scrape": skip})


@app.route("/stream-logs")
def stream_logs():
    def generate():
        yield "data: Connected\n\n"
        while True:
            try:
                msg = pipeline_state["log_queue"].get(timeout=30)
                if msg == "__DONE__":
                    yield f"data: {msg}\n\n"
                    break
                safe = msg.replace("\n", "<br>")
                yield f"data: {safe}\n\n"
            except Empty:
                yield "data: ...\n\n"
    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ══════════════════════════════════════════════════════════════
# Routes — Sources & Health
# ══════════════════════════════════════════════════════════════

@app.route("/sources")
def sources():
    cfg = load_config()
    return render_template("sources.html",
                           active="sources",
                           targets=cfg.get("scrape_targets", []),
                           pipeline=pipeline_state)


@app.route("/sources/toggle/<source_id>", methods=["POST"])
def toggle_source(source_id):
    cfg = load_config()
    for t in cfg.get("scrape_targets", []):
        if t["id"] == source_id:
            t["enabled"] = not t.get("enabled", True)
            break
    save_config(cfg)
    return jsonify({"status": "ok"})


@app.route("/health")
def health_check():
    from ingestion.scraper_patch import SOURCES_TO_TEST
    import requests as req
    session = req.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    results = []
    for label, url, params in SOURCES_TO_TEST:
        try:
            r = session.get(url, params=params, timeout=8)
            results.append({
                "label": label, "url": url,
                "status": r.status_code,
                "size": f"{len(r.content)/1024:.1f} KB",
                "ok": r.status_code < 400
            })
        except Exception as e:
            results.append({
                "label": label, "url": url,
                "status": type(e).__name__,
                "size": "—", "ok": False
            })
        time.sleep(0.3)
    return render_template("health.html",
                           active="health",
                           results=results,
                           ok_count=sum(1 for r in results if r["ok"]),
                           total=len(results),
                           pipeline=pipeline_state)


# ══════════════════════════════════════════════════════════════
# Routes — Reports & Exports
# ══════════════════════════════════════════════════════════════

@app.route("/reports")
def reports_page():
    return render_template("reports.html",
                           active="reports",
                           exports=list_exports(),
                           reports=list_reports(),
                           pipeline=pipeline_state)


@app.route("/download/<path:filename>")
def download_file(filename):
    filepath = BASE_DIR / "data/exports" / filename
    if filepath.exists():
        return send_file(filepath, as_attachment=True)
    return "File not found", 404


@app.route("/dashboard-embed")
def dashboard_embed():
    dash = BASE_DIR / "data/reports/dashboard_v2.html"
    if dash.exists():
        return send_file(dash)
    return "<p style='padding:40px;font-family:sans-serif'>No dashboard yet. Run the pipeline first.</p>"


# ══════════════════════════════════════════════════════════════
# Routes — AI Narratives
# ══════════════════════════════════════════════════════════════

@app.route("/ai-narratives")
def ai_narratives():
    from analysis.ai_narrator import load_latest_narratives, _get_api_key
    narratives = load_latest_narratives()
    api_key_set = bool(_get_api_key())
    return render_template("ai_narratives.html",
                           active="ai",
                           narratives=narratives,
                           api_key_set=api_key_set,
                           pipeline=pipeline_state)


@app.route("/api/generate-narratives", methods=["POST"])
def generate_narratives():
    try:
        from analysis.ai_narrator import generate_all_narratives
        result = generate_all_narratives()
        if result.get("error") == "no_api_key":
            return jsonify({"error": "No API key. Set ANTHROPIC_API_KEY."}), 400
        return jsonify({"status": "ok", "narrative_count": result.get("narrative_count", 0)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
# Routes — Regional Dashboards
# ══════════════════════════════════════════════════════════════

@app.route("/regional")
def regional_hub():
    """Serve the regional hub — links all 8 market dashboards."""
    hub = BASE_DIR / "data/dashboards/index.html"
    if hub.exists():
        return send_file(str(hub))
    # Hub not built yet — build it now
    try:
        from analysis.regional.regional_analyzer import analyze_all_regions
        from visualization.regional_dashboard import build_all_regional_dashboards
        reports = analyze_all_regions()
        build_all_regional_dashboards(reports)
        if hub.exists():
            return send_file(str(hub))
    except Exception as e:
        logger.error(f"Could not build regional hub: {e}")
    return "<p style='padding:40px;font-family:sans-serif'>Regional hub not available. Run <code>python main.py --skip-scrape</code> first.</p>"


@app.route("/regional/<code>")
def regional_dashboard(code):
    """Serve a specific regional market dashboard."""
    code = code.upper()
    dash = BASE_DIR / f"data/dashboards/dashboard_{code}.html"
    if dash.exists():
        return send_file(str(dash))
    return f"<p style='padding:40px;font-family:sans-serif'>Dashboard for {code} not found. Run the pipeline first.</p>", 404


# ══════════════════════════════════════════════════════════════
# JSON API
# ══════════════════════════════════════════════════════════════

@app.route("/api/status")
def api_status():
    report = load_latest_report()
    opp    = report.get("opportunity_leaderboard", [])
    meta   = report.get("report_metadata", {})
    return jsonify({
        "pipeline_running": pipeline_state["running"],
        "last_run":         pipeline_state["last_run"],
        "last_status":      pipeline_state["last_status"],
        "report_generated": meta.get("generated_at"),
        "records_analyzed": meta.get("records_analyzed", 0),
        "top_opportunities": [
            {"sector": o["sector"], "score": o["opportunity_score"]}
            for o in opp[:5]
        ]
    })


@app.route("/api/history")
def api_history():
    return jsonify(load_history())


@app.route("/api/report")
def api_report():
    return jsonify(load_latest_report())


@app.route("/api/regional/<code>")
def api_regional(code):
    """Return JSON report for a specific region."""
    path = BASE_DIR / f"data/regional/{code.upper()}/report_{code.upper()}.json"
    if path.exists():
        with open(path) as f:
            return jsonify(json.load(f))
    return jsonify({"error": f"No report for {code}"}), 404


# ══════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  KoruFlux Intelligence Web UI")
    print("  http://localhost:5000")
    print("=" * 55 + "\n")
    app.run(debug=False, host="0.0.0.0", port=5000, threaded=True)
