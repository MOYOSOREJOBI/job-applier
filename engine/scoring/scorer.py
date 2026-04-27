"""
Scoring engine — weighted multi-dimension scoring for Calgary internship targeting.
Returns a score 0–100 and a per-dimension breakdown.
Covers all white-collar / knowledge-work role categories.
"""
import re
from typing import Optional

# ── Positive title keywords (all white-collar / tech-adjacent roles) ──────────
POSITIVE_TITLE = [
    # ── Core SWE ─────────────────────────────────────────────────────────────
    "software engineer", "software developer", "software engineering",
    "backend", "back-end", "back end",
    "frontend", "front-end", "front end",
    "full stack", "fullstack", "full-stack",
    "web developer", "web engineer", "web application",
    "application developer", "application engineer",
    "systems developer", "systems engineer", "systems software",
    "api engineer", "api developer", "sdk engineer",
    "platform engineer", "platform backend",
    "microservices engineer", "integration engineer",
    "internal tools engineer", "developer tools", "build engineer",
    "release engineer", "automation engineer",
    "cloud engineer", "cloud developer", "cloud platform",
    "cloud infrastructure", "cloud operations",
    "devops", "site reliability", "sre", "infrastructure engineer",
    "production engineer", "reliability engineer",
    "observability engineer", "monitoring engineer",
    "ci/cd engineer", "deployment engineer", "technical operations",
    # ── Data / Analytics ─────────────────────────────────────────────────────
    "data analyst", "data science", "data scientist",
    "business data analyst", "product data analyst",
    "operations data analyst", "financial data analyst",
    "marketing data analyst", "sports data analyst",
    "bi analyst", "business intelligence", "reporting analyst",
    "insights analyst", "data visualization", "dashboard developer",
    "data engineer", "analytics engineer", "data platform engineer",
    "etl developer", "data pipeline", "database engineer",
    "database developer", "data systems", "data infrastructure",
    "data management", "data operations",
    # ── AI / ML ──────────────────────────────────────────────────────────────
    "machine learning", "ml engineer", "ml intern",
    "ai engineer", "applied ai", "ai product engineer",
    "mlops", "llm engineer", "prompt engineer",
    "nlp engineer", "computer vision", "deep learning",
    "ai research", "data scientist", "decision scientist",
    "quantitative data scientist",
    "artificial intelligence",
    # ── QA / Testing ─────────────────────────────────────────────────────────
    "qa engineer", "qa analyst", "software tester",
    "test engineer", "automation test", "sdet",
    "qa automation", "manual tester", "api tester",
    "performance tester", "uat analyst", "quality assurance",
    "product quality analyst",
    # ── Security ─────────────────────────────────────────────────────────────
    "cybersecurity", "security engineer", "application security",
    "cloud security", "soc analyst", "threat analyst",
    "vulnerability analyst", "security automation",
    "grc analyst", "risk technology", "iam engineer",
    "information security", "security analyst",
    # ── Product / PM ─────────────────────────────────────────────────────────
    "product manager", "associate product manager", "apm",
    "technical product manager", "tpm", "product owner",
    "product analyst", "product operations",
    "project manager", "project coordinator",
    "technical project manager", "program manager",
    "program coordinator", "scrum master", "agile coach",
    "delivery manager",
    # ── Business / Systems Analyst ────────────────────────────────────────────
    "business analyst", "technical business analyst",
    "it business analyst", "systems analyst",
    "information systems analyst", "functional analyst",
    "requirements analyst", "solutions analyst",
    "technology consultant", "it consultant",
    "digital consultant", "strategy consultant",
    "management consultant", "data consultant",
    "cloud consultant", "risk consultant",
    "erp consultant", "salesforce consultant",
    "servicenow consultant",
    # ── Finance / Fintech / Quant ─────────────────────────────────────────────
    "fintech engineer", "trading systems", "quant developer",
    "quantitative developer", "quantitative analyst",
    "quant researcher", "risk analyst", "model risk",
    "financial data analyst", "investment data analyst",
    "market data analyst", "trading analyst", "treasury analyst",
    "payments engineer", "fraud analyst", "credit risk",
    "compliance tech", "blockchain developer", "smart contract",
    "crypto analyst", "defi analyst",
    "financial analyst", "finance intern", "capital markets",
    # ── Solutions / Sales Engineering ─────────────────────────────────────────
    "solutions engineer", "solutions architect",
    "sales engineer", "pre-sales engineer",
    "customer success engineer", "technical account manager",
    "implementation engineer", "forward deployed",
    "developer advocate", "developer relations",
    "partner engineer",
    # ── Marketing / Growth / RevOps ───────────────────────────────────────────
    "growth engineer", "growth analyst", "marketing analyst",
    "marketing data analyst", "digital marketing analyst",
    "seo analyst", "marketing operations",
    "revenue operations", "crm analyst", "lifecycle marketing",
    "product marketing manager", "conversion rate optimization",
    "web marketing", "e-commerce manager", "shopify developer",
    # ── UX / Design Tech ─────────────────────────────────────────────────────
    "ux engineer", "ux designer", "ui engineer",
    "product designer", "design technologist",
    "creative technologist", "interaction designer",
    "prototyping engineer", "motion developer",
    # ── Engineering Adjacent ──────────────────────────────────────────────────
    "embedded software", "firmware engineer", "iot engineer",
    "simulation engineer", "digital engineering",
    "robotics engineer", "controls engineer",
    "engineering analyst", "technical project engineer",
    # ── Operations / Strategy ─────────────────────────────────────────────────
    "operations analyst", "business operations",
    "strategy analyst", "corporate analyst",
    "process improvement", "supply chain analyst",
    "logistics analyst", "procurement analyst",
    "compliance analyst", "internal audit", "it audit",
    "policy analyst", "privacy analyst", "enterprise risk",
    # ── Technical Writing ─────────────────────────────────────────────────────
    "technical writer", "documentation engineer",
    "api documentation", "developer content",
    # ── Science / Research / Health ───────────────────────────────────────────
    "research assistant", "research software engineer",
    "computational scientist", "bioinformatics",
    "health data analyst", "clinical data analyst",
    "scientific programmer", "simulation researcher",
    "ai research assistant", "digital health engineer",
    # ── Industry-Specific ────────────────────────────────────────────────────
    "sports analytics", "energy data analyst",
    "smart grid", "climate tech",
    "healthtech engineer", "medical software",
    "autonomous systems", "adas engineer",
    "vehicle software", "network software",
    "banking technology", "capital markets technology",
    "government it", "digital service developer",
    # ── Entry / General level signals ────────────────────────────────────────
    "junior developer", "junior engineer", "junior analyst",
    "associate engineer", "associate developer", "associate analyst",
    "new grad", "entry level", "entry-level",
    "co-op", "coop", "intern", "internship", "student",
    "graduate", "coordinator", "specialist", "technologist",
    # ── Oil & gas / energy (Calgary-specific) ─────────────────────────────────
    "petroleum engineer", "reservoir engineer",
    "production engineer", "geospatial analyst",
    "digital engineer", "process engineer",
    "operations technology", "pipeline data",
    "instrumentation", "scada",
]

