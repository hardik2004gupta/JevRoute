"""Unit tests: WorkloadLoader strict separation of state and ground truth."""

from __future__ import annotations

from pathlib import Path

import pytest

from jevroute.benchmark.loader import WorkloadLoader


DATASETS_DIR = Path(__file__).parent.parent.parent / "datasets"


def test_loader_loads_test_split():
    loader = WorkloadLoader(DATASETS_DIR)
    examples = loader.load("benchmark_fixture", "test")
    assert len(examples) == 10


def test_loader_loads_train_split():
    loader = WorkloadLoader(DATASETS_DIR)
    examples = loader.load("benchmark_fixture", "train")
    assert len(examples) == 4


def test_loader_loads_validation_split():
    loader = WorkloadLoader(DATASETS_DIR)
    examples = loader.load("benchmark_fixture", "validation")
    assert len(examples) == 3


def test_loader_state_has_no_ground_truth():
    """ApplicationState must not contain ground_truth field."""
    loader = WorkloadLoader(DATASETS_DIR)
    examples = loader.load("benchmark_fixture", "test")
    for ex in examples:
        state = ex.state
        assert not hasattr(state, "ground_truth"), "ground_truth must not be on ApplicationState"
        state_dict = state.model_dump()
        assert "ground_truth" not in state_dict, "ground_truth leaked into ApplicationState dict"


def test_no_test_labels_in_state_fields():
    """Test labels (severity, category, action) must not appear in ApplicationState."""
    loader = WorkloadLoader(DATASETS_DIR)
    examples = loader.load("benchmark_fixture", "test")
    for ex in examples:
        state_dict = ex.state.model_dump()
        for label_field in ("severity", "category", "action", "policy_violation"):
            assert label_field not in state_dict, (
                f"Label field '{label_field}' found in ApplicationState for {ex.example_id}"
            )


def test_ground_truth_stays_separate():
    """Ground truth values are accessible only through WorkloadExample.ground_truth."""
    loader = WorkloadLoader(DATASETS_DIR)
    examples = loader.load("benchmark_fixture", "test")
    for ex in examples:
        assert ex.ground_truth.severity in ("P1", "P2", "P3", "P4")
        assert ex.ground_truth.action in ("SEND", "HOLD", "ESCALATE")


def test_loader_invalid_split_raises():
    loader = WorkloadLoader(DATASETS_DIR)
    with pytest.raises(ValueError, match="Invalid split"):
        loader.load("benchmark_fixture", "bogus_split")


def test_loader_missing_dataset_raises():
    loader = WorkloadLoader(DATASETS_DIR)
    with pytest.raises(FileNotFoundError):
        loader.load("nonexistent_dataset", "test")
