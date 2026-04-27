#!/usr/bin/env python3
"""
Job Applier — Moyosore Ogunjobi
================================
Automated job application bot. Scrapes job descriptions, generates a tailored
resume + cover letter with Claude, builds PDFs, and submits forms.

DAILY LIMIT:
  40/day is the recommended max. The bot enforces a 6-10 second delay between
  jobs. At 40 jobs that is roughly 60-90 minutes of runtime. LinkedIn Easy Apply
  has no official published cap but bot detection triggers around 80-100 rapid
  applications. External ATS portals (Workday, Greenhouse, etc.) have no shared
  limit. Stay at or below 40/day and you will not get flagged.

JOB SOURCES (use one or many per run):
  --apply-url URL         Any direct job or ATS URL — Ashby, Lever, Greenhouse,
                          Workday, Cisco, iCIMS, or generic. Scrapes the page,
                          generates documents, and submits. Handles any site.
  --url URL               LinkedIn job URL
  --recommended           LinkedIn recommended feed
  --search QUERY          LinkedIn keyword search
  --github                Canadian-Tech-Internships-2026 repo (auto-updated daily)
  --from-file PATH        CSV or MD file of job links

CATEGORY (controls resume framing and Claude tone):
  --category tech         Software engineering / data / ML / DevOps (default)
  --category finance      Finance, fintech, banking, data analytics
  --category consulting   Consulting, strategy, operations, business analyst
  --category pm           Product management, project management, coordinator

EXAMPLES:
  python scripts/run.py --apply-url "https://jobs.ashbyhq.com/super.com/8e3c12f4..."
  python scripts/run.py --github --limit 40
  python scripts/run.py --recommended --limit 20 --category finance
  python scripts/run.py --search "product manager intern Canada" --category pm
  python scripts/run.py --github --limit 5 --dry-run

SETUP (run once):
  pip install -r requirements.txt
  playwright install chromium
  cp .env.example .env
"""

import argparse
import csv
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from weasyprint import HTML as WPHtml

load_dotenv()
console = Console()

# ─────────────────────────────────────────────────────────────────────────────
# PROFILE — Moyosore Ogunjobi  (source of truth — all resume data lives here)
# ─────────────────────────────────────────────────────────────────────────────

