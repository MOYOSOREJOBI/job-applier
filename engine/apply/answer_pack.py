"""
Truth-based application answer pack and label normalization.

Sensitive demographic questions are not answered automatically. If a required
field normalizes to one of those keys, the apply engine moves the job to
assisted review so the user can answer manually.
"""
from __future__ import annotations

from pathlib import Path
from engine.profile_loader import load_profile

_TRUTH = load_profile()
_IDENTITY = _TRUTH.get("identity", {})
_EDUCATION = _TRUTH.get("education", {})
_AVAILABILITY = _TRUTH.get("availability", {})
_COMPENSATION = _TRUTH.get("compensation", {})
_AUTH = _TRUTH.get("work_authorization", {})
_BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Transcript PDF path (January 2026 version)
_TRANSCRIPT_CANDIDATES = (
    _BASE_DIR / "config" / "transcript_jan2026.pdf",
    _BASE_DIR.parent / "restored-history" / "transcripts" / "transcript_jan2026.pdf",
)

CANONICAL_ANSWERS: dict[str, str] = {
    # ── Identity ────────────────────────────────────────────────────────────
    "first_name":         _IDENTITY.get("first_name", "Moyosore"),
    "last_name":          _IDENTITY.get("last_name", "Ogunjobi"),
    "full_name":          _IDENTITY.get("name", "Moyosore Ogunjobi"),
    "email":              _IDENTITY.get("email", "moyosorejobi@gmail.com"),
    "phone":              _IDENTITY.get("phone", "825-736-5656"),
    "city":               "Calgary",
    "province":           "Alberta",
    "country":            "Canada",
    "address_line1":      "Calgary, AB, Canada",
    "address_full":       "Calgary, AB, Canada",
    "postal_code":        "T3A 2Z7",

    # ── Education ────────────────────────────────────────────────────────────
    "school":             _EDUCATION.get("school", "University of Calgary"),
    "university":         _EDUCATION.get("school", "University of Calgary"),
    "degree":             _EDUCATION.get("degree", "BSc Software Engineering"),
    "major":              "Software Engineering",
    "field_of_study":     "Software Engineering",
    "gpa":                _EDUCATION.get("gpa", "3.45"),
    "gpa_scale":          "4.0",
    "graduation_date":    _EDUCATION.get("graduation", "May 2027"),
    "graduation_year":    "2027",
    "enrollment_status":  "Full-time",
    "year_of_study":      "3rd Year",

    # ── Work authorization ────────────────────────────────────────────────────
    "work_authorized_canada":    "Yes",
    "needs_sponsorship_canada":  "No",
    "work_authorized_us":        "No",
    "needs_sponsorship_us":      "Yes",
    "citizen_or_pr_canada":      "No",
    "permanent_resident_canada": "No",
    "student_visa":              "Yes",
    "right_to_work":             "Yes",

    # ── Links / Profiles ─────────────────────────────────────────────────────
    "linkedin_url":   "https://linkedin.com/in/moyosore-ogunjobi-b187b8205",
    "github_url":     "https://github.com/MOYOSOREJOBI",
    "portfolio_url":  "https://moyosore.dev",
    "website_url":    "https://moyosore.dev",

    # ── Availability & Compensation ───────────────────────────────────────────
    "start_date":               _AVAILABILITY.get("target_start", "May 2026 or June 2026"),
    "internship_availability":  _AVAILABILITY.get("internship_availability",
        "Available May 2026 or June 2026 for a Summer 2026 internship or co-op."),
    "term_availability":        "Summer 2026 (May or June start)",
    "hours_per_week":           "40",
    "part_time_full_time":      "Full-time",
    "salary_expectation":       _COMPENSATION.get("salary_expectation",
        "$25–35+ per hour depending on scope, location, and total compensation."),
    "hourly_rate":              "$28–35",
    "willing_to_relocate":      "Yes",
    "remote_preference":        "Open to remote, hybrid, or in-person",

    # ── Experience level ──────────────────────────────────────────────────────
    "years_of_experience":      "1",
    "experience_level":         "Entry Level / Internship",
    "seniority":                "Intern / Entry Level",

    # ── Certifications ────────────────────────────────────────────────────────
    "aws_certified":            "Yes — AWS Certified (ML Engineer, Data Engineer, Developer, Solutions Architect). Also HashiCorp Terraform Associate and CKAD.",
    "certifications":           "AWS Certified Machine Learning Engineer Associate, AWS Certified Data Engineer Associate, HashiCorp Certified Terraform Associate, Certified Kubernetes Application Developer (CKAD), AWS Certified Developer Associate, AWS Certified Solutions Architect Associate",

    # ── Profile questions ─────────────────────────────────────────────────────
    "tell_us_about_yourself": (
        "I am a third-year Software Engineering student at the University of Calgary with hands-on experience "
        "across backend systems, data engineering, AI/ML evaluation, and cloud infrastructure. I hold 4 AWS "
        "certifications and have built production-style systems in Python, TypeScript, Go, and Java. My strongest "
        "work sits at the intersection of technical depth and practical execution — I care about reliability, clean "
        "communication, and learning fast in environments that move with purpose."
    ),
    "why_company": (
        "I'm drawn to this company because the work is technically serious and tied to a real product problem. "
        "The strongest teams for me are ones where engineering quality matters, people ship often, and the mission "
        "is visible in the day-to-day work."
    ),
    "why_role": (
        "This role aligns with the kind of work I want to keep doing — it sits at the intersection of my background "
        "in software engineering, backend systems, and data-driven thinking, and it would push me to go deeper on "
        "the problems I find most interesting."
    ),
    "fit_for_role": (
        "I am a strong fit because my background combines software engineering, backend systems, data/ML work, and "
        "reliable execution under pressure. I've built production-style APIs, automation, cloud infrastructure, and "
        "real-time systems. I'm comfortable learning quickly when the problem is ambiguous, and I bring strong "
        "technical fundamentals, clear communication, and a habit of turning messy problems into working systems."
    ),
    "additional_info": (
        "Thank you for reviewing my application. I'm a third-year Software Engineering student at the University of "
        "Calgary (expected May 2027), with hands-on experience in backend systems, AI evaluation, data pipelines, "
        "cloud infrastructure, and AWS-certified engineering work. I'm available starting May or June 2026 for a "
        "full-time co-op or internship."
    ),
    "relevant_project": (
        "A strong example is the real-time telemetry system I built for Solar Racing — streaming 50+ sensor signals "
        "per second at sub-100ms latency, with live anomaly detection and Grafana dashboards that helped the team "
        "finish top 10 at Formula Sun Grand Prix 2024. It is the clearest example of me taking a technical problem "
        "from concept to a working system under real constraints."
    ),
    "strength": (
        "One of my strengths is staying calm and useful when the problem is still messy. I break things down quickly, "
        "move toward the highest-signal work first, and keep communication clear as I go."
    ),
    "weakness": (
        "I used to spend too long polishing details before sharing early work. I've gotten better about showing "
        "progress sooner, collecting feedback earlier, and iterating in tighter loops."
    ),
    "proudest_achievement": (
        "Building the real-time telemetry system for Solar Racing — streaming 50+ live sensor signals with sub-100ms "
        "latency and anomaly detection — that helped the team finish top 10 at Formula Sun Grand Prix 2024."
    ),
    "leadership": (
        "My most meaningful leadership work has been as Software VP for the University of Calgary Solar Racing team, "
        "where I led the software architecture and delivery of a real-time telemetry platform under competition pressure."
    ),
    "teamwork": (
        "I work well in teams that communicate directly and move with urgency. On Solar Racing, I collaborated across "
        "hardware, software, and strategy sub-teams to define requirements and ship a working system on a tight timeline."
    ),
    "conflict": (
        "When there is disagreement, I try to make the real tradeoff visible and keep the conversation anchored in "
        "the outcome we want. Most conflict gets easier once the team agrees on what matters most."
    ),
    "failure_lesson": (
        "A useful lesson for me was that speed without enough visibility creates hidden problems. I now put more "
        "effort into small checkpoints, clearer notes, and faster feedback before a problem grows."
    ),
    "learning_speed": (
        "I learn quickly by getting my hands on the real problem early. I read just enough to avoid obvious mistakes, "
        "build a small version, and let the work show me where I need more depth."
    ),
    "career_goals": (
        "Long term, I want to grow into an engineer who can own important systems end-to-end and make strong technical "
        "decisions in high-trust environments. In the near term, I want to sharpen the exact skills this role demands "
        "most and learn from engineers who already operate at a high level."
    ),
    "interested_in_full_time": "Yes — I'm open to full-time conversion after graduation (May 2027).",
    "cover_letter_textarea": "",  # filled dynamically

    # ── Yes/No questions ──────────────────────────────────────────────────────
    "agree_terms":           "Yes",
    "confirm_accuracy":      "Yes",
    "certify_truthful":      "Yes",
    "equal_opportunity":     "I prefer not to disclose",
    "18_or_older":           "Yes",
    "can_work_full_time":    "Yes",
    "open_to_relocation":    "Yes",
    "security_clearance":    "No",
    "has_disability":        "I prefer not to disclose",

    # ── Internship / co-op specific ───────────────────────────────────────────
    "returning_intern":      "Yes, I am open to returning for a subsequent co-op or internship term if the opportunity arises.",
    "consecutive_terms":     "Yes, I am available for consecutive terms if the role and team are a good fit.",
    "coop_term_preference":  "Summer 2026 (May or June start preferred). I am open to Fall 2026 as well.",

    # ── Diversity / demographic ───────────────────────────────────────────────
    "race_ethnicity":        "Black or African",
    "indigenous":            "No",
    "first_generation":      "Yes",
    "gender_identity":       "Male",
    "pronouns":              "He/Him",

    # ── Background / clearance ────────────────────────────────────────────────
    "criminal_record":       "No",
    "background_check":      "Yes, I consent to a background check.",
    "drug_test":             "Yes, I am willing to complete a drug test.",
    "bonded":                "No",

    # ── References / contacts ─────────────────────────────────────────────────
    "family_in_company":     "No, I do not have any family members or personal relationships with employees at this company.",
    "referred_by":           "No",
    "military_contacts":     "No, I do not have family members or contacts in the military or government who referred me.",
    "government_contacts":   "No.",
    "how_did_you_hear":      "Online job board / company careers page.",

    # ── Favourite / best project ──────────────────────────────────────────────
    "favourite_project": (
        "My favourite project is the Real-Time Telemetry System I built for the University of Calgary Solar Racing team. "
        "It streams 50+ live sensor signals per second with sub-100ms latency and includes anomaly detection that "
        "surfaces critical issues within 2 seconds. I built it in Python with WebSockets and PostgreSQL, with Grafana "
        "dashboards the team used in real competition conditions. The system contributed to a top-10 finish at Formula "
        "Sun Grand Prix 2024. I love it because it was a hard real-time constraint, built under pressure, and it actually worked."
    ),
    "best_project":          "",  # patched below after dict is fully defined

    # ── Miscellaneous ─────────────────────────────────────────────────────────
    "hear_about_us":         "Online — company careers page.",
    "current_employer":      "Alignerr (via Labelbox) — AI Training Engineer (part-time, remote).",
    "notice_period":         "No notice period required. I am a student and can start on the agreed date.",
    "driver_license":        "Yes, I hold a valid driver's license.",
    "transportation":        "Yes, I have reliable transportation.",
    "overtime_willing":      "Yes, I am willing to work overtime when needed.",
    "shift_flexibility":     "Yes, I am flexible with shift scheduling.",
    "us_work_authorized":    "No. I am authorized to work in Canada only. I would require US visa sponsorship.",
    "other_offers":          "I am actively interviewing and would appreciate a timely decision, but I am genuinely interested in this role.",
    "expected_start":        "May 2026 or June 2026, depending on the employer's preference.",

    # ── 30 Common screening questions (from APPLICATION_CHEAT_SHEET) ──────────
    "challenge_overcome": (
        "During the Solar Racing team's first competition with the telemetry system I built, the alerting system "
        "was firing false positives. During a race, that is dangerous. I had built structured logging into the "
        "ingestion pipeline, so I was able to trace the bad alerts back to a sensor calibration issue rather than "
        "a software bug. I wrote a filtering layer that normalized the outlier readings and the false positives "
        "stopped. The team finished in the top 10 at FSGP 2024. The key was having the instrumentation to diagnose "
        "the problem quickly instead of guessing."
    ),
    "teamwork_example": (
        "I lead a 10-person software team at the University of Calgary Solar Racing team as Software VP. My job is "
        "to own architecture decisions, run Agile sprints, and make sure people are unblocked and shipping. The "
        "biggest challenge is coordination — making sure the person building the dashboard and the person building "
        "the data pipeline are not making incompatible assumptions. I run weekly syncs, do code reviews on every PR, "
        "and keep a shared architecture doc that everyone writes to. We delivered the full telemetry system on time "
        "for FSGP 2024."
    ),
    "leadership_example": (
        "When I joined Solar Racing as a junior member, the telemetry software was undocumented, untested, and "
        "dependent on one person who had graduated. I proposed a full rebuild, scoped the project, and led a team "
        "of 3 to rearchitect it from scratch. I set up code review standards, broke the work into sprints, and "
        "made sure we had something working at each checkpoint. The system was live at competition and the crew "
        "trusted it. That project is what got me promoted to Software VP."
    ),
    "5_years": (
        "As a senior software engineer at a company I believe in, working on hard problems at scale. I want to "
        "be the person other engineers bring their hardest architectural questions to. I am interested in "
        "distributed systems and infrastructure long term, but I am still early in my career and the best thing "
        "I can do right now is work on as many real production problems as possible and build genuine depth."
    ),
    "why_engineering": (
        "I like building things that work correctly and that other people rely on. I got into engineering because "
        "I wanted to understand how systems work. Software engineering is the field where you build the systems, "
        "measure them, break them, and fix them, all in one job. The combination of creative problem-solving, "
        "rigorous correctness requirements, and real-world impact is what keeps me engaged."
    ),
    "tight_deadlines": (
        "I break the work down immediately. At Solar Racing I had 3 weeks before competition to finish the "
        "alerting system. I scoped it to the 2-3 alert types the crew actually needed, shipped those first, and "
        "added the rest after the race. I do not try to do everything; I try to do the right things first."
    ),
    "staying_current": (
        "I build things. Reading about a technology tells me what it does; building something with it tells me "
        "where it breaks. I have been working through distributed systems fundamentals using Designing "
        "Data-Intensive Applications, and I pick up new tools by taking a small real problem and solving it with "
        "that tool. I also review production-grade code weekly at Alignerr across Python and Go."
    ),
    "critical_feedback": (
        "Early in my work at Alignerr, my annotation accuracy was around 88%, below the 95% threshold. My "
        "reviewer flagged that I was applying rubrics inconsistently on edge cases. I went back through my "
        "rejections, identified the pattern, wrote a personal rubric addendum, and applied it for two weeks. "
        "My accuracy hit 95%+ and has stayed there."
    ),
    "alone_or_team": (
        "Both, depending on the phase. I prefer to design alone — I think better without interruption — but "
        "I want constant feedback once I have something working. I show work early, ask for review before I think "
        "it is ready, and I change direction based on feedback."
    ),
    "agile_experience": (
        "I run Agile sprints as Software VP at Solar Racing. Two-week sprints, backlog grooming, sprint reviews, "
        "and retrospectives. I use GitHub Projects for task tracking and GitHub Actions for CI/CD so the team "
        "gets automated test feedback on every PR. I have seen what breaks Agile: unclear acceptance criteria, "
        "no code review, and skipping retros."
    ),
    "missed_deadline": (
        "Yes. I underestimated how long a PostgreSQL schema migration would take at Solar Racing because I did "
        "not account for data backfill time. I caught it a week early, told the team lead, we cut one dashboard "
        "feature, completed the migration clean, and built the cut feature the next sprint. Communicating early "
        "was what made the recovery possible."
    ),
    "cloud_experience": (
        "Yes, primarily AWS. I hold four AWS certifications: Solutions Architect, Developer, Data Engineer, and "
        "Machine Learning Engineer. I have hands-on experience with EC2, S3, Lambda, RDS, ECS, and CloudWatch. "
        "I have deployed containerized services using Terraform for infrastructure-as-code and GitHub Actions "
        "for CI/CD."
    ),
    "database_experience": (
        "I use PostgreSQL as my primary database. I designed the schema for the Solar Racing telemetry system "
        "and the payment gateway. I understand indexing, query plan analysis, and schema design for write-heavy "
        "workloads. I have also used MongoDB, Redis, and SQL Server."
    ),
    "testing_approach": (
        "Tests before merge, always. I write unit tests for business logic, integration tests for database and "
        "API behavior, and I treat coverage of failure paths as mandatory. I do not consider a feature done "
        "until the happy path, error path, and at least one edge case are covered. At the payment gateway "
        "project, tests caught three race condition bugs before deployment."
    ),
    "recently_learned": (
        "I recently went deep on idempotency in distributed payment systems — how to design REST endpoints that "
        "are safe under client retry without double-processing. The key insight was that idempotency is a schema "
        "design problem: you need a durable record of which requests have been processed and what they returned. "
        "I implemented this with a PostgreSQL idempotency key table and it reduced failure cascades by 60%."
    ),
    "why_leaving": (
        "I am a student looking for my Summer 2026 internship. My current work at Alignerr is part-time "
        "contract work alongside school. I am looking for a full-time internship where I can work on a real "
        "engineering team, ship production code, and build depth."
    ),
    "good_code": (
        "Code that is correct, readable, and testable. Correct means it handles failure cases, not just the "
        "happy path. Readable means a new person can understand what it does without asking someone. Testable "
        "means the logic is separated from side effects so you can unit test it without mocking everything."
    ),
    "legacy_code": (
        "I read it before I touch it. I try to understand the invariants the code is actually enforcing before "
        "I change them. Then I add tests around the behavior I am about to change so I can tell if I break "
        "something. I do not rewrite things just because I do not like the style."
    ),
    "ambiguity": (
        "Yes. At Oando the ask was to help reduce maintenance costs. I had to figure out what data existed, "
        "what questions were actually answerable, and what output format would be useful. I am comfortable "
        "starting with a fuzzy problem, identifying what I need to know, and narrowing scope until something "
        "concrete is deliverable."
    ),
    "questions_for_interviewer": (
        "What does the first two weeks look like for an intern on this team? "
        "What is the biggest technical challenge the team is working on right now? "
        "How do interns get access to production systems and how is code reviewed? "
        "What does a strong intern look like at the end of the term?"
    ),
    "experience_python": (
        "Python is my primary language for 3+ years. I use it for data pipelines, ML model training and "
        "serving with FastAPI, automation scripts, and data analysis. At Alignerr I built Python automation "
        "that reduced annotation workflow steps by 40%."
    ),
    "experience_java": (
        "I used Java to build a distributed payment gateway with idempotent REST endpoints, PostgreSQL "
        "persistence, and concurrent request handling. Comfortable with Spring Boot patterns, JUnit testing, "
        "and Java concurrency."
    ),
    "experience_sql": (
        "Daily use for data quality queries. I built the full PostgreSQL schema for the payment gateway and "
        "the Solar Racing telemetry system, including time-series data modeling and index design for "
        "query performance."
    ),
    "interview_questions": (
        "What does a successful first 90 days look like for this role? "
        "What technical problems is the team working on right now? "
        "How are interns typically onboarded and supported?"
    ),
}

