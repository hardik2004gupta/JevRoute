"""Deterministic train/validation/test splitter for benchmark datasets."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Sequence


def split_dataset(
    records: Sequence[dict],
    train_frac: float = 0.70,
    validation_frac: float = 0.15,
    seed: int = 42,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Split records into train, validation, test using a fixed seed.

    test_frac = 1 - train_frac - validation_frac

    Returns (train, validation, test) lists.
    """
    if not (0.0 < train_frac < 1.0):
        raise ValueError(f"train_frac must be in (0, 1): {train_frac}")
    if not (0.0 < validation_frac < 1.0):
        raise ValueError(f"validation_frac must be in (0, 1): {validation_frac}")
    if train_frac + validation_frac >= 1.0:
        raise ValueError("train_frac + validation_frac must be < 1.0")

    shuffled = list(records)
    rng = random.Random(seed)
    rng.shuffle(shuffled)

    n = len(shuffled)
    n_train = int(n * train_frac)
    n_val = int(n * validation_frac)

    train = shuffled[:n_train]
    validation = shuffled[n_train : n_train + n_val]
    test = shuffled[n_train + n_val :]

    return train, validation, test


def write_splits(
    train: list[dict],
    validation: list[dict],
    test: list[dict],
    out_dir: Path | str,
    stem: str,
) -> dict[str, Path]:
    """Write split JSONL files; raise FileExistsError if they already exist."""
    out_dir = Path(out_dir)
    paths = {
        "train": out_dir / "train" / f"{stem}.jsonl",
        "validation": out_dir / "validation" / f"{stem}.jsonl",
        "test": out_dir / "test" / f"{stem}.jsonl",
    }
    for split_name, path in paths.items():
        if path.exists():
            raise FileExistsError(
                f"Split file already exists: {path}. "
                "Use a new dataset version rather than overwriting an existing split."
            )

    for split_name, (path, records) in {
        "train": (paths["train"], train),
        "validation": (paths["validation"], validation),
        "test": (paths["test"], test),
    }.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

    return paths
