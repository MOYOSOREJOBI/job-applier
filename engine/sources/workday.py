"""
Workday source adapter.
Queries the public Workday Jobs API for each configured tenant.
No authentication required for public job boards.
API: POST https://{tenant}.wd3.myworkdayjobs.com/wday/cxs/{tenant}/{board}/jobs
"""
import hashlib
import json
import time
import requests
from datetime import datetime, timezone
from typing import Optional

from engine.scoring.scorer import score_job

TIMEOUT = 20
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}

# Search queries targeted at Moyosore's expanded role scope
SEARCH_QUERIES = [
    "software engineer intern",
    "software developer co-op",
    "data analyst intern",
    "data scientist intern",
    "machine learning intern",
    "technology intern",
    "developer student",
    "digital analyst",
    "IT intern",
]

COMPANIES = [
    # Canadian banks
    {"tenant": "rbc",        "board": "RBC_Careers",          "name": "RBC"},
    {"tenant": "td",         "board": "TD_Bank_Careers",       "name": "TD Bank"},
    {"tenant": "bmo",        "board": "External",              "name": "BMO"},
    {"tenant": "scotiabank", "board": "Global_Campus",         "name": "Scotiabank"},
    {"tenant": "cibc",       "board": "CIBC_External",         "name": "CIBC"},
    # Alberta / Canadian employers
    {"tenant": "atb",        "board": "ATB-External-Posting",  "name": "ATB Financial"},
    {"tenant": "telus",      "board": "TELUS_External",        "name": "TELUS"},
    {"tenant": "suncor",     "board": "SuncorCareers",         "name": "Suncor Energy"},
    {"tenant": "enbridge",   "board": "Enbridge",              "name": "Enbridge"},
    {"tenant": "tcenergy",   "board": "TCEnergy",              "name": "TC Energy"},
    {"tenant": "pembina",    "board": "Pembina",               "name": "Pembina Pipeline"},
    {"tenant": "atco",       "board": "ATCO",                  "name": "ATCO"},
    {"tenant": "cenovus",    "board": "CenovusCareers",        "name": "Cenovus Energy"},
    # Consulting / professional services
    {"tenant": "deloitte",   "board": "Deloitte_Canada",       "name": "Deloitte Canada"},
    {"tenant": "pwc",        "board": "Global_Campus",         "name": "PwC Canada"},
    {"tenant": "ey",         "board": "EYCareers",             "name": "EY Canada"},
    {"tenant": "kpmg",       "board": "KPMG_Careers",          "name": "KPMG Canada"},
    {"tenant": "accenture",  "board": "AccentureCanada",       "name": "Accenture Canada"},
    # Insurance / financial services
    {"tenant": "manulife",   "board": "MFCGLOBAL",             "name": "Manulife"},
    {"tenant": "sunlife",    "board": "Sunlife",               "name": "Sun Life"},
    {"tenant": "intact",     "board": "IntactFinancial",       "name": "Intact Financial"},
    # Other large Alberta / Canadian
    {"tenant": "cpkc",       "board": "CPKCCareers",           "name": "CPKC Railway"},
    {"tenant": "rogers",     "board": "RogersCareers",         "name": "Rogers"},
    {"tenant": "bell",       "board": "BellCareers",           "name": "Bell Canada"},
]


def make_job_id(tenant: str, wd_id: str) -> str:
    key = f"workday:{tenant}:{wd_id}"
    return "wd_" + hashlib.md5(key.encode()).hexdigest()[:14]


def _base_url(tenant: str, board: str) -> str:
    return f"https://{tenant}.wd3.myworkdayjobs.com/wday/cxs/{tenant}/{board}/jobs"


def _job_url(tenant: str, board: str, external_path: str) -> str:
    return f"https://{tenant}.wd3.myworkdayjobs.com/en-US/{board}{external_path}"


def fetch_company_jobs(tenant: str, board: str, company_name: str) -> list[dict]:
    url = _base_url(tenant, board)
    now = datetime.now(timezone.utc).isoformat()
    jobs = []
    seen_ids: set[str] = set()

    for query in SEARCH_QUERIES:
        payload = {"limit": 20, "offset": 0, "searchText": query}
        try:
            resp = requests.post(url, json=payload, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code in (404, 403, 401):
                break  # wrong slug — skip all queries for this company
            if resp.status_code != 200:
                continue
            data = resp.json()
        except (requests.RequestException, json.JSONDecodeError):
            continue

        postings = data.get("jobPostings") or data.get("jobs") or []
        for item in postings:
            wd_id = item.get("bulletFields", [""])[0] if item.get("bulletFields") else ""
            external_path = item.get("externalPath", "")
            if not external_path:
                continue

            job_id = make_job_id(tenant, external_path)
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            title = item.get("title", "")
            location = item.get("locationsText", "Canada")
            apply_url = _job_url(tenant, board, external_path)
            posted_raw = item.get("postedOn", "")
            desc = item.get("jobFunctionSummary", "") or title

            score, breakdown, fit_band = score_job({
                "title": title,
                "location": location,
                "company": company_name,
                "description_raw": desc,
                "portal": "workday",
                "posted_at": now,
            })

            jobs.append({
                "id": job_id,
                "source": f"workday:{tenant}",
                "source_type": "api",
                "portal": "workday",
                "company": company_name,
                "title": title,
                "location": location,
                "remote_type": "remote" if "remote" in location.lower() else "onsite",
                "url": apply_url,
                "description_raw": desc[:8000],
                "description_normalized": desc[:4000],
                "posted_at": now,
                "first_seen_at": now,
                "last_seen_at": now,
                "score": score,
                "score_breakdown": json.dumps(breakdown),
                "fit_band": fit_band,
                "support_tier": "B",
                "apply_mode": "PREP_ONLY",
                "status": "discovered",
                "manual_only": 1,
                "restricted_reason": "Workday account/email-verification flow — prep artifacts only; skip auto-apply.",
                "created_at": now,
                "updated_at": now,
            })

        time.sleep(0.4)

    return jobs


def fetch_all(companies: Optional[list[dict]] = None) -> list[dict]:
    targets = companies or COMPANIES
    all_jobs = []
    for co in targets:
        jobs = fetch_company_jobs(co["tenant"], co["board"], co["name"])
        all_jobs.extend(jobs)
        time.sleep(0.5)
    return all_jobs