PROFILE = {
    "name":         "Moyosore Ogunjobi",
    "email":        "moyosorejobi@gmail.com",
    "phone":        "825-736-5656",
    "phone_digits": "8257365656",
    "github":       "github.com/MOYOSOREJOBI",
    "linkedin":     "linkedin.com/in/moyosore-ogunjobi-b187b8205",
    "portfolio":    "moyosore.dev",

    # Full street addresses per city — used in resume header and form fields
    "addresses": {
        "Vancouver": "1205-1305 W 12th Ave, Vancouver, BC V6H 1M2",
        "Calgary":   "1401-4755 Dalton Dr, Calgary, AB T3A 2Z7",
        "Toronto":   "1008-571 Bloor Street, Toronto, ON M6G 1K3",
        "Ottawa":    "Ottawa, ON",
        "Montreal":  "Montreal, QC",
        "default":   "1401-4755 Dalton Dr, Calgary, AB T3A 2Z7",
    },
    "default_city":     "Calgary",
    "default_province": "Alberta",

    "university":  "University of Calgary",
    "degree":      "BSc Software Engineering",
    "graduation":  "Expected May 2027",

    "work_auth_canada":     True,
    "work_auth_us":         False,
    "prior_cisco_employee": False,

    # LOCKED summary — used verbatim for tech roles
    "summary_tech": (
        "Software Engineering student with production experience in backend systems, "
        "ML pipelines, and cloud infrastructure. Built distributed services handling "
        "real-time data at scale. Strong foundation in Python, Java, and AWS. "
        "Focused on shipping reliable software under pressure."
    ),

    # Finance / analytics framing
    "summary_finance": (
        "Software Engineering student with hands-on experience in data analytics, "
        "automation, and quantitative reasoning. Built systems that process and analyze "
        "large datasets, identify anomalies, and surface actionable insights. "
        "AWS certified. Strong in Python, SQL, and Excel. Available May 2026."
    ),

    # Consulting framing
    "summary_consulting": (
        "Software Engineering student with experience delivering cross-functional projects "
        "under pressure. Led a 10-person technical team, managed a $35,000 budget, and "
        "built data systems that cut downtime costs by $35K+. "
        "Strong communicator and fast learner. Available May 2026."
    ),

    # PM framing
    "summary_pm": (
        "Software Engineering student with leadership experience across technical teams "
        "and student organizations. Led 10-person software team through full product cycles, "
        "from requirements to deployment. Managed operations for 200+ members and a $35,000 "
        "budget. Available May 2026."
    ),

    "certifications": [
        "AWS Certified Machine Learning Engineer Associate (MLA-C01)",
        "AWS Certified Developer Associate (DVA-C02)",
        "AWS Certified Data Engineer Associate (DEA-C01)",
        "AWS Certified Solutions Architect Associate (SAA-C03)",
        "HackerRank Software Engineer (2026)",
    ],

    "experience": [
        {
            "title":    "AI Training Engineer",
            "company":  "Alignerr (via Labelbox)",
            "start":    "Aug 2024",
            "end":      "Present",
            "location": "Remote, Canada",
            "tools":    "Python · C++ · Labelbox · Git",
            "bullets": {
                "tech": [
                    "Evaluate 200+ AI model outputs weekly across code generation in Python and C++, mathematical reasoning, and live coding tasks",
                    "Built Python automation scripts reducing annotation workflow steps by 40% while maintaining data quality standards",
                    "Maintain 95%+ quality scores while meeting weekly throughput targets across technical domains",
                ],
                "finance": [
                    "Evaluate 200+ structured outputs weekly for accuracy, consistency, and quality across quantitative reasoning tasks",
                    "Built Python automation reducing workflow steps by 40%, improving data throughput while maintaining 95%+ accuracy rates",
                    "Deliver precise, actionable feedback on technical outputs — strong attention to detail under volume and deadline pressure",
                ],
                "consulting": [
                    "Evaluate 200+ AI model outputs weekly against defined quality frameworks, maintaining 95%+ accuracy consistently",
                    "Built automation scripts reducing repetitive review steps by 40%, improving team throughput without sacrificing standards",
                    "Provide structured, data-driven feedback that improves model performance — fast learner, high-output environment",
                ],
                "pm": [
                    "Evaluate and quality-assure 200+ outputs weekly against defined criteria, meeting throughput targets consistently",
                    "Built automation tools reducing repetitive workflow steps by 40%, enabling team to focus on higher-value tasks",
                    "Communicate structured feedback clearly and on schedule — 95%+ quality score maintained across all review cycles",
                ],
            },
        },
        {
            "title":    "AI Data Specialist",
            "company":  "Data Annotation",
            "start":    "Mar 2024",
            "end":      "Present",
            "location": "Remote, Canada",
            "tools":    "Python · Label Studio · SQL · Excel",
            "bullets": {
                "tech": [
                    "Annotate and validate 500+ data samples weekly for ML training across NLP, computer vision, and audio domains",
                    "Develop QA guidelines improving inter annotator agreement by 20% through standardized labeling protocols",
                    "Collaborate with ML engineers on labeling schema design and edge case documentation for model training",
                ],
                "finance": [
                    "Process and validate 500+ structured data samples weekly, applying rigorous QA protocols to ensure data integrity",
                    "Developed documentation standards improving consistency by 20% across annotation teams",
                    "Collaborate with technical teams on schema design and data pipeline integration",
                ],
                "consulting": [
                    "Validate and QA 500+ data samples weekly against defined quality standards, delivering consistent output at scale",
                    "Built documentation frameworks improving team consistency by 20% — structured problem decomposition and process design",
                    "Collaborate cross-functionally with engineers to define requirements and resolve edge cases",
                ],
                "pm": [
                    "Manage quality assurance for 500+ data samples weekly, coordinating with engineers on schema and delivery requirements",
                    "Designed labeling guidelines adopted across the team, improving inter-rater agreement by 20%",
                    "Drive cross-functional collaboration between annotators and ML engineers on data pipeline requirements",
                ],
            },
        },
        {
            "title":    "Solutions Representative (Team Lead)",
            "company":  "Pitch Perfect Solutions",
            "start":    "Sept 2023",
            "end":      "Apr 2024",
            "location": "Remote, Canada",
            "tools":    "CRM Systems · Jira · Slack",
            "bullets": {
                "tech": [
                    "Promoted to Team Lead within 6 months. Earned Employee of the Month twice",
                    "Resolved 150+ customer interactions weekly and escalated complex technical issues to engineering",
                    "Trained 8 new hires on product and CRM workflows, reducing onboarding time by 30%",
                ],
                "finance": [
                    "Promoted to Team Lead within 6 months managing a team of 8 — consistent top performer",
                    "Handled 150+ client interactions weekly with high accuracy on financial product questions",
                    "Trained 8 new hires on compliance workflows and documentation standards",
                ],
                "consulting": [
                    "Promoted to Team Lead within 6 months — led 8-person team, trained new hires, drove 30% onboarding improvement",
                    "Managed 150+ client interactions weekly, diagnosing issues and escalating appropriately",
                    "Documented recurring pain points and proposed workflow improvements adopted by the product team",
                ],
                "pm": [
                    "Promoted to Team Lead within 6 months — managed 8-person team, set priorities, and ran weekly syncs",
                    "Reduced onboarding time by 30% through clear documentation and structured training programs",
                    "Handled 150+ stakeholder interactions weekly, triaged issues, and coordinated resolution across teams",
                ],
            },
        },
        {
            "title":    "Engineering Intern",
            "company":  "Oando PLC",
            "start":    "May 2023",
            "end":      "Sept 2023",
            "location": "Lagos, Nigeria",
            "tools":    "Python · Excel · SQL",
            "bullets": {
                "tech": [
                    "Analyzed 90 days of operational data using Python and Excel, identifying patterns supporting 15% reduction in unplanned maintenance",
                    "Flagged 20+ equipment anomalies through data analysis, preventing potential downtime worth $35K+ in operational costs",
                ],
                "finance": [
                    "Analyzed 90 days of operational and cost data using Python and Excel, supporting 15% reduction in unplanned maintenance spend",
                    "Identified 20+ cost-risk anomalies through data analysis, preventing $35K+ in avoidable operational losses",
                    "Generated weekly KPI reports tracking performance across 4 departments, improving cross-team financial visibility",
                ],
                "consulting": [
                    "Analyzed 90 days of operational data and delivered findings that supported a 15% reduction in unplanned maintenance",
                    "Identified 20+ anomalies flagged to leadership — data-driven recommendations that prevented $35K+ in losses",
                    "Produced weekly summary reports tracking KPIs across 4 departments, improving cross-functional visibility",
                ],
                "pm": [
                    "Coordinated cross-functional data collection across 4 departments and delivered weekly KPI summary reports to leadership",
                    "Analyzed 90 days of operational data, surfacing patterns that drove a 15% reduction in unplanned maintenance",
                    "Flagged 20+ equipment anomalies to operations teams — structured handoffs prevented $35K+ in downtime costs",
                ],
            },
        },
    ],

    "projects": [
        {
            "name":  "Distributed Microservices Payment Gateway",
            "year":  "2025",
            "stack": "Java · Python · Docker · Kubernetes · Terraform · PostgreSQL · Redis · AWS · CI/CD",
            "bullets": [
                "Architected containerized microservices backend with separate services for auth, transactions, and notifications",
                "Implemented reliability patterns including retries, circuit breakers, and idempotency keys, reducing failure cascades by 60% under load",
                "Provisioned infrastructure as code using Terraform with automated deployments via GitHub Actions",
                "Instrumented metrics and logging for production-style observability with alerting",
            ],
            "best_for": ["tech", "backend", "devops", "finance", "fintech"],
        },
        {
            "name":  "Real Time Telemetry System | Solar Racing",
            "year":  "2024",
            "stack": "Python · WebSockets · PostgreSQL · Grafana · Prometheus",
            "bullets": [
                "Built real time dashboards streaming 50+ sensor signals per second with under 100ms latency",
                "Designed alerting system surfacing critical anomalies within 2 seconds",
                "Contributed to team top 10 finish at FSGP 2024 competition",
            ],
            "best_for": ["tech", "data", "systems", "consulting"],
        },
        {
            "name":  "ML Powered Data Analytics Platform",
            "year":  "2025",
            "stack": "Python · React · PyTorch · PostgreSQL · Docker · FastAPI",
            "bullets": [
                "Developed end to end ML pipeline with training, evaluation, and model serving via FastAPI REST endpoints",
                "Reduced inference latency by 35% through batch processing optimization and connection pooling",
                "Deployed containerized services validated under 100+ concurrent requests in load testing",
            ],
            "best_for": ["tech", "ml", "finance", "data"],
        },
        {
            "name":  "Financial Analytics Dashboard",
            "year":  "2025",
            "stack": "Python · SQL · Pandas · PostgreSQL · React · FastAPI",
            "bullets": [
                "Built end to end data pipeline ingesting, cleaning, and visualizing multi-source financial datasets",
                "Designed interactive dashboards surfacing key metrics, trends, and anomalies for decision-making",
                "Automated weekly reporting workflows, reducing manual preparation time by 60%",
            ],
            "best_for": ["finance", "consulting", "data", "pm"],
        },
    ],

    "leadership": [
        {
            "title":  "Software VP",
            "org":    "Solar Racing Team, University of Calgary",
            "period": "2023 to Present",
            "bullets": [
                "Lead 10 person software team building telemetry, data logging, and driver interface systems for competition vehicles",
                "Own architecture decisions, conduct code reviews, and run Agile sprints from design through deployment",
            ],
        },
        {
            "title":  "Junior President",
            "org":    "African Caribbean Students Association",
            "period": "2023 to 2025",
            "bullets": [
                "Managed operations for 200+ members and $35,000 budget across cultural events and student programming",
                "Introduced digital payments increasing dues collection rate by 25%",
            ],
        },
        {
            "title":  "ICT & Math Tutor",
            "org":    "Calgary, AB",
            "period": "2021 to Present",
            "bullets": [
                "Tutored 40+ students in Python, problem-solving, and mathematics with 90%+ improvement rates",
            ],
        },
    ],

    "coursework": {
        "tech":       ["Data Structures and Algorithms", "Software Architecture", "Machine Learning Systems", "Practices in Data Management"],
        "backend":    ["Data Structures and Algorithms", "Software Architecture", "Principles of Software Design", "Software Testing"],
        "ml":         ["Machine Learning Systems", "Applied Deep Learning", "Probability Statistics and ML", "Software Architecture"],
        "data":       ["Practices in Data Management", "Machine Learning Systems", "Data Structures and Algorithms", "Probability Statistics and ML"],
        "finance":    ["Practices in Data Management", "Probability Statistics and ML", "Data Structures and Algorithms", "Software Architecture"],
        "consulting": ["Industry Practice and Communication", "Software Architecture", "Practices in Data Management", "Professional Technical Communication"],
        "pm":         ["Industry Practice and Communication", "Principles of Software Design", "Software Architecture", "Professional Technical Communication"],
        "default":    ["Data Structures and Algorithms", "Software Architecture", "Machine Learning Systems", "Practices in Data Management"],
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# LOCATION RESOLVER
# Priority: Calgary > Remote > Vancouver > Toronto (per user preference)
# ─────────────────────────────────────────────────────────────────────────────

LOCATION_MAP = {
    "vancouver": "Vancouver", "burnaby": "Vancouver", "langley": "Vancouver",
    "surrey": "Vancouver", "richmond, bc": "Vancouver", "bc,": "Vancouver",
    "toronto": "Toronto", "ontario": "Toronto", "mississauga": "Toronto",
    "brampton": "Toronto", "markham": "Toronto", "waterloo": "Toronto",
    "hamilton": "Toronto", "oakville": "Toronto", "vaughan": "Toronto",
    "montreal": "Montreal", "québec": "Montreal", "laval": "Montreal",
    "ottawa": "Ottawa", "kanata": "Ottawa", "gatineau": "Ottawa",
    "calgary": "Calgary", "alberta": "Calgary", "ab,": "Calgary",
    "edmonton": "Calgary", "lethbridge": "Calgary",
    "remote": "default", "anywhere": "default", "canada": "default",
}

CITY_DISPLAY = {
    "Vancouver": "Vancouver, BC",
    "Toronto":   "Toronto, ON",
    "Calgary":   "Calgary, AB",
    "Ottawa":    "Ottawa, ON",
    "Montreal":  "Montreal, QC",
    "default":   "Calgary, AB",
}

PROVINCE_MAP = {
    "Vancouver": "British Columbia",
    "Toronto":   "Ontario",
    "Calgary":   "Alberta",
    "Ottawa":    "Ontario",
    "Montreal":  "Quebec",
    "default":   "Alberta",
}


def resolve_location(job_location: str) -> tuple[str, str]:
    """Returns (city_key, full_street_address)."""
    loc = (job_location or "").lower()
    for keyword, city_key in LOCATION_MAP.items():
        if keyword in loc:
            return city_key, PROFILE["addresses"].get(city_key, PROFILE["addresses"]["default"])
    return "default", PROFILE["addresses"]["default"]


# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class JobDetails:
    title:       str = ""
    company:     str = ""
    location:    str = ""
    description: str = ""
    source_url:  str = ""
    apply_url:   str = ""
    easy_apply:  bool = False
    job_id:      str = ""
    source:      str = ""   # linkedin | github_repo | csv | direct


@dataclass
class ApplicationResult:
    job_id:            str
    title:             str
    company:           str
    location:          str
    apply_url:         str
    status:            str   # submitted | skipped | failed
    error:             str = ""
    resume_path:       str = ""
    cover_letter_path: str = ""
    applied_at:        str = field(default_factory=lambda: datetime.now().isoformat())


# ─────────────────────────────────────────────────────────────────────────────
# JOB SCRAPER — any URL (Ashby, Greenhouse, Lever, Workday, LinkedIn, generic)
# ─────────────────────────────────────────────────────────────────────────────

def scrape_job_from_url(url: str, page: Page) -> JobDetails:
    """
    Navigate to any job listing URL and extract title, company, location,
    and job description. Works on Ashby, Greenhouse, Lever, Workday,
    LinkedIn, and generic HTML pages.
    """
    console.print(f"  [cyan]Scraping:[/cyan] {url[:80]}")
    page.goto(url, timeout=30000)
    time.sleep(random.uniform(2, 4))

    # Expand any "See more" / "Show more" buttons
    for label in ["See more", "Show more", "Read more", "View full description"]:
        try:
            btn = page.locator(f'button:has-text("{label}"), a:has-text("{label}")').first
            if btn.is_visible(timeout=1000):
                btn.click()
                time.sleep(0.5)
        except Exception:
            pass

    html = page.content()
    soup = BeautifulSoup(html, "html.parser")

    # Remove noise tags
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    job = JobDetails(source_url=url, apply_url=url, source="direct")

    # ── Title ────────────────────────────────────────────────────────────────
    title_candidates = [
        soup.find("h1"),
        soup.find(class_=re.compile(r"job.?title|role.?title|position.?title", re.I)),
        soup.find("title"),
    ]
    for el in title_candidates:
        if el and el.get_text(strip=True):
            raw = el.get_text(" ", strip=True)
            # Clean company suffix like "at Acme | Greenhouse"
            raw = re.split(r"\s*[\|·—]\s*", raw)[0].strip()
            job.title = raw[:120]
            break

    # ── Company ──────────────────────────────────────────────────────────────
    company_candidates = [
        soup.find(class_=re.compile(r"company.?name|employer.?name|org.?name", re.I)),
        soup.find(attrs={"data-company": True}),
        soup.find(class_=re.compile(r"brand|logo.?text", re.I)),
    ]
    # Try Ashby pattern: URL contains company slug
    ashby_match = re.search(r"ashbyhq\.com/([^/]+)/", url)
    if ashby_match:
        job.company = ashby_match.group(1).replace("-", " ").replace(".", " ").title()

    for el in company_candidates:
        if el and el.get_text(strip=True) and not job.company:
            job.company = el.get_text(" ", strip=True)[:80]
            break

    # ── Location ─────────────────────────────────────────────────────────────
    location_candidates = [
        soup.find(class_=re.compile(r"location|city|region", re.I)),
        soup.find(attrs={"data-location": True}),
    ]
    for el in location_candidates:
        if el and el.get_text(strip=True):
            job.location = el.get_text(" ", strip=True)[:100]
            break

    # Fallback: search text for Canadian city names
    if not job.location:
        page_text = soup.get_text(" ")
        for city in ["Calgary", "Vancouver", "Toronto", "Ottawa", "Montreal", "Remote", "Canada"]:
            if city in page_text:
                job.location = city
                break

    # ── Description ──────────────────────────────────────────────────────────
    desc_candidates = [
        soup.find(class_=re.compile(r"job.?description|description.?content|job.?detail|posting.?body", re.I)),
        soup.find(id=re.compile(r"job.?description|description", re.I)),
        soup.find("article"),
        soup.find("main"),
    ]
    for el in desc_candidates:
        if el:
            text = el.get_text("\n", strip=True)
            if len(text) > 200:
                job.description = text[:5000]
                break

    # Fallback: grab all body text
    if not job.description:
        job.description = soup.get_text("\n", strip=True)[:5000]

    job.job_id = f"direct_{re.sub(r'[^a-z0-9]', '_', (job.title or 'job').lower()[:20])}_{int(time.time())}"

    console.print(
        f"  [green]Scraped:[/green] {job.title or '(no title)'} @ "
        f"{job.company or '(no company)'} | {job.location or 'Location unknown'}"
    )
    return job


# ─────────────────────────────────────────────────────────────────────────────
# JOB SOURCE: GitHub Repo — negarprh/Canadian-Tech-Internships-2026
# ─────────────────────────────────────────────────────────────────────────────

GITHUB_REPO_URL = "https://raw.githubusercontent.com/negarprh/Canadian-Tech-Internships-2026/main/README.md"

SKIP_ROLES = [
    "merchandise", "hospitality", "apparel", "food", "retail", "sales associate",
    "marketing coordinator", "brand ambassador",
]


def scrape_github_repo(limit: int = 50, skip_closed: bool = True) -> list[JobDetails]:
    console.print("  [cyan]Fetching Canadian-Tech-Internships-2026 repo...[/cyan]")
    try:
        resp = requests.get(GITHUB_REPO_URL, timeout=15)
        resp.raise_for_status()
        md = resp.text
    except Exception as e:
        console.print(f"  [red]GitHub fetch failed: {e}[/red]")
        return []

    jobs = []
    row_re = re.compile(
        r"\|\s*(?:↳\s*)?([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*\[Apply\]\(([^)]+)\)\s*\|\s*([^|]+?)\s*\|",
        re.MULTILINE,
    )
    last_company = ""
    for m in row_re.finditer(md):
        company_raw, role, location, link, _ = m.groups()
        company = company_raw.strip() or last_company
        if company:
            last_company = company

        role = role.strip()
        link = link.strip()

        if skip_closed and not link.startswith("http"):
            continue
        if any(k in role.lower() for k in SKIP_ROLES):
            continue

        jobs.append(JobDetails(
            title=role, company=company, location=location.strip(),
            apply_url=link, source_url=link, source="github_repo",
            job_id=f"gh_{re.sub(r'[^a-z0-9]','_',role.lower()[:18])}_{re.sub(r'[^a-z0-9]','_',company.lower()[:12])}",
        ))
        if len(jobs) >= limit:
            break

    console.print(f"  [green]{len(jobs)}[/green] open roles from GitHub repo")
    return jobs


# ─────────────────────────────────────────────────────────────────────────────
# JOB SOURCE: Indeed (no login needed)
# ─────────────────────────────────────────────────────────────────────────────

INDEED_QUERIES = [
    ("software engineer intern", "Calgary+AB"),
    ("software developer intern", "Vancouver+BC"),
    ("software engineer intern", "Canada"),
    ("backend engineer intern", "Canada"),
    ("data engineer intern", "Canada"),
]

def scrape_indeed(limit: int = 40) -> list[JobDetails]:
    """Scrape Indeed job listings without login using their JSON API endpoint."""
    import urllib.parse

    console.print("  [cyan]Fetching Indeed listings...[/cyan]")
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-CA,en;q=0.9",
    }

    jobs: list[JobDetails] = []
    seen: set[str] = set()

    for query, location in INDEED_QUERIES:
        if len(jobs) >= limit:
            break

        params = {
            "q": query,
            "l": location.replace("+", " "),
            "sort": "date",
            "fromage": "7",   # last 7 days
            "limit": "25",
            "start": "0",
            "radius": "100",
        }
        url = "https://ca.indeed.com/jobs?" + urllib.parse.urlencode(params)
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            console.print(f"  [yellow]Indeed fetch failed ({query}): {e}[/yellow]")
            continue

        # Parse job cards from HTML
        card_re = re.compile(
            r'data-jk="([a-f0-9]+)"[^>]*>.*?'
            r'class="jobTitle"[^>]*>.*?<span[^>]*>([^<]+)</span>.*?'
            r'data-testid="company-name"[^>]*>([^<]+)<.*?'
            r'data-testid="text-location"[^>]*>([^<]+)<',
            re.DOTALL,
        )
        for m in card_re.finditer(resp.text):
            if len(jobs) >= limit:
                break
            jk, title, company, loc = m.group(1), m.group(2), m.group(3), m.group(4)
            if jk in seen:
                continue
            seen.add(jk)
            title   = title.strip()
            company = company.strip()
            loc     = loc.strip()
            if any(k in title.lower() for k in SKIP_ROLES):
                continue
            apply_url = f"https://ca.indeed.com/viewjob?jk={jk}"
            jobs.append(JobDetails(
                title=title, company=company, location=loc,
                apply_url=apply_url, source_url=apply_url, source="indeed",
                job_id=f"indeed_{jk}",
            ))

        time.sleep(random.uniform(3, 6))   # polite delay between Indeed queries

    console.print(f"  [green]{len(jobs)}[/green] open roles from Indeed")
    return jobs


# ─────────────────────────────────────────────────────────────────────────────
# JOB SOURCE: Local file (CSV or MD)
# ─────────────────────────────────────────────────────────────────────────────

def load_jobs_from_file(file_path: str) -> list[JobDetails]:
    path = Path(file_path)
    if not path.exists():
        console.print(f"  [red]File not found: {file_path}[/red]")
        return []

    jobs = []
    suffix = path.suffix.lower()

    if suffix == ".csv":
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                link = (
                    row.get("Apply link") or row.get("apply_link") or
                    row.get("URL") or row.get("url") or row.get("Link") or ""
                ).strip()
                if not link or not link.startswith("http"):
                    continue
                jobs.append(JobDetails(
                    title=(row.get("Role title") or row.get("Role") or "").strip(),
                    company=(row.get("Company") or "").strip(),
                    location=(row.get("Location") or "Canada").strip(),
                    apply_url=link, source_url=link, source="csv",
                    job_id=f"csv_{len(jobs):04d}",
                ))
    elif suffix in (".md", ".txt"):
        for i, link in enumerate(re.findall(r"https?://[^\s\)\"\']+", path.read_text(encoding="utf-8"))):
            if any(s in link for s in ["github.com", "twitter", "linkedin.com/in/"]):
                continue
            jobs.append(JobDetails(apply_url=link, source_url=link, source="file", job_id=f"file_{i:04d}"))

    console.print(f"  Loaded [green]{len(jobs)}[/green] jobs from {path.name}")
    return jobs


# ─────────────────────────────────────────────────────────────────────────────
# CLAUDE RESUME + COVER LETTER GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

CATEGORY_SUMMARIES = {
    "tech":       "summary_tech",
    "finance":    "summary_finance",
    "consulting": "summary_consulting",
    "pm":         "summary_pm",
}


class ResumeGenerator:
    def __init__(self):
        api_key = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("CLAUDE_API_KEY not set in .env")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = os.getenv("CLAUDE_MODEL", "claude-opus-4-6")

    def generate(self, job: JobDetails, category: str = "tech") -> dict:
        city_key, address = resolve_location(job.location)
        prompt = self._build_prompt(job, city_key, address, category)
        console.print(f"  [dim]Claude generating [{category}] resume + cover letter...[/dim]")

        resp = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()

        m = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL) or re.search(r"\{.*\}", raw, re.DOTALL)
        raw_json = m.group(1) if m and m.lastindex else (m.group(0) if m else raw)

        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            data = {"resume_md": raw, "cover_letter": "", "role_type": "default"}

        data["city_key"] = city_key
        data["address"] = address
        return data

    def _build_prompt(self, job: JobDetails, city_key: str, address: str, category: str) -> str:
        city_display = CITY_DISPLAY.get(city_key, "Calgary, AB")
        summary_key  = CATEGORY_SUMMARIES.get(category, "summary_tech")
        summary      = PROFILE[summary_key]
        coursework   = PROFILE["coursework"].get(category, PROFILE["coursework"]["default"])

        # Pull correct bullet variant per experience entry
        exp_tailored = []
        for exp in PROFILE["experience"]:
            bullets_map = exp.get("bullets", {})
            bullets = bullets_map.get(category) or bullets_map.get("tech") or bullets_map.get("default", [])
            exp_tailored.append({
                "title":    exp["title"],
                "company":  exp["company"],
                "start":    exp["start"],
                "end":      exp["end"],
                "location": exp["location"],
                "tools":    exp.get("tools", ""),
                "bullets":  bullets,
            })

        # Pick 2 most relevant projects
        projects = sorted(
            PROFILE["projects"],
            key=lambda p: 1 if category in p["best_for"] else 0,
            reverse=True,
        )[:2]

        profile_json = json.dumps({
            "name": PROFILE["name"], "email": PROFILE["email"],
            "phone": PROFILE["phone"], "address": address,
            "city_display": city_display,
            "github": PROFILE["github"], "linkedin": PROFILE["linkedin"],
            "portfolio": PROFILE["portfolio"],
            "university": PROFILE["university"], "degree": PROFILE["degree"],
            "graduation": PROFILE["graduation"],
            "summary": summary,
            "certifications": PROFILE["certifications"],
            "experience": exp_tailored,
            "projects": projects,
            "leadership": PROFILE["leadership"],
            "coursework": coursework,
        }, indent=2)

        availability = "May 1, 2026 (earlier if possible). Latest start: June 1, 2026."

        return f"""
You are generating a tailored resume and cover letter for Moyosore Ogunjobi.

CATEGORY: {category.upper()}  (tech | finance | consulting | pm)
JOB TITLE: {job.title or 'Not specified'}
COMPANY: {job.company or 'Not specified'}
LOCATION: {job.location or 'Canada'}
ADDRESS IN RESUME HEADER: {address}
CITY DISPLAY: {city_display}
AVAILABILITY: {availability}

JOB DESCRIPTION:
{(job.description or '')[:4000]}

CANDIDATE PROFILE (JSON):
{profile_json}

────────────────────────────────────────────────────────────────
RESUME RULES — follow all exactly:
────────────────────────────────────────────────────────────────
1. Summary: copy the provided summary VERBATIM. Do not rewrite it.
2. Header address: use "{address}". Never write "Open to relocation".
3. Graduation: always "Expected May 2027".
4. Use the pre-selected bullet variants already in the experience data.
5. Use the 2 projects already selected (in order provided).
6. Use the pre-selected coursework list.
7. Reorder certifications so the most relevant cert for this role comes first.
8. No em dashes anywhere. Use commas or periods.
9. Output clean markdown. One page of content.
10. Skills section: lead with languages most relevant to this JD.
11. If category is finance: add Excel, SQL, and data analytics tools prominently to skills.
12. If category is pm: add project coordination tools (Jira, Confluence, Notion, Agile).
13. If category is consulting: add communication and analytical tools.

────────────────────────────────────────────────────────────────
COVER LETTER RULES — plain text only, no markdown:
────────────────────────────────────────────────────────────────
1. Hook (2-3 sentences): something specific about {job.company or 'the company'}.
   Reference their product, mission, a recent announcement, or why this role matters.
   No generic openers. No "I am writing to express my interest."
2. Story (3-4 sentences): ONE project. Context, what you built, ONE metric.
3. How you work (2-3 sentences): ownership, quality bar, collaboration.
4. Coursework (1-2 sentences): 2-3 relevant courses.
5. Close: graduation May 2027, available full-time from May 1 2026, Canada work authorization.
6. Sign off: "Best regards, Moyosore Ogunjobi"
7. Max 2 numbers in entire letter. No em dashes. No semicolons. Sound human.
8. Writing style: clear, direct, active voice. No clichés. No "passionate about".
   No "leverage". No "utilize". No "excited to". No "would love the opportunity".

────────────────────────────────────────────────────────────────
OUTPUT — JSON only, no other text before or after:
────────────────────────────────────────────────────────────────
{{
  "resume_md": "<full resume in clean markdown>",
  "cover_letter": "<full cover letter as plain text paragraphs, no markdown>",
  "role_type": "<specific role type: backend|ml|data|finance|consulting|pm|systems|fullstack>",
  "coursework_used": ["Course A", "Course B", "Course C", "Course D"]
}}
"""


