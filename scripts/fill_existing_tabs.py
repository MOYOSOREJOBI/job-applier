#!/usr/bin/env python3
"""Refill already-open Chrome application tabs without submitting."""

from __future__ import annotations

import json
import re
import sys
import time
import uuid
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from engine.apply.browser_apply import BrowserSession
from fill_only_batch import artifact_map_for_job, launch_chrome
from storage.db import get_conn


RESULTS_PATH = ROOT / "logs" / "fill_only_batch_results.json"


def load_jobs_by_index() -> dict[int, dict]:
    payload = json.loads(RESULTS_PATH.read_text())
    job_ids = [item["job_id"] for item in payload.get("results", [])]
    conn = get_conn()
    placeholders = ",".join("?" * len(job_ids))
    rows = conn.execute(f"SELECT * FROM jobs WHERE id IN ({placeholders})", job_ids).fetchall()
    conn.close()
    by_id = {row["id"]: dict(row) for row in rows}
    return {idx: by_id[item["job_id"]] for idx, item in enumerate(payload.get("results", []), start=1) if item["job_id"] in by_id}


def page_index(page) -> int | None:
    try:
        title = page.title() or ""
        match = re.match(r"\[(\d+)\]", title)
        if match:
            return int(match.group(1))
    except Exception:
        pass
    return None


def main() -> None:
    jobs_by_index = load_jobs_by_index()
    launch_chrome(9222)
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
        pages = []
        for context in browser.contexts:
            pages.extend(context.pages)
        for page in pages:
            idx = page_index(page)
            if not idx or idx not in jobs_by_index:
                continue
            job = jobs_by_index[idx]
            session = BrowserSession(
                session_id=str(uuid.uuid4()),
                job=job,
                artifacts=artifact_map_for_job(job),
                headless=False,
                keep_open_on_blocker=True,
            )
            session.page = page
            print(f"[{idx}] filling existing tab: {job.get('company')} | {job.get('title')}", flush=True)
            item = {
                "index": idx,
                "job_id": job["id"],
                "company": job.get("company", ""),
                "title": job.get("title", ""),
                "status": "unknown",
                "filled": 0,
            }
            try:
                captcha = session.detect_captcha(notify=False)
                if captcha.get("detected"):
                    item["status"] = "captcha_still_blocking"
                    results.append(item)
                    continue
                session.map_fields()
                fill = session.fill_all_fields_auto()
                item["filled"] = len(fill.get("filled") or [])
                if fill.get("captcha"):
                    item["status"] = "captcha_still_blocking"
                elif fill.get("blocker"):
                    item["status"] = f"blocked_{fill.get('blocker')}"
                    item["error"] = fill.get("error", "")
                else:
                    item["status"] = "filled_review_and_submit"
                page.evaluate(
                    """([index, status]) => { document.title = `[${index}] ${status} | ${document.title.replace(/^\\[\\d+\\]\\s+[^|]+\\|\\s*/, '')}`; }""",
                    [idx, item["status"]],
                )
                time.sleep(0.5)
            except Exception as exc:
                item["status"] = "fill_failed"
                item["error"] = str(exc)
            results.append(item)
        browser.close()
    out = ROOT / "logs" / "fill_existing_tabs_results.json"
    out.write_text(json.dumps({"results": results}, indent=2))
    print(f"Results: {out}")
    for item in results:
        print(f"- [{item['index']}] {item['status']}: {item['company']} | {item['title']} | filled={item['filled']}")


if __name__ == "__main__":
    main()
