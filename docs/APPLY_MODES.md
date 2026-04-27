# Apply Modes

## Overview

Every job has an `apply_mode` that determines how the system can assist:

| Mode | What it means |
|---|---|
| `SAFE_AUTO_SUBMIT` | Central policy allows automatic submit after strict checks |
| `ASSISTED_REVIEW` | Browser opens, safe known fields are filled, files are uploaded, screenshot is saved, and the system stops before submit |
| `MANUAL_ONLY` | Artifacts are generated and the job is queued for manual handling; no submit automation |

All submit paths must call `can_submit_automatically(job, page_state, artifacts, answers, domain_memory)` before automatic submission.

## Mode 1: SAFE_AUTO_SUBMIT

Allowed only for clean Lever, Ashby, simple company forms, and future verified official application API paths. Greenhouse requires a verified official application endpoint with complete known questions and no CAPTCHA/login/manual confirmation requirement.

Required before auto-submit:
- Score >= 80
- No CAPTCHA, bot challenge, login, account creation, or email verification
- No unknown required questions
- No required manual attestation/certification checkbox
- Resume PDF, cover letter PDF, and answer pack exist
- Work authorization, location, and salary questions are known when required
- Domain has no recent failure/CAPTCHA history

## Mode 2: ASSISTED_REVIEW

Used for Greenhouse when not API-safe, Workday, Amazon, Microsoft, Oracle, Taleo, SuccessFactors, custom portals, and complex forms.

**Workflow (10 steps):**

1. Click **ASSIST APPLY** on a job in the UI
2. Browser opens visibly on the job application page
3. System scans all form fields
4. For each text/email/phone/URL field: system proposes a value from your profile
5. System fills all safe (non-sensitive) fields automatically
6. Resume PDF is uploaded to file input if found
7. System takes a screenshot for review
8. **You review the browser window** — check every field, fix anything wrong
9. System saves a screenshot and places the job in the review queue
10. You review and submit manually in the browser/site when appropriate

**What is NEVER auto-filled without review:**
- Checkboxes, radio buttons (sensitive)
- Password fields
- Work authorization questions
- Salary fields
- Custom essay questions

## Mode 3: MANUAL_ONLY

Used for LinkedIn, Indeed, Glassdoor, blocked sources, login walls, CAPTCHA, account creation, and unknown required question flows. The system saves the job, generates tailored artifacts, and puts it in the manual queue.

## Auto-Safe Portals

Batch auto-apply only queues jobs that pass viability scoring and dry-parse checks. CAPTCHA, login, email verification, account creation, unknown required fields, unsupported portals, and manual-review outcomes pause the queue and mark the job for assistance.

Lever, Ashby, and simple forms are eligible when clean. Greenhouse is assisted unless a verified official API path is available and all questions are complete.

## Extra Checkpoints: Workday, iCIMS

Same assisted workflow, but with extra wait states for multi-page forms. Field mapping may be less complete on these portals.

## Tier C: PREP_ONLY (GitHub repo, text import)

System generates your resume PDF, cover letter, and answer pack. You apply manually using these artifacts. No browser automation.

## LinkedIn: BLOCKED

LinkedIn is permanently disabled. The system:
- Does not run LinkedIn automation
- Blocks any `linkedin.com` URL at import
- Returns an error if assist-apply is attempted on a LinkedIn URL
- Shows permanent warning banners in the UI

Apply on linkedin.com yourself. Use the generated PDFs and answer pack.

## Screenshot Archive

After each browser session, screenshots are saved to `logs/screenshots/`:
- `{session_id_prefix}_after_fill_{ts}.png` — state after auto-fill
- `{session_id_prefix}_review_{ts}.png` — state at review gate
- `{session_id_prefix}_before_submit_{ts}.png` — just before click
- `{session_id_prefix}_after_submit_{ts}.png` — confirmation page
- `{session_id_prefix}_open_failed_{ts}.png` — if page load fails
