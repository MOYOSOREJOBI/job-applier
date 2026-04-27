# APPLICATION CHEAT SHEET — Moyosore Ogunjobi
### Keep this open in a second window. Copy-paste everything. Each application: 3-5 min.

---

## PERSONAL INFO — Always the same

| Field | Answer |
|---|---|
| First Name | Moyosore |
| Last Name | Ogunjobi |
| Preferred Name | Moyosore (MOY-oh-sor-ay) |
| Email | moyosorejobi@gmail.com |
| Phone | 825-736-5656 |
| City | Calgary |
| Province/State | Alberta (AB) |
| Country | Canada |
| Postal Code | (use your current postal code) |
| LinkedIn | linkedin.com/in/moyosore-ogunjobi-b187b8205 |
| GitHub | github.com/MOYOSOREJOBI |
| Portfolio / Website | moyosore.dev |
| University | University of Calgary |
| Degree | Bachelor of Science, Software Engineering |
| GPA | (enter your actual GPA) |
| Expected Graduation | May 2027 |
| Student ID | (enter your actual ID if required) |

---

## WORK AUTHORIZATION

| Question | Answer |
|---|---|
| Are you legally authorized to work in Canada? | Yes |
| Do you require sponsorship now or in the future? | No |
| Are you a Canadian citizen or permanent resident? | Yes / (use whichever applies) |
| Eligible for co-op/intern work permit? | Yes |
| Available for Fall 2026 (Sept–Dec)? | Yes, full-time |
| Available start date | September 2, 2026 |
| Available end date | December 19, 2026 |
| Hours per week available | 40 |

---

## 30 COMMON SCREENING QUESTIONS — Copy-paste ready

---

### Q1. Tell me about yourself / Introduce yourself.

I am a third-year Software Engineering student at the University of Calgary, graduating May 2027. I have production experience in backend systems, ML pipelines, and cloud infrastructure — I have built distributed services, real-time data pipelines, and ML-powered platforms. I currently evaluate 200+ AI model outputs weekly at Alignerr and lead a 10-person software team at the University of Calgary Solar Racing team. I am looking for a Fall 2026 internship where I can work on hard engineering problems and ship real software.

---

### Q2. Why do you want to work here? / Why this company?

*(Use the company-specific answer from the cover letter section below. The first paragraph of each cover letter is your answer to this question.)*

---

### Q3. What are your strengths?

My strongest technical skill is building reliable backend systems — designing for failure from the start, writing tests before considering a feature done, and making the system observable so problems are diagnosable. I also communicate well between technical and non-technical stakeholders; at Oando I turned 90 days of sensor data into a maintenance recommendation leadership could act on. And I am fast — I pick up new tools and frameworks quickly and I do not stay stuck.

---

### Q4. What is your greatest weakness?

I move fast by default, which sometimes means I start implementing before I have fully thought through the edge cases. I have learned to slow down at the design phase — I now write out the failure modes I am worried about before I write any code, which catches most of the issues I would otherwise find mid-implementation.

---

### Q5. Tell me about a challenge you faced and how you overcame it.

During the Solar Racing team's first competition with the telemetry system I built, the alerting system was firing false positives. During a race, that is dangerous — the crew cannot afford noise. I had built structured logging into the ingestion pipeline, so I was able to trace the bad alerts back to a sensor calibration issue rather than a software bug. I wrote a filtering layer that normalized the outlier readings and the false positives stopped. The team finished in the top 10 at FSGP 2024. The key was that I had the instrumentation to diagnose the problem quickly instead of guessing.

---

### Q6. Tell me about a time you worked on a team.

I lead a 10-person software team at the University of Calgary Solar Racing team as Software VP. My job is to own architecture decisions, run Agile sprints, and make sure 10 people with different skill levels are unblocked and shipping. The biggest challenge is coordination — making sure the person building the dashboard and the person building the data pipeline are not making incompatible assumptions. I run weekly syncs, do code reviews on every PR, and keep a shared architecture doc that everyone writes to. We delivered the full telemetry system on time for FSGP 2024.

