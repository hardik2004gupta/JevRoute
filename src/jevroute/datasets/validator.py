"""Dataset validator: schema, enum, probability, duplicate, and leakage checks."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from jevroute.datasets.models import ValidationReport

logger = logging.getLogger(__name__)

_REQUIRED_STATE_FIELDS = {
    "example_id", "customer_tier", "product", "region",
    "ticket_subject", "ticket_body", "draft_reply",
}
_REQUIRED_GT_FIELDS = {
    "severity", "category", "policy_violation",
    "hallucination_risk", "tone_risk", "action",
}
_VALID_SEVERITY = {"P1", "P2", "P3", "P4"}
_VALID_CATEGORY = {"Billing", "Bug", "Feature", "Account", "Other"}
_VALID_ACTION = {"SEND", "HOLD", "ESCALATE"}


def validate_dataset(path: Path | str) -> ValidationReport:
    """Run all quality checks on a JSONL dataset file.

    Returns a ValidationReport. gate_passed=True only if no critical errors.
    """
    path = Path(path)
    errors: list[str] = []
    warnings: list[str] = []

    if not path.exists():
        return ValidationReport(
            dataset_path=str(path),
            record_count=0,
            missing_field_count=0,
            invalid_enum_count=0,
            probability_out_of_range_count=0,
            empty_text_count=0,
            duplicate_id_count=0,
            duplicate_record_count=0,
            missing_ground_truth_count=0,
            errors=[f"File not found: {path}"],
            warnings=[],
            gate_passed=False,
        )

    records: list[dict[str, Any]] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            errors.append(f"Row {i+1}: JSON decode error: {exc}")

    n = len(records)
    missing_field_count = 0
    invalid_enum_count = 0
    prob_oor = 0
    empty_text = 0
    missing_gt = 0

    seen_ids: set[str] = set()
    dup_ids: set[str] = set()
    seen_hashes: set[str] = set()
    dup_record_count = 0

    import hashlib

    for i, r in enumerate(records):
        row_label = f"Row {i+1} ({r.get('example_id', '?')})"

        # State fields
        for f in _REQUIRED_STATE_FIELDS:
            if f not in r or r[f] is None:
                missing_field_count += 1
                errors.append(f"{row_label}: missing required field '{f}'")

        # Ground truth
        gt = r.get("ground_truth")
        if gt is None:
            missing_gt += 1
            errors.append(f"{row_label}: missing ground_truth")
        else:
            for f in _REQUIRED_GT_FIELDS:
                if f not in gt or gt[f] is None:
                    missing_field_count += 1
                    errors.append(f"{row_label}: missing ground_truth.{f}")

            sev = gt.get("severity", "")
            if sev not in _VALID_SEVERITY:
                invalid_enum_count += 1
                errors.append(f"{row_label}: invalid severity {sev!r}")

            cat = gt.get("category", "")
            if cat not in _VALID_CATEGORY:
                invalid_enum_count += 1
                errors.append(f"{row_label}: invalid category {cat!r}")

            act = gt.get("action", "")
            if act not in _VALID_ACTION:
                invalid_enum_count += 1
                errors.append(f"{row_label}: invalid action {act!r}")

            for prob_field in ("hallucination_risk", "tone_risk"):
                val = gt.get(prob_field)
                if val is not None:
                    try:
                        v = float(val)
                        if not (0.0 <= v <= 1.0):
                            prob_oor += 1
                            errors.append(f"{row_label}: {prob_field}={v} out of [0,1]")
                    except (TypeError, ValueError):
                        prob_oor += 1
                        errors.append(f"{row_label}: {prob_field} not numeric")

        # Empty text check
        for text_field in ("ticket_subject", "ticket_body", "draft_reply"):
            val = r.get(text_field, "")
            if not val or not str(val).strip():
                empty_text += 1
                warnings.append(f"{row_label}: empty or blank '{text_field}'")

        # Duplicate ID check
        eid = r.get("example_id", "")
        if eid in seen_ids:
            dup_ids.add(eid)
        else:
            seen_ids.add(eid)

        # Duplicate record check (hash of key fields)
        body = json.dumps({
            "ticket_subject": r.get("ticket_subject", ""),
            "ticket_body": r.get("ticket_body", ""),
            "draft_reply": r.get("draft_reply", ""),
        }, sort_keys=True)
        h = hashlib.sha256(body.encode()).hexdigest()
        if h in seen_hashes:
            dup_record_count += 1
            warnings.append(f"{row_label}: duplicate content detected")
        else:
            seen_hashes.add(h)

    dup_id_count = len(dup_ids)
    if dup_id_count:
        for eid in sorted(dup_ids):
            errors.append(f"Duplicate example_id: {eid!r}")

    if dup_record_count:
        warnings.append(f"{dup_record_count} duplicate content record(s) detected")

    # Critical gate: any errors block benchmark
    gate_passed = (
        len(errors) == 0
        and missing_gt == 0
        and missing_field_count == 0
        and invalid_enum_count == 0
        and dup_id_count == 0
    )

    return ValidationReport(
        dataset_path=str(path),
        record_count=n,
        missing_field_count=missing_field_count,
        invalid_enum_count=invalid_enum_count,
        probability_out_of_range_count=prob_oor,
        empty_text_count=empty_text,
        duplicate_id_count=dup_id_count,
        duplicate_record_count=dup_record_count,
        missing_ground_truth_count=missing_gt,
        errors=errors,
        warnings=warnings,
        gate_passed=gate_passed,
    )


def check_split_leakage(
    train_path: Path | str,
    validation_path: Path | str,
    test_path: Path | str,
) -> dict[str, Any]:
    """Check for example_id overlap across splits. Returns a leakage report."""

    def _load_ids(p: Path) -> set[str]:
        if not p.exists():
            return set()
        ids = set()
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    r = json.loads(line)
                    ids.add(r.get("example_id", ""))
                except json.JSONDecodeError:
                    pass
        return ids

    train_ids = _load_ids(Path(train_path))
    val_ids = _load_ids(Path(validation_path))
    test_ids = _load_ids(Path(test_path))

    train_test = train_ids & test_ids
    val_test = val_ids & test_ids
    train_val = train_ids & val_ids

    leakage_detected = bool(train_test or val_test)

    return {
        "train_test_overlap": sorted(train_test),
        "validation_test_overlap": sorted(val_test),
        "train_validation_overlap": sorted(train_val),
        "leakage_detected": leakage_detected,
        "train_count": len(train_ids),
        "validation_count": len(val_ids),
        "test_count": len(test_ids),
    }
