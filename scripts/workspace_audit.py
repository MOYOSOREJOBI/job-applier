from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
JOB_APPLIER = ROOT / "job-applier"
LOG_PATH = JOB_APPLIER / "logs" / "workspace_inventory.json"


def list_names(path: Path) -> list[str]:
    if not path.exists():
        return []
    return sorted(child.name for child in path.iterdir())


def main() -> None:
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "root": str(ROOT),
        "top_level": list_names(ROOT),
        "archive": list_names(ROOT / "archive"),
        "resume_materials": list_names(ROOT / "resume-materials"),
        "job_applier_config": list_names(JOB_APPLIER / "config"),
        "job_applier_docs": list_names(JOB_APPLIER / "docs"),
        "job_applier_logs": list_names(JOB_APPLIER / "logs"),
    }
    LOG_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    print(LOG_PATH)


if __name__ == "__main__":
    main()
