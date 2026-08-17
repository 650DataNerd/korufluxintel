"""
KoruFlux Intelligence System
==============================
ingestion/doc_ingestor.py

Reads KoruFlux's own business documents (PDFs) and converts them
into structured intelligence records that feed the analysis engine.

This gives the analysis engine:
  - KoruFlux's exact service definitions (used for relevance scoring)
  - Pricing anchors (for opportunity sizing)
  - Client profile signals (who KoruFlux works with → what sectors matter)
  - Competitive framing (what KoruFlux says about the market)
  - Entity vocabulary (protocols, regions, regulations mentioned)

Output: records saved to data/raw/  (same schema as scraper output)
        + a context file: data/processed/koruflux_context.json

Run standalone:  python ingestion/doc_ingestor.py
"""

import json
import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("koruflux.doc_ingestor")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Docs folder — relative to project root
DOCS_DIR = Path("docs")


# ══════════════════════════════════════════════════════════════
# PDF Text Extraction
# ══════════════════════════════════════════════════════════════

def extract_pdf_text(pdf_path: Path) -> Optional[str]:
    """Extract clean text from a PDF. Uses pypdf with pdftotext fallback."""
    # Try pdftotext first (cleaner output for formatted docs)
    import subprocess
    try:
        result = subprocess.run(
            ["pdftotext", str(pdf_path), "-"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Fallback: pypdf
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)
    except Exception as e:
        logger.error(f"  ❌ Could not extract text from {pdf_path.name}: {e}")
        return None


# ══════════════════════════════════════════════════════════════
# Structured Extraction from KoruFlux Docs
# ══════════════════════════════════════════════════════════════

def _extract_services(text: str) -> list:
    """Pull service names and descriptions."""
    services = []
    # Match pillar headings and their bullet points
    pillar_pattern = re.compile(
        r'(Build|Transition|Strategize|Land)\s*[:\n•](.+?)(?=Build|Transition|Strategize|Land|Who We|$)',
        re.DOTALL | re.IGNORECASE
    )
    for match in pillar_pattern.finditer(text):
        name = match.group(1).strip()
        body = re.sub(r'\s+', ' ', match.group(2)).strip()[:400]
        services.append({"pillar": name, "description": body})
    return services


def _extract_pricing(text: str) -> list:
    """Extract pricing signals."""
    pricing = []
    # USD amounts
    amounts = re.findall(r'USD[\s]?[\d,]+(?:\s?[–\-]\s?[\d,]+)?(?:\s?/\s?\w+)?', text)
    # Week/month ranges
    durations = re.findall(r'\d+[–\-]\d+\s+(?:week|month|wk)', text, re.IGNORECASE)
    for a in amounts:
        pricing.append({"type": "price", "value": a.strip()})
    for d in durations:
        pricing.append({"type": "duration", "value": d.strip()})
    return pricing


def _extract_client_types(text: str) -> list:
    """Extract who KoruFlux works with."""
    client_keywords = [
        "Web3 Startup", "International Corp", "African Fintech",
        "Web2 Business", "Growth-Stage", "DeFi platform",
        "RWA project", "infrastructure provider", "crypto-native"
    ]
    found = []
    text_lower = text.lower()
    for kw in client_keywords:
        if kw.lower() in text_lower:
            found.append(kw)
    return found


def _extract_markets(text: str) -> list:
    """Extract all geographic markets mentioned."""
    MARKET_TERMS = [
        "Kenya", "East Africa", "Nigeria", "Ghana", "Rwanda", "Uganda",
        "Tanzania", "Ethiopia", "South Africa", "Africa",
        "US", "EU", "UK", "UAE", "Singapore", "Hong Kong",
        "Nairobi", "Lagos", "Kigali"
    ]
    found = []
    for term in MARKET_TERMS:
        if term.lower() in text.lower():
            found.append(term)
    return list(set(found))


def _extract_technologies(text: str) -> list:
    """Extract specific tech stack mentions."""
    TECH_TERMS = [
        "Solidity", "Rust", "Solana", "Ethereum", "DeFi", "NFT", "DAO",
        "Smart contract", "LLM", "AI", "Machine learning", "Data pipeline",
        "M-Pesa", "CBDC", "Stablecoin", "Tokenomics", "RWA",
        "KYC", "AML", "API", "CRM", "Web3", "Blockchain"
    ]
    found = []
    for term in TECH_TERMS:
        if term.lower() in text.lower():
            found.append(term)
    return list(set(found))


def _extract_regulators(text: str) -> list:
    """Extract regulatory bodies mentioned."""
    REGULATORS = [
        "CMA", "CBK", "SEC", "FCA", "MAS", "VARA",
        "FSCA", "CMSA", "Data Protection", "GDPR", "VASP", "FATF"
    ]
    found = [r for r in REGULATORS if r.lower() in text.lower()]
    return found


def _extract_competitors(text: str) -> list:
    """Any competitors or comparable firms mentioned."""
    # Look for "competitor", "unlike", "other consultancies" patterns
    patterns = re.findall(
        r'(?:unlike|compared to|other|competitors?)\s+([A-Z][a-zA-Z\s&]{3,30})',
        text
    )
    return list(set(patterns))[:10]


# ══════════════════════════════════════════════════════════════
# Per-Document Parsing
# ══════════════════════════════════════════════════════════════

DOC_ROLES = {
    "KoruFlux_Whitepaper": "core_whitepaper",
    "KoruFlux_Company_Overview": "company_overview",
    "KoruFlux_Services": "services_detail",
    "KoruFlux.docx": "pitch_sheet",
    "KoruFlux (2)": "pitch_sheet_alt"
}


def parse_document(pdf_path: Path) -> Optional[dict]:
    """Parse a single PDF into a structured intelligence record."""
    logger.info(f"  📄 Reading {pdf_path.name}...")
    text = extract_pdf_text(pdf_path)
    if not text or len(text.strip()) < 100:
        logger.warning(f"     ⚠️  Insufficient text extracted from {pdf_path.name}")
        return None

    # Determine doc role
    role = "unknown"
    for key, val in DOC_ROLES.items():
        if key.lower() in pdf_path.stem.lower():
            role = val
            break

    services   = _extract_services(text)
    pricing    = _extract_pricing(text)
    clients    = _extract_client_types(text)
    markets    = _extract_markets(text)
    techs      = _extract_technologies(text)
    regulators = _extract_regulators(text)
    competitors= _extract_competitors(text)

    # All named entities combined
    entities = list(set(markets + techs + regulators))

    clean_data = {
        "document_role": role,
        "word_count": len(text.split()),
        "service_pillars": services,
        "pricing_signals": pricing,
        "client_types": clients,
        "markets_mentioned": markets,
        "technologies": techs,
        "regulators_mentioned": regulators,
        "competitors_mentioned": competitors,
        "text_excerpt": text[:1200].strip()
    }

    record = {
        "source": f"koruflux_doc_{pdf_path.stem.replace(' ', '_').lower()}",
        "url": f"local://{pdf_path}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category": "internal_document",
        "entities": entities,
        "raw_data": text[:3000],
        "clean_data": clean_data,
        "record_hash": f"doc_{pdf_path.stem[:12]}_{datetime.utcnow().strftime('%Y%m%d')}"
    }
    return record


# ══════════════════════════════════════════════════════════════
# Context Synthesiser
# ══════════════════════════════════════════════════════════════

def build_koruflux_context(records: list) -> dict:
    """
    Synthesise all doc records into a single KoruFlux context object.
    This is loaded by the analyzer to calibrate recommendations.
    """
    all_services = []
    all_pricing  = []
    all_clients  = []
    all_markets  = []
    all_techs    = []
    all_regs     = []

    for r in records:
        cd = r.get("clean_data", {})
        all_services  += cd.get("service_pillars", [])
        all_pricing   += cd.get("pricing_signals", [])
        all_clients   += cd.get("client_types", [])
        all_markets   += cd.get("markets_mentioned", [])
        all_techs     += cd.get("technologies", [])
        all_regs      += cd.get("regulators_mentioned", [])

    # Deduplicate
    from collections import Counter
    market_freq = Counter(all_markets)
    tech_freq   = Counter(all_techs)
    client_freq = Counter(all_clients)

    context = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_documents": len(records),
        "company": {
            "name": "KoruFlux",
            "hq": "Nairobi, Kenya",
            "founded": "2026",
            "tagline": "Build. Transition. Strategize. Land.",
            "contact": "hello@koruflux.io"
        },
        "service_pillars": ["Build", "Transition", "Strategize", "Land"],
        "engagement_types": [
            {"type": "Intelligence Sprint", "duration": "4-6 weeks", "price": "USD 4,500–7,500"},
            {"type": "Retainer", "duration": "monthly", "price": "USD 2,500–4,000/month"},
            {"type": "Entry Programme", "duration": "8-16 weeks", "price": "USD 15,000–25,000"},
            {"type": "Sprint (Project)", "duration": "4-8 weeks", "price": "defined per scope"},
            {"type": "Integrated Programme", "duration": "8-16 weeks", "price": "multi-pillar"}
        ],
        "target_markets": dict(market_freq.most_common(12)),
        "core_technologies": dict(tech_freq.most_common(15)),
        "client_types": dict(client_freq.most_common(10)),
        "regulators_tracked": list(set(all_regs)),
        "unique_advantages": [
            "Nairobi HQ — Africa's tech capital gateway",
            "Rare skill stack: Web3 + AI + Data + Strategy",
            "Data-driven backbone — no guesswork",
            "Bridge positioning: Web3-native AND corporate enterprise",
            "Local + global network access"
        ],
        "methodology_layers": [
            "Layer 1: Market Intelligence (macro, regulatory, competitive)",
            "Layer 2: On-Chain & Off-Chain Data (wallet, social, developer signals)",
            "Layer 3: Client Data & Operational Metrics (CRM, product, financials)"
        ]
    }

    return context


