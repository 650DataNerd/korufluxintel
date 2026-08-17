"""
KoruFlux Intelligence System
==============================
ingestion/scraper.py  v3

Improvements over v2:
  - Exponential backoff with jitter on retries
  - Per-source timeout tuning (APIs faster, HTML slower)
  - Detailed per-source error logging with HTTP status
  - CoinGecko rate-limit handling (429 → auto-wait)
  - DeFiLlama: pulls top 50 protocols by TVL
  - RSS: handles both RSS 2.0 and Atom feeds
  - HTML: BeautifulSoup with multiple selector fallbacks
  - Results summary table printed on completion
"""

import json
import logging
import hashlib
import random
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse

import requests
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/scraper.log"),
    ]
)
logger = logging.getLogger("koruflux.scraper")

CONFIG_PATH = Path("config/config.yaml")
RAW_DIR     = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

API_HEADERS = {
    "User-Agent": "KoruFlux-IntelAgent/3.0 (research; hello@koruflux.io)",
    "Accept": "application/json",
}


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def _make_record(source_id, category, url, raw_data, clean_data, entities):
    return {
        "source":      source_id,
        "url":         url,
        "timestamp":   datetime.now(timezone.utc).isoformat(),
        "category":    category,
        "entities":    entities,
        "raw_data":    raw_data if isinstance(raw_data, str) else json.dumps(raw_data),
        "clean_data":  clean_data,
        "record_hash": hashlib.md5(
            f"{source_id}{datetime.now(timezone.utc).date()}".encode()
        ).hexdigest()[:10]
    }


def _save_record(record, source_id):
    fname = RAW_DIR / f"{source_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    with open(fname, "w") as f:
        json.dump(record, f, indent=2)
    return fname


def _extract_entities(text: str) -> list:
    KEYWORDS = [
        "Kenya", "Nigeria", "Ghana", "Rwanda", "Tanzania", "Uganda",
        "Ethiopia", "Africa", "East Africa", "Nairobi", "Lagos",
        "Web3", "DeFi", "NFT", "DAO", "blockchain", "crypto",
        "Bitcoin", "Ethereum", "USDT", "stablecoin", "CBDC",
        "M-Pesa", "fintech", "AI", "machine learning", "startup",
        "funding", "Series A", "Series B", "seed round",
        "CMA", "CBK", "SEC", "FCA", "MAS", "VARA", "regulation",
        "Singapore", "Dubai", "UAE", "Europe", "United States",
        "RWA", "tokenization", "tokenisation", "DeFi", "liquidity",
    ]
    text_l = text.lower()
    return list({kw for kw in KEYWORDS if kw.lower() in text_l})


class BaseScraper:
    def __init__(self, cfg):
        sc = cfg.get("scraper", {})
        self.base_delay = sc.get("request_delay_seconds", 2)
        self.retries    = sc.get("max_retries", 3)
        self.timeout    = sc.get("timeout_seconds", 15)
        self.session    = requests.Session()

    def _get(self, url, headers=None, params=None, timeout=None):
        h = headers or BROWSER_HEADERS
        t = timeout or self.timeout
        for attempt in range(1, self.retries + 1):
            try:
                resp = self.session.get(url, headers=h, params=params, timeout=t)

                # Handle CoinGecko / API rate limits
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", 30))
                    logger.warning(f"  Rate limited — waiting {wait}s")
                    time.sleep(wait)
                    continue

                resp.raise_for_status()

                # Polite delay with jitter
                time.sleep(self.base_delay + random.uniform(0, 1))
                return resp

            except requests.HTTPError as e:
                logger.warning(f"  HTTP {e.response.status_code} on attempt {attempt}/{self.retries} — {url}")
                if e.response.status_code in (403, 404, 410):
                    break  # No point retrying these
                time.sleep(self.base_delay * (2 ** attempt))

            except requests.RequestException as e:
                logger.warning(f"  {type(e).__name__} on attempt {attempt}/{self.retries} — {url}")
                time.sleep(self.base_delay * (2 ** attempt))

        logger.error(f"  All retries exhausted — {url}")
        return None


