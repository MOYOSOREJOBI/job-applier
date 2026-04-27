"""
Browser apply engine.
Supports both assisted (supervised) and fully automated (headless, no confirmation) apply modes.

PORTAL SUPPORT:
  Auto-safe — Lever, Ashby, and simple direct forms after viability checks
  Assisted — Greenhouse, Workday/account-first portals, and custom portals
  Blocked — LinkedIn and any portal with CAPTCHA/login/unknown required fields

AUTO-APPLY MODE (auto_apply_full):
  - Runs headless
  - Fills all field types: text, email, tel, url, select, radio, checkbox, file
  - Handles multi-page forms (clicks Next/Continue automatically)
  - Detects CAPTCHA and pauses queue, notifies UI
  - Submits without a user confirmation gate only after policy + dry-parse pass
"""
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

from engine.apply.answer_pack import SENSITIVE_KEYS, answer_for_label, normalize_label
from engine.apply.eligibility import explain_auto_apply_eligibility
from engine.apply.portal_policy import calculate_viability, classify_portal
from engine.apply.submit_policy import can_submit_automatically
from engine.artifacts.local_engine import answer_application_question

BASE_DIR = Path(__file__).parent.parent.parent
SCREENSHOTS_DIR = BASE_DIR / "logs" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
UNKNOWN_QUESTIONS_PATH = DATA_DIR / "user_questions_needed.json"

CAPTCHA_INDICATORS = [
    # Visible challenge text (not script references)
    "are you a robot",
    "verify you are human",
    "i am not a robot",
    "prove you're human",
    "human verification",
    "security check — cloudflare",
    "enable javascript and cookies to continue",
    "checking if the site connection is secure",
    "please verify you are a human",
    "just a moment",  # Cloudflare challenge page title
]

# Selectors for captcha widgets (some are invisible but still intercept pointer events)
CAPTCHA_SELECTORS = [
    "iframe[src*='recaptcha']",
    "iframe[src*='hcaptcha']",
    "iframe[src*='newassets.hcaptcha.com']",
    "iframe[src*='turnstile']",
    ".g-recaptcha",
    ".h-captcha",
    "[data-sitekey]",
    "#h-captcha",
    "#cf-challenge-running",
    "#challenge-form",
    ".cf-challenge",
]

SUBMISSION_CONFIRMATION_TEXT = [
    "application submitted",
    "your application has been submitted",
    "successfully submitted",
    "application received",
    "we have received your application",
    "thanks for applying",
    "thank you for applying",
    "thank you for your application",
    "we'll be in touch",
]

# Profile data for form filling
PROFILE = {
    "firstName": "Moyosore",
    "lastName": "Ogunjobi",
    "fullName": "Moyosore Ogunjobi",
    "email": "moyosorejobi@gmail.com",
    "phone": "825-736-5656",
    "phone_digits": "8257365656",
    "city": "Calgary",
    "province": "Alberta",
    "country": "Canada",
    "linkedin": "linkedin.com/in/moyosore-ogunjobi-b187b8205",
    "github": "github.com/MOYOSOREJOBI",
    "portfolio": "moyosore.dev",
    "university": "University of Calgary",
    "degree": "BSc Software Engineering",
    "gpa": "3.45",
    "graduation_year": "2027",
}

# Session state — in-memory per run (not persisted to DB)
_active_sessions: dict[str, dict] = {}


