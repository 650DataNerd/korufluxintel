"""
KoruFlux Intelligence System
==============================
ingestion/regional_scraper.py

Scrapes all 8 regional markets from regional_sources.yaml.
Handles:
  - JSON APIs   (CoinGecko, DeFiLlama, GitHub)
  - RSS feeds   (news, regulatory)
  - HTML pages  (CMA, CBK, VARA, DIFC, MAS, FCA, ESMA)
  - Farcaster   (open public API — no key needed)
  - Twitter/X   (requires TWITTER_BEARER_TOKEN env var)

Every record saved includes:
  - source_url  (verifiable)
  - timestamp   (when scraped)
  - region_code (KE/EA/NG/US/EU/GB/SG/AE)
  - raw_text    (original content, no inference)

Run:
  python ingestion/regional_scraper.py --region KE
  python ingestion/regional_scraper.py --all
"""

import json
import logging
import os
import time
import hashlib
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import yaml

logger = logging.getLogger("koruflux.regional_scraper")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s"
)

CONFIG_PATH  = Path("config/regional_sources.yaml")
DATA_DIR     = Path("data/regional")

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
API_HEADERS = {
    "User-Agent": "KoruFlux-IntelAgent/2.0",
    "Accept": "application/json",
}


def load_regional_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def _make_record(source_id: str, region_code: str, category: str,
                 url: str, raw_data, clean_data: dict,
                 entities: list, verified: bool = True) -> dict:
    return {
        "source":      source_id,
        "region":      region_code,
        "url":         url,
        "timestamp":   datetime.now(timezone.utc).isoformat(),
        "category":    category,
        "verified":    verified,
        "entities":    entities,
        "raw_data":    raw_data if isinstance(raw_data, str) else json.dumps(raw_data)[:4000],
        "clean_data":  clean_data,
        "record_hash": hashlib.md5(
            f"{source_id}{region_code}{datetime.now(timezone.utc).date()}".encode()
        ).hexdigest()[:10]
    }


def _save_record(record: dict, region_code: str, source_id: str) -> Path:
    out_dir = DATA_DIR / region_code / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = out_dir / f"{source_id}_{ts}.json"
    with open(out, "w") as f:
        json.dump(record, f, indent=2)
    return out


def _robots_ok(url: str) -> bool:
    try:
        parsed = urlparse(url)
        rp = RobotFileParser()
        rp.set_url(f"{parsed.scheme}://{parsed.netloc}/robots.txt")
        rp.read()
        return rp.can_fetch(BROWSER_HEADERS["User-Agent"], url)
    except Exception:
        return True


def _extract_entities(text: str, region_code: str) -> list:
    """Extract region-relevant entities from text."""
    GLOBAL_TERMS = [
        "Web3", "DeFi", "NFT", "DAO", "blockchain", "crypto",
        "Bitcoin", "Ethereum", "stablecoin", "CBDC", "AI",
        "fintech", "startup", "funding", "regulation", "compliance",
        "Series A", "Series B", "seed round", "IPO", "acquisition"
    ]
    REGION_TERMS = {
        "KE": ["Kenya", "Nairobi", "M-Pesa", "Safaricom", "CBK", "CMA", "KES"],
        "EA": ["East Africa", "Tanzania", "Uganda", "Rwanda", "Ethiopia", "EAC"],
        "NG": ["Nigeria", "Lagos", "Abuja", "CBN", "NGN", "Naira"],
        "US": ["SEC", "CFTC", "Federal Reserve", "Wall Street", "Silicon Valley"],
        "EU": ["MiCA", "ESMA", "ECB", "European Union", "Brussels", "Frankfurt"],
        "GB": ["FCA", "Bank of England", "London", "HM Treasury", "GBP"],
        "SG": ["MAS", "Singapore", "SGD", "Project Guardian", "Fintech Festival"],
        "AE": ["VARA", "DIFC", "ADGM", "Dubai", "Abu Dhabi", "AED", "CBUAE"]
    }
    text_l = text.lower()
    found = set()
    for term in GLOBAL_TERMS:
        if term.lower() in text_l:
            found.add(term)
    for term in REGION_TERMS.get(region_code, []):
        if term.lower() in text_l:
            found.add(term)
    return list(found)


