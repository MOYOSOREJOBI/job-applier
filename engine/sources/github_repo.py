"""
GitHub Internship Repo adapter.
Fetches the Canadian-Tech-Internships-2026 README and parses the markdown table.
This is a Tier-C source (discovery only — links to external ATS pages).
"""
import re
import json
import hashlib
import requests
from datetime import datetime, timezone

from engine.scoring.scorer import score_job

SIMPLIFY_2026_URL = "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/README.md"
SIMPLIFY_2026_MAIN_URL = "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/main/README.md"
CANADA_REPO_URL = "https://raw.githubusercontent.com/AHAbdulaziz/Canadian-Tech-Internships-2026/main/README.md"
NEGARPRH_URL = "https://raw.githubusercontent.com/negarprh/Canadian-Tech-Internships-2026/main/README.md"
PITTCSC_URL = "https://raw.githubusercontent.com/pittcsc/Summer2026-Internships/dev/README.md"
TIMEOUT = 20

# Filter out clearly non-tech roles
EXCLUDE_KEYWORDS = [
    "merchandise", "hospitality", "food", "retail", "sales manager",
    "marketing manager", "human resources", "barista", "driver",
    "janitor", "security guard", "administrative assistant",
]


def make_job_id(company: str, title: str, url: str) -> str:
    key = f"{company}:{title}:{url}"
    return "github_" + hashlib.md5(key.encode()).hexdigest()[:12]


def _fetch_readme(url: str) -> str:
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"[github_repo] failed to fetch {url}: {e}")
        return ""


def _parse_table(content: str) -> list[dict]:
    """Parse markdown table rows from README."""
    rows = []
    # Match table rows: | Company | Role | Location | Link | ... |
    pattern = re.compile(r"\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|")
    for match in pattern.finditer(content):
        cols = [c.strip() for c in match.groups()]
        if len(cols) < 4:
            continue
        company = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cols[0]).strip()
        role = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cols[1]).strip()
        location = cols[2].strip()
        link_col = cols[3].strip()

        # Extract URL from markdown link
        url_match = re.search(r"\[.*?\]\((https?://[^)]+)\)", link_col)
        if not url_match:
            url_match = re.search(r"https?://[^\s|>]+", link_col)
        apply_url = url_match.group(1) if url_match else ""

        # Skip header rows
        if company.lower() in ("company", "---", "name"):
            continue
        # Skip closed/filled
        if "🔒" in link_col or "closed" in link_col.lower():
            continue
        if not company or not role:
            continue
        # Filter non-tech
        if any(kw in role.lower() for kw in EXCLUDE_KEYWORDS):
            continue

        rows.append({
            "company": company,
            "role": role,
            "location": location,
            "apply_url": apply_url,
        })
    return rows


def _rows_to_jobs(rows: list[dict], now: str) -> list[dict]:
    jobs = []
    seen_ids = set()
    for row in rows:
        job_id = make_job_id(row["company"], row["role"], row["apply_url"])
        if job_id in seen_ids:
            continue
        seen_ids.add(job_id)
        score, breakdown, fit_band = score_job({
            "title": row["role"],
            "location": row["location"],
            "company": row["company"],
            "description_raw": f"{row['role']} at {row['company']} — {row['location']}",
            "portal": "github_repo",
            "posted_at": now,
        })
        jobs.append({
            "id": job_id,
            "source": "github_repo",
            "source_type": "repo",
            "portal": "external",
            "company": row["company"],
            "title": row["role"],
            "location": row["location"],
            "remote_type": "remote" if "remote" in row["location"].lower() else "unknown",
            "url": row["apply_url"],
            "description_raw": f"{row['role']} at {row['company']}. Location: {row['location']}. Apply: {row['apply_url']}",
            "description_normalized": f"{row['role']} at {row['company']}. Location: {row['location']}",
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
            "restricted_reason": "GitHub repo link — must open ATS page to apply; no auto-fill",
            "created_at": now,
            "updated_at": now,
        })
    return jobs


def fetch_all() -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    all_jobs = []
    seen_ids: set[str] = set()

    # Pull from all repo sources; deduplicate by job_id
    repo_sources = [
        SIMPLIFY_2026_URL,
        SIMPLIFY_2026_MAIN_URL,
        NEGARPRH_URL,
        CANADA_REPO_URL,
        PITTCSC_URL,
    ]

    for url in repo_sources:
        content = _fetch_readme(url)
        if not content:
            continue
        rows = _parse_table(content)
        batch = _rows_to_jobs(rows, now)
        for job in batch:
            if job["id"] not in seen_ids:
                seen_ids.add(job["id"])
                all_jobs.append(job)

    return all_jobs