# Patch cross-references that couldn't be set inline
CANONICAL_ANSWERS["best_project"] = CANONICAL_ANSWERS["favourite_project"]

SENSITIVE_KEYS: set[str] = {
    "gender",
    "race",
    "ethnicity",
    "veteran_status",
    "disability_status",
    "background_check_consent",
    "references",
}

# Transcript is handled separately as a file upload — not a text answer
TRANSCRIPT_KEY = "transcript"


def get_transcript_path() -> str | None:
    """Return path to transcript PDF if it exists."""
    for transcript_path in _TRANSCRIPT_CANDIDATES:
        if transcript_path.exists():
            return str(transcript_path)
    # Fallback: look for any transcript PDF in known transcript directories.
    for transcript_dir in {path.parent for path in _TRANSCRIPT_CANDIDATES}:
        if transcript_dir.exists():
            candidates = sorted(transcript_dir.glob("transcript*.pdf"), reverse=True)
            if candidates:
                return str(candidates[0])
    return None


LABEL_SYNONYMS = [
    # Identity
    ("first_name",          ("first name", "given name", "legal first name", "first")),
    ("last_name",           ("last name", "surname", "family name", "legal last name", "last")),
    ("full_name",           ("full name", "your name", "name", "applicant name", "candidate name")),
    ("email",               ("email address", "email", "e-mail")),
    ("phone",               ("phone number", "mobile phone", "telephone", "phone", "cell")),
    ("city",                ("city", "municipality")),
    ("province",            ("province", "state", "region", "state/province")),
    ("country",             ("country",)),
    ("address_line1",       ("address line 1", "street address", "address", "mailing address")),
    ("postal_code",         ("postal code", "zip code", "zip")),
    # Education
    ("school",              ("school", "university", "institution", "college", "where do you attend")),
    ("degree",              ("degree", "program of study", "field of study", "major", "program",
                             "educational background", "area of study", "discipline")),
    ("gpa",                 ("gpa", "grade point average", "cumulative gpa", "cgpa",
                             "academic average", "academic standing")),
    ("gpa_scale",           ("gpa scale", "out of", "gpa out of")),
    ("graduation_date",     ("graduation date", "expected graduation", "grad date", "graduation year",
                             "when do you graduate", "completion date")),
    ("year_of_study",       ("year of study", "current year", "academic year")),
    ("enrollment_status",   ("enrollment status", "student status", "enrollment")),
    # Work authorization
    ("work_authorized_canada",    ("authorized to work in canada", "legally authorized to work in canada",
                                   "eligible to work in canada", "canadian work authorization")),
    ("needs_sponsorship_canada",  ("require sponsorship in canada", "need sponsorship in canada",
                                   "future sponsorship canada")),
    ("work_authorized_us",        ("authorized to work in the united states", "eligible to work in the us")),
    ("needs_sponsorship_us",      ("require sponsorship in the united states", "need sponsorship in the us",
                                   "u.s. visa sponsorship", "us visa sponsorship", "future sponsorship us")),
    ("right_to_work",             ("right to work", "legally able to work")),
    # Links
    ("linkedin_url",        ("linkedin profile", "linkedin url", "linkedin", "linkedin account")),
    ("github_url",          ("github profile", "github url", "github", "github account", "code portfolio")),
    ("portfolio_url",       ("portfolio", "website", "personal site", "personal website", "portfolio url")),
    # Availability
    ("start_date",          ("start date", "earliest start", "available to start", "when can you start",
                             "preferred start date", "earliest available date")),
    ("internship_availability", ("internship availability", "co-op availability", "coop availability",
                                  "availability", "available for internship", "term availability")),
    ("hours_per_week",      ("hours per week", "hours available", "weekly hours")),
    ("part_time_full_time", ("part time or full time", "employment type", "position type")),
    # Compensation
    ("salary_expectation",  ("salary", "compensation", "pay expectation", "hourly rate", "desired pay",
                             "expected salary", "salary expectations", "compensation expectations",
                             "wage expectation", "expected hourly", "hourly expectation")),
    # Experience
    ("years_of_experience", ("years of experience", "how many years", "years experience",
                             "total experience", "experience in years")),
    ("experience_level",    ("experience level", "level", "seniority level")),
    # Profile
    ("tell_us_about_yourself", ("tell us about yourself", "tell me about yourself", "introduce yourself",
                                "about you", "bio", "about yourself")),
    ("why_company",         ("why this company", "why do you want to work at", "why do you want to join",
                             "why us", "what draws you", "what attracted you", "why apply here")),
    ("why_role",            ("why this role", "why are you interested in this role",
                             "why this position", "why this internship", "why this opportunity")),
    ("fit_for_role",        ("what makes you a good fit", "good fit for", "why are you a good fit",
                             "why should we hire", "why are you the right candidate",
                             "how are you qualified", "what qualifies you")),
    ("additional_info",     ("anything else", "additional information", "additional comments",
                             "anything you would like us to know", "other information")),
    ("relevant_project",    ("relevant project", "best project", "project you are proud",
                             "describe a project", "most relevant project")),
    ("strength",            ("biggest strength", "one of your strengths", "your strength",
                             "greatest strength", "key strength")),
    ("weakness",            ("biggest weakness", "area for improvement", "weakness", "growth area")),
    ("career_goals",        ("career goals", "long-term goals", "where do you see yourself",
                             "five year plan", "professional goals")),
    ("cover_letter_textarea", ("cover letter", "cover letter text", "your cover letter",
                               "write a cover letter", "paste your cover letter")),
    # Certifications
    ("aws_certified",       ("aws certified", "aws certification", "aws cert")),
    # Logistical
    ("willing_to_relocate", ("willing to relocate", "able to relocate", "open to relocation",
                             "relocation", "would you relocate")),
    ("remote_preference",   ("remote preference", "work arrangement", "work location preference",
                             "remote or in-person", "hybrid preference")),
    ("open_to_relocation",  ("open to relocation", "relocation required")),
    ("18_or_older",         ("18 or older", "are you 18", "at least 18 years of age")),
    ("agree_terms",         ("agree to terms", "accept terms", "terms and conditions",
                             "i agree", "acknowledgement")),
    ("confirm_accuracy",    ("information is accurate", "certify accuracy", "confirm all information")),
    # Files
    ("transcript",          ("transcript", "academic transcript", "unofficial transcript",
                             "official transcript", "grade report")),
    ("references",          ("reference", "references", "referees")),
    ("background_check_consent", ("background check", "criminal check", "background screening")),
    # Demographic (sensitive)
    ("gender",              ("gender", "sex")),
    ("race",                ("race", "ethnicity", "ethnic background")),
    ("veteran_status",      ("veteran", "military service", "military status")),
    ("disability_status",   ("disability", "accommodation", "disabilities")),
    # Internship
    ("returning_intern",    ("returning intern", "return for another term", "returning co-op",
                             "interested in returning", "would you return")),
    ("coop_term_preference", ("preferred term", "which term", "co-op term", "coop term")),
    # Contacts
    ("family_in_company",   ("family member", "relatives", "family at this company",
                             "know anyone at", "personal relationship", "employee referral",
                             "do you have any friends or family")),
    ("referred_by",         ("referred by", "who referred", "referral source")),
    ("how_did_you_hear",    ("how did you hear", "how did you find", "source of application",
                             "where did you see this posting")),
    ("military_contacts",   ("military contacts", "government contacts", "family in military",
                             "family in government", "government relationship")),
    # Project
    ("favourite_project",   ("favourite project", "favorite project", "best project",
                             "project you are most proud", "proudest project",
                             "describe your best project", "most interesting project",
                             "technical project", "capstone", "side project")),
    # Miscellaneous
    ("current_employer",    ("current employer", "current company", "where do you work now",
                             "current role", "current position")),
    ("notice_period",       ("notice period", "how soon can you start", "when available")),
    ("driver_license",      ("driver license", "drivers licence", "valid license", "drive")),
    ("hear_about_us",       ("how did you hear about us", "how did you find us")),
    ("other_offers",        ("other offers", "other opportunities", "competing offers")),
    ("expected_start",      ("expected start", "when can you start", "earliest start date")),
    ("us_work_authorized",  ("authorized to work in the us", "us work authorization", "us work auth")),
    # 30 screening questions
    ("challenge_overcome",  ("tell me about a challenge", "overcome a challenge", "describe a difficulty",
                             "difficult situation", "problem you solved", "obstacle you faced")),
    ("teamwork_example",    ("time you worked on a team", "team experience", "collaboration example",
                             "worked in a team", "team project")),
    ("leadership_example",  ("time you showed leadership", "leadership experience", "led a team",
                             "describe leadership")),
    ("5_years",             ("where do you see yourself in 5 years", "5 year plan", "long term plan",
                             "future goals", "career in 5 years")),
    ("why_engineering",     ("why software engineering", "why did you choose engineering",
                             "passion for engineering", "why computer science")),
    ("tight_deadlines",     ("how do you handle deadlines", "tight deadline", "time pressure",
                             "pressure and deadlines", "managing deadlines")),
    ("staying_current",     ("how do you stay current", "keep up with technology", "learning new tech",
                             "professional development", "stay up to date")),
    ("critical_feedback",   ("received critical feedback", "negative feedback", "constructive criticism",
                             "feedback you disagreed with", "handling criticism")),
    ("alone_or_team",       ("prefer working alone or team", "work style", "independent or collaborative",
                             "do you prefer")),
    ("agile_experience",    ("agile experience", "scrum experience", "sprint", "agile methodology",
                             "waterfall or agile")),
    ("missed_deadline",     ("missed a deadline", "failed to meet deadline", "late on a project")),
    ("cloud_experience",    ("aws experience", "cloud experience", "gcp experience", "azure experience",
                             "cloud platforms")),
    ("database_experience", ("database experience", "sql experience", "postgres", "database design",
                             "experience with databases")),
    ("testing_approach",    ("approach to testing", "how do you test", "unit testing", "tdd",
                             "software testing", "test driven")),
    ("recently_learned",    ("recently learned", "technical concept", "something new", "self-study",
                             "what have you been learning")),
    ("why_leaving",         ("why are you leaving", "why looking for new role", "why change jobs")),
    ("good_code",           ("what is good code", "code quality", "clean code", "what makes code good")),
    ("legacy_code",         ("legacy code", "messy codebase", "old code", "working with existing code")),
    ("ambiguity",           ("comfortable with ambiguity", "handle ambiguity", "unclear requirements",
                             "ambiguous problems")),
    ("questions_for_interviewer", ("do you have any questions", "questions for us",
                                   "anything you want to ask")),
    ("experience_python",   ("python experience", "experience with python", "python skills")),
    ("experience_java",     ("java experience", "experience with java", "java skills")),
    ("experience_sql",      ("sql experience", "experience with sql", "database sql")),
]