# ══════════════════════════════════════════════════════════════
# Scrapers
# ══════════════════════════════════════════════════════════════

class RegionalBaseScraper:
    def __init__(self):
        self.session = requests.Session()
        self.delay   = 2

    def _get(self, url: str, headers=None, params=None,
             timeout: int = 15) -> Optional[requests.Response]:
        for attempt in range(1, 4):
            try:
                resp = self.session.get(
                    url, headers=headers or BROWSER_HEADERS,
                    params=params, timeout=timeout
                )
                resp.raise_for_status()
                time.sleep(self.delay)
                return resp
            except requests.RequestException as e:
                logger.warning(f"    Attempt {attempt}/3 failed: {e}")
                time.sleep(self.delay * attempt)
        return None


class RegionalJsonScraper(RegionalBaseScraper):

    def fetch(self, source: dict, region_code: str) -> Optional[dict]:
        url    = source["url"]
        params = source.get("params")
        logger.info(f"  [API] {source['name']}")

        resp = self._get(url, headers=API_HEADERS, params=params)
        if not resp:
            return None
        try:
            data = resp.json()
        except ValueError:
            return None

        clean, entities = self._parse(source["id"], data, region_code)
        return _make_record(
            source["id"], region_code, source["category"],
            url, data, clean, entities
        )

    def _parse(self, source_id: str, data, region_code: str):
        if "defillama" in source_id or "protocols" in source_id:
            return self._parse_defillama(data)
        elif "coingecko" in source_id and "global" in source_id:
            return self._parse_coingecko_global(data)
        elif "coingecko" in source_id and "trending" in source_id:
            return self._parse_coingecko_trending(data)
        elif "coingecko" in source_id:
            return self._parse_coingecko_markets(data)
        elif "github" in source_id:
            return self._parse_github(data)
        else:
            items = data if isinstance(data, list) else [data]
            return {"items": items[:10]}, []

    def _parse_defillama(self, data):
        if not isinstance(data, list):
            return {}, []
        top = sorted(data, key=lambda x: x.get("tvl", 0), reverse=True)[:15]
        clean = {
            "total_protocols": len(data),
            "top_protocols": [
                {"name": p.get("name"), "tvl_usd": round(p.get("tvl", 0)),
                 "chain": p.get("chain"), "category": p.get("category")}
                for p in top
            ]
        }
        return clean, [p.get("name") for p in top if p.get("name")]

    def _parse_coingecko_global(self, data):
        d = data.get("data", {})
        return {
            "total_market_cap_usd": d.get("total_market_cap", {}).get("usd"),
            "volume_24h_usd":       d.get("total_volume", {}).get("usd"),
            "btc_dominance":        round(d.get("market_cap_percentage", {}).get("btc", 0), 2),
            "active_cryptos":       d.get("active_cryptocurrencies"),
            "market_cap_change_24h":d.get("market_cap_change_percentage_24h_usd")
        }, ["Bitcoin", "Ethereum", "Crypto Market"]

    def _parse_coingecko_trending(self, data):
        coins = data.get("coins", [])
        return {
            "trending": [
                {"name": c["item"].get("name"), "symbol": c["item"].get("symbol"),
                 "rank": c["item"].get("market_cap_rank")}
                for c in coins[:10] if c.get("item")
            ]
        }, [c["item"].get("name") for c in coins if c.get("item")]

    def _parse_coingecko_markets(self, data):
        if not isinstance(data, list):
            return {}, []
        return {
            "coins": [
                {"name": c.get("name"), "symbol": c.get("symbol"),
                 "price_usd": c.get("current_price"),
                 "market_cap": c.get("market_cap"),
                 "change_24h": c.get("price_change_percentage_24h"),
                 "rank": c.get("market_cap_rank")}
                for c in data[:20]
            ]
        }, [c.get("name") for c in data[:20]]

    def _parse_github(self, data):
        items = data.get("items", [])
        return {
            "total": data.get("total_count", len(items)),
            "repos": [
                {"name": r.get("full_name"), "stars": r.get("stargazers_count"),
                 "language": r.get("language"), "description": r.get("description"),
                 "updated": r.get("updated_at"), "url": r.get("html_url")}
                for r in items[:15]
            ]
        }, [r.get("full_name") for r in items]