NEGATIVE_TITLE = [
    "senior software", "staff engineer", "principal engineer",
    "director of", "vp of", "vice president",
    "physician", "nurse practitioner", "registered nurse",
    "accountant cpa", "actuar",
    "recruiter", "talent acquisition", "headhunter",
    "account executive", "account manager", "sales representative",
    "lawyer", "attorney", "counselor", "paralegal",
    "social worker", "therapist", "psychologist",
    "electrician", "plumber", "carpenter", "hvac",
    "civil technician", "administrative assistant",
    "receptionist", "cashier", "retail associate",
    "truck driver", "delivery driver", "warehouse associate",
    "chef", "cook", "server", "bartender",
    "custodian", "janitor",
]

SENIORITY_POSITIVE = [
    "intern", "internship", "co-op", "coop", "student",
    "junior", "jr.", "associate",
    "entry level", "entry-level", "new grad", "graduate",
    "i ", "level 1", "l1", "engineer i", "developer i",
    "analyst i", "coordinator",
]
SENIORITY_NEGATIVE = [
    "senior", "sr.", "staff", "principal", "lead engineer",
    "manager", "director", "head of", "vp", "c-level",
    "chief", "executive", "5+ years", "7+ years", "10+ years",
    "12+ years", "15+ years",
]

TECH_SKILLS = [
    # Languages
    "python", "java", "javascript", "typescript", "golang", "go ",
    "rust", "c++", "c#", "swift", "kotlin", "scala", "ruby",
    "php", "r programming", "matlab",
    # Web / Frameworks
    "react", "next.js", "vue", "angular", "svelte",
    "node", "express", "fastapi", "django", "flask", "spring",
    "rails", "laravel",
    # Databases
    "postgresql", "mysql", "sqlite", "mongodb", "redis",
    "cassandra", "dynamodb", "elasticsearch", "neo4j",
    "snowflake", "bigquery", "redshift",
    # Cloud / Infra
    "docker", "kubernetes", "k8s", "aws", "gcp", "azure",
    "terraform", "pulumi", "ansible", "helm", "argocd",
    "github actions", "gitlab ci", "jenkins", "circleci",
    "linux", "unix", "bash",
    # AI / ML
    "machine learning", "pytorch", "tensorflow", "scikit",
    "hugging face", "langchain", "openai", "llm",
    "computer vision", "nlp", "transformers",
    # Data
    "pandas", "numpy", "spark", "hadoop", "kafka", "airflow",
    "dbt", "tableau", "power bi", "looker", "metabase",
    "data pipeline", "etl", "elt", "data warehouse",
    # APIs / Arch
    "rest api", "graphql", "grpc", "microservices",
    "event-driven", "message queue", "rabbitmq",
    # Finance domain
    "bloomberg", "vba", "excel", "financial modeling",
    "sql", "git", "ci/cd",
    # Security
    "penetration testing", "owasp", "siem", "soar",
    # QA
    "selenium", "playwright", "cypress", "jest", "pytest",
    # Design / UX
    "figma", "sketch", "adobe xd",
    # Project mgmt
    "jira", "confluence", "notion", "agile", "scrum",
]

