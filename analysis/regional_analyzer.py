"""
KoruFlux Intelligence System
==============================
analysis/regional_analyzer.py

Runs independent analysis for each of the 8 markets.
Each region gets its own:
  - Sector scores (calibrated to that market's context)
  - Sentiment analysis from regional sources
  - Opportunity rankings
  - Risk flags
  - Entity frequency map
  - Social signal summary (Farcaster/Twitter if available)

Output: data/regional/{code}/processed/regional_report_{code}.json
"""

import json
import logging
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger("koruflux.regional_analyzer")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

DATA_DIR    = Path("data/regional")
CONFIG_PATH = Path("config/config.yaml")


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


# ══════════════════════════════════════════════════════════════
# Region-specific market baselines
# Each value is 0-100, calibrated to that specific market
# Sources: IMF, World Bank, BIS, regional CB reports, CoinGecko
# ══════════════════════════════════════════════════════════════

REGIONAL_BASELINES = {

    "KE": {  # Kenya / Nairobi
        "meta": {
            "gdp_usd_bn": 118,
            "mobile_penetration_pct": 63,
            "internet_penetration_pct": 42,
            "unbanked_pct": 27,
            "key_stat": "M-Pesa processes $314B annually",
            "risk_level": "MODERATE",
            "regulatory_stance": "Cautiously progressive"
        },
        "sectors": {
            "Payments":       {"market_size":90,"growth_rate":75,"regulatory_clarity":70,"ecosystem_maturity":80,"competitive_gap":40,"tech_readiness":85},
            "DeFi":           {"market_size":65,"growth_rate":85,"regulatory_clarity":45,"ecosystem_maturity":55,"competitive_gap":75,"tech_readiness":65},
            "AI_Fintech":     {"market_size":80,"growth_rate":90,"regulatory_clarity":55,"ecosystem_maturity":50,"competitive_gap":80,"tech_readiness":60},
            "RWA":            {"market_size":70,"growth_rate":75,"regulatory_clarity":40,"ecosystem_maturity":40,"competitive_gap":85,"tech_readiness":55},
            "Infrastructure": {"market_size":60,"growth_rate":70,"regulatory_clarity":50,"ecosystem_maturity":50,"competitive_gap":65,"tech_readiness":55},
            "NFT":            {"market_size":35,"growth_rate":50,"regulatory_clarity":30,"ecosystem_maturity":30,"competitive_gap":85,"tech_readiness":45},
            "DAO":            {"market_size":30,"growth_rate":60,"regulatory_clarity":20,"ecosystem_maturity":25,"competitive_gap":90,"tech_readiness":40},
            "AgriTech":       {"market_size":70,"growth_rate":65,"regulatory_clarity":60,"ecosystem_maturity":55,"competitive_gap":70,"tech_readiness":50},
            "Regulatory":     {"market_size":55,"growth_rate":60,"regulatory_clarity":65,"ecosystem_maturity":60,"competitive_gap":55,"tech_readiness":60},
        }
    },

    "EA": {  # East Africa
        "meta": {
            "gdp_usd_bn": 340,
            "mobile_penetration_pct": 55,
            "internet_penetration_pct": 35,
            "unbanked_pct": 60,
            "key_stat": "350M+ population, fastest growing mobile money region",
            "risk_level": "MODERATE-HIGH",
            "regulatory_stance": "Fragmented — varies by country"
        },
        "sectors": {
            "Payments":       {"market_size":85,"growth_rate":80,"regulatory_clarity":55,"ecosystem_maturity":70,"competitive_gap":50,"tech_readiness":70},
            "DeFi":           {"market_size":55,"growth_rate":80,"regulatory_clarity":35,"ecosystem_maturity":40,"competitive_gap":80,"tech_readiness":55},
            "AI_Fintech":     {"market_size":75,"growth_rate":85,"regulatory_clarity":45,"ecosystem_maturity":40,"competitive_gap":85,"tech_readiness":55},
            "RWA":            {"market_size":65,"growth_rate":70,"regulatory_clarity":30,"ecosystem_maturity":30,"competitive_gap":88,"tech_readiness":45},
            "Infrastructure": {"market_size":55,"growth_rate":65,"regulatory_clarity":40,"ecosystem_maturity":40,"competitive_gap":70,"tech_readiness":45},
            "NFT":            {"market_size":30,"growth_rate":45,"regulatory_clarity":25,"ecosystem_maturity":25,"competitive_gap":85,"tech_readiness":40},
            "DAO":            {"market_size":25,"growth_rate":55,"regulatory_clarity":15,"ecosystem_maturity":20,"competitive_gap":90,"tech_readiness":35},
            "AgriTech":       {"market_size":80,"growth_rate":70,"regulatory_clarity":55,"ecosystem_maturity":50,"competitive_gap":75,"tech_readiness":50},
            "Regulatory":     {"market_size":45,"growth_rate":55,"regulatory_clarity":50,"ecosystem_maturity":45,"competitive_gap":60,"tech_readiness":50},
        }
    },

    "NG": {  # Nigeria
        "meta": {
            "gdp_usd_bn": 477,
            "mobile_penetration_pct": 72,
            "internet_penetration_pct": 55,
            "unbanked_pct": 38,
            "key_stat": "Largest crypto market by volume in Africa, 6th globally",
            "risk_level": "HIGH",
            "regulatory_stance": "Volatile — CBN historically restrictive, SEC progressive"
        },
        "sectors": {
            "Payments":       {"market_size":88,"growth_rate":70,"regulatory_clarity":45,"ecosystem_maturity":75,"competitive_gap":45,"tech_readiness":75},
            "DeFi":           {"market_size":80,"growth_rate":90,"regulatory_clarity":35,"ecosystem_maturity":65,"competitive_gap":55,"tech_readiness":70},
            "AI_Fintech":     {"market_size":82,"growth_rate":88,"regulatory_clarity":40,"ecosystem_maturity":55,"competitive_gap":70,"tech_readiness":65},
            "RWA":            {"market_size":72,"growth_rate":72,"regulatory_clarity":30,"ecosystem_maturity":38,"competitive_gap":80,"tech_readiness":55},
            "Infrastructure": {"market_size":65,"growth_rate":75,"regulatory_clarity":35,"ecosystem_maturity":55,"competitive_gap":65,"tech_readiness":60},
            "NFT":            {"market_size":55,"growth_rate":60,"regulatory_clarity":25,"ecosystem_maturity":50,"competitive_gap":70,"tech_readiness":60},
            "DAO":            {"market_size":40,"growth_rate":65,"regulatory_clarity":20,"ecosystem_maturity":40,"competitive_gap":80,"tech_readiness":55},
            "AgriTech":       {"market_size":75,"growth_rate":65,"regulatory_clarity":50,"ecosystem_maturity":50,"competitive_gap":72,"tech_readiness":55},
            "Regulatory":     {"market_size":55,"growth_rate":50,"regulatory_clarity":40,"ecosystem_maturity":50,"competitive_gap":55,"tech_readiness":55},
        }
    },

    "US": {  # United States
        "meta": {
            "gdp_usd_bn": 27360,
            "mobile_penetration_pct": 97,
            "internet_penetration_pct": 92,
            "unbanked_pct": 5,
            "key_stat": "Largest Web3 capital market, 40%+ of global crypto VC",
            "risk_level": "LOW-MODERATE",
            "regulatory_stance": "Increasingly clear post-2024 elections"
        },
        "sectors": {
            "Payments":       {"market_size":95,"growth_rate":60,"regulatory_clarity":70,"ecosystem_maturity":95,"competitive_gap":20,"tech_readiness":98},
            "DeFi":           {"market_size":95,"growth_rate":75,"regulatory_clarity":65,"ecosystem_maturity":88,"competitive_gap":30,"tech_readiness":95},
            "AI_Fintech":     {"market_size":98,"growth_rate":95,"regulatory_clarity":70,"ecosystem_maturity":92,"competitive_gap":25,"tech_readiness":98},
            "RWA":            {"market_size":95,"growth_rate":90,"regulatory_clarity":72,"ecosystem_maturity":80,"competitive_gap":45,"tech_readiness":95},
            "Infrastructure": {"market_size":95,"growth_rate":80,"regulatory_clarity":68,"ecosystem_maturity":92,"competitive_gap":35,"tech_readiness":98},
            "NFT":            {"market_size":80,"growth_rate":55,"regulatory_clarity":60,"ecosystem_maturity":85,"competitive_gap":40,"tech_readiness":90},
            "DAO":            {"market_size":75,"growth_rate":65,"regulatory_clarity":50,"ecosystem_maturity":78,"competitive_gap":45,"tech_readiness":88},
            "AgriTech":       {"market_size":85,"growth_rate":65,"regulatory_clarity":75,"ecosystem_maturity":88,"competitive_gap":40,"tech_readiness":90},
            "Regulatory":     {"market_size":90,"growth_rate":70,"regulatory_clarity":78,"ecosystem_maturity":90,"competitive_gap":35,"tech_readiness":90},
        }
    },

    "EU": {  # European Union
        "meta": {
            "gdp_usd_bn": 18350,
            "mobile_penetration_pct": 95,
            "internet_penetration_pct": 90,
            "unbanked_pct": 7,
            "key_stat": "MiCA — world's first comprehensive crypto regulatory framework",
            "risk_level": "LOW",
            "regulatory_stance": "MiCA framework fully live — most clarity globally"
        },
        "sectors": {
            "Payments":       {"market_size":92,"growth_rate":65,"regulatory_clarity":88,"ecosystem_maturity":90,"competitive_gap":25,"tech_readiness":95},
            "DeFi":           {"market_size":88,"growth_rate":70,"regulatory_clarity":80,"ecosystem_maturity":80,"competitive_gap":35,"tech_readiness":90},
            "AI_Fintech":     {"market_size":90,"growth_rate":85,"regulatory_clarity":75,"ecosystem_maturity":85,"competitive_gap":30,"tech_readiness":90},
            "RWA":            {"market_size":90,"growth_rate":85,"regulatory_clarity":82,"ecosystem_maturity":78,"competitive_gap":40,"tech_readiness":88},
            "Infrastructure": {"market_size":88,"growth_rate":75,"regulatory_clarity":78,"ecosystem_maturity":85,"competitive_gap":38,"tech_readiness":90},
            "NFT":            {"market_size":75,"growth_rate":50,"regulatory_clarity":72,"ecosystem_maturity":78,"competitive_gap":42,"tech_readiness":85},
            "DAO":            {"market_size":72,"growth_rate":60,"regulatory_clarity":65,"ecosystem_maturity":72,"competitive_gap":48,"tech_readiness":82},
            "AgriTech":       {"market_size":85,"growth_rate":60,"regulatory_clarity":80,"ecosystem_maturity":85,"competitive_gap":38,"tech_readiness":88},
            "Regulatory":     {"market_size":88,"growth_rate":72,"regulatory_clarity":90,"ecosystem_maturity":88,"competitive_gap":30,"tech_readiness":88},
        }
    },

    "GB": {  # United Kingdom
        "meta": {
            "gdp_usd_bn": 3070,
            "mobile_penetration_pct": 96,
            "internet_penetration_pct": 96,
            "unbanked_pct": 3,
            "key_stat": "London — Europe's largest fintech hub, 10%+ global fintech investment",
            "risk_level": "LOW",
            "regulatory_stance": "Progressive post-Brexit framework, FCA crypto regime live"
        },
        "sectors": {
            "Payments":       {"market_size":90,"growth_rate":68,"regulatory_clarity":82,"ecosystem_maturity":92,"competitive_gap":22,"tech_readiness":95},
            "DeFi":           {"market_size":85,"growth_rate":72,"regulatory_clarity":75,"ecosystem_maturity":82,"competitive_gap":32,"tech_readiness":88},
            "AI_Fintech":     {"market_size":90,"growth_rate":88,"regulatory_clarity":78,"ecosystem_maturity":88,"competitive_gap":28,"tech_readiness":92},
            "RWA":            {"market_size":88,"growth_rate":82,"regulatory_clarity":78,"ecosystem_maturity":78,"competitive_gap":40,"tech_readiness":88},
            "Infrastructure": {"market_size":85,"growth_rate":75,"regulatory_clarity":75,"ecosystem_maturity":85,"competitive_gap":35,"tech_readiness":90},
            "NFT":            {"market_size":75,"growth_rate":52,"regulatory_clarity":68,"ecosystem_maturity":80,"competitive_gap":40,"tech_readiness":85},
            "DAO":            {"market_size":70,"growth_rate":60,"regulatory_clarity":62,"ecosystem_maturity":72,"competitive_gap":48,"tech_readiness":80},
            "AgriTech":       {"market_size":78,"growth_rate":58,"regulatory_clarity":78,"ecosystem_maturity":82,"competitive_gap":42,"tech_readiness":85},
            "Regulatory":     {"market_size":85,"growth_rate":70,"regulatory_clarity":85,"ecosystem_maturity":88,"competitive_gap":30,"tech_readiness":88},
        }
    },

    "SG": {  # Singapore
        "meta": {
            "gdp_usd_bn": 497,
            "mobile_penetration_pct": 99,
            "internet_penetration_pct": 99,
            "unbanked_pct": 2,
            "key_stat": "MAS Project Guardian — $10B+ institutional RWA tokenisation",
            "risk_level": "LOW",
            "regulatory_stance": "Most progressive Web3 jurisdiction in Asia"
        },
        "sectors": {
            "Payments":       {"market_size":85,"growth_rate":75,"regulatory_clarity":90,"ecosystem_maturity":90,"competitive_gap":30,"tech_readiness":98},
            "DeFi":           {"market_size":80,"growth_rate":82,"regulatory_clarity":88,"ecosystem_maturity":82,"competitive_gap":38,"tech_readiness":95},
            "AI_Fintech":     {"market_size":85,"growth_rate":92,"regulatory_clarity":85,"ecosystem_maturity":85,"competitive_gap":32,"tech_readiness":98},
            "RWA":            {"market_size":85,"growth_rate":92,"regulatory_clarity":90,"ecosystem_maturity":80,"competitive_gap":42,"tech_readiness":95},
            "Infrastructure": {"market_size":82,"growth_rate":82,"regulatory_clarity":88,"ecosystem_maturity":85,"competitive_gap":38,"tech_readiness":95},
            "NFT":            {"market_size":72,"growth_rate":58,"regulatory_clarity":80,"ecosystem_maturity":78,"competitive_gap":45,"tech_readiness":90},
            "DAO":            {"market_size":70,"growth_rate":68,"regulatory_clarity":75,"ecosystem_maturity":75,"competitive_gap":48,"tech_readiness":88},
            "AgriTech":       {"market_size":60,"growth_rate":62,"regulatory_clarity":82,"ecosystem_maturity":78,"competitive_gap":50,"tech_readiness":88},
            "Regulatory":     {"market_size":80,"growth_rate":78,"regulatory_clarity":92,"ecosystem_maturity":88,"competitive_gap":35,"tech_readiness":92},
        }
    },

    "AE": {  # UAE / Dubai
        "meta": {
            "gdp_usd_bn": 509,
            "mobile_penetration_pct": 99,
            "internet_penetration_pct": 99,
            "unbanked_pct": 10,
            "key_stat": "VARA issued 2024 comprehensive DeFi regs. Crypto Oasis: 1,500+ Web3 companies",
            "risk_level": "LOW-MODERATE",
            "regulatory_stance": "Aggressive Web3 adoption — VARA, DIFC, ADGM competing for deals"
        },
        "sectors": {
            "Payments":       {"market_size":88,"growth_rate":78,"regulatory_clarity":85,"ecosystem_maturity":85,"competitive_gap":32,"tech_readiness":95},
            "DeFi":           {"market_size":82,"growth_rate":85,"regulatory_clarity":85,"ecosystem_maturity":80,"competitive_gap":40,"tech_readiness":90},
            "AI_Fintech":     {"market_size":85,"growth_rate":90,"regulatory_clarity":80,"ecosystem_maturity":82,"competitive_gap":38,"tech_readiness":90},
            "RWA":            {"market_size":88,"growth_rate":92,"regulatory_clarity":88,"ecosystem_maturity":80,"competitive_gap":42,"tech_readiness":90},
            "Infrastructure": {"market_size":82,"growth_rate":85,"regulatory_clarity":85,"ecosystem_maturity":82,"competitive_gap":40,"tech_readiness":90},
            "NFT":            {"market_size":75,"growth_rate":68,"regulatory_clarity":78,"ecosystem_maturity":78,"competitive_gap":45,"tech_readiness":88},
            "DAO":            {"market_size":72,"growth_rate":72,"regulatory_clarity":72,"ecosystem_maturity":72,"competitive_gap":50,"tech_readiness":82},
            "AgriTech":       {"market_size":55,"growth_rate":65,"regulatory_clarity":70,"ecosystem_maturity":65,"competitive_gap":60,"tech_readiness":80},
            "Regulatory":     {"market_size":82,"growth_rate":80,"regulatory_clarity":88,"ecosystem_maturity":82,"competitive_gap":38,"tech_readiness":85},
        }
    }
}