def normalize_label(label: str) -> str:
    """Map a form field label to a canonical key."""
    text = " ".join((label or "").lower().replace("_", " ").replace("-", " ").split())
    if not text:
        return ""
    # Sponsorship disambiguation
    if "sponsor" in text or "visa" in text:
        if any(k in text for k in ("united states", "u.s.", " us ", "usa", "american")):
            return "needs_sponsorship_us"
        if "canada" in text or "canadian" in text:
            return "needs_sponsorship_canada"
    # Walk synonym table
    for key, phrases in LABEL_SYNONYMS:
        if any(phrase in text for phrase in phrases):
            return key
    return ""


def answer_for_label(label: str, context: dict | None = None) -> tuple[str, bool]:
    """
    Return (answer_text, is_sensitive) for a form field label.
    Pass context dict with 'cover_letter' key to dynamically fill cover letter fields.
    """
    key = normalize_label(label)
    if not key:
        return "", False
    if key in SENSITIVE_KEYS:
        return "", True
    if key == TRANSCRIPT_KEY:
        return "", True  # transcript is a file upload, not a text answer
    if key == "cover_letter_textarea" and context:
        cl = context.get("cover_letter", "")
        if cl:
            return cl, False
    answer = CANONICAL_ANSWERS.get(key, "")
    return answer, False