---

### Q7. Tell me about a time you showed leadership.

When I joined Solar Racing as a junior member, the telemetry software was held together with duct tape — undocumented, untested, and dependent on one person who had graduated. I proposed a full rebuild to the team leads, scoped the project, and led a team of 3 to rearchitect it from scratch. I set up code review standards, broke the work into sprints, and made sure we had something working at each checkpoint rather than a big-bang delivery. The system was live at competition and the crew trusted it. That project is what got me promoted to Software VP.

---

### Q8. Where do you see yourself in 5 years?

As a senior software engineer at a company I believe in, working on hard problems at scale. I want to be the person other engineers bring their hardest architectural questions to. I am interested in distributed systems and infrastructure long term, but I am still early in my career and I think the best thing I can do right now is work on as many real production problems as possible and build genuine depth.

---

### Q9. Why software engineering?

I like building things that work correctly and that other people rely on. I got into engineering because I wanted to understand how systems work — and software engineering is the field where you build the systems, measure them, break them, and fix them, all in one job. The combination of creative problem-solving, rigorous correctness requirements, and real-world impact is what keeps me engaged.

---

### Q10. What is your most significant project?

The project I am most proud of is the real-time telemetry system I built for the University of Calgary Solar Racing Team. It streams 50+ sensor signals per second from a moving solar vehicle to live Grafana dashboards, with alerts that fire within 2 seconds of a critical event. I built the entire system — the WebSocket ingestion pipeline, PostgreSQL time-series schema, Prometheus metrics, and Grafana dashboards. It was live under race conditions at FSGP 2024 and the team finished in the top 10. The technical challenge was reliability under noise — sensors misfire, connections drop, and the system had to handle those gracefully without alarming the crew on false positives.

---

### Q11. Describe your experience with [Python / Java / SQL].

**Python:** My primary language for 3+ years. I use it for data pipelines, ML model training and serving with FastAPI, automation scripts, and data analysis with Pandas and NumPy. At Alignerr I built Python automation that reduced annotation workflow steps by 40%.

**Java:** Used Java to build a distributed payment gateway with idempotent REST endpoints, PostgreSQL persistence, and concurrent request handling. Comfortable with Spring Boot patterns, JUnit testing, and Java concurrency.

**SQL:** Daily use at Alignerr and Data Annotation for data quality queries. Built the full PostgreSQL schema for both the payment gateway and the Solar Racing telemetry system, including time-series data modeling and index design for query performance.

---

### Q12. How do you handle tight deadlines?

I break the work down immediately — what is blocking everything else, what can be parallelized, what can be cut without breaking the core requirement. At Solar Racing I had 3 weeks before competition to finish the alerting system. I scoped it to the 2-3 alert types the crew actually needed, shipped those first, and added the nice-to-haves after the race. The system worked. I do not try to do everything; I try to do the right things first.

---

### Q13. How do you stay current with technology?

I build things. Reading about a technology tells me what it does; building something with it tells me where it breaks. I have been working through distributed systems fundamentals using Designing Data-Intensive Applications, and I pick up new tools by taking a small real problem and solving it with that tool. I also review production-grade code weekly at Alignerr across Python, Ruby, and Go, which gives me exposure to how experienced engineers actually write systems.

---

### Q14. Tell me about a time you received critical feedback.

Early in my work at Alignerr, my annotation accuracy was around 88% — below the 95% threshold. My senior reviewer flagged that I was applying rubrics inconsistently on edge cases. I went back through my rejections, identified the pattern (I was underweighting partial completeness in code generation tasks), wrote a personal rubric addendum, and applied it consistently for two weeks. My accuracy hit 95%+ and has stayed there. The feedback was correct and I am glad I got it early.

---

### Q15. Do you prefer working alone or in a team?

Both, depending on the phase. I prefer to design alone — I think better without interruption — but I want constant feedback once I have something working. I show work early, ask for review before I think it is ready, and I change direction based on feedback. The worst outcome is spending two weeks building the wrong thing, and the only way to avoid that is staying in sync with the team.

