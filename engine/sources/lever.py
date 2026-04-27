"""
Lever source adapter.
Uses the official public Postings API — no authentication required.
API: GET https://api.lever.co/v0/postings/{company}?mode=json&limit=500
"""
import json
import time
import requests
from datetime import datetime, timezone
from typing import Optional

from engine.scoring.scorer import score_job

COMPANIES = [
    {"slug": "shopify",            "name": "Shopify"},
    {"slug": "wealthsimple",       "name": "Wealthsimple"},
    {"slug": "mistral",            "name": "Mistral AI"},
    {"slug": "wandb",              "name": "Weights & Biases"},
    {"slug": "palantir",           "name": "Palantir"},
    {"slug": "langchain",          "name": "LangChain"},
    {"slug": "cohere",             "name": "Cohere"},
    {"slug": "clarity-ai",         "name": "Clarity AI"},
    {"slug": "crisp",              "name": "Crisp"},
    {"slug": "gusto",              "name": "Gusto"},
    {"slug": "figma",              "name": "Figma"},
    {"slug": "robinhood",          "name": "Robinhood"},
    {"slug": "aurora-innovation",  "name": "Aurora Innovation"},
    {"slug": "scale-ai",           "name": "Scale AI"},
    {"slug": "perplexity",         "name": "Perplexity AI"},
    {"slug": "grammarly",          "name": "Grammarly"},
    {"slug": "duolingo",           "name": "Duolingo"},
    {"slug": "carta",              "name": "Carta"},
    {"slug": "mercury",            "name": "Mercury"},
    {"slug": "watershed",          "name": "Watershed"},
    {"slug": "neon",               "name": "Neon"},
    {"slug": "descript",           "name": "Descript"},
    {"slug": "verkada",            "name": "Verkada"},
    {"slug": "benchling",          "name": "Benchling"},
    # Additional Canadian tech
    {"slug": "ecobee",             "name": "ecobee"},
    {"slug": "ritual",             "name": "Ritual"},
    {"slug": "s1",                 "name": "S1"},
    {"slug": "koho",               "name": "KOHO"},
    {"slug": "borrowell",          "name": "Borrowell"},
    {"slug": "league",             "name": "League"},
    {"slug": "d1g1t",              "name": "d1g1t"},
    {"slug": "properly",           "name": "Properly"},
    {"slug": "breather",           "name": "Breather"},
    # Additional US tech
    {"slug": "discord",            "name": "Discord"},
    {"slug": "deel",               "name": "Deel"},
    {"slug": "remote",             "name": "Remote"},
    {"slug": "lattice",            "name": "Lattice"},
    {"slug": "pitch",              "name": "Pitch"},
    {"slug": "gem",                "name": "Gem"},
    {"slug": "rippling",           "name": "Rippling"},
    {"slug": "sourcegraph",        "name": "Sourcegraph"},
    {"slug": "teleport",           "name": "Teleport"},
    {"slug": "oxide",              "name": "Oxide Computer"},
    {"slug": "1password",          "name": "1Password"},
    {"slug": "domo",               "name": "Domo"},
    {"slug": "pendo",              "name": "Pendo"},
    {"slug": "gainsight",          "name": "Gainsight"},
    {"slug": "churnzero",          "name": "ChurnZero"},
    {"slug": "appcues",            "name": "Appcues"},
    {"slug": "heap",               "name": "Heap"},
    {"slug": "ironclad",           "name": "Ironclad"},
    {"slug": "docusign",           "name": "DocuSign"},
    {"slug": "evisort",            "name": "Evisort"},
    {"slug": "sprig",              "name": "Sprig"},
    {"slug": "maze",               "name": "Maze"},
    {"slug": "usertesting",        "name": "UserTesting"},
    {"slug": "hotjar",             "name": "Hotjar"},
    {"slug": "contentsquare",      "name": "Contentsquare"},
    {"slug": "glassbox",           "name": "Glassbox"},
    {"slug": "quantum-metric",     "name": "Quantum Metric"},
    # ── Canadian tech (2026 expansion) ─────────────────────────────────────
    {"slug": "absorb-lms",        "name": "Absorb LMS"},
    {"slug": "jobber",            "name": "Jobber"},
    {"slug": "trulioo",           "name": "Trulioo"},
    {"slug": "klue",              "name": "Klue"},
    {"slug": "vendasta",          "name": "Vendasta"},
    {"slug": "helcim",            "name": "Helcim"},
    {"slug": "thinkific",         "name": "Thinkific"},
    {"slug": "nuvei",             "name": "Nuvei"},
    {"slug": "coveo",             "name": "Coveo"},
    {"slug": "visier",            "name": "Visier"},
    {"slug": "snaptravel",        "name": "SnapTravel"},
    {"slug": "clearbit",          "name": "Clearbit"},
    {"slug": "tailscale",         "name": "Tailscale"},
    {"slug": "willo",             "name": "Willo Video"},
    {"slug": "certn",             "name": "Certn"},
    {"slug": "bitsight",          "name": "BitSight"},
    {"slug": "simetric",          "name": "Simetric"},
    # ── DevOps / Infra / SRE ────────────────────────────────────────────────
    {"slug": "grafana-labs",      "name": "Grafana Labs"},
    {"slug": "honeycomb",         "name": "Honeycomb"},
    {"slug": "sentry",            "name": "Sentry"},
    {"slug": "incident-io",       "name": "incident.io"},
    {"slug": "rootly",            "name": "Rootly"},
    {"slug": "firehydrant",       "name": "FireHydrant"},
    {"slug": "blameless",         "name": "Blameless"},
    {"slug": "cortex",            "name": "Cortex"},
    {"slug": "OpsLevel",          "name": "OpsLevel"},
    {"slug": "humanitec",         "name": "Humanitec"},
    {"slug": "massdriver",        "name": "Massdriver"},
    {"slug": "porter",            "name": "Porter"},
    {"slug": "qovery",            "name": "Qovery"},
    # ── AI / LLM startups ───────────────────────────────────────────────────
    {"slug": "mistralai",         "name": "Mistral AI"},
    {"slug": "together-ai",       "name": "Together AI"},
    {"slug": "replicate",         "name": "Replicate"},
    {"slug": "modal",             "name": "Modal"},
    {"slug": "e2b",               "name": "E2B"},
    {"slug": "fixie",             "name": "Fixie AI"},
    {"slug": "dust-tt",           "name": "Dust"},
    {"slug": "vellum",            "name": "Vellum AI"},
    {"slug": "baseten",           "name": "Baseten"},
    {"slug": "banana-dev",        "name": "Banana Dev"},
    {"slug": "cerebras",          "name": "Cerebras Systems"},
    {"slug": "groq",              "name": "Groq"},
    {"slug": "sambanova",         "name": "SambaNova Systems"},
    {"slug": "inflection",        "name": "Inflection AI"},
    {"slug": "adept",             "name": "Adept AI"},
    {"slug": "imbue",             "name": "Imbue"},
    {"slug": "latent-space",      "name": "Latent Space"},
    {"slug": "humanloop",         "name": "Humanloop"},
    {"slug": "brainlogic",        "name": "BrainLogic"},
    # ── Fintech / Payments ───────────────────────────────────────────────────
    {"slug": "ramp",              "name": "Ramp"},
    {"slug": "brex",              "name": "Brex"},
    {"slug": "mercury",           "name": "Mercury"},
    {"slug": "column",            "name": "Column"},
    {"slug": "unit",              "name": "Unit Finance"},
    {"slug": "lithic",            "name": "Lithic"},
    {"slug": "increase",          "name": "Increase"},
    {"slug": "modern-treasury",   "name": "Modern Treasury"},
    {"slug": "parafin",           "name": "Parafin"},
    {"slug": "treasury-prime",    "name": "Treasury Prime"},
    {"slug": "synctera",          "name": "Synctera"},
    {"slug": "stripe-capital",    "name": "Stripe Capital"},
    {"slug": "bill",              "name": "BILL"},
    {"slug": "airwallex",         "name": "Airwallex"},
    {"slug": "nium",              "name": "Nium"},
    # ── Data / Analytics ─────────────────────────────────────────────────────
    {"slug": "hex-tech",          "name": "Hex"},
    {"slug": "metabase",          "name": "Metabase"},
    {"slug": "lightdash",         "name": "Lightdash"},
    {"slug": "evidence",          "name": "Evidence"},
    {"slug": "rill-data",         "name": "Rill Data"},
    {"slug": "tinybird",          "name": "Tinybird"},
    {"slug": "clickhouse",        "name": "ClickHouse"},
    {"slug": "turntable",         "name": "Turntable"},
    {"slug": "cube",              "name": "Cube Dev"},
    {"slug": "superset",          "name": "Apache Superset"},
    # ── Sales / RevOps ───────────────────────────────────────────────────────
    {"slug": "apollo-io",         "name": "Apollo.io"},
    {"slug": "outreach-io",       "name": "Outreach"},
    {"slug": "salesloft",         "name": "Salesloft"},
    {"slug": "gong-io",           "name": "Gong"},
    {"slug": "clari",             "name": "Clari"},
    {"slug": "chorus",            "name": "Chorus.ai"},
    {"slug": "klenty",            "name": "Klenty"},
    {"slug": "instantly",         "name": "Instantly"},
    {"slug": "smartlead",         "name": "Smartlead"},
    # ── HR / Talent tech ─────────────────────────────────────────────────────
    {"slug": "greenhouse-hris",   "name": "Greenhouse HRIS"},
    {"slug": "rippling",          "name": "Rippling"},
    {"slug": "remote-com",        "name": "Remote.com"},
    {"slug": "deel",              "name": "Deel"},
    {"slug": "velocity-global",   "name": "Velocity Global"},
    {"slug": "multiplier",        "name": "Multiplier"},
    {"slug": "papaya-global",     "name": "Papaya Global"},
    {"slug": "oyster",            "name": "Oyster HR"},
    {"slug": "hibob",             "name": "HiBob"},
    {"slug": "lattice-hq",        "name": "Lattice"},
    {"slug": "leapsome",          "name": "Leapsome"},
    {"slug": "culture-amp",       "name": "Culture Amp"},
    {"slug": "15five",            "name": "15Five"},
    {"slug": "betterworks",       "name": "Betterworks"},
    # ── EdTech ──────────────────────────────────────────────────────────────
    {"slug": "coursera",          "name": "Coursera"},
    {"slug": "udemy",             "name": "Udemy"},
    {"slug": "chegg",             "name": "Chegg"},
    {"slug": "noodle",            "name": "Noodle"},
    {"slug": "age-of-learning",   "name": "Age of Learning"},
    {"slug": "curriculum-assoc",  "name": "Curriculum Associates"},
    {"slug": "instructure",       "name": "Instructure (Canvas)"},
    {"slug": "renaissance",       "name": "Renaissance Learning"},
    # ── PropTech / Real Estate ───────────────────────────────────────────────
    {"slug": "properly",          "name": "Properly"},
    {"slug": "realtor-ca",        "name": "Realtor.ca"},
    {"slug": "zolo",              "name": "Zolo"},
    {"slug": "nestready",         "name": "NestReady"},
    {"slug": "opendoor",          "name": "Opendoor"},
    {"slug": "offerpad",          "name": "Offerpad"},
    {"slug": "homepoint",         "name": "Homepoint"},
    {"slug": "orchard",           "name": "Orchard"},
    # ── Media / Creator Tech ─────────────────────────────────────────────────
    {"slug": "substack",          "name": "Substack"},
    {"slug": "beehiiv",           "name": "Beehiiv"},
    {"slug": "ghost-foundation",  "name": "Ghost"},
    {"slug": "kajabi",            "name": "Kajabi"},
    {"slug": "circle-so",         "name": "Circle"},
    {"slug": "mighty-networks",   "name": "Mighty Networks"},
    {"slug": "patreon",           "name": "Patreon"},
]

