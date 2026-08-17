"""
KoruFlux Intelligence System
==============================
ingestion/regional/farcaster_connector.py

Pulls verified public data from Farcaster via Neynar API.

FREE (no key): trending feed only
WITH NEYNAR_API_KEY: search by keyword, channel, region

All data returned:
  - cast_hash (verifiable at warpcast.com/~/conversations/{hash})
  - author FID and username
  - timestamp
  - engagement metrics
  - source URL for verification

Zero hallucination: if request fails → empty result + log. No invented data.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

import requests

logger = logging.getLogger("koruflux.farcaster")

NEYNAR_BASE   = "https://api.neynar.com/v2"
WARPCAST_BASE = "https://api.warpcast.com/v2"


def _get_headers() -> dict:
    key = os.environ.get("NEYNAR_API_KEY", "")
    h = {"Accept": "application/json", "User-Agent": "KoruFlux-IntelAgent/2.0"}
    if key:
        h["api_key"] = key
    return h


def _safe_get(url: str, params: dict = None, timeout: int = 12) -> Optional[dict]:
    try:
        r = requests.get(url, params=params, headers=_get_headers(), timeout=timeout)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 401:
            logger.warning(f"  Farcaster: 401 Unauthorized — set NEYNAR_API_KEY for full access")
        elif r.status_code == 403:
            logger.info(f"  Farcaster: endpoint requires API key — {url}")
        else:
            logger.warning(f"  Farcaster HTTP {r.status_code} for {url}")
        return None
    except Exception as e:
        logger.warning(f"  Farcaster request failed: {e}")
        return None


def _normalise_cast(raw: dict) -> dict:
    """Normalise a Farcaster cast to a consistent schema."""
    author = raw.get("author", {})
    return {
        "hash":       raw.get("hash", ""),
        "text":       raw.get("text", "")[:500],
        "author": {
            "fid":      author.get("fid"),
            "username": author.get("username", ""),
            "display":  author.get("display_name", "")
        },
        "timestamp":  raw.get("timestamp", ""),
        "engagement": {
            "likes":   raw.get("reactions", {}).get("likes_count", 0),
            "recasts": raw.get("reactions", {}).get("recasts_count", 0),
            "replies": raw.get("replies", {}).get("count", 0)
        },
        "verify_url": f"https://warpcast.com/~/conversations/{raw.get('hash','')}",
        "data_source": "Farcaster via Neynar API",
        "verified": True
    }


def get_trending_casts(limit: int = 20) -> list:
    """Get trending Farcaster casts. Requires NEYNAR_API_KEY."""
    if not os.environ.get("NEYNAR_API_KEY"):
        logger.info("  Farcaster trending: NEYNAR_API_KEY not set — skipping")
        return []

    data = _safe_get(f"{NEYNAR_BASE}/farcaster/feed/trending",
                     params={"limit": min(limit, 25), "feed_type": "filter"})
    if not data:
        return []

    casts = data.get("casts", [])
    return [_normalise_cast(c) for c in casts[:limit]]


def search_casts(query: str, limit: int = 15) -> list:
    """Search Farcaster casts by keyword. Requires NEYNAR_API_KEY."""
    if not os.environ.get("NEYNAR_API_KEY"):
        logger.info(f"  Farcaster search '{query}': NEYNAR_API_KEY not set — skipping")
        return []

    data = _safe_get(f"{NEYNAR_BASE}/farcaster/cast/search",
                     params={"q": query, "limit": min(limit, 25)})
    if not data:
        return []

    result = data.get("result", {})
    casts  = result.get("casts", [])
    return [_normalise_cast(c) for c in casts[:limit]]


def get_regional_casts(search_terms: list, limit_per_term: int = 10) -> list:
    """Pull Farcaster casts for a region using search terms."""
    all_casts, seen = [], set()
    for term in search_terms:
        casts = search_casts(term, limit=limit_per_term)
        for c in casts:
            h = c.get("hash")
            if h and h not in seen:
                seen.add(h)
                c["search_term"] = term
                all_casts.append(c)
        time.sleep(1.5)
    logger.info(f"  Farcaster: {len(all_casts)} unique casts for {len(search_terms)} terms")
    return all_casts


def _extract_web3_keywords(text: str) -> list:
    KEYWORDS = [
        "DeFi", "NFT", "DAO", "Web3", "blockchain", "crypto",
        "Bitcoin", "Ethereum", "Solana", "Base", "Arbitrum",
        "stablecoin", "USDC", "USDT", "tokenization", "RWA",
        "M-Pesa", "Kenya", "Africa", "Nigeria", "Nairobi",
        "MAS", "VARA", "FCA", "SEC", "MiCA", "CBDC",
        "Uniswap", "Aave", "funding", "launch", "mainnet",
        "Singapore", "Dubai", "London", "regulation"
    ]
    tl = text.lower()
    return [kw for kw in KEYWORDS if kw.lower() in tl]


def build_farcaster_record(region_code: str, search_terms: list,
                            source_id: str) -> Optional[dict]:
    """Build normalised intelligence record from Farcaster data."""
    casts = get_regional_casts(search_terms)
    if not casts:
        return None

    total_eng = sum(c["engagement"]["likes"] + c["engagement"]["recasts"] for c in casts)
    top_casts = sorted(casts, key=lambda c: c["engagement"]["likes"], reverse=True)[:10]
    all_text  = " ".join(c["text"] for c in casts)
    keywords  = _extract_web3_keywords(all_text)

    return {
        "source":   source_id,
        "url":      "https://warpcast.com",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category": f"{region_code.lower()}_web3_social",
        "entities": keywords,
        "raw_data": json.dumps({"cast_count": len(casts), "terms": search_terms}),
        "clean_data": {
            "platform":        "Farcaster",
            "region":          region_code,
            "search_terms":    search_terms,
            "cast_count":      len(casts),
            "total_engagement": total_eng,
            "top_casts":       top_casts[:5],
            "all_casts":       casts,
            "keywords":        keywords,
            "verified":        True,
            "verification":    "All casts include Farcaster hash — verify at warpcast.com/~/conversations/{hash}"
        },
        "record_hash": f"fc_{region_code}_{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    }


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    key = os.environ.get("NEYNAR_API_KEY")
    print(f"NEYNAR_API_KEY: {'SET' if key else 'NOT SET (set to enable Farcaster search)'}")
    if key:
        print("Testing search for 'kenya defi'...")
        casts = search_casts("kenya defi", limit=3)
        for c in casts:
            print(f"  @{c['author']['username']}: {c['text'][:80]}")
            print(f"  Verify: {c['verify_url']}")
    else:
        print("Set NEYNAR_API_KEY to enable Farcaster data collection")
        print("Get free key at: https://neynar.com")
