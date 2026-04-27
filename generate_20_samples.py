"""
Generate 20 sample application folders across diverse roles and industries.
Each folder: MOYOSORE_JOBI_RESUME.pdf, MOYOSORE_JOBI_COVERLETTER.pdf,
             job_description.md, notes.md, answers.json
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

JOBS = [
    # ── 1. Shopify — Backend Intern ──────────────────────────────────────────
    {
        "title": "Backend Developer Intern",
        "company": "Shopify",
        "location": "Toronto, ON",
        "url": "https://www.shopify.com/careers/backend-developer-intern",
        "description_raw": """About the role

Shopify is the leading commerce platform for businesses of all sizes. We power over 1.7 million merchants in more than 175 countries, and we're growing fast. Our Backend Developer Internship is a hands-on, production-level experience where you'll contribute to real systems used by real merchants from day one.

As a Backend Developer Intern at Shopify, you will:

- Design, build, and ship features in Ruby on Rails, Go, or Python that power Shopify's core commerce platform
- Work with distributed systems that handle millions of requests per day
- Collaborate with senior engineers, product managers, and designers in a multi-functional team
- Participate in code reviews, architecture discussions, and sprint planning
- Write clean, well-tested, and well-documented code
- Contribute to internal tooling and developer experience improvements
- Analyze and improve system performance, reliability, and scalability
- Be involved in on-call rotation to develop operational awareness

What you'll need:

- Enrolled in a Computer Science, Software Engineering, or related degree program
- Experience with at least one backend language (Ruby, Go, Python, Java, or similar)
- Solid understanding of data structures, algorithms, and system design fundamentals
- Familiarity with relational databases and SQL
- Experience working with REST APIs
- Ability to work effectively in a remote-first, distributed team environment
- Strong written and verbal communication skills
- Comfort with ambiguity and a bias toward shipping

Nice to have:

- Experience with distributed systems, caching (Redis/Memcached), or message queues
- Familiarity with Docker and Kubernetes
- Prior internship or co-op experience in software engineering
- Open source contributions
- Experience with GraphQL APIs

Term: May – August 2026 (4 months)
Location: Remote Canada or Toronto, ON (hybrid available)
Compensation: Competitive internship rate
""",
    },

    # ── 2. Google — Software Engineer Intern ────────────────────────────────
    {
        "title": "Software Engineer Intern, Summer 2026",
        "company": "Google",
        "location": "Waterloo, ON",
        "url": "https://careers.google.com/jobs/results/software-engineer-intern-summer-2026",
        "description_raw": """About the job

At Google, we don't just accept difference—we celebrate it, we support it, and we thrive on it for the benefit of our employees, our products and our community. Google is proud to be an equal opportunity workplace and is an affirmative action employer.

As a Software Engineer Intern, you'll work on challenging technical problems in a team that values thoughtful, high-quality engineering. You'll be embedded in a product team and contribute to real features shipped to billions of users.

Minimum qualifications:

- Currently pursuing a Bachelor's or Master's degree in Computer Science, Computer Engineering, or a related technical field
- Experience with data structures and algorithms
- Experience in one or more general purpose programming languages including but not limited to: Java, C/C++, C#, Objective C, Python, JavaScript, or Go
- Experience with algorithms and data structures including graphs, sorting, tree structures

Preferred qualifications:

- Experience working on a team and collaborating on projects
- Experience with web application development or distributed systems
- Familiarity with Unix/Linux environments
- Strong problem-solving skills and attention to detail

Responsibilities:

- Design, develop, test, deploy, maintain, and improve software
- Manage individual project priorities, deadlines, and deliverables
- Design and implement algorithms and data structures for a variety of applications
- Participate in code reviews and contribute to engineering best practices
- Collaborate with product managers, UX designers, and other engineers to build and ship product features

About internships at Google:

Google's intern program is one of the largest and most impactful in the industry. You'll work on meaningful projects, attend tech talks, and build relationships with Googlers across the company. Our 12-week summer internship offers a full-time, paid experience.
""",
    },

    # ── 3. Cloudflare — Network Engineering Intern ──────────────────────────
    {
        "title": "Network Engineering Intern",
        "company": "Cloudflare",
        "location": "Remote, Canada",
        "url": "https://boards.greenhouse.io/cloudflare/jobs/network-engineering-intern",
        "description_raw": """About Cloudflare

Cloudflare is on a mission to help build a better Internet. Today the company runs one of the world's largest networks that powers millions of websites and other Internet properties for customers ranging from individual bloggers to SMBs to Fortune 500 companies. Cloudflare protects and accelerates any Internet application online without adding hardware, installing software, or changing a line of code.

What you'll do

As a Network Engineering Intern at Cloudflare, you'll be part of the team that operates and evolves Cloudflare's global Anycast network spanning 300+ cities across 100+ countries. You will:

