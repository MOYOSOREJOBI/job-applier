"""
Glassdoor job discovery adapter.
Scrapes public Glassdoor job search results.
All results are Tier-C / PREP_ONLY.
"""
import hashlib
import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

from engine.scoring.scorer import score_job

TIMEOUT = 20
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-CA,en;q=0.9",
}

SEARCH_QUERIES = [
    ("software engineer intern", "Canada"),
    ("backend developer intern", "Canada"),
    ("machine learning intern", "Canada"),
    ("data engineer intern", "Canada"),
    ("devops intern", "Canada"),
    ("full stack intern", "Canada"),
]


def make_job_id(company: str, title: str, url: str) -> str:
    key = f"gd:{company}:{title}:{url}"
    return "gd_" + hashlib.md5(key.encode()).hexdigest()[:12]


def _search_url(keywords: str, location: str) -> str:
    kw = keywords.replace(" ", "+")
    loc = location.replace(" ", "+")
    return (
        f"https://www.glassdoor.com/Job/{loc.lower()}-{kw.lower()}-jobs-SRCH_IL.0,6_IN3_KO7,{7+len(kw)}.htm"
        f"?fromAge=7"
    )


def _parse_page(html: str, base_url: str = "https://www.glassdoor.com") -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    for card in soup.find_all("li", class_=re.compile(r"JobsList|react-job-listing", re.I)):
        try:
            title_el = card.find(class_=re.compile(r"job-title|jobTitle", re.I)) or card.find("a", class_=re.compile(r"job|title", re.I))
            company_el = card.find(class_=re.compile(r"employer|company", re.I))
            loc_el = card.find(class_=re.compile(r"location|loc", re.I))
            link_el = card.find("a", href=re.compile(r"/job-listing|/Job/", re.I))

            title = title_el.get_text(strip=True) if title_el else ""
            company = company_el.get_text(strip=True) if company_el else ""
            location = loc_el.get_text(strip=True) if loc_el else "Canada"
            href = link_el.get("href", "") if link_el else ""
            url = href if href.startswith("http") else base_url + href

            if not title:
                continue
            jobs.append({"title": title, "company": company, "location": location, "url": url})
        except Exception:
            continue

    # Fallback: try JSON embedded in page script tags
    if not jobs:
        for script in soup.find_all("script", type="application/json"):
            try:
                data = json.loads(script.string or "{}")
                # Glassdoor sometimes embeds job data in Apollo/Redux state
                _extract_from_json(data, jobs)
            except Exception:
                continue

    return jobs


def _extract_from_json(data: dict | list, out: list, depth: int = 0):
    """Recursively look for job-like dicts in JSON blobs."""
    if depth > 8:
        return
    if isinstance(data, dict):
        title = data.get("jobTitleText") or data.get("title") or data.get("jobTitle", "")
        company = data.get("employerName") or data.get("company", "")
        url = data.get("jobViewUrl") or data.get("applyUrl") or data.get("url", "")
        location = data.get("locationName") or data.get("location", "")
        if title and company:
            out.append({"title": title, "company": company, "location": location, "url": url})
            return
        for v in data.values():
            if isinstance(v, (dict, list)):
                _extract_from_json(v, out, depth + 1)
    elif isinstance(data, list):
        for item in data:
            _extract_from_json(item, out, depth + 1)


def fetch_all(max_jobs: int = 150) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    seen: set[str] = set()
    all_jobs: list[dict] = []

    for keywords, location in SEARCH_QUERIES:
        if len(all_jobs) >= max_jobs:
            break
        try:
            url = _search_url(keywords, location)
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code != 200:
                print(f"[glassdoor] {resp.status_code} for '{keywords}'")
                continue

            raw = _parse_page(resp.text)
            print(f"[glassdoor] '{keywords}': {len(raw)} listings")

            for item in raw:
                key = f"{item['company']}:{item['title']}"
                if key in seen:
                    continue
                seen.add(key)

                desc = f"{item['title']} at {item['company']}. Location: {item['location']}."
                score, breakdown, fit_band = score_job({
                    "title": item["title"],
                    "location": item["location"],
                    "company": item["company"],
                    "description_raw": desc,
                    "portal": "glassdoor",
                    "posted_at": now,
                })

                job_id = make_job_id(item["company"], item["title"], item["url"])
                all_jobs.append({
                    "id": job_id,
                    "source": "glassdoor",
                    "source_type": "scrape",
                    "portal": "glassdoor",
                    "company": item["company"],
                    "title": item["title"],
                    "location": item["location"],
                    "remote_type": "remote" if "remote" in item["location"].lower() else "unknown",
                    "url": item["url"],
                    "description_raw": desc,
                    "description_normalized": desc,
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
                    "restricted_reason": "Glassdoor listing — open job URL to apply",
                    "created_at": now,
                    "updated_at": now,
                })
        except Exception as e:
            print(f"[glassdoor] Error for '{keywords}': {e}")

    print(f"[glassdoor] Total: {len(all_jobs)}")
    return all_jobs
