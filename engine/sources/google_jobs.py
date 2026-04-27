"""
Google Jobs source adapter.
Scrapes Google's job search results via the /search?q=...+jobs endpoint.
Google renders job cards in structured JSON-LD inside the HTML — we parse that.
All results classified by detected ATS portal (Greenhouse/Lever/Ashby = auto-fillable).
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from engine.scoring.scorer import score_job

TIMEOUT = 25
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-CA,en;q=0.9",
}

SEARCH_QUERIES = [
    "software engineer intern Canada 2025 2026",
    "software developer intern Calgary Alberta",
    "backend engineer intern Canada remote",
    "data engineer intern Canada 2026",
    "machine learning intern Canada 2026",
    "devops engineer intern Canada remote",
    "cloud engineer intern Canada",
    "full stack developer intern Canada",
    "platform engineer intern Canada",
    "software engineering co-op Calgary",
    "software engineer new grad Canada",
    "data scientist intern Canada 2026",
    "AI engineer intern Canada",
    "SRE intern Canada remote",
    "quantitative analyst intern Canada",
    "infrastructure engineer intern Canada",
    "software engineer intern Greenhouse",
    "software engineer intern Lever Canada",
    "software developer co-op Alberta",
]

_PORTAL_PATTERNS = {
    "greenhouse": ["greenhouse.io", "boards.greenhouse.io"],
    "lever": ["jobs.lever.co", "lever.co"],
    "ashby": ["ashbyhq.com", "jobs.ashbyhq.com"],
    "workday": ["myworkdayjobs.com", "workday.com/en-us/pages/careers"],
    "amazon": ["amazon.jobs", "amazondaftar.amazon.jobs"],
    "microsoft": ["careers.microsoft.com", "microsoft.com/en-us/careers"],
    "indeed": ["indeed.com"],
    "linkedin": ["linkedin.com/jobs"],
}


def _detect_portal(url: str) -> str:
    if not url:
        return "google"
    url_l = url.lower()
    for portal, patterns in _PORTAL_PATTERNS.items():
        if any(p in url_l for p in patterns):
            return portal
    return "google"


def _make_job_id(company: str, title: str, url: str) -> str:
    key = f"gj:{company}:{title}:{url}"
    return "gj_" + hashlib.md5(key.encode()).hexdigest()[:12]


def _is_relevant(title: str) -> bool:
    t = title.lower()
    exclude = [
        "senior", "staff", "lead", "principal", "manager", "director",
        "architect", "phd", "lawyer", "legal", "recruiter", "sales",
        "marketing", "human resources", "customer success", "account executive",
    ]
    if any(e in t for e in exclude):
        return False
    include = [
        "intern", "co-op", "coop", "new grad", "junior", "entry",
        "software", "engineer", "developer", "data", "ml", "machine learning",
        "backend", "frontend", "full stack", "devops", "cloud", "platform",
        "infrastructure", "sre", "analyst", "quantitative", "research",
    ]
    return any(i in t for i in include)


def _parse_json_ld(html: str) -> list[dict]:
    """Extract JobPosting JSON-LD from Google search HTML."""
    jobs = []
    now = datetime.now(timezone.utc).isoformat()
    soup = BeautifulSoup(html, "html.parser")

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except Exception:
            continue

        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("@type") != "JobPosting":
                continue
            title = item.get("title") or ""
            company = ""
            org = item.get("hiringOrganization") or {}
            if isinstance(org, dict):
                company = org.get("name") or ""
            location_obj = item.get("jobLocation") or {}
            location = ""
            if isinstance(location_obj, dict):
                addr = location_obj.get("address") or {}
                if isinstance(addr, dict):
                    parts = [addr.get("addressLocality", ""), addr.get("addressRegion", ""), addr.get("addressCountry", "")]
                    location = ", ".join(p for p in parts if p)
            elif isinstance(location_obj, list) and location_obj:
                addr = location_obj[0].get("address") or {}
                if isinstance(addr, dict):
                    parts = [addr.get("addressLocality", ""), addr.get("addressRegion", ""), addr.get("addressCountry", "")]
                    location = ", ".join(p for p in parts if p)
            apply_url = item.get("url") or item.get("sameAs") or ""
            description = item.get("description") or ""
            posted = item.get("datePosted") or ""

            if not title or not company:
                continue
            if not _is_relevant(title):
                continue

            portal = _detect_portal(apply_url)
            if portal in ("indeed", "linkedin"):
                continue  # already covered by dedicated scrapers

            job = {
                "id": _make_job_id(company, title, apply_url),
                "source": "google_jobs",
                "source_type": "scrape",
                "portal": portal,
                "company": company,
                "title": title,
                "location": location or "Remote",
                "remote_type": "remote" if "remote" in location.lower() else "",
                "url": apply_url,
                "description_raw": re.sub(r"<[^>]+>", " ", description)[:4000],
                "description_normalized": re.sub(r"<[^>]+>", " ", description)[:4000],
                "posted_at": posted,
                "first_seen_at": now,
                "last_seen_at": now,
                "status": "DISCOVERED",
            }
            score, breakdown, fit_band = score_job(job)
            job["score"] = score
            job["score_breakdown"] = json.dumps(breakdown)
            job["fit_band"] = fit_band
            jobs.append(job)

    return jobs


def _parse_google_jobs_widget(html: str) -> list[dict]:
    """Parse job cards from Google's job search widget (div.job_seen_beacon or similar)."""
    jobs = []
    now = datetime.now(timezone.utc).isoformat()
    soup = BeautifulSoup(html, "html.parser")

    for card in soup.find_all("div", attrs={"data-hveid": True}):
        try:
            title_el = card.find(class_=re.compile(r"title|job-title", re.I))
            company_el = card.find(class_=re.compile(r"company|employer", re.I))
            loc_el = card.find(class_=re.compile(r"location|loc", re.I))
            link_el = card.find("a", href=True)
            if not title_el or not company_el:
                continue
            title = title_el.get_text(strip=True)
            company = company_el.get_text(strip=True)
            location = loc_el.get_text(strip=True) if loc_el else ""
            url = link_el["href"] if link_el else ""
            if not _is_relevant(title):
                continue
            portal = _detect_portal(url)
            job = {
                "id": _make_job_id(company, title, url),
                "source": "google_jobs",
                "source_type": "scrape",
                "portal": portal,
                "company": company,
                "title": title,
                "location": location or "Remote",
                "remote_type": "remote" if "remote" in location.lower() else "",
                "url": url,
                "description_raw": f"{title} at {company}. {location}",
                "description_normalized": f"{title} at {company}. {location}",
                "posted_at": "",
                "first_seen_at": now,
                "last_seen_at": now,
                "status": "DISCOVERED",
            }
            score, breakdown, fit_band = score_job(job)
            job["score"] = score
            job["score_breakdown"] = json.dumps(breakdown)
            job["fit_band"] = fit_band
            jobs.append(job)
        except Exception:
            continue

    return jobs


def _fetch_query(query: str) -> list[dict]:
    url = f"https://www.google.com/search?q={requests.utils.quote(query)}&ibp=htl;jobs"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            return []
        jobs = _parse_json_ld(resp.text)
        if not jobs:
            jobs = _parse_google_jobs_widget(resp.text)
        return jobs
    except Exception as exc:
        print(f"[google_jobs] query '{query}': {exc}", flush=True)
        return []


def fetch_all() -> list[dict]:
    all_jobs: list[dict] = []
    seen: set[str] = set()

    for query in SEARCH_QUERIES:
        jobs = _fetch_query(query)
        for job in jobs:
            if job["id"] not in seen:
                seen.add(job["id"])
                all_jobs.append(job)
        print(f"[google_jobs] '{query[:40]}': {len(jobs)} jobs", flush=True)
        time.sleep(2)  # respectful crawl delay

    print(f"[google_jobs] total unique: {len(all_jobs)}", flush=True)
    return all_jobs