---

### Q16. What do you know about our tech stack / what technologies are you familiar with?

*(Use the role-specific tech stack from the resume for that application. Example for Shopify: Ruby, Go, Python, Java, REST APIs, GraphQL, PostgreSQL, Redis, Kafka, Docker, Kubernetes, CI/CD, Grafana, Prometheus.)*

---

### Q17. What is your experience with Agile / Scrum?

I run Agile sprints as Software VP at Solar Racing — two-week sprints, backlog grooming, sprint reviews, and retrospectives. I use GitHub Projects for task tracking and GitHub Actions for CI/CD so the team gets automated test feedback on every PR. I have seen what breaks Agile: unclear acceptance criteria, no code review, and skipping retros. I try to address all three.

---

### Q18. Have you ever missed a deadline? What happened?

Yes. Early in my first semester leading Solar Racing, I underestimated how long the PostgreSQL schema migration would take because I did not account for data backfill time. I caught it a week before the deadline and immediately told the team lead we needed to adjust scope. We cut one dashboard feature, completed the migration clean, and I built the cut feature the following sprint. Missing the deadline would have been worse than cutting scope — and communicating early was what made the recovery possible.

---

### Q19. What are your salary expectations?

I am targeting the standard market rate for software engineering internships in Canada, which I understand is in the range of $25–35/hour depending on the company and location. I am flexible and primarily focused on finding the right role where I can learn and contribute.

---

### Q20. Are you interviewing anywhere else?

I am actively exploring a number of opportunities in [backend engineering / data / infrastructure / ML depending on role]. I am focused on Fall 2026 positions and am prioritizing roles where I can work on meaningful technical problems.

---

### Q21. What is your GPA?

*(Enter your actual GPA. If below 3.0, do not volunteer it — only enter if the form requires it.)*

---

### Q22. Have you worked with cloud platforms (AWS/GCP/Azure)?

Yes, primarily AWS. I hold four AWS certifications: Solutions Architect Associate, Developer Associate, Data Engineer Associate, and Machine Learning Engineer Associate. I have hands-on experience with EC2, S3, Lambda, RDS, ECS, Route 53, and CloudWatch. I have deployed containerized services on AWS using Terraform for infrastructure-as-code and GitHub Actions for CI/CD.

---

### Q23. Tell me about your experience with databases.

I use PostgreSQL as my primary database. I designed the schema for the Solar Racing telemetry system (time-series sensor data, event logging) and the payment gateway (transaction records, idempotency key tracking, audit tables). I understand indexing, query plan analysis, and schema design for write-heavy workloads. I have also used MongoDB for document storage, Redis for caching and rate limiting, and have worked with SQL Server in data annotation pipelines.

---

### Q24. How do you approach testing?

Tests before merge, always. I write unit tests for business logic, integration tests for database and API behavior, and I treat coverage of failure paths as mandatory. I do not consider a feature done until the happy path, the error path, and at least one concurrency or edge case are covered. At the payment gateway project I built the full test suite before deployment — 90%+ coverage on critical paths — and it caught three race condition bugs I would not have found manually.

---

### Q25. What is a technical concept you recently learned?

I recently went deep on idempotency in distributed payment systems — specifically how to design REST endpoints that are safe under client retry without double-processing. The key insight was that idempotency is a schema design problem, not just an application logic problem: you need a durable record of which requests have been processed and what they returned, so that a duplicate request returns the same result without re-executing the side effects. I implemented this with a PostgreSQL idempotency key table and it reduced failure cascades under concurrent load by 60%.

---

### Q26. Why are you leaving your current role / looking for a new position?

I am a student looking for my Fall 2026 internship. My current work at Alignerr and Data Annotation is part-time contract work I do alongside school. I am looking for a full-time internship role where I can work on a real engineering team, ship production code, and build depth in [backend systems / infrastructure / ML / depending on role].

---

### Q27. What does good code look like to you?

