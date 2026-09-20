# JevRoute — Implementation Map

Maps specification components to repository files and tests.
This is a planning document. It does not replace the technical architecture contract.

---

## Domain Models

| Specification Concept | Repository File | Tests |
|---|---|---|
| `ApplicationState` | `src/jevroute/models/state.py` | `tests/unit/test_state.py` |
| `DecisionResult` | `src/jevroute/models/decision.py` | `tests/unit/test_decision.py` |
| `Severity` enum (P1–P4) | `src/jevroute/models/decision.py` | `tests/unit/test_decision.py` |
| `Category` enum | `src/jevroute/models/decision.py` | `tests/unit/test_decision.py` |
| `Action` enum (SEND/HOLD/ESCALATE) | `src/jevroute/models/decision.py` | `tests/unit/test_decision.py` |
| `ConfidenceOutput` | `src/jevroute/models/decision.py` | `tests/unit/test_decision.py` |
| `RouterError` / error categories | `src/jevroute/models/errors.py` | `tests/unit/test_errors.py` |

---

## Router Abstraction

| Specification Concept | Repository File | Tests |
|---|---|---|
| `DecisionRouter` Protocol | `src/jevroute/routers/base.py` | `tests/unit/test_router_base.py` |
| `RulesRouter` | `src/jevroute/routers/rules.py` | `tests/unit/test_rules_router.py` |
| `LLMSingleRouter` | `src/jevroute/routers/llm_single.py` | `tests/unit/test_llm_single_router.py` |
| `LLMParallelRouter` | `src/jevroute/routers/llm_parallel.py` | `tests/unit/test_llm_parallel_router.py` |
| `JevRouter` | `src/jevroute/routers/jev.py` | `tests/unit/test_jev_router.py` |
| `MockJevRouter` | `src/jevroute/routers/mock_jev.py` | `tests/unit/test_mock_jev.py` |

---

## Policy Engine

| Specification Concept | Repository File | Tests |
|---|---|---|
| `PolicyEngine.apply_policy()` | `src/jevroute/policy/engine.py` | `tests/unit/test_policy_engine.py` |
| Policy versioning (`policy_version`) | `src/jevroute/policy/engine.py` | `tests/unit/test_policy_engine.py` |

---

## Benchmark Runner

| Specification Concept | Repository File | Tests |
|---|---|---|
| `BenchmarkRunner` | `src/jevroute/benchmark/runner.py` | `tests/integration/test_runner.py` |
| `ResultRecorder` / raw JSONL writer | `src/jevroute/benchmark/recorder.py` | `tests/unit/test_recorder.py` |
| `BenchmarkConfig` / YAML loading | `src/jevroute/benchmark/config.py` | `tests/unit/test_config.py` |
| `WorkloadLoader` (train/val/test splits) | `src/jevroute/benchmark/loader.py` | `tests/unit/test_loader.py` |

---

## Evaluation

| Specification Concept | Repository File | Tests |
|---|---|---|
| Quality metrics (accuracy, F1, confusion matrix) | `src/jevroute/evaluation/quality.py` | `tests/unit/test_quality.py` |
| Latency metrics (p50/p95/p99) | `src/jevroute/evaluation/latency.py` | `tests/unit/test_latency.py` |
| Cost accounting (centralized, per-token) | `src/jevroute/evaluation/cost.py` | `tests/unit/test_cost.py` |
| Calibration (Brier, ECE) | `src/jevroute/evaluation/calibration.py` | `tests/unit/test_calibration.py` |
| Throughput (decisions/s) | `src/jevroute/evaluation/throughput.py` | `tests/unit/test_throughput.py` |
| Schema validator | `src/jevroute/evaluation/schema_validator.py` | `tests/unit/test_schema_validator.py` |

---

## Experiments

| Specification Concept | Repository File |
|---|---|
| Baseline comparison config | `experiments/baseline.yaml` |
| Decision scaling config | `experiments/scaling.yaml` |
| Fast-path experiment config | `experiments/fast_path.yaml` |
| Context scaling config | `experiments/context_scaling.yaml` |
| Dependency experiment config | `experiments/dependency.yaml` |
| End-to-end experiment config | `experiments/end_to_end.yaml` |

---

## Result Storage

| Specification Concept | Repository Path |
|---|---|
| Raw JSONL (per router per experiment) | `results/raw/<experiment-id>/<router>.jsonl` |
| Aggregate CSV | `results/aggregate/<experiment-id>.csv` |
| Experiment metadata JSON | `results/aggregate/<experiment-id>_meta.json` |
| Figures | `results/figures/` |

---

## Datasets

| Specification Concept | Repository Path |
|---|---|
| Raw source data | `datasets/raw/` |
| Processed examples | `datasets/processed/` |
| Training split | `datasets/train/` |
| Validation split | `datasets/validation/` |
| Test split (frozen) | `datasets/test/` |

---

## FastAPI

| Specification Concept | Repository File |
|---|---|
| API app entry point | `src/jevroute/api/main.py` |
| Benchmark trigger endpoint | `src/jevroute/api/routes/benchmark.py` |
| Results endpoint | `src/jevroute/api/routes/results.py` |
| Config endpoint | `src/jevroute/api/routes/config.py` |

---

## Dashboard

| Specification Concept | Repository Path |
|---|---|
| Dashboard entry point | `dashboard/index.html` |
| Benchmark comparison panel | `dashboard/` |
| Intelligence Cost Curve visualization | `dashboard/` |
| Quality × Cost Frontier | `dashboard/` |
| Control-Plane Economics panel | `dashboard/` |
| Reliability panel | `dashboard/` |

---

## Tests

| Test Category | Repository Path |
|---|---|
| Unit tests | `tests/unit/` |
| Integration tests | `tests/integration/` |
| Benchmark validation tests (10-example fixture) | `tests/benchmark/` |
| Synthetic fixtures | `tests/fixtures/` |

---

## Configuration

| Specification Concept | Repository File |
|---|---|
| Environment variables template | `.env.example` |
| Package definition | `pyproject.toml` |
| Settings model (Pydantic Settings) | `src/jevroute/config/settings.py` |

---

## Key Invariant Enforcement Points

| Invariant | Enforced in |
|---|---|
| One state → one DecisionResult | `routers/base.py` (Protocol), `models/decision.py` |
| Policy engine is router-independent | `policy/engine.py` (no router imports) |
| Test labels never enter router prompts | `benchmark/loader.py` (split guard) |
| Evaluation code never modifies predictions | `evaluation/*.py` (read-only) |
| Raw records are immutable | `benchmark/recorder.py` (append-only JSONL) |
| All router costs are observable | `models/decision.py` (required cost fields) |

---

## Raw Benchmark Record Fields

Per `JevRoute_MVP_Technical_Architecture.md` §14:

```
experiment_id, run_id, example_id, router, router_version,
decision_schema_version, started_at, router_latency_ms,
total_latency_ms, input_tokens, output_tokens, estimated_cost_usd,
schema_valid, prediction (full DecisionResult), ground_truth
```

---

## Aggregate Output Fields

Per §39:

```
router, examples, decisions, correct_decisions, accuracy,
macro_f1, p50_latency_ms, p95_latency_ms, p99_latency_ms,
input_tokens, output_tokens, total_cost_usd,
cost_per_correct_decision_usd, decision_throughput,
schema_failure_rate, brier_score, ece
```

Fields unavailable for a router: `null` or `N/A`.
