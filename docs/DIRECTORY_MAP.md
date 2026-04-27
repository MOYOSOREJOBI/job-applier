# Directory Map

This map keeps `job-applier/` easy to scan and audit.

## Source Of Truth

- [config/profile_truth.json](/Users/mac/Desktop/resume/job-applier/config/profile_truth.json)
  Minimal verified identity, education, skills, work authorization, and baseline project facts.
- [config/profile_catalog.json](/Users/mac/Desktop/resume/job-applier/config/profile_catalog.json)
  Audit-friendly coursework, projects, leadership, and resume asset references.
- [docs/](/Users/mac/Desktop/resume/job-applier/docs)
  Operational notes and workspace rules.

## Runtime And Generated Output

- [applications/](/Users/mac/Desktop/resume/job-applier/applications)
  Per-job application folders grouped by date, company, and role.
- [artifacts/](/Users/mac/Desktop/resume/job-applier/artifacts)
  Generated resumes, cover letters, answer files, staged artifacts, and batches.
- [storage/](/Users/mac/Desktop/resume/job-applier/storage)
  SQLite data, browser state, and other runtime storage.
- [logs/](/Users/mac/Desktop/resume/job-applier/logs)
  Proof logs, run logs, screenshots, and maintenance notes. Preserve these unless you have exported and reviewed them.

## Code Areas

- [backend/](/Users/mac/Desktop/resume/job-applier/backend)
  FastAPI server entrypoints.
- [engine/](/Users/mac/Desktop/resume/job-applier/engine)
  Discovery, scoring, artifact generation, apply logic, and profile loading.
- [frontend/](/Users/mac/Desktop/resume/job-applier/frontend)
  React dashboard.
- [tests/](/Users/mac/Desktop/resume/job-applier/tests)
  Test coverage for critical policies.

## Maintenance Rules

- Keep `logs/` intact.
- Prefer archiving over deleting when a file might still have audit value.
- Remove cache noise such as `__pycache__/` and `.DS_Store` freely.