def is_yes_no_question(label: str) -> bool:
    """Return True if the label maps to a boolean/yes-no question."""
    key = normalize_label(label)
    return key in {
        "work_authorized_canada", "needs_sponsorship_canada",
        "work_authorized_us", "needs_sponsorship_us",
        "right_to_work", "willing_to_relocate", "open_to_relocation",
        "18_or_older", "agree_terms", "confirm_accuracy",
        "citizen_or_pr_canada", "can_work_full_time", "interested_in_full_time",
        "security_clearance",
    }


def yes_no_value(label: str) -> str:
    """Return the appropriate Yes/No/Prefer not to disclose string."""
    key = normalize_label(label)
    mapping = {
        "work_authorized_canada":    "Yes",
        "needs_sponsorship_canada":  "No",
        "work_authorized_us":        "No",
        "needs_sponsorship_us":      "Yes",
        "right_to_work":             "Yes",
        "willing_to_relocate":       "Yes",
        "open_to_relocation":        "Yes",
        "18_or_older":               "Yes",
        "agree_terms":               "Yes",
        "confirm_accuracy":          "Yes",
        "citizen_or_pr_canada":      "No",
        "can_work_full_time":        "Yes",
        "interested_in_full_time":   "Yes",
        "security_clearance":        "No",
        "has_disability":            "I prefer not to disclose",
        "veteran_status":            "I prefer not to disclose",
    }
    return mapping.get(key, "")