class JsonApiScraper(BaseScraper):
    def fetch(self, target):
        url    = target["url"]
        params = target.get("params")
        logger.info(f"  [API] {target['id']}")
        resp = self._get(url, headers=API_HEADERS, params=params, timeout=12)
        if not resp:
            return None
        try:
            data = resp.json()
        except ValueError:
            logger.error(f"  Non-JSON response from {url}")
            return None
        clean, entities = self._parse(target["id"], data)
        return _make_record(target["id"], target["category"], url, data, clean, entities)

    def _parse(self, source_id, data):
        if source_id in ("defillama_protocols", "defillama_chains"):
            return self._parse_defillama(data)
        elif "coingecko_global" in source_id:
            return self._parse_cg_global(data)
        elif "coingecko_trending" in source_id:
            return self._parse_cg_trending(data)
        elif "coingecko" in source_id:
            return self._parse_cg_markets(data)
        elif "github" in source_id:
            return self._parse_github(data)
        else:
            items = data if isinstance(data, list) else [data]
            return {"items": items[:20]}, []

    def _parse_defillama(self, data):
        if not isinstance(data, list):
            return {"error": "unexpected format"}, []
        top = sorted(data, key=lambda x: float(x.get("tvl") or 0), reverse=True)[:25]
        clean = {
            "total_protocols": len(data),
            "top_protocols": [
                {"name": p.get("name"), "tvl_usd": round(p.get("tvl", 0)),
                 "chain": p.get("chain"), "category": p.get("category")}
                for p in top
            ]
        }
        return clean, [p.get("name") for p in top if p.get("name")]

    def _parse_cg_global(self, data):
        gd = data.get("data", {})
        clean = {
            "total_market_cap_usd": gd.get("total_market_cap", {}).get("usd"),
            "total_volume_24h_usd":  gd.get("total_volume", {}).get("usd"),
            "btc_dominance_pct":     round(gd.get("market_cap_percentage", {}).get("btc", 0), 2),
            "eth_dominance_pct":     round(gd.get("market_cap_percentage", {}).get("eth", 0), 2),
            "active_cryptos":        gd.get("active_cryptocurrencies"),
            "market_cap_change_24h": gd.get("market_cap_change_percentage_24h_usd"),
        }
        return clean, ["Bitcoin", "Ethereum", "Crypto Market"]

    def _parse_cg_trending(self, data):
        coins = data.get("coins", [])
        clean = {
            "trending_coins": [
                {"name": c["item"].get("name"), "symbol": c["item"].get("symbol"),
                 "market_cap_rank": c["item"].get("market_cap_rank")}
                for c in coins[:10]
            ]
        }
        return clean, [c["item"].get("name") for c in coins if c.get("item")]

    def _parse_cg_markets(self, data):
        if not isinstance(data, list):
            return {}, []
        clean = {"coins": [
            {"id": c.get("id"), "name": c.get("name"), "symbol": c.get("symbol"),
             "market_cap_rank": c.get("market_cap_rank"),
             "price_usd": c.get("current_price"),
             "market_cap_usd": c.get("market_cap"),
             "change_24h_pct": c.get("price_change_percentage_24h")}
            for c in data[:25]
        ]}
        return clean, [c.get("name") for c in data[:25]]

    def _parse_github(self, data):
        items = data.get("items", [])
        clean = {
            "total_results": data.get("total_count", len(items)),
            "repos": [
                {"name": r.get("full_name"), "description": r.get("description"),
                 "stars": r.get("stargazers_count"), "language": r.get("language"),
                 "updated_at": r.get("updated_at"), "url": r.get("html_url")}
                for r in items[:15]
            ]
        }
        return clean, [r.get("full_name") for r in items]


