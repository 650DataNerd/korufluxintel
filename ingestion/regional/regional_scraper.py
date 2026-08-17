"""
KoruFlux Intelligence System
==============================
ingestion/regional/regional_scraper.py

Orchestrates data collection for all 8 regional markets.
Each region gets its own dedicated data pipeline.

Data saved to: data/regional/{CODE}/raw/

Run:
  python ingestion/regional/regional_scraper.py            # all regions
  python ingestion/regional/regional_scraper.py --region KE
  python ingestion/regional/regional_scraper.py --health
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger("koruflux.regional_scraper")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")

CONFIG_PATH  = Path("config/config.yaml")
REGIONS_PATH = Path("config/regions.yaml")
REGIONAL_DIR = Path("data/regional")

BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
API_HEADERS = {
    "User-Agent": "KoruFlux-IntelAgent/2.0 (research; hello@koruflux.io)",
    "Accept": "application/json",
}


def load_regions() -> dict:
    with open(REGIONS_PATH) as f:
        return yaml.safe_load(f)


def _save(record: dict, region_code: str) -> Path:
    d = REGIONAL_DIR / region_code / "raw"
    d.mkdir(parents=True, exist_ok=True)
    fname = d / f"{record['source']}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    with open(fname, "w") as f:
        json.dump(record, f, indent=2)
    return fname


def _make_record(source_id, category, url, raw, clean, entities) -> dict:
    return {
        "source":     source_id,
        "url":        url,
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "category":   category,
        "entities":   entities,
        "raw_data":   raw if isinstance(raw, str) else json.dumps(raw)[:2000],
        "clean_data": clean,
        "record_hash": f"{source_id}_{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    }


# ── Individual scrapers ────────────────────────────────────────

def _fetch_rss(source: dict, region_code: str, session: requests.Session) -> Optional[dict]:
    import xml.etree.ElementTree as ET
    import re

    url = source["url"]
    try:
        r = session.get(url, headers=BROWSER_HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        logger.warning(f"  RSS {source['id']}: {e}")
        return None

    try:
        try:
            root = ET.fromstring(r.content)
        except ET.ParseError:
            text = r.text
            if text.startswith("﻿"):
                text = text[1:]
            idx = text.find("<")
            if idx > 0:
                text = text[idx:]
            root = ET.fromstring(text.encode("utf-8"))
    except ET.ParseError:
        return None

    def txt(el, tag):
        f = el.find(tag)
        return f.text if f is not None else ""

    def clean_html(t):
        return re.sub(r"<[^>]+>", " ", t or "").strip()

    items = []
    REGION_KEYWORDS = {
        "KE": ["kenya", "nairobi", "mpesa", "cbk", "cma kenya", "safaricom"],
        "EA": ["east africa", "kenya", "tanzania", "uganda", "rwanda", "ethiopia", "africa"],
        "NG": ["nigeria", "lagos", "cbn", "naira", "abuja"],
        "US": ["defi", "ethereum", "bitcoin", "sec", "cftc", "crypto", "blockchain", "rwa"],
        "EU": ["europe", "eu", "mica", "esma", "ecb", "european"],
        "GB": ["uk", "fca", "london", "britain", "sterling"],
        "SG": ["singapore", "mas", "project guardian", "token2049"],
        "AE": ["dubai", "uae", "vara", "difc", "adgm", "abu dhabi"],
    }.get(region_code, [])

    for item in root.findall(".//item"):
        title = txt(item, "title").strip()
        desc  = clean_html(txt(item, "description"))[:300]
        link  = txt(item, "link")
        pubdate = txt(item, "pubDate")

        combined = (title + " " + desc).lower()

        # Only keep articles relevant to this region
        relevant = (
            not REGION_KEYWORDS or
            any(kw in combined for kw in REGION_KEYWORDS)
        )
        if not relevant:
            continue

        entities = [kw for kw in [
            "Kenya","Nigeria","East Africa","Dubai","Singapore","Europe",
            "DeFi","NFT","Web3","blockchain","crypto","Bitcoin","Ethereum",
            "M-Pesa","VARA","MAS","FCA","SEC","MiCA","RWA","AI","fintech"
        ] if kw.lower() in combined]

        items.append({
            "title":     title,
            "summary":   desc[:250],
            "url":       link,
            "published": pubdate,
            "entities":  entities,
            "source_name": source.get("label", source["id"]),
            "verified":  True,
            "source_url": url
        })

    if not items:
        return None

    all_entities = list({e for item in items for e in item["entities"]})
    clean = {
        "feed_title":  txt(root, ".//channel/title"),
        "region":      region_code,
        "article_count": len(items),
        "articles":    items[:25],
        "source_url":  url
    }
    return _make_record(source["id"], source["category"], url,
                        r.text[:1000], clean, all_entities)


def _fetch_api_json(source: dict, region_code: str, session: requests.Session) -> Optional[dict]:
    url    = source["url"]
    params = source.get("params", {})
    try:
        r = session.get(url, headers=API_HEADERS, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.warning(f"  API {source['id']}: {e}")
        return None

    sid = source["id"]

    # CoinGecko markets
    if "coins/markets" in url:
        coins = data[:25] if isinstance(data, list) else []
        clean = {"coins": [{
            "id": c.get("id"), "name": c.get("name"), "symbol": c.get("symbol"),
            "price_usd": c.get("current_price"), "market_cap": c.get("market_cap"),
            "change_24h": c.get("price_change_percentage_24h"),
            "market_cap_rank": c.get("market_cap_rank")
        } for c in coins], "source_url": url}
        return _make_record(sid, source["category"], url, {}, clean,
                            [c.get("name") for c in coins[:10]])

    # CoinGecko global
    if "global" in url:
        gd = data.get("data", {})
        clean = {
            "total_market_cap_usd": gd.get("total_market_cap", {}).get("usd"),
            "total_volume_24h_usd": gd.get("total_volume", {}).get("usd"),
            "btc_dominance": round(gd.get("market_cap_percentage", {}).get("btc", 0), 2),
            "active_cryptos": gd.get("active_cryptocurrencies"),
            "market_cap_change_24h": gd.get("market_cap_change_percentage_24h_usd"),
            "source_url": url
        }
        return _make_record(sid, source["category"], url, {}, clean,
                            ["Bitcoin", "Ethereum", "Crypto Market"])

    # CoinGecko trending
    if "trending" in url:
        coins = data.get("coins", [])[:10]
        clean = {"trending": [{
            "name": c["item"].get("name"), "symbol": c["item"].get("symbol"),
            "rank": c["item"].get("market_cap_rank")
        } for c in coins if c.get("item")], "source_url": url}
        return _make_record(sid, source["category"], url, {}, clean,
                            [c["item"].get("name") for c in coins if c.get("item")])

    # DeFiLlama protocols
    if "llama.fi/protocols" in url:
        protos = sorted(data, key=lambda x: float(x.get("tvl") or 0), reverse=True)[:20] if isinstance(data, list) else []
        clean = {"top_protocols": [{
            "name": p.get("name"), "tvl_usd": round(p.get("tvl", 0)),
            "category": p.get("category"), "chain": p.get("chain")
        } for p in protos], "source_url": url}
        return _make_record(sid, source["category"], url, {}, clean,
                            [p.get("name") for p in protos])

    # GitHub
    if "github.com/search" in url:
        items = data.get("items", [])[:15]
        clean = {"total": data.get("total_count", 0), "repos": [{
            "name": r.get("full_name"), "desc": r.get("description"),
            "stars": r.get("stargazers_count"), "lang": r.get("language"),
            "updated": r.get("updated_at"), "url": r.get("html_url")
        } for r in items], "source_url": url}
        return _make_record(sid, source["category"], url, {}, clean,
                            [r.get("full_name") for r in items])

    # Generic
    clean = {"data": data if isinstance(data, dict) else {"items": data[:10]},
             "source_url": url}
    return _make_record(sid, source["category"], url, {}, clean, [])


def _fetch_html(source: dict, region_code: str, session: requests.Session) -> Optional[dict]:
    url = source["url"]
    try:
        r = session.get(url, headers=BROWSER_HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        logger.warning(f"  HTML {source['id']}: {e}")
        return None

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")
        selector = source.get("selectors", {}).get("articles", "h2 a, h3 a, article a")
        links = soup.select(selector)
        articles = [{"title": el.get_text(strip=True), "url": el.get("href", "")}
                    for el in links[:20] if len(el.get_text(strip=True)) > 10]
        clean = {"articles": articles, "article_count": len(articles), "source_url": url}
        return _make_record(source["id"], source["category"], url,
                            r.text[:500], clean, [])
    except ImportError:
        logger.warning("  beautifulsoup4 not installed")
        return None


# ── Social sources ─────────────────────────────────────────────

def _fetch_farcaster(source: dict, region_code: str, region_cfg: dict) -> Optional[dict]:
    from ingestion.regional.farcaster_connector import build_farcaster_record
    terms = source.get("search_terms", region_cfg.get("farcaster_terms", []))
    return build_farcaster_record(region_code, terms, source["id"])


def _fetch_twitter(source: dict, region_code: str, region_cfg: dict) -> Optional[dict]:
    from ingestion.regional.twitter_connector import build_twitter_record
    terms = region_cfg.get("twitter_terms", [])
    return build_twitter_record(region_code, terms, source["id"])


# ── Main orchestrator ──────────────────────────────────────────

def scrape_region(region_code: str, region_cfg: dict) -> list:
    """Scrape all sources for one region. Returns list of records."""
    logger.info(f"\n--- Scraping {region_code}: {region_cfg['name']} ---")
    records = []
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)

    sources = region_cfg.get("sources", [])
    logger.info(f"  {len(sources)} sources configured")

    for source in sources:
        sid  = source["id"]
        stype = source.get("type", "rss")
        record = None

        logger.info(f"  [{stype.upper()}] {sid}")

        if stype == "rss":
            record = _fetch_rss(source, region_code, session)
        elif stype == "api_json":
            record = _fetch_api_json(source, region_code, session)
        elif stype == "html":
            record = _fetch_html(source, region_code, session)
        elif stype == "farcaster":
            record = _fetch_farcaster(source, region_code, region_cfg)
        elif stype == "twitter":
            record = _fetch_twitter(source, region_code, region_cfg)

        if record:
            _save(record, region_code)
            records.append(record)
            logger.info(f"    -> saved")
        else:
            logger.info(f"    -> no data")

        time.sleep(1.5)

    logger.info(f"  {region_code}: {len(records)}/{len(sources)} sources returned data")
    return records


def scrape_all_regions() -> dict:
    """Scrape all 8 regions. Returns dict of region_code -> records."""
    regions = load_regions().get("regions", {})
    results = {}
    for code, cfg in regions.items():
        try:
            records = scrape_region(code, cfg)
            results[code] = records
        except Exception as e:
            logger.error(f"Region {code} failed: {e}")
            results[code] = []
    logger.info(f"\nAll regions scraped: {sum(len(v) for v in results.values())} total records")
    return results


def health_check(region_code: str = None) -> dict:
    """Check connectivity for all sources in a region (or all regions)."""
    regions = load_regions().get("regions", {})
    if region_code:
        regions = {region_code: regions[region_code]}

    session = requests.Session()
    results = {"ok": [], "fail": [], "skip": []}

    print(f"\nKoruFlux Regional Source Health Check")
    print("=" * 58)

    for code, cfg in regions.items():
        print(f"\n  {code} — {cfg['name']}")
        for source in cfg.get("sources", []):
            stype = source.get("type", "rss")
            if stype in ("farcaster", "twitter"):
                print(f"    [SOCIAL] {source['id']} — requires API key")
                results["skip"].append(source["id"])
                continue
            try:
                r = session.head(source["url"], timeout=8, allow_redirects=True)
                ok = r.status_code < 400
                symbol = "OK" if ok else "FAIL"
                print(f"    [{symbol}] {r.status_code}  {source.get('label', source['id'])}")
                (results["ok"] if ok else results["fail"]).append(source["id"])
            except Exception as e:
                print(f"    [ERR]      {source.get('label', source['id'])} — {type(e).__name__}")
                results["fail"].append(source["id"])
            time.sleep(0.3)

    print(f"\n{'='*58}")
    print(f"  OK: {len(results['ok'])}  FAIL: {len(results['fail'])}  SKIP: {len(results['skip'])}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", help="Single region code (KE/EA/NG/US/EU/GB/SG/AE)")
    parser.add_argument("--health", action="store_true", help="Health check only")
    args = parser.parse_args()

    if args.health:
        health_check(args.region)
    elif args.region:
        regions = load_regions().get("regions", {})
        if args.region not in regions:
            print(f"Unknown region: {args.region}. Valid: {list(regions.keys())}")
        else:
            scrape_region(args.region, regions[args.region])
    else:
        scrape_all_regions()
