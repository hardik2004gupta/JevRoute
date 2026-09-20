"""WorkloadLoader: loads and validates benchmark datasets.

Enforces strict separation between ApplicationState (router input) and
ground_truth (evaluation only). Ground truth must never reach router prompts.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, field_validator

from jevroute.models.state import ApplicationState

logger = logging.getLogger(__name__)

SUPPORTED_SPLITS = frozenset({"train", "validation", "test"})


class GroundTruth(BaseModel):
    """Ground truth labels for one example.

    Kept entirely separate from ApplicationState.
    Must never be passed to a router during inference.
    """

    severity: str
    category: str
    policy_violation: bool
    hallucination_risk: float
    tone_risk: float
    action: str

    @field_validator("hallucination_risk", "tone_risk")
    @classmethod
    def _validate_probability(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"Probability must be in [0, 1], got {v}")
        return v


class WorkloadExample(BaseModel):
    """A single benchmark example: state for the router + ground truth for evaluation."""

    state: ApplicationState
    ground_truth: GroundTruth
    metadata: dict[str, Any] = {}

    @property
    def example_id(self) -> str:
        return self.state.example_id


class WorkloadLoader:
    """Loads JSONL benchmark datasets.

    Ground truth is retained internally and returned alongside the state only
    for evaluation purposes. It must never be injected into ApplicationState.
    """

    def __init__(self, datasets_dir: Path | str) -> None:
        self._datasets_dir = Path(datasets_dir)

    def load(self, dataset_name: str, split: str) -> list[WorkloadExample]:
        """Load examples for a given dataset name and split.

        Args:
            dataset_name: Name of the dataset file (without .jsonl extension).
            split: One of 'train', 'validation', 'test'.

        Returns:
            List of WorkloadExample with state and ground_truth kept separate.
        """
        if split not in SUPPORTED_SPLITS:
            raise ValueError(
                f"Invalid split '{split}'. Supported: {sorted(SUPPORTED_SPLITS)}"
            )

        # Try split-specific subdirectory first, then root datasets dir
        candidate_paths = [
            self._datasets_dir / split / f"{dataset_name}.jsonl",
            self._datasets_dir / f"{dataset_name}_{split}.jsonl",
            self._datasets_dir / f"{dataset_name}.jsonl",
        ]

        jsonl_path: Path | None = None
        for p in candidate_paths:
            if p.exists():
                jsonl_path = p
                break

        if jsonl_path is None:
            raise FileNotFoundError(
                f"Dataset '{dataset_name}' split '{split}' not found. "
                f"Tried: {[str(p) for p in candidate_paths]}"
            )

        examples = self._parse_jsonl(jsonl_path, split)
        logger.info(
            "Loaded %d examples from %s (split=%s)", len(examples), jsonl_path, split
        )
        return examples

    def _parse_jsonl(self, path: Path, split: str) -> list[WorkloadExample]:
        examples: list[WorkloadExample] = []
        errors: list[str] = []

        with path.open("r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                    example = self._parse_row(raw, split)
                    if example is not None:
                        examples.append(example)
                except Exception as exc:
                    errors.append(f"Line {lineno}: {exc}")

        if errors:
            raise ValueError(
                f"Dataset parse errors in {path}:\n" + "\n".join(errors[:10])
            )

        return examples

    def _parse_row(self, raw: dict[str, Any], split: str) -> WorkloadExample | None:
        """Parse one JSONL row into a WorkloadExample.

        If the row has a 'split' field and it does not match, skip the row.
        Ground truth is extracted and kept separate from ApplicationState.
        """
        row_split = raw.get("split")
        if row_split is not None and row_split != split:
            return None

        # Extract ground truth BEFORE constructing ApplicationState.
        # This ensures ground_truth can never accidentally leak into the state object.
        gt_raw = raw.get("ground_truth")
        if gt_raw is None:
            raise ValueError(f"Missing 'ground_truth' in row: {raw.get('example_id', '?')}")

        ground_truth = GroundTruth.model_validate(gt_raw)

        # ApplicationState receives only the fields it is supposed to have.
        # Any 'ground_truth' or 'split' key is explicitly excluded.
        state = ApplicationState(
            example_id=raw["example_id"],
            customer_tier=raw["customer_tier"],
            product=raw["product"],
            region=raw["region"],
            ticket_subject=raw["ticket_subject"],
            ticket_body=raw["ticket_body"],
            draft_reply=raw["draft_reply"],
        )

        metadata = {
            k: v
            for k, v in raw.items()
            if k not in (
                "example_id",
                "customer_tier",
                "product",
                "region",
                "ticket_subject",
                "ticket_body",
                "draft_reply",
                "ground_truth",
                "split",
            )
        }

        return WorkloadExample(
            state=state,
            ground_truth=ground_truth,
            metadata=metadata,
        )
