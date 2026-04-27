"""
Simplify.jobs source adapter.
Pulls from Simplify's public GitHub job listings repo (SimplifyJobs/New-Grad-Positions
and SimplifyJobs/Summer2025-Internships) which are updated daily.
Also attempts the Simplify search API if accessible.

All jobs discovered here get scored and stored. ATS links are extracted and
re-classified by portal (Greenhouse/Lever/Ashby → auto-fillable).
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

from engine.scoring.scorer import score_job

TIMEOUT = 20
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-CA,en;q=0.9",
}

# Simplify's curated GitHub repos — updated daily by the community
SIMPLIFY_GITHUB_REPOS = [
    {
        "url": "https://raw.githubusercontent.com/SimplifyJobs/Summer2025-Internships/dev/README.md",
        "label": "simplify_internship_2025",
    },
    {
        "url": "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md",
        "label": "simplify_newgrad",
    },
    {
        "url": "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/README.md",
        "label": "simplify_internship_2026",
    },
]

# Simplify public search endpoint (unofficial, may change)
SIMPLIFY_SEARCH_URL = "https://simplify.jobs/api/jobs"
SIMPLIFY_SEARCH_QUERIES = [
    {"q": "software engineer intern", "location": "Canada"},
    {"q": "software developer intern", "location": "Canada"},
    {"q": "backend engineer intern", "location": "Canada"},
    {"q": "data engineer intern", "location": "Canada"},
    {"q": "machine learning intern", "location": "Canada"},
    {"q": "cloud engineer intern", "location": "Canada"},
    {"q": "devops intern", "location": "Canada"},
    {"q": "software engineer intern", "location": "Calgary"},
    {"q": "software engineer intern", "location": "Remote"},
    {"q": "data scientist intern", "location": "Canada"},
    {"q": "platform engineer intern", "location": "Canada"},
    {"q": "full stack intern", "location": "Canada"},
]

_PORTAL_DOMAINS = {
    "greenhouse.io": "greenhouse",
    "lever.co": "lever",
    "ashbyhq.com": "ashby",
    "myworkdayjobs.com": "workday",
    "jobs.workday.com": "workday",
    "amazondaftar.amazon.jobs": "amazon",
    "amazon.jobs": "amazon",
    "microsoft.com/en-us/careers": "microsoft",
    "careers.microsoft.com": "microsoft",
}


def _detect_portal(url: str) -> str:
    if not url:
        return "simplify"
    url_lower = url.lower()
    for domain, portal in _PORTAL_DOMAINS.items():
        if domain in url_lower:
            return portal
    return "simplify"


def _make_job_id(company: str, title: str, url: str) -> str:
    key = f"simplify:{company}:{title}:{url}"
    return "sy_" + hashlib.md5(key.encode()).hexdigest()[:12]


def _is_relevant(title: str) -> bool:
    title_l = title.lower()
    exclude = [
        "senior", "staff", "lead", "principal", "manager", "director",
        "architect", "phd", "lawyer", "counsel", "legal", "recruiter",
        "sales", "marketing", "social media", "product marketing",
        "human resources", "hr ", "customer success", "account executive",
    ]
    if any(e in title_l for e in exclude):
        return False
    include = [
        "intern", "co-op", "coop", "new grad", "junior", "entry",
        "software", "engineer", "developer", "data", "ml", "machine learning",
        "backend", "frontend", "full stack", "devops", "cloud", "platform",
        "infrastructure", "sre", "analyst", "quantitative", "research",
    ]
    return any(i in title_l for i in include)


def _parse_github_readme_table(text: str, source_label: str) -> list[dict]:
    """Parse markdown table rows from SimplifyJobs README files."""
    jobs: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()

    # Match table rows: | Company | Title | Location | ... | Link |
    row_pattern = re.compile(r"^\|(.+)\|$", re.MULTILINE)
    rows = row_pattern.findall(text)

    for row in rows:
        cols = [c.strip() for c in row.split("|")]
        if len(cols) < 3:
            continue
        # Skip header/separator rows
        if any(c.startswith("---") or c.lower() in ("company", "role", "title", "location", "notes", "link", "apply") for c in cols):
            continue

        # Typical format: Company | Title | Location | Notes | Apply
        company_raw = cols[0] if len(cols) > 0 else ""
        title_raw = cols[1] if len(cols) > 1 else ""
        location_raw = cols[2] if len(cols) > 2 else ""

        # Extract text from markdown links: [text](url)
        def extract_text(s: str) -> str:
            m = re.search(r"\[([^\]]+)\]", s)
            return m.group(1) if m else re.sub(r"<[^>]+>", "", s).strip()

        def extract_url(s: str) -> str:
            m = re.search(r"\]\((https?://[^\)]+)\)", s)
            return m.group(1) if m else ""

        company = extract_text(company_raw)
        title = extract_text(title_raw)
        location = extract_text(location_raw)
        apply_url = ""

        # Look for apply link in any column
        for col in cols:
            url = extract_url(col)
            if url and "simplify.jobs" not in url.lower():
                apply_url = url
                break
        if not apply_url:
            for col in cols:
                url = extract_url(col)
                if url:
                    apply_url = url
                    break

        if not company or not title or company.startswith("!") or "🔒" in title:
            continue
        if not _is_relevant(title):
            continue

        portal = _detect_portal(apply_url)
        job = {
            "id": _make_job_id(company, title, apply_url),
            "source": source_label,
            "source_type": "api",
            "portal": portal,
            "company": company,
            "title": title,
            "location": location or "Remote",
            "remote_type": "remote" if "remote" in location.lower() else "",
            "url": apply_url,
            "description_raw": f"{title} at {company}. Location: {location}.",
            "description_normalized": f"{title} at {company}. Location: {location}.",
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

    return jobs


def _fetch_github_repos() -> list[dict]:
    jobs: list[dict] = []
    for repo in SIMPLIFY_GITHUB_REPOS:
        try:
            resp = requests.get(repo["url"], headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code == 200:
                parsed = _parse_github_readme_table(resp.text, repo["label"])
                jobs.extend(parsed)
                print(f"[simplify] {repo['label']}: {len(parsed)} jobs from README", flush=True)
            else:
                print(f"[simplify] {repo['label']}: HTTP {resp.status_code}", flush=True)
            time.sleep(1)
        except Exception as exc:
            print(f"[simplify] {repo['label']}: error {exc}", flush=True)
    return jobs


def _fetch_simplify_search_api() -> list[dict]:
    """Try Simplify's unofficial search API."""
    jobs: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()
    for params in SIMPLIFY_SEARCH_QUERIES:
        try:
            resp = requests.get(
                SIMPLIFY_SEARCH_URL,
                params=params,
                headers={**HEADERS, "Referer": "https://simplify.jobs/"},
                timeout=TIMEOUT,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            items = data if isinstance(data, list) else data.get("jobs", data.get("results", []))
            for item in items:
                if not isinstance(item, dict):
                    continue
                title = item.get("title") or item.get("role") or ""
                company = item.get("company") or item.get("company_name") or ""
                location = item.get("location") or ""
                apply_url = item.get("url") or item.get("apply_url") or item.get("link") or ""
                description = item.get("description") or item.get("body") or f"{title} at {company}"
                if not title or not company:
                    continue
                if not _is_relevant(title):
                    continue
                portal = _detect_portal(apply_url)
                job = {
                    "id": _make_job_id(company, title, apply_url),
                    "source": "simplify_api",
                    "source_type": "api",
                    "portal": portal,
                    "company": company,
                    "title": title,
                    "location": location or "Remote",
                    "remote_type": "remote" if "remote" in location.lower() else "",
                    "url": apply_url,
                    "description_raw": description[:4000],
                    "description_normalized": description[:4000],
                    "posted_at": item.get("posted_at") or item.get("date") or "",
                    "first_seen_at": now,
                    "last_seen_at": now,
                    "status": "DISCOVERED",
                }
                score, breakdown, fit_band = score_job(job)
                job["score"] = score
                job["score_breakdown"] = json.dumps(breakdown)
                job["fit_band"] = fit_band
                jobs.append(job)
            time.sleep(0.5)
        except Exception as exc:
            print(f"[simplify] search API error ({params}): {exc}", flush=True)
    return jobs


def fetch_all() -> list[dict]:
    """Fetch all jobs from Simplify — GitHub README tables + search API."""
    all_jobs: list[dict] = []

    github_jobs = _fetch_github_repos()
    all_jobs.extend(github_jobs)

    api_jobs = _fetch_simplify_search_api()
    all_jobs.extend(api_jobs)

    # Deduplicate by id
    seen: set[str] = set()
    deduped: list[dict] = []
    for job in all_jobs:
        if job["id"] not in seen:
            seen.add(job["id"])
            deduped.append(job)

    print(f"[simplify] total unique jobs: {len(deduped)}", flush=True)
    return deduped