# ══════════════════════════════════════════════════════════════
# Scoring
# ══════════════════════════════════════════════════════════════

WEIGHTS = {
    "market_size": 0.25, "growth_rate": 0.20,
    "regulatory_clarity": 0.20, "ecosystem_maturity": 0.15,
    "competitive_gap": 0.10, "tech_readiness": 0.10
}

SENTIMENT_KEYWORDS = {
    "positive": ["launch","funding","partnership","growth","adoption","approved",
                 "investment","expansion","milestone","record","breakthrough",
                 "license","raises","secures","integrates","grants","pilot"],
    "negative": ["ban","crackdown","fraud","hack","exploit","lawsuit","shutdown",
                 "suspended","scam","breach","collapse","warning","probe","restrict"]
}


def score_sentiment(text: str) -> dict:
    text_l = text.lower()
    pos = sum(1 for w in SENTIMENT_KEYWORDS["positive"] if w in text_l)
    neg = sum(1 for w in SENTIMENT_KEYWORDS["negative"] if w in text_l)
    total = pos + neg or 1
    score = max(-1.0, min(1.0, (pos - neg) / total))
    label = "positive" if score > 0.15 else "negative" if score < -0.15 else "neutral"
    momentum = "Rising" if score > 0.15 else "Declining" if score < -0.15 else "Stable"
    return {"score": round(score, 3), "label": label, "momentum": momentum,
            "positive_signals": pos, "negative_signals": neg}