# ─────────────────────────────────────────────────────────────────────────────
# PDF BUILDER
# ─────────────────────────────────────────────────────────────────────────────

RESUME_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: 'Times New Roman', serif;
    font-size: 9.5pt; line-height: 1.18;
    margin: 0.5in 0.55in 0.5in 0.55in; color: #000;
}
h1 { text-align: center; font-size: 16pt; font-weight: 700; margin-bottom: 2px; }
.contact { text-align: center; font-size: 8pt; margin-bottom: 5px; }
.contact a { color: #000; text-decoration: none; }
h2 {
    font-size: 9.5pt; font-weight: 700; text-transform: uppercase;
    border-bottom: 0.8px solid #000; margin: 5px 0 2px 0;
}
.entry-row {
    display: flex; justify-content: space-between;
    font-size: 9.5pt; font-weight: 700; margin: 1px 0 0 0;
}
.entry-sub {
    display: flex; justify-content: space-between;
    font-size: 9.5pt; font-style: italic; margin: 0 0 1px 0;
}
.tech { font-style: italic; font-size: 9pt; margin: 0 0 2px 2px; }
ul { margin: 1px 0 3px 0; padding-left: 16px; }
li { margin-bottom: 1px; font-size: 9.5pt; }
p { margin: 0 0 2px 0; font-size: 9.5pt; }
strong { font-weight: 700; }
em { font-style: italic; }
"""

COVER_CSS = """
body {
    font-family: 'Times New Roman', serif;
    font-size: 11pt; line-height: 1.6; margin: 1in; color: #000;
}
.header { text-align: center; margin-bottom: 20px; }
.header h1 { font-size: 15pt; margin: 0; }
.header p { font-size: 10pt; margin: 3px 0 0 0; }
p { margin: 0 0 14px 0; }
.sig { margin-top: 20px; }
"""


class PDFBuilder:
    def __init__(self, output_dir: Path):
        self.out = output_dir
        self.out.mkdir(parents=True, exist_ok=True)

    def build_resume(self, resume_md: str, address: str, job: JobDetails) -> Path:
        html = self._md_to_html(resume_md, address)
        path = self.out / f"resume_{self._slug(job)}.pdf"
        WPHtml(string=html).write_pdf(str(path))
        return path

    def build_cover_letter(self, cover_text: str, address: str, job: JobDetails) -> Path:
        html = self._cl_to_html(cover_text, address, job)
        path = self.out / f"cover_{self._slug(job)}.pdf"
        WPHtml(string=html).write_pdf(str(path))
        return path

    def _slug(self, job: JobDetails) -> str:
        c = re.sub(r"[^a-z0-9]", "_", (job.company or "co").lower())[:18]
        t = re.sub(r"[^a-z0-9]", "_", (job.title or "role").lower())[:18]
        return f"{c}_{t}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _md_to_html(self, md: str, address: str) -> str:
        lines = md.strip().split("\n")
        parts = [f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{RESUME_CSS}</style></head><body>"]
        i = 0
        in_ul = False

        def close_ul():
            nonlocal in_ul
            if in_ul:
                parts.append("</ul>"); in_ul = False

        def inl(t):
            t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
            t = re.sub(r"\*(.+?)\*", r"<em>\1</em>", t)
            return t

        while i < len(lines):
            line = lines[i].rstrip()
            if line.strip().startswith("<div") or line.strip().startswith("</div"):
                i += 1; continue
            if line.startswith("# "):
                close_ul()
                parts.append(f"<h1>{line[2:].strip()}</h1>")
                if i + 1 < len(lines) and lines[i + 1].strip():
                    parts.append(f'<p class="contact">{lines[i+1].strip()}</p>')
                    i += 2
                else:
                    i += 1
                continue
            if line.startswith("## "):
                close_ul(); parts.append(f"<h2>{line[3:].strip()}</h2>"); i += 1; continue
            if line.startswith("### "):
                close_ul()
                parts.append(f'<div class="entry-row"><span>{inl(line[4:].strip())}</span></div>')
                i += 1; continue
            if line.startswith(("- ", "* ")):
                if not in_ul:
                    parts.append("<ul>"); in_ul = True
                parts.append(f"<li>{inl(line[2:].strip())}</li>"); i += 1; continue
            if line.startswith("**") and "|" in line:
                close_ul()
                seg = [s.strip() for s in line.split("|")]
                left = inl(seg[0]); right = inl(seg[-1]) if len(seg) > 1 else ""
                mid = [inl(s) for s in seg[1:-1]] if len(seg) > 2 else []
                parts.append(f'<div class="entry-row"><span>{left}</span><span>{right}</span></div>')
                if mid:
                    parts.append(f'<div class="entry-sub"><span>{" | ".join(mid)}</span></div>')
                i += 1; continue
            if line.strip().startswith("*") and not line.strip().startswith("**"):
                close_ul()
                parts.append(f'<p class="tech"><em>{line.strip().strip("*")}</em></p>')
                i += 1; continue
            if not line.strip():
                close_ul(); i += 1; continue
            close_ul(); parts.append(f"<p>{inl(line.strip())}</p>"); i += 1

        close_ul()
        parts.append("</body></html>")
        return "\n".join(parts)

    def _cl_to_html(self, text: str, address: str, job: JobDetails) -> str:
        date_str = datetime.now().strftime("%B %d, %Y")
        paras = [p.strip() for p in text.strip().split("\n\n") if p.strip()]
        body = "\n".join(f"<p>{p}</p>" for p in paras if not p.lower().startswith("best regards"))
        return f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><style>{COVER_CSS}</style></head>
<body>
<div class="header">
  <h1>{PROFILE['name']}</h1>
  <p>{PROFILE['email']} &bull; {PROFILE['phone']} &bull; {address}</p>
</div>
<p>{date_str}</p>
<p>{job.company or 'Hiring Team'}<br>Hiring Team<br>{job.location or 'Canada'}</p>
{body}
<div class="sig"><p>Best regards,<br><strong>{PROFILE['name']}</strong><br>
Software Engineering, University of Calgary &rsquo;27<br>
AWS Certified (4x) &bull; {PROFILE['github']} &bull; {PROFILE['portfolio']}</p></div>
</body></html>"""


# ─────────────────────────────────────────────────────────────────────────────
# LINKEDIN BOT
# ─────────────────────────────────────────────────────────────────────────────

COOKIES_FILE = Path.home() / ".cache" / "moyo_apply_bot" / "session.json"

DAILY_LIMIT = 120  # hard cap — enforced in main()


class LinkedInBot:
    def __init__(self, page: Page, context: BrowserContext):
        self.page = page
        self.ctx  = context

    def login(self) -> bool:
        email    = os.getenv("LINKEDIN_EMAIL", "")
        password = os.getenv("LINKEDIN_PASSWORD", "")

        if self._load_cookies():
            self.page.goto("https://www.linkedin.com/feed/", timeout=20000)
            self._sleep(2, 3)
            if any(x in self.page.url for x in ["feed", "mynetwork", "jobs"]):
                console.print("  [green]LinkedIn session restored[/green]")
                return True

        if not email or not password:
            console.print("[red]Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD in .env[/red]")
            return False

        console.print("  Logging in to LinkedIn...")
        self.page.goto("https://www.linkedin.com/login", timeout=20000)
        self._sleep(1, 2)
        self.page.fill("#username", email)
        self._sleep(0.3, 0.7)
        self.page.fill("#password", password)
        self._sleep(0.5, 1.0)
        self.page.click('[type="submit"]')
        self._sleep(3, 5)

        if "checkpoint" in self.page.url or "challenge" in self.page.url:
            console.print("[yellow]LinkedIn verification — complete it in the browser then press Enter.[/yellow]")
            input()
            self._sleep(2, 3)

        if any(x in self.page.url for x in ["feed", "mynetwork", "jobs"]):
            self._save_cookies()
            console.print("  [green]Logged in[/green]")
            return True

        console.print(f"[red]Login failed. URL: {self.page.url}[/red]")
        return False

    def scrape_job(self, url: str) -> Optional[JobDetails]:
        m = re.search(r"/jobs/view/(\d+)", url)
        job_id = m.group(1) if m else str(int(time.time()))
        clean_url = f"https://www.linkedin.com/jobs/view/{job_id}/" if m else url

        self.page.goto(clean_url, timeout=30000)
        self._sleep(2, 4)
        try:
            btn = self.page.query_selector('button[aria-label*="more"]')
            if btn:
                btn.click(); self._sleep(0.5, 1)
        except Exception:
            pass

        job = JobDetails(job_id=job_id, source_url=clean_url, source="linkedin")

        for sel in ["h1.t-24", "h1", ".job-details-jobs-unified-top-card__job-title"]:
            try:
                t = self.page.locator(sel).first.inner_text(timeout=3000).strip()
                if t:
                    job.title = t; break
            except Exception:
                pass
        for sel in [".job-details-jobs-unified-top-card__company-name a", ".topcard__org-name-link"]:
            try:
                c = self.page.locator(sel).first.inner_text(timeout=3000).strip()
                if c:
                    job.company = c; break
            except Exception:
                pass
        for sel in [".job-details-jobs-unified-top-card__bullet", ".topcard__flavor--bullet"]:
            try:
                l = self.page.locator(sel).first.inner_text(timeout=3000).strip()
                if l:
                    job.location = l; break
            except Exception:
                pass
        for sel in [".jobs-description__content", "#job-details", ".job-view-layout"]:
            try:
                d = self.page.locator(sel).first.inner_text(timeout=6000).strip()
                if d:
                    job.description = d; break
            except Exception:
                pass

        try:
            easy_btn = self.page.query_selector('.jobs-apply-button--top-card button[aria-label*="Easy Apply"]')
            job.easy_apply = bool(easy_btn)
            if not job.easy_apply:
                ext = self.page.query_selector('.jobs-apply-button--top-card a[href]')
                if ext:
                    job.apply_url = ext.get_attribute("href") or ""
        except Exception:
            pass

        console.print(
            f"  [green]Scraped:[/green] {job.title} @ {job.company} | "
            f"{job.location} | {'Easy Apply' if job.easy_apply else 'External'}"
        )
        return job

    def get_recommended(self, limit: int = 10) -> list[str]:
        self.page.goto("https://www.linkedin.com/jobs/", timeout=20000)
        self._sleep(2, 3)
        return self._collect_urls(limit)

    def search(self, query: str, limit: int = 10) -> list[str]:
        enc = requests.utils.quote(query)
        self.page.goto(
            f"https://www.linkedin.com/jobs/search/?keywords={enc}&f_WT=2&location=Canada",
            timeout=20000,
        )
        self._sleep(2, 3)
        return self._collect_urls(limit)

    def _collect_urls(self, limit: int) -> list[str]:
        urls, seen = [], set()
        for _ in range(10):
            for a in self.page.query_selector_all('a[href*="/jobs/view/"]'):
                href = a.get_attribute("href") or ""
                m = re.search(r"/jobs/view/(\d+)", href)
                if m and m.group(1) not in seen:
                    seen.add(m.group(1))
                    urls.append(f"https://www.linkedin.com/jobs/view/{m.group(1)}/")
                if len(urls) >= limit:
                    return urls
            self.page.evaluate("window.scrollBy(0, 900)")
            self._sleep(1.5, 2.5)
        return urls[:limit]

    def easy_apply(self, job: JobDetails, resume_pdf: Path, cl_pdf: Path) -> bool:
        self.page.goto(job.source_url, timeout=20000)
        self._sleep(2, 3)
        try:
            self.page.locator('button:has-text("Easy Apply")').first.click(timeout=5000)
            self._sleep(1, 2)
        except Exception as e:
            console.print(f"  [red]Easy Apply button not found: {e}[/red]")
            return False

        for _ in range(12):
            self._sleep(0.5, 1)
            try:
                inp = self.page.query_selector('[name*="phone"], input[placeholder*="phone"]')
                if inp and not inp.input_value():
                    inp.fill(PROFILE["phone_digits"])
            except Exception:
                pass
            try:
                f = self.page.query_selector('input[type="file"]')
                if f:
                    f.set_input_files(str(resume_pdf)); self._sleep(1, 2)
            except Exception:
                pass
            result = self._advance()
            if result == "submitted":
                console.print("  [green]Easy Apply submitted[/green]")
                return True
            if result == "error":
                break
        return False

    def get_external_apply_url(self, job: JobDetails) -> Optional[str]:
        self.page.goto(job.source_url, timeout=20000)
        self._sleep(2, 3)
        try:
            with self.page.expect_popup(timeout=8000) as p:
                self.page.locator(
                    'button:has-text("Apply"), a:has-text("Apply on company website")'
                ).first.click()
            popup = p.value
            popup.wait_for_load_state("domcontentloaded", timeout=15000)
            return popup.url
        except Exception:
            try:
                return self.page.locator('a[href*="apply"]').first.get_attribute("href", timeout=3000)
            except Exception:
                return None

    def _advance(self) -> str:
        for label in ["Submit application", "Submit", "Review", "Next", "Continue", "Done"]:
            try:
                btn = self.page.locator(f'button:has-text("{label}")').first
                if btn.is_visible(timeout=1000):
                    btn.click(); self._sleep(1, 2)
                    return "submitted" if label in ("Submit application", "Submit") else "next"
            except Exception:
                pass
        return "error"

    def _save_cookies(self):
        COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
        COOKIES_FILE.write_text(json.dumps(self.ctx.cookies()))

    def _load_cookies(self) -> bool:
        if not COOKIES_FILE.exists():
            return False
        try:
            self.ctx.add_cookies(json.loads(COOKIES_FILE.read_text()))
            return True
        except Exception:
            return False

    @staticmethod
    def _sleep(lo=0.5, hi=1.5):
        time.sleep(random.uniform(lo, hi))


# ─────────────────────────────────────────────────────────────────────────────
# APPLICATION BOT — external ATS filler
# ─────────────────────────────────────────────────────────────────────────────

class ApplicationBot:
    def __init__(self, browser: Browser):
        self.browser = browser

    def apply(self, job: JobDetails, resume_pdf: Path, cl_pdf: Path) -> bool:
        url = job.apply_url or job.source_url
        ats = self._detect_ats(url)
        console.print(f"  ATS: [cyan]{ats}[/cyan]")

        page = self.browser.new_page()
        try:
            city_key, address = resolve_location(job.location)
            ctx = {
                "page":     page,
                "address":  address,
                "city":     address.split(",")[0].strip() if "," in address else PROFILE["default_city"],
                "province": PROVINCE_MAP.get(city_key, "Alberta"),
            }
            return {
                "workday":    self._workday,
                "greenhouse": self._greenhouse,
                "lever":      self._lever,
                "cisco":      self._cisco,
                "icims":      self._icims,
                "ashby":      self._ashby,
                "generic":    self._generic,
            }.get(ats, self._generic)(url, job, resume_pdf, cl_pdf, ctx)
        except Exception as e:
            console.print(f"  [red]ATS error: {e}[/red]")
            return False
        finally:
            page.close()

    def _detect_ats(self, url: str) -> str:
        u = url.lower()
        if "myworkdayjobs" in u or "/workday" in u:    return "workday"
        if "greenhouse.io" in u:                        return "greenhouse"
        if "lever.co" in u:                             return "lever"
        if "cisco.com" in u or "careers.cisco" in u:   return "cisco"
        if "icims.com" in u:                            return "icims"
        if "ashbyhq.com" in u:                         return "ashby"
        return "generic"

    def _workday(self, url, job, res, cl, ctx) -> bool:
        p = ctx["page"]
        p.goto(url, timeout=30000); self._w(2, 3)
        self._click(p, 'button:has-text("Apply Now"), a:has-text("Apply Now")')
        self._w(2, 3)
        self._fill_empty(p, '[data-automation-id*="firstName"]', PROFILE["name"].split()[0])
        self._fill_empty(p, '[data-automation-id*="lastName"]', PROFILE["name"].split()[-1])
        self._fill_empty(p, 'input[data-automation-id*="email"]', PROFILE["email"])
        self._fill_empty(p, 'input[data-automation-id*="phone"]', PROFILE["phone_digits"])
        self._fill_empty(p, 'input[data-automation-id*="city"]', ctx["city"])
        self._select_fuzzy(p, '[data-automation-id*="country"]', "Canada")
        self._upload(p, 'input[type="file"]', res); self._w(1, 2)
        self._click(p, 'button[data-automation-id*="next-btn"]'); self._w(1, 2)
        return self._submit(p)

    def _greenhouse(self, url, job, res, cl, ctx) -> bool:
        p = ctx["page"]
        apply_url = url if "apply" in url else url.rstrip("/") + "?gh_src=auto"
        p.goto(apply_url, timeout=30000); self._w(2, 3)
        self._fill_label(p, "First Name", PROFILE["name"].split()[0])
        self._fill_label(p, "Last Name", PROFILE["name"].split()[-1])
        self._fill_label(p, "Email", PROFILE["email"])
        self._fill_label(p, "Phone", PROFILE["phone_digits"])
        self._upload(p, '#resume input[type="file"], input[name="resume"]', res); self._w(1, 2)
        try:
            self._upload(p, '#cover_letter input[type="file"]', cl)
        except Exception:
            pass
        return self._submit(p)

    def _lever(self, url, job, res, cl, ctx) -> bool:
        p = ctx["page"]
        apply_url = url if url.endswith("/apply") else url.rstrip("/") + "/apply"
        p.goto(apply_url, timeout=30000); self._w(2, 3)
        self._fill_any(p, ["name", "fullName"], PROFILE["name"])
        self._fill_any(p, ["email"], PROFILE["email"])
        self._fill_any(p, ["phone"], PROFILE["phone_digits"])
        self._upload(p, 'input[type="file"][name*="resume"]', res); self._w(1, 2)
        return self._submit(p)

    def _ashby(self, url, job, res, cl, ctx) -> bool:
        """Handles Ashby HQ applications — e.g. jobs.ashbyhq.com/company/uuid"""
        p = ctx["page"]
        p.goto(url, timeout=30000); self._w(2, 4)
        # Ashby shows job posting first — look for Apply button
        self._click(p, 'a:has-text("Apply"), button:has-text("Apply"), a:has-text("Apply for this job")')
        self._w(2, 3)
        # Fill personal info
        self._fill_any(p, ["name", "fullName", "full_name", "applicantName"], PROFILE["name"])
        self._fill_any(p, ["firstName", "first_name"], PROFILE["name"].split()[0])
        self._fill_any(p, ["lastName", "last_name"], PROFILE["name"].split()[-1])
        self._fill_any(p, ["email", "emailAddress"], PROFILE["email"])
        self._fill_any(p, ["phone", "phoneNumber", "mobile"], PROFILE["phone_digits"])
        self._fill_any(p, ["city", "location"], ctx["city"])
        self._select_fuzzy(p, 'select[name*="country"], select[id*="country"]', "Canada")
        # Upload resume
        self._upload(p, 'input[type="file"]', res); self._w(1, 2)
        # LinkedIn profile field if present
        try:
            li_inp = p.locator('input[placeholder*="LinkedIn"], input[name*="linkedin"]').first
            if li_inp.is_visible(timeout=1000) and not li_inp.input_value():
                li_inp.fill(f"https://{PROFILE['linkedin']}")
        except Exception:
            pass
        return self._submit(p)

    def _cisco(self, url, job, res, cl, ctx) -> bool:
        p = ctx["page"]
        p.goto(url, timeout=30000); self._w(2, 4)
        self._click(p, 'a:has-text("Apply"), button:has-text("Apply")')
        self._w(2, 3)
        self._select_fuzzy(p, 'select[name*="country"], select[id*="country"]', "Canada")
        self._w(0.5, 1)
        self._fill_any(p, ["firstName", "first_name"], PROFILE["name"].split()[0])
        self._fill_any(p, ["lastName", "last_name"], PROFILE["name"].split()[-1])
        self._fill_any(p, ["city"], ctx["city"])
        self._select_fuzzy(p, 'select[name*="state"], select[name*="province"]', ctx["province"])
        self._fill_any(p, ["email", "emailAddress"], PROFILE["email"])
        self._fill_any(p, ["phone", "phoneNumber"], PROFILE["phone_digits"])
        try:
            p.locator('label:has-text("No")').first.click()
        except Exception:
            pass
        try:
            for cb in p.query_selector_all('input[type="checkbox"]')[:3]:
                if not cb.is_checked():
                    cb.click(); self._w(0.2, 0.4)
        except Exception:
            pass
        self._click_next(p); self._w(2, 3)
        self._upload(p, 'input[type="file"]', res); self._w(2, 3)
        self._click_next(p); self._w(1, 2)
        for _ in range(6):
            if self._submit(p, dry=True):
                return self._submit(p)
            self._click_next(p); self._w(1, 2)
        return False

    def _icims(self, url, job, res, cl, ctx) -> bool:
        p = ctx["page"]
        p.goto(url, timeout=30000); self._w(2, 3)
        self._click(p, 'input[value="Apply Now"], a:has-text("Apply Now")')
        self._w(2, 3)
        self._fill_any(p, ["firstname", "firstName"], PROFILE["name"].split()[0])
        self._fill_any(p, ["lastname", "lastName"], PROFILE["name"].split()[-1])
        self._fill_any(p, ["email"], PROFILE["email"])
        self._fill_any(p, ["phone"], PROFILE["phone_digits"])
        self._upload(p, 'input[type="file"]', res); self._w(1, 2)
        return self._submit(p)

    def _generic(self, url, job, res, cl, ctx) -> bool:
        p = ctx["page"]
        p.goto(url, timeout=30000); self._w(2, 4)
        field_map = {
            "first": PROFILE["name"].split()[0], "fname": PROFILE["name"].split()[0],
            "last":  PROFILE["name"].split()[-1], "lname": PROFILE["name"].split()[-1],
            "name":  PROFILE["name"], "fullname": PROFILE["name"],
            "email": PROFILE["email"], "phone": PROFILE["phone_digits"],
            "city":  ctx["city"],
        }
        for inp in p.query_selector_all('input[type="text"], input[type="email"], input[type="tel"]'):
            try:
                combined = " ".join([
                    (inp.get_attribute("placeholder") or "").lower(),
                    (inp.get_attribute("name") or "").lower(),
                    (inp.get_attribute("id") or "").lower(),
                ])
                for key, val in field_map.items():
                    if key in combined and not inp.input_value():
                        inp.fill(val); self._w(0.2, 0.4); break
            except Exception:
                pass
        self._upload(p, 'input[type="file"]', res); self._w(1, 2)
        return self._submit(p)

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _fill_label(self, p, label, val):
        try:
            for_id = p.locator(f'label:has-text("{label}")').first.get_attribute("for")
            if for_id:
                inp = p.locator(f"#{for_id}").first
                if not inp.input_value():
                    inp.fill(val)
        except Exception:
            pass

    def _fill_any(self, p, names, val):
        for n in ([names] if isinstance(names, str) else names):
            try:
                inp = p.locator(f'input[name="{n}"], input[id="{n}"]').first
                if inp.is_visible(timeout=1000) and not inp.input_value():
                    inp.fill(val); return
            except Exception:
                pass

    def _fill_empty(self, p, sel, val):
        try:
            inp = p.locator(sel).first
            if inp.is_visible(timeout=2000) and not inp.input_value():
                inp.fill(val)
        except Exception:
            pass

    def _select_fuzzy(self, p, sel, val):
        try:
            el = p.locator(sel).first
            if el.is_visible(timeout=2000):
                opts = el.locator("option").all_inner_texts()
                match = next((o for o in opts if val.lower() in o.lower()), None)
                if match:
                    el.select_option(label=match)
        except Exception:
            pass

    def _upload(self, p, sel, path):
        try:
            inp = p.locator(sel).first
            if inp.count() > 0:
                inp.set_input_files(str(path)); self._w(1, 2)
        except Exception:
            pass

    def _click(self, p, sel):
        try:
            btn = p.locator(sel).first
            if btn.is_visible(timeout=3000):
                btn.click()
        except Exception:
            pass

    def _click_next(self, p):
        for label in ["Next", "Continue", "Save and Continue"]:
            try:
                btn = p.locator(f'button:has-text("{label}"), input[value="{label}"]').first
                if btn.is_visible(timeout=2000):
                    btn.click(); return
            except Exception:
                pass

    def _submit(self, p, dry=False) -> bool:
        for label in ["Submit application", "Submit Application", "Submit", "Send Application"]:
            try:
                btn = p.locator(f'button:has-text("{label}"), input[value="{label}"]').first
                if btn.is_visible(timeout=2000):
                    if not dry:
                        btn.click(); self._w(2, 3)
                        console.print("  [green]Submitted[/green]")
                    return True
            except Exception:
                pass
        return False

    @staticmethod
    def _w(lo=0.5, hi=1.5):
        time.sleep(random.uniform(lo, hi))


# ─────────────────────────────────────────────────────────────────────────────
# LOGGER
# ─────────────────────────────────────────────────────────────────────────────

class ApplicationLogger:
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = log_dir / f"applications_{datetime.now().strftime('%Y%m%d')}.csv"
        self.results: list[ApplicationResult] = []
        if not self.log_file.exists():
            with open(self.log_file, "w", newline="") as f:
                csv.DictWriter(f, fieldnames=list(ApplicationResult.__dataclass_fields__.keys())).writeheader()

    def log(self, result: ApplicationResult):
        self.results.append(result)
        with open(self.log_file, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=list(ApplicationResult.__dataclass_fields__.keys())).writerow(asdict(result))
        col = "green" if result.status == "submitted" else "red" if result.status == "failed" else "yellow"
        console.print(f"  [{col}]{result.status.upper()}[/{col}] — {result.title} @ {result.company}")

    def today_submitted_count(self) -> int:
        """Count submitted applications in today's log file to enforce daily limit."""
        if not self.log_file.exists():
            return 0
        count = 0
        with open(self.log_file, newline="") as f:
            for row in csv.DictReader(f):
                if row.get("status") == "submitted":
                    count += 1
        return count

    def summary(self):
        submitted = sum(1 for r in self.results if r.status == "submitted")
        failed    = sum(1 for r in self.results if r.status == "failed")
        skipped   = sum(1 for r in self.results if r.status == "skipped")
        t = Table(box=box.SIMPLE, title="Session Summary")
        t.add_column("Job", style="cyan"); t.add_column("Company"); t.add_column("Status")
        for r in self.results:
            col = "green" if r.status == "submitted" else "red" if r.status == "failed" else "yellow"
            t.add_row(r.title[:42], r.company[:24], f"[{col}]{r.status}[/{col}]")
        console.print(t)
        console.print(
            f"[bold]Total: {len(self.results)}[/bold] | "
            f"[green]Submitted: {submitted}[/green] | "
            f"[red]Failed: {failed}[/red] | "
            f"[yellow]Skipped: {skipped}[/yellow]"
        )
        console.print(f"Log: {self.log_file}")


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE — single job end-to-end
# ─────────────────────────────────────────────────────────────────────────────

def process_job(
    job: JobDetails,
    linkedin_bot: Optional[LinkedInBot],
    app_bot: ApplicationBot,
    generator: ResumeGenerator,
    pdf_builder: PDFBuilder,
    logger: ApplicationLogger,
    category: str = "tech",
    dry_run: bool = False,
) -> bool:
    """Returns True if submitted successfully."""
    console.print(f"\n  [bold]Processing:[/bold] {job.title or job.apply_url[:60]} @ {job.company or '?'}")

    # Generate
    try:
        gen = generator.generate(job, category=category)
    except Exception as e:
        console.print(f"  [red]Claude error: {e}[/red]")
        logger.log(ApplicationResult(
            job_id=job.job_id, title=job.title, company=job.company,
            location=job.location, apply_url=job.apply_url or job.source_url,
            status="failed", error=str(e),
        ))
        return False

    address = gen.get("address", PROFILE["addresses"]["default"])

    # Build PDFs
    try:
        resume_pdf = pdf_builder.build_resume(gen["resume_md"], address, job)
        cover_pdf  = pdf_builder.build_cover_letter(gen["cover_letter"], address, job)
        console.print(f"  [green]PDFs:[/green] {resume_pdf.name}")
    except Exception as e:
        console.print(f"  [red]PDF error: {e}[/red]")
        logger.log(ApplicationResult(
            job_id=job.job_id, title=job.title, company=job.company,
            location=job.location, apply_url=job.apply_url or job.source_url,
            status="failed", error=f"PDF: {e}",
        ))
        return False

    if dry_run:
        console.print("  [yellow][DRY RUN] PDFs built — skipping submit[/yellow]")
        logger.log(ApplicationResult(
            job_id=job.job_id, title=job.title, company=job.company,
            location=job.location, apply_url=job.apply_url or job.source_url,
            status="skipped", resume_path=str(resume_pdf), cover_letter_path=str(cover_pdf),
        ))
        return False

    # Submit
    success = False
    try:
        if job.easy_apply and linkedin_bot:
            success = linkedin_bot.easy_apply(job, resume_pdf, cover_pdf)
        else:
            apply_url = job.apply_url
            if not apply_url and job.source == "linkedin" and linkedin_bot:
                apply_url = linkedin_bot.get_external_apply_url(job) or ""
            if apply_url:
                job.apply_url = apply_url
                success = app_bot.apply(job, resume_pdf, cover_pdf)
            else:
                console.print("  [yellow]No apply URL — skipping[/yellow]")
    except Exception as e:
        console.print(f"  [red]Submit error: {e}[/red]")

    logger.log(ApplicationResult(
        job_id=job.job_id, title=job.title, company=job.company,
        location=job.location, apply_url=job.apply_url or job.source_url,
        status="submitted" if success else "failed",
        resume_path=str(resume_pdf), cover_letter_path=str(cover_pdf),
        error="" if success else "Did not complete",
    ))
    return success


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Job Applier — Moyosore Ogunjobi",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
DAILY LIMIT: 40 applications/day (enforced automatically)

EXAMPLES:
  # Paste any job URL directly — Ashby, Greenhouse, Lever, Workday, LinkedIn
  python scripts/run.py --apply-url "https://jobs.ashbyhq.com/super.com/8e3c12f4..."

  # LinkedIn job page URL
  python scripts/run.py --url "https://linkedin.com/jobs/view/4374445317"

  # Scrape Canadian tech internships repo (40 jobs)
  python scripts/run.py --github --limit 40

  # LinkedIn recommended, finance-framed resume
  python scripts/run.py --recommended --limit 20 --category finance

  # Search PM roles
  python scripts/run.py --search "product manager intern Canada" --category pm

  # Load from your saved CSV
  python scripts/run.py --from-file ../study/unique_verified_application_links_jan22_2026.csv

  # Always dry-run first to check PDFs
  python scripts/run.py --github --limit 5 --dry-run
        """,
    )

    source = parser.add_argument_group("Job Sources (pick one or combine)")
    source.add_argument("--apply-url",   metavar="URL",
                        help="Any direct job or ATS URL — scrapes it and applies. Works on Ashby, Greenhouse, Lever, Workday, Cisco, LinkedIn, or any site.")
    source.add_argument("--url",         metavar="URL",
                        help="LinkedIn job page URL")
    source.add_argument("--recommended", action="store_true",
                        help="LinkedIn recommended jobs feed")
    source.add_argument("--search",      metavar="QUERY",
                        help="LinkedIn job search (e.g. 'software engineer intern Calgary')")
    source.add_argument("--github",      action="store_true",
                        help="Scrape open roles from Canadian-Tech-Internships-2026 GitHub repo")
    source.add_argument("--indeed",      action="store_true",
                        help="Scrape recent internships from Indeed Canada (no login)")
    source.add_argument("--from-file",   metavar="PATH",
                        help="CSV or MD file containing job links")

    opts = parser.add_argument_group("Options")
    opts.add_argument("--limit",    type=int, default=40,
                      help="Max jobs to process per run (default: 40, max: 120)")
    opts.add_argument("--category", choices=["tech", "finance", "consulting", "pm"],
                      default="tech",
                      help="Resume framing: tech (default) | finance | consulting | pm")
    opts.add_argument("--dry-run",  action="store_true",
                      help="Generate and save PDFs but do NOT submit any forms")
    opts.add_argument("--headless", action="store_true",
                      help="Run browser without a visible window")

    args = parser.parse_args()

    if not any([args.apply_url, args.url, args.recommended, args.search, args.github, args.indeed, args.from_file]):
        parser.print_help()
        sys.exit(1)

    # Enforce daily limit
    limit = min(args.limit, DAILY_LIMIT)
    if args.limit > DAILY_LIMIT:
        console.print(f"[yellow]Limit capped at {DAILY_LIMIT}/day to avoid account flags.[/yellow]")

    base_dir    = Path(__file__).parent.parent
    generator   = ResumeGenerator()
    pdf_builder = PDFBuilder(base_dir / "pdfs")
    logger      = ApplicationLogger(base_dir / "logs")

    # Check how many already submitted today
    already_submitted = logger.today_submitted_count()
    remaining = DAILY_LIMIT - already_submitted
    if remaining <= 0:
        console.print(f"[red]Daily limit of {DAILY_LIMIT} reached for today. Run again tomorrow.[/red]")
        sys.exit(0)
    if remaining < limit:
        console.print(f"[yellow]Adjusting limit to {remaining} (daily cap).[/yellow]")
        limit = remaining

    console.print(Panel(
        f"[bold #818cf8]JOB APPLIER[/bold #818cf8]\n\n"
        f"  Candidate:  [cyan]{PROFILE['name']}[/cyan]\n"
        f"  Category:   [cyan]{args.category.upper()}[/cyan]\n"
        f"  Mode:       {'[yellow]DRY RUN[/yellow]' if args.dry_run else '[green]LIVE[/green]'}\n"
        f"  Daily cap:  {already_submitted} submitted today, {remaining} remaining\n"
        f"  This run:   up to {limit} job(s)\n"
        f"  Output:     {base_dir / 'pdfs'}\n",
        border_style="#818cf8",
    ))

    # Non-LinkedIn sources (no login needed)
    pre_scraped: list[JobDetails] = []
    if args.github:
        pre_scraped.extend(scrape_github_repo(limit=limit))
    if args.indeed:
        pre_scraped.extend(scrape_indeed(limit=limit))
    if args.from_file:
        pre_scraped.extend(load_jobs_from_file(args.from_file))

    needs_linkedin = any([args.apply_url, args.url, args.recommended, args.search])

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=args.headless,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.new_page()
        linkedin_bot = LinkedInBot(page, ctx)
        app_bot      = ApplicationBot(browser)

        if needs_linkedin:
            console.print("\n[bold]LinkedIn Login[/bold]")
            if not linkedin_bot.login():
                sys.exit(1)

        linkedin_jobs: list[JobDetails] = []

        if args.apply_url:
            # Direct URL — scrape it directly, no LinkedIn needed
            job = scrape_job_from_url(args.apply_url, page)
            linkedin_jobs.append(job)

        elif args.url:
            job = linkedin_bot.scrape_job(args.url)
            if job:
                linkedin_jobs.append(job)

        elif args.recommended:
            urls = linkedin_bot.get_recommended(limit)
            for u in urls:
                j = linkedin_bot.scrape_job(u)
                if j:
                    linkedin_jobs.append(j)
                time.sleep(random.uniform(1.5, 3))

        elif args.search:
            urls = linkedin_bot.search(args.search, limit)
            for u in urls:
                j = linkedin_bot.scrape_job(u)
                if j:
                    linkedin_jobs.append(j)
                time.sleep(random.uniform(1.5, 3))

        all_jobs = (linkedin_jobs + pre_scraped)[:limit]
        console.print(f"\n[bold]Processing {len(all_jobs)} job(s)[/bold]")

        submitted_this_run = 0
        for i, job in enumerate(all_jobs, 1):
            if submitted_this_run >= limit:
                break
            console.print(f"\n[bold dim]── {i}/{len(all_jobs)} ──[/bold dim]")
            try:
                ok = process_job(
                    job, linkedin_bot, app_bot, generator, pdf_builder, logger,
                    category=args.category, dry_run=args.dry_run,
                )
                if ok:
                    submitted_this_run += 1
            except Exception as e:
                console.print(f"  [red]Error: {e}[/red]")

            # Polite delay between jobs — 6-10 seconds
            if i < len(all_jobs):
                delay = random.uniform(6, 10)
                console.print(f"  [dim]Waiting {delay:.1f}s...[/dim]")
                time.sleep(delay)

        browser.close()

    console.print("\n[bold]Done.[/bold]")
    logger.summary()


if __name__ == "__main__":
    main()