- Assist with capacity planning and deployment of network infrastructure at Cloudflare's Points of Presence worldwide
- Work alongside network engineers to analyze traffic patterns and optimize routing for performance and reliability
- Contribute to automation tooling for network provisioning, monitoring, and alerting using Python and Go
- Help investigate and resolve network incidents using Grafana, Prometheus, and internal observability tools
- Participate in architecture discussions around BGP routing policy, traffic engineering, and DDoS mitigation
- Write runbooks, documentation, and post-mortems for network events

What we're looking for

- Currently pursuing a degree in Computer Science, Electrical Engineering, Network Engineering, or a related field
- Solid understanding of networking concepts: TCP/IP, BGP, DNS, HTTP/HTTPS, TLS
- Programming experience in Python or Go
- Exposure to Linux command line and shell scripting
- Familiarity with monitoring and observability concepts
- Strong analytical and problem-solving skills
- Excellent written communication skills — we are a writing-first culture

Bonus points

- Experience with network automation frameworks (Ansible, Terraform, Nautobot)
- Knowledge of Anycast networking and CDN architecture
- Prior experience with a cloud provider (AWS, GCP, Azure)
- Contributions to open source networking projects

Duration: 4 months (May – August 2026)
""",
    },

    # ── 4. RBC — Software Developer Co-op ───────────────────────────────────
    {
        "title": "Software Developer Co-op",
        "company": "RBC",
        "location": "Toronto, ON",
        "url": "https://jobs.rbc.com/ca/en/software-developer-coop",
        "description_raw": """Job Summary

At RBC, we are committed to supporting flexible work arrangements when and where available. Details to be discussed with Hiring Manager.

RBC's Technology and Operations team builds and maintains the software that runs Canada's largest bank. We are looking for a Software Developer Co-op student to join one of our platform engineering or capital markets technology teams.

What will you do?

- Develop and maintain backend services and APIs in Java, Python, or C# supporting banking operations and capital markets trading systems
- Build automated test suites (unit, integration, and regression) and participate in test-driven development
- Work within Agile/Scrum teams, attending standups, sprint reviews, and retrospectives
- Contribute to CI/CD pipeline improvements using Jenkins and GitHub Actions
- Assist in migrating legacy systems to cloud-native architectures on AWS and Azure
- Monitor application performance using Dynatrace and Splunk, investigate production incidents
- Document technical designs and write clear, maintainable code

What do you need to succeed?

Must have:
- Enrolled in Computer Science, Software Engineering, Mathematics, or a related program
- Proficiency in Java, Python, C#, or JavaScript/TypeScript
- Understanding of object-oriented programming and software design principles
- Familiarity with SQL and relational database concepts (Oracle, PostgreSQL, or SQL Server)
- Strong analytical and problem-solving abilities

Nice to have:
- Experience with Spring Boot or .NET frameworks
- Exposure to Agile/Scrum methodology
- Basic understanding of financial instruments (equities, fixed income, derivatives) is a strong asset
- Experience with Docker or Kubernetes
- Familiarity with cloud platforms (AWS, Azure)

What's in it for you?

- Competitive co-op compensation
- Mentorship from experienced software engineers
- Exposure to financial technology at scale
- Networking events and co-op community programming

Co-op Term: May – August 2026 | Full-time (40 hours/week)
Location: 20 King Street West, Toronto, ON (Hybrid)
""",
    },

    # ── 5. Citadel — Quantitative Researcher (intern) ───────────────────────
    {
        "title": "Quantitative Researcher Intern",
        "company": "Citadel",
        "location": "Toronto, ON",
        "url": "https://www.citadel.com/careers/details/quantitative-researcher-intern",
        "description_raw": """About Citadel

Citadel is one of the world's leading alternative investment managers. For over three decades, Citadel has pursued excellence through innovation and a rigorous, research-driven approach to investing. Our global team of experts, including quantitative researchers, engineers, and traders, work together to analyze markets and find signal in complex data.

The Role

As a Quantitative Researcher Intern, you will work alongside our researchers and portfolio managers to analyze financial data, develop predictive models, and prototype signals that inform trading decisions. This is a highly quantitative, research-intensive internship.

Responsibilities

- Apply statistical, machine learning, and mathematical techniques to large financial datasets to identify alpha-generating signals
- Build and backtest systematic trading strategies across equities, futures, or fixed income markets
- Collaborate with engineers to productionize models and integrate them into live trading systems
- Present research findings to senior researchers and portfolio managers
- Clean, process, and explore large datasets using Python and SQL

Requirements

- Currently pursuing a PhD, Master's, or final year of undergraduate studies in Mathematics, Statistics, Physics, Computer Science, Financial Engineering, or a related quantitative field
- Strong mathematical foundation: probability, statistics, linear algebra, calculus, stochastic processes
- Proficiency in Python (pandas, NumPy, scikit-learn) and/or C++
- Experience with data analysis and statistical modeling
- Strong problem-solving skills and intellectual curiosity
- Ability to communicate complex quantitative concepts clearly

Nice to Have

- Experience with financial data (tick data, order book data, factor models)
- Prior research experience in ML, NLP, or time series analysis
- Understanding of market microstructure or derivatives pricing
- Publications or research projects in quantitative domains

