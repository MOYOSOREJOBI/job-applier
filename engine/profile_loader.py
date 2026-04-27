from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
PROFILE_TRUTH_PATH = BASE_DIR / "config" / "profile_truth.json"
PROFILE_CATALOG_PATH = BASE_DIR / "config" / "profile_catalog.json"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _deep_merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_profile() -> dict[str, Any]:
    truth = _load_json(PROFILE_TRUTH_PATH)
    catalog = _load_json(PROFILE_CATALOG_PATH)
    if not truth and not catalog:
        return {}
    merged = _deep_merge(truth, catalog)
    merged.setdefault(
        "metadata",
        {
            "primary_profile_path": str(PROFILE_TRUTH_PATH),
            "catalog_path": str(PROFILE_CATALOG_PATH),
        },
    )
    return merged