def compute_sector_score(region_code: str, sector: str,
                          sentiment_score: float, mention_count: int) -> dict:
    baseline = REGIONAL_BASELINES.get(region_code, {}).get("sectors", {}).get(sector, {
        k: 50 for k in WEIGHTS
    })
    base = sum(baseline.get(dim, 50) * w for dim, w in WEIGHTS.items())
    sentiment_adj = sentiment_score * 15
    mention_boost = min(10, math.log1p(mention_count) * 2.5)
    final = max(0, min(100, round(base + sentiment_adj + mention_boost, 1)))

    if final >= 75:   tier = "HIGH OPPORTUNITY"
    elif final >= 55: tier = "MODERATE OPPORTUNITY"
    elif final >= 35: tier = "EMERGING"
    else:             tier = "HIGH RISK"

    return {
        "sector": sector, "region": region_code,
        "opportunity_score": final, "tier": tier,
        "base_score": round(base, 1),
        "sentiment_adjustment": round(sentiment_adj, 1),
        "mention_boost": round(mention_boost, 1),
        "dimensions": baseline,
        "mention_count": mention_count
    }


# ══════════════════════════════════════════════════════════════
# Per-Region Analysis
# ══════════════════════════════════════════════════════════════

def analyze_region(region_code: str, records: list = None) -> dict:
    """
    Full analysis for a single region.
    Returns a region intelligence report.
    """
    if records is None:
        from ingestion.regional_scraper import load_regional_records
        records = load_regional_records(region_code)

    baseline_meta = REGIONAL_BASELINES.get(region_code, {}).get("meta", {})
    sectors = list(REGIONAL_BASELINES.get(region_code, {}).get("sectors", {}).keys())

    logger.info(f"Analyzing {region_code} — {len(records)} records, {len(sectors)} sectors")

    # Aggregate from records
    sector_mentions  = Counter()
    sector_texts     = defaultdict(list)
    entity_mentions  = Counter()
    social_signals   = []
    news_articles    = []
    regulatory_items = []

    for rec in records:
        cd  = rec.get("clean_data", {})
        cat = rec.get("category", "")

        # Collect text for sentiment
        text_blob = json.dumps(cd)
        for sector in sectors:
            if sector.lower().replace("_", " ") in text_blob.lower() or \
               any(kw in text_blob.lower() for kw in _sector_keywords(sector)):
                sector_mentions[sector] += 1
                sector_texts[sector].append(text_blob[:800])

        # Entity counts
        for ent in rec.get("entities", []):
            entity_mentions[ent] += 1

        # Social signals
        if cat in ("social_web3", "social_sentiment"):
            if "casts" in cd:
                social_signals.extend(cd["casts"][:5])
            if "tweets" in cd:
                social_signals.extend(cd["tweets"][:5])

        # News articles
        if "articles" in cd:
            for a in cd["articles"][:3]:
                a["source"] = rec.get("source", "")
                a["source_url"] = cd.get("feed_url") or rec.get("url", "")
                news_articles.append(a)

        # Regulatory
        if cat == "regulatory" and "articles" in cd:
            for a in cd["articles"][:3]:
                a["source"] = rec.get("source", "")
                regulatory_items.append(a)

    # Score each sector
    scores = []
    for sector in sectors:
        texts = sector_texts.get(sector, [])
        combined_text = " ".join(texts)
        sentiment = score_sentiment(combined_text)
        score = compute_sector_score(
            region_code, sector,
            sentiment["score"], sector_mentions.get(sector, 0)
        )
        score["sentiment"] = sentiment
        scores.append(score)

    scores.sort(key=lambda x: x["opportunity_score"], reverse=True)

    # Risk flags
    risks = _detect_risks(records, region_code)

    # Crypto market data (if available)
    market_data = _extract_market_data(records)

    # Social summary
    social_summary = _summarise_social(social_signals)

    report = {
        "region_code":   region_code,
        "region_name":   REGIONAL_BASELINES.get(region_code, {}).get("meta", {}).get("key_stat", region_code),
        "generated_at":  datetime.now(timezone.utc).isoformat(),
        "records_used":  len(records),
        "region_meta":   baseline_meta,
        "opportunity_leaderboard": scores,
        "top_entities":  entity_mentions.most_common(15),
        "news_articles": news_articles[:15],
        "regulatory_updates": regulatory_items[:8],
        "social_signals": social_summary,
        "market_data":   market_data,
        "risk_flags":    risks,
        "watch_list":    [s for s in scores if 45 <= s["opportunity_score"] < 65][:4]
    }

    # Save
    out_dir = DATA_DIR / region_code / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = out_dir / f"regional_report_{region_code}_{ts}.json"
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"  Report saved: {out.name}")

    return report


