"""
KoruFlux Intelligence System
==============================
analysis/ai_narrator.py  —  AI-Powered Insight Generation

Calls the Anthropic API (claude-sonnet-4-20250514) to generate:
  - Executive narrative summaries from scored data
  - Client-specific intelligence briefs (in natural language)
  - Market entry recommendations
  - Risk assessments with mitigation strategies
  - Opportunity memos (ready to send to clients)

No SDK required — uses requests directly.

Setup:
  Set your API key in config/config.yaml under:
    ai:
      api_key: "sk-ant-..."
  OR set environment variable: ANTHROPIC_API_KEY

Usage:
  from analysis.ai_narrator import generate_all_narratives
  narratives = generate_all_narratives(report, context)
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger("koruflux.ai_narrator")

REPORTS_DIR   = Path("data/reports")
PROCESSED_DIR = Path("data/processed")
AI_DIR        = Path("data/ai_narratives")
AI_DIR.mkdir(parents=True, exist_ok=True)

API_URL = "https://api.anthropic.com/v1/messages"
MODEL   = "claude-sonnet-4-20250514"


# ══════════════════════════════════════════════════════════════
# API Client
# ══════════════════════════════════════════════════════════════

def _get_api_key() -> Optional[str]:
    """Retrieve API key from env or config."""
    # 1. Environment variable (preferred)
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key

    # 2. Config file
    try:
        import yaml
        with open("config/config.yaml") as f:
            cfg = yaml.safe_load(f)
        key = cfg.get("ai", {}).get("api_key")
        if key and key != "sk-ant-YOUR_KEY_HERE":
            return key
    except Exception:
        pass

    return None


def _call_api(system_prompt: str, user_prompt: str,
               max_tokens: int = 1200) -> Optional[str]:
    """
    Make a single call to the Anthropic Messages API.
    Returns the text response or None on failure.
    """
    api_key = _get_api_key()
    if not api_key:
        logger.warning(
            "No Anthropic API key found. Set ANTHROPIC_API_KEY env var "
            "or add 'ai.api_key' to config/config.yaml"
        )
        return None

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    payload = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": user_prompt}
        ]
    }

    try:
        resp = requests.post(API_URL, headers=headers,
                             json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]
    except requests.HTTPError as e:
        logger.error(f"API HTTP error: {e.response.status_code} — {e.response.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"API call failed: {e}")
        return None


# ══════════════════════════════════════════════════════════════
# Prompt Builders
# ══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are a senior market intelligence analyst at KoruFlux, 
a Nairobi-based strategy consultancy specialising in Web3, AI, and African market entry.

Your writing style is:
- Direct and professional — no filler phrases
- Data-driven — reference specific scores, figures, and signals
- Actionable — every paragraph ends with a clear implication or recommendation
- Confident but honest about uncertainty
- Written for C-suite readers at technology companies

KoruFlux context:
- Founded 2026, headquartered in Nairobi, Kenya
- Serves: Web3 startups, international companies entering Africa, African fintechs, Web2→Web3 transitions
- Target markets: Kenya/Nairobi, East Africa, Nigeria, US, EU, UK, Singapore, UAE
- Tagline: Build. Transition. Strategize. Land.
- Contact: hello@koruflux.io

Do not use bullet points excessively. Write in paragraphs. 
Do not use phrases like "In conclusion", "It is worth noting", "Importantly".
Be specific. Use numbers. Be direct."""