Compensation: Highly competitive; top-of-market internship rates
""",
    },

    # ── 6. Palantir — Forward Deployed Software Engineer ────────────────────
    {
        "title": "Forward Deployed Software Engineer, New Grad",
        "company": "Palantir",
        "location": "Toronto, ON",
        "url": "https://jobs.lever.co/palantir/forward-deployed-software-engineer-new-grad",
        "description_raw": """A World-Changing Company

Palantir builds the world's leading software for data-driven decisions and operations. By the end of our first week of deployment in any given organization, our software is operationally critical to that organization—whether it is making their supply chain run better, improving the quality of investigations into financial crime, or optimizing the deployment of emergency services in natural disasters.

The Role

Forward Deployed Engineers (FDEs) are software engineers who embed with our customers to understand their most important operational problems and build the software solutions that solve them. FDEs operate at the intersection of software engineering, data engineering, and product ownership.

Core Responsibilities

- Work directly with customers to understand their data infrastructure, operational workflows, and decision-making processes
- Build, deploy, and iterate on software products tailored to customer environments using Palantir's Foundry platform and custom code
- Write backend services, data pipelines, and APIs in Python, Java, or TypeScript
- Translate ambiguous operational problems into concrete technical solutions
- Own the full stack: from database design and API development to frontend interfaces
- Train customer teams to use and extend the software you build
- Travel on-site to customer locations regularly (25–50%)

Qualifications

- Bachelor's or Master's degree in Computer Science, Engineering, or a related field (or equivalent experience)
- Strong proficiency in Python, Java, or TypeScript
- Demonstrated ability to learn new technologies quickly and work in ambiguous environments
- Experience building data pipelines, REST APIs, or web applications
- Strong communication skills — you'll be presenting to executives and working directly with operators
- Willingness to travel

Bonus

- Experience with data analysis tools (SQL, Spark, pandas)
- Prior internship in software engineering or consulting
- Interest in government, intelligence, healthcare, or financial services applications
""",
    },

    # ── 7. Cohere — Machine Learning Intern ─────────────────────────────────
    {
        "title": "Machine Learning Intern",
        "company": "Cohere",
        "location": "Toronto, ON",
        "url": "https://jobs.ashbyhq.com/cohere/machine-learning-intern",
        "description_raw": """Who are we?

Cohere is transforming enterprises with its world-class AI. Built on the foundational belief that research and productization are symbiotic, Cohere's platform, models, and capabilities reflect the work of thousands of the world's best researchers and engineers.

The Opportunity

We are looking for a Machine Learning Intern to join one of our core research or applied ML teams. You'll work on challenging problems at the frontier of large language models—whether it's improving model quality, building evaluation pipelines, or applying LLMs to enterprise use cases.

You Might Work On

- Training and fine-tuning large transformer-based language models using PyTorch
- Designing and running model evaluation experiments across benchmarks and custom datasets
- Building data pipelines for collecting, cleaning, and filtering large-scale training data
- Implementing and testing new model architectures, attention mechanisms, or training techniques
- Analyzing model behavior through interpretability techniques and failure mode analysis
- Contributing to Cohere's research infrastructure: distributed training, experiment tracking, and evaluation harnesses

What We're Looking For

- Pursuing a degree in Machine Learning, Computer Science, Mathematics, or Statistics
- Strong Python programming skills with proficiency in PyTorch or JAX
- Understanding of deep learning fundamentals: backpropagation, optimization, transformer architecture
- Experience training and evaluating machine learning models
- Solid mathematical foundation in linear algebra, probability, and calculus
- Ability to read, understand, and implement ideas from recent ML research papers

Nice to Have

- Experience with LLMs, RLHF, or instruction tuning
- Familiarity with distributed training (FSDP, DeepSpeed, Megatron)
- Publications or contributions to ML research
- Experience with evaluation frameworks and benchmarking

Duration: 4 months (May – August 2026)
Location: Toronto, ON — in-person or hybrid
""",
    },

    # ── 8. Snowflake — Software Engineer Intern ──────────────────────────────
    {
        "title": "Software Engineer Intern - Core Database",
        "company": "Snowflake",
        "location": "Remote, Canada",
        "url": "https://careers.snowflake.com/us/en/job/software-engineer-intern-core-database",
        "description_raw": """Build the future of the AI Data Cloud.

Join Snowflake's engineering team and help us build the most trusted and widely used data platform in the world. Snowflake's mission is to enable every organization to be data-driven.

About the Team

The Core Database team is responsible for the SQL query engine, storage layer, and transaction processing that powers Snowflake's platform. This is highly complex systems work at massive scale.

What You'll Do

- Contribute to the design and implementation of core database features including query optimization, indexing, and transaction management
- Write high-performance C++ and Java code for Snowflake's query engine and storage systems
- Work with distributed systems concepts: consistency, fault tolerance, and horizontal scaling
- Profile and optimize query performance using benchmarking and profiling tools
- Participate in code reviews, design discussions, and architecture planning
- Write comprehensive unit and integration tests
- Collaborate with a senior engineering team on complex technical challenges

What We Need

