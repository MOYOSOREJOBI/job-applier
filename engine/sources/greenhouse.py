"""
Greenhouse source adapter.
Uses the official public Boards API — no authentication needed for public boards.
API: GET https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs?content=true
"""
import hashlib
import json
import time
import requests
from datetime import datetime, timezone
from typing import Optional

from engine.scoring.scorer import score_job

# Companies with Greenhouse boards relevant to Calgary/Canada internships
COMPANIES = [
    # Canadian tech companies
    {"slug": "shopify",           "name": "Shopify"},
    {"slug": "hootsuite",         "name": "Hootsuite"},
    {"slug": "freshbooks",        "name": "FreshBooks"},
    {"slug": "nuvei",             "name": "Nuvei"},
    {"slug": "trulioo",           "name": "Trulioo"},
    {"slug": "benevity",          "name": "Benevity"},
    {"slug": "coveo",             "name": "Coveo"},
    {"slug": "intellicheck",      "name": "Intellicheck"},
    {"slug": "visier",            "name": "Visier"},
    {"slug": "d2l",               "name": "D2L"},
    {"slug": "crowdstrike",       "name": "CrowdStrike"},
    {"slug": "applyboard",        "name": "ApplyBoard"},
    {"slug": "lightspeedpos",     "name": "Lightspeed"},
    {"slug": "clio",              "name": "Clio"},
    {"slug": "procore",           "name": "Procore"},
    {"slug": "1password",         "name": "1Password"},
    {"slug": "thinkific",         "name": "Thinkific"},
    {"slug": "later",             "name": "Later"},
    {"slug": "klue",              "name": "Klue"},
    {"slug": "vendasta",          "name": "Vendasta"},
    {"slug": "procurify",         "name": "Procurify"},
    {"slug": "jobber",            "name": "Jobber"},
    {"slug": "unbounce",          "name": "Unbounce"},
    {"slug": "absorblms",         "name": "Absorb LMS"},
    {"slug": "tulip-retail",      "name": "Tulip Retail"},
    {"slug": "spare",             "name": "Spare Labs"},
    {"slug": "dapper-labs",       "name": "Dapper Labs"},
    {"slug": "clearco",           "name": "Clearco"},
    {"slug": "beanworks",         "name": "Beanworks"},
    {"slug": "flipp",             "name": "Flipp"},
    {"slug": "achievers",         "name": "Achievers"},
    {"slug": "wattpad",           "name": "Wattpad"},
    {"slug": "resolver",          "name": "Resolver"},
    {"slug": "top-hat",           "name": "Top Hat"},
    {"slug": "vidyard",           "name": "Vidyard"},
    {"slug": "intellijoint",      "name": "Intellijoint Surgical"},
    # US tech companies that hire Canadian interns
    {"slug": "anthropic",         "name": "Anthropic"},
    {"slug": "vercel",            "name": "Vercel"},
    {"slug": "temporal",          "name": "Temporal"},
    {"slug": "arizeai",           "name": "Arize AI"},
    {"slug": "gleanwork",         "name": "Glean"},
    {"slug": "airtable",          "name": "Airtable"},
    {"slug": "intercom",          "name": "Intercom"},
    {"slug": "humeai",            "name": "Hume AI"},
    {"slug": "runpod",            "name": "RunPod"},
    {"slug": "polyai",            "name": "PolyAI"},
    {"slug": "parloa",            "name": "Parloa"},
    {"slug": "ada",               "name": "Ada"},
    {"slug": "factorial",         "name": "Factorial"},
    {"slug": "webflow",           "name": "Webflow"},
    {"slug": "notion",            "name": "Notion"},
    {"slug": "loom",              "name": "Loom"},
    {"slug": "faire",             "name": "Faire"},
    {"slug": "benchscience",      "name": "Bench"},
    {"slug": "brex",              "name": "Brex"},
    {"slug": "rippling",          "name": "Rippling"},
    {"slug": "hashicorp",         "name": "HashiCorp"},
    {"slug": "cloudflare",        "name": "Cloudflare"},
    {"slug": "stripe",            "name": "Stripe"},
    {"slug": "databricks",        "name": "Databricks"},
    {"slug": "mongodb",           "name": "MongoDB"},
    {"slug": "confluent",         "name": "Confluent"},
    {"slug": "datadog",           "name": "Datadog"},
    {"slug": "samsara",           "name": "Samsara"},
    {"slug": "hubspot",           "name": "HubSpot"},
    {"slug": "airbnb",            "name": "Airbnb"},
    {"slug": "pinterest",         "name": "Pinterest"},
    {"slug": "twitch",            "name": "Twitch"},
    {"slug": "lyft",              "name": "Lyft"},
    {"slug": "snap",              "name": "Snap"},
    {"slug": "reddit",            "name": "Reddit"},
    {"slug": "coinbase",          "name": "Coinbase"},
    {"slug": "okta",              "name": "Okta"},
    {"slug": "pagerduty",         "name": "PagerDuty"},
    {"slug": "elastic",           "name": "Elastic"},
    {"slug": "cockroachdb",       "name": "CockroachDB"},
    {"slug": "toast",             "name": "Toast"},
    {"slug": "klaviyo",           "name": "Klaviyo"},
    {"slug": "amplitude",         "name": "Amplitude"},
    {"slug": "mixpanel",          "name": "Mixpanel"},
    {"slug": "sentry",            "name": "Sentry"},
    {"slug": "plaid",             "name": "Plaid"},
    {"slug": "algolia",           "name": "Algolia"},
    {"slug": "netlify",           "name": "Netlify"},
    {"slug": "jfrog",             "name": "JFrog"},
    {"slug": "snyk",              "name": "Snyk"},
    {"slug": "fivetran",          "name": "Fivetran"},
    {"slug": "braze",             "name": "Braze"},
    {"slug": "gong-io",           "name": "Gong"},
    {"slug": "salesloft",         "name": "Salesloft"},
    {"slug": "ramp",              "name": "Ramp"},
    {"slug": "replit",            "name": "Replit"},
    {"slug": "dropbox",           "name": "Dropbox"},
    {"slug": "box",               "name": "Box"},
    {"slug": "zendesk",           "name": "Zendesk"},
    {"slug": "checkr",            "name": "Checkr"},
    {"slug": "heap",              "name": "Heap"},
    {"slug": "fullstory",         "name": "FullStory"},
    {"slug": "lattice",           "name": "Lattice"},
    {"slug": "contentful",        "name": "Contentful"},
    {"slug": "cloudinary",        "name": "Cloudinary"},
    {"slug": "segment",           "name": "Segment"},
    {"slug": "iterable",          "name": "Iterable"},
    {"slug": "hightouch",         "name": "Hightouch"},
    {"slug": "census",            "name": "Census"},
    {"slug": "modern-treasury",   "name": "Modern Treasury"},
    {"slug": "openai",            "name": "OpenAI"},
    {"slug": "huggingface",       "name": "Hugging Face"},
    {"slug": "scale",             "name": "Scale AI"},
    {"slug": "lacework",          "name": "Lacework"},
    {"slug": "dremio",            "name": "Dremio"},
    {"slug": "starburst",         "name": "Starburst Data"},
    {"slug": "airbyte",           "name": "Airbyte"},
    {"slug": "appdirect",         "name": "AppDirect"},
    {"slug": "phreesia",          "name": "Phreesia"},
    {"slug": "flatiron",          "name": "Flatiron Health"},
    {"slug": "outreach",          "name": "Outreach"},
    {"slug": "drift",             "name": "Drift"},
    {"slug": "clearbit",          "name": "Clearbit"},
    {"slug": "pilot",             "name": "Pilot"},
    {"slug": "column",            "name": "Column"},
    {"slug": "lithic",            "name": "Lithic"},
    {"slug": "unit-finance",      "name": "Unit"},
    {"slug": "quizlet",           "name": "Quizlet"},
    {"slug": "khanacademy",       "name": "Khan Academy"},
    {"slug": "duolingo",          "name": "Duolingo"},
    # Energy & consulting (Calgary-heavy)
    {"slug": "cenovus",           "name": "Cenovus Energy"},
    {"slug": "aecom",             "name": "AECOM"},
    {"slug": "suncor",            "name": "Suncor Energy"},
    {"slug": "enbridge",          "name": "Enbridge"},
    {"slug": "cpkc",              "name": "CPKC"},
    # More general tech
    {"slug": "zapier",            "name": "Zapier"},
    {"slug": "attio",             "name": "Attio"},
    {"slug": "tinybird",          "name": "Tinybird"},
    {"slug": "linear",            "name": "Linear"},
    {"slug": "posthog",           "name": "PostHog"},
    {"slug": "dbt-labs",          "name": "dbt Labs"},
    {"slug": "miro",              "name": "Miro"},
    {"slug": "sendbird",          "name": "Sendbird"},
    {"slug": "coda",              "name": "Coda"},
    {"slug": "superhuman",        "name": "Superhuman"},
    {"slug": "front",             "name": "Front"},
    {"slug": "livekit",           "name": "LiveKit"},
    {"slug": "dagster-labs",      "name": "Dagster"},
    {"slug": "prefect",           "name": "Prefect"},
    {"slug": "astronomer",        "name": "Astronomer"},
    {"slug": "grafana",           "name": "Grafana Labs"},
    {"slug": "honeycomb-io",      "name": "Honeycomb"},
    {"slug": "incident-io",       "name": "incident.io"},
    {"slug": "rootly",            "name": "Rootly"},
    {"slug": "firehydrant",       "name": "FireHydrant"},
    {"slug": "getdbt",            "name": "dbt Labs (alt)"},
    {"slug": "neon",              "name": "Neon"},
    {"slug": "xata",              "name": "Xata"},
    {"slug": "turso",             "name": "Turso"},
    # Gaming
    {"slug": "ea",                "name": "EA Sports / Electronic Arts"},
    {"slug": "electronicarts",    "name": "Electronic Arts"},
    {"slug": "electronic-arts",   "name": "Electronic Arts (alt)"},
    {"slug": "riotgames",         "name": "Riot Games"},
    {"slug": "unity",             "name": "Unity Technologies"},
    {"slug": "epicgames",         "name": "Epic Games"},
    {"slug": "warnerbros",        "name": "Warner Bros. Games"},
    {"slug": "activision",        "name": "Activision Blizzard"},
    {"slug": "ubisoft",           "name": "Ubisoft"},
    # Additional Calgary / Alberta energy
    {"slug": "arc-resources",     "name": "ARC Resources"},
    {"slug": "tourmalinenergy",   "name": "Tourmaline Oil"},
    {"slug": "canadiannatural",   "name": "Canadian Natural Resources"},
    {"slug": "ovintiv",           "name": "Ovintiv"},
    {"slug": "keyera",            "name": "Keyera"},
    {"slug": "pembina",           "name": "Pembina Pipeline"},
    {"slug": "transalta",         "name": "TransAlta"},
    {"slug": "capital-power",     "name": "Capital Power"},
    {"slug": "brc",               "name": "BRC Analytics"},
    # Additional consulting
    {"slug": "deloitte",          "name": "Deloitte"},
    {"slug": "ibm",               "name": "IBM"},
    {"slug": "sap",               "name": "SAP"},
    {"slug": "oracle",            "name": "Oracle"},
    {"slug": "salesforce",        "name": "Salesforce"},
    {"slug": "servicenow",        "name": "ServiceNow"},
    {"slug": "workday",           "name": "Workday"},
    {"slug": "veeva",             "name": "Veeva Systems"},
    {"slug": "palantir",          "name": "Palantir"},
    # Canadian banks / fintech (Greenhouse-based or mixed)
    {"slug": "atb-financial",     "name": "ATB Financial"},
    {"slug": "atbfinancial",      "name": "ATB Financial"},
    {"slug": "nuvei",             "name": "Nuvei"},
    {"slug": "wealthsimple",      "name": "Wealthsimple"},
    {"slug": "koho",              "name": "KOHO"},
    {"slug": "borrowell",         "name": "Borrowell"},
    {"slug": "mogo",              "name": "Mogo"},
    {"slug": "peoples-group",     "name": "Peoples Group"},
    {"slug": "plooto",            "name": "Plooto"},
    {"slug": "versapay",          "name": "Versapay"},
    {"slug": "clearco",           "name": "Clearco"},
    {"slug": "float-financial",   "name": "Float"},
    {"slug": "league",            "name": "League"},
    {"slug": "symend",            "name": "Symend"},
    # US fintech
    {"slug": "chime",             "name": "Chime"},
    {"slug": "sofi",              "name": "SoFi"},
    {"slug": "robinhood",         "name": "Robinhood"},
    {"slug": "affirm",            "name": "Affirm"},
    {"slug": "marqeta",           "name": "Marqeta"},
    # ── Additional Canadian tech (2026 expansion) ───────────────────────────
    {"slug": "ecobee",            "name": "ecobee"},
    {"slug": "ada",               "name": "Ada Support"},
    {"slug": "flipp",             "name": "Flipp"},
    {"slug": "achievers",         "name": "Achievers"},
    {"slug": "wattpad",           "name": "Wattpad"},
    {"slug": "resolver",          "name": "Resolver"},
    {"slug": "top-hat",           "name": "Top Hat"},
    {"slug": "vidyard",           "name": "Vidyard"},
    {"slug": "unbounce",          "name": "Unbounce"},
    {"slug": "absorblms",         "name": "Absorb LMS"},
    {"slug": "tulip-retail",      "name": "Tulip Retail"},
    {"slug": "spare",             "name": "Spare Labs"},
    {"slug": "beanworks",         "name": "Beanworks"},
    {"slug": "procurify",         "name": "Procurify"},
    {"slug": "klue",              "name": "Klue"},
    {"slug": "vendasta",          "name": "Vendasta"},
    {"slug": "applyboard",        "name": "ApplyBoard"},
    {"slug": "snapcommerce",      "name": "SnapCommerce"},
    {"slug": "borrowell",         "name": "Borrowell"},
    {"slug": "mogo",              "name": "Mogo"},
    {"slug": "plooto",            "name": "Plooto"},
    {"slug": "versapay",          "name": "Versapay"},
    {"slug": "float-financial",   "name": "Float"},
    {"slug": "symend",            "name": "Symend"},
    {"slug": "helcim",            "name": "Helcim"},
    {"slug": "sensibill",         "name": "Sensibill"},
    {"slug": "routemaster",       "name": "Routemaster"},
    {"slug": "zafin",             "name": "Zafin"},
    {"slug": "bounteous",         "name": "Bounteous"},
    {"slug": "stradigi",          "name": "Stradigi AI"},
    # ── US tech (infrastructure / developer tools) ──────────────────────────
    {"slug": "tailscale",         "name": "Tailscale"},
    {"slug": "fly-io",            "name": "Fly.io"},
    {"slug": "railway",           "name": "Railway"},
    {"slug": "render",            "name": "Render"},
    {"slug": "supabase",          "name": "Supabase"},
    {"slug": "planetscale",       "name": "PlanetScale"},
    {"slug": "prisma",            "name": "Prisma"},
    {"slug": "hasura",            "name": "Hasura"},
    {"slug": "retool",            "name": "Retool"},
    {"slug": "airplane",          "name": "Airplane"},
    {"slug": "windmill",          "name": "Windmill"},
    {"slug": "inngest",           "name": "Inngest"},
    {"slug": "trigger",           "name": "Trigger.dev"},
    {"slug": "trieve",            "name": "Trieve"},
    {"slug": "loop-industries",   "name": "Loop Industries"},
    {"slug": "comet",             "name": "Comet ML"},
    {"slug": "weights-biases",    "name": "Weights & Biases"},
    {"slug": "neptune-ai",        "name": "Neptune AI"},
    {"slug": "arize",             "name": "Arize AI"},
    {"slug": "whylabs",           "name": "WhyLabs"},
    {"slug": "evidently",         "name": "Evidently AI"},
    {"slug": "gantry",            "name": "Gantry"},
    # ── Security companies ──────────────────────────────────────────────────
    {"slug": "1password",         "name": "1Password"},
    {"slug": "crowdstrike",       "name": "CrowdStrike"},
    {"slug": "snyk",              "name": "Snyk"},
    {"slug": "lacework",          "name": "Lacework"},
    {"slug": "orca-security",     "name": "Orca Security"},
    {"slug": "wiz-io",            "name": "Wiz"},
    {"slug": "panther",           "name": "Panther Labs"},
    {"slug": "axonius",           "name": "Axonius"},
    {"slug": "hunters",           "name": "Hunters"},
    # ── Data / Analytics ────────────────────────────────────────────────────
    {"slug": "fivetran",          "name": "Fivetran"},
    {"slug": "airbyte",           "name": "Airbyte"},
    {"slug": "dremio",            "name": "Dremio"},
    {"slug": "starburst",         "name": "Starburst Data"},
    {"slug": "hightouch",         "name": "Hightouch"},
    {"slug": "census",            "name": "Census"},
    {"slug": "hex",               "name": "Hex"},
    {"slug": "mode",              "name": "Mode Analytics"},
    {"slug": "preset",            "name": "Preset"},
    {"slug": "metaplane",         "name": "Metaplane"},
    {"slug": "monte-carlo",       "name": "Monte Carlo"},
    {"slug": "great-expectations","name": "Great Expectations"},
    {"slug": "datacoves",         "name": "Datacoves"},
    # ── Product / Customer tools ─────────────────────────────────────────────
    {"slug": "productboard",      "name": "Productboard"},
    {"slug": "launchdarkly",      "name": "LaunchDarkly"},
    {"slug": "split",             "name": "Split"},
    {"slug": "chameleon",         "name": "Chameleon"},
    {"slug": "userflow",          "name": "Userflow"},
    {"slug": "appcues",           "name": "Appcues"},
    {"slug": "pendo",             "name": "Pendo"},
    {"slug": "gainsight",         "name": "Gainsight"},
    {"slug": "churnzero",         "name": "ChurnZero"},
    {"slug": "totango",           "name": "Totango"},
    {"slug": "catalyst",          "name": "Catalyst"},
    # ── HealthTech ───────────────────────────────────────────────────────────
    {"slug": "maple",             "name": "Maple Health"},
    {"slug": "well-health",       "name": "WELL Health"},
    {"slug": "medbridge",         "name": "MedBridge"},
    {"slug": "carebook",          "name": "Carebook"},
    {"slug": "dialogue",          "name": "Dialogue"},
    {"slug": "jane-app",          "name": "Jane App"},
    {"slug": "lifeworks",         "name": "LifeWorks"},
    {"slug": "genesiscare",       "name": "GenesisCare"},
    # ── Climate / Clean tech ─────────────────────────────────────────────────
    {"slug": "watershed",         "name": "Watershed"},
    {"slug": "persefoni",         "name": "Persefoni"},
    {"slug": "patch",             "name": "Patch"},
    {"slug": "terra-carbon",      "name": "Terra Carbon"},
    {"slug": "cleanly",           "name": "Cleanly"},
    {"slug": "loop-returns",      "name": "Loop Returns"},
    {"slug": "verdagy",           "name": "Verdagy"},
    # ── Consulting (Big 4 + Strategy) ────────────────────────────────────────
    {"slug": "mckinsey",          "name": "McKinsey & Company"},
    {"slug": "bain",              "name": "Bain & Company"},
    {"slug": "bcg",               "name": "BCG"},
    {"slug": "kpmg",              "name": "KPMG"},
    {"slug": "pwc",               "name": "PwC"},
    {"slug": "ey",                "name": "EY"},
    {"slug": "accenture",         "name": "Accenture"},
    {"slug": "capgemini",         "name": "Capgemini"},
    {"slug": "cognizant",         "name": "Cognizant"},
    {"slug": "infosys",           "name": "Infosys"},
    {"slug": "tata-consultancy",  "name": "TCS"},
    {"slug": "ntt-data",          "name": "NTT Data"},
    # ── Canadian banks / insurance ───────────────────────────────────────────
    {"slug": "rbc",               "name": "RBC"},
    {"slug": "td-bank",           "name": "TD Bank"},
    {"slug": "bmo",               "name": "BMO"},
    {"slug": "cibc",              "name": "CIBC"},
    {"slug": "scotiabank",        "name": "Scotiabank"},
    {"slug": "national-bank",     "name": "National Bank"},
    {"slug": "sunlife",           "name": "Sun Life"},
    {"slug": "manulife",          "name": "Manulife"},
    {"slug": "intact",            "name": "Intact Financial"},
    {"slug": "aviva-canada",      "name": "Aviva Canada"},
    # ── Enterprise SaaS ──────────────────────────────────────────────────────
    {"slug": "hubspot",           "name": "HubSpot"},
    {"slug": "zendesk",           "name": "Zendesk"},
    {"slug": "intercom",          "name": "Intercom"},
    {"slug": "freshworks",        "name": "Freshworks"},
    {"slug": "zoho",              "name": "Zoho"},
    {"slug": "chargebee",         "name": "Chargebee"},
    {"slug": "recurly",           "name": "Recurly"},
    {"slug": "paddle",            "name": "Paddle"},
    {"slug": "maxio",             "name": "Maxio"},
    {"slug": "zuora",             "name": "Zuora"},
    {"slug": "netsuite",          "name": "NetSuite"},
    # ── Commerce / Marketplaces ──────────────────────────────────────────────
    {"slug": "faire",             "name": "Faire"},
    {"slug": "flexport",          "name": "Flexport"},
    {"slug": "shipbob",           "name": "ShipBob"},
    {"slug": "shippo",            "name": "Shippo"},
    {"slug": "easypost",          "name": "EasyPost"},
    {"slug": "goshippo",          "name": "Shippo (alt)"},
    {"slug": "narvar",            "name": "Narvar"},
    {"slug": "loop-commerce",     "name": "Loop Commerce"},
    # ── Communications / Collab ──────────────────────────────────────────────
    {"slug": "livekit",           "name": "LiveKit"},
    {"slug": "daily-co",          "name": "Daily.co"},
    {"slug": "100ms",             "name": "100ms"},
    {"slug": "agora",             "name": "Agora"},
    {"slug": "twilio",            "name": "Twilio"},
    {"slug": "bandwidth",         "name": "Bandwidth"},
    {"slug": "messagebird",       "name": "MessageBird"},
    {"slug": "vonage",            "name": "Vonage"},
    {"slug": "zoom",              "name": "Zoom"},
    {"slug": "slack",             "name": "Slack"},
    {"slug": "airtable",          "name": "Airtable"},
    {"slug": "coda",              "name": "Coda"},
    {"slug": "notion",            "name": "Notion"},
    {"slug": "miro",              "name": "Miro"},
]

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
TIMEOUT = 15