def analyze_all_regions(records_map: dict = None) -> dict:
    """Analyze all 8 regions. Returns dict of region_code -> report."""
    reports = {}
    for code in REGIONAL_BASELINES:
        recs = records_map.get(code, []) if records_map else None
        try:
            reports[code] = analyze_region(code, recs)
        except Exception as e:
            logger.error(f"Failed to analyze {code}: {e}")
    return reports


def load_latest_regional_report(region_code: str) -> Optional[dict]:
    proc_dir = DATA_DIR / region_code / "processed"
    if not proc_dir.exists():
        return None
    files = sorted(proc_dir.glob(f"regional_report_{region_code}_*.json"), reverse=True)
    if not files:
        return None
    with open(files[0]) as f:
        return json.load(f)


# ── Helpers ────────────────────────────────────────────────────

def _sector_keywords(sector: str) -> list:
    MAP = {
        "Payments":       ["payment","remittance","mpesa","mobile money","stablecoin"],
        "DeFi":           ["defi","decentralized finance","dex","yield","liquidity"],
        "AI_Fintech":     ["artificial intelligence","machine learning","ai fintech","credit scoring"],
        "RWA":            ["real world asset","rwa","tokenized","real estate"],
        "Infrastructure": ["infrastructure","layer 2","oracle","bridge","validator"],
        "NFT":            ["nft","non-fungible","digital collectible"],
        "DAO":            ["dao","governance","on-chain voting"],
        "AgriTech":       ["agriculture","agritech","farming","crop"],
        "Regulatory":     ["regulation","compliance","license","framework","sandbox"]
    }
    return MAP.get(sector, [sector.lower()])


