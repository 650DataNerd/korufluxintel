# KoruFlux Intelligence System

> **Build. Transition. Strategize. Land.**  
> Automated market intelligence for Web3, DeFi, RWA, and AI Fintech across 8 global markets.

---

## What This Is

A data scraping, analysis, and visualization system built for [KoruFlux](https://koruflux.com) — a Nairobi-based strategy consultancy specialising in Web3 and African market entry.

The system collects intelligence from 14+ live sources, scores opportunities across 9 sectors and 8 markets, and produces client-ready dashboards and reports automatically.

**Live dashboard:** https://korufluxintel.netlify.app

---

## Markets Covered

| Code | Market | Top Sector |
|------|--------|------------|
| KE | Kenya / Nairobi | Payments |
| EA | East Africa | Payments |
| NG | Nigeria | Payments |
| US | United States | DeFi |
| EU | European Union | Regulatory |
| GB | United Kingdom | AI Fintech |
| SG | Singapore | RWA |
| AE | UAE / Dubai | RWA |

---

## Setup

```bash
# 1. Clone
git clone https://github.com/650DataNerd/korufluxintel.git
cd korufluxintel

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install pyyaml requests beautifulsoup4 lxml matplotlib openpyxl flask pypdf numpy

# 4. Run the pipeline
python main.py --skip-scrape    # Use cached data (fast)
python main.py                  # Live scrape (pulls real data)

# 5. Start web UI
python webui/app.py
# Open: http://localhost:5000
```

---

## Project Structure
korufluxintel/
├── main.py # Master pipeline runner
├── scheduler.py # Daily auto-run
├── config/
│ ├── config.yaml # Global sources + settings
│ └── regions.yaml # Per-region source config
├── ingestion/
│ ├── scraper.py # Web scraper (API, RSS, HTML)
│ ├── doc_ingestor.py # PDF document reader
│ ├── twitter_connector.py # Twitter/X social signals
│ └── regional/
│ ├── regional_scraper.py # Per-region data collection
│ └── farcaster_connector.py # Farcaster Web3 social
├── processing/
│ └── parser.py # Normaliser + tagger
├── analysis/
│ ├── analyzer.py # Global scoring engine
│ ├── history_tracker.py # Trend tracking
│ ├── ai_narrator.py # AI narrative generation
│ └── regional/
│ └── regional_analyzer.py # Per-market scoring
├── visualization/
│ ├── dashboard_builder.py # Global interactive dashboard
│ ├── regional_dashboard.py # 8 regional dashboards + hub
│ ├── visualizer.py # PNG charts
│ └── exporter.py # Excel + Markdown exports
├── webui/
│ └── app.py # Flask web UI
│ templates/ # HTML templates
└── docs/ # KoruFlux business documents (PDFs)


---

## Pipeline Commands

```bash
python main.py                    # Full pipeline (scrape + analyze + build)
python main.py --skip-scrape      # Skip scraping, use cached data
python main.py --only-regional    # Regional pipeline only
python main.py --health-check     # Test source connectivity
python scheduler.py --crontab     # Print cron setup line
```

---

## Optional: API Keys

Add to environment variables to unlock additional features:

```bash
# AI narrative briefs (claude.ai API)
export ANTHROPIC_API_KEY=sk-ant-...

# Twitter/X social signals
export TWITTER_BEARER_TOKEN=...
```

---

## Data Sources

**Market Data:** CoinGecko, DeFiLlama  
**News:** CoinDesk, CoinTelegraph, TechPoint Africa, BitcoinKE  
**Developer Activity:** GitHub API  
**Social:** Farcaster (open), Twitter/X (key required)  
**Regulatory:** CBK Kenya, CMA Kenya, ESMA, FCA, MAS, VARA  
**Internal:** KoruFlux business documents (PDFs)

---

## Contact

**KoruFlux** · Nairobi, Kenya  
hello@koruflux.io · [koruflux.com](https://koruflux.com)