BASE_URL = "https://api.lever.co/v0/postings/{slug}"
TIMEOUT = 15


def make_job_id(slug: str, lever_id: str) -> str:
    return f"lever_{slug}_{lever_id}"


def detect_remote(title: str, location: str, desc: str) -> str:
    combined = (title + " " + location + " " + (desc or "")[:500]).lower()
    if "remote" in combined:
        return "remote"
    if "hybrid" in combined:
        return "hybrid"
    return "onsite"


def fetch_company_jobs(slug: str, company_name: str) -> list[dict]:
    url = BASE_URL.format(slug=slug)
    try:
        resp = requests.get(url, params={"mode": "json", "limit": 500}, timeout=TIMEOUT)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        items = resp.json()
        if not isinstance(items, list):
            return []
    except (requests.RequestException, json.JSONDecodeError) as e:
        print(f"[lever] {company_name}: {e}")
        return []

    jobs = []
    now = datetime.now(timezone.utc).isoformat()
    for item in items:
        lever_id = item.get("id", "")
        title = item.get("text", "")
        location = item.get("categories", {}).get("location", "Remote")
        apply_url = item.get("hostedUrl") or item.get("applyUrl") or ""
        created_ms = item.get("createdAt", 0)
        posted_at = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc).isoformat() if created_ms else now
        desc_lists = item.get("lists", [])
        desc_parts = []
        for lst in desc_lists:
            desc_parts.append(lst.get("text", ""))
            desc_parts.append(" ".join(lst.get("content", "")) if isinstance(lst.get("content"), list) else str(lst.get("content", "")))
        desc = " ".join(desc_parts)
        desc_additional = item.get("additional", "") or ""
        full_desc = (desc + " " + desc_additional)[:8000]

        job_id = make_job_id(slug, lever_id)
        score, breakdown, fit_band = score_job({
            "title": title,
            "location": location,
            "company": company_name,
            "description_raw": full_desc,
            "portal": "lever",
            "posted_at": posted_at,
        })

        job = {
            "id": job_id,
            "source": f"lever:{slug}",
            "source_type": "api",
            "portal": "lever",
            "company": company_name,
            "title": title,
            "location": location,
            "remote_type": detect_remote(title, location, full_desc),
            "url": apply_url,
            "description_raw": full_desc,
            "description_normalized": _strip_html(full_desc),
            "posted_at": posted_at,
            "first_seen_at": now,
            "last_seen_at": now,
            "score": score,
            "score_breakdown": json.dumps(breakdown),
            "fit_band": fit_band,
            "support_tier": "A",
            "apply_mode": "ASSISTED_FILL",
            "status": "discovered",
            "manual_only": 0,
            "restricted_reason": None,
            "created_at": now,
            "updated_at": now,
        }
        jobs.append(job)
    return jobs


def _strip_html(text: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:4000]


def fetch_all(company_slugs: Optional[list[dict]] = None) -> list[dict]:
    targets = company_slugs or COMPANIES
    all_jobs = []
    for company in targets:
        jobs = fetch_company_jobs(company["slug"], company["name"])
        all_jobs.extend(jobs)
        time.sleep(0.3)
    return all_jobs