class RegionalRssScraper(RegionalBaseScraper):

    def fetch(self, source: dict, region_code: str) -> Optional[dict]:
        logger.info(f"  [RSS] {source['name']}")
        resp = self._get(source["url"])
        if not resp:
            return None
        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError:
            return None

        filter_kw = source.get("filter_keyword", "").lower()
        items = []
        for item in root.findall(".//item"):
            title = (getattr(item.find("title"), "text", "") or "").strip()
            desc  = (getattr(item.find("description"), "text", "") or "").strip()
            link  = (getattr(item.find("link"), "text", "") or "").strip()
            pub   = (getattr(item.find("pubDate"), "text", "") or "").strip()

            # Apply keyword filter if set
            combined = (title + " " + desc).lower()
            if filter_kw and filter_kw not in combined:
                continue

            import re
            desc_clean = re.sub(r"<[^>]+>", " ", desc)[:400].strip()
            entities   = _extract_entities(title + " " + desc_clean, region_code)

            items.append({
                "title":       title,
                "description": desc_clean,
                "url":         link,
                "published":   pub,
                "entities":    entities,
                "source_url":  source["url"]   # verifiable
            })

        all_entities = list({e for item in items for e in item.get("entities", [])})
        clean = {
            "feed_url":    source["url"],
            "item_count":  len(items),
            "articles":    items[:25]
        }
        return _make_record(
            source["id"], region_code, source["category"],
            source["url"], resp.text[:2000], clean, all_entities
        )


class RegionalHtmlScraper(RegionalBaseScraper):

    def fetch(self, source: dict, region_code: str) -> Optional[dict]:
        url = source["url"]
        logger.info(f"  [HTML] {source['name']}")

        if not _robots_ok(url):
            logger.warning(f"    robots.txt disallows — skipping")
            return None

        resp = self._get(url)
        if not resp:
            return None

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
        except ImportError:
            logger.error("beautifulsoup4 not installed")
            return None

        selector = source.get("selectors", {}).get("articles", "h3 a, h2 a")
        links    = soup.select(selector)
        articles = []

        for el in links[:20]:
            title = el.get_text(strip=True)
            href  = el.get("href", "")
            if not href.startswith("http"):
                parsed = urlparse(url)
                href   = f"{parsed.scheme}://{parsed.netloc}{href}"
            if title and len(title) > 10:
                entities = _extract_entities(title, region_code)
                articles.append({
                    "title":      title,
                    "url":        href,
                    "entities":   entities,
                    "source_url": url   # verifiable
                })

        all_entities = list({e for a in articles for e in a.get("entities", [])})
        clean = {
            "page_url":       url,
            "articles_found": len(articles),
            "articles":       articles
        }
        return _make_record(
            source["id"], region_code, source["category"],
            url, resp.text[:1500], clean, all_entities
        )