SALARY_SIGNALS = [
    "$25", "$26", "$27", "$28", "$29", "$30",
    "$31", "$32", "$33", "$34", "$35", "$36", "$37", "$38", "$39", "$40",
    "$41", "$42", "$43", "$44", "$45",
    "25/hr", "26/hr", "27/hr", "28/hr", "29/hr", "30/hr",
    "25 per hour", "30 per hour", "35 per hour", "40 per hour",
    "25.00", "26.00", "27.00", "28.00", "29.00", "30.00",
    "competitive salary", "competitive compensation",
    "equity", "stock options", "benefits",
]

CALGARY_SIGNALS = [
    "calgary", "alberta", "remote", "canada remote", "remote canada",
    "work from home", "distributed", "anywhere in canada",
    "pan-canadian", "coast to coast",
]

INTERNSHIP_SIGNALS = [
    "intern", "co-op", "coop", "student",
    "4 months", "8 months", "12 months", "16 months",
    "summer 2026", "fall 2026", "winter 2026", "spring 2026",
    "summer 2025", "fall 2025",
    "new grad", "entry", "graduate",
    "may 2026", "may 1", "starting may", "start may", "2026 intern",
    "intern 2026", "co-op 2026", "coop 2026", "student 2026",
    "january 2026", "september 2026",
    "4-month", "8-month", "12-month",
]

LOW_FRICTION_ATS = ["greenhouse", "lever", "ashby", "workable", "smartrecruiters"]


def _contains(text: str, keywords: list[str]) -> int:
    """Return count of keywords found in text (case-insensitive)."""
    t = text.lower()
    return sum(1 for kw in keywords if kw in t)


