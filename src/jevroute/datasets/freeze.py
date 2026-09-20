"""Frozen test-set mechanism: create and verify frozen test manifests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from jevroute.datasets.hasher import hash_example_ids, hash_file
from jevroute.datasets.models import FrozenTestManifest


def freeze_test_set(
    test_path: Path | str,
    dataset_version: str,
    manifest_dir: Path | str,
    frozen_by: str | None = None,
) -> FrozenTestManifest:
    """Create a frozen test manifest for the given test split file.

    Raises FileExistsError if a manifest already exists for this version
    (prevents accidental re-freezing).
    """
    test_path = Path(test_path)
    manifest_dir = Path(manifest_dir)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = manifest_dir / f"frozen_test_{dataset_version}.json"
    if manifest_path.exists():
        raise FileExistsError(
            f"Frozen test manifest already exists for version {dataset_version!r}: {manifest_path}"
        )

    test_hash = hash_file(test_path)
    example_ids: list[str] = []
    for line in test_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                r = json.loads(line)
                example_ids.append(r.get("example_id", ""))
            except json.JSONDecodeError:
                pass

    ids_hash = hash_example_ids(example_ids)

    manifest = FrozenTestManifest(
        dataset_version=dataset_version,
        test_hash=test_hash,
        example_count=len(example_ids),
        example_ids_hash=ids_hash,
        freeze_timestamp=datetime.now(timezone.utc).isoformat(),
        frozen_by=frozen_by,
    )

    manifest_path.write_text(
        json.dumps(manifest.model_dump(), indent=2), encoding="utf-8"
    )
    return manifest


def verify_test_set(
    test_path: Path | str,
    manifest_dir: Path | str,
    dataset_version: str,
) -> tuple[bool, str]:
    """Verify the test split against its frozen manifest.

    Returns (ok, reason). ok=True only if hashes match exactly.
    """
    test_path = Path(test_path)
    manifest_dir = Path(manifest_dir)
    manifest_path = manifest_dir / f"frozen_test_{dataset_version}.json"

    if not manifest_path.exists():
        return False, f"No frozen manifest for version {dataset_version!r}"

    manifest = FrozenTestManifest.model_validate(
        json.loads(manifest_path.read_text(encoding="utf-8"))
    )

    if not test_path.exists():
        return False, f"Test file not found: {test_path}"

    current_hash = hash_file(test_path)
    if current_hash != manifest.test_hash:
        return False, f"Test file hash mismatch (expected {manifest.test_hash[:16]}…, got {current_hash[:16]}…)"

    return True, "OK"