# ══════════════════════════════════════════════════════════════
# Main Entry Point
# ══════════════════════════════════════════════════════════════

def ingest_documents(docs_path: Path = None) -> tuple[list, dict]:
    """
    Ingest all PDFs from the docs folder.
    Returns (list of records, koruflux_context dict).
    """
    if docs_path is None:
        # Try a few common locations
        for candidate in [Path("docs"), Path("../koruflux/Docs"), Path("koruflux/Docs")]:
            if candidate.exists():
                docs_path = candidate
                break

    if docs_path is None or not docs_path.exists():
        logger.warning("⚠️  Docs folder not found. Skipping document ingestion.")
        return [], {}

    pdfs = list(docs_path.glob("*.pdf"))
    logger.info(f"📂 Found {len(pdfs)} PDFs in {docs_path}")

    records = []
    for pdf in pdfs:
        record = parse_document(pdf)
        if record:
            # Save as raw record
            out = RAW_DIR / f"{record['source']}_{datetime.utcnow().strftime('%Y%m%d')}.json"
            with open(out, "w") as f:
                json.dump(record, f, indent=2)
            logger.info(f"     ✅ Saved → {out.name}")
            records.append(record)

    context = build_koruflux_context(records)

    # Save context file
    ctx_path = PROCESSED_DIR / "koruflux_context.json"
    with open(ctx_path, "w") as f:
        json.dump(context, f, indent=2)
    logger.info(f"\n✅ KoruFlux context saved → {ctx_path}")

    return records, context


if __name__ == "__main__":
    records, ctx = ingest_documents()
    print(f"\n📊 Context Summary:")
    print(f"  Documents processed : {ctx.get('source_documents', 0)}")
    print(f"  Service pillars     : {ctx.get('service_pillars', [])}")
    print(f"  Top markets         : {list(ctx.get('target_markets', {}).keys())[:6]}")
    print(f"  Core technologies   : {list(ctx.get('core_technologies', {}).keys())[:8]}")
    print(f"  Engagement types    : {len(ctx.get('engagement_types', []))}")
    print(f"  Pricing range       : {ctx['engagement_types'][0]['price']} → {ctx['engagement_types'][2]['price']}")