def _build_executive_summary_prompt(report: dict, context: dict) -> str:
    opp  = report.get("opportunity_leaderboard", [])
    meta = report.get("report_metadata", {})
    themes = report.get("theme_clusters", {})
    risks  = report.get("risk_flags", [])
    regions = report.get("market_summary", {}).get("top_regions_by_mention", [])

    top5 = [f"{o['sector']} ({o['opportunity_score']}/100, {o['tier'].split(' ',1)[-1]})"
            for o in opp[:5]]
    theme_summary = ", ".join(
        f"{k}: {v['theme_score']}/100 {v['signal']}"
        for k, v in themes.items()
    )
    risk_summary = ", ".join(r['risk_keyword'] for r in risks[:5]) if risks else "none detected"
    region_summary = ", ".join(r[0] for r in regions[:8]) if regions else "global"

    return f"""Write a 3-paragraph executive summary for a KoruFlux intelligence report.

DATA:
- Report date: {meta.get('generated_at', '')[:10]}
- Records analysed: {meta.get('records_analyzed', 0)}
- Markets covered: {', '.join(meta.get('markets_covered', []))}
- Top 5 sectors by opportunity score: {', '.join(top5)}
- Strategic theme scores: {theme_summary}
- Risk signals detected: {risk_summary}
- Most active regions in data: {region_summary}

Write exactly 3 paragraphs:
1. Overall market conditions and what the data shows (2-3 sentences)
2. The 2-3 highest-signal opportunities and why they matter now (3-4 sentences)
3. Key risks and the strategic posture KoruFlux recommends (2-3 sentences)

Do not add a title or headers. Write the 3 paragraphs directly."""


def _build_client_brief_prompt(profile_key: str, profile_data: dict,
                                report: dict, context: dict) -> str:
    recs = profile_data.get("recommendations", [])
    markets = profile_data.get("markets", [])
    profile_label = profile_data.get("profile", profile_key)

    rec_data = ""
    for r in recs:
        dims = r.get("dimensions", {})
        rec_data += (
            f"\n  Sector: {r['sector']} | Score: {r.get('score', '?')}/100 | {r['tier']}\n"
            f"  Pre-written rec: {r['recommendation'][:200]}\n"
            f"  Actions: {'; '.join(r.get('action_items', [])[:3])}\n"
        )

    risks = report.get("risk_flags", [])
    risk_txt = ", ".join(r['risk_keyword'] for r in risks[:4]) if risks else "none"

    return f"""Write a client intelligence brief for this KoruFlux client profile.

CLIENT PROFILE: {profile_label}
TARGET MARKETS: {', '.join(markets)}

SECTOR DATA:
{rec_data}

RISK SIGNALS: {risk_txt}

Write a professional intelligence brief with these sections:
1. MARKET POSITION (1 paragraph): What is the current state of this client's target market?
2. PRIMARY OPPORTUNITY (1 paragraph): What is the single biggest opportunity and why now?
3. ENTRY STRATEGY (1 paragraph): Concrete first steps for market entry or expansion.
4. RISK WATCH (2-3 sentences): Key risks and how to mitigate them.
5. KORUFLUX RECOMMENDATION (1 sentence): A direct, confident recommendation.

Use the section labels as headers (bold). Be specific with numbers and timelines.
Write for a decision-maker who has 3 minutes to read this."""


def _build_opportunity_memo_prompt(sector: str, score_data: dict,
                                    report: dict) -> str:
    dims = score_data.get("dimensions", {})
    sentiment = score_data.get("sentiment", {})
    regions = report.get("market_summary", {}).get("top_regions_by_mention", [])

    return f"""Write a one-page opportunity memo for the {sector} sector in Africa/global markets.

INTELLIGENCE DATA:
- Opportunity score: {score_data.get('opportunity_score')}/100
- Tier: {score_data.get('tier')}
- Sentiment: {sentiment.get('label', 'neutral')} ({sentiment.get('momentum', '→ stable')})
- Market size score: {dims.get('market_size', '?')}/100
- Growth rate score: {dims.get('growth_rate', '?')}/100
- Regulatory clarity: {dims.get('regulatory_clarity', '?')}/100
- Competitive gap: {dims.get('competitive_gap', '?')}/100
- Ecosystem maturity: {dims.get('ecosystem_maturity', '?')}/100
- Active regions: {', '.join(r[0] for r in regions[:6]) if regions else 'Africa'}

Write a concise opportunity memo with:
- 2-sentence headline finding
- Why this sector scores {score_data.get('opportunity_score')}/100 (reference the dimension scores)
- The specific opportunity within this sector for a company entering Kenya/East Africa
- One concrete action to take in the next 30 days
- One risk to watch

Maximum 250 words. No fluff. Write like a McKinsey analyst."""


# ══════════════════════════════════════════════════════════════
# Narrative Generators
# ══════════════════════════════════════════════════════════════

