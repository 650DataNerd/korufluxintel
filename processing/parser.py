"""
KoruFlux Intelligence System
==============================
processing/parser.py

Takes raw JSON records from data/raw/ and:
  1. Validates & normalises schema
  2. Deduplicates
  3. Enriches with basic metadata (sector tags, region tags)
  4. Outputs to data/processed/

Run standalone:  python processing/parser.py
Or import:       from processing.parser import process_all
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("koruflux.parser")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# ── Taxonomy maps ──────────────────────────────────────────────
SECTOR_KEYWORDS = {
    "DeFi": ["defi", "decentralized finance", "dex", "amm", "liquidity", "yield",
              "lending", "borrowing", "staking", "tvl"],
    "NFT": ["nft", "non-fungible", "digital collectible", "tokenized art"],
    "DAO": ["dao", "governance", "on-chain voting", "decentralized autonomous"],
    "Payments": ["payment", "remittance", "cross-border", "money transfer",
                 "m-pesa", "mobile money", "stablecoin", "cbdc"],
    "AI_Fintech": ["ai", "machine learning", "artificial intelligence", "llm",
                   "credit scoring", "fraud detection", "robo-advisor"],
    "RWA": ["real world asset", "rwa", "tokenized", "real estate", "commodities"],
    "Infrastructure": ["layer 1", "layer 2", "l2", "rollup", "validator",
                       "node", "oracle", "bridge", "interoperability"],
    "AgriTech": ["agriculture", "agritech", "farming", "crop", "food supply"],
    "HealthTech": ["health", "medtech", "telemedicine", "hospital"],
    "Regulatory": ["regulation", "compliance", "license", "sec", "cma", "cbk",
                   "finra", "mifid", "kyc", "aml"]
}

REGION_KEYWORDS = {
    # Africa
    "Kenya": ["kenya", "nairobi", "mombasa", "kisumu", "m-pesa", "safaricom", "cbk"],
    "Nigeria": ["nigeria", "lagos", "abuja", "kano"],
    "East Africa": ["east africa", "kenya", "tanzania", "uganda", "rwanda",
                    "ethiopia", "burundi", "south sudan"],
    "West Africa": ["west africa", "nigeria", "ghana", "senegal", "ivory coast"],
    "South Africa": ["south africa", "johannesburg", "cape town"],
    "Pan-Africa": ["africa", "african", "sub-saharan"],
    # Global expansion markets
    "United States": ["united states", "us market", "usa", "sec", "cftc", "new york",
                       "silicon valley", "san francisco", "wall street"],
    "European Union": ["european union", "eu", "europe", "brussels", "frankfurt",
                        "paris", "amsterdam", "mica", "esma", "ecb"],
    "United Kingdom": ["united kingdom", "uk", "london", "fca", "britain"],
    "Singapore": ["singapore", "mas", "monetary authority", "fintech festival"],
    "UAE": ["uae", "dubai", "abu dhabi", "difc", "vara", "adgm",
              "emirates", "middle east"],
    "Asia": ["asia", "hong kong", "japan", "korea", "china", "india"],
    "Global": ["global", "worldwide", "international", "cross-border"]
}


# ══════════════════════════════════════════════════════════════
# Core Parser Logic
# ══════════════════════════════════════════════════════════════

def _tag_sectors(text: str) -> list:
    text_l = text.lower()
    return [sector for sector, keywords in SECTOR_KEYWORDS.items()
            if any(kw in text_l for kw in keywords)]


def _tag_regions(text: str) -> list:
    text_l = text.lower()
    return [region for region, keywords in REGION_KEYWORDS.items()
            if any(kw in text_l for kw in keywords)]


def _normalise_text(text: str) -> str:
    """Strip HTML, collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_numbers(text: str) -> list:
    """Pull dollar amounts and percentages from text."""
    amounts = re.findall(r"\$[\d,.]+[BMK]?", text)
    percents = re.findall(r"\d+\.?\d*\s*%", text)
    return amounts + percents


def parse_record(raw: dict) -> Optional[dict]:
    """
    Validate and enrich a single raw record.
    Returns None if the record fails validation.
    """
    required = ["source", "timestamp", "category", "clean_data"]
    for field in required:
        if field not in raw:
            logger.warning(f"  ⚠️  Missing field '{field}' — skipping record")
            return None

    # Build combined text for NLP-style tagging
    clean = raw.get("clean_data", {})
    combined_text = json.dumps(clean)

    # Pull text snippets from known clean_data shapes
    article_titles = []
    if "articles" in clean:
        article_titles = [a.get("title", "") for a in clean.get("articles", [])]
    if "repos" in clean:
        article_titles += [r.get("description", "") or "" for r in clean.get("repos", [])]
    if "trending_coins" in clean:
        article_titles += [c.get("name", "") for c in clean.get("trending_coins", [])]

    full_text = combined_text + " " + " ".join(article_titles)

    sectors = _tag_sectors(full_text)
    regions = _tag_regions(full_text)
    numbers = _extract_numbers(full_text)

    processed = {
        "record_id": raw.get("record_hash", "unknown"),
        "source": raw["source"],
        "url": raw.get("url", ""),
        "original_timestamp": raw["timestamp"],
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "category": raw["category"],
        "entities": list(set(raw.get("entities", []))),
        "sectors_detected": sectors,
        "regions_detected": regions,
        "financial_figures": numbers[:10],
        "article_count": len(article_titles),
        "clean_data": clean,
        "text_sample": _normalise_text(full_text)[:600]
    }
    return processed


def deduplicate(records: list) -> list:
    """Remove records with identical source+date combos."""
    seen = set()
    unique = []
    for r in records:
        key = f"{r['source']}_{r['original_timestamp'][:10]}"
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def process_all(raw_records: list = None) -> list:
    """
    Main entry point.
    If raw_records is provided, processes those directly.
    Otherwise, reads all JSON files from data/raw/.
    """
    if raw_records is None:
        raw_records = []
        for fpath in sorted(RAW_DIR.glob("*.json")):
            try:
                with open(fpath) as f:
                    raw_records.append(json.load(f))
            except Exception as e:
                logger.warning(f"  ⚠️  Could not read {fpath.name}: {e}")

    logger.info(f"🔧 Parsing {len(raw_records)} raw records...")

    processed = []
    for raw in raw_records:
        result = parse_record(raw)
        if result:
            processed.append(result)

    processed = deduplicate(processed)
    logger.info(f"  ✅ {len(processed)} unique records after deduplication")

    # Save consolidated processed file
    outfile = PROCESSED_DIR / f"processed_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(outfile, "w") as f:
        json.dump(processed, f, indent=2)
    logger.info(f"  💾 Saved → {outfile.name}")

    return processed


if __name__ == "__main__":
    process_all()