Code that is correct, readable, and testable. Correct means it handles the failure cases, not just the happy path. Readable means a new person can understand what it does and why, without needing to ask someone. Testable means the logic is separated from side effects so you can unit test it without mocking everything. I also think good code is code that was changed — if it has never been refactored, it probably reflects a misunderstanding that was never corrected.

---

### Q28. How do you handle working with legacy or messy code?

I read it before I touch it. I try to understand the invariants the code is actually enforcing before I change them, even if the code is hard to read. Then I add tests around the behavior I am about to change, so that I can tell if I accidentally broke something. I do not rewrite things just because I do not like the style — I scope changes to what the task requires.

---

### Q29. Are you comfortable with ambiguity?

Yes. Most of my meaningful work has started with an unclear problem. At Oando the ask was "help us reduce maintenance costs" — I had to figure out what data existed, what questions were actually answerable, and what output format would be useful to the people making decisions. I am comfortable starting with a fuzzy problem, identifying what I need to know, and narrowing scope until something concrete is deliverable.

---

### Q30. Do you have any questions for us?

- What does the first 2 weeks look like for an intern on this team?
- What is the biggest technical challenge the team is working on right now?
- How do interns get access to production systems and how is code reviewed?
- What does a strong intern look like at the end of the term?

---

## COVER LETTERS — Copy-paste ready (paste into "cover letter" or "additional comments" fields)

---

### 1. SUNCOR — Digital Analyst Co-op

My first real experience with operational data was at Oando PLC, Nigeria's largest energy company. I spent a summer sitting with field engineers, learning what data they actually looked at versus what they ignored, and why the gap between those two things was costing the company money. That work is what brought me to data engineering and to Calgary — and it is why your Digital and Technology team is the exact environment I want to grow in.

The telemetry system I built for the University of Calgary Solar Racing Team is the project that best shows what I bring to operational data problems. We needed live visibility into 50+ sensor signals from a moving vehicle, with dashboards the crew could read in seconds and alerts that fired within 2 seconds of a critical event. I built the pipeline in Python with PostgreSQL time-series storage, Grafana dashboards, and Prometheus-backed alerting — the same patterns used in SCADA and PI System historian environments. That system was live in competition, and the crew trusted it. The team finished in the top 10 at FSGP 2024.

I work well at the boundary between technical systems and the people who depend on them. At Oando I did not just run queries — I turned sensor data into a report the operations manager could present to leadership. That translation between technical output and business decision is where I am most effective, and it is the core of what your Digital Analyst role requires.

My coursework in Practices in Data Management, Probability Statistics and ML, Software Architecture, and Embedded System Interfacing gives me both the data engineering foundation and the systems context to work across Suncor's OT and IT environments.

I am a Software Engineering student at the University of Calgary, graduating in May 2027. I am available full-time for Fall 2026. I hold work authorization for Canada.

I look forward to discussing how I can contribute to the Operations Analytics team. Thank you for your time.

Moyosore Ogunjobi — moyosorejobi@gmail.com — 825-736-5656 — moyosore.dev

---

### 2. RBC — Data Analyst Intern, Capital Markets

Capital markets data is some of the most demanding data engineering work there is. Trade records, risk metrics, and market feeds all need to be accurate, timely, and consistent — and the cost of getting it wrong is immediate. That combination of technical rigor and business consequence is exactly the environment I want to work in, and RBC Capital Markets is one of the best places in Canada to do it.

At Oando PLC I got my first real taste of what operational data analysis looks like when the outputs actually matter. I queried 90 days of field equipment sensor data using Python and SQL, built dashboards for the operations leadership team, and translated the findings into maintenance recommendations that supported a 15% reduction in unplanned downtime. The challenge was not just writing the queries — it was making the output trustworthy and useful to stakeholders who were making resourcing decisions based on it. That accountability is the same standard I would bring to your trading desk reporting and risk data pipelines.

I write clean, reproducible SQL and I treat data quality as a hard requirement, not a nice-to-have. At Alignerr and Data Annotation I review structured datasets daily with 95%+ accuracy and I build QA protocols that other reviewers can follow consistently. That same discipline applies to financial data where label errors translate directly to bad decisions.

