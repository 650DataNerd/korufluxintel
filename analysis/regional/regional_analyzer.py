"""
KoruFlux Intelligence System
==============================
analysis/regional/regional_analyzer.py

Scores each of the 8 markets independently using:
  - Region-specific market baseline intelligence
  - Live data signals from regional scrapers
  - Sentiment from regional news + social sources
  - Regulatory environment per jurisdiction

Each region gets its own:
  - Opportunity leaderboard (sector scores for THAT market)
  - Risk flags (jurisdiction-specific)
  - Regulatory signals
  - Investment signals
  - Social momentum score

Output: data/regional/{CODE}/report_{code}.json
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

BASE_DIR    = Path(__file__).parent.parent.parent
CONFIG_PATH = BASE_DIR / "config/config.yaml"


def _load_global_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


# ══════════════════════════════════════════════════════════════
# Region-specific market baselines
# Each dimension scored 0-100 for that specific jurisdiction
# Sources: World Bank, IMF, Chainalysis, DeFiLlama public data
# ══════════════════════════════════════════════════════════════

REGIONAL_BASELINES = {

    "KE": {  # Kenya / Nairobi
        "meta": {
            "name": "Kenya / Nairobi",
            "gdp_usd": "118B",
            "unbanked_pct": 33,
            "mobile_money_users": "38M+",
            "internet_penetration_pct": 40,
            "key_stat": "M-Pesa processes $314B/year",
            "key_regulator": "CMA + CBK",
            "sandbox": True,
            "data_source": "World Bank 2024, CBK Annual Report 2023"
        },
        "sectors": {
            "Payments":      {"market_size":90,"growth_rate":80,"regulatory_clarity":70,"ecosystem_maturity":80,"competitive_gap":40,"tech_readiness":85},
            "AI_Fintech":    {"market_size":75,"growth_rate":88,"regulatory_clarity":55,"ecosystem_maturity":50,"competitive_gap":80,"tech_readiness":60},
            "DeFi":          {"market_size":60,"growth_rate":82,"regulatory_clarity":45,"ecosystem_maturity":50,"competitive_gap":75,"tech_readiness":60},
            "RWA":           {"market_size":70,"growth_rate":75,"regulatory_clarity":40,"ecosystem_maturity":40,"competitive_gap":85,"tech_readiness":55},
            "Infrastructure":{"market_size":55,"growth_rate":70,"regulatory_clarity":50,"ecosystem_maturity":50,"competitive_gap":70,"tech_readiness":55},
            "AgriTech":      {"market_size":72,"growth_rate":68,"regulatory_clarity":65,"ecosystem_maturity":60,"competitive_gap":65,"tech_readiness":55},
            "Regulatory":    {"market_size":55,"growth_rate":65,"regulatory_clarity":70,"ecosystem_maturity":65,"competitive_gap":55,"tech_readiness":60},
            "NFT":           {"market_size":35,"growth_rate":50,"regulatory_clarity":30,"ecosystem_maturity":30,"competitive_gap":85,"tech_readiness":45},
            "DAO":           {"market_size":30,"growth_rate":55,"regulatory_clarity":20,"ecosystem_maturity":25,"competitive_gap":90,"tech_readiness":40},
        }
    },

    "EA": {  # East Africa
        "meta": {
            "name": "East Africa",
            "gdp_usd": "350B (bloc)",
            "unbanked_pct": 67,
            "mobile_money_users": "80M+",
            "internet_penetration_pct": 28,
            "key_stat": "67% unbanked — largest DeFi addressable market globally",
            "key_regulator": "Multiple: CBK, BoT, BoU, BNR",
            "sandbox": False,
            "data_source": "World Bank 2024, GSMA Mobile Economy 2024"
        },
        "sectors": {
            "Payments":      {"market_size":88,"growth_rate":82,"regulatory_clarity":60,"ecosystem_maturity":70,"competitive_gap":50,"tech_readiness":75},
            "AI_Fintech":    {"market_size":78,"growth_rate":90,"regulatory_clarity":50,"ecosystem_maturity":45,"competitive_gap":82,"tech_readiness":55},
            "DeFi":          {"market_size":65,"growth_rate":85,"regulatory_clarity":35,"ecosystem_maturity":40,"competitive_gap":80,"tech_readiness":55},
            "RWA":           {"market_size":72,"growth_rate":78,"regulatory_clarity":35,"ecosystem_maturity":35,"competitive_gap":88,"tech_readiness":50},
            "Infrastructure":{"market_size":50,"growth_rate":72,"regulatory_clarity":45,"ecosystem_maturity":42,"competitive_gap":75,"tech_readiness":50},
            "AgriTech":      {"market_size":82,"growth_rate":75,"regulatory_clarity":62,"ecosystem_maturity":58,"competitive_gap":70,"tech_readiness":52},
            "Regulatory":    {"market_size":48,"growth_rate":60,"regulatory_clarity":55,"ecosystem_maturity":55,"competitive_gap":60,"tech_readiness":55},
            "NFT":           {"market_size":30,"growth_rate":48,"regulatory_clarity":25,"ecosystem_maturity":25,"competitive_gap":88,"tech_readiness":40},
            "DAO":           {"market_size":28,"growth_rate":52,"regulatory_clarity":18,"ecosystem_maturity":22,"competitive_gap":92,"tech_readiness":38},
        }
    },

    "NG": {  # Nigeria
        "meta": {
            "name": "Nigeria",
            "gdp_usd": "477B",
            "unbanked_pct": 38,
            "mobile_money_users": "45M+",
            "internet_penetration_pct": 55,
            "key_stat": "Largest crypto market in Africa by volume — Chainalysis 2024",
            "key_regulator": "SEC Nigeria + CBN",
            "sandbox": True,
            "data_source": "Chainalysis 2024 Geography of Crypto, World Bank 2024"
        },
        "sectors": {
            "Payments":      {"market_size":88,"growth_rate":78,"regulatory_clarity":55,"ecosystem_maturity":72,"competitive_gap":45,"tech_readiness":78},
            "AI_Fintech":    {"market_size":80,"growth_rate":85,"regulatory_clarity":50,"ecosystem_maturity":60,"competitive_gap":72,"tech_readiness":65},
            "DeFi":          {"market_size":78,"growth_rate":88,"regulatory_clarity":42,"ecosystem_maturity":62,"competitive_gap":65,"tech_readiness":65},
            "RWA":           {"market_size":72,"growth_rate":75,"regulatory_clarity":40,"ecosystem_maturity":45,"competitive_gap":80,"tech_readiness":55},
            "Infrastructure":{"market_size":62,"growth_rate":75,"regulatory_clarity":45,"ecosystem_maturity":55,"competitive_gap":68,"tech_readiness":60},
            "AgriTech":      {"market_size":75,"growth_rate":70,"regulatory_clarity":58,"ecosystem_maturity":55,"competitive_gap":68,"tech_readiness":55},
            "Regulatory":    {"market_size":55,"growth_rate":62,"regulatory_clarity":52,"ecosystem_maturity":60,"competitive_gap":58,"tech_readiness":58},
            "NFT":           {"market_size":55,"growth_rate":65,"regulatory_clarity":32,"ecosystem_maturity":48,"competitive_gap":72,"tech_readiness":55},
            "DAO":           {"market_size":40,"growth_rate":60,"regulatory_clarity":22,"ecosystem_maturity":38,"competitive_gap":82,"tech_readiness":45},
        }
    },

    "US": {  # United States
        "meta": {
            "name": "United States",
            "gdp_usd": "27.4T",
            "unbanked_pct": 5,
            "mobile_money_users": "N/A",
            "internet_penetration_pct": 92,
            "key_stat": "Largest Web3 capital market — $2.1T+ market cap",
            "key_regulator": "SEC + CFTC",
            "sandbox": False,
            "data_source": "CoinGecko 2024, Chainalysis 2024, FDIC 2023"
        },
        "sectors": {
            "DeFi":          {"market_size":95,"growth_rate":80,"regulatory_clarity":45,"ecosystem_maturity":85,"competitive_gap":35,"tech_readiness":95},
            "Infrastructure":{"market_size":95,"growth_rate":82,"regulatory_clarity":50,"ecosystem_maturity":90,"competitive_gap":30,"tech_readiness":95},
            "AI_Fintech":    {"market_size":95,"growth_rate":92,"regulatory_clarity":58,"ecosystem_maturity":85,"competitive_gap":40,"tech_readiness":95},
            "RWA":           {"market_size":95,"growth_rate":88,"regulatory_clarity":55,"ecosystem_maturity":65,"competitive_gap":55,"tech_readiness":90},
            "Payments":      {"market_size":88,"growth_rate":70,"regulatory_clarity":60,"ecosystem_maturity":85,"competitive_gap":30,"tech_readiness":90},
            "Regulatory":    {"market_size":80,"growth_rate":75,"regulatory_clarity":50,"ecosystem_maturity":75,"competitive_gap":45,"tech_readiness":85},
            "NFT":           {"market_size":75,"growth_rate":55,"regulatory_clarity":38,"ecosystem_maturity":72,"competitive_gap":50,"tech_readiness":88},
            "DAO":           {"market_size":65,"growth_rate":65,"regulatory_clarity":30,"ecosystem_maturity":65,"competitive_gap":55,"tech_readiness":85},
            "AgriTech":      {"market_size":70,"growth_rate":60,"regulatory_clarity":62,"ecosystem_maturity":68,"competitive_gap":55,"tech_readiness":82},
        }
    },

    "EU": {  # European Union
        "meta": {
            "name": "European Union",
            "gdp_usd": "18.3T",
            "unbanked_pct": 7,
            "mobile_money_users": "N/A",
            "internet_penetration_pct": 89,
            "key_stat": "MiCA — world's first comprehensive crypto regulatory framework, June 2024",
            "key_regulator": "ESMA + ECB + National regulators",
            "sandbox": True,
            "data_source": "ESMA 2024, European Commission MiCA implementation report"
        },
        "sectors": {
            "Regulatory":    {"market_size":85,"growth_rate":82,"regulatory_clarity":85,"ecosystem_maturity":75,"competitive_gap":45,"tech_readiness":82},
            "DeFi":          {"market_size":88,"growth_rate":75,"regulatory_clarity":72,"ecosystem_maturity":75,"competitive_gap":45,"tech_readiness":85},
            "RWA":           {"market_size":90,"growth_rate":85,"regulatory_clarity":78,"ecosystem_maturity":65,"competitive_gap":55,"tech_readiness":82},
            "Infrastructure":{"market_size":85,"growth_rate":78,"regulatory_clarity":70,"ecosystem_maturity":80,"competitive_gap":40,"tech_readiness":85},
            "AI_Fintech":    {"market_size":88,"growth_rate":85,"regulatory_clarity":68,"ecosystem_maturity":78,"competitive_gap":48,"tech_readiness":85},
            "Payments":      {"market_size":85,"growth_rate":70,"regulatory_clarity":80,"ecosystem_maturity":82,"competitive_gap":38,"tech_readiness":85},
            "NFT":           {"market_size":70,"growth_rate":52,"regulatory_clarity":65,"ecosystem_maturity":65,"competitive_gap":52,"tech_readiness":80},
            "DAO":           {"market_size":62,"growth_rate":62,"regulatory_clarity":55,"ecosystem_maturity":58,"competitive_gap":58,"tech_readiness":78},
            "AgriTech":      {"market_size":72,"growth_rate":65,"regulatory_clarity":70,"ecosystem_maturity":68,"competitive_gap":55,"tech_readiness":78},
        }
    },

    "GB": {  # United Kingdom
        "meta": {
            "name": "United Kingdom",
            "gdp_usd": "3.1T",
            "unbanked_pct": 4,
            "mobile_money_users": "N/A",
            "internet_penetration_pct": 96,
            "key_stat": "FCA registered 43 crypto firms as of 2024",
            "key_regulator": "FCA",
            "sandbox": True,
            "data_source": "FCA Crypto Asset Register 2024, ONS Digital Economy 2024"
        },
        "sectors": {
            "Regulatory":    {"market_size":82,"growth_rate":80,"regulatory_clarity":80,"ecosystem_maturity":80,"competitive_gap":42,"tech_readiness":88},
            "AI_Fintech":    {"market_size":88,"growth_rate":88,"regulatory_clarity":72,"ecosystem_maturity":82,"competitive_gap":45,"tech_readiness":90},
            "DeFi":          {"market_size":82,"growth_rate":75,"regulatory_clarity":65,"ecosystem_maturity":75,"competitive_gap":48,"tech_readiness":85},
            "Payments":      {"market_size":85,"growth_rate":72,"regulatory_clarity":78,"ecosystem_maturity":85,"competitive_gap":35,"tech_readiness":88},
            "RWA":           {"market_size":85,"growth_rate":82,"regulatory_clarity":72,"ecosystem_maturity":65,"competitive_gap":55,"tech_readiness":85},
            "Infrastructure":{"market_size":80,"growth_rate":75,"regulatory_clarity":68,"ecosystem_maturity":78,"competitive_gap":45,"tech_readiness":85},
            "NFT":           {"market_size":68,"growth_rate":52,"regulatory_clarity":60,"ecosystem_maturity":68,"competitive_gap":55,"tech_readiness":82},
            "DAO":           {"market_size":60,"growth_rate":62,"regulatory_clarity":52,"ecosystem_maturity":58,"competitive_gap":58,"tech_readiness":80},
            "AgriTech":      {"market_size":65,"growth_rate":60,"regulatory_clarity":68,"ecosystem_maturity":65,"competitive_gap":58,"tech_readiness":78},
        }
    },

    "SG": {  # Singapore
        "meta": {
            "name": "Singapore",
            "gdp_usd": "501B",
            "unbanked_pct": 2,
            "mobile_money_users": "N/A",
            "internet_penetration_pct": 92,
            "key_stat": "MAS Project Guardian: $10B+ institutional RWA committed 2024",
            "key_regulator": "MAS",
            "sandbox": True,
            "data_source": "MAS Annual Report 2024, Project Guardian Progress Report 2024"
        },
        "sectors": {
            "RWA":           {"market_size":88,"growth_rate":92,"regulatory_clarity":88,"ecosystem_maturity":72,"competitive_gap":50,"tech_readiness":90},
            "DeFi":          {"market_size":85,"growth_rate":85,"regulatory_clarity":82,"ecosystem_maturity":80,"competitive_gap":45,"tech_readiness":90},
            "Infrastructure":{"market_size":82,"growth_rate":82,"regulatory_clarity":85,"ecosystem_maturity":82,"competitive_gap":42,"tech_readiness":92},
            "AI_Fintech":    {"market_size":85,"growth_rate":90,"regulatory_clarity":80,"ecosystem_maturity":80,"competitive_gap":48,"tech_readiness":92},
            "Payments":      {"market_size":80,"growth_rate":75,"regulatory_clarity":85,"ecosystem_maturity":85,"competitive_gap":38,"tech_readiness":90},
            "Regulatory":    {"market_size":78,"growth_rate":80,"regulatory_clarity":90,"ecosystem_maturity":80,"competitive_gap":42,"tech_readiness":88},
            "NFT":           {"market_size":72,"growth_rate":58,"regulatory_clarity":75,"ecosystem_maturity":70,"competitive_gap":52,"tech_readiness":85},
            "DAO":           {"market_size":65,"growth_rate":68,"regulatory_clarity":65,"ecosystem_maturity":65,"competitive_gap":55,"tech_readiness":85},
            "AgriTech":      {"market_size":60,"growth_rate":62,"regulatory_clarity":72,"ecosystem_maturity":62,"competitive_gap":58,"tech_readiness":80},
        }
    },

    "AE": {  # UAE / Dubai
        "meta": {
            "name": "UAE / Dubai",
            "gdp_usd": "509B",
            "unbanked_pct": 10,
            "mobile_money_users": "N/A",
            "internet_penetration_pct": 99,
            "key_stat": "Dubai Crypto Oasis: 1,500+ Web3 companies as of 2024",
            "key_regulator": "VARA + ADGM + DIFC",
            "sandbox": True,
            "data_source": "VARA Annual Report 2024, Dubai Future Foundation 2024"
        },
        "sectors": {
            "DeFi":          {"market_size":85,"growth_rate":88,"regulatory_clarity":82,"ecosystem_maturity":78,"competitive_gap":45,"tech_readiness":88},
            "RWA":           {"market_size":90,"growth_rate":92,"regulatory_clarity":85,"ecosystem_maturity":72,"competitive_gap":48,"tech_readiness":88},
            "Infrastructure":{"market_size":85,"growth_rate":85,"regulatory_clarity":85,"ecosystem_maturity":80,"competitive_gap":42,"tech_readiness":90},
            "AI_Fintech":    {"market_size":85,"growth_rate":90,"regulatory_clarity":78,"ecosystem_maturity":75,"competitive_gap":48,"tech_readiness":88},
            "Payments":      {"market_size":82,"growth_rate":78,"regulatory_clarity":80,"ecosystem_maturity":80,"competitive_gap":42,"tech_readiness":88},
            "Regulatory":    {"market_size":80,"growth_rate":82,"regulatory_clarity":88,"ecosystem_maturity":78,"competitive_gap":42,"tech_readiness":85},
            "NFT":           {"market_size":78,"growth_rate":65,"regulatory_clarity":78,"ecosystem_maturity":72,"competitive_gap":50,"tech_readiness":85},
            "DAO":           {"market_size":68,"growth_rate":72,"regulatory_clarity":70,"ecosystem_maturity":65,"competitive_gap":55,"tech_readiness":82},
            "AgriTech":      {"market_size":55,"growth_rate":58,"regulatory_clarity":65,"ecosystem_maturity":55,"competitive_gap":62,"tech_readiness":78},
        }
    }
}


# ══════════════════════════════════════════════════════════════
# Sentiment scoring
# ══════════════════════════════════════════════════════════════

POSITIVE_SIGNALS = [
    "launch","funding","partnership","growth","adoption","approved",
    "investment","expansion","milestone","breakthrough","license",
    "raises","secures","integrates","regulation clarity","sandbox",
    "pilot","record","signed","tokenized","deployed"
]
NEGATIVE_SIGNALS = [
    "ban","crackdown","fraud","hack","exploit","lawsuit","shutdown",
    "suspended","scam","breach","collapse","warning","probe","seized",
    "crash","penalty","violation","arrested","indicted"
]


def _score_sentiment(text: str) -> dict:
    text_l = text.lower()
    pos = sum(1 for w in POSITIVE_SIGNALS if w in text_l)
    neg = sum(1 for w in NEGATIVE_SIGNALS if w in text_l)
    total = pos + neg or 1
    score = max(-1.0, min(1.0, (pos - neg) / total))
    label = "positive" if score > 0.15 else "negative" if score < -0.15 else "neutral"
    momentum = "Growing" if score > 0.15 else "Declining" if score < -0.15 else "Stable"
    return {"score": round(score, 3), "label": label, "momentum": momentum,
            "positive_signals": pos, "negative_signals": neg}


# ══════════════════════════════════════════════════════════════
# Opportunity scoring per region
# ══════════════════════════════════════════════════════════════

WEIGHTS = {
    "market_size": 0.25,
    "growth_rate": 0.20,
    "regulatory_clarity": 0.20,
    "ecosystem_maturity": 0.15,
    "competitive_gap": 0.10,
    "tech_readiness": 0.10
}

# ──────────────────────────────────────────────────────────────
# KoruFlux Client-Relevance Weights (per koruflux.com)
# Web3 protocols, DeFi platforms, RWA projects choosing a
# jurisdiction care most about regulatory clarity and whether
# there is a competitive gap (open market) to enter.
# ──────────────────────────────────────────────────────────────
KORUFLUX_CLIENT_WEIGHTS = {
    "regulatory_clarity": 0.30,
    "competitive_gap":    0.20,
    "ecosystem_maturity": 0.20,
    "tech_readiness":     0.15,
    "growth_rate":        0.10,
    "market_size":        0.05,
}

JURISDICTION_INTEL = {
    "KE": {
        "entity_structure": "Kenyan limited company (Ltd) under the Companies Act 2015. No crypto-specific entity type yet — operate under standard fintech/tech licensing pending VASP framework.",
        "tax_exposure": "30% corporate tax. Digital Asset Tax (3% on transfer value) introduced 2023. No specific RWA tax guidance yet.",
        "compliance_framework": "CMA published a draft VASP framework in 2023; CBK oversees payment systems. Operate via CMA sandbox or partnership with licensed entity.",
        "rwa_tokenization_status": "No specific RWA framework yet. Land Registry digitisation (Ardhisasa) underway — early signal for future on-chain land title pilots.",
        "recommended_engagement": "Diagnostic Session",
        "engagement_rationale": "Regulatory framework still forming — a Diagnostic maps the CMA sandbox pathway before committing to entity setup.",
        "network_access": "KoruFlux maintains relationships with CMA sandbox liaisons, Kenyan fintech law firms, and SACCO/MFI distribution partners.",
    },
    "EA": {
        "entity_structure": "Kenya Ltd as regional holding entity, with branch registration in Tanzania, Uganda, Rwanda as needed. EAC Common Market Protocol eases cross-border operations.",
        "tax_exposure": "30% corporate tax (Kenya/Tanzania/Uganda), 28% (Rwanda). No harmonised digital asset tax — assess per-country.",
        "compliance_framework": "Fragmented — each central bank regulates independently. Rwanda's BNR is most progressive on fintech sandboxes. KIFC positioning as a future tokenisation hub.",
        "rwa_tokenization_status": "No regional framework. Rwanda's KIFC is positioning as a future tokenisation hub.",
        "recommended_engagement": "Diagnostic Session",
        "engagement_rationale": "Multi-jurisdiction complexity requires a Diagnostic to sequence which EA country to enter first.",
        "network_access": "KoruFlux's Nairobi base provides direct access to EAC policy networks and cross-border payment corridors.",
    },
    "NG": {
        "entity_structure": "Nigerian LLC under CAMA 2020. SEC Nigeria introduced VASP registration framework in 2024 — formal crypto-asset registration now possible.",
        "tax_exposure": "30% corporate tax. 2023 Finance Act: 10% capital gains tax on digital asset disposals.",
        "compliance_framework": "SEC Nigeria's 2024 rules are Africa's most developed crypto regulatory framework. Registration as Digital Asset Exchange or Issuer required for token offerings.",
        "rwa_tokenization_status": "SEC framework explicitly covers tokenised securities — Nigeria is currently the most RWA-ready jurisdiction in Sub-Saharan Africa.",
        "recommended_engagement": "Full Entry Programme",
        "engagement_rationale": "SEC framework is live — Entry Programme moves directly to entity structuring and SEC registration.",
        "network_access": "KoruFlux's partner network includes Nigerian securities lawyers and SEC-registered VASP applicants for fast-track introductions.",
    },
    "US": {
        "entity_structure": "Delaware C-Corp or LLC standard. Token issuers typically separate offshore foundation (Cayman/BVI) from US operating entity to manage securities exposure.",
        "tax_exposure": "21% federal corporate tax. IRS treats most tokens as property — capital gains apply. 0% in Wyoming/Delaware franchise structures.",
        "compliance_framework": "SEC asserts jurisdiction over Howey-test tokens; CFTC covers commodity tokens. No comprehensive federal crypto law as of 2026 — patchwork of state money-transmitter licences.",
        "rwa_tokenization_status": "Active — BlackRock BUIDL, Franklin Templeton operating tokenised US Treasuries under Reg D/S exemptions. Legally viable but requires securities counsel.",
        "recommended_engagement": "Full Entry Programme",
        "engagement_rationale": "High regulatory complexity and large market justify full entity structuring and regulator-introduction support.",
        "network_access": "KoruFlux's vetted network includes US securities law firms and compliance-as-a-service providers for SEC/CFTC navigation.",
    },
    "EU": {
        "entity_structure": "EU entity (Ireland, Malta, or Lithuania) operating under a MiCA CASP licence — passportable across all 27 member states.",
        "tax_exposure": "Corporate tax 9% (Hungary) to 25% (Germany effective). VAT generally does not apply to crypto-to-crypto exchanges per EU Court of Justice.",
        "compliance_framework": "MiCA fully applicable since December 2024 — world's first comprehensive crypto regulatory framework. CASP licence covers exchanges, custody, and most token issuance.",
        "rwa_tokenization_status": "MiCA explicitly categorises Asset-Referenced Tokens (ARTs) — RWA tokenisation has a defined legal pathway. AIFM licensing may be required for fund-like structures.",
        "recommended_engagement": "Intelligence Retainer",
        "engagement_rationale": "MiCA is stable but evolving — a retainer tracks ESMA technical standards updates through 2026-2027.",
        "network_access": "KoruFlux tracks ESMA/national regulator guidance and maintains relationships with MiCA-licensed CASP operators in Lithuania and Malta.",
    },
    "GB": {
        "entity_structure": "UK Limited Company. FCA registration required under Money Laundering Regulations for crypto-asset businesses (separate from full authorisation).",
        "tax_exposure": "25% corporate tax (main rate). HMRC treats crypto-assets as property for CGT. Detailed guidance published for DeFi staking/lending.",
        "compliance_framework": "FCA Cryptoasset Registration regime since 2020. Broader 'same risk, same outcome' framework for stablecoins and trading venues phasing in 2025-2026.",
        "rwa_tokenization_status": "FCA Digital Securities Sandbox (DSS) launched 2024 — allows regulated tokenised securities trading. UK positioning as post-Brexit RWA hub.",
        "recommended_engagement": "Full Entry Programme",
        "engagement_rationale": "FCA registration plus DSS sandbox application benefit from end-to-end entry support and regulator introductions.",
        "network_access": "KoruFlux's London network includes FCA-registered crypto-asset firms and DSS sandbox participants.",
    },
    "SG": {
        "entity_structure": "Singapore Pte Ltd. MAS Payment Services Act (PSA) Major Payment Institution (MPI) licence required for DPT services at scale.",
        "tax_exposure": "17% corporate tax. No capital gains tax — significant advantage for token issuers and treasuries.",
        "compliance_framework": "MAS PSA is mature and well-understood. MPI licence applications take 6-12 months. MAS is selective but transparent.",
        "rwa_tokenization_status": "Most advanced in Asia — MAS Project Guardian has $10B+ committed with JPMorgan, DBS, and others tokenising bonds, funds, and FX.",
        "recommended_engagement": "Full Entry Programme",
        "engagement_rationale": "MAS licensing requires structured preparation — Entry Programme sequences the MPI application and Project Guardian participation.",
        "network_access": "KoruFlux's network includes MAS-licensed MPI holders and Project Guardian ecosystem participants.",
    },
    "AE": {
        "entity_structure": "Free zone entity — ADGM or DIFC for financial services, or mainland UAE for VARA-regulated activities. ADGM/DIFC offer common-law jurisdiction and 0% corporate tax on qualifying income.",
        "tax_exposure": "0% personal income tax. 9% UAE corporate tax above AED 375,000 profit; free zone qualifying income often exempt. No capital gains tax on crypto for individuals.",
        "compliance_framework": "VARA issued the region's most comprehensive Virtual Asset framework in 2023 — covers exchanges, custody, broker-dealers, and advisory. ADGM's FSRA operates a parallel framework.",
        "rwa_tokenization_status": "Active — VARA and ADGM both have published guidance for tokenised securities and funds. Dubai Land Department has piloted real estate tokenisation since 2023.",
        "recommended_engagement": "Full Entry Programme",
        "engagement_rationale": "Free zone selection (ADGM vs DIFC vs VARA mainland) materially affects licensing scope — Entry Programme determines optimal structure before incorporation.",
        "network_access": "KoruFlux's Dubai network includes VARA-licensed VASPs, ADGM-registered fund managers, and real estate tokenisation pilot participants.",
    }
}

CLIENT_ARCHETYPES = {
    "web3_protocol": {
        "label": "Web3 Protocol",
        "description": "Infrastructure, L2s, oracles, and developer tooling expanding into new jurisdictions.",
        "priority_sectors": ["Infrastructure", "DeFi", "DAO"]
    },
    "defi_platform": {
        "label": "DeFi Platform",
        "description": "Lending, trading, and yield platforms seeking regulatory clarity for market entry.",
        "priority_sectors": ["DeFi", "Payments", "AI_Fintech"]
    },
    "rwa_project": {
        "label": "RWA Project",
        "description": "Real-world asset tokenisation projects evaluating jurisdictions for issuer registration.",
        "priority_sectors": ["RWA", "Regulatory", "Infrastructure"]
    }
}



def _compute_client_relevance_score(dims: dict) -> dict:
    score = sum(dims.get(d, 50) * w for d, w in KORUFLUX_CLIENT_WEIGHTS.items())
    score = max(0, min(100, round(score, 1)))
    if score >= 75:   tier = "STRONG FIT"
    elif score >= 55: tier = "GOOD FIT"
    elif score >= 35: tier = "POSSIBLE FIT"
    else:             tier = "WEAK FIT"
    return {"score": score, "tier": tier}


def _build_archetype_recommendations(region_code: str, scored_sectors: list) -> list:
    score_map = {s["sector"]: s for s in scored_sectors}
    jur  = JURISDICTION_INTEL.get(region_code, {})
    recs = []
    for key, archetype in CLIENT_ARCHETYPES.items():
        relevant = [score_map[s] for s in archetype["priority_sectors"] if s in score_map]
        if not relevant:
            continue
        avg_opp = round(sum(s["opportunity_score"] for s in relevant) / len(relevant), 1)
        avg_fit = round(sum(s["client_relevance"]["score"] for s in relevant) / len(relevant), 1)
        best    = max(relevant, key=lambda x: x["opportunity_score"])
        recs.append({
            "archetype": archetype["label"],
            "description": archetype["description"],
            "avg_opportunity_score": avg_opp,
            "avg_client_fit_score":  avg_fit,
            "best_sector":           best["sector"],
            "best_sector_score":     best["opportunity_score"],
            "recommended_engagement": jur.get("recommended_engagement", "Diagnostic Session"),
            "engagement_rationale":   jur.get("engagement_rationale", ""),
            "priority_sectors": [
                {"sector": s["sector"], "opportunity": s["opportunity_score"],
                 "client_fit": s["client_relevance"]["score"]}
                for s in relevant
            ]
        })
    return sorted(recs, key=lambda x: x["avg_client_fit_score"], reverse=True)


def _compute_opportunity_score(sector: str, dims: dict,
                                sentiment_score: float,
                                mention_count: int) -> dict:
    base = sum(dims.get(d, 50) * w for d, w in WEIGHTS.items())
    sentiment_adj = sentiment_score * 15
    mention_boost = min(10, math.log1p(mention_count) * 2.5)
    final = max(0, min(100, round(base + sentiment_adj + mention_boost, 1)))

    if final >= 75:   tier = "HIGH OPPORTUNITY"
    elif final >= 55: tier = "MODERATE OPPORTUNITY"
    elif final >= 35: tier = "EMERGING / MONITOR"
    else:             tier = "HIGH RISK / LOW PRIORITY"

    return {
        "sector": sector,
        "opportunity_score": final,
        "tier": tier,
        "base_score": round(base, 1),
        "sentiment_adjustment": round(sentiment_adj, 1),
        "mention_boost": round(mention_boost, 1),
        "dimensions": dims,
        "mention_count": mention_count
    }


# ══════════════════════════════════════════════════════════════
# Main regional analysis
# ══════════════════════════════════════════════════════════════

def analyze_region(region_code: str,
                   raw_records: list = None) -> dict:
    """
    Full analysis for a single region.
    raw_records: list of scraped records for this region.
    Falls back to baseline if no live data.
    """
    region_code = region_code.upper()
    baseline    = REGIONAL_BASELINES.get(region_code)
    if not baseline:
        logger.error(f"Unknown region: {region_code}")
        return {}

    meta    = baseline["meta"]
    sectors = baseline["sectors"]

    # Aggregate signals from raw records
    sector_mentions = Counter()
    sector_texts    = defaultdict(list)
    news_items      = []
    social_items    = []
    regulatory_items = []
    risk_signals    = []

    for rec in (raw_records or []):
        cat  = rec.get("category", "")
        text = rec.get("clean_data", {})

        # Pull article titles/text
        articles = []
        if "articles" in text:
            articles = text["articles"]
        elif "top_casts" in text:
            articles = [{"title": c.get("text", ""), "url": c.get("source_url", ""),
                         "source": "Farcaster — verified cast"} for c in text["top_casts"]]

        for a in articles:
            title = a.get("title", "")
            if not title:
                continue

            # Sector tagging
            for sector in sectors:
                if any(kw.lower() in title.lower() for kw in
                       [sector.lower(), sector.replace("_", " ").lower()]):
                    sector_mentions[sector] += 1
                    sector_texts[sector].append(title)

            # Categorise
            item = {
                "title": title[:200],
                "url": a.get("url", ""),
                "source": rec.get("source", ""),
                "timestamp": rec.get("timestamp", ""),
                "verified": bool(a.get("url"))
            }
            if "regulatory" in cat or "regulator" in title.lower():
                regulatory_items.append(item)
            elif cat in ("web3_social", "crypto_news", "startup_news"):
                if "Farcaster" in rec.get("source", ""):
                    social_items.append(item)
                else:
                    news_items.append(item)

            # Risk detection
            for kw in NEGATIVE_SIGNALS:
                if kw in title.lower() and len(risk_signals) < 8:
                    risk_signals.append({
                        "keyword": kw,
                        "title": title[:120],
                        "source": rec.get("source", ""),
                        "url": a.get("url", ""),
                        "severity": "HIGH" if kw in ["ban","hack","fraud","crackdown"] else "MEDIUM"
                    })

    # Score each sector
    scored_sectors = []
    for sector, dims in sectors.items():
        text_blob = " ".join(sector_texts.get(sector, []))
        sentiment = _score_sentiment(text_blob) if text_blob else {"score": 0, "label": "neutral", "momentum": "Stable"}
        score     = _compute_opportunity_score(
            sector, dims,
            sentiment["score"],
            sector_mentions.get(sector, 0)
        )
        score["sentiment"] = sentiment
        score["client_relevance"] = _compute_client_relevance_score(dims)
        scored_sectors.append(score)

    scored_sectors.sort(key=lambda x: x["opportunity_score"], reverse=True)
    client_ranked = sorted(scored_sectors, key=lambda x: x["client_relevance"]["score"], reverse=True)

    # Overall market sentiment
    all_text = " ".join(
        a.get("title", "") for rec in (raw_records or [])
        for a in rec.get("clean_data", {}).get("articles", [])
    )
    market_sentiment = _score_sentiment(all_text)

    report = {
        "region_code":  region_code,
        "region_name":  meta["name"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_points":  len(raw_records or []),
        "meta":         meta,
        "market_sentiment": market_sentiment,
        "opportunity_leaderboard": scored_sectors,
        "top_sector":   scored_sectors[0] if scored_sectors else {},
        "high_opportunity_count": len([s for s in scored_sectors if s["opportunity_score"] >= 75]),
        "news_items":   news_items[:15],
        "social_items": social_items[:10],
        "regulatory_items": regulatory_items[:8],
        "risk_signals": sorted(risk_signals, key=lambda x: x["severity"])[:6],
        "sources_used": list({r.get("source") for r in (raw_records or [])}),
        "client_relevance_ranking": [
            {"sector": s["sector"], "score": s["client_relevance"]["score"],
             "tier": s["client_relevance"]["tier"]}
            for s in client_ranked
        ],
        "jurisdiction_intelligence": JURISDICTION_INTEL.get(region_code, {}),
        "client_archetypes": _build_archetype_recommendations(region_code, scored_sectors)
    }

    # Save
    out_dir = BASE_DIR / f"data/regional/{region_code}"
    out_dir.mkdir(parents=True, exist_ok=True)
    outfile = out_dir / f"report_{region_code}.json"
    with open(outfile, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"  [{region_code}] Report saved — top sector: {scored_sectors[0]['sector']} ({scored_sectors[0]['opportunity_score']}) if scored_sectors else 'n/a'")

    return report


def analyze_all_regions(regional_raw: dict = None) -> dict:
    """
    Analyze all 8 regions.
    regional_raw: {code: [records]} from regional scraper.
    If None, uses baseline only.
    """
    all_reports = {}
    for code in REGIONAL_BASELINES:
        records = (regional_raw or {}).get(code, [])
        logger.info(f"Analyzing {code} ({len(records)} records)...")
        report = analyze_region(code, records)
        all_reports[code] = report
    logger.info(f"All {len(all_reports)} regional reports complete")
    return all_reports


def load_all_regional_reports() -> dict:
    """Load the most recent saved report for each region."""
    reports = {}
    for code in REGIONAL_BASELINES:
        path = BASE_DIR / f"data/regional/{code}/report_{code}.json"
        if path.exists():
            with open(path) as f:
                reports[code] = json.load(f)
    return reports


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(BASE_DIR))
    reports = analyze_all_regions()
    print(f"\n{'='*55}")
    print("  REGIONAL OPPORTUNITY SUMMARY")
    print(f"{'='*55}")
    for code, r in reports.items():
        top = r.get("top_sector", {})
        print(f"  {code:<4} {r['region_name']:<22} Top: {top.get('sector','—'):<16} {top.get('opportunity_score','—')}")
    print(f"{'='*55}")
