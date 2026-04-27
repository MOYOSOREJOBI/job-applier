"""
URL import adapter.
Fetches a single job page and extracts the description via BeautifulSoup.
Detects the portal type and sets support_tier accordingly.
"""
import hashlib
import json
import re
import requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from typing import Optional

from engine.scoring.scorer import score_job

TIMEOUT = 20

PORTAL_MAP = {
    "greenhouse.io": ("greenhouse", "A", "ASSISTED_FILL"),
    "lever.co":      ("lever",      "A", "ASSISTED_FILL"),
    "ashbyhq.com":   ("ashby",      "A", "ASSISTED_FILL"),
    "workable.com":  ("workable",   "B", "ASSISTED_FILL"),
    "myworkdayjobs": ("workday",    "B", "PREP_ONLY"),
    "icims.com":     ("icims",      "B", "ASSISTED_FILL"),
    "breezy.hr":     ("breezy",     "B", "ASSISTED_FILL"),
    "linkedin.com":  ("linkedin",   None, None),  # BLOCKED
}


def detect_portal(url: str) -> tuple[str, str, str, bool]:
    """Returns (portal, support_tier, apply_mode, is_blocked)."""
    url_lower = url.lower()
    for domain, (portal, tier, mode) in PORTAL_MAP.items():
        if domain in url_lower:
            if portal == "linkedin":
                return "linkedin", "BLOCKED", "BLOCKED", True
            return portal, tier, mode, False
    return "generic", "C", "PREP_ONLY", False


def make_job_id(url: str) -> str:
    return "url_" + hashlib.md5(url.encode()).hexdigest()[:12]


def extract_text(soup: BeautifulSoup, max_chars: int = 8000) -> str:
    """Extract visible text from page, skip nav/header/footer."""
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text)[:max_chars]


def extract_title(soup: BeautifulSoup, url: str) -> str:
    # Try common job title selectors
    for selector in ["h1", "[class*='job-title']", "[class*='position-title']", "[data-testid*='title']"]:
        el = soup.select_one(selector)
        if el and el.get_text(strip=True):
            return el.get_text(strip=True)[:200]
    # Fall back to page title
    if soup.title:
        return soup.title.string or "Unknown Role"
    return "Unknown Role"


def extract_company(soup: BeautifulSoup, url: str) -> str:
    for selector in ["[class*='company']", "[class*='employer']", "[data-company]"]:
        el = soup.select_one(selector)
        if el:
            return el.get_text(strip=True)[:100]
    # Try meta
    meta = soup.find("meta", attrs={"name": "author"})
    if meta:
        return meta.get("content", "")[:100]
    return ""


def import_from_url(url: str) -> Optional[dict]:
    """Fetch a job URL, extract info, score it, return normalized job dict."""
    portal, tier, apply_mode, is_blocked = detect_portal(url)

    if is_blocked:
        return {
            "error": True,
            "reason": "LinkedIn is not supported. This system does not automate LinkedIn. Please apply manually.",
            "url": url,
        }

    now = datetime.now(timezone.utc).isoformat()
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
        html = resp.text
    except requests.RequestException as e:
        return {"error": True, "reason": str(e), "url": url}

    soup = BeautifulSoup(html, "html.parser")
    title = extract_title(soup, url)
    company = extract_company(soup, url)
    raw_text = extract_text(soup)
    location = _extract_location(soup, raw_text)

    job_id = make_job_id(url)
    score, breakdown, fit_band = score_job({
        "title": title,
        "location": location,
        "company": company,
        "description_raw": raw_text,
        "portal": portal,
        "posted_at": now,
    })

    manual_only = 1 if apply_mode in (None, "PREP_ONLY", "BLOCKED") else 0
    restricted_reason = None
    if portal == "workday":
        restricted_reason = "Workday account/email-verification flow — prep artifacts only; skip auto-apply."
    elif manual_only:
        restricted_reason = "Portal is prep-only for automation."

    return {
        "id": job_id,
        "source": "url_import",
        "source_type": "url",
        "portal": portal,
        "company": company,
        "title": title,
        "location": location,
        "remote_type": "remote" if "remote" in raw_text[:1000].lower() else "unknown",
        "url": url,
        "description_raw": raw_text,
        "description_normalized": raw_text[:4000],
        "posted_at": now,
        "first_seen_at": now,
        "last_seen_at": now,
        "score": score,
        "score_breakdown": json.dumps(breakdown),
        "fit_band": fit_band,
        "support_tier": tier,
        "apply_mode": apply_mode,
        "status": "discovered",
        "manual_only": manual_only,
        "restricted_reason": restricted_reason,
        "created_at": now,
        "updated_at": now,
    }


def import_from_text(text: str, title_hint: str = "", company_hint: str = "") -> dict:
    """Import a pasted job description as a new job."""
    now = datetime.now(timezone.utc).isoformat()
    job_id = "text_" + hashlib.md5(text.encode()).hexdigest()[:12]
    title = title_hint or _extract_title_from_text(text)
    company = company_hint or ""
    location = _extract_location_from_text(text)

    score, breakdown, fit_band = score_job({
        "title": title,
        "location": location,
        "company": company,
        "description_raw": text,
        "portal": "pasted",
        "posted_at": now,
    })

    return {
        "id": job_id,
        "source": "text_import",
        "source_type": "text",
        "portal": "pasted",
        "company": company,
        "title": title,
        "location": location,
        "remote_type": "remote" if "remote" in text.lower() else "unknown",
        "url": "",
        "description_raw": text[:8000],
        "description_normalized": text[:4000],
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
        "restricted_reason": "Text import — no URL to open for assisted apply",
        "created_at": now,
        "updated_at": now,
    }


def _extract_location(soup: BeautifulSoup, text: str) -> str:
    for selector in ["[class*='location']", "[data-location]", "[class*='office']"]:
        el = soup.select_one(selector)
        if el:
            return el.get_text(strip=True)[:100]
    return _extract_location_from_text(text)


def _extract_location_from_text(text: str) -> str:
    patterns = [
        r"Location[:\s]+([^\n]+)",
        r"(Remote|Calgary|Vancouver|Toronto|Ottawa|Montreal|Alberta|Canada)",
    ]
    for pat in patterns:
        m = re.search(pat, text[:2000], re.IGNORECASE)
        if m:
            return m.group(1).strip()[:100]
    return "Unknown"


def _extract_title_from_text(text: str) -> str:
    first_line = text.strip().split("\n")[0][:200]
    return first_line if first_line else "Imported Role"
