"""Taxonomy configuration loaded from config/taxonomy.json."""

import json
from pathlib import Path
from typing import List, Set, Dict


def _load_taxonomy_config() -> Dict[str, List[str]]:
    repo_root = Path(__file__).resolve().parent.parent.parent
    config_path = repo_root / "config" / "taxonomy.json"
    if not config_path.exists():
        return {"labels": [], "relation_types": []}
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


_TAXONOMY_DATA = _load_taxonomy_config()

TAXONOMY_LABELS: List[str] = sorted(_TAXONOMY_DATA.get("labels", []))
TAXONOMY_LABEL_SET: Set[str] = set(TAXONOMY_LABELS)

TAXONOMY_RELATION_TYPES: List[str] = sorted(_TAXONOMY_DATA.get("relation_types", []))
TAXONOMY_RELATION_TYPE_SET: Set[str] = set(TAXONOMY_RELATION_TYPES)

DEFAULT_LABEL: str = TAXONOMY_LABELS[0] if TAXONOMY_LABELS else "Claim"


def is_valid_label(label: str) -> bool:
    """Return True if the label name exists in the taxonomy."""
    return label in TAXONOMY_LABEL_SET


def is_valid_relation_type(rel_type: str) -> bool:
    """Return True if the relationship type exists in the taxonomy."""
    return rel_type in TAXONOMY_RELATION_TYPE_SET

