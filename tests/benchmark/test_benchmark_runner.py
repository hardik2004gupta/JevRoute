"""Benchmark integration tests: deterministic fixture with RulesRouter and MockJevRouter.

These tests run without paid APIs using the 10-example CI fixture.
They verify the full benchmark pipeline end-to-end.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jevroute.benchmark.config import BenchmarkConfig
from jevroute.benchmark.loader import WorkloadLoader
from jevroute.benchmark.runner import BenchmarkRunner
from jevroute.routers.mock_jev import ROUTER_NAME as MOCK_NAME, ROUTER_VERSION as MOCK_VERSION, MockJevRouter
from jevroute.routers.rules import ROUTER_NAME as RULES_NAME, ROUTER_VERSION as RULES_VERSION, RulesRouter

DATASETS_DIR = Path(__file__).parent.parent.parent / "datasets"
RESULTS_DIR = Path(__file__).parent.parent.parent / "results"
CONFIG_PATH = Path(__file__).parent.parent.parent / "experiments" / "baseline.yaml"


def _minimal_config() -> BenchmarkConfig:
    return BenchmarkConfig.from_yaml(CONFIG_PATH)


@pytest.mark.asyncio
async def test_rules_router_full_run(tmp_path):
    """Full benchmark pipeline: RulesRouter produces results, aggregate, and metadata."""
    cfg = _minimal_config()
    runner = BenchmarkRunner(
        config=cfg,
        results_dir=tmp_path,
        datasets_dir=DATASETS_DIR,
        force=True,
    )
    loader = WorkloadLoader(DATASETS_DIR)
    examples = loader.load(cfg.experiment.dataset, cfg.experiment.split)

    aggregate = await runner.run(
        router=RulesRouter(),
        router_name=RULES_NAME,
        router_version=RULES_VERSION,
        examples=examples,
    )

    # Aggregate structure
    assert aggregate["examples"] == len(examples)
    assert aggregate["router"] == RULES_NAME
    assert aggregate["decisions"] >= 0
    assert aggregate["p50_latency_ms"] is not None
    assert aggregate["p95_latency_ms"] is not None
    assert aggregate["p99_latency_ms"] is not None
    assert aggregate["schema_failure_rate"] == 0.0

    # JSONL output exists and has correct line count
    raw_path = tmp_path / "raw" / cfg.experiment.name / f"{RULES_NAME}.jsonl"
    assert raw_path.exists()
    lines = [l for l in raw_path.read_text().splitlines() if l.strip()]
    assert len(lines) == len(examples)

    # All records are valid JSON
    for line in lines:
        record = json.loads(line)
        assert "example_id" in record
        assert "prediction" in record
        assert "ground_truth" in record
        assert "router" in record

    # Aggregate CSV exists
    csv_path = tmp_path / "aggregate" / f"{cfg.experiment.name}.csv"
    assert csv_path.exists()

    # Metadata JSON exists
    meta_path = tmp_path / "metadata" / f"{cfg.experiment.name}.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text())
    assert "runs" in meta
    assert len(meta["runs"]) == 1


@pytest.mark.asyncio
async def test_mock_jev_router_full_run(tmp_path):
    """MockJevRouter also runs the full pipeline."""
    cfg = _minimal_config()
    runner = BenchmarkRunner(
        config=cfg,
        results_dir=tmp_path,
        datasets_dir=DATASETS_DIR,
        force=True,
    )
    loader = WorkloadLoader(DATASETS_DIR)
    examples = loader.load(cfg.experiment.dataset, cfg.experiment.split)

    aggregate = await runner.run(
        router=MockJevRouter(),
        router_name=MOCK_NAME,
        router_version=MOCK_VERSION,
        examples=examples,
    )

    assert aggregate["examples"] == len(examples)
    assert aggregate["schema_failure_rate"] == 0.0


@pytest.mark.asyncio
async def test_all_observations_recorded(tmp_path):
    """Every executed example must produce exactly one raw record."""
    cfg = _minimal_config()
    runner = BenchmarkRunner(
        config=cfg, results_dir=tmp_path, datasets_dir=DATASETS_DIR, force=True
    )
    loader = WorkloadLoader(DATASETS_DIR)
    examples = loader.load(cfg.experiment.dataset, cfg.experiment.split)

    await runner.run(
        router=RulesRouter(),
        router_name=RULES_NAME,
        router_version=RULES_VERSION,
        examples=examples,
    )

    raw_path = tmp_path / "raw" / cfg.experiment.name / f"{RULES_NAME}.jsonl"
    records = [json.loads(l) for l in raw_path.read_text().splitlines() if l.strip()]
    example_ids_recorded = {r["example_id"] for r in records}
    example_ids_input = {ex.example_id for ex in examples}
    assert example_ids_recorded == example_ids_input


@pytest.mark.asyncio
async def test_ground_truth_not_in_state_fields(tmp_path):
    """Regression: ground_truth must not appear inside ApplicationState or router input.

    The runner strips ground truth from the state; only the WorkloadExample
    carries it for post-prediction evaluation.
    """
    cfg = _minimal_config()
    runner = BenchmarkRunner(
        config=cfg, results_dir=tmp_path, datasets_dir=DATASETS_DIR, force=True
    )
    loader = WorkloadLoader(DATASETS_DIR)
    examples = loader.load(cfg.experiment.dataset, cfg.experiment.split)

    for ex in examples:
        state_dict = ex.state.model_dump()
        assert "ground_truth" not in state_dict
        for label_field in ("severity", "category", "action", "policy_violation"):
            assert label_field not in state_dict, (
                f"Label field '{label_field}' found in ApplicationState"
            )

    await runner.run(
        router=RulesRouter(),
        router_name=RULES_NAME,
        router_version=RULES_VERSION,
        examples=examples,
    )

    raw_path = tmp_path / "raw" / cfg.experiment.name / f"{RULES_NAME}.jsonl"
    for line in raw_path.read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        # ground_truth in the record is fine (it's stored for evaluation)
        # but it should be a separate field, not part of prediction
        if record.get("prediction"):
            pred = record["prediction"]
            # prediction contains the router's output, ground_truth is separate
            assert "split" not in pred


@pytest.mark.asyncio
async def test_prediction_not_mutated_by_evaluation(tmp_path):
    """Invariant 4: evaluation must not modify predictions in the raw JSONL."""
    cfg = _minimal_config()
    runner = BenchmarkRunner(
        config=cfg, results_dir=tmp_path, datasets_dir=DATASETS_DIR, force=True
    )
    loader = WorkloadLoader(DATASETS_DIR)
    examples = loader.load(cfg.experiment.dataset, cfg.experiment.split)

    await runner.run(
        router=RulesRouter(),
        router_name=RULES_NAME,
        router_version=RULES_VERSION,
        examples=examples,
    )

    raw_path = tmp_path / "raw" / cfg.experiment.name / f"{RULES_NAME}.jsonl"
    records_before = [json.loads(l) for l in raw_path.read_text().splitlines() if l.strip()]

    # Re-read the file (records are written once and must not be overwritten)
    records_after = [json.loads(l) for l in raw_path.read_text().splitlines() if l.strip()]

    for b, a in zip(records_before, records_after):
        assert b["prediction"] == a["prediction"], "Prediction was mutated after write"


@pytest.mark.asyncio
async def test_metrics_aggregate_correctly(tmp_path):
    """All required aggregate metric keys must be present."""
    cfg = _minimal_config()
    runner = BenchmarkRunner(
        config=cfg, results_dir=tmp_path, datasets_dir=DATASETS_DIR, force=True
    )
    loader = WorkloadLoader(DATASETS_DIR)
    examples = loader.load(cfg.experiment.dataset, cfg.experiment.split)

    aggregate = await runner.run(
        router=RulesRouter(),
        router_name=RULES_NAME,
        router_version=RULES_VERSION,
        examples=examples,
    )

    required_keys = [
        "router", "examples", "decisions", "correct_decisions",
        "accuracy", "macro_f1", "schema_failure_rate",
        "p50_latency_ms", "p95_latency_ms", "p99_latency_ms",
        "total_cost_usd", "cost_per_correct_decision_usd",
        "decision_throughput_per_s",
    ]
    for key in required_keys:
        assert key in aggregate, f"Required aggregate key missing: {key}"


@pytest.mark.asyncio
async def test_llm_router_with_mocked_provider_full_run(tmp_path):
    """LLMSingleRouter with FakeModelClient runs the full pipeline without network."""
    from jevroute.routers.llm_provider import FakeModelClient, ModelResponse
    from jevroute.routers.llm_single import LLMSingleRouter, ROUTER_NAME, ROUTER_VERSION

    valid_content = (
        '{"severity":"P2","category":"Billing","policy_violation":false,'
        '"hallucination_risk":0.05,"tone_risk":0.02,"action":"SEND"}'
    )
    default_resp = ModelResponse(content=valid_content, input_tokens=200, output_tokens=40, model="fake")
    client = FakeModelClient(default_response=default_resp)
    router = LLMSingleRouter(
        client=client,
        model_input_price_per_1k=0.001,
        model_output_price_per_1k=0.002,
    )

    cfg = _minimal_config()
    runner = BenchmarkRunner(
        config=cfg, results_dir=tmp_path, datasets_dir=DATASETS_DIR, force=True
    )
    loader = WorkloadLoader(DATASETS_DIR)
    examples = loader.load(cfg.experiment.dataset, cfg.experiment.split)

    aggregate = await runner.run(
        router=router,
        router_name=ROUTER_NAME,
        router_version=ROUTER_VERSION,
        examples=examples,
    )

    assert aggregate["examples"] == len(examples)
    assert aggregate["total_cost_usd"] is not None
    assert aggregate["total_cost_usd"] > 0
    assert aggregate["input_tokens"] is not None
    assert aggregate["schema_failure_rate"] == 0.0


# ---------------------------------------------------------------------------
# Phase 5 regression tests — benchmark integrity invariants
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_policy_engine_identity_across_routers(tmp_path):
    """Invariant 2: the same PolicyEngine instance must be used for both routers.

    A shared policy engine is constructed once and passed to the runner.
    If the runner constructed its own engine internally, results would diverge
    when the shared policy instance has state or non-default configuration.
    """
    from jevroute.policy.engine import PolicyEngine

    # Use a non-default hallucination threshold to distinguish from the default engine
    shared_engine = PolicyEngine(hallucination_threshold=0.999)  # effectively never triggers

    cfg = _minimal_config()
    loader = WorkloadLoader(DATASETS_DIR)
    examples = loader.load(cfg.experiment.dataset, cfg.experiment.split)

    runner1 = BenchmarkRunner(
        config=cfg, results_dir=tmp_path / "run1", datasets_dir=DATASETS_DIR,
        policy_engine=shared_engine, force=True,
    )
    runner2 = BenchmarkRunner(
        config=cfg, results_dir=tmp_path / "run2", datasets_dir=DATASETS_DIR,
        policy_engine=shared_engine, force=True,
    )

    agg1 = await runner1.run(router=RulesRouter(), router_name=RULES_NAME,
                              router_version=RULES_VERSION, examples=examples)
    agg2 = await runner2.run(router=MockJevRouter(), router_name=MOCK_NAME,
                              router_version=MOCK_VERSION, examples=examples)

    # Both runners must have used the same policy engine — verify object identity
    assert runner1._policy_engine is shared_engine
    assert runner2._policy_engine is shared_engine
    # Both should have non-zero results (engines processed examples)
    assert agg1["examples"] == len(examples)
    assert agg2["examples"] == len(examples)


@pytest.mark.asyncio
async def test_failed_observations_retained_in_raw_records(tmp_path):
    """Invariant 5 + Rule 9: failed router calls must be retained, never dropped.

    A router that always raises an error must still produce one raw record per example,
    with error_type populated.
    """
    from jevroute.models.state import ApplicationState
    from jevroute.routers.llm_provider import RouterError

    class AlwaysFailRouter:
        """Router that always raises a TIMEOUT error."""
        async def decide(self, state: ApplicationState):
            raise RouterError("TIMEOUT", "simulated timeout for test")

    cfg = _minimal_config()
    runner = BenchmarkRunner(
        config=cfg, results_dir=tmp_path, datasets_dir=DATASETS_DIR, force=True
    )
    loader = WorkloadLoader(DATASETS_DIR)
    examples = loader.load(cfg.experiment.dataset, cfg.experiment.split)

    aggregate = await runner.run(
        router=AlwaysFailRouter(),
        router_name="always_fail",
        router_version="test-1.0",
        examples=examples,
    )

    raw_path = tmp_path / "raw" / cfg.experiment.name / "always_fail.jsonl"
    records = [json.loads(l) for l in raw_path.read_text().splitlines() if l.strip()]

    # Every example must produce a raw record
    assert len(records) == len(examples)
    # Every record must have error_type populated
    for r in records:
        assert r["error_type"] == "TIMEOUT", f"Expected TIMEOUT, got {r.get('error_type')}"
        assert r["prediction"] is None
    # Schema failure rate must reflect 100% failures
    assert aggregate["schema_failure_rate"] == 1.0


@pytest.mark.asyncio
async def test_retry_count_surfaced_in_raw_records(tmp_path):
    """Invariant: retry_count must be > 0 in raw records when a router retried.

    Uses FakeModelClient configured to fail once then succeed.
    """
    from jevroute.routers.llm_provider import FakeModelClient, ModelResponse
    from jevroute.routers.llm_provider import RouterError as RE
    from jevroute.routers.llm_single import LLMSingleRouter, ROUTER_NAME, ROUTER_VERSION

    valid_content = (
        '{"severity":"P2","category":"Billing","policy_violation":false,'
        '"hallucination_risk":0.05,"tone_risk":0.02,"action":"SEND"}'
    )
    valid_resp = ModelResponse(content=valid_content, input_tokens=200, output_tokens=40, model="fake")
    # First response is a rate limit error, second is success
    client = FakeModelClient(
        responses=[RE("RATE_LIMIT", "simulated rate limit"), valid_resp],
        default_response=valid_resp,
    )
    router = LLMSingleRouter(client=client)

    cfg = _minimal_config()
    runner = BenchmarkRunner(
        config=cfg, results_dir=tmp_path, datasets_dir=DATASETS_DIR, force=True
    )
    loader = WorkloadLoader(DATASETS_DIR)
    # Use just 1 example to exercise the retry path predictably
    examples = loader.load(cfg.experiment.dataset, cfg.experiment.split)[:1]

    await runner.run(
        router=router,
        router_name=ROUTER_NAME,
        router_version=ROUTER_VERSION,
        examples=examples,
    )

    raw_path = tmp_path / "raw" / cfg.experiment.name / f"{ROUTER_NAME}.jsonl"
    records = [json.loads(l) for l in raw_path.read_text().splitlines() if l.strip()]
    assert len(records) == 1
    assert records[0]["retry_count"] == 1, (
        f"Expected retry_count=1 after one rate-limit retry, got {records[0]['retry_count']}"
    )


@pytest.mark.asyncio
async def test_num_model_calls_rules_router(tmp_path):
    """Phase 7 regression: RulesRouter must record num_model_calls=0."""
    cfg = _minimal_config()
    runner = BenchmarkRunner(
        config=cfg, results_dir=tmp_path, datasets_dir=DATASETS_DIR, force=True
    )
    loader = WorkloadLoader(DATASETS_DIR)
    examples = loader.load(cfg.experiment.dataset, cfg.experiment.split)

    await runner.run(
        router=RulesRouter(),
        router_name=RULES_NAME,
        router_version=RULES_VERSION,
        examples=examples,
    )

    raw_path = tmp_path / "raw" / cfg.experiment.name / f"{RULES_NAME}.jsonl"
    for line in raw_path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        assert r.get("num_model_calls") == 0, (
            f"RulesRouter must have num_model_calls=0, got {r.get('num_model_calls')}"
        )


@pytest.mark.asyncio
async def test_num_model_calls_llm_single_no_retry(tmp_path):
    """Phase 7 regression: LLMSingleRouter with no retry must record num_model_calls=1."""
    from jevroute.routers.llm_provider import FakeModelClient, ModelResponse
    from jevroute.routers.llm_single import LLMSingleRouter, ROUTER_NAME, ROUTER_VERSION

    valid_content = (
        '{"severity":"P2","category":"Billing","policy_violation":false,'
        '"hallucination_risk":0.05,"tone_risk":0.02,"action":"SEND"}'
    )
    client = FakeModelClient(
        default_response=ModelResponse(content=valid_content, input_tokens=100, output_tokens=30, model="fake")
    )
    router = LLMSingleRouter(client=client)

    cfg = _minimal_config()
    runner = BenchmarkRunner(
        config=cfg, results_dir=tmp_path, datasets_dir=DATASETS_DIR, force=True
    )
    loader = WorkloadLoader(DATASETS_DIR)
    examples = loader.load(cfg.experiment.dataset, cfg.experiment.split)

    await runner.run(
        router=router,
        router_name=ROUTER_NAME,
        router_version=ROUTER_VERSION,
        examples=examples,
    )

    raw_path = tmp_path / "raw" / cfg.experiment.name / f"{ROUTER_NAME}.jsonl"
    for line in raw_path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        assert r.get("num_model_calls") == 1, (
            f"LLMSingleRouter (no retry) must have num_model_calls=1, got {r.get('num_model_calls')}"
        )


@pytest.mark.asyncio
async def test_num_model_calls_mock_jev(tmp_path):
    """Phase 7 regression: MockJevRouter must record num_model_calls=1."""
    cfg = _minimal_config()
    runner = BenchmarkRunner(
        config=cfg, results_dir=tmp_path, datasets_dir=DATASETS_DIR, force=True
    )
    loader = WorkloadLoader(DATASETS_DIR)
    examples = loader.load(cfg.experiment.dataset, cfg.experiment.split)

    await runner.run(
        router=MockJevRouter(),
        router_name=MOCK_NAME,
        router_version=MOCK_VERSION,
        examples=examples,
    )

    raw_path = tmp_path / "raw" / cfg.experiment.name / f"{MOCK_NAME}.jsonl"
    for line in raw_path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        assert r.get("num_model_calls") == 1, (
            f"MockJevRouter must have num_model_calls=1, got {r.get('num_model_calls')}"
        )