- Currently pursuing a Bachelor's or Master's degree in Computer Science or a related field
- Strong programming skills in C++, Java, or Python
- Solid understanding of data structures, algorithms, and operating systems concepts
- Familiarity with database concepts: SQL, query processing, storage engines
- Experience writing clean, well-tested code
- Strong analytical and debugging skills

Nice to Have

- Experience with distributed systems, parallel computing, or database internals
- Coursework or research in compilers, operating systems, or database systems
- Experience with cloud platforms (AWS, GCP, Azure)
- Prior internship experience in systems engineering

Internship Duration: 12 weeks (May – August 2026)
Location: Remote (Canada) or San Mateo, CA (US) — candidate's choice
""",
    },

    # ── 9. Suncor Energy — Software Developer Co-op ─────────────────────────
    {
        "title": "Software Developer Co-op",
        "company": "Suncor Energy",
        "location": "Calgary, AB",
        "url": "https://suncor.com/careers/software-developer-co-op",
        "description_raw": """Joining Suncor means you will work for a company that is Canada's leading integrated energy company. Suncor's operations include oil sands development and upgrading, offshore oil and gas production, petroleum refining, and product marketing under the Petro-Canada brand.

Overview

We are looking for a Software Developer Co-op student to join our Digital and Technology team in Calgary. You'll contribute to building and maintaining internal applications that support oil sands operations, refinery optimization, and supply chain management.

What You'll Do

- Develop and maintain web applications and backend services in Python and JavaScript/TypeScript supporting upstream and downstream operations
- Build data pipelines to ingest, process, and visualize operational data from field sensors, historians, and ERP systems
- Integrate with industrial data platforms including OSIsoft PI Historian and SAP
- Build internal dashboards and reporting tools using React and Power BI to give operational teams visibility into equipment performance and KPIs
- Work with PostgreSQL and SQL Server databases to support data modeling and reporting needs
- Collaborate with operations, engineering, and IT teams to translate operational requirements into software solutions
- Write unit and integration tests and contribute to CI/CD pipelines

What You Bring

Required:
- Enrolled in Computer Science, Software Engineering, or a related degree program
- Experience in Python and at least one web framework (FastAPI, Flask, or Django)
- Familiarity with JavaScript/TypeScript and front-end frameworks (React or Vue)
- Understanding of SQL and relational databases
- Good communication skills and ability to work in multidisciplinary teams

Preferred:
- Experience with data visualization tools (Grafana, Power BI, Tableau)
- Familiarity with industrial data systems (OSIsoft PI, SCADA) is a strong asset
- Exposure to cloud platforms (Azure preferred in our environment)
- Understanding of oil and gas operations is an asset but not required

Duration: January – April 2026 or May – August 2026
Location: Calgary, AB — Onsite (Suncor Energy Centre)
""",
    },

    # ── 10. Stripe — Backend Engineer Intern ────────────────────────────────
    {
        "title": "Software Engineer Intern",
        "company": "Stripe",
        "location": "Toronto, ON",
        "url": "https://stripe.com/jobs/listing/software-engineer-intern",
        "description_raw": """About Stripe

Stripe is a financial infrastructure platform for businesses. Millions of companies—from the world's largest enterprises to the most ambitious startups—use Stripe to accept payments, grow their revenue, and accelerate new business opportunities. Our mission is to increase the GDP of the internet, and we have a staggering amount of work ahead. That means you have an incredible opportunity to put your abilities and interests to work on problems that matter.

About the role

You'll join one of Stripe's product engineering teams and build software that's used by businesses around the world. Stripe interns are expected to work on real products and ship code that impacts production.

What you'll do

- Design and build features that help businesses accept payments, manage subscriptions, or prevent fraud
- Write highly reliable, well-tested code in Ruby, Go, Java, or Scala running at massive scale
- Work with distributed systems that process hundreds of billions of dollars of transactions annually
- Collaborate with product managers, designers, and senior engineers
- Participate in code reviews and contribute to engineering culture
- Instrument code with metrics and alerts; respond to reliability issues

Who you are

- Enrolled in a Computer Science, Software Engineering, or related degree
- Strong fundamentals in computer science: data structures, algorithms, distributed systems
- Experience in at least one production-level programming language
- Product mindset — you think about the person using what you build
- Collaborative, clear communicator who can work across teams

Nice to have

- Experience building payment systems or financial applications
- Familiarity with API design and REST or GraphQL
- Experience with Kafka, PostgreSQL, or Redis at scale
- Prior internship at a software company

Duration: 12 weeks, May – August 2026
Location: Toronto, ON (hybrid) or Remote Canada
""",
    },

    # ── 11. Wealthsimple — iOS Developer Intern ─────────────────────────────
    {
        "title": "iOS Developer Intern",
        "company": "Wealthsimple",
        "location": "Toronto, ON",
        "url": "https://jobs.lever.co/wealthsimple/ios-developer-intern",
        "description_raw": """About Wealthsimple

Wealthsimple is Canada's leading fintech company, serving over 3 million clients and managing billions in assets. We're on a mission to help everyone achieve financial freedom, regardless of their background or wealth. Our products include investing, saving, tax filing, and spending — all built mobile-first.