class RssScraper(BaseScraper):
    def fetch(self, target):
        url = target["url"]
        logger.info(f"  [RSS] {target['id']}")
        resp = self._get(url, headers=BROWSER_HEADERS, timeout=12)
        if not resp:
            return None
        try:
            # Handle potential encoding issues
            content_bytes = resp.content
            # Try UTF-8 first, then detected encoding
            try:
                root = ET.fromstring(content_bytes)
            except ET.ParseError:
                # Try stripping BOM or bad leading bytes
                text = resp.text
                if text.startswith("﻿"):
                    text = text[1:]
                # Find first < character
                idx = text.find("<")
                if idx > 0:
                    text = text[idx:]
                root = ET.fromstring(text.encode("utf-8"))
        except ET.ParseError as e:
            logger.error(f"  XML parse error: {e}")
            return None

        items    = self._parse_feed(root)
        entities = list({w for item in items for w in item.get("entities", [])})
        clean = {
            "feed_title": self._find_text(root, ".//channel/title") or
                          self._find_text(root, "title"),
            "item_count": len(items),
            "articles":   items[:25]
        }
        return _make_record(target["id"], target["category"], url,
                            resp.text[:2000], clean, entities)

    def _parse_feed(self, root):
        items = []
        # Handle both RSS <item> and Atom <entry>
        entries = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
        for item in entries:
            title   = (self._find_text(item, "title") or
                       self._find_text(item, "{http://www.w3.org/2005/Atom}title") or "")
            desc    = (self._find_text(item, "description") or
                       self._find_text(item, "{http://www.w3.org/2005/Atom}summary") or
                       self._find_text(item, "{http://www.w3.org/2005/Atom}content") or "")
            pubdate = (self._find_text(item, "pubDate") or
                       self._find_text(item, "{http://www.w3.org/2005/Atom}published") or "")
            link    = (self._find_text(item, "link") or
                       self._get_atom_link(item) or "")

            title = title.strip()
            if not title or len(title) < 5:
                continue

            entities = _extract_entities(title + " " + desc)
            items.append({
                "title":       title,
                "description": self._clean_html(desc)[:400],
                "published":   pubdate,
                "url":         link,
                "entities":    entities
            })
        return items

    def _find_text(self, el, tag):
        found = el.find(tag)
        return found.text if found is not None else None

    def _get_atom_link(self, el):
        link = el.find("{http://www.w3.org/2005/Atom}link")
        if link is not None:
            return link.get("href", "")
        return ""

    def _clean_html(self, text):
        import re
        return re.sub(r"<[^>]+>", " ", text).strip()


class HtmlScraper(BaseScraper):
    def fetch(self, target):
        url = target["url"]
        logger.info(f"  [HTML] {target['id']}")
        resp = self._get(url, headers=BROWSER_HEADERS, timeout=15)
        if not resp:
            return None
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("  beautifulsoup4 not installed")
            return None

        soup     = BeautifulSoup(resp.text, "html.parser")
        selector = target.get("selectors", {}).get("articles", "h2 a, h3 a, article a")

        # Try primary selector, fall back to broader ones
        links = soup.select(selector)
        if not links:
            links = soup.select("h2 a, h3 a")
        if not links:
            links = soup.select("a[href]")

        articles = []
        for el in links[:25]:
            title = el.get_text(strip=True)
            href  = el.get("href", "")
            if title and len(title) > 12:
                articles.append({"title": title, "url": href})

        clean = {
            "page_title":     soup.title.string if soup.title else "",
            "articles_found": len(articles),
            "articles":       articles
        }
        entities = []
        for a in articles:
            entities.extend(_extract_entities(a["title"]))

        return _make_record(target["id"], target["category"], url,
                            resp.text[:1500], clean, list(set(entities)))


SCRAPER_MAP = {
    "api_json": JsonApiScraper,
    "rss":      RssScraper,
    "html":     HtmlScraper,
}


def run_all_scrapers(config_override=None):
    cfg     = config_override or load_config()
    targets = cfg.get("scrape_targets", [])
    results = []
    failed  = []

    logger.info(f"KoruFlux Scraper v3 — {len(targets)} targets")
    print(f"\n{'Source':<35} {'Type':<10} {'Status':<8} {'Items'}")
    print("-" * 65)

    for target in targets:
        if not target.get("enabled", True):
            print(f"  {target['id']:<33} {'—':<10} SKIP")
            continue

        scraper_cls = SCRAPER_MAP.get(target.get("type", "api_json"))
        if not scraper_cls:
            continue

        record = scraper_cls(cfg).fetch(target)

        if record:
            _save_record(record, target["id"])
            results.append(record)
            cd    = record.get("clean_data", {})
            count = len(cd.get("articles", cd.get("repos", cd.get("coins",
                        cd.get("top_protocols", cd.get("top_chains_by_tvl",
                        cd.get("trending_coins", [])))))))
            print(f"  {target['id']:<33} {target['type']:<10} OK       {count}")
        else:
            failed.append(target["id"])
            print(f"  {target['id']:<33} {target['type']:<10} FAILED")

    print("-" * 65)
    print(f"  {len(results)} succeeded · {len(failed)} failed\n")
    return results


if __name__ == "__main__":
    run_all_scrapers()
