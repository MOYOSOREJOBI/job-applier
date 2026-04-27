"""
Indeed source adapter.
Scrapes Indeed's public job listings (no login required).
Focuses on Calgary + Canada remote software/tech/data/finance roles.
All Indeed jobs are PREP_ONLY — apply manually at indeed.com or via company ATS link.
"""
import hashlib
import json
import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

from engine.scoring.scorer import score_job

TIMEOUT = 20
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-CA,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Targeted search pairs (query, location)
SEARCH_QUERIES = [
    ("software engineer intern",         "Calgary, AB"),
    ("software developer co-op",         "Calgary, AB"),
    ("data analyst intern",              "Calgary, AB"),
    ("data scientist intern",            "Calgary, AB"),
    ("machine learning intern",          "Calgary, AB"),
    ("software engineer intern",         "Canada"),
    ("software developer intern",        "Canada"),
    ("data analyst intern",              "Canada"),
    ("data scientist co-op",             "Canada"),
    ("cloud engineer intern",            "Canada"),
    ("backend developer intern",         "Canada"),
    ("full stack intern",                "Canada"),
    ("financial analyst intern",         "Calgary, AB"),
    ("digital analyst intern",           "Calgary, AB"),
    ("petroleum engineer intern",        "Calgary, AB"),
    ("technology intern",                "Calgary, AB"),
    ("devops intern",                    "Canada"),
    ("machine learning engineer intern", "Canada"),
    ("AI engineer intern",               "Canada"),
    ("software engineer intern",         "Vancouver, BC"),
]

MAX_PER_QUERY = 15


def make_job_id(indeed_id: str) -> str:
    return "indeed_" + hashlib.md5(indeed_id.encode()).hexdigest()[:12]


def _search_url(query: str, location: str, start: int = 0) -> str:
    q = requests.utils.quote(query)
    l = requests.utils.quote(location)
    return (
        f"https://ca.indeed.com/jobs?q={q}&l={l}&start={start}"
        f"&fromage=30"   # posted in last 30 days
        f"&jt=internship,parttime"
    )


def _parse_jobs(html: str, query: str, location: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    now = datetime.now(timezone.utc).isoformat()
    jobs = []

    for card in soup.find_all("div", attrs={"data-jk": True}):
        try:
            job_key = card.get("data-jk", "")
            if not job_key:
                continue

            title_el = card.find("h2", class_=re.compile(r"jobTitle|job-title", re.I))
            if not title_el:
                title_el = card.find("a", attrs={"data-jk": True})
            title = title_el.get_text(strip=True) if title_el else query

            company_el = card.find(attrs={"data-testid": "company-name"}) or card.find(class_=re.compile(r"company|employer", re.I))
            company = company_el.get_text(strip=True) if company_el else "Unknown"

            loc_el = card.find(attrs={"data-testid": "text-location"}) or card.find(class_=re.compile(r"location", re.I))
            loc = loc_el.get_text(strip=True) if loc_el else location

            salary_el = card.find(attrs={"data-testid": "attribute_snippet_testid"}) or card.find(class_=re.compile(r"salary|wage", re.I))
            salary_text = salary_el.get_text(strip=True) if salary_el else ""

            apply_url = f"https://ca.indeed.com/viewjob?jk={job_key}"
            desc = f"{title} at {company}. Location: {loc}. {salary_text}".strip()

            job_id = make_job_id(job_key)
            score, breakdown, fit_band = score_job({
                "title": title,
                "location": loc,
                "company": company,
                "description_raw": desc,
                "portal": "indeed",
                "posted_at": now,
            })

            jobs.append({
                "id": job_id,
                "source": "indeed",
                "source_type": "scrape",
                "portal": "indeed",
                "company": company,
                "title": title,
                "location": loc,
                "remote_type": "remote" if "remote" in loc.lower() else "onsite",
                "url": apply_url,
                "description_raw": desc[:8000],
                "description_normalized": desc[:4000],
                "posted_at": now,
                "first_seen_at": now,
                "last_seen_at": now,
                "score": score,
                "score_breakdown": json.dumps(breakdown),
                "fit_band": fit_band,
                "support_tier": "C",
                "apply_mode": "PREP_ONLY",
                "status": "discovered",
                "manual_only": 1,
                "restricted_reason": "Indeed listing — open job link and apply with tailored resume",
                "created_at": now,
                "updated_at": now,
            })
        except Exception:
            continue

    return jobs


def fetch_all(max_jobs: int = 300) -> list[dict]:
    all_jobs = []
    seen_ids: set[str] = set()

    for query, location in SEARCH_QUERIES:
        if len(all_jobs) >= max_jobs:
            break
        try:
            url = _search_url(query, location)
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code != 200:
                print(f"[indeed] {resp.status_code} for '{query}' in '{location}'")
                time.sleep(2)
                continue

            batch = _parse_jobs(resp.text, query, location)
            for job in batch:
                if job["id"] not in seen_ids:
                    seen_ids.add(job["id"])
                    all_jobs.append(job)

            print(f"[indeed] '{query}' / '{location}': {len(batch)} listings")
            time.sleep(1.5)  # polite delay — avoid rate limiting

        except Exception as e:
            print(f"[indeed] Error for '{query}': {e}")
            continue

    print(f"[indeed] Total fetched: {len(all_jobs)}")
    return all_jobs
