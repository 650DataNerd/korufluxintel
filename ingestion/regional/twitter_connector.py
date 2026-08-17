"""
KoruFlux Intelligence System
==============================
ingestion/regional/twitter_connector.py

Twitter/X API v2 connector. Requires paid developer account.

SETUP:
  1. Go to developer.twitter.com
  2. Create project + app (Basic tier: $100/month)
  3. Generate Bearer Token
  4. export TWITTER_BEARER_TOKEN=AAAA...

WITHOUT KEY: returns empty, system continues normally.
DATA: tweet_id, author_id, text, created_at, metrics, URL.
VERIFICATION: every tweet links to twitter.com/i/web/status/{id}
"""

import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests

logger = logging.getLogger("koruflux.twitter")
API_BASE = "https://api.twitter.com/2"


def _get_headers() -> Optional[dict]:
    token = os.environ.get("TWITTER_BEARER_TOKEN")
    if not token:
        return None
    return {"Authorization": f"Bearer {token}", "User-Agent": "KoruFlux-IntelAgent/2.0"}


def _normalise_tweet(raw: dict) -> dict:
    metrics = raw.get("public_metrics", {})
    return {
        "tweet_id":   raw.get("id", ""),
        "text":       raw.get("text", "")[:500],
        "author_id":  raw.get("author_id", ""),
        "created_at": raw.get("created_at", ""),
        "likes":      metrics.get("like_count", 0),
        "retweets":   metrics.get("retweet_count", 0),
        "replies":    metrics.get("reply_count", 0),
        "impressions": metrics.get("impression_count", 0),
        "verify_url": f"https://twitter.com/i/web/status/{raw.get('id','')}",
        "data_source": "Twitter/X API v2",
        "verified":   True
    }


def search_recent(query: str, max_results: int = 20) -> list:
    """Search recent tweets (last 7 days). Requires Bearer Token."""
    headers = _get_headers()
    if not headers:
        logger.info(f"  Twitter: TWITTER_BEARER_TOKEN not set — skipping")
        return []

    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {
        "query":        f"{query} -is:retweet lang:en",
        "max_results":  min(max_results, 100),
        "tweet.fields": "created_at,public_metrics,author_id",
        "start_time":   since
    }
    try:
        r = requests.get(f"{API_BASE}/tweets/search/recent",
                         headers=headers, params=params, timeout=15)
        if r.status_code == 200:
            data = r.json()
            tweets = data.get("data", [])
            logger.info(f"  Twitter: {len(tweets)} tweets for '{query}'")
            return [_normalise_tweet(t) for t in tweets]
        elif r.status_code == 401:
            logger.warning("  Twitter: 401 — invalid or expired Bearer Token")
        elif r.status_code == 429:
            logger.warning("  Twitter: 429 — rate limit hit")
        else:
            logger.warning(f"  Twitter: HTTP {r.status_code}")
        return []
    except Exception as e:
        logger.warning(f"  Twitter request failed: {e}")
        return []


def get_regional_tweets(search_terms: list, max_per_term: int = 15) -> list:
    """Pull tweets for a region across all search terms."""
    all_tweets, seen = [], set()
    for term in search_terms:
        tweets = search_recent(term, max_results=max_per_term)
        for t in tweets:
            tid = t.get("tweet_id")
            if tid and tid not in seen:
                seen.add(tid)
                t["search_term"] = term
                all_tweets.append(t)
        time.sleep(2)  # Respect rate limits
    logger.info(f"  Twitter: {len(all_tweets)} unique tweets")
    return all_tweets


def build_twitter_record(region_code: str, search_terms: list,
                          source_id: str) -> Optional[dict]:
    """Build normalised intelligence record from Twitter data."""
    tweets = get_regional_tweets(search_terms)
    if not tweets:
        return None

    total_eng = sum(t["likes"] + t["retweets"] for t in tweets)
    all_text  = " ".join(t["text"] for t in tweets)

    return {
        "source":    source_id,
        "url":       "https://twitter.com",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category":  f"{region_code.lower()}_social_twitter",
        "entities":  [],
        "raw_data":  json.dumps({"tweet_count": len(tweets), "terms": search_terms}),
        "clean_data": {
            "platform":         "Twitter/X",
            "region":           region_code,
            "search_terms":     search_terms,
            "tweet_count":      len(tweets),
            "total_engagement": total_eng,
            "top_tweets":       sorted(tweets, key=lambda t: t["likes"], reverse=True)[:5],
            "all_tweets":       tweets,
            "verified":         True,
            "verification":     "Each tweet links to twitter.com/i/web/status/{tweet_id}"
        },
        "record_hash": f"tw_{region_code}_{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    }


def check_api_status() -> dict:
    headers = _get_headers()
    if not headers:
        return {"available": False, "reason": "TWITTER_BEARER_TOKEN not set"}
    try:
        r = requests.get(f"{API_BASE}/tweets/search/recent",
                         headers=headers,
                         params={"query": "test", "max_results": 10},
                         timeout=10)
        if r.status_code == 200:
            return {"available": True, "tier": "Basic+"}
        return {"available": False, "reason": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"available": False, "reason": str(e)}


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    token = os.environ.get("TWITTER_BEARER_TOKEN")
    print(f"TWITTER_BEARER_TOKEN: {'SET' if token else 'NOT SET'}")
    if not token:
        print("\nTo enable Twitter/X data:")
        print("  1. Go to developer.twitter.com")
        print("  2. Create app (Basic tier required: $100/month)")
        print("  3. export TWITTER_BEARER_TOKEN=your_token_here")
    else:
        status = check_api_status()
        print(f"API Status: {status}")
