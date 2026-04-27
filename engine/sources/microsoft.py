"""
Microsoft Careers source adapter.
Uses Microsoft's public jobs search API — no authentication required.
Targets intern / co-op / new grad roles in Canada.
"""
import hashlib
import json
import time
import requests
from datetime import datetime, timezone

from engine.scoring.scorer import score_job

TIMEOUT = 20
BASE_URL = "https://jobs.careers.microsoft.com/global/en/search"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://jobs.careers.microsoft.com/",
}

SEARCH_QUERIES = [
    "software engineer intern",
    "software engineer co-op",
    "data scientist intern",
    "machine learning intern",
    "cloud engineer intern",
    "data analyst intern",
    "explore intern",
]


def make_job_id(ms_id: str) -> str:
    return "msft_" + hashlib.md5(str(ms_id).encode()).hexdigest()[:12]


def fetch_query(query: str) -> list[dict]:
    params = {
        "q": query,
        "l": "en_us",
        "pg": 1,
        "pgSz": 20,
        "o": "Relevance",
        "flt": "true",
        "lc": "Canada",  # location filter
    }
    try:
        resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            print(f"[microsoft] {resp.status_code} for '{query}'")
            return []
        data = resp.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        print(f"[microsoft] '{query}': {e}")
        return []

    now = datetime.now(timezone.utc).isoformat()
    jobs = []

    # API response shape: {"operationResult": {"result": {"jobs": [...]}}}
    items = (
        data.get("operationResult", {}).get("result", {}).get("jobs", [])
        or data.get("value", [])
        or []
    )

    for item in items:
        job_id_raw = str(item.get("jobId", "") or item.get("id", ""))
        if not job_id_raw:
            continue

        title = item.get("title", "")
        location = (
            item.get("primaryLocation", "")
            or item.get("location", "")
            or "Canada"
        )
        desc = item.get("descriptionTeaser", "") or item.get("description", "") or title
        posted_date = item.get("postingDate", now)
        apply_url = f"https://jobs.careers.microsoft.com/global/en/job/{job_id_raw}/"

        job_id = make_job_id(job_id_raw)
        score, breakdown, fit_band = score_job({
            "title": title,
            "location": location,
            "company": "Microsoft",
            "description_raw": desc,
            "portal": "microsoft",
            "posted_at": posted_date,
        })

        jobs.append({
            "id": job_id,
            "source": "microsoft",
            "source_type": "api",
            "portal": "microsoft",
            "company": "Microsoft",
            "title": title,
            "location": location,
            "remote_type": "remote" if "remote" in location.lower() else "onsite",
            "url": apply_url,
            "description_raw": desc[:8000],
            "description_normalized": desc[:4000],
            "posted_at": posted_date,
            "first_seen_at": now,
            "last_seen_at": now,
            "score": score,
            "score_breakdown": json.dumps(breakdown),
            "fit_band": fit_band,
            "support_tier": "C",
            "apply_mode": "PREP_ONLY",
            "status": "discovered",
            "manual_only": 1,
            "restricted_reason": "Microsoft custom ATS — apply at jobs.careers.microsoft.com with tailored resume",
            "created_at": now,
            "updated_at": now,
        })

    return jobs


def fetch_all() -> list[dict]:
    all_jobs = []
    seen_ids: set[str] = set()
    for query in SEARCH_QUERIES:
        batch = fetch_query(query)
        for job in batch:
            if job["id"] not in seen_ids:
                seen_ids.add(job["id"])
                all_jobs.append(job)
        time.sleep(0.8)
    print(f"[microsoft] Total fetched: {len(all_jobs)}")
    return all_jobs