def make_job_id(company: str, job_id: str) -> str:
    return f"greenhouse_{company}_{job_id}"


def normalize_location(loc_str: Optional[str]) -> str:
    if not loc_str:
        return "Remote"
    return loc_str.strip()


def detect_remote(title: str, location: str, desc: str) -> str:
    combined = (title + " " + location + " " + desc[:500]).lower()
    if "remote" in combined:
        return "remote"
    if "hybrid" in combined:
        return "hybrid"
    return "onsite"


def fetch_company_jobs(slug: str, company_name: str) -> list[dict]:
    """Fetch all jobs for one company via Greenhouse API."""
    url = BASE_URL.format(slug=slug)
    try:
        resp = requests.get(url, params={"content": "true"}, timeout=TIMEOUT)
        if resp.status_code == 404:
            return []  # company not on Greenhouse or wrong slug
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"[greenhouse] {company_name}: request error — {e}")
        return []
    except json.JSONDecodeError:
        print(f"[greenhouse] {company_name}: JSON decode error")
        return []

    jobs = []
    now = datetime.now(timezone.utc).isoformat()
    for item in data.get("jobs", []):
        gh_id = str(item.get("id", ""))
        title = item.get("title", "")
        location_data = item.get("location", {})
        location = normalize_location(location_data.get("name") if isinstance(location_data, dict) else str(location_data))
        url_apply = item.get("absolute_url", "")
        updated = item.get("updated_at", now)
        content = item.get("content", "") or ""

        job_id = make_job_id(slug, gh_id)
        score, breakdown, fit_band = score_job({
            "title": title,
            "location": location,
            "company": company_name,
            "description_raw": content,
            "portal": "greenhouse",
            "posted_at": updated,
        })

        job = {
            "id": job_id,
            "source": f"greenhouse:{slug}",
            "source_type": "api",
            "portal": "greenhouse",
            "company": company_name,
            "title": title,
            "location": location,
            "remote_type": detect_remote(title, location, content),
            "url": url_apply,
            "description_raw": content[:8000],
            "description_normalized": _normalize_desc(content),
            "posted_at": updated,
            "first_seen_at": now,
            "last_seen_at": now,
            "score": score,
            "score_breakdown": json.dumps(breakdown),
            "fit_band": fit_band,
            "support_tier": "A",
            "apply_mode": "ASSISTED_FILL",
            "status": "discovered",
            "manual_only": 0,
            "restricted_reason": None,
            "created_at": now,
            "updated_at": now,
        }
        jobs.append(job)
    return jobs


def _normalize_desc(html: str) -> str:
    """Strip HTML tags for normalized description."""
    import re
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:4000]


def fetch_all(company_slugs: Optional[list[dict]] = None) -> list[dict]:
    """Fetch jobs from all configured Greenhouse companies."""
    targets = company_slugs or COMPANIES
    all_jobs = []
    for company in targets:
        slug = company["slug"]
        name = company["name"]
        jobs = fetch_company_jobs(slug, name)
        all_jobs.extend(jobs)
        time.sleep(0.3)  # polite delay
    return all_jobs
