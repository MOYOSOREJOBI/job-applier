"""
Amazon Jobs source adapter.
Uses Amazon's public jobs search API — no authentication required.
Targets software intern / co-op / new grad roles in Canada.
"""
import hashlib
import json
import time
import requests
from datetime import datetime, timezone

from engine.scoring.scorer import score_job

TIMEOUT = 20
BASE_URL = "https://www.amazon.jobs/en/search.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*",
    "Referer": "https://www.amazon.jobs/",
}

SEARCH_QUERIES = [
    "software engineer intern",
    "software development engineer intern",
    "data scientist intern",
    "machine learning engineer intern",
    "software co-op",
    "data engineer intern",
    "cloud engineer intern",
    "SDE intern",
]


def make_job_id(amazon_id: str) -> str:
    return "amzn_" + hashlib.md5(amazon_id.encode()).hexdigest()[:12]


def fetch_query(query: str, country: str = "CAN") -> list[dict]:
    params = {
        "normalized_keywords": query,
        "country[]": country,
        "result_limit": 20,
        "offset": 0,
        "sort": "relevant",
    }
    try:
        resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            return []
        data = resp.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        print(f"[amazon] '{query}': {e}")
        return []

    now = datetime.now(timezone.utc).isoformat()
    jobs = []
    for item in data.get("jobs", []):
        job_id_raw = str(item.get("id_icims", "") or item.get("job_id", ""))
        if not job_id_raw:
            continue

        title = item.get("title", "")
        location = item.get("location", "Canada")
        company = item.get("company_name", "Amazon")
        apply_url = f"https://www.amazon.jobs{item.get('job_path', '')}" if item.get("job_path") else "https://www.amazon.jobs"
        desc = item.get("description_short", "") or item.get("basic_qualifications", "") or title
        posted_date = item.get("posted_date", now)

        job_id = make_job_id(job_id_raw)
        score, breakdown, fit_band = score_job({
            "title": title,
            "location": location,
            "company": company,
            "description_raw": desc,
            "portal": "amazon",
            "posted_at": posted_date,
        })

        jobs.append({
            "id": job_id,
            "source": "amazon",
            "source_type": "api",
            "portal": "amazon",
            "company": company,
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
            "restricted_reason": "Amazon custom ATS — apply at amazon.jobs with tailored resume",
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
        time.sleep(1.0)
    print(f"[amazon] Total fetched: {len(all_jobs)}")
    return all_jobs
