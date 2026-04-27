#!/usr/bin/env python3
"""Open and fill a batch of applications without submitting.

This launches a real Google Chrome window via remote debugging, opens one tab per
job, stages upload files as Resume.pdf / Cover Letter.pdf, fills safe fields and
known application answers, then leaves the tabs open for human review/submit.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.apply.browser_apply import BrowserSession
from engine.campaign_runner import (
    AUTO_APPLY_COMPANY_BLOCKLIST,
    _is_auto_apply_target,
    persist_artifacts,
)
from engine.artifacts.generator import generate_artifacts
from storage.db import get_conn


CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
PROFILE_DIR = ROOT / "storage" / "chrome_fill_only_profile"
STAGED_DIR = ROOT / "artifacts" / "staged"

SKIP_COMPANIES = {"palantir", "mistral ai"}
SKIP_TITLE_BITS = {
    "senior",
    "staff",
    "manager",
    "director",
    "head of",
    "marketing",
    "sales",
    "accounting",
    "women",
    "afirmativa",
    "product designer",
}
PREFER_COMPANIES = {
    "cohere",
    "sierra",
    "lindy",
    "weaviate",
    "supabase",
    "langchain",
    "deepgram",
    "contentsquare",
    "railway",
    "vapi",
    "cursor",
    "anyscale",
    "hootsuite",
    "pinterest",
    "stripe",
    "cloudflare",
}


def chrome_ready(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1) as resp:
            return resp.status == 200
    except Exception:
        return False


def launch_chrome(port: int) -> None:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    if chrome_ready(port):
        return
    if not CHROME.exists():
        raise RuntimeError(f"Google Chrome not found at {CHROME}")
    subprocess.Popen(
        [
            str(CHROME),
            f"--remote-debugging-port={port}",
            f"--user-data-dir={PROFILE_DIR}",
            "--no-first-run",
            "--new-window",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(30):
        if chrome_ready(port):
            return
        time.sleep(0.5)
    raise RuntimeError(f"Chrome remote debugging did not open on port {port}")


def select_jobs(limit: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT *
        FROM jobs
        WHERE manual_only=0
          AND COALESCE(url, '') != ''
          AND status NOT IN ('applied', 'skip')
          AND portal IN ('ashby', 'lever', 'greenhouse')
          AND score >= 45
        ORDER BY score DESC, first_seen_at DESC
        LIMIT 500
        """
    ).fetchall()
    conn.close()

    candidates: list[tuple[float, dict]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        job = dict(row)
        company = (job.get("company") or "").strip().lower()
        title = (job.get("title") or "").strip().lower()
        if company in SKIP_COMPANIES or company in AUTO_APPLY_COMPANY_BLOCKLIST:
            continue
        if any(bit in title for bit in SKIP_TITLE_BITS):
            continue
        if not _is_auto_apply_target(job, auto_submit=False):
            continue
        key = (company, title, (job.get("url") or "").strip().lower())
        if key in seen:
            continue
        seen.add(key)
        boost = 0.0
        if company in PREFER_COMPANIES:
            boost += 12
        if any(bit in title for bit in ("intern", "co-op", "new grad", "junior", "early career")):
            boost += 28
        if any(bit in title for bit in ("software", "backend", "frontend", "full stack", "data", "ml", "ai", "agent", "developer", "devops", "cloud")):
            boost += 15
        loc = (job.get("location") or "").lower()
        if any(bit in loc for bit in ("canada", "remote", "toronto", "vancouver", "calgary")):
            boost += 10
        candidates.append((float(job.get("score") or 0) + boost, job))

    return [job for _, job in sorted(candidates, key=lambda item: item[0], reverse=True)[:limit]]


def artifact_map_for_job(job: dict) -> dict[str, str]:
    job_id = job["id"]
    conn = get_conn()
    rows = conn.execute("SELECT * FROM artifacts WHERE job_id=? ORDER BY created_at DESC", (job_id,)).fetchall()
    artifacts = {dict(row)["type"]: dict(row)["path"] for row in rows}
    missing = [kind for kind in ("resume_pdf", "cover_pdf") if not artifacts.get(kind) or not Path(artifacts[kind]).exists()]
    if missing:
        result = generate_artifacts(job)
        persist_artifacts(conn, job_id, result)
        conn.commit()
        rows = conn.execute("SELECT * FROM artifacts WHERE job_id=? ORDER BY created_at DESC", (job_id,)).fetchall()
        artifacts = {dict(row)["type"]: dict(row)["path"] for row in rows}
    conn.close()

    staged = STAGED_DIR / job_id
    staged.mkdir(parents=True, exist_ok=True)
    resume = staged / "Resume.pdf"
    cover = staged / "Cover Letter.pdf"
    if artifacts.get("resume_pdf") and Path(artifacts["resume_pdf"]).exists():
        shutil.copy2(artifacts["resume_pdf"], resume)
    if artifacts.get("cover_pdf") and Path(artifacts["cover_pdf"]).exists():
        shutil.copy2(artifacts["cover_pdf"], cover)
    return {
        "resume_pdf_path": str(resume) if resume.exists() else "",
        "cover_pdf_path": str(cover) if cover.exists() else "",
    }


def fill_job(context, job: dict, index: int) -> dict:
    page = context.new_page()
    session = BrowserSession(
        session_id=str(uuid.uuid4()),
        job=job,
        artifacts=artifact_map_for_job(job),
        headless=False,
        keep_open_on_blocker=True,
    )
    session.page = page
    page.on("pageerror", lambda err: session._log(f"Page error: {err}"))
    result = {
        "job_id": job["id"],
        "company": job.get("company", ""),
        "title": job.get("title", ""),
        "portal": job.get("portal", ""),
        "status": "opened",
        "filled": 0,
        "skipped": 0,
    }
    try:
        page.goto(job["url"], wait_until="domcontentloaded", timeout=45000)
        time.sleep(2)
        session._dismiss_cookie_banner()
        session.map_fields()
        fill = session.fill_all_fields_auto()
        result["filled"] = len(fill.get("filled") or [])
        result["skipped"] = len(fill.get("skipped") or [])
        if fill.get("captcha"):
            result["status"] = "captcha_open_for_user"
        elif fill.get("blocker"):
            result["status"] = f"blocked_{fill.get('blocker')}"
            result["error"] = fill.get("error", "")
        else:
            result["status"] = "filled_review_and_submit"
        page.evaluate(
            """([index, status]) => {
                document.title = `[${index}] ${status} | ${document.title}`;
            }""",
            [index, result["status"]],
        )
    except Exception as exc:
        result["status"] = "open_failed"
        result["error"] = str(exc)
        try:
            page.evaluate(
                """([index, status]) => { document.title = `[${index}] ${status}`; }""",
                [index, result["status"]],
            )
        except Exception:
            pass
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--port", type=int, default=9222)
    args = parser.parse_args()

    jobs = select_jobs(args.limit)
    if not jobs:
        raise SystemExit("No fill-only candidates found.")

    launch_chrome(args.port)
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{args.port}")
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        for idx, job in enumerate(jobs, start=1):
            print(f"[{idx}/{len(jobs)}] {job.get('company')} | {job.get('title')}", flush=True)
            results.append(fill_job(context, job, idx))
        browser.close()

    out = ROOT / "logs" / "fill_only_batch_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"results": results}, indent=2))
    print(f"\nOpened/fill attempted {len(results)} tabs. Results: {out}")
    for item in results:
        print(f"- {item['status']}: {item['company']} | {item['title']} | filled={item['filled']}")


if __name__ == "__main__":
    main()
