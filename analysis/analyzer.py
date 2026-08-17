"""
KoruFlux Intelligence System
==============================
analysis/analyzer.py

Intelligence layer that:
  - Scores sentiment (positive / neutral / negative)
  - Computes opportunity scores (0-100) per sector/region combo
  - Clusters insights into strategic themes
  - Generates structured intelligence reports
  - Outputs to data/reports/

Run standalone:  python analysis/analyzer.py
Or import:       from analysis.analyzer import run_analysis
"""

import json
import logging
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger("koruflux.analyzer")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

PROCESSED_DIR = Path("data/processed")
REPORTS_DIR = Path("data/reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = Path("config/config.yaml")


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


# ══════════════════════════════════════════════════════════════
# 1. Sentiment Scoring
# ══════════════════════════════════════════════════════════════

def score_sentiment(text: str, cfg: dict) -> dict:
    """
    Returns sentiment label and a score from -1.0 (very negative)
    to +1.0 (very positive).
    """
    text_l = text.lower()
    sentiment_cfg = cfg.get("analysis", {}).get("sentiment_keywords", {})

    pos_words = sentiment_cfg.get("positive", [])
    neg_words = sentiment_cfg.get("negative", [])
    neu_words = sentiment_cfg.get("neutral", [])

    pos_hits = sum(1 for w in pos_words if w in text_l)
    neg_hits = sum(1 for w in neg_words if w in text_l)
    neu_hits = sum(1 for w in neu_words if w in text_l)

    total = pos_hits + neg_hits + neu_hits or 1

    # Weighted ratio: neutrals dampen the score
    raw_score = (pos_hits - neg_hits) / total
    # Clamp to [-1, 1]
    score = max(-1.0, min(1.0, raw_score))

    if score > 0.15:
        label = "positive"
        momentum = "↑ growing"
    elif score < -0.15:
        label = "negative"
        momentum = "↓ declining"
    else:
        label = "neutral"
        momentum = "→ stable"

    return {
        "score": round(score, 3),
        "label": label,
        "momentum": momentum,
        "positive_signals": pos_hits,
        "negative_signals": neg_hits
    }


# ══════════════════════════════════════════════════════════════
# 2. Opportunity Scoring Model
# ══════════════════════════════════════════════════════════════

# Static baseline intelligence (Kenya/EA market — updated from KoruFlux docs)
MARKET_BASELINE = {
    "DeFi": {
        "market_size": 70,    # relative 0-100
        "growth_rate": 85,
        "regulatory_clarity": 45,  # Kenya still drafting frameworks
        "ecosystem_maturity": 55,
        "competitive_gap": 75,
        "tech_readiness": 65
    },
    "Payments": {
        "market_size": 90,    # M-Pesa dominance; massive addressable market
        "growth_rate": 75,
        "regulatory_clarity": 70,  # CBK relatively clear
        "ecosystem_maturity": 80,
        "competitive_gap": 40,     # M-Pesa entrenched
        "tech_readiness": 85
    },
    "AI_Fintech": {
        "market_size": 80,
        "growth_rate": 90,
        "regulatory_clarity": 55,
        "ecosystem_maturity": 50,
        "competitive_gap": 80,     # Low competition in EA
        "tech_readiness": 60
    },
    "NFT": {
        "market_size": 40,
        "growth_rate": 50,
        "regulatory_clarity": 30,
        "ecosystem_maturity": 35,
        "competitive_gap": 85,
        "tech_readiness": 50
    },
    "DAO": {
        "market_size": 35,
        "growth_rate": 60,
        "regulatory_clarity": 20,
        "ecosystem_maturity": 30,
        "competitive_gap": 90,
        "tech_readiness": 45
    },
    "RWA": {
        "market_size": 75,
        "growth_rate": 80,
        "regulatory_clarity": 40,
        "ecosystem_maturity": 40,
        "competitive_gap": 85,
        "tech_readiness": 55
    },
    "Infrastructure": {
        "market_size": 60,
        "growth_rate": 70,
        "regulatory_clarity": 50,
        "ecosystem_maturity": 50,
        "competitive_gap": 65,
        "tech_readiness": 55
    },
    "AgriTech": {
        "market_size": 65,
        "growth_rate": 65,
        "regulatory_clarity": 60,
        "ecosystem_maturity": 55,
        "competitive_gap": 70,
        "tech_readiness": 50
    },
    "Regulatory": {
        "market_size": 50,
        "growth_rate": 60,
        "regulatory_clarity": 65,
        "ecosystem_maturity": 60,
        "competitive_gap": 55,
        "tech_readiness": 60
    }
}


def compute_opportunity_score(sector: str, sentiment_score: float,
                               mention_count: int, cfg: dict) -> dict:
    """
    Composite opportunity score (0–100) combining:
      - Market baseline (static intelligence)
      - Live sentiment signal (from scraped data)
      - Mention frequency (proxy for momentum)
    """
    weights = cfg.get("analysis", {}).get("opportunity_weights", {
        "market_size": 0.25,
        "growth_rate": 0.20,
        "regulatory_clarity": 0.20,
        "ecosystem_maturity": 0.15,
        "competitive_gap": 0.10,
        "tech_readiness": 0.10
    })

    baseline = MARKET_BASELINE.get(sector, {
        k: 50 for k in weights.keys()
    })

    # Weighted baseline score
    base_score = sum(
        baseline.get(dim, 50) * weight
        for dim, weight in weights.items()
    )

    # Sentiment adjustment: ±15 points max
    sentiment_adjustment = sentiment_score * 15

    # Mention frequency boost: log-scale, max +10 points
    mention_boost = min(10, math.log1p(mention_count) * 2.5)

    final_score = base_score + sentiment_adjustment + mention_boost
    final_score = max(0, min(100, round(final_score, 1)))

    # Risk tier
    if final_score >= 75:
        tier = "HIGH OPPORTUNITY"
    elif final_score >= 55:
        tier = "MODERATE OPPORTUNITY"
    elif final_score >= 35:
        tier = "EMERGING / MONITOR"
    else:
        tier = "HIGH RISK / LOW PRIORITY"

    return {
        "sector": sector,
        "opportunity_score": final_score,
        "tier": tier,
        "baseline_score": round(base_score, 1),
        "sentiment_adjustment": round(sentiment_adjustment, 1),
        "mention_boost": round(mention_boost, 1),
        "dimensions": baseline
    }


# ══════════════════════════════════════════════════════════════
# 3. Theme Clustering
# ══════════════════════════════════════════════════════════════

THEME_CLUSTERS = {
    "Market Demand": ["Payments", "AI_Fintech", "RWA", "AgriTech"],
    "Competitive Landscape": ["Payments", "DeFi", "Infrastructure"],
    "Technology Trends": ["DeFi", "AI_Fintech", "Infrastructure", "DAO"],
    "Investment Signals": ["DeFi", "RWA", "AI_Fintech", "NFT"],
    "Regulatory Environment": ["Regulatory", "Payments", "DeFi"]
}


def cluster_by_theme(opportunity_scores: list) -> dict:
    score_map = {s["sector"]: s["opportunity_score"] for s in opportunity_scores}
    themed = {}
    for theme, sectors in THEME_CLUSTERS.items():
        relevant = [
            {"sector": s, "score": score_map.get(s, 0)}
            for s in sectors if s in score_map
        ]
        avg = sum(r["score"] for r in relevant) / len(relevant) if relevant else 0
        themed[theme] = {
            "sectors": relevant,
            "theme_score": round(avg, 1),
            "signal": "↑ Strong" if avg >= 65 else "→ Moderate" if avg >= 45 else "↓ Weak"
        }
    return themed


# ══════════════════════════════════════════════════════════════
# 4. Insight & Recommendation Engine
# ══════════════════════════════════════════════════════════════

CLIENT_PROFILES = {
    "web3_startup_kenya": {
        "label": "Web3 Startup Entering Kenya",
        "markets": ["Kenya", "East Africa"],
        "priority_sectors": ["DeFi", "Payments", "Infrastructure"],
        "key_risks": ["regulatory_clarity", "ecosystem_maturity"],
        "key_strengths": ["competitive_gap", "growth_rate"]
    },
    "ai_fintech_ea": {
        "label": "AI Fintech — East Africa",
        "markets": ["Kenya", "East Africa", "Nigeria"],
        "priority_sectors": ["AI_Fintech", "Payments", "AgriTech"],
        "key_risks": ["tech_readiness", "regulatory_clarity"],
        "key_strengths": ["market_size", "competitive_gap"]
    },
    "intl_corp_africa_entry": {
        "label": "International Corp Entering Africa (US/EU/UK)",
        "markets": ["United States", "European Union", "United Kingdom", "Kenya", "East Africa"],
        "priority_sectors": ["Payments", "RWA", "AI_Fintech", "Regulatory"],
        "key_risks": ["regulatory_clarity", "ecosystem_maturity"],
        "key_strengths": ["market_size", "competitive_gap"]
    },
    "web3_hub_expansion": {
        "label": "Web3 Protocol Expanding to Singapore / UAE",
        "markets": ["Singapore", "UAE", "United States"],
        "priority_sectors": ["DeFi", "RWA", "Infrastructure", "DAO"],
        "key_risks": ["regulatory_clarity", "tech_readiness"],
        "key_strengths": ["ecosystem_maturity", "competitive_gap"]
    }
}


def generate_recommendations(scores: list, profile_key: str) -> list:
    profile = CLIENT_PROFILES.get(profile_key, {})
    priority = profile.get("priority_sectors", [])
    key_strengths = profile.get("key_strengths", [])
    key_risks = profile.get("key_risks", [])

    score_map = {s["sector"]: s for s in scores}
    recs = []

    for sector in priority:
        data = score_map.get(sector)
        if not data:
            continue
        dims = data.get("dimensions", {})
        strengths = [k for k in key_strengths if dims.get(k, 0) >= 65]
        risks = [k for k in key_risks if dims.get(k, 0) <= 50]

        rec = {
            "sector": sector,
            "score": data["opportunity_score"],
            "tier": data["tier"],
            "recommendation": _build_rec_text(sector, data, strengths, risks, profile_key),
            "action_items": _build_actions(sector, profile_key)
        }
        recs.append(rec)

    return sorted(recs, key=lambda x: x["score"], reverse=True)


def _build_rec_text(sector: str, data: dict, strengths: list,
                     risks: list, profile: str) -> str:
    score = data["opportunity_score"]
    if profile == "web3_startup_kenya":
        if sector == "DeFi" and score >= 60:
            return (
                "Kenya's DeFi market shows strong upside. Regulatory clarity is improving "
                "post-CMA sandbox framework. Entry via lending/stablecoin products aligned "
                "with existing M-Pesa corridors offers fastest PMF path. Partner with local "
                "SACCOs or MFIs to build trust and distribution."
            )
        elif sector == "Payments":
            return (
                "Payments is hyper-competitive (M-Pesa ~95% mobile money dominance) but "
                "cross-border and B2B stablecoin rails remain open. Focus on the $48B East "
                "African remittance corridor — USDT/USDC rails outcompete SWIFT on cost. "
                "Regulatory path: engage CBK directly, use KoruFlux's existing contacts."
            )
        elif sector == "Infrastructure":
            return (
                "Node infrastructure and oracle networks in EA are thin — significant gap "
                "for middleware/tooling plays. Low-risk entry: build developer tooling that "
                "doesn't require local regulatory approval. GitHub activity in 'blockchain Kenya' "
                "is growing 40%+ YoY signalling developer demand."
            )
    elif profile == "ai_fintech_ea":
        if sector == "AI_Fintech" and score >= 65:
            return (
                "East Africa represents one of the highest-upside AI fintech markets globally. "
                "Thin incumbent AI infrastructure, massive mobile-first data pools, and a "
                "young (median age 20) digitally-native population. Priority use cases: "
                "alternative credit scoring (67% unbanked in EA), fraud detection for mobile "
                "money, and AI-driven KYC automation."
            )
        elif sector == "Payments":
            return (
                "AI + Payments convergence is the core opportunity. M-Pesa processes $314B/year "
                "in Kenya alone. Embedding AI credit, risk, and personalisation layers into "
                "existing payment flows — without replacing the rails — is the fastest GTM. "
                "Regulatory path: partner with licensed EMI or bank for immediate market access."
            )
        elif sector == "AgriTech":
            return (
                "Agricultural AI in EA is underserved and high-impact. 70%+ of EA workforce "
                "is in agriculture. AI-driven crop prediction, supply chain finance, and "
                "satellite data-based insurance represent a $2B+ addressable market by 2028. "
                "USAID and WFP actively funding pilot programmes — useful non-dilutive entry path."
            )

    elif profile == "intl_corp_africa_entry":
        if sector == "Payments":
            return (
                "Africa's payment infrastructure is the primary entry vector for international corps. "
                "The $48B EA remittance corridor and $700B+ pan-Africa mobile money volume offer "
                "immediate B2B revenue. Regulatory path: partner with a licensed Kenyan EMI or bank, "
                "structure under CBK's Payment Service Provider framework. US/EU compliance teams "
                "should note Kenya's AML/CFT framework is FATF-aligned since 2022."
            )
        elif sector == "RWA":
            return (
                "Real World Asset tokenisation is the highest-signal opportunity for international "
                "corporates in Africa. Kenya's land registry digitisation, Nairobi's commercial "
                "real estate market, and agricultural commodity tokenisation all represent "
                "multi-billion dollar TAMs with thin competition. MiCA (EU) and SEC frameworks "
                "are converging — structure now for dual compliance."
            )
        elif sector == "AI_Fintech":
            return (
                "International AI fintech firms have a structural advantage in Africa: "
                "proprietary models trained on global data can be fine-tuned on African datasets "
                "at low marginal cost. Target: SME credit underwriting, trade finance automation, "
                "and B2B payment intelligence. East Africa is the beachhead; Nigeria is scale."
            )
        elif sector == "Regulatory":
            return (
                "Regulatory arbitrage is a genuine opportunity. Kenya's CMA sandbox, Dubai's VARA, "
                "and Singapore's MAS all offer fast-track licensing for international firms. "
                "KoruFlux recommends a multi-jurisdiction structure: Singapore or UAE holding, "
                "Kenya/EA operating entity. Reduces tax burden and maximises regulatory optionality."
            )
    elif profile == "web3_hub_expansion":
        if sector == "DeFi":
            return (
                "Singapore (MAS) and UAE (VARA/ADGM) are the two most permissive DeFi jurisdictions "
                "globally as of 2026. Singapore's MAS Payment Services Act covers DeFi protocols "
                "under a clear licensing regime. UAE's VARA issued comprehensive DeFi regulations "
                "in 2024. Both offer 0% capital gains on crypto. Recommended structure: "
                "Singapore entity for Asia-Pacific, ADGM for MENA, with Kenya as Africa gateway."
            )
        elif sector == "RWA":
            return (
                "RWA tokenisation is the dominant narrative in Singapore and UAE financial markets. "
                "MAS Project Guardian (RWA tokenisation) has $10B+ in committed institutional capital. "
                "DIFC and ADGM both have sandbox frameworks specifically for tokenised securities. "
                "KoruFlux can structure end-to-end: protocol architecture, regulatory filing, "
                "and Africa-side asset origination pipeline."
            )
        elif sector == "Infrastructure":
            return (
                "Web3 infrastructure protocols face minimal regulatory friction in Singapore and UAE. "
                "Both jurisdictions actively recruit node operators, validator sets, and oracle networks. "
                "MAS's $150M Financial Sector Technology and Innovation grant scheme covers "
                "blockchain infrastructure. Dubai's Crypto Oasis has 1,500+ Web3 companies. "
                "KoruFlux provides: entity setup, MAS/VARA regulatory mapping, team hiring support."
            )

    return f"{sector} presents a {data['tier']} with score {score}/100. Monitor and evaluate entry timing."


def _build_actions(sector: str, profile: str) -> list:
    actions = {
        ("web3_startup_kenya", "DeFi"): [
            "Engage CMA Kenya sandbox programme",
            "Map existing SACCO and MFI networks for distribution partnerships",
            "Audit competitor protocols (no EA-native DeFi leaders yet)",
            "Commission KoruFlux Jurisdiction Intelligence sprint"
        ],
        ("web3_startup_kenya", "Payments"): [
            "Identify cross-border stablecoin corridor (KES/UGX/TZS)",
            "Engage CBK FinTech liaison office",
            "Pilot with 3 Kenyan SMEs on B2B payment flows",
            "Legal: review VASP framework timeline"
        ],
        ("ai_fintech_ea", "AI_Fintech"): [
            "Source anonymised mobile money transaction datasets",
            "Pilot alternative credit scoring model with MFI partner",
            "Register data processor under Kenya Data Protection Act 2019",
            "Build local AI/ML team (Nairobi has 3rd-largest AI talent pool in Africa)"
        ],
        ("ai_fintech_ea", "Payments"): [
            "Secure API partnership with Safaricom Daraja",
            "Build AI fraud layer as white-label offering to PSPs",
            "Engage CBK on AI model risk disclosure requirements",
            "KoruFlux can facilitate Safaricom / Equity Bank introductions"
        ],
        ("intl_corp_africa_entry", "Payments"): [
            "Engage CBK Payment Service Provider licensing process",
            "Map SWIFT vs stablecoin cost comparison for target corridors",
            "Identify licensed Kenyan bank or EMI for partnership",
            "KoruFlux: East Africa regulatory compliance sprint (6 weeks)"
        ],
        ("intl_corp_africa_entry", "RWA"): [
            "Identify tokenisable asset class in target African market",
            "Engage CMA Kenya on digital securities framework",
            "Structure dual-compliance: MiCA/SEC + CMA",
            "KoruFlux: RWA market entry programme (12 weeks)"
        ],
        ("intl_corp_africa_entry", "AI_Fintech"): [
            "Source African financial dataset partnerships (telcos, MFIs)",
            "Register under Kenya Data Protection Act 2019",
            "Pilot AI credit model with 1 Kenyan MFI",
            "Scale to Nigeria in month 6 via KoruFlux partner network"
        ],
        ("intl_corp_africa_entry", "Regulatory"): [
            "Engage KoruFlux for multi-jurisdiction regulatory map",
            "Assess: Kenya CMA sandbox, Dubai VARA, Singapore MAS",
            "Structure: Singapore/UAE holding + Kenya operating entity",
            "Timeline: 3-4 months to operational licensing"
        ],
        ("web3_hub_expansion", "DeFi"): [
            "File MAS Payment Services Act licence application (Singapore)",
            "Engage VARA for UAE Virtual Asset Service Provider licence",
            "Structure ADGM SPV for MENA operations",
            "KoruFlux: Singapore + UAE dual-jurisdiction setup programme"
        ],
        ("web3_hub_expansion", "RWA"): [
            "Apply to MAS Project Guardian RWA framework",
            "Engage DIFC Innovation Testing Licence for RWA pilot",
            "Identify Africa-side asset origination partner (KoruFlux network)",
            "Timeline: 4-6 months to first tokenised asset on-chain"
        ],
        ("web3_hub_expansion", "Infrastructure"): [
            "Register Singapore entity (Pte Ltd) — 1 week via KoruFlux",
            "Apply for MAS FSTI grant (up to SGD 200K)",
            "Set up Dubai Crypto Oasis presence for MENA access",
            "KoruFlux: end-to-end hub expansion programme (8 weeks)"
        ],
    }
    key = (profile, sector)
    return actions.get(key, [
        f"Research {sector} landscape in target market",
        "Identify 3-5 potential local partners",
        "Assess regulatory requirements",
        "Develop pilot scope with KoruFlux advisory support"
    ])


# ══════════════════════════════════════════════════════════════
# 5. Main Analysis Runner
# ══════════════════════════════════════════════════════════════

def run_analysis(processed_records: list = None) -> dict:
    """
    Master analysis function.
    Returns a complete intelligence report dict.
    """
    cfg = load_config()

    if processed_records is None:
        processed_records = []
        for fpath in sorted(PROCESSED_DIR.glob("*.json")):
            try:
                with open(fpath) as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        processed_records.extend(data)
                    else:
                        processed_records.append(data)
            except Exception as e:
                logger.warning(f"Could not read {fpath.name}: {e}")

    logger.info(f" Analyzing {len(processed_records)} processed records...")

    # ── Aggregate sector mentions ──────────────────────────────
    sector_mentions = Counter()
    sector_texts = defaultdict(list)
    region_mentions = Counter()
    entity_mentions = Counter()

    for rec in processed_records:
        for sector in rec.get("sectors_detected", []):
            sector_mentions[sector] += 1
            sector_texts[sector].append(rec.get("text_sample", ""))
        for region in rec.get("regions_detected", []):
            region_mentions[region] += 1
        for ent in rec.get("entities", []):
            entity_mentions[ent] += 1

    # ── Sentiment per sector ───────────────────────────────────
    sector_sentiments = {}
    for sector, texts in sector_texts.items():
        combined = " ".join(texts)
        sector_sentiments[sector] = score_sentiment(combined, cfg)

    # ── Opportunity scores ─────────────────────────────────────
    all_sectors = set(list(MARKET_BASELINE.keys()) + list(sector_mentions.keys()))
    opportunity_scores = []
    for sector in all_sectors:
        sentiment = sector_sentiments.get(sector, {"score": 0})
        score = compute_opportunity_score(
            sector=sector,
            sentiment_score=sentiment["score"],
            mention_count=sector_mentions.get(sector, 0),
            cfg=cfg
        )
        score["sentiment"] = sentiment
        score["mention_count"] = sector_mentions.get(sector, 0)
        opportunity_scores.append(score)

    opportunity_scores.sort(key=lambda x: x["opportunity_score"], reverse=True)

    # ── Theme clusters ─────────────────────────────────────────
    themes = cluster_by_theme(opportunity_scores)

    # ── Client-specific recommendations ───────────────────────
    recs_web3_kenya  = generate_recommendations(opportunity_scores, "web3_startup_kenya")
    recs_ai_ea       = generate_recommendations(opportunity_scores, "ai_fintech_ea")
    recs_intl_corp   = generate_recommendations(opportunity_scores, "intl_corp_africa_entry")
    recs_hub_expan   = generate_recommendations(opportunity_scores, "web3_hub_expansion")

    # ── Assemble report ────────────────────────────────────────
    report = {
        "report_metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "system": "KoruFlux Intelligence Agent v2.0",
            "records_analyzed": len(processed_records),
            "sources_included": list({r.get("source") for r in processed_records}),
            "markets_covered": ["Kenya", "East Africa", "Nigeria", "United States",
                                  "European Union", "United Kingdom", "Singapore", "UAE"]
        },
        "market_summary": {
            "top_sectors_by_mention": sector_mentions.most_common(10),
            "top_regions_by_mention": region_mentions.most_common(15),
            "top_entities": entity_mentions.most_common(15),
            "data_freshness": processed_records[0].get("original_timestamp", "unknown") if processed_records else "no data"
        },
        "opportunity_leaderboard": opportunity_scores,
        "theme_clusters": themes,
        "client_insights": {
            "web3_startup_kenya": {
                "profile": CLIENT_PROFILES["web3_startup_kenya"]["label"],
                "markets": CLIENT_PROFILES["web3_startup_kenya"]["markets"],
                "recommendations": recs_web3_kenya
            },
            "ai_fintech_ea": {
                "profile": CLIENT_PROFILES["ai_fintech_ea"]["label"],
                "markets": CLIENT_PROFILES["ai_fintech_ea"]["markets"],
                "recommendations": recs_ai_ea
            },
            "intl_corp_africa_entry": {
                "profile": CLIENT_PROFILES["intl_corp_africa_entry"]["label"],
                "markets": CLIENT_PROFILES["intl_corp_africa_entry"]["markets"],
                "recommendations": recs_intl_corp
            },
            "web3_hub_expansion": {
                "profile": CLIENT_PROFILES["web3_hub_expansion"]["label"],
                "markets": CLIENT_PROFILES["web3_hub_expansion"]["markets"],
                "recommendations": recs_hub_expan
            }
        },
        "risk_flags": _identify_risks(processed_records, cfg),
        "strategic_watch_list": _build_watchlist(opportunity_scores, region_mentions)
    }

    # Save report
    outfile = REPORTS_DIR / f"intelligence_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(outfile, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f" Intelligence report saved → {outfile.name}")

    return report


