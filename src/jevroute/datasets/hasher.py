"""Deterministic hashing utilities for dataset files and record sets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Sequence


def hash_file(path: Path | str) -> str:
    """SHA-256 of file bytes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def hash_records(records: Sequence[dict]) -> str:
    """SHA-256 of canonically serialized records (sorted keys, sorted by JSON string)."""
    serialized = sorted(
        json.dumps(_canonical(r), separators=(",", ":"), sort_keys=True)
        for r in records
    )
    canonical = json.dumps(serialized, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def hash_example_ids(example_ids: Sequence[str]) -> str:
    """SHA-256 of sorted example_ids joined by newline."""
    joined = "\n".join(sorted(example_ids))
    return hashlib.sha256(joined.encode()).hexdigest()


def _canonical(obj: object) -> object:
    if isinstance(obj, dict):
        return {k: _canonical(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_canonical(x) for x in obj]
    return obj
