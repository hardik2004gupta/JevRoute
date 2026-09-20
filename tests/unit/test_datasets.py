"""Tests for dataset infrastructure: models, validator, splitter, freeze, hashing."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from jevroute.datasets.hasher import hash_example_ids, hash_file, hash_records
from jevroute.datasets.models import (
    DatasetExample,
    FrozenTestManifest,
    GroundTruth,
    SourceType,
    ValidationReport,
)
from jevroute.datasets.splitter import split_dataset, write_splits
from jevroute.datasets.validator import check_split_leakage, validate_dataset


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(
    example_id: str = "ex-001",
    subject: str = "Test subject",
    body: str = "Test body text",
    reply: str = "Test reply text",
    severity: str = "P2",
    category: str = "Bug",
    action: str = "SEND",
) -> dict:
    return {
        "example_id": example_id,
        "customer_tier": "Gold",
        "product": "API",
        "region": "US",
        "ticket_subject": subject,
        "ticket_body": body,
        "draft_reply": reply,
        "ground_truth": {
            "severity": severity,
            "category": category,
            "policy_violation": False,
            "hallucination_risk": 0.1,
            "tone_risk": 0.2,
            "action": action,
        },
    }


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")


# ---------------------------------------------------------------------------
# GroundTruth validation
# ---------------------------------------------------------------------------

def test_ground_truth_valid():
    gt = GroundTruth(
        severity="P1", category="Billing", policy_violation=True,
        hallucination_risk=0.5, tone_risk=0.0, action="HOLD",
    )
    assert gt.severity == "P1"


def test_ground_truth_invalid_severity():
    with pytest.raises(Exception):
        GroundTruth(
            severity="P9", category="Bug", policy_violation=False,
            hallucination_risk=0.0, tone_risk=0.0, action="SEND",
        )


def test_ground_truth_invalid_action():
    with pytest.raises(Exception):
        GroundTruth(
            severity="P2", category="Bug", policy_violation=False,
            hallucination_risk=0.0, tone_risk=0.0, action="IGNORE",
        )


def test_ground_truth_prob_out_of_range():
    with pytest.raises(Exception):
        GroundTruth(
            severity="P2", category="Bug", policy_violation=False,
            hallucination_risk=1.5, tone_risk=0.0, action="SEND",
        )


# ---------------------------------------------------------------------------
# DatasetExample validation
# ---------------------------------------------------------------------------

def test_dataset_example_roundtrip():
    r = _make_record()
    ex = DatasetExample.model_validate(r)
    assert ex.example_id == "ex-001"
    assert ex.ground_truth.severity == "P2"


# ---------------------------------------------------------------------------
# Hasher
# ---------------------------------------------------------------------------

def test_hash_file_deterministic(tmp_path):
    f = tmp_path / "data.jsonl"
    f.write_bytes(b"hello world")
    h1 = hash_file(f)
    h2 = hash_file(f)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_hash_file_changes_with_content(tmp_path):
    f = tmp_path / "data.jsonl"
    f.write_bytes(b"aaa")
    h1 = hash_file(f)
    f.write_bytes(b"bbb")
    h2 = hash_file(f)
    assert h1 != h2


def test_hash_records_deterministic():
    records = [{"a": 1}, {"b": 2}]
    assert hash_records(records) == hash_records(records)


def test_hash_example_ids_deterministic():
    ids = ["ex-003", "ex-001", "ex-002"]
    h1 = hash_example_ids(ids)
    h2 = hash_example_ids(ids)
    assert h1 == h2
    assert len(h1) == 64


# ---------------------------------------------------------------------------
# Validator — happy path
# ---------------------------------------------------------------------------

def test_validate_dataset_valid(tmp_path):
    records = [_make_record(f"ex-{i:03d}") for i in range(5)]
    path = tmp_path / "ds.jsonl"
    _write_jsonl(path, records)
    report = validate_dataset(path)
    assert report.record_count == 5
    assert report.gate_passed is True
    assert report.duplicate_id_count == 0
    assert report.missing_field_count == 0


def test_validate_dataset_missing_file():
    report = validate_dataset(Path("/nonexistent/dataset.jsonl"))
    assert report.gate_passed is False
    assert report.record_count == 0
    assert any("not found" in e for e in report.errors)


# ---------------------------------------------------------------------------
# Validator — error cases
# ---------------------------------------------------------------------------

def test_validate_duplicate_ids(tmp_path):
    records = [_make_record("dup-001"), _make_record("dup-001"), _make_record("ex-003")]
    path = tmp_path / "ds.jsonl"
    _write_jsonl(path, records)
    report = validate_dataset(path)
    assert report.duplicate_id_count == 1
    assert report.gate_passed is False


def test_validate_invalid_severity(tmp_path):
    r = _make_record()
    r["ground_truth"]["severity"] = "P9"
    path = tmp_path / "ds.jsonl"
    _write_jsonl(path, [r])
    report = validate_dataset(path)
    assert report.invalid_enum_count >= 1
    assert report.gate_passed is False


def test_validate_invalid_category(tmp_path):
    r = _make_record()
    r["ground_truth"]["category"] = "Unknown"
    path = tmp_path / "ds.jsonl"
    _write_jsonl(path, [r])
    report = validate_dataset(path)
    assert report.invalid_enum_count >= 1
    assert report.gate_passed is False


def test_validate_prob_out_of_range(tmp_path):
    r = _make_record()
    r["ground_truth"]["hallucination_risk"] = 1.5
    path = tmp_path / "ds.jsonl"
    _write_jsonl(path, [r])
    report = validate_dataset(path)
    assert report.probability_out_of_range_count >= 1
    assert report.gate_passed is False


def test_validate_missing_ground_truth(tmp_path):
    r = _make_record()
    del r["ground_truth"]
    path = tmp_path / "ds.jsonl"
    _write_jsonl(path, [r])
    report = validate_dataset(path)
    assert report.missing_ground_truth_count == 1
    assert report.gate_passed is False


def test_validate_duplicate_content(tmp_path):
    r = _make_record("ex-001")
    r2 = _make_record("ex-002")  # different ID but same content → warning only
    path = tmp_path / "ds.jsonl"
    _write_jsonl(path, [r, r2])
    report = validate_dataset(path)
    assert report.duplicate_record_count >= 1
    # Content dup is a warning, not an error → gate may still pass
    assert len(report.warnings) >= 1


# ---------------------------------------------------------------------------
# Splitter
# ---------------------------------------------------------------------------

def test_split_dataset_sizes():
    records = list(range(100))
    train, val, test = split_dataset(records, train_frac=0.70, validation_frac=0.15, seed=42)
    assert len(train) == 70
    assert len(val) == 15
    assert len(test) == 15
    assert len(train) + len(val) + len(test) == 100


def test_split_dataset_deterministic():
    records = list(range(50))
    t1, v1, s1 = split_dataset(records, seed=42)
    t2, v2, s2 = split_dataset(records, seed=42)
    assert t1 == t2
    assert s1 == s2


def test_split_dataset_no_overlap():
    records = list(range(30))
    train, val, test = split_dataset(records, seed=7)
    assert set(train) & set(test) == set()
    assert set(val) & set(test) == set()


def test_write_splits_creates_files(tmp_path):
    records = [_make_record(f"ex-{i:03d}") for i in range(20)]
    train, val, test = split_dataset(records, seed=42)
    write_splits(train, val, test, out_dir=tmp_path, stem="my_dataset")
    assert (tmp_path / "train" / "my_dataset.jsonl").exists()
    assert (tmp_path / "validation" / "my_dataset.jsonl").exists()
    assert (tmp_path / "test" / "my_dataset.jsonl").exists()


def test_write_splits_refuses_overwrite(tmp_path):
    records = [_make_record(f"ex-{i:03d}") for i in range(10)]
    train, val, test = split_dataset(records, seed=42)
    write_splits(train, val, test, out_dir=tmp_path, stem="ds")
    with pytest.raises(FileExistsError):
        write_splits(train, val, test, out_dir=tmp_path, stem="ds")


# ---------------------------------------------------------------------------
# Freeze
# ---------------------------------------------------------------------------

def test_freeze_and_verify(tmp_path):
    from jevroute.datasets.freeze import freeze_test_set, verify_test_set

    records = [_make_record(f"ex-{i:03d}") for i in range(5)]
    test_path = tmp_path / "test" / "ds.jsonl"
    _write_jsonl(test_path, records)

    manifest_dir = tmp_path / "manifests"
    manifest = freeze_test_set(test_path, "v0.1.0", manifest_dir, frozen_by="test")
    assert manifest.example_count == 5
    assert len(manifest.test_hash) == 64

    ok, reason = verify_test_set(test_path, manifest_dir, "v0.1.0")
    assert ok is True
    assert reason == "OK"


def test_freeze_refuses_double_freeze(tmp_path):
    from jevroute.datasets.freeze import freeze_test_set

    records = [_make_record(f"ex-{i:03d}") for i in range(3)]
    test_path = tmp_path / "test" / "ds.jsonl"
    _write_jsonl(test_path, records)
    manifest_dir = tmp_path / "manifests"
    freeze_test_set(test_path, "v0.1.0", manifest_dir)
    with pytest.raises(FileExistsError):
        freeze_test_set(test_path, "v0.1.0", manifest_dir)


def test_verify_detects_tampered_file(tmp_path):
    from jevroute.datasets.freeze import freeze_test_set, verify_test_set

    records = [_make_record(f"ex-{i:03d}") for i in range(3)]
    test_path = tmp_path / "test" / "ds.jsonl"
    _write_jsonl(test_path, records)
    manifest_dir = tmp_path / "manifests"
    freeze_test_set(test_path, "v1.0", manifest_dir)

    # Tamper
    test_path.write_text("tampered content", encoding="utf-8")
    ok, reason = verify_test_set(test_path, manifest_dir, "v1.0")
    assert ok is False
    assert "mismatch" in reason


# ---------------------------------------------------------------------------
# Leakage check
# ---------------------------------------------------------------------------

def test_no_leakage(tmp_path):
    train = [_make_record(f"ex-{i:03d}") for i in range(0, 7)]
    val = [_make_record(f"ex-{i:03d}") for i in range(7, 9)]
    test = [_make_record(f"ex-{i:03d}") for i in range(9, 12)]

    train_p = tmp_path / "train" / "ds.jsonl"
    val_p = tmp_path / "validation" / "ds.jsonl"
    test_p = tmp_path / "test" / "ds.jsonl"
    _write_jsonl(train_p, train)
    _write_jsonl(val_p, val)
    _write_jsonl(test_p, test)

    result = check_split_leakage(train_p, val_p, test_p)
    assert result["leakage_detected"] is False
    assert result["train_test_overlap"] == []
    assert result["validation_test_overlap"] == []


def test_leakage_detected(tmp_path):
    # ex-001 appears in both train and test
    train = [_make_record("ex-001"), _make_record("ex-002")]
    val = [_make_record("ex-003")]
    test = [_make_record("ex-001"), _make_record("ex-004")]

    train_p = tmp_path / "train" / "ds.jsonl"
    val_p = tmp_path / "validation" / "ds.jsonl"
    test_p = tmp_path / "test" / "ds.jsonl"
    _write_jsonl(train_p, train)
    _write_jsonl(val_p, val)
    _write_jsonl(test_p, test)

    result = check_split_leakage(train_p, val_p, test_p)
    assert result["leakage_detected"] is True
    assert "ex-001" in result["train_test_overlap"]