def _detect_risks(records: list, region_code: str) -> list:
    NEG = SENTIMENT_KEYWORDS["negative"]
    seen, risks = set(), []
    for rec in records:
        text = (json.dumps(rec.get("clean_data", {})) + " " + rec.get("raw_data", ""))[:2000].lower()
        for kw in NEG:
            if kw in text and kw not in seen:
                seen.add(kw)
                risks.append({
                    "risk_keyword": kw,
                    "source": rec.get("source", ""),
                    "source_url": rec.get("url", ""),
                    "region": region_code,
                    "severity": "HIGH" if kw in ["ban","hack","fraud","crackdown","exploit"] else "MEDIUM"
                })
    return sorted(risks, key=lambda x: x["severity"])[:8]


def _extract_market_data(records: list) -> dict:
    """Pull structured market data from API records."""
    market = {}
    for rec in records:
        sid = rec.get("source", "")
        cd  = rec.get("clean_data", {})
        if "total_market_cap_usd" in cd:
            market["global_market_cap_usd"] = cd["total_market_cap_usd"]
            market["btc_dominance_pct"]     = cd.get("btc_dominance")
            market["market_cap_change_24h"] = cd.get("market_cap_change_24h")
        if "top_protocols" in cd:
            market["top_defi_protocols"] = cd["top_protocols"][:5]
        if "coins" in cd and isinstance(cd["coins"], list):
            market["top_coins"] = cd["coins"][:5]
        if "trending" in cd:
            market["trending_coins"] = cd["trending"][:5]
        if "repos" in cd:
            market["dev_activity_repos"] = cd["repos"][:5]
    return market