My coursework in Practices in Data Management, Probability Statistics and ML, Data Structures and Algorithms, and Applied Deep Learning gives me the quantitative and pipeline-building foundation to contribute to your team immediately.

I am a Software Engineering student at the University of Calgary, graduating in May 2027. I am available full-time for Fall 2026. I hold work authorization for Canada.

Moyosore Ogunjobi — moyosorejobi@gmail.com — 825-736-5656 — moyosore.dev

---

### 3. DELOITTE — Technology Consulting Analyst Intern

What draws me to consulting is the combination of technical problem-solving and stakeholder communication — the requirement that you not only figure out what is wrong and how to fix it, but that you explain it clearly enough that someone else can make a decision. That combination is rare and it is exactly what Deloitte Technology and Transformation does at scale across industries.

The work I am most proud of from my Oando PLC internship was not the analysis itself — it was what happened after it. I had 90 days of field equipment sensor data, Python and SQL to work with, and an operations manager who needed to make a maintenance staffing decision. I built the analysis, identified the patterns, and then wrote a structured recommendation that the manager could present to leadership. That recommendation supported a 15% reduction in unplanned maintenance and gave the team a process for ongoing anomaly monitoring. The technical output only had value because I translated it into something actionable for a non-technical stakeholder.

At Alignerr I communicate evaluation findings weekly across technical and non-technical reviewers, translating AI output quality issues into clear, prioritized feedback. That skill — making complex technical work accessible and actionable — is what consulting demands, and it is something I have been building deliberately.

My coursework in Software Architecture, Practices in Data Management, Industry Practice and Communication, and Principles of Software Design gives me the analytical and communication foundation to contribute on client engagements from day one.

I am a Software Engineering student at the University of Calgary, graduating in May 2027. I am available full-time for Fall 2026. I hold work authorization for Canada.

Moyosore Ogunjobi — moyosorejobi@gmail.com — 825-736-5656 — moyosore.dev

---

### 4. ATB FINANCIAL — Technology Developer Intern

ATB is an Alberta institution — 800,000 customers who trust you with their mortgages, payroll, and savings. Building the backend systems behind that level of trust means that correctness is not optional. Every API, every transaction, every database write has to be right the first time. That is the standard I build to, and it is why I want to work on ATB's Digital Banking platform.

The project that most directly maps to what your team builds is my distributed payment gateway, designed in Java and Python with a PostgreSQL-backed transaction store. The hardest design problem was making payment operations safe under retry conditions — concurrent requests, partial network failures, and client-side retries all creating the risk of double-processing. I implemented idempotency keys across every payment endpoint and designed the PostgreSQL schema to track API state in a way that guaranteed exactly-once processing semantics. Failure cascades under concurrent load dropped by 60%.

I hold a high bar and I do not merge code I have not tested. I write unit and integration tests before I consider a feature done, and I treat test coverage of failure paths as mandatory, not optional.

My coursework in Data Structures and Algorithms, Software Architecture, Principles of Software Design, and Software Testing maps directly to the reliability-first engineering your team does.

I am a Software Engineering student at the University of Calgary, graduating in May 2027. I am available full-time for Fall 2026. I hold work authorization for Canada.

Moyosore Ogunjobi — moyosorejobi@gmail.com — 825-736-5656 — moyosore.dev

---

### 5. WEALTHSIMPLE — Full Stack Software Engineer Intern

I use Wealthsimple to invest. The reason I have stayed is not the returns — it is that the product feels like it is on my side. The UI does not hide fees or bury information in footnotes. The trade execution is fast and clear. Most financial products feel like they are designed to confuse you; yours does not. Building products that feel that honest is exactly the kind of work I want to do.

The project that best shows my full stack range is a data analytics platform I built end-to-end in React, TypeScript, and FastAPI. I owned the product from PostgreSQL schema through API layer to frontend state management. The hardest problem was user experience — the model inference was slow and I needed the UI to stay responsive while waiting on results. I rearchitected the backend with a GraphQL API layer and batch processing, cutting over-fetching by 40% and making the frontend feel fast regardless of model complexity. I built the React user flows myself, wrote Jest unit tests, and shipped each feature with coverage on the paths that matter.

