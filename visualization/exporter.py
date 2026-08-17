"""
KoruFlux Intelligence System
==============================
visualization/exporter.py

Generates client-ready export formats:
  1. Excel workbook  (.xlsx)  — multi-sheet, formatted, ready to email
  2. PDF report      (.pdf)   — generated from HTML via weasyprint or
                                 pdfkit, with fallback to markdown

Run standalone:  python visualization/exporter.py
Or import:       from visualization.exporter import export_all
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("koruflux.exporter")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

REPORTS_DIR   = Path("data/reports")
EXPORTS_DIR   = Path("data/exports")
PROCESSED_DIR = Path("data/processed")
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _load_latest_report() -> dict:
    reports = sorted(REPORTS_DIR.glob("intelligence_report_*.json"), reverse=True)
    if not reports:
        raise FileNotFoundError("No intelligence report found. Run analyzer first.")
    with open(reports[0]) as f:
        return json.load(f)


def _load_context() -> dict:
    ctx = PROCESSED_DIR / "koruflux_context.json"
    if ctx.exists():
        with open(ctx) as f:
            return json.load(f)
    return {}


# ══════════════════════════════════════════════════════════════
# 1. Excel Export
# ══════════════════════════════════════════════════════════════

def export_excel(report: dict = None, context: dict = None) -> Optional[Path]:
    """
    Generate a formatted Excel workbook with 4 sheets:
      1. Opportunity Leaderboard
      2. Sector Heatmap (dimensions)
      3. Client Intelligence Briefs
      4. KoruFlux Context & Pricing
    """
    try:
        import openpyxl
        from openpyxl.styles import (Font, PatternFill, Alignment,
                                      Border, Side, numbers)
        from openpyxl.utils import get_column_letter
    except ImportError:
        logger.error("openpyxl not installed. Run: pip install openpyxl")
        return None

    if report is None:
        report = _load_latest_report()
    if context is None:
        context = _load_context()

    wb = openpyxl.Workbook()

    # ── Colour palette ────────────────────────────────────────
    DARK_TEAL  = "0A2E36"
    TEAL       = "2EC4B6"
    BLUE       = "00B4D8"
    AMBER      = "F4A261"
    YELLOW     = "FFB703"
    RED        = "E63946"
    LIGHT_GRAY = "F8F9FA"
    MID_GRAY   = "E5E7EB"
    WHITE      = "FFFFFF"

    def hdr_style(cell, bg=DARK_TEAL, fg=WHITE, bold=True, size=11):
        cell.font = Font(name="Calibri", bold=bold, color=fg, size=size)
        cell.fill = PatternFill("solid", fgColor=bg)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    def cell_style(cell, bold=False, size=10, color="1A1A2E", wrap=False):
        cell.font = Font(name="Calibri", bold=bold, size=size, color=color)
        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=wrap)

    def score_fill(score):
        if score >= 75: return TEAL
        if score >= 55: return AMBER
        if score >= 35: return YELLOW
        return RED

    def dim_fill(val):
        if val >= 75: return "2EC4B6"
        if val >= 60: return "90E0EF"
        if val >= 45: return "FFB703"
        if val >= 30: return "F4A261"
        return "E63946"

    def set_border(cell, sides="all"):
        thin = Side(style="thin", color=MID_GRAY)
        b = Border(left=thin, right=thin, top=thin, bottom=thin)
        cell.border = b

    # ── Sheet 1: Opportunity Leaderboard ─────────────────────
    ws1 = wb.active
    ws1.title = "Opportunity Leaderboard"
    ws1.sheet_view.showGridLines = False

    # Title row
    ws1.merge_cells("A1:J1")
    title_cell = ws1["A1"]
    title_cell.value = "KoruFlux Intelligence — Opportunity Leaderboard"
    title_cell.font = Font(name="Calibri", bold=True, size=16, color=WHITE)
    title_cell.fill = PatternFill("solid", fgColor=DARK_TEAL)
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws1.row_dimensions[1].height = 36

    # Sub-title
    ws1.merge_cells("A2:J2")
    sub = ws1["A2"]
    sub.value = f"Kenya & East Africa · Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC"
    sub.font = Font(name="Calibri", size=10, color="8D99AE")
    sub.alignment = Alignment(horizontal="center")
    ws1.row_dimensions[2].height = 20

    # Headers row 3
    headers = ["#", "Sector", "Score", "Tier", "Sentiment",
               "Mentions", "Market Size", "Growth Rate", "Reg. Clarity", "Comp. Gap"]
    for col, h in enumerate(headers, 1):
        c = ws1.cell(row=3, column=col, value=h)
        hdr_style(c)
        set_border(c)
    ws1.row_dimensions[3].height = 28

    # Data rows
    opp = report.get("opportunity_leaderboard", [])
    for i, o in enumerate(opp):
        row = 4 + i
        sentiment = o.get("sentiment") or {}
        dims = o.get("dimensions") or {}
        values = [
            i + 1,
            o["sector"],
            o["opportunity_score"],
            o["tier"].split(" ", 1)[1] if " " in o["tier"] else o["tier"],
            sentiment.get("momentum", "—"),
            o["mention_count"],
            dims.get("market_size", "—"),
            dims.get("growth_rate", "—"),
            dims.get("regulatory_clarity", "—"),
            dims.get("competitive_gap", "—"),
        ]
        bg = LIGHT_GRAY if i % 2 == 0 else WHITE
        for col, val in enumerate(values, 1):
            c = ws1.cell(row=row, column=col, value=val)
            c.fill = PatternFill("solid", fgColor=bg)
            cell_style(c)
            set_border(c)
            # Colour-code score
            if col == 3:
                sfill = score_fill(o["opportunity_score"])
                c.fill = PatternFill("solid", fgColor=sfill)
                c.font = Font(name="Calibri", bold=True, size=12, color=WHITE)
                c.alignment = Alignment(horizontal="center", vertical="center")

    # Column widths
    widths = [5, 18, 10, 26, 16, 12, 14, 14, 14, 14]
    for col, w in enumerate(widths, 1):
        ws1.column_dimensions[get_column_letter(col)].width = w

    # ── Sheet 2: Sector Heatmap ───────────────────────────────
    ws2 = wb.create_sheet("Sector Heatmap")
    ws2.sheet_view.showGridLines = False

    ws2.merge_cells("A1:H1")
    t = ws2["A1"]
    t.value = "KoruFlux — Sector Intelligence Heatmap (Dimension Scores 0–100)"
    t.font  = Font(name="Calibri", bold=True, size=14, color=WHITE)
    t.fill  = PatternFill("solid", fgColor=DARK_TEAL)
    t.alignment = Alignment(horizontal="center", vertical="center")
    ws2.row_dimensions[1].height = 32

    dims_list  = ["market_size", "growth_rate", "regulatory_clarity",
                  "ecosystem_maturity", "competitive_gap", "tech_readiness"]
    dim_labels = ["Market Size", "Growth Rate", "Reg. Clarity",
                  "Ecosystem", "Comp. Gap", "Tech Ready"]

    hdr_row = ["Sector"] + dim_labels + ["SCORE"]
    for col, h in enumerate(hdr_row, 1):
        c = ws2.cell(row=2, column=col, value=h)
        hdr_style(c, bg=DARK_TEAL)
        set_border(c)
    ws2.row_dimensions[2].height = 24

    for i, o in enumerate(opp):
        row = 3 + i
        dims = o.get("dimensions") or {}
        ws2.cell(row=row, column=1, value=o["sector"]).font = Font(bold=True, name="Calibri")
        ws2.cell(row=row, column=1).alignment = Alignment(horizontal="left", vertical="center")
        set_border(ws2.cell(row=row, column=1))

        for j, dim in enumerate(dims_list):
            val = dims.get(dim, 0)
            c = ws2.cell(row=row, column=2 + j, value=val)
            c.fill = PatternFill("solid", fgColor=dim_fill(val))
            c.font = Font(name="Calibri", bold=True, size=10,
                          color=WHITE if val >= 60 or val < 30 else "1A1A2E")
            c.alignment = Alignment(horizontal="center", vertical="center")
            set_border(c)

        # Final score column
        sc = ws2.cell(row=row, column=8, value=o["opportunity_score"])
        sc.fill = PatternFill("solid", fgColor=score_fill(o["opportunity_score"]))
        sc.font = Font(name="Calibri", bold=True, color=WHITE, size=11)
        sc.alignment = Alignment(horizontal="center", vertical="center")
        set_border(sc)

    for col in range(1, 9):
        ws2.column_dimensions[get_column_letter(col)].width = 16
    ws2.column_dimensions["A"].width = 20

    # ── Sheet 3: Client Intelligence Briefs ──────────────────
    ws3 = wb.create_sheet("Client Briefs")
    ws3.sheet_view.showGridLines = False

    ws3.merge_cells("A1:F1")
    t3 = ws3["A1"]
    t3.value = "KoruFlux — Client Intelligence Briefs"
    t3.font  = Font(name="Calibri", bold=True, size=14, color=WHITE)
    t3.fill  = PatternFill("solid", fgColor=DARK_TEAL)
    t3.alignment = Alignment(horizontal="center", vertical="center")
    ws3.row_dimensions[1].height = 32

    ci = report.get("client_insights", {})
    current_row = 2

    for profile_key, label_prefix in [
        ("web3_startup_kenya", "🚀 Web3 Startup Entering Kenya"),
        ("ai_fintech_ea", "🤖 AI Fintech — East Africa")
    ]:
        # Profile header
        ws3.merge_cells(f"A{current_row}:F{current_row}")
        ph = ws3.cell(row=current_row, column=1, value=label_prefix)
        ph.font = Font(name="Calibri", bold=True, size=12, color=WHITE)
        ph.fill = PatternFill("solid", fgColor=BLUE)
        ph.alignment = Alignment(horizontal="left", vertical="center")
        ws3.row_dimensions[current_row].height = 24
        current_row += 1

        recs = ci.get(profile_key, {}).get("recommendations", [])
        for rec in recs:
            # Sector row
            c = ws3.cell(row=current_row, column=1, value=rec["sector"])
            c.font = Font(name="Calibri", bold=True, size=11, color=DARK_TEAL)
            c.fill = PatternFill("solid", fgColor="EEF9F8")

            sc = ws3.cell(row=current_row, column=2, value=rec["score"])
            sc.font = Font(name="Calibri", bold=True, size=13,
                           color=score_fill(rec["score"]))
            sc.alignment = Alignment(horizontal="center")

            tier_c = ws3.cell(row=current_row, column=3,
                               value=rec["tier"].split(" ", 1)[1] if " " in rec["tier"] else rec["tier"])
            tier_c.font = Font(name="Calibri", size=10, color="444444")
            current_row += 1

            # Recommendation text
            ws3.merge_cells(f"A{current_row}:F{current_row}")
            rc = ws3.cell(row=current_row, column=1, value=rec["recommendation"])
            rc.font = Font(name="Calibri", size=10, color="333333")
            rc.alignment = Alignment(wrap_text=True, vertical="top")
            ws3.row_dimensions[current_row].height = 60
            current_row += 1

            # Action items
            for action in rec.get("action_items", []):
                ws3.merge_cells(f"B{current_row}:F{current_row}")
                ac = ws3.cell(row=current_row, column=2, value=f"• {action}")
                ac.font = Font(name="Calibri", size=10, color="555555")
                ac.alignment = Alignment(wrap_text=True)
                current_row += 1

            current_row += 1  # spacer

        current_row += 1  # spacer between profiles

    ws3.column_dimensions["A"].width = 22
    ws3.column_dimensions["B"].width = 10
    ws3.column_dimensions["C"].width = 26
    for col in "DEF":
        ws3.column_dimensions[col].width = 20

    # ── Sheet 4: KoruFlux Context ─────────────────────────────
    ws4 = wb.create_sheet("KoruFlux Context")
    ws4.sheet_view.showGridLines = False

    ws4.merge_cells("A1:D1")
    t4 = ws4["A1"]
    t4.value = "KoruFlux — Company Context & Engagement Pricing"
    t4.font  = Font(name="Calibri", bold=True, size=14, color=WHITE)
    t4.fill  = PatternFill("solid", fgColor=DARK_TEAL)
    t4.alignment = Alignment(horizontal="center", vertical="center")
    ws4.row_dimensions[1].height = 32

    r = 2
    for eng in context.get("engagement_types", []):
        for col, val in enumerate([eng["type"], eng["duration"], eng["price"]], 1):
            c = ws4.cell(row=r, column=col, value=val)
            c.font = Font(name="Calibri",
                          bold=(col == 1),
                          size=10,
                          color=BLUE if col == 3 else "1A1A2E")
            c.fill = PatternFill("solid", fgColor=LIGHT_GRAY if r % 2 == 0 else WHITE)
            set_border(c)
        r += 1

    for col, w in zip("ABCD", [28, 18, 22, 18]):
        ws4.column_dimensions[col].width = w

    # ── Save ──────────────────────────────────────────────────
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    outfile  = EXPORTS_DIR / f"KoruFlux_Intelligence_{date_str}.xlsx"
    wb.save(outfile)
    logger.info(f"📊 Excel report saved → {outfile}")
    return outfile


# ══════════════════════════════════════════════════════════════
# 2. Markdown Report (PDF fallback)
# ══════════════════════════════════════════════════════════════

def export_markdown_report(report: dict = None, context: dict = None) -> Path:
    """
    Generate a clean Markdown report — acts as PDF source
    or standalone shareable document.
    """
    if report is None:
        report = _load_latest_report()
    if context is None:
        context = _load_context()

    meta = report.get("report_metadata", {})
    opp  = report.get("opportunity_leaderboard", [])
    ci   = report.get("client_insights", {})
    risks= report.get("risk_flags", [])
    themes = report.get("theme_clusters", {})

    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

    lines = [
        "# KoruFlux Intelligence Report",
        f"**{date_str}** · Kenya & East Africa",
        "",
        "> *Build. Transition. Strategize. Land.* — hello@koruflux.io",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        f"This report analyses **{len(opp)} sectors** across the Kenya and East Africa",
        "technology landscape, combining live market intelligence with KoruFlux's",
        "proprietary scoring framework.",
        "",
        f"- **Top opportunity:** {opp[0]['sector']} ({opp[0]['opportunity_score']}/100)" if opp else "",
        f"- **High-opportunity sectors:** {len([o for o in opp if o['opportunity_score'] >= 75])}",
        f"- **Risk signals detected:** {len(risks)}",
        f"- **Records analysed:** {meta.get('records_analyzed', 0)}",
        "",
        "---",
        "",
        "## Opportunity Leaderboard",
        "",
        "| Sector | Score | Tier | Sentiment |",
        "|--------|-------|------|-----------|",
    ]

    for o in opp:
        sentiment = (o.get("sentiment") or {}).get("momentum", "—")
        tier = o["tier"].split(" ", 1)[1] if " " in o["tier"] else o["tier"]
        lines.append(f"| **{o['sector']}** | {o['opportunity_score']} | {tier} | {sentiment} |")

    lines += ["", "---", "", "## Strategic Theme Analysis", ""]

    for theme, data in themes.items():
        sig = data["signal"]
        sc  = data["theme_score"]
        sec = ", ".join(s["sector"] for s in data["sectors"])
        lines.append(f"### {theme}  `{sc}/100`  {sig}")
        lines.append(f"*Sectors: {sec}*")
        lines.append("")

    lines += ["---", "", "## Client Intelligence Briefs", ""]

    for profile_key, title in [
        ("web3_startup_kenya", "Web3 Startup Entering Kenya"),
        ("ai_fintech_ea", "AI Fintech in East Africa")
    ]:
        lines.append(f"### {title}")
        lines.append("")
        recs = ci.get(profile_key, {}).get("recommendations", [])
        for rec in recs:
            lines.append(f"#### {rec['sector']}  —  Score: {rec.get('score', rec.get('opportunity_score','—'))}")
            lines.append("")
            lines.append(rec["recommendation"])
            lines.append("")
            lines.append("**Action Items:**")
            for action in rec.get("action_items", []):
                lines.append(f"- {action}")
            lines.append("")

    if risks:
        lines += ["---", "", "## Risk Signals", "", "| Signal | Source | Severity |",
                  "|--------|--------|----------|"]
        for r in risks:
            lines.append(f"| {r['risk_keyword']} | {r.get('source','—')} | **{r.get('severity','—')}** |")
        lines.append("")

    lines += [
        "---",
        "",
        "## About KoruFlux",
        "",
        "KoruFlux is a Nairobi-based technology and strategy consultancy operating at the",
        "intersection of Web3, AI, Data Analytics, and African market entry.",
        "",
        "**Engagement Types:**",
        "",
    ]

    for eng in context.get("engagement_types", []):
        lines.append(f"- **{eng['type']}** — {eng['duration']} — {eng['price']}")

    lines += [
        "",
        "---",
        f"*Confidential · KoruFlux · Nairobi, Kenya · {date_str}*"
    ]

    date_key = datetime.now(timezone.utc).strftime("%Y%m%d")
    outfile  = EXPORTS_DIR / f"KoruFlux_Intelligence_{date_key}.md"
    with open(outfile, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"📝 Markdown report saved → {outfile}")
    return outfile


# ══════════════════════════════════════════════════════════════
# 3. Master Export Runner
# ══════════════════════════════════════════════════════════════

def export_all(report: dict = None, context: dict = None) -> dict:
    """Generate all export formats."""
    if report is None:
        report = _load_latest_report()
    if context is None:
        context = _load_context()

    outputs = {}

    logger.info("📤 Generating exports...")

    # Excel
    xlsx = export_excel(report, context)
    if xlsx:
        outputs["excel"] = str(xlsx)

    # Markdown
    md = export_markdown_report(report, context)
    outputs["markdown"] = str(md)

    logger.info(f"✅ Exports complete: {list(outputs.keys())}")
    return outputs


if __name__ == "__main__":
    outputs = export_all()
    for fmt, path in outputs.items():
        print(f"  {fmt:<12} → {path}")