class BrowserSession:
    """Represents one supervised apply session."""

    def __init__(self, session_id: str, job: dict, artifacts: dict, headless: bool = False, keep_open_on_blocker: bool = False):
        self.session_id = session_id
        self.job = job
        self.artifacts = artifacts
        self.headless = headless
        self.keep_open_on_blocker = keep_open_on_blocker
        self.browser = None
        self.page = None
        self.log: list[str] = []
        self.field_map: Optional[list[dict]] = None
        self.state = "init"  # init → open → mapped → filling → review → submitted | failed
        self.last_screenshot_path = ""

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {msg}"
        self.log.append(entry)
        print(f"[apply:{self.session_id[:8]}] {msg}")

    def _scopes(self):
        if not self.page:
            return []
        scopes = [self.page]
        try:
            scopes.extend(frame for frame in self.page.frames if frame is not self.page.main_frame)
        except Exception:
            pass
        return scopes

    def _scope_for_field(self, field: dict):
        scopes = self._scopes()
        idx = int(field.get("frame_index") or 0)
        return scopes[idx] if 0 <= idx < len(scopes) else self.page

    def start(self) -> dict:
        """Open browser and navigate to job URL."""
        import asyncio
        # Playwright sync API requires no running event loop in this thread.
        # FastAPI worker threads inherit the main loop reference; reset it.
        try:
            asyncio.set_event_loop(asyncio.new_event_loop())
        except Exception:
            pass
        from playwright.sync_api import sync_playwright
        url = self.job.get("url", "")
        portal = self.job.get("portal", "generic")

        if not url:
            return {"ok": False, "error": "No URL for this job. Add a job URL to use ASSIST APPLY."}
        if "linkedin.com" in url.lower():
            return {"ok": False, "error": "LinkedIn is not supported. This system does not automate LinkedIn. Please apply manually via linkedin.com."}

        self._log(f"Opening browser for: {self.job.get('title')} @ {self.job.get('company')}")
        self._log(f"URL: {url}")
        self._log(f"Portal: {portal} — support tier: {self.job.get('support_tier', 'C')}")

        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(headless=self.headless, slow_mo=300)
        domain = self._session_domain()
        user_data_dir = None
        ctx = None
        if domain and ("workday" in domain or "myworkdayjobs" in domain):
            user_data_dir = BASE_DIR / "storage" / "browser_profiles" / domain.replace(":", "_")
            user_data_dir.mkdir(parents=True, exist_ok=True)
        if user_data_dir:
            try:
                # Close the plain browser and use a persistent context so a
                # human Workday login can be reused for that exact tenant.
                self.browser.close()
                self.browser = None
                ctx = self._pw.chromium.launch_persistent_context(
                    user_data_dir=str(user_data_dir),
                    headless=self.headless,
                    slow_mo=300,
                    viewport={"width": 1280, "height": 900},
                )
                self.browser = ctx
            except Exception as e:
                self._log(f"Persistent Workday profile unavailable: {e}")
        if ctx is None:
            ctx = self.browser.new_context(viewport={"width": 1280, "height": 900})
        self.page = ctx.new_page()
        self.page.on("pageerror", lambda e: self._log(f"Page error: {e}"))

        try:
            # Use networkidle for SPAs (Workday, Greenhouse) so JS renders fully
            wait_condition = "networkidle" if any(x in url.lower() for x in [
                "workday", "greenhouse", "lever", "ashby", "icims", "smartrecruiters"
            ]) else "domcontentloaded"
            self.page.goto(url, wait_until=wait_condition, timeout=45000)
            wait_secs = 4 if "workday" in url.lower() else 2
            time.sleep(wait_secs)
            self._dismiss_cookie_banner()
            self.state = "open"
            self._log("Page loaded.")
        except Exception as e:
            self._screenshot("open_failed")
            return {"ok": False, "error": f"Failed to load page: {e}"}

        return {"ok": True, "session_id": self.session_id, "state": self.state}

    def _session_domain(self) -> str:
        try:
            from urllib.parse import urlparse
            return urlparse(self.job.get("url", "")).netloc.lower().removeprefix("www.")
        except Exception:
            return ""

    def _blocked_result(self, blocker: str, error: str, **extra) -> dict:
        if blocker == "unknown_required_field":
            self._record_unknown_questions(extra.get("unknown_required_fields") or [], error)
        if not self.keep_open_on_blocker:
            self.close()
        else:
            self.state = f"assisted_{blocker}"
            self._screenshot(f"blocked_{blocker}")
        return {"ok": False, "captcha": blocker == "captcha", "blocker": blocker, "error": error, "session_id": self.session_id, **extra}

    def _policy_artifacts(self) -> dict:
        return {
            "resume_pdf": self.artifacts.get("resume_pdf") or self.artifacts.get("resume_pdf_path", ""),
            "cover_pdf": self.artifacts.get("cover_pdf") or self.artifacts.get("cover_pdf_path", ""),
            "answer_pack": self.artifacts.get("answer_pack") or self.artifacts.get("answer_pack_path", ""),
        }

    def _policy_answers(self) -> dict:
        answer_path = self._policy_artifacts().get("answer_pack", "")
        if not answer_path or not Path(answer_path).exists():
            return {}
        try:
            return json.loads(Path(answer_path).read_text())
        except Exception:
            return {}

    def _policy_domain_memory(self) -> dict:
        try:
            from engine.apply.portal_policy import job_domain
            from storage.db import get_conn
            domain = job_domain(self.job)
            if not domain:
                return {}
            conn = get_conn()
            row = conn.execute("SELECT * FROM domain_memory WHERE domain=?", (domain,)).fetchone()
            conn.close()
            return dict(row) if row else {}
        except Exception:
            return {}

    def _page_state_for_policy(self, blocker: str | None = None, unknown_required: list[str] | None = None) -> dict:
        captcha = {"detected": False}
        try:
            captcha = self.detect_captcha(notify=False)
        except Exception:
            pass
        return {
            "blocker": blocker,
            "captcha": bool(captcha.get("detected")),
            "unknown_required_fields": unknown_required or [],
            "fields": self.field_map or [],
            "current_url": self.page.url if self.page else "",
        }

    def _record_unknown_questions(self, questions: list[str], reason: str = "") -> None:
        if not questions:
            return
        try:
            payload = json.loads(UNKNOWN_QUESTIONS_PATH.read_text()) if UNKNOWN_QUESTIONS_PATH.exists() else {
                "updated_at": "",
                "blocking_questions": [],
                "known_manual_topics": [],
            }
            existing = {
                (item.get("job_id"), item.get("question"))
                for item in payload.get("blocking_questions", [])
                if isinstance(item, dict)
            }
            for question in questions:
                key = (self.job.get("id", ""), question)
                if key in existing:
                    continue
                payload.setdefault("blocking_questions", []).append({
                    "job_id": self.job.get("id", ""),
                    "company": self.job.get("company", ""),
                    "title": self.job.get("title", ""),
                    "portal": self.job.get("portal", ""),
                    "url": self.job.get("url", ""),
                    "question": question,
                    "reason": reason or "Required field could not be answered from profile_truth.json.",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
            payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            UNKNOWN_QUESTIONS_PATH.write_text(json.dumps(payload, indent=2))
        except Exception as exc:
            self._log(f"Unknown question logging failed: {exc}")

    def map_fields(self) -> dict:
        """Detect form fields on the current page and propose values."""
        if not self.page:
            return {"ok": False, "error": "Browser not started"}

        self._log("Mapping form fields...")
        fields = []

        try:
            # Always try to move from the job detail page to the actual
            # application form before collecting fields. Job detail pages often
            # contain unrelated selects/inputs that otherwise fool the mapper.
            self._maybe_open_application_form()
            fields = self._collect_fields()
            if not fields:
                self._maybe_open_application_form()
                fields = self._collect_fields()
        except Exception as e:
            self._log(f"Field mapping error: {e}")

        self.field_map = fields
        self.state = "mapped"
        self._log(f"Found {len(fields)} fields. {sum(1 for f in fields if f['proposed_value'])} have proposed values.")
        return {"ok": True, "fields": fields, "state": self.state}

    def fill_safe_fields(self) -> dict:
        """Fill non-sensitive text/email/tel/url fields with proposed values."""
        if not self.page or self.field_map is None:
            return {"ok": False, "error": "Run map_fields first"}

        # Check for CAPTCHA before filling
        captcha = self.detect_captcha()
        if captcha["detected"]:
            return {
                "ok": False,
                "captcha_detected": True,
                "captcha_indicators": captcha.get("indicators", []),
                "error": "CAPTCHA detected. Check browser and Telegram for instructions.",
                "filled": [],
                "skipped": [],
            }

        filled = []
        skipped = []
        for field in self.field_map:
            if not field["proposed_value"]:
                skipped.append(field["label"])
                continue
            if field["is_sensitive"] or field["is_file"]:
                skipped.append(f"{field['label']} (sensitive/file — manual required)")
                continue
            if not field["can_autofill"]:
                skipped.append(field["label"])
                continue

            try:
                sel = field["selector"]
                self.page.fill(sel, field["proposed_value"], timeout=5000)
                filled.append(field["label"])
                self._log(f"Filled: {field['label']} = {field['proposed_value'][:40]}")
                time.sleep(0.2)
            except Exception as e:
                skipped.append(f"{field['label']} (error: {e})")

        resume_path = self.artifacts.get("resume_pdf_path", "")
        cover_path = self.artifacts.get("cover_pdf_path", "")
        uploaded_resume = False
        uploaded_cover = False
        for field in [f for f in self.field_map if f.get("is_file")]:
            try:
                sel = field["selector"]
                label = f"{field.get('label', '')} {field.get('name', '')}".lower()
                target_path = ""
                target_label = ""
                if "cover" in label and cover_path and Path(cover_path).exists():
                    target_path = cover_path
                    target_label = "cover letter file upload"
                    uploaded_cover = True
                elif resume_path and Path(resume_path).exists() and not uploaded_resume:
                    target_path = resume_path
                    target_label = "resume file upload"
                    uploaded_resume = True
                elif cover_path and Path(cover_path).exists() and not uploaded_cover:
                    target_path = cover_path
                    target_label = "cover letter file upload"
                    uploaded_cover = True

                if not target_path:
                    continue

                scope = self._scope_for_field(field)
                el = scope.query_selector(sel)
                if el:
                    el.set_input_files(target_path)
                    filled.append(target_label)
                    self._log(f"Uploaded {target_label}: {target_path}")
            except Exception as e:
                skipped.append(f"{field.get('label') or 'file upload'} (error: {e})")

        self.state = "filling"
        self._screenshot("after_fill")
        return {"ok": True, "filled": filled, "skipped": skipped, "state": self.state}

    def get_review_state(self) -> dict:
        """Return current state for user review before submission."""
        if not self.page:
            return {"ok": False, "error": "Browser not started"}

        screenshot_path = self._screenshot("review")
        url = self.page.url
        title = self.page.title()
        self.state = "review"
        return {
            "ok": True,
            "state": "review",
            "current_url": url,
            "page_title": title,
            "log": self.log[-20:],
            "field_map": self.field_map,
            "screenshot_path": screenshot_path,
            "instructions": (
                "REVIEW REQUIRED: Check the open browser window. "
                "Verify all fields are filled correctly. "
                "Do NOT submit manually. "
                "Click CONFIRM SUBMIT in the UI to proceed, or CANCEL to abort."
            ),
            "submit_disabled_by_default": True,
        }

    def submit(self) -> dict:
        """
        Final submission — ONLY called after user explicitly confirms.
        Looks for submit button and clicks it.
        """
        if not self.page:
            return {"ok": False, "error": "Browser not started"}

        policy_decision = can_submit_automatically(
            self.job,
            self._page_state_for_policy(),
            self._policy_artifacts(),
            self._policy_answers(),
            self._policy_domain_memory(),
        )
        if not policy_decision.get("allowed"):
            return {
                "ok": False,
                "blocker": "manual_review",
                "policy_decision": policy_decision,
                "error": f"Central policy blocked submit: {policy_decision.get('reason')}",
                "session_id": self.session_id,
            }

        self._log("USER CONFIRMED SUBMISSION. Proceeding...")
        quality = self._pre_submit_quality_check()
        if not quality.get("ok"):
            self._log(f"Pre-submit quality check blocked submission: {quality.get('error')}")
            return quality
        # Scroll to bottom to reveal submit button and trigger any lazy-loaded elements
        try:
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
        except Exception:
            pass
        self._screenshot("before_submit")
        submit_selectors = [
            "button[type=submit]",
            "input[type=submit]",
            "button:has-text('Submit Application')",
            "button:has-text('Submit application')",
            "button:has-text('Submit')",
            "button:has-text('Apply Now')",
            "button:has-text('Apply now')",
            "button:has-text('Apply')",
            "button:has-text('Send Application')",
            "button:has-text('Send application')",
            "button:has-text('Confirm')",
            "[data-testid*='submit']",
            "[data-automation-id*='submit']",
            "button[class*='submit']",
        ]
        for scope in self._scopes():
            for sel in submit_selectors:
                try:
                    btn = scope.query_selector(sel)
                    if btn and btn.is_visible():
                        self._log(f"Found submit button: {sel}")
                        self._screenshot("before_submit")
                        self._click_with_retry(btn, f"submit:{sel}", attempts=3)
                        confirmation = self._wait_for_submission_confirmation()
                        self._screenshot("after_submit")
                        if confirmation.get("detected"):
                            self.state = "submitted"
                            self._log(f"Submission confirmed: {confirmation.get('reason')}")
                            return {
                                "ok": True,
                                "state": "submitted",
                                "url": self.page.url,
                                "confirmation": confirmation,
                            }
                        self.state = "failed"
                        return {
                            "ok": False,
                            "blocker": "manual_review",
                            "error": "Submit click attempted, but no submission confirmation was detected.",
                            "url": self.page.url,
                            "session_id": self.session_id,
                        }
                except Exception as e:
                    self._log(f"Submit attempt failed ({sel}): {e}")
                    # If click timed out due to CAPTCHA intercepting pointer events, detect and return
                    captcha = self.detect_captcha()
                    if captcha["detected"]:
                        return self._blocked_result("captcha", "CAPTCHA appeared at submit time", captcha_indicators=captcha.get("indicators", []))

        # Last resort: find any visible button that looks like submission
        try:
            for scope in self._scopes():
                buttons = scope.query_selector_all("button, input[type=submit]")
                for btn in buttons:
                    try:
                        if not btn.is_visible():
                            continue
                        text = (btn.inner_text() or btn.get_attribute("value") or "").lower()
                        if any(x in text for x in ["submit", "apply", "send", "confirm", "finish"]):
                            self._log(f"Fallback submit: clicking '{text}' button")
                            self._screenshot("before_submit_fallback")
                            self._click_with_retry(btn, f"fallback submit:{text[:30]}", attempts=3)
                            confirmation = self._wait_for_submission_confirmation()
                            self._screenshot("after_submit")
                            if confirmation.get("detected"):
                                self.state = "submitted"
                                self._log(f"Submission confirmed (fallback): {confirmation.get('reason')}")
                                return {
                                    "ok": True,
                                    "state": "submitted",
                                    "url": self.page.url,
                                    "confirmation": confirmation,
                                }
                            self.state = "failed"
                            return {
                                "ok": False,
                                "blocker": "manual_review",
                                "error": "Fallback submit click attempted, but no submission confirmation was detected.",
                                "url": self.page.url,
                                "session_id": self.session_id,
                            }
                    except Exception:
                        continue
        except Exception:
            pass

        # JS fallback: click visible submit-looking buttons or call form.requestSubmit()
        try:
            js_result = self.page.evaluate("""() => {
                // Walk all forms — find first visible submit-like button
                for (const form of document.querySelectorAll('form')) {
                    const candidates = form.querySelectorAll(
                        'button[type=submit], input[type=submit], button:not([type=button])'
                    );
                    for (const el of candidates) {
                        if (el.offsetParent !== null && !el.disabled) {
                            const t = (el.innerText || el.value || '').toLowerCase().trim();
                            if (!t || /submit|apply|send|confirm|finish|continue/.test(t)) {
                                el.click();
                                return 'clicked:' + (t || 'unnamed');
                            }
                        }
                    }
                }
                // requestSubmit on first visible form as last resort
                const form = document.querySelector('form');
                if (form) {
                    try { form.requestSubmit(); return 'requestSubmit'; } catch (e) {}
                }
                return 'none';
            }""")
            if js_result and js_result != "none":
                self._log(f"JS submit fallback: {js_result}")
                time.sleep(1.5)
                confirmation = self._wait_for_submission_confirmation()
                self._screenshot("after_submit_js")
                if confirmation.get("detected"):
                    self.state = "submitted"
                    self._log(f"Submission confirmed (JS fallback): {confirmation.get('reason')}")
                    return {
                        "ok": True,
                        "state": "submitted",
                        "url": self.page.url,
                        "confirmation": confirmation,
                    }
        except Exception as js_err:
            self._log(f"JS submit fallback error: {js_err}")

        self.state = "failed"
        self._log("No submit button found. Manual submission required.")
        return {
            "ok": False,
            "blocker": "manual_review",
            "error": "No submit button found. Please submit manually in the browser.",
            "url": self.page.url,
            "session_id": self.session_id,
        }

    def _click_with_retry(self, el, label: str, attempts: int = 2) -> None:
        """Click with scroll + force fallback for sticky overlays or lazy buttons."""
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                try:
                    el.scroll_into_view_if_needed(timeout=3000)
                except Exception:
                    pass
                time.sleep(0.3 * attempt)
                el.click(timeout=6000)
                return
            except Exception as exc:
                last_error = exc
                self._log(f"Click retry {attempt}/{attempts} failed for {label}: {exc}")
                time.sleep(0.7 * attempt)
        try:
            el.click(timeout=5000, force=True)
            self._log(f"Force-clicked {label}")
            return
        except Exception as exc:
            raise RuntimeError(f"Could not click {label}: {last_error or exc}") from exc

    def _fill_with_events(self, el, value: str, timeout: int = 4000) -> None:
        """Fill Playwright input and dispatch events for React-controlled forms."""
        el.fill(value, timeout=timeout)
        try:
            el.evaluate(
                """(node) => {
                    node.dispatchEvent(new Event('input', { bubbles: true }));
                    node.dispatchEvent(new Event('change', { bubbles: true }));
                    node.dispatchEvent(new Event('blur', { bubbles: true }));
                }"""
            )
        except Exception:
            pass

    def _wait_for_submission_confirmation(self, timeout_secs: int = 10) -> dict:
        if not self.page:
            return {"detected": False}
        deadline = time.time() + timeout_secs
        while time.time() < deadline:
            try:
                try:
                    self.page.wait_for_load_state("networkidle", timeout=1500)
                except Exception:
                    pass
                url = self.page.url.lower()
                if any(token in url for token in ["confirmation", "submitted", "success"]):
                    return {"detected": True, "reason": f"url:{self.page.url}"}
                text = (self.page.locator("body").inner_text(timeout=2500) or "").lower()
                for phrase in SUBMISSION_CONFIRMATION_TEXT:
                    if phrase in text:
                        return {"detected": True, "reason": phrase}
            except Exception:
                pass
            time.sleep(1)
        return {"detected": False}

    def close(self):
        try:
            if self.browser:
                self.browser.close()
            if hasattr(self, "_pw"):
                self._pw.stop()
        except Exception:
            pass
        self.state = "closed"

    def _handle_login_if_needed(self, apply_url: str = "") -> bool:
        """
        Detect login forms and fill credentials automatically.
        Handles Workday, Greenhouse, Lever, and generic portals.
        Returns True if login was attempted (so caller can re-navigate if needed).
        """
        if not self.page:
            return False
        try:
            page_url = self.page.url.lower()
            page_text = (self.page.content() or "").lower()

            # Check if we're on a login/signin page — require URL signal OR actual password field
            url_signal = (
                "sign-in" in page_url or "signin" in page_url or
                "login" in page_url or "log-in" in page_url or
                "sign_in" in page_url or "/auth" in page_url
            )
            has_password = self.page.query_selector("input[type=password]") is not None
            # Only treat as login page if URL signals it OR page has a visible password field
            is_login_page = url_signal or has_password
            if not is_login_page:
                return False

            if "workday" in page_url or "myworkdayjobs" in page_url:
                self._log("Workday login/account wall detected — marking assisted instead of creating an account.")
                return False

            pwd_el = self.page.query_selector("input[type=password]")
            if not pwd_el or not pwd_el.is_visible():
                # Could be a 2-step login (email first, then password)
                # Try entering email to reveal password
                for sel in ["input[type=email]", "input[name*='email']", "input[id*='email']",
                            "input[placeholder*='email' i]", "input[data-automation-id='email']"]:
                    el = self.page.query_selector(sel)
                    if el and el.is_visible():
                        self._log("Two-step login detected — entering email first")
                        el.fill(PROFILE["email"], timeout=3000)
                        # Click Next/Continue/Sign In to reveal password
                        for btn_sel in ["button[type=submit]", "button:has-text('Next')",
                                        "button:has-text('Continue')", "button:has-text('Sign In')"]:
                            try:
                                btn = self.page.query_selector(btn_sel)
                                if btn and btn.is_visible():
                                    btn.click(timeout=3000)
                                    time.sleep(2)
                                    break
                            except Exception:
                                continue
                        break
                # Re-check for password
                time.sleep(1.5)
                pwd_el = self.page.query_selector("input[type=password]")
                if not pwd_el or not pwd_el.is_visible():
                    return False

            self._log("Login form detected — filling credentials")
            login_password = os.environ.get("JOB_APPLIER_LOGIN_PASSWORD", "")
            if not login_password:
                self._log("Login password is not configured — marking assisted instead of guessing credentials.")
                return False

            # Fill email/username field (try all common selectors)
            for sel in [
                "input[data-automation-id='email']",
                "input[type=email]",
                "input[name*='email']",
                "input[name*='username']",
                "input[id*='email']",
                "input[id*='username']",
                "input[placeholder*='email' i]",
                "input[placeholder*='username' i]",
                "input[autocomplete='email']",
                "input[autocomplete='username']",
            ]:
                try:
                    el = self.page.query_selector(sel)
                    if el and el.is_visible():
                        el.fill(PROFILE["email"], timeout=3000)
                        self._log(f"Filled email into {sel}")
                        break
                except Exception:
                    continue

            time.sleep(0.3)

            # Fill password
            pwd_el.fill(login_password, timeout=3000)
            self._log("Filled password")
            time.sleep(0.5)

            # Click sign-in button
            for btn_sel in [
                "button[data-automation-id='signInSubmitButton']",
                "button[type=submit]",
                "input[type=submit]",
                "button:has-text('Sign in')",
                "button:has-text('Sign In')",
                "button:has-text('Log in')",
                "button:has-text('Login')",
                "button:has-text('Continue')",
                "button:has-text('Submit')",
            ]:
                try:
                    btn = self.page.query_selector(btn_sel)
                    if btn and btn.is_visible():
                        btn.click(timeout=3000)
                        self._log(f"Clicked login button: {btn_sel}")
                        break
                except Exception:
                    continue

            # Wait for redirect/response from Workday
            try:
                self.page.wait_for_load_state("networkidle", timeout=12000)
            except Exception:
                time.sleep(5)
            time.sleep(1)

            # Check for login failure (wrong credentials, no account)
            page_text2 = (self.page.content() or "").lower()
            page_url2 = self.page.url.lower()

            # If password field is gone and page changed → login succeeded
            pwd_after = self.page.query_selector("input[type=password]")
            if not pwd_after or not pwd_after.is_visible():
                self._log("Login appears successful (password field gone)")
                return True

            # Check if login actually failed (still showing sign-in form with errors)
            login_failed = any(x in page_text2 for x in [
                "incorrect password", "invalid password", "wrong password",
                "account not found", "no account", "user not found",
                "invalid credentials", "sign in failed",
            ])
            sign_in_still_present = self.page.query_selector(
                "input[data-automation-id='password'], input[type=password]"
            ) is not None

            # Only create account if we're still on sign-in AND there's an explicit "no account" error
            if login_failed and sign_in_still_present and (
                "sign up" in page_url2 or "register" in page_url2 or
                any(x in page_text2 for x in ["create an account", "create your account", "new account"])
            ):
                self._log("Account creation required — marking assisted; account creation is not automated.")
                return False

            # Handle email verification
            if any(x in page_text2 for x in ["verify your email", "verification code",
                                               "check your email", "enter the code",
                                               "we sent a code", "check your inbox"]):
                self._log("Email verification required — marking assisted; verification is not automated.")
                try:
                    ss_path = str(SCREENSHOTS_DIR / f"login_verify_{self.session_id}.png")
                    self.page.screenshot(path=ss_path)
                    self._log(f"Screenshot saved: {ss_path}")
                except Exception:
                    pass
                return False

            # If still on login/error page, log and continue best-effort
            if "sign-in" in self.page.url.lower() or "login" in self.page.url.lower():
                self._log("Login may have failed — continuing best-effort")

            self._log("Login step complete")
            return True
        except Exception as e:
            self._log(f"Login handler error (non-fatal): {e}")
            return False

    def _create_workday_account(self, apply_url: str = "") -> None:
        """Create a Workday account when no account exists."""
        try:
            # Click "Create Account" button
            for sel in ["button:has-text('Create Account')", "a:has-text('Create Account')",
                        "button:has-text('Sign Up')", "a:has-text('Sign Up')",
                        "button:has-text('Register')"]:
                el = self.page.query_selector(sel)
                if el and el.is_visible():
                    el.click(timeout=3000)
                    self._log(f"Clicked {sel}")
                    time.sleep(2)
                    break

            # Fill registration form
            for sel in ["input[data-automation-id='email']", "input[type=email]",
                        "input[name*='email']", "input[id*='email']"]:
                el = self.page.query_selector(sel)
                if el and el.is_visible():
                    el.fill(PROFILE["email"], timeout=3000)
                    self._log("Filled registration email")
                    break

            for sel in ["input[type=password]", "input[name*='password']", "input[id*='password']"]:
                el = self.page.query_selector(sel)
                if el and el.is_visible():
                    el.fill(os.environ.get("JOB_APPLIER_LOGIN_PASSWORD", ""), timeout=3000)
                    self._log("Filled registration password")
                    break

            # Confirm password field
            for sel in ["input[name*='confirm']", "input[id*='confirm']",
                        "input[placeholder*='confirm' i]", "input[placeholder*='repeat' i]"]:
                el = self.page.query_selector(sel)
                if el and el.is_visible():
                    el.fill(os.environ.get("JOB_APPLIER_LOGIN_PASSWORD", ""), timeout=3000)
                    break

            # Submit registration
            for btn_sel in ["button[data-automation-id='createAccountSubmitButton']",
                            "button[type=submit]", "button:has-text('Create Account')",
                            "button:has-text('Register')"]:
                try:
                    btn = self.page.query_selector(btn_sel)
                    if btn and btn.is_visible():
                        btn.click(timeout=3000)
                        self._log("Submitted account creation")
                        break
                except Exception:
                    continue

            try:
                self.page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                time.sleep(4)

            # Email verification likely required after registration
            page_text = (self.page.content() or "").lower()
            if any(x in page_text for x in ["verify", "check your email", "confirmation", "sent"]):
                self._log("ACCOUNT VERIFICATION email sent — waiting 90s for user to verify...")
                try:
                    ss_path = str(SCREENSHOTS_DIR / f"register_verify_{self.session_id}.png")
                    self.page.screenshot(path=ss_path)
                    self._log(f"Screenshot: {ss_path}")
                except Exception:
                    pass
                time.sleep(90)

            self._log("Account creation step complete")
        except Exception as e:
            self._log(f"Account creation error (non-fatal): {e}")

    def auto_apply_full(self) -> dict:
        """
        Fully automated apply — no user confirmation required.
        Runs headless, fills all field types, handles multi-page forms, auto-submits.
        Returns {"ok": True} on success or {"ok": False, "captcha": True} if blocked.
        """
        eligible, reason = explain_auto_apply_eligibility(self.job)
        if not eligible:
            return {"ok": False, "blocker": "unsupported_portal", "error": reason}

        result = self.start()
        if not result.get("ok"):
            return result

        # CAPTCHA check after page load
        blocker = self.detect_blocker()
        if blocker:
            return self._blocked_result(blocker, f"Blocked on page load: {blocker}")
        captcha = self.detect_captcha()
        if captcha["detected"]:
            return self._blocked_result("captcha", "CAPTCHA on page load", captcha_indicators=captcha.get("indicators", []))

        result = self.map_fields()
        if not result.get("ok"):
            self.close()
            return result

        # Portals like Workday redirect to login AFTER clicking Apply
        self._screenshot("after_map_fields")
        apply_url = self.page.url if self.page else ""
        logged_in = self._handle_login_if_needed(apply_url=apply_url)
        if logged_in or (self.field_map is not None and len(self.field_map) == 0):
            # Navigate back to the application URL if redirected away
            current_url = self.page.url if self.page else ""
            if apply_url and "sign" not in current_url.lower() and "login" not in current_url.lower():
                pass  # already on application page
            elif apply_url and self.page:
                try:
                    self.page.goto(apply_url, wait_until="domcontentloaded", timeout=20000)
                    time.sleep(2)
                except Exception as _e:
                    self._log(f"Re-navigate error: {_e}")
            self._log("Re-mapping fields after login...")
            self.map_fields()

        blocker = self.detect_blocker()
        if blocker:
            return self._blocked_result(blocker, f"Blocked before fill: {blocker}")

        fill = self.fill_all_fields_auto()
        if fill.get("captcha"):
            self.close()
            return {"ok": False, "captcha": True, "error": "CAPTCHA after fill"}
        if fill.get("blocker"):
            self.close()
            return fill

        # Handle multi-page forms — click Next up to 8 times
        seen_page_signatures: set[str] = set()
        for _page in range(8):
            self._fill_required_empty_fields()
            unknown_required = self._unknown_required_fields()
            if unknown_required:
                return self._blocked_result(
                    "unknown_required_field",
                    f"Unknown required fields remain: {', '.join(unknown_required[:5])}",
                    unknown_required_fields=unknown_required,
                )
            advanced = self._click_next_if_present()
            if not advanced:
                break
            time.sleep(1.5)
            blocker = self.detect_blocker()
            if blocker:
                return self._blocked_result(blocker, f"Blocked on page {_page + 2}: {blocker}")
            # Re-map and fill new page fields
            self.map_fields()
            page_signature = self._page_signature()
            if page_signature in seen_page_signatures:
                return self._blocked_result("manual_review", "Repeated the same form step without progress.")
            seen_page_signatures.add(page_signature)
            fill = self.fill_all_fields_auto()
            if fill.get("blocker"):
                self.close()
                return fill

        # Final CAPTCHA check before submit
        blocker = self.detect_blocker()
        if blocker:
            return self._blocked_result(blocker, f"Blocked before submit: {blocker}")

        unknown_required = self._unknown_required_fields()
        if unknown_required:
            self._fill_required_empty_fields()
            unknown_required = self._unknown_required_fields()
        if unknown_required:
            return self._blocked_result(
                "unknown_required_field",
                f"Unknown required fields remain before submit: {', '.join(unknown_required[:5])}",
                unknown_required_fields=unknown_required,
            )

        policy_decision = can_submit_automatically(
            self.job,
            self._page_state_for_policy(unknown_required=unknown_required),
            self._policy_artifacts(),
            self._policy_answers(),
            self._policy_domain_memory(),
        )
        if not policy_decision.get("allowed"):
            return self._blocked_result(
                policy_decision.get("reason", "manual_review"),
                f"Central policy blocked auto-submit: {policy_decision.get('reason')}",
                policy_decision=policy_decision,
            )

        result = self.submit()
        if result.get("ok"):
            self.close()
            return result
        if (result.get("blocker") or "") == "manual_review":
            if self.keep_open_on_blocker:
                self.state = "assisted_manual_review"
                self._screenshot("blocked_manual_review")
            else:
                self.close()
            return result
        self.close()
        return result

    def resume_after_human(self) -> dict:
        """Continue after the user solved CAPTCHA/login/MFA in the open browser."""
        if not self.page:
            return {"ok": False, "error": "Browser session is not open."}
        confirmation = self._wait_for_submission_confirmation()
        if confirmation.get("detected"):
            self.state = "submitted"
            return {
                "ok": True,
                "state": "submitted",
                "url": self.page.url,
                "confirmation": confirmation,
            }
        blocker = self.detect_blocker(skip_captcha=False)
        if blocker:
            return self._blocked_result(blocker, f"Still blocked after human step: {blocker}")
        self.map_fields()
        fill = self.fill_all_fields_auto()
        if fill.get("blocker") or fill.get("captcha"):
            return fill
        unknown_required = self._unknown_required_fields()
        if unknown_required:
            self._fill_required_empty_fields()
            unknown_required = self._unknown_required_fields()
        if unknown_required:
            return self._blocked_result(
                "unknown_required_field",
                f"Unknown required fields remain after human step: {', '.join(unknown_required[:5])}",
                unknown_required_fields=unknown_required,
            )
        result = self.submit()
        self.close()
        return result

    def fill_all_fields_auto(self) -> dict:
        """Fill ALL field types automatically: text/email/tel/url, select, radio, checkbox, file."""
        if not self.page or self.field_map is None:
            return {"ok": False, "error": "Run map_fields first"}

        captcha = self.detect_captcha()
        if captcha["detected"]:
            return {"ok": False, "captcha": True, "filled": [], "skipped": []}
        blocker = self.detect_blocker(skip_captcha=True)
        if blocker:
            return {"ok": False, "blocker": blocker, "filled": [], "skipped": [], "error": f"Blocked before fill: {blocker}"}

        filled = []
        skipped = []

        # ── Text / email / tel / url ──────────────────────────────────────────
        for field in self.field_map:
            if field.get("is_file") or field.get("is_sensitive"):
                continue
            if not field.get("proposed_value") or not field.get("can_autofill"):
                skipped.append(field["label"])
                continue
            try:
                sel = field["selector"]
                scope = self._scope_for_field(field)
                el = scope.query_selector(sel)
                if el and el.is_visible():
                    self._fill_with_events(el, field["proposed_value"], timeout=4000)
                    filled.append(field["label"])
                    time.sleep(0.15)
            except Exception as e:
                skipped.append(f"{field['label']} ({e})")

        # ── Select dropdowns ──────────────────────────────────────────────────
        try:
            selects = []
            for scope in self._scopes():
                selects.extend(scope.query_selector_all("select"))
            for el in selects:
                try:
                    label = self._get_label(el)
                    name = el.get_attribute("name") or ""
                    combined = (label + " " + name).lower()
                    value = self._propose_select_value(combined, el)
                    if value:
                        el.select_option(value=value, timeout=3000)
                        filled.append(f"select:{label or name}")
                        time.sleep(0.1)
                except Exception:
                    pass
        except Exception:
            pass

        # ── Radio buttons ─────────────────────────────────────────────────────
        try:
            radios = []
            for scope in self._scopes():
                radios.extend(scope.query_selector_all("input[type=radio]"))
            handled_groups: set = set()
            for el in radios:
                try:
                    name = el.get_attribute("name") or ""
                    if name in handled_groups:
                        continue
                    option_label = self._get_label(el)
                    # Walk up DOM to find the question text for this radio group
                    question_text = ""
                    try:
                        question_text = el.evaluate("""el => {
                            let p = el.closest('fieldset, [role=group], [class*="question"], [class*="form-group"], [class*="field"]');
                            if (!p) p = el.parentElement && el.parentElement.parentElement;
                            if (!p) return '';
                            let leg = p.querySelector('legend, [class*="label"], [class*="title"], [class*="question"], p, h3, h4, span[class*="label"]');
                            return leg ? leg.innerText : p.innerText.split('\\n')[0];
                        }""") or ""
                    except Exception:
                        pass
                    combined = (question_text + " " + option_label + " " + name).lower()
                    answer = self._propose_radio_answer(combined)
                    if answer:
                        try:
                            radio_scope = el.owner_frame()
                        except Exception:
                            radio_scope = self.page
                        group = radio_scope.query_selector_all(f"input[type=radio][name='{name}']")
                        for r in group:
                            r_val = (r.get_attribute("value") or "").lower()
                            r_label_text = self._get_label(r).lower()
                            if answer.lower() in r_val or answer.lower() in r_label_text:
                                if r.is_visible():
                                    r.click(timeout=3000)
                                    handled_groups.add(name)
                                    filled.append(f"radio:{name}={answer}")
                                    time.sleep(0.15)
                                    break
                except Exception:
                    pass
        except Exception:
            pass

        # ── Checkboxes (terms / consent only) ────────────────────────────────
        try:
            checkboxes = []
            for scope in self._scopes():
                checkboxes.extend(scope.query_selector_all("input[type=checkbox]"))
            for el in checkboxes:
                try:
                    label = self._get_label(el).lower()
                    name = (el.get_attribute("name") or "").lower()
                    combined = label + " " + name
                    if any(kw in combined for kw in ["agree", "terms", "consent"]) and not any(
                        kw in combined for kw in ["acknowledge", "confirm", "certify", "authorize", "attest"]
                    ):
                        if el.is_visible() and not el.is_checked():
                            el.check(timeout=3000)
                            filled.append(f"checkbox:{label or name}")
                            time.sleep(0.1)
                except Exception:
                    pass
        except Exception:
            pass

        # ── File uploads (resume + cover letter) ─────────────────────────────
        resume_path = self.artifacts.get("resume_pdf_path", "")
        cover_path = self.artifacts.get("cover_pdf_path", "")
        uploaded_resume = False
        uploaded_cover = False
        for field in [f for f in self.field_map if f.get("is_file")]:
            try:
                sel = field["selector"]
                label = (field.get("label", "") + " " + field.get("name", "")).lower()
                # Skip "Autofill from resume" convenience buttons — they steal the resume slot
                if "autofill" in label:
                    skipped.append(f"file:{field.get('label', '')} (autofill skip)")
                    continue
                target_path = ""
                if "cover" in label and cover_path and Path(cover_path).exists():
                    target_path = cover_path
                    uploaded_cover = True
                elif resume_path and Path(resume_path).exists() and not uploaded_resume:
                    target_path = resume_path
                    uploaded_resume = True
                elif cover_path and Path(cover_path).exists() and not uploaded_cover:
                    target_path = cover_path
                    uploaded_cover = True
                if not target_path:
                    continue
                scope = self._scope_for_field(field)
                el = scope.query_selector(sel)
                if el:
                    el.set_input_files(target_path)
                    filled.append(f"file:{Path(target_path).name}")
                    time.sleep(0.3)
            except Exception as e:
                skipped.append(f"file:{field.get('label', '')} ({e})")

        # Direct file-input fallback for custom embeds with anonymous inputs.
        # Only runs if the field_map pass didn't already upload these files.
        if not uploaded_resume or not uploaded_cover:
            try:
                file_inputs = []
                for scope in self._scopes():
                    file_inputs.extend(scope.query_selector_all("input[type=file]"))
                for idx, el in enumerate(file_inputs):
                    try:
                        # Skip inputs near "autofill" text to avoid the Ashby autofill-from-resume slot
                        nearby_text = ""
                        try:
                            nearby_text = (el.evaluate("""el => {
                                let p = el.closest('div,section,label') || el.parentElement;
                                return p ? p.innerText.toLowerCase() : '';
                            }""") or "").lower()
                        except Exception:
                            pass
                        if "autofill" in nearby_text:
                            continue
                        if idx == 0 and not uploaded_resume and resume_path and Path(resume_path).exists():
                            el.set_input_files(resume_path)
                            uploaded_resume = True
                            filled.append(f"file:{Path(resume_path).name}")
                        elif not uploaded_cover and cover_path and Path(cover_path).exists():
                            el.set_input_files(cover_path)
                            uploaded_cover = True
                            filled.append(f"file:{Path(cover_path).name}")
                    except Exception:
                        continue
            except Exception:
                pass

        positional = self._fill_standard_profile_fields_by_position()
        filled.extend(positional)

        ashby = self._fill_ashby_custom_dropdowns()
        filled.extend(ashby)

        self._screenshot("auto_fill")
        return {"ok": True, "filled": filled, "skipped": skipped}

    def _field_context_text(self, el) -> str:
        """Best-effort label plus nearby text for React/custom form fields."""
        try:
            return (el.evaluate("""el => {
                const parts = [];
                for (const attr of ['aria-label', 'name', 'placeholder', 'id']) {
                    const v = el.getAttribute(attr);
                    if (v) parts.push(v);
                }
                const labelled = el.getAttribute('aria-labelledby');
                if (labelled) {
                    for (const id of labelled.split(/\\s+/)) {
                        const n = document.getElementById(id);
                        if (n && n.innerText) parts.push(n.innerText);
                    }
                }
                let p = el.closest('label, [data-field], [data-qa], div, section, fieldset');
                let hops = 0;
                while (p && hops < 3) {
                    if (p.innerText) parts.push(p.innerText);
                    p = p.parentElement;
                    hops += 1;
                }
                return parts.join(' ').replace(/\\s+/g, ' ').trim().slice(0, 600);
            }""") or "")
        except Exception:
            return self._get_label(el) or ""

    def _is_open_ended_prompt(self, text: str) -> bool:
        prompt = (text or "").lower()
        return any(s in prompt for s in [
            "what makes", "why", "how did", "how do", "describe", "tell us", "tell me",
            "explain", "research interests", "interests/focuses", "project",
            "experience", "background", "additional information", "cover letter",
            "statement", "essay", "good fit", "excites you", "why should we hire",
        ])

    def _pre_submit_quality_check(self) -> dict:
        """
        Last gate before real submission. Blocks obvious corrupted autofill such as
        phone numbers in essay fields or a name in the LinkedIn field.
        """
        if not self.page:
            return {"ok": False, "blocker": "manual_review", "error": "Browser page unavailable."}

        problems: list[str] = []
        try:
            for scope in self._scopes():
                fields = scope.query_selector_all("input:not([type=hidden]), textarea")
                for el in fields:
                    try:
                        if not el.is_visible():
                            continue
                        field_type = (el.get_attribute("type") or "").lower()
                        if field_type in ("checkbox", "radio", "file", "password", "submit", "button"):
                            continue
                        context = self._field_context_text(el).lower()
                        try:
                            value = el.input_value(timeout=500) or ""
                        except Exception:
                            value = el.get_attribute("value") or ""
                        value_l = value.lower().strip()
                        if not value_l:
                            continue
                        if "linkedin" in context and "linkedin.com" not in value_l:
                            problems.append("LinkedIn field does not contain linkedin.com")
                        if ("github" in context or "git hub" in context) and "github.com" not in value_l:
                            problems.append("GitHub field does not contain github.com")
                        if ("website" in context or "portfolio" in context) and not any(x in value_l for x in ["moyosore.dev", "github.com", "linkedin.com"]):
                            problems.append("website/portfolio field has unexpected value")
                        if ("email" in context or field_type == "email") and PROFILE["email"] not in value_l:
                            problems.append("email field has unexpected value")
                        if ("phone" in context or field_type == "tel") and PROFILE["phone_digits"] not in "".join(ch for ch in value_l if ch.isdigit()):
                            problems.append("phone field has unexpected value")
                        if self._is_open_ended_prompt(context):
                            word_count = len(value.split())
                            identity_only = value_l in {
                                PROFILE["firstName"].lower(),
                                PROFILE["lastName"].lower(),
                                PROFILE["fullName"].lower(),
                                PROFILE["email"].lower(),
                                PROFILE["phone"].lower(),
                                PROFILE["city"].lower(),
                            }
                            if identity_only or word_count < 18:
                                problems.append(f"open-ended answer too short or corrupted: {context[:80]}")
                    except Exception:
                        continue
        except Exception as exc:
            return {"ok": False, "blocker": "manual_review", "error": f"Quality check failed: {exc}"}

        if problems:
            return {
                "ok": False,
                "blocker": "unknown_required_field",
                "error": "; ".join(problems[:5]),
                "session_id": self.session_id,
            }
        return {"ok": True}

    def _fill_ashby_custom_dropdowns(self) -> list[str]:
        """
        Ashby uses React-controlled combobox/listbox components that aren't standard
        <select> elements. This pass finds them, clicks to open, and picks an option.
        """
        if not self.page:
            return []
        filled: list[str] = []
        try:
            # Ashby comboboxes: div or button with role="combobox" or data-qa*="select"
            combos = self.page.query_selector_all('[role="combobox"], [data-qa*="select"], button[aria-haspopup="listbox"]')
            for el in combos:
                try:
                    if not el.is_visible():
                        continue
                    label = self._field_context_text(el).lower()
                    answer = self._propose_ashby_dropdown_answer(label)
                    if not answer:
                        continue
                    el.click(timeout=3000)
                    time.sleep(0.4)
                    # For "Start typing..." searchable dropdowns, type the answer to surface options
                    placeholder = (el.get_attribute("placeholder") or "").lower()
                    tag = el.evaluate("el => el.tagName.toLowerCase()")
                    if "typing" in placeholder or tag == "input":
                        try:
                            try:
                                el.fill("", timeout=1500)
                            except Exception:
                                pass
                            el.type(answer, delay=50)
                            time.sleep(0.6)
                        except Exception:
                            pass
                    # After click (and optional type), find visible listbox options
                    option_found = False
                    for opt_sel in ['[role="option"]', 'li[role="option"]', '[data-qa*="option"]']:
                        opts = self.page.query_selector_all(opt_sel)
                        for opt in opts:
                            try:
                                if not opt.is_visible():
                                    continue
                                opt_text = (opt.inner_text() or "").lower()
                                if answer.lower() in opt_text:
                                    opt.click(timeout=2000)
                                    filled.append(f"ashby-select:{label[:40]}")
                                    option_found = True
                                    time.sleep(0.3)
                                    break
                            except Exception:
                                continue
                        if option_found:
                            break
                    if not option_found:
                        # Press Escape to close the opened dropdown without selecting
                        try:
                            self.page.keyboard.press("Escape")
                        except Exception:
                            pass
                except Exception:
                    continue
        except Exception:
            pass
        if filled:
            self._log(f"Filled Ashby custom dropdowns: {', '.join(filled)}")
        return filled

    def _propose_ashby_dropdown_answer(self, label: str) -> str:
        """Map an Ashby dropdown label to the best option text to select."""
        if any(k in label for k in ["how did you hear", "how did you find", "source", "referred by"]):
            return "linkedin"
        if any(k in label for k in ["area of software", "area of interest", "software area", "engineering area"]):
            return "backend"
        if any(k in label for k in ["location", "closest to", "nearest to", "work location"]):
            return "canada"
        if any(k in label for k in ["pronouns"]):
            return ""
        if any(k in label for k in ["employment type", "job type"]):
            return "intern"
        if any(k in label for k in ["work authorization", "authorized to work"]):
            return "yes"
        return ""

    def _fill_standard_profile_fields_by_position(self) -> list[str]:
        """Fallback for application forms whose inputs have no stable labels/names."""
        if not self.page:
            return []
        filled: list[str] = []
        try:
            answers = [
                PROFILE["firstName"],
                PROFILE["lastName"],
                PROFILE["email"],
                PROFILE["phone"],
                PROFILE["city"],
            ]
            fields = []
            all_inputs = []
            for scope in self._scopes():
                all_inputs.extend(scope.query_selector_all("input:not([type=hidden]), textarea"))
            for el in all_inputs:
                try:
                    field_type = (el.get_attribute("type") or "text").lower()
                    if field_type in ("checkbox", "radio", "file", "password", "submit", "button"):
                        continue
                    if not el.is_visible():
                        continue
                    try:
                        current = el.input_value(timeout=500) or ""
                    except Exception:
                        current = el.get_attribute("value") or ""
                    if current.strip():
                        continue
                    context = self._field_context_text(el).lower()
                    unsafe_positional = [
                        "linkedin", "github", "website", "portfolio", "how did you hear",
                        "source", "location", "closest to", "area of software",
                        "work authorization", "sponsor", "gpa", "school", "university",
                    ]
                    if any(s in context for s in unsafe_positional):
                        continue
                    # Don't fill essay/open-ended textareas positionally (they need real answers)
                    tag = el.evaluate("el => el.tagName.toLowerCase()")
                    if tag == "textarea" or self._is_open_ended_prompt(context):
                        continue
                    fields.append(el)
                except Exception:
                    continue
            for el, value in zip(fields, answers):
                try:
                    self._fill_with_events(el, value, timeout=3000)
                    filled.append("profile positional field")
                    time.sleep(0.1)
                except Exception:
                    continue
            all_selects = []
            for scope in self._scopes():
                all_selects.extend(scope.query_selector_all("select"))
            for sel in all_selects:
                try:
                    if sel.is_visible():
                        val = self._propose_select_value("country", sel)
                        if val:
                            sel.select_option(value=val, timeout=3000)
                            filled.append("profile country select")
                            break
                except Exception:
                    continue
        except Exception:
            pass
        if filled:
            self._log(f"Filled positional profile fields: {len(filled)}")
        return filled

    def _fill_required_empty_fields(self) -> list[str]:
        """Second pass for required textareas/custom fields discovered after mapping."""
        if not self.page:
            return []
        filled: list[str] = []
        positional_answers = [
            PROFILE["firstName"],
            PROFILE["lastName"],
            PROFILE["email"],
            PROFILE["phone"],
            PROFILE["city"],
        ]
        text_position = 0
        try:
            fields = []
            for scope in self._scopes():
                fields.extend(scope.query_selector_all("input:not([type=hidden]), textarea, select"))
            for el in fields:
                try:
                    if not el.is_visible():
                        continue
                    required = (
                        el.get_attribute("required") is not None
                        or (el.get_attribute("aria-required") or "").lower() == "true"
                    )
                    if not required:
                        continue
                    tag = el.evaluate("el => el.tagName.toLowerCase()")
                    field_type = (el.get_attribute("type") or ("textarea" if tag == "textarea" else "text")).lower()
                    if field_type in ("checkbox", "radio", "file", "password"):
                        continue
                    try:
                        value = el.input_value(timeout=800) or ""
                    except Exception:
                        value = el.get_attribute("value") or ""
                    if value.strip():
                        continue
                    label = self._field_context_text(el) or self._get_label(el) or el.get_attribute("name") or el.get_attribute("placeholder") or ""
                    if tag == "select":
                        select_value = self._propose_select_value(label.lower(), el)
                        if select_value:
                            el.select_option(value=select_value, timeout=3000)
                            filled.append(label or "required select")
                    else:
                        proposed = self._propose_value(
                            el.get_attribute("name") or "",
                            el.get_attribute("placeholder") or "",
                            label,
                            "text" if tag == "textarea" else field_type,
                        )
                        can_use_positional = tag != "textarea" and not self._is_open_ended_prompt(label)
                        if not proposed and can_use_positional and text_position < len(positional_answers):
                            proposed = positional_answers[text_position]
                            text_position += 1
                        if not proposed:
                            continue
                        self._fill_with_events(el, proposed, timeout=4000)
                        filled.append(label or "required field")
                    time.sleep(0.15)
                except Exception:
                    continue
        except Exception:
            pass
        if filled:
            self._log(f"Filled required second-pass fields: {', '.join(filled[:5])}")
        return filled

    def _propose_select_value(self, combined: str, el) -> Optional[str]:
        """Return the best option value for a select element."""
        try:
            options = el.query_selector_all("option")
            option_texts = [(o.get_attribute("value") or "", o.inner_text().strip().lower()) for o in options]
        except Exception:
            return None

        def _pick(candidates):
            for val, text in option_texts:
                if any(c in text for c in candidates):
                    return val
            return None

        if any(k in combined for k in ["country", "citizenship", "nation"]):
            return _pick(["canada", "canadian"])
        if any(k in combined for k in ["province", "state", "region"]):
            return _pick(["alberta", "ab"])
        if any(k in combined for k in ["degree", "education", "qualification"]):
            return _pick(["bachelor", "bsc", "b.sc", "undergraduate"])
        if any(k in combined for k in ["grad year", "graduation year", "expected grad"]):
            return _pick(["2027"])
        country_context = self._country_context(combined)
        if any(k in combined for k in ["work auth", "authorized", "legally", "eligible to work", "right to work"]):
            return _pick(["yes", "authorized", "eligible"]) if country_context != "us" else _pick(["no", "not authorized"])
        if any(k in combined for k in ["sponsor", "visa", "require sponsor"]):
            return _pick(["yes", "require"]) if country_context == "us" else _pick(["no", "not require"])
        if any(k in combined for k in ["gender", "sex", "race", "ethnicity", "veteran", "disability"]):
            return None
        if any(k in combined for k in ["how did you hear", "source", "referred"]):
            return _pick(["linkedin", "job board", "website", "online"])
        return None

    def _propose_radio_answer(self, combined: str) -> Optional[str]:
        """Return best radio answer string for a group label."""
        country_context = self._country_context(combined)
        if any(k in combined for k in ["authorized", "work auth", "legally eligible", "eligible to work", "right to work"]):
            return "no" if country_context == "us" else "yes"
        if any(k in combined for k in ["require sponsor", "need sponsor", "visa sponsor", "sponsorship"]):
            return "yes" if country_context == "us" else "no"
        if any(k in combined for k in ["18 years", "of age", "legal age"]):
            return "yes"
        if any(k in combined for k in ["relocat"]):
            return "yes"
        if any(k in combined for k in ["remote", "work from home"]):
            return "yes"
        if any(k in combined for k in ["gender", "sex", "race", "ethnicity", "veteran", "disability"]):
            return None
        # Internship/availability questions → yes
        if any(k in combined for k in ["available", "full-time", "full time", "internship available"]):
            return "yes"
        # Education level
        if any(k in combined for k in ["education level", "level of education", "current level", "pursuing"]):
            return "undergrad"
        # Degree type
        if any(k in combined for k in ["degree type", "type of degree"]):
            return "bachelor"
        # Will you graduate
        if any(k in combined for k in ["graduate", "graduating", "expected graduation"]):
            return "yes"
        return None

    def _country_context(self, field_text: str = "") -> str:
        text = " ".join([
            field_text or "",
            str(self.job.get("location") or ""),
            str(self.job.get("description_raw") or "")[:1200],
            str(self.job.get("description_normalized") or "")[:1200],
        ]).lower()
        if any(k in text for k in ["united states", "u.s.", "usa", "us work", "work in the us", "work in us"]):
            return "us"
        if any(k in text for k in ["canada", "canadian", "calgary", "toronto", "vancouver", "montreal", "ottawa", "alberta", "ontario", "british columbia"]):
            return "canada"
        return "canada"

    def _click_next_if_present(self) -> bool:
        """Click a Next/Continue button if present. Returns True if clicked."""
        selectors = [
            "button:has-text('Next')",
            "button:has-text('Continue')",
            "button:has-text('Save and Continue')",
            "button:has-text('Save & Continue')",
            "button:has-text('Review')",
            "button:has-text('Review Application')",
            "button:has-text('Next Step')",
            "button:has-text('Next Page')",
            "input[value='Next']",
            "input[value='Continue']",
            "input[value='Save and Continue']",
            "input[value='Review']",
            "a:has-text('Next')",
        ]
        for sel in selectors:
            try:
                btn = self.page.query_selector(sel)
                if btn and btn.is_visible() and btn.is_enabled():
                    self._click_with_retry(btn, f"next:{sel}", attempts=2)
                    time.sleep(1.5)
                    self._log(f"Clicked next: {sel}")
                    return True
            except Exception:
                continue
        return False

    def _propose_value(self, name: str, placeholder: str, label: str, field_type: str) -> Optional[str]:
        combined = (name + " " + placeholder + " " + label).lower()
        country_context = self._country_context(combined)
        if any(k in combined for k in ["require sponsor", "need sponsor", "visa sponsor", "sponsorship"]):
            return "Yes" if country_context == "us" else "No"
        if any(k in combined for k in ["authorized", "work auth", "legally eligible", "eligible to work", "right to work"]):
            return "No" if country_context == "us" else "Yes"
        canonical_answer, needs_assistance = answer_for_label(combined)
        if needs_assistance:
            return None
        if canonical_answer:
            return canonical_answer
        if field_type == "email" or "email" in combined:
            return PROFILE["email"]
        if "phone" in combined or "tel" in combined or field_type == "tel":
            return PROFILE["phone"]
        if "first" in combined and "name" in combined:
            return PROFILE["firstName"]
        if "last" in combined and "name" in combined:
            return PROFILE["lastName"]
        if "full" in combined and "name" in combined:
            return PROFILE["fullName"]
        if combined.strip() in ("name", "yourname"):
            return PROFILE["fullName"]
        if "city" in combined:
            return PROFILE["city"]
        if "province" in combined or "state" in combined:
            return PROFILE["province"]
        if "country" in combined:
            return PROFILE["country"]
        if "linkedin" in combined:
            return f"https://{PROFILE['linkedin']}"
        if "github" in combined:
            return f"https://{PROFILE['github']}"
        if "twitter" in combined or "x.com" in combined:
            return ""
        if "portfolio" in combined or "website" in combined:
            return f"https://{PROFILE['portfolio']}"
        if "current company" in combined or "current employer" in combined:
            return "Alignerr (via Labelbox)"
        if "university" in combined or "school" in combined or "institution" in combined:
            return PROFILE["university"]
        if "graduation" in combined or "grad year" in combined:
            return PROFILE["graduation_year"]
        if "gpa" in combined or "grade point average" in combined:
            return PROFILE["gpa"]
        # "programming language" must come before "program" degree check
        if any(x in combined for x in ["programming language", "languages you", "languages proficient",
                                        "coding language", "technical skill", "tech stack", "skills you",
                                        "proficient in", "experience with languages"]):
            return "Python, Java, TypeScript, C++, SQL, Bash, Go"
        if "degree" in combined or ("program" in combined and "language" not in combined):
            return PROFILE["degree"]
        if "address" in combined and "email" not in combined:
            return "1401-4755 Dalton Dr, Calgary, AB T3A 2Z7"
        if "postal" in combined or "zip" in combined:
            return "T3A 2Z7"
        answer = answer_application_question(label or placeholder or name, self.job)
        if answer:
            return answer
        return None

    def detect_captcha(self, notify: bool = True) -> dict:
        """Check current page for CAPTCHA or robot-verification patterns."""
        if not self.page:
            return {"detected": False}
        try:
            content = self.page.content().lower()
            # Check visible text indicators
            found = [ind for ind in CAPTCHA_INDICATORS if ind in content]
            # Also check for captcha DOM elements (visible OR just present in DOM for iframe widgets)
            if not found:
                for sel in CAPTCHA_SELECTORS:
                    try:
                        el = self.page.query_selector(sel)
                        if el:
                            # Iframes can intercept clicks even when not "visible" per Playwright
                            # (e.g. hCaptcha invisible checkbox positioned over submit button)
                            is_iframe = el.evaluate("el => el.tagName.toLowerCase() === 'iframe'")
                            if is_iframe or el.is_visible():
                                found = [sel]
                                break
                    except Exception:
                        continue
            if found:
                self._log(f"CAPTCHA detected: {found}")
                self._screenshot("captcha_detected")
                # Send Telegram alert
                if notify:
                    try:
                        from engine.notifier import notify_captcha
                        notify_captcha(
                            job_title=self.job.get("title", ""),
                            company=self.job.get("company", ""),
                            url=self.page.url,
                            indicators=found,
                        )
                    except Exception as tg_err:
                        self._log(f"Telegram captcha alert failed: {tg_err}")
                return {"detected": True, "indicators": found, "url": self.page.url}
        except Exception as e:
            self._log(f"CAPTCHA check error: {e}")
        return {"detected": False}

    def detect_blocker(self, skip_captcha: bool = False, notify_captcha: bool = True) -> Optional[str]:
        if not self.page:
            return None
        try:
            if not skip_captcha and self.detect_captcha(notify=notify_captcha)["detected"]:
                return "captcha"
            url = self.page.url.lower()
            text = (self.page.locator("body").inner_text(timeout=2500) or "").lower()
            has_password = self.page.query_selector("input[type=password]") is not None
            if any(token in text for token in ["verify your email", "verification code", "check your email", "enter the code", "we sent a code"]):
                return "email_verification"
            if any(token in text for token in ["create an account", "create account", "register to apply", "sign up to apply"]):
                return "account_required"
            if has_password or any(token in url for token in ["login", "signin", "sign-in"]) or any(token in text for token in [
                "sign in to apply",
                "log in to apply",
                "user is not logged in",
                "unauthorized: user is not logged in",
            ]):
                return "login_required"
        except Exception:
            return None
        return None

    def _unknown_required_fields(self) -> list[str]:
        if not self.page:
            return []
        unknown: list[str] = []
        try:
            fields = self.page.query_selector_all("input:not([type=hidden]), textarea, select")
            for el in fields:
                try:
                    if not el.is_visible():
                        continue
                    required = (
                        el.get_attribute("required") is not None
                        or (el.get_attribute("aria-required") or "").lower() == "true"
                    )
                    if not required:
                        continue
                    field_type = (el.get_attribute("type") or "text").lower()
                    if field_type in ("checkbox", "radio", "file"):
                        continue
                    # input_value() reads live DOM value (works for textarea too);
                    # get_attribute("value") is static and always empty for textareas.
                    try:
                        value = el.input_value(timeout=800) or ""
                    except Exception:
                        value = el.get_attribute("value") or ""
                    if value.strip():
                        continue
                    label = self._get_label(el) or el.get_attribute("name") or el.get_attribute("placeholder") or "required field"
                    canonical = normalize_label(label)
                    if not canonical or canonical in SENSITIVE_KEYS:
                        unknown.append(label[:100])
                except Exception:
                    continue
        except Exception:
            pass
        return unknown

    def _page_signature(self) -> str:
        if not self.page:
            return ""
        try:
            return self.page.evaluate("""() => {
                const title = document.title || '';
                const h = document.querySelector('h1,h2,h3,[role=heading]');
                const fields = document.querySelectorAll('input:not([type=hidden]), textarea, select').length;
                return `${location.pathname}|${title}|${h ? h.innerText : ''}|${fields}`;
            }""")
        except Exception:
            return self.page.url if self.page else ""

    def _get_label(self, el) -> str:
        try:
            el_id = el.get_attribute("id")
            if el_id:
                label = self.page.query_selector(f"label[for='{el_id}']")
                if label:
                    return label.inner_text().strip()[:100]
            labelled_by = el.get_attribute("aria-labelledby") or ""
            for labelled_id in labelled_by.split():
                try:
                    labelled = self.page.query_selector(f"#{labelled_id}")
                    if labelled:
                        text = labelled.inner_text().strip()
                        if text:
                            return text[:100]
                except Exception:
                    continue
            aria = el.get_attribute("aria-label")
            if aria:
                return aria.strip()[:100]
            placeholder = el.get_attribute("placeholder")
            if placeholder:
                return placeholder.strip()[:100]
            nearby = el.evaluate("""el => {
                const label = el.closest('label');
                if (label && label.innerText) return label.innerText;
                const container = el.closest('[class*="field"], [class*="question"], [data-testid*="question"], div');
                if (!container) return '';
                const candidates = Array.from(container.querySelectorAll('label, p, span, div'))
                  .map(n => (n.innerText || '').trim())
                  .filter(t => t && t.length < 240);
                return candidates[0] || '';
            }""")
            if nearby:
                return str(nearby).strip()[:100]
        except Exception:
            pass
        return ""

    def _best_selector(self, el, field_id: str, name: str) -> str:
        if field_id:
            return f"#{field_id}"
        if name:
            return f"[name='{name}']"
        try:
            tag = el.evaluate("el => el.tagName.toLowerCase()")
            return tag  # "textarea", "select", "input"
        except Exception:
            return "input"

    def _dismiss_cookie_banner(self):
        if not self.page:
            return
        selectors = [
            "button:has-text('Accept All')",
            "button:has-text('Accept all')",
            "button:has-text('Allow all')",
            "button:has-text('Allow All')",
            "button:has-text('I agree')",
            "button:has-text('I Agree')",
            "button:has-text('Accept')",
            "button:has-text('Agree')",
            "[id*='accept']",
            "[aria-label*='accept']",
        ]
        for sel in selectors:
            try:
                btn = self.page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click(timeout=2000)
                    self._log(f"Dismissed cookie banner via {sel}")
                    time.sleep(1)
                    return
            except Exception:
                continue

    def _collect_fields(self) -> list[dict]:
        if not self.page:
            return []

        fields = []
        inputs = []
        for frame_index, scope in enumerate(self._scopes()):
            for el in scope.query_selector_all("input:not([type=hidden]), textarea, select"):
                inputs.append((frame_index, el))
        for frame_index, el in inputs:
            try:
                field_type = el.get_attribute("type") or "text"
                name = el.get_attribute("name") or ""
                placeholder = el.get_attribute("placeholder") or ""
                label_text = self._get_label(el)
                field_id = el.get_attribute("id") or ""
                required = (
                    el.get_attribute("required") is not None
                    or (el.get_attribute("aria-required") or "").lower() == "true"
                )

                proposed = self._propose_value(name, placeholder, label_text, field_type)
                canonical_key = normalize_label(" ".join([name, placeholder, label_text]))
                fields.append({
                    "selector": self._best_selector(el, field_id, name),
                    "frame_index": frame_index,
                    "type": field_type,
                    "name": name,
                    "label": label_text or placeholder or name,
                    "required": required,
                    "canonical_key": canonical_key,
                    "requires_assistance": canonical_key in SENSITIVE_KEYS,
                    "proposed_value": proposed,
                    "can_autofill": proposed is not None and field_type in ("text", "email", "tel", "url"),
                    "is_file": field_type == "file",
                    "is_sensitive": field_type in ("password", "radio", "checkbox") or canonical_key in SENSITIVE_KEYS,
                })
            except Exception:
                continue
        return fields

    def _navigate_greenhouse_embed(self) -> bool:
        """
        Detect a Greenhouse embed iframe and navigate directly to its src URL
        so we fill the actual application form rather than the outer marketing page.
        Retries up to 3s waiting for the iframe to appear after JS renders it.
        Returns True if successfully navigated.
        """
        if not self.page:
            return False
        EMBED_SELECTORS = [
            "iframe[src*='embed.greenhouse.io']",
            "iframe[src*='boards.greenhouse.io/embed']",
            "iframe[id='grnhse_iframe']",
            "iframe[name*='greenhouse']",
        ]
        deadline = time.time() + 3.0
        while time.time() < deadline:
            for sel in EMBED_SELECTORS:
                try:
                    embed = self.page.query_selector(sel)
                    if embed:
                        src = embed.get_attribute("src") or ""
                        if src and src.startswith("http"):
                            self._log(f"Greenhouse embed iframe → navigating to: {src[:100]}")
                            self.page.goto(src, wait_until="domcontentloaded", timeout=30000)
                            time.sleep(2)
                            return True
                except Exception:
                    continue
            time.sleep(0.5)
        return False

    def _maybe_open_application_form(self):
        if not self.page:
            return

        if self.job.get("portal") == "lever" and not self.page.url.rstrip("/").endswith("/apply"):
            try:
                apply_url = self.page.url.rstrip("/") + "/apply"
                self.page.goto(apply_url, wait_until="domcontentloaded", timeout=20000)
                self._log(f"Opened application form via direct Lever apply URL: {apply_url}")
                time.sleep(2)
                return
            except Exception:
                pass

        selectors = [
            "a[href*='/apply']",
            "a:has-text('Apply for this job')",
            "button:has-text('Apply for this job')",
            "a:has-text('Apply now')",
            "button:has-text('Apply now')",
            "a:has-text('Apply')",
            "button:has-text('Apply')",
            "a:has-text('Submit application')",
            "button:has-text('Submit application')",
        ]
        for sel in selectors:
            try:
                el = self.page.query_selector(sel)
                if el and el.is_visible():
                    href = el.get_attribute("href") or ""
                    current_url = self.page.url
                    is_workday = "workday" in current_url.lower()
                    if href:
                        target = href if href.startswith("http") else urljoin(current_url, href)
                        wait_cond = "networkidle" if is_workday else "domcontentloaded"
                        self.page.goto(target, wait_until=wait_cond, timeout=45000)
                        self._log(f"Opened application form via {sel}: {target}")
                    else:
                        el.click(timeout=4000)
                        self._log(f"Opened application form via {sel}")
                    wait_secs = 5 if is_workday else 2
                    time.sleep(wait_secs)
                    # After clicking Apply, check for Greenhouse embed iframe and navigate into it
                    if self._navigate_greenhouse_embed():
                        return
                    return
            except Exception:
                continue
        # Last-chance: detect Greenhouse embed even without an explicit Apply button
        self._navigate_greenhouse_embed()

    def _screenshot(self, label: str) -> str:
        try:
            path = SCREENSHOTS_DIR / f"{self.session_id[:8]}_{label}_{int(time.time())}.png"
            self.page.screenshot(path=str(path))
            self.last_screenshot_path = str(path)
            return str(path)
        except Exception:
            return ""

    # ── LinkedIn Easy Apply ───────────────────────────────────────────────────

    def _linkedin_login(self, email: str, password: str) -> bool:
        """Log in to LinkedIn. Returns True on success."""
        try:
            self.page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
            self.page.fill("#username", email, timeout=5000)
            self.page.fill("#password", password, timeout=5000)
            self.page.click("button[type=submit]", timeout=5000)
            self.page.wait_for_load_state("networkidle", timeout=15000)
            if "feed" in self.page.url or "mynetwork" in self.page.url or "jobs" in self.page.url:
                self._log("LinkedIn login successful")
                return True
            if "checkpoint" in self.page.url or "challenge" in self.page.url:
                self._log("LinkedIn security checkpoint — needs human")
                return False
            self._log(f"LinkedIn login unclear: {self.page.url}")
            return "linkedin.com" in self.page.url
        except Exception as exc:
            self._log(f"LinkedIn login error: {exc}")
            return False

    def _linkedin_fill_easy_apply_modal(self) -> dict:
        """
        Fill the LinkedIn Easy Apply modal. Handles multi-step forms.
        Returns {ok, blocker}.
        """
        resume_path = self.artifacts.get("resume_pdf_path", "")
        max_steps = 12

        for step in range(max_steps):
            time.sleep(1.5)
            page_text = self.page.inner_text("body").lower()

            # Confirm success
            if any(s in page_text for s in [
                "application submitted", "your application was sent",
                "you applied", "application was sent",
            ]):
                self._log("LinkedIn Easy Apply: application submitted")
                return {"ok": True}

            # CAPTCHA check
            if any(s in page_text for s in CAPTCHA_INDICATORS):
                return {"ok": False, "blocker": "captcha"}

            # Upload resume if file input present
            try:
                file_inputs = self.page.query_selector_all("input[type=file]")
                for fi in file_inputs:
                    if fi.is_visible() and resume_path and Path(resume_path).exists():
                        fi.set_input_files(resume_path)
                        self._log(f"LinkedIn Easy Apply: uploaded resume (step {step+1})")
                        time.sleep(1)
            except Exception:
                pass

            # Fill all text/select fields in modal
            try:
                modal = self.page.query_selector("[data-test-modal], .jobs-easy-apply-modal, [role=dialog]")
                scope = modal if modal else self.page
                for inp in scope.query_selector_all("input:not([type=hidden]):not([type=file]), textarea, select"):
                    try:
                        if not inp.is_visible():
                            continue
                        label = self._get_label(inp)
                        field_type = inp.get_attribute("type") or "text"
                        if field_type in ("checkbox", "radio"):
                            continue
                        answer, is_sensitive = answer_for_label(label)
                        if not answer:
                            name = inp.get_attribute("name") or ""
                            ph = inp.get_attribute("placeholder") or ""
                            answer, is_sensitive = answer_for_label(ph or name)
                        if is_sensitive:
                            continue
                        if answer and field_type not in ("file",):
                            tag = inp.evaluate("el => el.tagName.toLowerCase()")
                            if tag == "select":
                                try:
                                    inp.select_option(value=answer, timeout=2000)
                                except Exception:
                                    try:
                                        inp.select_option(label=answer, timeout=2000)
                                    except Exception:
                                        pass
                            else:
                                inp.fill("", timeout=2000)
                                inp.fill(answer, timeout=2000)
                    except Exception:
                        continue

                # Handle Yes/No radio/select questions
                for question_el in scope.query_selector_all("[data-test-form-element], .fb-form-element"):
                    try:
                        q_text = (question_el.inner_text() or "").lower()
                        answer, sensitive = answer_for_label(q_text[:120])
                        if sensitive or not answer:
                            continue
                        # Try radio buttons
                        yes_val = answer.lower()
                        radios = question_el.query_selector_all("input[type=radio]")
                        for radio in radios:
                            val = (radio.get_attribute("value") or "").lower()
                            rid = radio.get_attribute("id") or ""
                            if val == yes_val or yes_val in val or yes_val in rid.lower():
                                radio.check(timeout=2000)
                                break
                    except Exception:
                        continue
            except Exception as exc:
                self._log(f"LinkedIn fill step {step+1} error: {exc}")

            # Try Next / Continue / Review / Submit buttons
            clicked = False
            for btn_text in ["Submit application", "Review", "Next", "Continue", "Done"]:
                try:
                    btn = self.page.query_selector(f"button:has-text('{btn_text}')")
                    if btn and btn.is_visible() and not btn.is_disabled():
                        btn.click(timeout=5000)
                        self._log(f"LinkedIn Easy Apply: clicked '{btn_text}' (step {step+1})")
                        clicked = True
                        time.sleep(2)
                        break
                except Exception:
                    continue

            if not clicked:
                # Might have already submitted or modal closed
                break

        # Final confirmation check
        time.sleep(2)
        final_text = self.page.inner_text("body").lower()
        if any(s in final_text for s in ["application submitted", "your application was sent", "you applied"]):
            return {"ok": True}
        return {"ok": False, "blocker": "linkedin_incomplete"}

    def linkedin_easy_apply_full(self, email: str, password: str) -> dict:
        """
        Full LinkedIn Easy Apply pipeline: login → navigate to job → click Easy Apply → fill → submit.
        Returns {ok, blocker, screenshot_path}.
        """
        import asyncio
        try:
            asyncio.set_event_loop(asyncio.new_event_loop())
        except Exception:
            pass
        from playwright.sync_api import sync_playwright

        job_url = self.job.get("url", "")
        if not job_url or "linkedin.com" not in job_url.lower():
            return {"ok": False, "blocker": "not_linkedin_url"}

        self._pw = sync_playwright().start()
        # Persistent context to reuse LinkedIn session across runs
        profile_dir = BASE_DIR / "storage" / "browser_profiles" / "linkedin"
        profile_dir.mkdir(parents=True, exist_ok=True)
        ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=self.headless,
            slow_mo=200,
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        self.browser = ctx
        self.page = ctx.new_page()

        try:
            # Check if already logged in
            self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=20000)
            time.sleep(2)
            if "login" in self.page.url or "authwall" in self.page.url:
                if not self._linkedin_login(email, password):
                    return {"ok": False, "blocker": "linkedin_login_failed"}

            # Navigate to job
            self.page.goto(job_url, wait_until="networkidle", timeout=30000)
            time.sleep(3)
            self._dismiss_cookie_banner()

            page_text = self.page.inner_text("body").lower()
            if "easy apply" not in page_text:
                return {"ok": False, "blocker": "no_easy_apply_button"}

            # Click Easy Apply
            clicked = False
            for sel in [
                "button.jobs-apply-button:has-text('Easy Apply')",
                "button:has-text('Easy Apply')",
                ".jobs-s-apply button",
                "[data-control-name='jobdetails_topcard_inapply']",
            ]:
                try:
                    btn = self.page.query_selector(sel)
                    if btn and btn.is_visible():
                        btn.click(timeout=5000)
                        clicked = True
                        time.sleep(2)
                        break
                except Exception:
                    continue

            if not clicked:
                return {"ok": False, "blocker": "easy_apply_button_not_found"}

            self._log("LinkedIn Easy Apply modal opened")
            result = self._linkedin_fill_easy_apply_modal()
            ss = self._screenshot("linkedin_easy_apply_result")
            return {**result, "screenshot_path": ss}
        except Exception as exc:
            ss = self._screenshot("linkedin_error")
            return {"ok": False, "blocker": "exception", "error": str(exc), "screenshot_path": ss}
        finally:
            try:
                ctx.close()
            except Exception:
                pass
            try:
                self._pw.stop()
            except Exception:
                pass

    # ── Indeed Easy Apply ─────────────────────────────────────────────────────

    def _indeed_login(self, email: str, password: str) -> bool:
        """Log in to Indeed. Returns True on success."""
        try:
            self.page.goto("https://secure.indeed.com/account/login", wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
            # Fill email
            for sel in ["#login-email-input", "input[name=email]", "input[type=email]"]:
                try:
                    el = self.page.query_selector(sel)
                    if el and el.is_visible():
                        el.fill(email, timeout=3000)
                        break
                except Exception:
                    continue
            # Submit email step
            for sel in ["button[type=submit]", "button:has-text('Continue')", "button:has-text('Sign in')"]:
                try:
                    btn = self.page.query_selector(sel)
                    if btn and btn.is_visible():
                        btn.click(timeout=3000)
                        break
                except Exception:
                    continue
            time.sleep(2)
            # Fill password
            for sel in ["#login-password-input", "input[type=password]", "input[name=password]"]:
                try:
                    el = self.page.query_selector(sel)
                    if el and el.is_visible():
                        el.fill(password, timeout=3000)
                        break
                except Exception:
                    continue
            for sel in ["button[type=submit]", "button:has-text('Sign in')", "button:has-text('Log in')"]:
                try:
                    btn = self.page.query_selector(sel)
                    if btn and btn.is_visible():
                        btn.click(timeout=3000)
                        break
                except Exception:
                    continue
            self.page.wait_for_load_state("networkidle", timeout=15000)
            time.sleep(2)
            if "indeed.com" in self.page.url and "login" not in self.page.url:
                self._log("Indeed login successful")
                return True
            self._log(f"Indeed login unclear: {self.page.url}")
            return False
        except Exception as exc:
            self._log(f"Indeed login error: {exc}")
            return False

    def _indeed_fill_apply_form(self) -> dict:
        """Fill Indeed's apply form/modal. Handles multi-step."""
        resume_path = self.artifacts.get("resume_pdf_path", "")
        max_steps = 15

        for step in range(max_steps):
            time.sleep(1.5)
            try:
                page_text = self.page.inner_text("body").lower()
            except Exception:
                break

            if any(s in page_text for s in [
                "application submitted", "your application has been submitted",
                "successfully submitted", "thank you for applying",
                "application received", "you applied",
            ]):
                self._log("Indeed: application submitted")
                return {"ok": True}

            if any(s in page_text for s in CAPTCHA_INDICATORS):
                return {"ok": False, "blocker": "captcha"}

            # Upload resume
            try:
                for fi in self.page.query_selector_all("input[type=file]"):
                    if fi.is_visible() and resume_path and Path(resume_path).exists():
                        fi.set_input_files(resume_path)
                        self._log(f"Indeed: uploaded resume step {step+1}")
                        time.sleep(1)
            except Exception:
                pass

            # Fill text fields
            try:
                for inp in self.page.query_selector_all(
                    "input:not([type=hidden]):not([type=file]):not([type=radio]):not([type=checkbox]), textarea, select"
                ):
                    try:
                        if not inp.is_visible():
                            continue
                        label = self._get_label(inp)
                        field_type = inp.get_attribute("type") or "text"
                        answer, sensitive = answer_for_label(label)
                        if not answer:
                            ph = inp.get_attribute("placeholder") or inp.get_attribute("name") or ""
                            answer, sensitive = answer_for_label(ph)
                        if sensitive or not answer:
                            continue
                        tag = inp.evaluate("el => el.tagName.toLowerCase()")
                        if tag == "select":
                            try:
                                inp.select_option(value=answer, timeout=2000)
                            except Exception:
                                try:
                                    inp.select_option(label=answer, timeout=2000)
                                except Exception:
                                    pass
                        else:
                            existing = inp.input_value() if field_type != "file" else ""
                            if not existing:
                                inp.fill(answer, timeout=2000)
                    except Exception:
                        continue
            except Exception as exc:
                self._log(f"Indeed fill step {step+1}: {exc}")

            # Click Yes on yes/no questions
            try:
                for radio in self.page.query_selector_all("input[type=radio]"):
                    try:
                        if not radio.is_visible():
                            continue
                        val = (radio.get_attribute("value") or "").lower()
                        if val in ("yes", "true", "1"):
                            label_el = self.page.query_selector(f"label[for='{radio.get_attribute('id')}']")
                            label_text = label_el.inner_text() if label_el else ""
                            answer, sensitive = answer_for_label(label_text)
                            if not sensitive and answer and answer.lower() in ("yes", "true"):
                                radio.check(timeout=2000)
                    except Exception:
                        continue
            except Exception:
                pass

            # Advance form
            clicked = False
            for btn_text in ["Submit your application", "Submit application", "Submit", "Continue", "Next", "Review"]:
                try:
                    btn = self.page.query_selector(f"button:has-text('{btn_text}')")
                    if btn and btn.is_visible() and not btn.is_disabled():
                        btn.click(timeout=5000)
                        self._log(f"Indeed: clicked '{btn_text}' step {step+1}")
                        clicked = True
                        time.sleep(2)
                        break
                except Exception:
                    continue

            if not clicked:
                break

        time.sleep(2)
        final = self.page.inner_text("body").lower()
        if any(s in final for s in ["application submitted", "thank you for applying", "you applied"]):
            return {"ok": True}
        return {"ok": False, "blocker": "indeed_incomplete"}

    def indeed_easy_apply_full(self, email: str, password: str) -> dict:
        """
        Full Indeed Easy Apply pipeline: login → navigate → click Apply → fill → submit.
        """
        import asyncio
        try:
            asyncio.set_event_loop(asyncio.new_event_loop())
        except Exception:
            pass
        from playwright.sync_api import sync_playwright

        job_url = self.job.get("url", "")
        if not job_url or "indeed.com" not in job_url.lower():
            return {"ok": False, "blocker": "not_indeed_url"}

        self._pw = sync_playwright().start()
        profile_dir = BASE_DIR / "storage" / "browser_profiles" / "indeed"
        profile_dir.mkdir(parents=True, exist_ok=True)
        ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=self.headless,
            slow_mo=200,
            viewport={"width": 1280, "height": 900},
        )
        self.browser = ctx
        self.page = ctx.new_page()

        try:
            self.page.goto("https://www.indeed.com/", wait_until="domcontentloaded", timeout=20000)
            time.sleep(1)
            page_text = self.page.inner_text("body").lower()
            is_logged_in = "sign in" not in page_text and "my jobs" in page_text
            if not is_logged_in:
                if not self._indeed_login(email, password):
                    return {"ok": False, "blocker": "indeed_login_failed"}

            self.page.goto(job_url, wait_until="networkidle", timeout=30000)
            time.sleep(3)
            self._dismiss_cookie_banner()

            # Click Apply / Easily Apply
            clicked = False
            for sel in [
                "button:has-text('Apply now')",
                "button:has-text('Easily apply')",
                "button:has-text('Apply')",
                "a:has-text('Apply now')",
                ".ia-IndeedApplyButton",
                "#indeedApplyButton",
                "[data-testid='applyButton']",
            ]:
                try:
                    btn = self.page.query_selector(sel)
                    if btn and btn.is_visible():
                        btn.click(timeout=5000)
                        clicked = True
                        time.sleep(2)
                        break
                except Exception:
                    continue

            if not clicked:
                return {"ok": False, "blocker": "no_apply_button"}

            # Handle popup/new tab
            try:
                self.page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                time.sleep(3)

            result = self._indeed_fill_apply_form()
            ss = self._screenshot("indeed_apply_result")
            return {**result, "screenshot_path": ss}
        except Exception as exc:
            ss = self._screenshot("indeed_error")
            return {"ok": False, "blocker": "exception", "error": str(exc), "screenshot_path": ss}
        finally:
            try:
                ctx.close()
            except Exception:
                pass
            try:
                self._pw.stop()
            except Exception:
                pass


# ── Session management ────────────────────────────────────────────────────────

def create_session(job: dict, artifacts: dict, headless: bool = False, keep_open_on_blocker: bool = False) -> str:
    session_id = str(uuid.uuid4())
    session = BrowserSession(session_id, job, artifacts, headless, keep_open_on_blocker=keep_open_on_blocker)
    _active_sessions[session_id] = session
    return session_id


def get_session(session_id: str) -> Optional[BrowserSession]:
    return _active_sessions.get(session_id)


def close_session(session_id: str):
    session = _active_sessions.pop(session_id, None)
    if session:
        session.close()


def dry_parse_application(job: dict, headless: bool = True) -> dict:
    """
    Open and inspect an application page without submitting.
    Returns blocker/form complexity data for queue eligibility decisions.
    """
    policy = classify_portal(job)
    if policy["automation_tier"] in ("manual", "skip"):
        return {
            "ok": False,
            "blocker": "unsupported_portal" if policy["automation_tier"] == "manual" else "unsupported_portal",
            "field_count": 0,
            "has_resume_upload": False,
            "has_cover_upload": False,
            "steps_estimated": 0,
            "recommended_mode": policy["automation_tier"],
            "reason": policy["reason"],
        }

    session = BrowserSession(str(uuid.uuid4()), job, artifacts={}, headless=headless)
    try:
        start = session.start()
        if not start.get("ok"):
            return {
                "ok": False,
                "blocker": "page_load",
                "field_count": 0,
                "has_resume_upload": False,
                "has_cover_upload": False,
                "steps_estimated": 0,
                "recommended_mode": "assisted",
                "reason": start.get("error", "Could not open page"),
            }

        if not session._collect_fields():
            session._maybe_open_application_form()

        blocker = session.detect_blocker(notify_captcha=False)
        fields = session._collect_fields()
        field_count = len(fields)
        upload_fields = [f for f in fields if f.get("is_file")]
        upload_text = " ".join((f.get("label", "") + " " + f.get("name", "")).lower() for f in upload_fields)
        has_resume_upload = bool(upload_fields) and ("resume" in upload_text or "cv" in upload_text or len(upload_fields) == 1)
        has_cover_upload = "cover" in upload_text
        next_buttons = 0
        submit_buttons = 0
        try:
            next_buttons = session.page.locator(
                "button:has-text('Next'), button:has-text('Continue'), button:has-text('Review'), input[value*='Next'], input[value*='Continue']"
            ).count()
            submit_buttons = session.page.locator(
                "button:has-text('Submit'), button:has-text('Apply'), input[type=submit]"
            ).count()
        except Exception:
            pass

        dry = {
            "ok": blocker is None,
            "blocker": blocker,
            "field_count": field_count,
            "has_resume_upload": has_resume_upload,
            "has_cover_upload": has_cover_upload,
            "steps_estimated": max(1, min(8, next_buttons + (1 if submit_buttons else 0))),
        }
        viability = calculate_viability(job, dry_parse=dry)
        recommended = "auto" if viability["score"] >= 85 and policy["should_auto_apply"] else "assisted" if viability["score"] >= 50 else "skip"
        return {
            **dry,
            "recommended_mode": recommended,
            "viability": viability,
            "current_url": session.page.url if session.page else "",
        }
    finally:
        session.close()
