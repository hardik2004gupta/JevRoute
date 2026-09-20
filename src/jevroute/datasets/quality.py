"""Dataset quality report generation."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from jevroute.datasets.hasher import hash_file
from jevroute.datasets.validator import check_split_leakage, validate_dataset


def generate_quality_report(
    dataset_dir: Path | str,
    output_dir: Path | str,
    dataset_stem: str = "benchmark_fixture",
) -> dict[str, Any]:
    """Generate dataset_quality.json and dataset_quality.csv.

    Validates all three splits (train/validation/test) and checks for leakage.
    Returns the report dict.
    """
    dataset_dir = Path(dataset_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    test_path = dataset_dir / "test" / f"{dataset_stem}.jsonl"
    train_path = dataset_dir / "train" / f"{dataset_stem}.jsonl"
    val_path = dataset_dir / "validation" / f"{dataset_stem}.jsonl"

    splits: dict[str, Any] = {}
    for split_name, path in [("test", test_path), ("train", train_path), ("validation", val_path)]:
        report = validate_dataset(path)
        file_hash = hash_file(path) if path.exists() else None
        splits[split_name] = {
            "path": str(path),
            "exists": path.exists(),
            "file_hash": file_hash,
            "record_count": report.record_count,
            "missing_field_count": report.missing_field_count,
            "invalid_enum_count": report.invalid_enum_count,
            "probability_out_of_range_count": report.probability_out_of_range_count,
            "empty_text_count": report.empty_text_count,
            "duplicate_id_count": report.duplicate_id_count,
            "duplicate_record_count": report.duplicate_record_count,
            "missing_ground_truth_count": report.missing_ground_truth_count,
            "errors": report.errors,
            "warnings": report.warnings,
            "gate_passed": report.gate_passed,
        }

    leakage = check_split_leakage(train_path, val_path, test_path)

    benchmark_gate = (
        splits.get("test", {}).get("gate_passed", False)
        and not leakage["leakage_detected"]
    )

    report = {
        "_schema": "jevroute-dataset-quality-v1",
        "dataset_stem": dataset_stem,
        "splits": splits,
        "split_leakage": leakage,
        "benchmark_gate": "PASS" if benchmark_gate else "BLOCKED",
        "benchmark_gate_reason": None if benchmark_gate else (
            "Test set leakage detected" if leakage["leakage_detected"]
            else "Test split validation errors"
        ),
    }

    (output_dir / "dataset_quality.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    rows: list[dict[str, Any]] = []
    for split_name, s in splits.items():
        rows.append({
            "split": split_name,
            "record_count": s["record_count"],
            "gate_passed": s["gate_passed"],
            "missing_fields": s["missing_field_count"],
            "invalid_enums": s["invalid_enum_count"],
            "prob_oor": s["probability_out_of_range_count"],
            "empty_text": s["empty_text_count"],
            "dup_ids": s["duplicate_id_count"],
            "dup_records": s["duplicate_record_count"],
            "missing_gt": s["missing_ground_truth_count"],
            "error_count": len(s["errors"]),
        })

    with (output_dir / "dataset_quality.csv").open("w", newline="", encoding="utf-8") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    return report