The role

We're looking for an iOS Developer Intern to join our mobile engineering team and help build the apps used by millions of Canadians to manage their financial lives.

What you'll do

- Build new features in our iOS app using Swift and UIKit/SwiftUI
- Collaborate closely with product, design, and backend teams to ship features end-to-end
- Write clean, maintainable Swift code with strong test coverage using XCTest
- Profile and optimize app performance: memory usage, render time, and network efficiency
- Participate in code reviews and contribute to mobile engineering best practices
- Integrate with backend REST APIs and GraphQL endpoints
- Contribute to our design system and shared component library
- Participate in daily standups, sprint planning, and retrospectives

What we look for

- Enrolled in a Computer Science, Software Engineering, or related degree program
- Strong Swift programming skills and familiarity with iOS SDK
- Understanding of UIKit and/or SwiftUI
- Experience with MVC, MVVM, or similar architectural patterns
- Familiarity with Xcode, Instruments, and the iOS build toolchain
- Strong problem-solving skills and attention to detail

Bonus

- Experience with Core Data, Combine, or async/await
- Familiarity with financial products (investing, tax, payments)
- Published apps on the App Store
- Experience with CI/CD for mobile (Fastlane, Bitrise)

Term: May – August 2026 | Full-time
Location: Toronto, ON — Hybrid (2 days/week in office)
""",
    },

    # ── 12. Epic Systems — Software Developer ───────────────────────────────
    {
        "title": "Software Developer",
        "company": "Epic Systems",
        "location": "Verona, WI (Relocation Required)",
        "url": "https://careers.epic.com/Software-Developer",
        "description_raw": """Why Epic?

At Epic, we create software to help doctors, nurses, and other caregivers provide better care for patients. We're not just building software — we're improving healthcare. If you want work that matters, Epic is the place to be.

About the role

As a Software Developer at Epic, you'll join one of our software development teams and build features used by hospitals across the country. You'll work across the full stack — from C# and M backend services to web front ends — and you'll own entire feature areas end to end.

What you'll do

- Design and implement features in Epic's electronic health record system in C# and M (MUMPS)
- Build web front-end components in JavaScript and TypeScript
- Write and maintain SQL queries against Epic's database systems
- Collaborate with analysts, quality assurance, and technical writers to deliver complete features
- Participate in code reviews and contribute to best practices
- Diagnose and fix bugs reported from customer hospital environments
- Travel to customer sites occasionally to provide implementation support

Requirements