def _identify_risks(records: list, cfg: dict) -> list:
    """Scan records for negative signals and flag as risks."""
    neg_keywords = cfg.get("analysis", {}).get("sentiment_keywords", {}).get("negative", [])
    risks = []
    seen = set()

    for rec in records:
        text = rec.get("text_sample", "").lower()
        for kw in neg_keywords:
            if kw in text and kw not in seen:
                seen.add(kw)
                risks.append({
                    "risk_keyword": kw,
                    "source": rec.get("source"),
                    "category": rec.get("category"),
                    "severity": "HIGH" if kw in ["ban", "hack", "fraud", "crackdown"] else "MEDIUM"
                })

    return sorted(risks, key=lambda x: x["severity"])[:10]


def _build_watchlist(scores: list, regions: Counter) -> list:
    """Top opportunities to monitor — not yet ready but high potential."""
    watchlist = [
        s for s in scores
        if 50 <= s["opportunity_score"] < 70
        and s["dimensions"].get("growth_rate", 0) >= 65
    ]
    return [
        {
            "sector": w["sector"],
            "score": w["opportunity_score"],
            "reason": f"High growth ({w['dimensions'].get('growth_rate')}/100) but maturing. Watch 6-12 months."
        }
        for w in watchlist[:5]
    ]


if __name__ == "__main__":
    report = run_analysis()
    print(f"\n Analysis complete. Top opportunities:")
    for opp in report["opportunity_leaderboard"][:5]:
        print(f"  {opp['tier']}  {opp['sector']:20s} Score: {opp['opportunity_score']}")