def score_job(job: dict) -> tuple[float, dict]:
    """
    Score a job dict. Returns (total_score 0-100, breakdown dict).

    Weights:
      title_match          20
      seniority_fit        20
      location_fit         15
      skill_fit            20
      internship_relevance 10
      recency               5
      application_friction  5
      company_signal        5
    Total                 100
    """
    title = (job.get("title") or "").lower()
    location = (job.get("location") or "").lower()
    desc = (job.get("description_raw") or job.get("description_normalized") or "").lower()
    company = (job.get("company") or "").lower()
    portal = (job.get("portal") or job.get("source") or "").lower()
    posted_at = job.get("posted_at") or ""

    breakdown = {}

    # ── 1. Title match (20 pts) ────────────────────────────────────────────────
    neg_title = _contains(title, NEGATIVE_TITLE)
    if neg_title:
        title_score = 0
    else:
        pos_hits = _contains(title, POSITIVE_TITLE)
        title_score = min(20, pos_hits * 5)
        if any(s in title for s in ["intern", "co-op", "coop", "student", "new grad",
                                     "junior", "associate", "entry", "graduate"]):
            title_score = min(20, title_score + 5)
    breakdown["title_match"] = round(title_score, 1)

    # ── 2. Seniority fit (20 pts) ─────────────────────────────────────────────
    seniority_text = title + " " + desc[:500]
    neg_sen = _contains(seniority_text, SENIORITY_NEGATIVE)
    pos_sen = _contains(seniority_text, SENIORITY_POSITIVE)
    if neg_sen and not pos_sen:
        seniority_score = 0
    elif pos_sen:
        seniority_score = min(20, 10 + pos_sen * 4)
    else:
        seniority_score = 8  # neutral — not clearly senior or intern
    breakdown["seniority_fit"] = round(seniority_score, 1)

    # ── 3. Location fit (15 pts) ──────────────────────────────────────────────
    loc_text = location + " " + desc[:300]
    if "calgary" in loc_text:
        location_score = 15
    elif "alberta" in loc_text:
        location_score = 12
    elif any(s in loc_text for s in ["canada remote", "remote canada", "remote, canada",
                                      "remote (canada)", "anywhere in canada",
                                      "work from home", "distributed",
                                      "pan-canadian"]):
        location_score = 12
    elif "remote" in loc_text:
        location_score = 9
    elif "canada" in loc_text:
        location_score = 8
    elif any(c in loc_text for c in ["toronto", "vancouver", "ottawa", "montreal",
                                      "kitchener", "waterloo", "edmonton", "winnipeg"]):
        location_score = 5
    else:
        location_score = 2
    breakdown["location_fit"] = round(location_score, 1)

    # ── 4. Skill fit (20 pts) ─────────────────────────────────────────────────
    skill_hits = _contains(desc, TECH_SKILLS)
    skill_score = min(20, skill_hits * 2)
    breakdown["skill_fit"] = round(skill_score, 1)

    # ── 5. Internship relevance (10 pts) ──────────────────────────────────────
    intern_hits = _contains(title + " " + desc[:1000], INTERNSHIP_SIGNALS)
    internship_score = min(10, intern_hits * 4)
    breakdown["internship_relevance"] = round(internship_score, 1)

    # ── 6. Recency (5 pts) ────────────────────────────────────────────────────
    recency_score = 3
    if posted_at:
        try:
            from datetime import datetime, timezone
            if "T" in posted_at:
                posted = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
            else:
                posted = datetime.fromisoformat(posted_at)
            if posted.tzinfo is None:
                posted = posted.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            days_old = (now - posted).days
            if days_old <= 3:
                recency_score = 5
            elif days_old <= 7:
                recency_score = 4
            elif days_old <= 14:
                recency_score = 3
            elif days_old <= 30:
                recency_score = 2
            else:
                recency_score = 1
        except Exception:
            recency_score = 3
    breakdown["recency"] = round(recency_score, 1)

    # ── 7. Application friction (5 pts) ───────────────────────────────────────
    if any(p in portal for p in LOW_FRICTION_ATS):
        friction_score = 5
    else:
        friction_score = 2
    breakdown["application_friction"] = round(friction_score, 1)

    # ── 8. Company signal (5 pts) ─────────────────────────────────────────────
    company_score = 2
    known_good = [
        # FAANG / Tier-1 tech
        "amazon", "microsoft", "google", "apple", "meta", "nvidia",
        "netflix", "salesforce", "adobe", "intel", "ibm",
        # Hot AI / ML companies
        "anthropic", "openai", "cohere", "mistral", "hugging face",
        "scale ai", "databricks", "palantir", "snowflake",
        "datadog", "cloudflare", "stripe", "plaid",
        # Canadian tech
        "shopify", "telus", "rogers", "bell", "wealthsimple", "benevity",
        "nuvei", "lightspeed", "clio", "d2l", "hootsuite", "freshbooks",
        "ecobee", "ritual", "koho", "league", "absorb",
        "1password", "coveo", "jobber", "vidyard",
        # Calgary / Alberta employers
        "suncor", "cenovus", "enbridge", "atco", "aecom", "cpkc",
        "canadian pacific", "ovintiv", "arc resources",
        "whitecap", "tourmaline", "canadian natural",
        "tc energy", "pembina", "keyera",
        "atb financial", "atb", "brc analytics",
        # Consulting / professional services
        "deloitte", "pwc", "kpmg", "ey", "ernst", "accenture",
        "mckinsey", "bain", "bcg", "capgemini", "cognizant", "infosys",
        # Finance / banking
        "rbc", "td bank", "bmo", "cibc", "scotiabank", "national bank",
        "manulife", "sun life", "intact", "fairfax",
        "jpmorgan", "goldman sachs", "morgan stanley",
        # Developer tools / infrastructure
        "github", "gitlab", "jfrog", "hashicorp", "elastic",
        "confluent", "mongodb", "cockroachdb", "neon",
        "grafana", "sentry", "pagerduty",
        # Gaming
        "electronic arts", "ea sports", "ubisoft", "roblox",
        "riot games", "epic games", "unity",
    ]
    if any(k in company for k in known_good):
        company_score = 5
    elif company:
        company_score = 3
    breakdown["company_signal"] = round(company_score, 1)

    # ── Salary bonus (up to 5 pts) ────────────────────────────────────────────
    salary_text = desc[:2000]
    if any(s in salary_text for s in SALARY_SIGNALS):
        total_salary_boost = min(5, sum(1 for s in SALARY_SIGNALS if s in salary_text))
    else:
        total_salary_boost = 0

    total = float(sum(breakdown.values())) + total_salary_boost
    total = round(min(100.0, total), 1)

    if total >= 75:
        fit_band = "strong"
    elif total >= 55:
        fit_band = "good"
    elif total >= 35:
        fit_band = "weak"
    else:
        fit_band = "poor"

    return total, breakdown, fit_band
