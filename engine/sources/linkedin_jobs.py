"""
LinkedIn Jobs discovery adapter.
Scrapes public LinkedIn job listings (no login required).

Detects apply type:
  easy_apply  — "Easy Apply" button (apply within LinkedIn, must do manually)
  link        — redirects to company ATS (extracted URL imported via url_import)
  manual      — standard LinkedIn apply

All LinkedIn jobs are PREP_ONLY / manual_only=1.
The system cannot automate LinkedIn apply (Terms of Service).
External ATS URLs found in LinkedIn listings ARE imported separately
and can be auto-filled via the normal Greenhouse/Lever/Ashby pipeline.
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
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Search terms that match the candidate profile
SEARCH_QUERIES = [
    ("software engineer intern", "Calgary, Alberta"),
    ("software developer intern", "Calgary, Alberta"),
    ("software engineer intern", "Canada"),
    ("software developer intern", "Canada"),
    ("backend engineer intern", "Canada"),
    ("machine learning intern", "Canada"),
    ("data engineer intern", "Canada"),
    ("cloud engineer intern", "Canada"),
    ("devops intern", "Canada"),
    ("full stack intern", "Canada"),
    ("AI engineer intern", "Canada"),
    ("software co-op", "Canada"),
    ("software co-op", "Calgary, Alberta"),
    ("python developer intern", "Canada"),
    ("AWS intern", "Canada"),
    ("infrastructure intern", "Canada"),
    ("platform engineer intern", "Canada"),
    ("software engineer new grad", "Canada"),
]

MAX_PER_QUERY = 25   # LinkedIn returns up to 25 per page


def make_job_id(linkedin_job_id: str) -> str:
    return "li_" + hashlib.md5(linkedin_job_id.encode()).hexdigest()[:12]


def _search_url(keywords: str, location: str, start: int = 0) -> str:
    kw = keywords.replace(" ", "%20")
    loc = location.replace(" ", "%20")
    return (
        f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        f"?keywords={kw}&location={loc}&start={start}&count={MAX_PER_QUERY}"
        f"&f_TPR=r2592000"  # posted in last 30 days
        f"&f_JT=I"          # internship job type filter
    )


def _detail_url(job_id: str) -> str:
    return f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"


def _parse_listings_page(html: str) -> list[dict]:
    """Parse the jobs-guest listings page into raw job dicts."""
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    for card in soup.find_all("li"):
        try:
            # Job ID
            base_card = card.find(attrs={"data-entity-urn": True})
            if not base_card:
                link_tag = card.find("a", href=re.compile(r"/jobs/view/(\d+)"))
                if not link_tag:
                    continue
                m = re.search(r"/jobs/view/(\d+)", link_tag.get("href", ""))
                raw_id = m.group(1) if m else None
            else:
                urn = base_card.get("data-entity-urn", "")
                raw_id = urn.split(":")[-1] if urn else None

            if not raw_id:
                continue

            # Title
            title_el = card.find("h3") or card.find(class_=re.compile(r"job.*title|title.*job", re.I))
            title = title_el.get_text(strip=True) if title_el else ""

            # Company
            company_el = card.find("h4") or card.find(class_=re.compile(r"company|employer", re.I))
            company = company_el.get_text(strip=True) if company_el else ""

            # Location
            loc_el = card.find(class_=re.compile(r"location|job.*location", re.I))
            location = loc_el.get_text(strip=True) if loc_el else "Canada"

            # Easy apply badge
            easy_apply = bool(card.find(string=re.compile(r"Easy Apply", re.I)))

            if not title or not raw_id:
                continue

            jobs.append({
                "raw_id": raw_id,
                "title": title,
                "company": company,
                "location": location,
                "easy_apply": easy_apply,
                "li_url": f"https://www.linkedin.com/jobs/view/{raw_id}/",
            })
        except Exception:
            continue
    return jobs


def _fetch_job_detail(raw_id: str) -> dict:
    """Fetch detail page to get description + external apply URL."""
    try:
        resp = requests.get(_detail_url(raw_id), headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            return {}
        soup = BeautifulSoup(resp.text, "html.parser")

        # Description
        desc_el = soup.find(class_=re.compile(r"description|job-description", re.I))
        desc = desc_el.get_text(separator=" ", strip=True)[:6000] if desc_el else ""

        # External apply URL (company ATS link)
        apply_url = ""
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if "apply" in href.lower() and "linkedin.com" not in href.lower():
                apply_url = href
                break
        # Also check for redirect patterns
        if not apply_url:
            for a in soup.find_all("a", href=re.compile(r"greenhouse|lever|ashby|workday|icims", re.I)):
                apply_url = a.get("href", "")
                break

        return {"description": desc, "external_apply_url": apply_url}
    except Exception:
        return {}


def fetch_all(max_jobs: int = 500) -> list[dict]:
    """Fetch LinkedIn jobs across all search queries. Returns normalized job dicts."""
    now = datetime.now(timezone.utc).isoformat()
    seen_ids: set[str] = set()
    all_jobs: list[dict] = []

    for keywords, location in SEARCH_QUERIES:
        if len(all_jobs) >= max_jobs:
            break
        try:
            url = _search_url(keywords, location)
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code != 200:
                print(f"[linkedin] {resp.status_code} for '{keywords}' — skipping")
                continue

            raw_listings = _parse_listings_page(resp.text)
            if not raw_listings:
                continue

            print(f"[linkedin] '{keywords}': found {len(raw_listings)} listings")

            for listing in raw_listings:
                raw_id = listing["raw_id"]
                if raw_id in seen_ids:
                    continue
                seen_ids.add(raw_id)

                # Fetch detail (rate-limit friendly)
                detail = _fetch_job_detail(raw_id)
                time.sleep(0.5)

                desc_raw = detail.get("description", "") or (
                    f"{listing['title']} at {listing['company']}. Location: {listing['location']}."
                )
                external_url = detail.get("external_apply_url", "")

                # Determine apply type
                if listing["easy_apply"]:
                    apply_type = "easy_apply"
                elif external_url:
                    apply_type = "link"
                else:
                    apply_type = "manual"

                score, breakdown, fit_band = score_job({
                    "title": listing["title"],
                    "location": listing["location"],
                    "company": listing["company"],
                    "description_raw": desc_raw,
                    "portal": "linkedin",
                    "posted_at": now,
                })

                job_id = make_job_id(raw_id)
                job = {
                    "id": job_id,
                    "source": "linkedin",
                    "source_type": "scrape",
                    "portal": "linkedin",
                    "company": listing["company"],
                    "title": listing["title"],
                    "location": listing["location"],
                    "remote_type": "remote" if "remote" in listing["location"].lower() else "unknown",
                    "url": listing["li_url"],
                    "description_raw": desc_raw,
                    "description_normalized": desc_raw[:4000],
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
                    "restricted_reason": (
                        "LinkedIn Easy Apply — must apply manually on linkedin.com"
                        if apply_type == "easy_apply"
                        else "LinkedIn job — apply manually or use extracted ATS link"
                    ),
                    "created_at": now,
                    "updated_at": now,
                    # Extra metadata (not in DB schema but used by notifier)
                    "linkedin_apply_type": apply_type,
                    "external_apply_url": external_url,
                }
                all_jobs.append(job)

        except Exception as e:
            print(f"[linkedin] Error for '{keywords}': {e}")
            continue

    print(f"[linkedin] Total fetched: {len(all_jobs)}")
    return all_jobs