- Bachelor's degree or higher in Computer Science, Software Engineering, or a closely related field
- Strong academic performance (3.0 GPA or higher preferred)
- Proficiency in an object-oriented language (C#, Java, or C++)
- Strong problem-solving and debugging skills
- Ability to work independently on open-ended problems
- Excellent written and verbal communication skills
- Willingness to relocate to the Madison, Wisconsin area

Note: We do not sponsor work visas. Candidates must be authorized to work in the United States without sponsorship.
""",
    },

    # ── 13. Riot Games — Software Engineer Intern ────────────────────────────
    {
        "title": "Software Engineer Intern - Backend Systems",
        "company": "Riot Games",
        "location": "Remote, Canada",
        "url": "https://www.riotgames.com/en/work-with-us/jobs/software-engineer-intern-backend-systems",
        "description_raw": """About Riot Games

Riot Games was founded in 2006 to develop, publish, and support the most player-focused games in the world. We're creators of League of Legends, Valorant, Teamfight Tactics, and more games serving hundreds of millions of players globally. Our tech runs at the intersection of entertainment and real-time systems engineering.

About the Role

Backend Systems interns at Riot work on the infrastructure that keeps our games and player services online and responsive for millions of concurrent users. You'll be building services that handle real-time game state, player data, matchmaking, and live events.

What you'll do

- Build and ship production backend services in Go, Java, or Python that serve millions of players
- Work with distributed systems: Kafka message queues, Redis caching, PostgreSQL and Cassandra databases
- Contribute to game services such as matchmaking, player profiles, game sessions, or live event management
- Instrument systems with metrics, traces, and alerts using Datadog and Prometheus
- Participate in on-call rotations to understand production reliability
- Collaborate with senior engineers, game designers, and data scientists
- Write clean, well-tested, and documented code

What we're looking for

- Currently pursuing a degree in Computer Science, Software Engineering, or equivalent
- Strong programming skills in Go, Java, Python, or C++
- Understanding of distributed systems concepts: consistency, latency, fault tolerance
- Experience with relational or NoSQL databases
- Comfort working in a Linux/Unix environment
- Passion for games (any platform) is a genuine plus

Nice to have

- Experience with real-time game backend systems or online gaming infrastructure
- Familiarity with gRPC, Kafka, or distributed tracing
- Experience building or operating services at high scale

Summer 2026 Internship | 12 weeks
Remote (Canada) or Los Angeles, CA
""",
    },

    # ── 14. TD Bank — Data Engineer Co-op ───────────────────────────────────
    {
        "title": "Data Engineer Co-op",
        "company": "TD Bank",
        "location": "Toronto, ON",
        "url": "https://jobs.td.com/en-CA/job-detail/data-engineer-coop",
        "description_raw": """TD is one of the largest banks in North America and among the most admired. We are driven by a commitment to our customers and the communities we serve. At TD, we make a meaningful difference in the lives of our customers, communities, and the employees who work here every day.

The Opportunity

We're looking for a Data Engineer Co-op to join our Enterprise Data and Analytics team. You'll be part of a team that builds and maintains the data infrastructure that powers analytics and reporting across TD.

What You'll Do

- Build, optimize, and maintain ETL/ELT pipelines using Apache Spark, Airflow, and dbt running on our Azure data platform
- Design and implement data models in Snowflake and Azure Synapse to support business intelligence and analytics use cases
- Monitor data pipeline health and quality using Great Expectations and custom alerting frameworks
- Work with data engineers and data scientists to understand requirements and deliver reliable data products
- Write well-structured Python and SQL code with tests and documentation
- Contribute to our data catalog and data governance practices using Collibra
- Participate in Agile ceremonies: standups, sprint planning, retrospectives

What We're Looking For

Required:
- Enrolled in Computer Science, Data Engineering, Statistics, or a related program
- Proficiency in Python and SQL
- Experience with data transformation and pipeline development
- Understanding of relational database concepts
- Good communication and teamwork skills

Preferred:
- Experience with Apache Spark, Airflow, or dbt
- Familiarity with cloud data platforms (Azure Synapse, Snowflake, or Databricks)
- Understanding of data modeling concepts (star schema, data vault)
- Exposure to financial data (transactions, risk, regulatory reporting) is an asset

Co-op Term: May – August 2026
Location: Toronto, ON — Hybrid (3 days/week in office at TD Centre)
""",
    },

    # ── 15. Grafana Labs — Software Engineer Intern ──────────────────────────
    {
        "title": "Software Engineer Intern - Observability",
        "company": "Grafana Labs",
        "location": "Remote, Canada",
        "url": "https://grafana.com/careers/software-engineer-intern-observability",
        "description_raw": """About Grafana Labs

Grafana Labs is the company behind Grafana, the leading open-source observability platform used by millions of engineers around the world. We build tools that help teams understand their systems — from metrics and logs to traces and dashboards. Our product suite includes Grafana, Loki (log aggregation), Tempo (distributed tracing), and Mimir (metrics at scale).

The Role

We're looking for a Software Engineer Intern to contribute to one of our open-source observability products. You'll write code that ships to thousands of users, participate in design discussions, and work with a globally distributed team.

What You'll Do

- Contribute features and bug fixes to Grafana, Loki, Tempo, or Mimir — all open source, all in Go
- Write frontend features in TypeScript and React within the Grafana plugin ecosystem
- Build and improve Prometheus-compatible query engines and ingestion pipelines
- Write tests (unit, integration, and end-to-end) and participate in code reviews
- Work with Kubernetes for local development and deployment testing
- Engage with the open-source community — your work will be public
- Participate in async and sync communication with team members across time zones

What We're Looking For

- Currently pursuing a degree in Computer Science, Software Engineering, or a related field
- Proficiency in Go or TypeScript (we write primarily in both)
- Understanding of distributed systems, databases, or data pipelines
- Familiarity with Linux/Unix environments
- Comfort with async, remote-first collaboration
- Curiosity about observability: metrics, logs, traces, alerting

Bonus

- Prior open-source contributions
- Experience with Prometheus, PromQL, or Grafana
- Familiarity with Kubernetes and containerized deployments
- Knowledge of time-series databases or columnar storage

Internship: 4 months, starting May 2026
Location: Fully Remote (Canada)
""",
    },

    # ── 16. Scale AI — AI Quality Engineer Intern ────────────────────────────
    {
        "title": "AI Quality Engineer Intern",
        "company": "Scale AI",
        "location": "Remote, Canada",
        "url": "https://jobs.ashbyhq.com/scale/ai-quality-engineer-intern",
        "description_raw": """About Scale AI

Scale AI is the leading AI data company, helping machine learning teams at the world's best AI companies — including OpenAI, Meta, Microsoft, and hundreds more — build, train, and evaluate AI systems. Our platform powers the data pipelines behind the most important AI models in the world.

The Opportunity

We're looking for an AI Quality Engineer Intern to join our model evaluation and red-teaming team. You'll work at the intersection of AI safety, model evaluation, and software engineering to help ensure the AI models we work with are safe, reliable, and high-quality.

What You'll Do

- Design, build, and run automated evaluation pipelines for large language models (LLMs) and multimodal models using Python
- Write prompts and adversarial test cases to probe model behavior, including jailbreak attempts, prompt injection, and edge-case reasoning
- Analyze model outputs to identify failure patterns, hallucinations, safety violations, and capability gaps
- Build tooling to scale evaluation workflows: batch inference, metric computation, and result dashboards
- Collaborate with ML researchers and product teams to define evaluation criteria for new model capabilities
- Contribute to red-teaming frameworks and maintain a growing library of adversarial test cases
- Write clear documentation of evaluation methodology and results

What We're Looking For

- Enrolled in Computer Science, Statistics, Cognitive Science, or a related field
- Strong Python programming skills
- Genuine interest in AI safety, model evaluation, or red-teaming
- Critical thinking — ability to find edge cases and adversarial inputs
- Clear written communication — you'll write detailed evaluation reports
- Prior experience with LLMs (API usage, prompt engineering, fine-tuning) is a plus

Nice to Have

- Experience with PyTorch, TensorFlow, or Hugging Face Transformers
- Familiarity with multimodal models (vision-language models)
- Understanding of AI safety research (RLHF, Constitutional AI, etc.)
- Prior annotation or evaluation work with AI systems

Duration: 4 months | May – August 2026
Location: Remote (Canada or US)
""",
    },

    # ── 17. Brex — Software Engineer Intern ─────────────────────────────────
    {
        "title": "Software Engineer Intern",
        "company": "Brex",
        "location": "Remote, Canada",
        "url": "https://www.brex.com/careers/software-engineer-intern",
        "description_raw": """About Brex

Brex is the financial stack for the modern company. We make it easy for businesses to manage spend, get funding, and grow. We give teams corporate cards, expense management, travel booking, and business banking — all connected in one platform. More than 30,000 businesses use Brex today, from startups to global enterprises.

About the internship

Brex interns work on real product features alongside full-time engineers. We don't have a separate intern track — you'll be assigned to a product team, attend all their meetings, review code, and ship changes to production.

What you'll do

- Build backend services in Go and Python powering Brex's financial products: card programs, expense management, travel, and banking
- Design and implement REST and gRPC APIs consumed by our mobile and web clients
- Work with PostgreSQL, Kafka, and Redis in a distributed microservices environment
- Write comprehensive tests (unit, integration, contract) and deploy through our CI/CD pipelines
- Participate in code reviews, architecture discussions, and sprint ceremonies
- Understand compliance and financial regulatory constraints and build software that respects them
- Collaborate with product, design, and risk teams to ship well-rounded features

What we look for

- Currently enrolled in a Computer Science or Software Engineering program
- Proficiency in at least one backend language (Go, Python, Java, or Kotlin)
- Understanding of distributed systems and API design
- Experience with relational databases and SQL
- Collaborative, curious, and comfortable asking questions
- Strong written communication skills (we're async-heavy)

Nice to have

- Experience building financial applications or understanding of payment systems
- Familiarity with gRPC, Protobuf, or message queues (Kafka, RabbitMQ)
- Exposure to compliance or regulatory requirements in financial services

Term: Summer 2026 (May – August, 12 weeks)
Location: Remote (Canada eligible)
Compensation: Competitive stipend + housing assistance
""",
    },

    # ── 18. Databricks — Software Engineer Intern ────────────────────────────
    {
        "title": "Software Engineer Intern - Runtime",
        "company": "Databricks",
        "location": "Remote, Canada",
        "url": "https://databricks.com/company/careers/software-engineer-intern-runtime",
        "description_raw": """About Databricks

Databricks is the Data and AI company. More than 10,000 organizations worldwide — including block, Comcast, Regeneron, and Rivian — rely on the Databricks Data Intelligence Platform to unify and democratize data, analytics, and AI. Databricks is headquartered in San Francisco, with offices around the globe and was founded by the original creators of Apache Spark, Delta Lake, and MLflow.

The Opportunity

The Runtime team builds the execution engine at the heart of Databricks — Apache Spark and the distributed compute layer that runs millions of jobs per day. This internship offers deep exposure to systems programming, distributed computing, and query optimization.

What You'll Do

- Contribute to Apache Spark and Databricks Runtime in Scala, Java, and Python
- Implement performance optimizations: adaptive query execution, vectorized execution, and memory management
- Build features for Delta Lake, our open-source ACID storage layer built on Parquet
- Write and run benchmarks to measure the impact of your changes at scale
- Work through the full engineering lifecycle: design, implement, test, document, ship
- Engage with the open-source community around Apache Spark and Delta Lake
- Pair with senior engineers on complex distributed systems problems

What We Need

- Currently pursuing a degree in Computer Science or closely related field
- Strong programming skills in at least one JVM language (Java, Scala, Kotlin)
- Understanding of distributed computing concepts and data processing
- Familiarity with SQL and relational query processing
- Strong debugging and performance analysis skills

Ideal Candidates Also Have

- Experience with Apache Spark or other distributed compute frameworks
- Understanding of columnar storage formats (Parquet, ORC)
- Coursework or research in compilers, database systems, or operating systems
- Experience with JVM performance tuning (GC, JIT, memory)

Duration: 12 weeks (May – August 2026)
Location: Remote (Canada eligible) or San Francisco, CA
""",
    },

    # ── 19. Ubisoft — Junior Gameplay Programmer ─────────────────────────────
    {
        "title": "Junior Gameplay Programmer (Co-op)",
        "company": "Ubisoft",
        "location": "Montreal, QC",
        "url": "https://www.ubisoft.com/en-us/company/careers/search?jobId=junior-gameplay-programmer-coop",
        "description_raw": """About Ubisoft

Ubisoft is a leading creator, publisher and distributor of interactive entertainment and services, with a rich portfolio of world-renowned brands, including Assassin's Creed, Far Cry, Ghost Recon, Just Dance, Watch Dogs, Tom Clancy's video game series including Rainbow Six Siege, The Crew, and Rocksmith. Ubisoft's teams, across 45+ studios worldwide, are committed to delivering original and memorable gaming experiences across all popular platforms.

The Role

We're looking for a Junior Gameplay Programmer (Co-op) to join one of our game development teams in Montreal. You'll contribute to game systems development on one of Ubisoft's shipped or in-production AAA games.

What You'll Do

- Implement and iterate on gameplay systems including AI behaviors, physics interactions, player controls, and game mechanics in C++
- Work with our in-house proprietary game engine and tools
- Collaborate closely with game designers to implement features that match design intent
- Profile and optimize gameplay code for performance on console and PC targets (PS5, Xbox Series X, PC)
- Write and maintain unit and integration tests for gameplay systems
- Participate in code reviews, tech talks, and team meetings
- Debug and fix gameplay issues identified through internal playtesting and QA

Requirements

- Enrolled in a Computer Science, Software Engineering, Game Development, or related program
- Proficiency in C++ (our primary language for gameplay and engine code)
- Understanding of object-oriented programming and software design patterns
- Familiarity with game development concepts: game loops, entity-component systems, physics
- Good debugging skills and ability to work with large, complex codebases

Assets

- Experience with Unreal Engine 4/5 or Unity (in C++ or C#)
- Understanding of multithreaded programming and memory management
- Passion for games — active player on any platform
- Experience with performance profiling tools (PIX, RenderDoc, VTune)
- Prior co-op or internship in game development

Co-op Term: May – August 2026 | Full-time
Location: Montreal, QC — On-site
""",
    },

    # ── 20. Amazon — SDE Intern ──────────────────────────────────────────────
    {
        "title": "Software Development Engineer Intern",
        "company": "Amazon",
        "location": "Vancouver, BC",
        "url": "https://www.amazon.jobs/en/jobs/sde-intern-summer-2026",
        "description_raw": """About Amazon

Amazon is guided by four principles: customer obsession rather than competitor focus, passion for invention, commitment to operational excellence, and long-term thinking. We are driven by the excitement of building technologies, inventing products, and providing services that change lives. We embrace new ways of doing things, make decisions quickly, and are not afraid to fail.

About the role

Our Software Development Engineer (SDE) interns write real software and run it in production. Amazon's intern projects are not toy problems — they are product features or platform components that Amazon customers and engineers will use.

Key job responsibilities

- Design, develop, test, and deploy software that runs in production on AWS infrastructure
- Work within a senior engineering team to scope, design, and deliver features end to end
- Write high-quality, well-tested code in Java, Python, C++, or the language of your team
- Participate in design reviews, sprint planning, and code reviews
- Work backwards from customer needs and operational metrics to define product direction
- Own your work: monitor it in production, respond to operational issues, iterate based on data

Basic qualifications

- Enrolled in a Bachelor's or Master's degree program in Computer Science or related field
- Proficient in at least one programming language such as Java, Python, C++, or Kotlin
- Experience with data structures and algorithms
- Understanding of object-oriented design

Preferred qualifications

- Experience with distributed systems or cloud computing concepts
- Familiarity with AWS services (S3, DynamoDB, Lambda, SQS)
- Experience with REST API design and development
- Prior software engineering internship experience
- Strong communication skills — writing, presenting, debugging collaboratively

Internship Details
Duration: 12 weeks (May – August 2026)
Location: Vancouver, BC (hybrid — 3 days/week in office at Amazon YVR17)
Compensation: Competitive internship rate + housing assistance
""",
    },
]


def main():
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from engine.artifacts.generator import generate_artifacts, ARTIFACTS_DIR
    from pathlib import Path

    # Remove old test Stripe files if present
    for old in ARTIFACTS_DIR.glob("Moyosore_Jobi_*Stripe*.pdf"):
        old.unlink(missing_ok=True)

    print(f"Generating {len(JOBS)} application folders in {ARTIFACTS_DIR}/\n")

    ok = 0
    for i, job in enumerate(JOBS, 1):
        company = job["company"]
        title = job["title"]
        print(f"[{i:02d}/{len(JOBS)}] {company} — {title} ... ", end="", flush=True)
        try:
            result = generate_artifacts(job)
            folder = result.get("app_folder", "?")
            # Print folder name only (basename)
            print(f"OK  →  {Path(folder).name}/")
            ok += 1
        except Exception as e:
            print(f"FAILED: {e}")

    print(f"\n{'='*60}")
    print(f"Done. {ok}/{len(JOBS)} applications generated.")
    print(f"Location: {ARTIFACTS_DIR}/")


if __name__ == "__main__":
    main()
