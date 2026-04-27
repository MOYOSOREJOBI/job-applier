"""
Ashby source adapter.
Uses the official public Job Board API — no authentication required.
API: GET https://api.ashbyhq.com/posting-api/job-board/{org}
     returns JSON { jobPostings: [...] }
"""
import json
import time
import requests
from datetime import datetime, timezone
from typing import Optional

from engine.scoring.scorer import score_job

COMPANIES = [
    {"slug": "cohere",        "name": "Cohere"},
    {"slug": "elevenlabs",    "name": "ElevenLabs"},
    {"slug": "deepgram",      "name": "Deepgram"},
    {"slug": "vapi",          "name": "Vapi"},
    {"slug": "bland",         "name": "Bland AI"},
    {"slug": "n8n",           "name": "n8n"},
    {"slug": "zapier",        "name": "Zapier"},
    {"slug": "langchain",     "name": "LangChain"},
    {"slug": "pinecone",      "name": "Pinecone"},
    {"slug": "lindy",         "name": "Lindy"},
    {"slug": "retool",        "name": "Retool"},
    {"slug": "attio",         "name": "Attio"},
    {"slug": "tinybird",      "name": "Tinybird"},
    {"slug": "travelperk",    "name": "TravelPerk"},
    {"slug": "sierra",        "name": "Sierra"},
    {"slug": "decagon",       "name": "Decagon"},
    # AI/ML infra companies
    {"slug": "anyscale",      "name": "Anyscale"},
    {"slug": "modal-labs",    "name": "Modal"},
    {"slug": "replicate",     "name": "Replicate"},
    {"slug": "cursor",        "name": "Cursor"},
    {"slug": "codeium",       "name": "Codeium"},
    {"slug": "harvey",        "name": "Harvey"},
    {"slug": "weaviate",      "name": "Weaviate"},
    {"slug": "chroma",        "name": "Chroma"},
    {"slug": "together-ai",   "name": "Together AI"},
    {"slug": "mistral",       "name": "Mistral AI"},
    {"slug": "moonhq",        "name": "Moon"},
    {"slug": "fixie-ai",      "name": "Fixie AI"},
    # Developer tools / infra
    {"slug": "supabase",      "name": "Supabase"},
    {"slug": "railway",       "name": "Railway"},
    {"slug": "fly",           "name": "Fly.io"},
    {"slug": "dagger",        "name": "Dagger"},
    {"slug": "earthly",       "name": "Earthly"},
    {"slug": "gitpod",        "name": "Gitpod"},
    {"slug": "speakeasy-api", "name": "Speakeasy"},
    {"slug": "stainless",     "name": "Stainless"},
    # Canadian companies on Ashby
    {"slug": "float",         "name": "Float"},
    {"slug": "coconut",       "name": "Coconut Software"},
    {"slug": "symend",        "name": "Symend"},
    {"slug": "no-more-ransom","name": "Folio"},
    {"slug": "financeactive", "name": "FinanceActive"},
    # ── Additional AI / LLM companies ───────────────────────────────────────
    {"slug": "anthropic",     "name": "Anthropic"},
    {"slug": "openai",        "name": "OpenAI"},
    {"slug": "perplexity",    "name": "Perplexity AI"},
    {"slug": "groq",          "name": "Groq"},
    {"slug": "cerebras",      "name": "Cerebras Systems"},
    {"slug": "inflection-ai", "name": "Inflection AI"},
    {"slug": "adept",         "name": "Adept AI"},
    {"slug": "imbue",         "name": "Imbue"},
    {"slug": "wandb",         "name": "Weights & Biases"},
    {"slug": "scale",         "name": "Scale AI"},
    {"slug": "labelbox",      "name": "Labelbox"},
    {"slug": "aquant",        "name": "Aquant"},
    {"slug": "genie-energy",  "name": "Genie Energy"},
    {"slug": "vectara",       "name": "Vectara"},
    {"slug": "qdrant",        "name": "Qdrant"},
    {"slug": "milvus",        "name": "Milvus"},
    {"slug": "zilliz",        "name": "Zilliz"},
    {"slug": "voyageai",      "name": "Voyage AI"},
    # ── Developer tools (2026 expansion) ────────────────────────────────────
    {"slug": "turso",         "name": "Turso"},
    {"slug": "neon",          "name": "Neon"},
    {"slug": "planetscale",   "name": "PlanetScale"},
    {"slug": "xata",          "name": "Xata"},
    {"slug": "prisma",        "name": "Prisma"},
    {"slug": "hasura",        "name": "Hasura"},
    {"slug": "inngest",       "name": "Inngest"},
    {"slug": "trigger-dev",   "name": "Trigger.dev"},
    {"slug": "windmill",      "name": "Windmill"},
    {"slug": "airplane",      "name": "Airplane"},
    {"slug": "resend",        "name": "Resend"},
    {"slug": "loops",         "name": "Loops"},
    {"slug": "plunk",         "name": "Plunk"},
    {"slug": "nango",         "name": "Nango"},
    {"slug": "merge-dev",     "name": "Merge.dev"},
    {"slug": "apideck",       "name": "Apideck"},
    {"slug": "codat",         "name": "Codat"},
    # ── Observability / Reliability ──────────────────────────────────────────
    {"slug": "axiom",         "name": "Axiom"},
    {"slug": "baselime",      "name": "Baselime"},
    {"slug": "highlight",     "name": "Highlight.io"},
    {"slug": "signoz",        "name": "SigNoz"},
    {"slug": "last9",         "name": "Last9"},
    {"slug": "betterstack",   "name": "Better Stack"},
    {"slug": "checkly",       "name": "Checkly"},
    # ── Fintech (emerging) ───────────────────────────────────────────────────
    {"slug": "warp-finance",  "name": "Warp"},
    {"slug": "cabal",         "name": "Cabal"},
    {"slug": "plaid",         "name": "Plaid"},
    {"slug": "mesh-connect",  "name": "Mesh Connect"},
    {"slug": "alpaca",        "name": "Alpaca"},
    {"slug": "composer",      "name": "Composer"},
    {"slug": "capitalone",    "name": "Capital One"},
    # ── Canadian banks / fintech on Ashby ────────────────────────────────────
    {"slug": "wealthsimple",  "name": "Wealthsimple"},
    {"slug": "koho",          "name": "KOHO"},
    {"slug": "borrowell",     "name": "Borrowell"},
    {"slug": "motusbank",     "name": "Motus Bank"},
    {"slug": "clearco",       "name": "Clearco"},
    {"slug": "league",        "name": "League"},
    {"slug": "dialogue",      "name": "Dialogue"},
    # ── Security ─────────────────────────────────────────────────────────────
    {"slug": "snyk",          "name": "Snyk"},
    {"slug": "tailscale",     "name": "Tailscale"},
    {"slug": "1password",     "name": "1Password"},
    {"slug": "vanta",         "name": "Vanta"},
    {"slug": "drata",         "name": "Drata"},
    {"slug": "secureframe",   "name": "Secureframe"},
    {"slug": "lacework",      "name": "Lacework"},
]