I care about the user experience at the component level. A form that gives unclear errors, a dashboard that loads slowly, an empty state that leaves the user confused — these are product bugs, not just UX issues, and I treat them that way.

My coursework in Full Stack Web Development, Software Architecture, Data Structures and Algorithms, and Principles of Software Design gives me the depth to work across your entire stack.

I am a Software Engineering student at the University of Calgary, graduating in May 2027. I am available full-time for Fall 2026. I hold work authorization for Canada.

Moyosore Ogunjobi — moyosorejobi@gmail.com — 825-736-5656 — moyosore.dev

---

### 6. CLOUDFLARE — Infrastructure Engineer Intern

Cloudflare runs the infrastructure layer under a significant portion of the internet. 300+ data centers, 60 million requests per second, DNS, TLS termination, DDoS mitigation, and edge compute — all of it has to work, at all times, at global scale. The engineering discipline required to keep that running is some of the most demanding systems work in the industry, and it is exactly the kind of infrastructure problem I want to work on.

The clearest example of my infrastructure approach is the payment gateway I deployed entirely as code. I wrote Terraform modules for every environment, configured Kubernetes with rolling updates and pod health checks, and provisioned DNS routing and TLS certificate management for cloud-deployed services via AWS Route 53 and container ingress controllers. When deployments broke I used Linux networking tools — tcpdump, netstat, kubectl exec — to trace the failure from the container boundary inward. Every environment was reproducible from a single git commit.

I think in layers. When something breaks I start at the network boundary and work inward: DNS resolves correctly, TLS handshake succeeds, request reaches the service, service responds correctly. I instrument everything — structured logs, Prometheus metrics, Grafana dashboards — so the next person on call does not have to guess.

My coursework in Software Architecture, Embedded System Interfacing, Data Structures and Algorithms, and Principles of Software Design gives me the systems-level foundation to contribute to your Core Infrastructure team.

I am a Software Engineering student at the University of Calgary, graduating in May 2027. I am available full-time for Fall 2026. I hold work authorization for Canada.

Moyosore Ogunjobi — moyosorejobi@gmail.com — 825-736-5656 — moyosore.dev

---

### 7. DATADOG — Backend Software Engineer Intern

I built an observability system from scratch for a solar race car. The race crew needed live dashboards, reliable anomaly alerts, and the confidence that if something went wrong with the vehicle, they would know about it within 2 seconds. Building that system — the ingestion pipeline, the metrics, the alert thresholds, the dashboard layout — gave me a concrete understanding of what good observability actually means: not just collecting data, but making sure the right signal reaches the right person at the right time. That is Datadog's entire mission, and it is why I want to work here.

That telemetry system streams 50+ sensor signals per second using Redis Streams for high-throughput event processing, stores structured time-series data in PostgreSQL, and surfaces everything through Grafana dashboards backed by Prometheus metrics. I built structured logging and error rate tracking across the ingestion layer so I could debug pipeline throughput issues without guessing. When the alerting system surfaced false positives during FSGP 2024, I had the instrumentation to trace the noise back to a sensor calibration issue rather than a software bug. The team finished in the top 10.

My coursework in Software Architecture, Data Structures and Algorithms, Probability Statistics and ML, and Embedded System Interfacing gives me the technical depth to contribute to your Backend Platform team.

I am a Software Engineering student at the University of Calgary, graduating in May 2027. I am available full-time for Fall 2026. I hold work authorization for Canada.

Moyosore Ogunjobi — moyosorejobi@gmail.com — 825-736-5656 — moyosore.dev

---

### 8. SHOPIFY — Backend Software Engineer Intern

Shopify's checkout flow is one of the most well-designed systems I have used as both a developer and a buyer. The cart state is preserved across devices, the payment routing handles edge cases cleanly, and the error messages are actually useful. That level of backend reliability does not come from good intentions — it comes from engineers who have thought carefully about every failure mode, every retry, every duplicate request. Building systems at that standard is exactly the kind of work I want to do.