class FarcasterScraper(RegionalBaseScraper):
    """
    Farcaster public API — no key required.
    Uses Warpcast/Neynar public endpoints.
    All data is verifiable on chain via Farcaster Hubs.
    """

    WARPCAST_BASE = "https://api.warpcast.com/v2"
    NEYNAR_BASE   = "https://api.neynar.com/v2/farcaster"

    def fetch(self, source: dict, region_code: str) -> Optional[dict]:
        logger.info(f"  [FARCASTER] {source['name']}")
        params = source.get("params", {})

        # Try channel casts first
        channel = params.get("channel")
        limit   = params.get("limit", 25)

        if source["url"].endswith("trending-casts"):
            data = self._get_trending(limit)
        elif channel:
            data = self._get_channel_casts(channel, limit)
        else:
            data = self._get_trending(limit)

        if not data:
            return None

        casts, entities = self._parse_casts(data, region_code)
        clean = {
            "platform":   "Farcaster",
            "source_url": "https://warpcast.com",
            "cast_count": len(casts),
            "casts":      casts,
            "note":       "On-chain verifiable at https://www.warpcast.com"
        }
        return _make_record(
            source["id"], region_code, source["category"],
            "https://api.warpcast.com", json.dumps(data)[:2000],
            clean, entities, verified=True
        )

    def _get_channel_casts(self, channel: str, limit: int) -> Optional[list]:
        """Fetch casts from a Farcaster channel."""
        url = f"{self.WARPCAST_BASE}/casts"
        try:
            resp = self.session.get(
                url,
                params={"channel": channel, "limit": limit},
                headers=API_HEADERS,
                timeout=12
            )
            if resp.status_code == 200:
                return resp.json().get("result", {}).get("casts", [])
        except Exception as e:
            logger.warning(f"    Farcaster channel fetch failed: {e}")

        # Fallback: search casts by keyword
        return self._search_casts(channel, limit)

    def _get_trending(self, limit: int) -> Optional[list]:
        """Fetch trending Farcaster casts."""
        try:
            resp = self.session.get(
                f"{self.WARPCAST_BASE}/trending-casts",
                params={"limit": limit},
                headers=API_HEADERS,
                timeout=12
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("result", {}).get("casts", []) or data.get("casts", [])
        except Exception as e:
            logger.warning(f"    Farcaster trending fetch failed: {e}")
        return []

    def _search_casts(self, keyword: str, limit: int) -> list:
        """Fallback: search Farcaster for keyword."""
        try:
            resp = self.session.get(
                f"{self.WARPCAST_BASE}/search-casts",
                params={"q": keyword, "limit": limit},
                headers=API_HEADERS,
                timeout=12
            )
            if resp.status_code == 200:
                return resp.json().get("result", {}).get("casts", [])
        except Exception:
            pass
        return []

    def _parse_casts(self, casts: list, region_code: str):
        parsed   = []
        entities = set()

        for cast in casts[:25]:
            if not isinstance(cast, dict):
                continue
            text    = cast.get("text", "") or ""
            author  = cast.get("author", {}) or {}
            hash_id = cast.get("hash", "")
            ts      = cast.get("timestamp", "")
            likes   = cast.get("reactions", {}).get("likes", 0) if cast.get("reactions") else 0
            recasts = cast.get("reactions", {}).get("recasts", 0) if cast.get("reactions") else 0

            ents = _extract_entities(text, region_code)
            entities.update(ents)

            parsed.append({
                "text":          text[:300],
                "author":        author.get("username", "unknown"),
                "author_fid":    author.get("fid"),
                "cast_hash":     hash_id,
                "timestamp":     ts,
                "likes":         likes,
                "recasts":       recasts,
                "entities":      ents,
                "verify_url":    f"https://warpcast.com/{author.get('username','')}/{hash_id[:8]}" if hash_id else None
            })

        return parsed, list(entities)


class TwitterScraper(RegionalBaseScraper):
    """
    Twitter/X API v2 — requires TWITTER_BEARER_TOKEN.
    Free tier removed Feb 2023. Requires Basic ($100/month) minimum.
    Falls back gracefully with clear message if no key.
    All returned data includes tweet IDs for verification.
    """

    API_BASE = "https://api.twitter.com/2"

    def fetch(self, source: dict, region_code: str) -> Optional[dict]:
        bearer = os.environ.get("TWITTER_BEARER_TOKEN")
        if not bearer:
            logger.info(
                f"  [TWITTER] Skipped — TWITTER_BEARER_TOKEN not set. "
                f"Requires Basic API ($100/mo). Set env var to enable."
            )
            return None

        logger.info(f"  [TWITTER] {source['name']}")
        params = source.get("params", {})
        query  = params.get("query", "web3 crypto")
        max_r  = params.get("max_results", 25)

        try:
            resp = self.session.get(
                f"{self.API_BASE}/tweets/search/recent",
                headers={"Authorization": f"Bearer {bearer}"},
                params={
                    "query":       query,
                    "max_results": min(max_r, 100),
                    "tweet.fields": "created_at,author_id,public_metrics,lang",
                    "expansions":   "author_id",
                    "user.fields":  "name,username,verified"
                },
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.HTTPError as e:
            logger.error(f"    Twitter API error: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"    Twitter request failed: {e}")
            return None

        tweets, entities = self._parse_tweets(data, region_code)
        clean = {
            "platform":   "Twitter/X",
            "query":      query,
            "tweet_count": len(tweets),
            "tweets":     tweets,
            "note":       "Verifiable at https://twitter.com/i/web/status/{id}"
        }
        return _make_record(
            source["id"], region_code, source["category"],
            f"{self.API_BASE}/tweets/search/recent",
            json.dumps(data)[:2000], clean, entities
        )

    def _parse_tweets(self, data: dict, region_code: str):
        tweets   = []
        entities = set()

        users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

        for tweet in data.get("data", []):
            text    = tweet.get("text", "")
            tid     = tweet.get("id", "")
            metrics = tweet.get("public_metrics", {})
            author  = users.get(tweet.get("author_id", ""), {})

            ents = _extract_entities(text, region_code)
            entities.update(ents)

            tweets.append({
                "id":           tid,
                "text":         text[:280],
                "author":       author.get("username", "unknown"),
                "created_at":   tweet.get("created_at", ""),
                "likes":        metrics.get("like_count", 0),
                "retweets":     metrics.get("retweet_count", 0),
                "replies":      metrics.get("reply_count", 0),
                "entities":     ents,
                "verify_url":   f"https://twitter.com/i/web/status/{tid}"
            })

        return tweets, list(entities)


# ══════════════════════════════════════════════════════════════
# Orchestrator
# ══════════════════════════════════════════════════════════════

SCRAPER_MAP = {
    "api_json":  RegionalJsonScraper,
    "rss":       RegionalRssScraper,
    "html":      RegionalHtmlScraper,
    "farcaster": FarcasterScraper,
    "twitter":   TwitterScraper
}


def scrape_region(region_code: str, cfg: dict = None) -> list:
    """Scrape all sources for a single region. Returns list of records."""
    if cfg is None:
        cfg = load_regional_config()

    region = cfg["regions"].get(region_code)
    if not region:
        logger.error(f"Unknown region: {region_code}")
        return []

    logger.info(f"\n{'='*55}")
    logger.info(f"  Scraping: {region['name']} ({region_code})")
    logger.info(f"  Sources:  {len(region['sources'])}")
    logger.info(f"{'='*55}")

    records = []
    for source in region["sources"]:
        scraper_cls = SCRAPER_MAP.get(source.get("type", "api_json"))
        if not scraper_cls:
            logger.warning(f"  Unknown type: {source['type']}")
            continue

        scraper = scraper_cls()
        try:
            record = scraper.fetch(source, region_code)
            if record:
                path = _save_record(record, region_code, source["id"])
                logger.info(f"    Saved: {path.name}")
                records.append(record)
            else:
                logger.warning(f"  No data: {source['id']}")
        except Exception as e:
            logger.error(f"  Error scraping {source['id']}: {e}")

    logger.info(f"\n  {region_code}: {len(records)}/{len(region['sources'])} sources successful")
    return records


def scrape_all_regions(cfg: dict = None) -> dict:
    """Scrape all 8 regions. Returns dict of region_code -> list of records."""
    if cfg is None:
        cfg = load_regional_config()

    all_records = {}
    for region_code in cfg["regions"]:
        all_records[region_code] = scrape_region(region_code, cfg)

    total = sum(len(v) for v in all_records.values())
    logger.info(f"\nTotal records scraped: {total}")
    return all_records


def load_regional_records(region_code: str) -> list:
    """Load all saved records for a region from disk."""
    raw_dir = DATA_DIR / region_code / "raw"
    if not raw_dir.exists():
        return []
    records = []
    for f in sorted(raw_dir.glob("*.json"), reverse=True)[:50]:
        try:
            with open(f) as fp:
                records.append(json.load(fp))
        except Exception:
            pass
    return records


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", help="Region code (KE/EA/NG/US/EU/GB/SG/AE)")
    parser.add_argument("--all", action="store_true", help="Scrape all regions")
    args = parser.parse_args()

    if args.all:
        scrape_all_regions()
    elif args.region:
        scrape_region(args.region.upper())
    else:
        print("Usage: python regional_scraper.py --region KE")
        print("       python regional_scraper.py --all")