def generate_executive_summary(report: dict, context: dict) -> Optional[str]:
    """Generate AI executive summary narrative."""
    logger.info("  Generating executive summary...")
    prompt = _build_executive_summary_prompt(report, context)
    result = _call_api(SYSTEM_PROMPT, prompt, max_tokens=600)
    if result:
        logger.info("  Executive summary generated")
    return result


def generate_client_brief(profile_key: str, profile_data: dict,
                           report: dict, context: dict) -> Optional[str]:
    """Generate AI narrative for a specific client profile."""
    logger.info(f"  Generating brief for: {profile_key}...")
    prompt = _build_client_brief_prompt(profile_key, profile_data, report, context)
    result = _call_api(SYSTEM_PROMPT, prompt, max_tokens=800)
    if result:
        logger.info(f"  Brief generated for {profile_key}")
    return result


def generate_sector_memo(sector: str, score_data: dict,
                          report: dict) -> Optional[str]:
    """Generate opportunity memo for a top-scoring sector."""
    logger.info(f"  Generating sector memo: {sector}...")
    prompt = _build_opportunity_memo_prompt(sector, score_data, report)
    result = _call_api(SYSTEM_PROMPT, prompt, max_tokens=400)
    if result:
        logger.info(f"  Memo generated for {sector}")
    return result


def generate_all_narratives(report: dict = None,
                             context: dict = None) -> dict:
    """
    Master function — generates all AI narratives for a report.
    Returns dict of narratives, saves to data/ai_narratives/.

    Requires ANTHROPIC_API_KEY to be set.
    Falls back gracefully if key is missing.
    """
    if report is None:
        reports = sorted(REPORTS_DIR.glob("intelligence_report_*.json"), reverse=True)
        if not reports:
            logger.error("No report found")
            return {}
        with open(reports[0]) as f:
            report = json.load(f)

    if context is None:
        ctx_path = PROCESSED_DIR / "koruflux_context.json"
        context = json.load(open(ctx_path)) if ctx_path.exists() else {}

    api_key = _get_api_key()
    if not api_key:
        logger.warning(
            "\n" + "="*55 +
            "\n  AI narratives skipped — no API key configured." +
            "\n  To enable: set ANTHROPIC_API_KEY environment variable" +
            "\n  or add to config/config.yaml under 'ai.api_key'" +
            "\n" + "="*55
        )
        return {"error": "no_api_key", "narratives": {}}

    logger.info("Generating AI narratives...")
    narratives = {}

    # 1. Executive summary
    exec_summary = generate_executive_summary(report, context)
    if exec_summary:
        narratives["executive_summary"] = exec_summary
    time.sleep(1)

    # 2. Client briefs (top 2 profiles)
    ci = report.get("client_insights", {})
    priority_profiles = ["web3_startup_kenya", "ai_fintech_ea",
                         "intl_corp_africa_entry", "web3_hub_expansion"]

    for profile_key in priority_profiles[:2]:  # 2 to manage API cost
        if profile_key in ci:
            brief = generate_client_brief(
                profile_key, ci[profile_key], report, context
            )
            if brief:
                narratives[f"client_brief_{profile_key}"] = brief
            time.sleep(1)

    # 3. Top 3 sector memos
    opp = report.get("opportunity_leaderboard", [])
    for sector_data in opp[:3]:
        memo = generate_sector_memo(
            sector_data["sector"], sector_data, report
        )
        if memo:
            narratives[f"sector_memo_{sector_data['sector'].lower()}"] = memo
        time.sleep(1)

    # Save narratives
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "narrative_count": len(narratives),
        "narratives": narratives
    }

    outfile = AI_DIR / f"narratives_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    with open(outfile, "w") as f:
        json.dump(result, f, indent=2)

    logger.info(f"AI narratives saved → {outfile.name}")
    return result


def load_latest_narratives() -> dict:
    """Load the most recently generated AI narratives."""
    files = sorted(AI_DIR.glob("narratives_*.json"), reverse=True)
    if not files:
        return {}
    with open(files[0]) as f:
        return json.load(f)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    result = generate_all_narratives()
    print(f"\nGenerated {result.get('narrative_count', 0)} narratives")
    if result.get("narratives"):
        print("\n--- EXECUTIVE SUMMARY ---")
        print(result["narratives"].get("executive_summary", "Not generated"))