Payment infrastructure is the problem I have spent the most time on. I built a distributed payment gateway in Java and Python where the core engineering challenge was correctness under failure: concurrent requests, network timeouts, client retries, all creating the risk of double-processing. I implemented idempotent REST endpoints with Redis caching, designed the PostgreSQL schema to track payment state explicitly, and added unit and integration tests covering API behavior, database persistence, and failure scenarios before any feature shipped. Failure cascades under concurrent load dropped by 60%.

I write tests before I consider a feature done and I do not merge without meaningful coverage on the failure paths. At Alignerr I review production backend code including Ruby and Go outputs weekly, which has given me practical familiarity with the patterns Shopify's stack depends on.

My coursework in Data Structures and Algorithms, Software Architecture, Principles of Software Design, and Software Testing gives me the fundamentals to contribute from day one.

I am a Software Engineering student at the University of Calgary, graduating in May 2027. I am available full-time for Fall 2026. I hold work authorization for Canada.

Moyosore Ogunjobi — moyosorejobi@gmail.com — 825-736-5656 — moyosore.dev

---

### 9. ANTHROPIC — ML Research Intern

I spend 200+ hours every month evaluating language model outputs professionally. I review code generation, mathematical reasoning, and instruction-following tasks — not as a user reacting to responses, but as an evaluator applying structured rubrics to identify exactly where models fail and why. That work has given me a practical, firsthand understanding of how transformer model behavior breaks down at scale, and it is what brought me to Anthropic's alignment research as the most important work I can contribute to.

The project I built to formalize that work is an LLM evaluation harness in Python and PyTorch. I designed structured rubrics testing model outputs across correctness, consistency, refusal behavior, and instruction-following quality, and built automated aggregate metrics to identify systematic failure patterns across 500+ test cases. The findings from that work — the consistent failure modes in mathematical reasoning and the specific conditions that trigger inconsistent refusal behavior — are the kind of signals that feed directly into RLHF training improvements.

I think carefully about what evaluation is actually measuring. A benchmark score is meaningless if the rubric does not capture the behavior you care about. At Alignerr I write the rubrics, apply them, and document the edge cases — the complete evaluation lifecycle.

My coursework in Machine Learning Systems, Applied Deep Learning, Probability Statistics and ML, and Software Architecture gives me the theoretical foundation to contribute to your evaluation and alignment research infrastructure.

I am a Software Engineering student at the University of Calgary, graduating in May 2027. I am available full-time for Fall 2026. I hold work authorization for Canada. I am open to United States roles with employer sponsorship.

Moyosore Ogunjobi — moyosorejobi@gmail.com — 825-736-5656 — moyosore.dev

---

### 10. ELECTRONIC ARTS — Software Engineer Intern, Game Systems

I have been playing EA Sports games since I was a kid. What I did not understand then, and what I find genuinely fascinating now as an engineer, is how much systems work makes a game feel right. Stable frame rates, collision that does not glitch, physics that behaves predictably under stress — none of that happens by accident. It is the result of engineers who understand cache behavior, memory layout, and real-time scheduling well enough to get it right at 60fps. That is the kind of engineering I want to do.

The project I built to pursue that directly is a C++17 2D physics simulation engine using SFML and CMake. I implemented an entity-component-system architecture with rigid body physics, AABB collision detection, and a fixed-timestep game loop. When the frame rate dropped under load I used Valgrind and gprof to profile the hot paths, identified that the collision detection phase was cache-inefficient due to scattered memory access, and restructured the entity storage to a data-oriented layout. Per-frame processing time dropped by 40% and the simulation held a stable 60fps under the full scene load.

My real-time telemetry system for the Solar Racing team reinforced the same principles. Streaming 50+ sensor signals per second with sub-100ms latency is the same class of problem as a game engine's input and rendering pipeline: high-throughput, low-latency, no dropped frames.

My coursework in Computer Organization, Embedded System Interfacing, Data Structures and Algorithms, and Software Architecture gives me the low-level systems foundation to contribute to your Game Technology team.