def _summarise_social(signals: list) -> dict:
    if not signals:
        return {"available": False, "platforms": [], "total_posts": 0}

    platforms = set()
    total_engagement = 0
    top_posts = []

    for s in signals[:10]:
        if "cast_hash" in s:
            platforms.add("Farcaster")
        elif "verify_url" in s and "twitter" in s.get("verify_url", ""):
            platforms.add("Twitter/X")
        engagement = s.get("likes", 0) + s.get("recasts", s.get("retweets", 0))
        total_engagement += engagement
        top_posts.append({
            "text":       s.get("text", "")[:200],
            "author":     s.get("author", ""),
            "engagement": engagement,
            "platform":   "Farcaster" if "cast_hash" in s else "Twitter/X",
            "verify_url": s.get("verify_url")
        })

    top_posts.sort(key=lambda x: x["engagement"], reverse=True)

    return {
        "available":        True,
        "platforms":        list(platforms),
        "total_posts":      len(signals),
        "total_engagement": total_engagement,
        "top_posts":        top_posts[:5]
    }


if __name__ == "__main__":
    import sys
    code = sys.argv[1].upper() if len(sys.argv) > 1 else "KE"
    report = analyze_region(code)
    print(f"\nRegion: {report['region_code']}")
    print(f"Top sectors:")
    for s in report["opportunity_leaderboard"][:5]:
        print(f"  {s['opportunity_score']:5.1f}  {s['sector']:<20}  {s['tier']}")
