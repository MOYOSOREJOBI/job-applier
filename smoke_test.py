#!/usr/bin/env python3
"""
Smoke test — verifies all systems are functional before real use.
Run after setup: python3 smoke_test.py
"""
import sys
import json
import time
import subprocess
import requests
from pathlib import Path

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

PASS = []
FAIL = []

def test(name, fn):
    try:
        fn()
        PASS.append(name)
        print(f"  ✓ {name}")
    except Exception as e:
        FAIL.append(f"{name}: {e}")
        print(f"  ✗ {name}: {e}")

print("=== Smoke Test ===\n")

print("1. Database:")
def test_db():
    from storage.db import bootstrap, seed_settings, get_conn
    bootstrap()
    seed_settings()
    conn = get_conn()
    conn.execute("SELECT 1").fetchone()
    conn.close()
test("DB bootstrap", test_db)

print("\n2. Scoring engine:")
def test_scorer():
    from engine.scoring.scorer import score_job
    score, breakdown, fit_band = score_job({
        "title": "Software Engineer Intern",
        "company": "Shopify",
        "location": "Calgary, AB",
        "description_raw": "We are looking for a software engineering intern to join our backend team in Calgary. Python, AWS experience preferred. Remote-friendly.",
        "portal": "greenhouse",
        "posted_at": "2026-04-09T00:00:00Z",
    })
    assert score > 50, f"Expected score > 50, got {score}"
    assert fit_band in ("strong", "good"), f"Expected strong/good, got {fit_band}"
test("Score job", test_scorer)

print("\n3. Source adapters (connectivity):")
def test_greenhouse():
    from engine.sources.greenhouse import fetch_company_jobs
    jobs = fetch_company_jobs("shopify", "Shopify")
    # May be 0 if Shopify doesn't have active listings, that's OK
    assert isinstance(jobs, list)
test("Greenhouse API (Shopify)", test_greenhouse)

def test_lever():
    from engine.sources.lever import fetch_company_jobs
    jobs = fetch_company_jobs("shopify", "Shopify")
    assert isinstance(jobs, list)
test("Lever API (Shopify)", test_lever)

def test_ashby():
    from engine.sources.ashby import fetch_company_jobs
    jobs = fetch_company_jobs("cohere", "Cohere")
    assert isinstance(jobs, list)
test("Ashby API (Cohere)", test_ashby)

print("\n4. URL import:")
def test_url_import():
    from engine.sources.url_import import import_from_text
    job = import_from_text(
        "Software Engineer Intern at ACME Corp. Calgary, AB. Python, AWS, Docker required.",
        "Software Engineer Intern",
        "ACME Corp"
    )
    assert job["title"] == "Software Engineer Intern"
    assert job["score"] >= 0
test("Text import", test_url_import)

print("\n5. Backend import:")
def test_backend_import():
    import backend.server  # should not raise
test("Backend imports", test_backend_import)

print("\n6. LinkedIn disabled:")
def test_linkedin_disabled():
    import backend.server as server
    assert server.health()["linkedin_disabled"] is True
    assert server.get_status()["linkedin_disabled"] is True
test("LinkedIn disabled flags", test_linkedin_disabled)

print("\n7. Frontend exists:")
def test_frontend():
    assert (BASE / "frontend" / "src" / "App.jsx").exists()
    assert (BASE / "frontend" / "package.json").exists()
    assert (BASE / "frontend" / "node_modules").exists(), "Run: cd frontend && npm install"
test("Frontend files", test_frontend)

print("\n8. Artifacts directory:")
def test_artifacts_dir():
    assert (BASE / "artifacts").exists()
test("Artifacts dir", test_artifacts_dir)

print("\n9. Artifact engine config:")
def test_artifact_config():
    from dotenv import load_dotenv
    import os
    from storage.db import get_setting
    load_dotenv(BASE / ".env")
    mode = (get_setting("ARTIFACT_ENGINE_MODE", "") or os.environ.get("ARTIFACT_ENGINE_MODE", "deterministic")).strip().lower()
    assert mode in ("deterministic", "llm"), f"Unknown ARTIFACT_ENGINE_MODE: {mode}"
    if mode == "deterministic":
        return
    keys = [
        os.environ.get("CLAUDE_API_KEY", ""),
        os.environ.get("ANTHROPIC_API_KEY", ""),
        os.environ.get("OPENAI_API_KEY", ""),
        os.environ.get("GEMINI_API_KEY", ""),
        os.environ.get("GOOGLE_API_KEY", ""),
    ]
    assert any(k and not k.startswith("PASTE_YOUR_") for k in keys), "LLM mode requires CLAUDE_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY"
test("Artifact engine configured", test_artifact_config)

print("\n10. Playwright browser:")
def test_playwright():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("data:text/html,<h1>Test</h1>")
        title = page.title()
        browser.close()
test("Playwright browser launch", test_playwright)

print(f"\n=== Results: {len(PASS)} passed, {len(FAIL)} failed ===")
if FAIL:
    print("\nFailed:")
    for f in FAIL: print(f"  ✗ {f}")
    sys.exit(1)
else:
    print("All smoke tests passed.")
