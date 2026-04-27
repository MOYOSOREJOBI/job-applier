#!/usr/bin/env python3
"""
Job Applier — run.py
=====================
Examples:
  python scripts/run.py --url "https://linkedin.com/jobs/view/4374445317"
  python scripts/run.py --recommended --limit 20
  python scripts/run.py --search "software engineer intern Canada" --limit 15
  python scripts/run.py --github --limit 30
  python scripts/run.py --from-file ../study/unique_verified_application_links_jan22_2026.csv
  python scripts/run.py --recommended --limit 5 --dry-run
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from job_applier import main

if __name__ == "__main__":
    main()
