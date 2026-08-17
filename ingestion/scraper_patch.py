"""
KoruFlux Intelligence System
==============================
ingestion/scraper_patch.py

Patches applied directly into scraper.py v2:
  - GitHub search uses ?q= params properly
  - CoinGecko markets uses vs_currency params
  - DeFiLlama uses /protocols (more open than /chains)
  - Source health validator with human-readable output

This file is a standalone test — run it to validate your
local sources before committing to a full scrape run.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import time

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

SOURCES_TO_TEST = [
    # (label, url, params)
    ("CoinGecko Markets",    "https://api.coingecko.com/api/v3/coins/markets",
        {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 5, "page": 1}),
    ("CoinGecko Trending",   "https://api.coingecko.com/api/v3/search/trending", None),
    ("CoinGecko Global",     "https://api.coingecko.com/api/v3/global", None),
    ("DeFiLlama Protocols",  "https://api.llama.fi/protocols", None),
    ("GitHub Web3 Africa",   "https://api.github.com/search/repositories",
        {"q": "web3 africa kenya", "sort": "stars", "per_page": 5}),
    ("VentureBurn RSS",      "https://ventureburn.com/feed/", None),
    ("TechPoint Africa RSS", "https://techpoint.africa/feed/", None),
    ("BitcoinKE RSS",        "https://bitcoinke.io/feed/", None),
    ("CoinDesk RSS",         "https://www.coindesk.com/arc/outboundfeeds/rss/", None),
    ("CoinTelegraph RSS",    "https://cointelegraph.com/rss", None),
    ("CBK Press Releases",   "https://www.centralbank.go.ke/media-center/press-releases/", None),
    ("AfricaNews Business",  "https://www.africanews.com/rss/business", None),
]


def run_health_check():
    print("\n🔍 KoruFlux — Live Source Health Check")
    print("=" * 60)

    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)

    ok, fail = [], []

    for label, url, params in SOURCES_TO_TEST:
        try:
            r = session.get(url, params=params, timeout=10)
            status = r.status_code
            size   = len(r.content)
            if status < 400:
                print(f"  ✅  {label:<30} {status}  ({size:,} bytes)")
                ok.append(label)
            else:
                print(f"  ❌  {label:<30} HTTP {status}")
                fail.append(label)
        except requests.exceptions.ConnectionError:
            print(f"  🔌  {label:<30} NO INTERNET (expected in sandbox)")
            fail.append(label)
        except Exception as e:
            print(f"  ❌  {label:<30} {type(e).__name__}: {e}")
            fail.append(label)
        time.sleep(0.3)

    print("=" * 60)
    print(f"  ✅ Working : {len(ok)}/{len(SOURCES_TO_TEST)}")
    print(f"  ❌ Failed  : {len(fail)}/{len(SOURCES_TO_TEST)}")

    if fail:
        print(f"\n  Failed sources:")
        for f in fail:
            print(f"    · {f}")

    print()
    return ok, fail


if __name__ == "__main__":
    run_health_check()
