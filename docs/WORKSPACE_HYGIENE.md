# Workspace Hygiene

This repo now treats files in four buckets:

1. `config/`
   Canonical user/profile data that should be easy to audit.
2. `docs/`
   Human-readable operating notes, setup steps, and workspace policies.
3. `logs/`
   Run history, proof exports, screenshots, and maintenance logs.
4. Runtime/generated directories
   `applications/`, `artifacts/`, `storage/`, and frontend build output.

## Profile Source Of Truth

- `config/profile_truth.json`
  Required, minimal truth set used by the apply engine.
- `config/profile_catalog.json`
  Audit-friendly catalog for coursework, projects, and leadership material.
- `engine/profile_loader.py`
  Merges both files so the application can stay simple while the profile stays readable.

## Root Workspace Layout

At `/Users/mac/Desktop/resume`, the preferred shape is:

- `job-applier/` for the application system
- `resume-materials/` for current and legacy resume artifacts
- `archive/` for downloads, references, extracted experiments, and one-off scripts
- `testing/` or other sandboxes only when they are actively useful

## Logs

Maintenance actions should leave a log in `logs/`.

Current workspace cleanup log:
- `logs/workspace_cleanup_2026-04-20.md`
- `logs/maintenance/workspace_cleanup_2026-04-21.md`

## Safe Cleanup Rules

- Do not delete proof logs, screenshots, or generated application folders unless you have exported or reviewed them.
- Keep browser/cache storage only if you still need the session state.
- Prefer archiving over deleting when the value is uncertain.
- Keep the readable resume source in `resume-materials/current/source/` aligned with the profile catalog so the active PDF is not the only current artifact.