BASE_URL = "https://api.ashbyhq.com/posting-api/job-board/{org}"
TIMEOUT = 15


def make_job_id(org: str, ashby_id: str) -> str:
    return f"ashby_{org}_{ashby_id}"


def detect_remote(title: str, location: str, desc: str) -> str:
    combined = (title + " " + (location or "") + " " + (desc or "")[:500]).lower()
    if "remote" in combined:
        return "remote"
    if "hybrid" in combined:
        return "hybrid"
    return "onsite"


def fetch_company_jobs(org: str, company_name: str) -> list[dict]:
    url = BASE_URL.format(org=org)
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        print(f"[ashby] {company_name}: {e}")
        return []

    jobs = []
    now = datetime.now(timezone.utc).isoformat()
    # API returns either "jobPostings" (old) or "jobs" (new v1)
    postings = data.get("jobPostings") or data.get("jobs") or []
    for item in postings:
        ashby_id = item.get("id", "")
        title = item.get("title", "")
        location = item.get("location") or item.get("locationName") or "Remote"
        apply_url = item.get("jobUrl") or item.get("applyUrl") or ""
        posted_at = item.get("publishedAt") or item.get("publishedDate") or now
        desc_body = item.get("descriptionHtml") or item.get("descriptionPlain") or item.get("description") or ""
        dept = item.get("department") or item.get("team") or ""

        full_desc = (desc_body + " " + dept)[:8000]
        job_id = make_job_id(org, ashby_id)
        score, breakdown, fit_band = score_job({
            "title": title,
            "location": location,
            "company": company_name,
            "description_raw": full_desc,
            "portal": "ashby",
            "posted_at": posted_at,
        })

        job = {
            "id": job_id,
            "source": f"ashby:{org}",
            "source_type": "api",
            "portal": "ashby",
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