I am a Software Engineering student at the University of Calgary, graduating in May 2027. I am available full-time for Fall 2026. I hold work authorization for Canada.

Moyosore Ogunjobi — moyosorejobi@gmail.com — 825-736-5656 — moyosore.dev

---

## APPLICATION TRACKER — v2 (USE THESE)

| # | Company | Role | Portal | Resume PDF | Status | Date Applied |
|---|---|---|---|---|---|---|
| 1 | Suncor Energy | Digital Analyst Co-op | careers.suncor.com | v2/01-suncor-digital-analyst/resume.pdf | [ ] | |
| 2 | RBC | Data Analyst Intern | jobs.rbc.com | v2/02-rbc-data-analyst/resume.pdf | [ ] | |
| 3 | Deloitte Canada | Technology Consulting Analyst | deloitte.com/careers | v2/03-deloitte-consulting/resume.pdf | [ ] | |
| 4 | ATB Financial | Technology Developer Intern | atb.com/careers | v2/04-atb-banking-tech/resume.pdf | [ ] | |
| 5 | Wealthsimple | Full Stack SWE Intern | grnh.se/wealthsimple | v2/05-wealthsimple-fullstack/resume.pdf | [ ] | |
| 6 | Cloudflare | Infrastructure Engineer Intern | cloudflare.com/careers | v2/06-cloudflare-infra/resume.pdf | [ ] | |
| 7 | Datadog | Backend SWE Intern | datadoghq.com/careers | v2/07-datadog-backend/resume.pdf | [ ] | |
| 8 | Shopify | Backend SWE Intern | shopify.com/careers | v2/08-shopify-backend/resume.pdf | [ ] | |
| 9 | Anthropic | ML Research Intern | anthropic.com/careers | v2/09-anthropic-ml-research/resume.pdf | [ ] | |
| 10 | Electronic Arts | Software Engineer Intern | ea.com/careers | v2/10-ea-software-engineer/resume.pdf | [ ] | |

## BONUS v1 (correctly named now — submit after v2 batch)

| # | Company | Role | Resume PDF | Status | Date Applied |
|---|---|---|---|---|---|
| 11 | Shopify | Backend SWE Intern | 01-shopify-backend/resume.pdf | [ ] | |
| 12 | Google | Software Engineer Intern | 02-google-swe-intern/resume.pdf | [ ] | |
| 13 | Cohere | ML Engineer Intern | 03-cohere-ml-engineer/resume.pdf | [ ] | |
| 14 | Wealthsimple | Full Stack Intern | 04-wealthsimple-fullstack/resume.pdf | [ ] | |
| 15 | Palantir | Infrastructure Intern | 05-palantir-devops/resume.pdf | [ ] | |
| 16 | TD Bank | Technology Solutions Intern | 06-td-bank-tech/resume.pdf | [ ] | |
| 17 | Stripe | Backend SWE Intern | 07-stripe-backend/resume.pdf | [ ] | |
| 18 | AWS / Amazon | Systems Dev Engineer | 08-aws-systems-dev/resume.pdf | [ ] | |
| 19 | Microsoft | Software Engineer | 09-microsoft-swe/resume.pdf | [ ] | |
| 20 | Scale AI | ML Platform Engineer | 10-scaleai-ml-platform/resume.pdf | [ ] | |

---

## HOW TO APPLY IN 3-5 MIN PER ROLE

1. Open company careers portal (links above)
2. Search: intern OR co-op + software OR data OR engineering + Fall 2026
3. Upload PDF from the path listed above
4. Paste cover letter from this doc into the cover letter field
5. Fill personal info from the top section
6. Answer screening questions from the Q&A above
7. Submit and mark tracker

**ALSO apply on LinkedIn Easy Apply** — search the company + role on LinkedIn, filter by Easy Apply. Fastest path for most roles.

**Install Simplify extension** (simplify.jobs) — auto-fills application forms from your resume. Works on Greenhouse, Lever, Workday, and most portals. Free and within ToS.
