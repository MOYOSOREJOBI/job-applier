import csv
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.apply.submit_policy import (  # noqa: E402
    ASSISTED_REVIEW,
    MANUAL_ONLY,
    SAFE_AUTO_SUBMIT,
    can_submit_automatically,
    status_for_policy_decision,
)
from engine.campaign_runner import _domain_is_penalized, export_coop_proof_log  # noqa: E402


class SubmitPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.artifacts = {
            "resume_pdf": str(base / "resume.pdf"),
            "cover_pdf": str(base / "cover_letter.pdf"),
            "answer_pack": str(base / "answers.json"),
        }
        Path(self.artifacts["resume_pdf"]).write_text("resume")
        Path(self.artifacts["cover_pdf"]).write_text("cover")
        Path(self.artifacts["answer_pack"]).write_text("{}")
        self.answers = {
            "answers": {
                "work_authorization": "I am authorized to work in Canada.",
                "salary_expectation": "$25-35 per hour depending on scope.",
                "relocation": "I am flexible for the right role.",
                "remote_hybrid": "I am flexible across hybrid and remote.",
            }
        }
        self.job = {
            "id": "job1",
            "company": "Example",
            "title": "Software Engineer Intern",
            "location": "Remote Canada",
            "url": "https://jobs.lever.co/example/1",
            "portal": "lever",
            "score": 88,
        }

    def tearDown(self):
        self.tmp.cleanup()

    def decide(self, **overrides):
        job = {**self.job, **overrides.pop("job", {})}
        return can_submit_automatically(
            job,
            overrides.pop("page_state", {}),
            overrides.pop("artifacts", self.artifacts),
            overrides.pop("answers", self.answers),
            overrides.pop("domain_memory", {}),
        )

    def test_linkedin_is_always_manual_only(self):
        decision = self.decide(job={"portal": "linkedin", "url": "https://linkedin.com/jobs/view/1"})
        self.assertEqual(decision["mode"], MANUAL_ONLY)
        self.assertEqual(decision["reason"], "manual_only_platform")

    def test_indeed_is_always_manual_only(self):
        decision = self.decide(job={"portal": "indeed", "url": "https://indeed.com/viewjob?jk=1"})
        self.assertEqual(decision["mode"], MANUAL_ONLY)
        self.assertEqual(decision["reason"], "manual_only_platform")

    def test_captcha_blocks_auto_submit(self):
        decision = self.decide(page_state={"captcha": True})
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "captcha_detected")

    def test_login_wall_blocks_auto_submit(self):
        decision = self.decide(page_state={"blocker": "login_required"})
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "login_required")

    def test_manual_attestation_blocks_auto_submit(self):
        decision = self.decide(page_state={"fields": [{"type": "checkbox", "required": True, "label": "I certify this information is accurate"}]})
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "manual_attestation_required")

    def test_unknown_required_question_blocks_auto_submit(self):
        decision = self.decide(page_state={"unknown_required_fields": ["Custom required question"]})
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "unknown_required_questions")

    def test_missing_resume_blocks_auto_submit(self):
        artifacts = {**self.artifacts, "resume_pdf": ""}
        decision = self.decide(artifacts=artifacts)
        self.assertEqual(decision["reason"], "missing_resume_pdf")

    def test_missing_cover_letter_blocks_auto_submit(self):
        artifacts = {**self.artifacts, "cover_pdf": ""}
        decision = self.decide(artifacts=artifacts)
        self.assertEqual(decision["reason"], "missing_cover_letter_pdf")

    def test_low_score_blocks_auto_submit(self):
        decision = self.decide(job={"score": 79})
        self.assertEqual(decision["reason"], "job_score_too_low")

    def test_lever_clean_application_allows_safe_auto_submit(self):
        decision = self.decide()
        self.assertTrue(decision["allowed"])
        self.assertEqual(decision["mode"], SAFE_AUTO_SUBMIT)

    def test_ashby_clean_application_allows_safe_auto_submit(self):
        decision = self.decide(job={"portal": "ashby", "url": "https://jobs.ashbyhq.com/example/1"})
        self.assertTrue(decision["allowed"])
        self.assertEqual(decision["mode"], SAFE_AUTO_SUBMIT)

    def test_greenhouse_requires_official_complete_api_path(self):
        blocked = self.decide(job={"portal": "greenhouse", "url": "https://boards.greenhouse.io/example/jobs/1"})
        self.assertFalse(blocked["allowed"])
        self.assertEqual(blocked["reason"], "official_api_not_available")
        allowed = self.decide(
            job={"portal": "greenhouse", "url": "https://boards.greenhouse.io/example/jobs/1"},
            page_state={"official_application_api": True, "questions_complete": True},
        )
        self.assertTrue(allowed["allowed"])

    def test_workday_defaults_to_assisted_review(self):
        decision = self.decide(job={"portal": "workday", "url": "https://example.myworkdayjobs.com/job/1"})
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["mode"], ASSISTED_REVIEW)

    def test_batch_2_avoids_domains_that_failed_in_batch_1(self):
        with patch("engine.campaign_runner.get_domain_memory", return_value={"fail_count": 2, "success_count": 0, "captcha_count": 0}):
            self.assertTrue(_domain_is_penalized(self.job))

    def test_csv_proof_log_exports_correctly(self):
        row = {
            "date": "2026-04-21",
            "company": "Example",
            "title": "Software Engineer Intern",
            "location": "Remote Canada",
            "portal": "lever",
            "job_url": "https://jobs.lever.co/example/1",
            "score": 88,
            "mode": SAFE_AUTO_SUBMIT,
            "status": "SAFE_AUTO_SUBMITTED",
            "submit_time": "2026-04-21T00:00:00Z",
            "block_reason": "",
            "resume_path": "resume.pdf",
            "cover_letter_path": "cover_letter.pdf",
            "answer_pack_path": "answers.json",
            "screenshot_path": "",
            "notes": "",
        }
        path = export_coop_proof_log([row], "test-run")
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]["company"], "Example")
        self.assertEqual(rows[0]["status"], "SAFE_AUTO_SUBMITTED")
        Path(path).unlink(missing_ok=True)
        (ROOT / "logs" / "coop_emergency_latest.csv").unlink(missing_ok=True)

    def test_review_queue_contains_assisted_and_manual_jobs(self):
        assisted = status_for_policy_decision({"allowed": False, "mode": ASSISTED_REVIEW, "reason": "unsupported_portal"})
        manual = status_for_policy_decision({"allowed": False, "mode": MANUAL_ONLY, "reason": "manual_only_platform"})
        self.assertEqual(assisted, "READY_FOR_REVIEW")
        self.assertEqual(manual, "MANUAL_ONLY")


if __name__ == "__main__":
    unittest.main()
