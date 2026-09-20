# JevRoute — Artifact Manifest

Documents every artifact in the repository: its type (source / derived / CI-only / research-published), its status, and its role in the benchmark.

---

## Source Artifacts (committed to version control)

### Core Implementation

| Path | Role | Status |
|------|------|--------|
| `src/jevroute/models/` | Domain types: ApplicationState, DecisionResult, enums | Source, stable |
| `src/jevroute/policy/engine.py` | Shared PolicyEngine — router-independent | Source, stable |
| `src/jevroute/routers/base.py` | DecisionRouter Protocol | Source, stable |
| `src/jevroute/routers/rules.py` | Deterministic rules baseline | Source, stable |
| `src/jevroute/routers/llm_single.py` | LLM single-call router | Source, stable |
| `src/jevroute/routers/llm_parallel.py` | LLM parallel 6-call router | Source, stable |
| `src/jevroute/routers/jev.py` | JevRouter adapter | Source, stable (OQ-001 pending) |
| `src/jevroute/routers/jev_client.py` | JevClient Protocol + HttpxJevClient + FakeJevClient | Source, stable |
| `src/jevroute/routers/mock_jev.py` | MockJevRouter (CI/dev only) | Source, CI only |
| `src/jevroute/routers/llm_provider.py` | ModelClient + FakeModelClient | Source, stable |
| `src/jevroute/benchmark/runner.py` | Router-agnostic benchmark runner | Source, stable |
| `src/jevroute/benchmark/recorder.py` | JSONL result recorder | Source, stable |
| `src/jevroute/benchmark/loader.py` | Workload loader with label isolation | Source, stable |
| `src/jevroute/benchmark/config.py` | BenchmarkConfig YAML parser | Source, stable |
| `src/jevroute/evaluation/quality.py` | Accuracy, F1, safety rates | Source, stable |
| `src/jevroute/evaluation/latency.py` | p50/p95/p99, mean latency | Source, stable |
| `src/jevroute/evaluation/cost.py` | Cost/correct, cost/1K | Source, stable |
| `src/jevroute/evaluation/throughput.py` | Decision throughput | Source, stable |
| `src/jevroute/evaluation/calibration.py` | Brier score, ECE | Source, stable |
| `src/jevroute/experiments/fast_path.py` | FastGate deterministic bypass | Source, stable |
| `src/jevroute/experiments/e2e.py` | SimulatedGeneration + e2e metrics | Source, stable (simulated) |
| `src/jevroute/api/app.py` | FastAPI research observatory API | Source, stable |
| `src/jevroute/api/models.py` | API request/response models | Source, stable |
| `src/jevroute/config/settings.py` | Pydantic settings (env vars) | Source, stable |

### Experiment Configurations (YAML)

| Path | Experiment | Status |
|------|-----------|--------|
| `experiments/baseline.yaml` | baseline-v1 | Source, stable |
| `experiments/scaling.yaml` | scaling-v1 | Source, stable |
| `experiments/fast_path.yaml` | fastpath-v1 | Source, stable |
| `experiments/context_scaling.yaml` | context-v1 | Source, stable |
| `experiments/dependency.yaml` | dependency-v1 | Source, stable |
| `experiments/e2e.yaml` | e2e-v1 | Source, stable |

### Datasets

| Path | Content | Status |
|------|---------|--------|
| `datasets/test/benchmark_fixture.jsonl` | 10-example CI fixture | Source, frozen (CI only) |
| `datasets/train/benchmark_fixture.jsonl` | CI fixture train split | Source, CI only |
| `datasets/validation/benchmark_fixture.jsonl` | CI fixture validation split | Source, CI only |
| `datasets/manifests/ci_fixture_v0.1.0.json` | CI fixture provenance manifest | Source, Phase 7 |

**Note:** The full 1,000–2,000 example research dataset does not yet exist. See [docs/DATASET.md](DATASET.md) and OQ-003.

### Dataset Infrastructure (Phase 7)

| Path | Role | Status |
|------|------|--------|
| `src/jevroute/datasets/models.py` | SourceType, GroundTruth, DatasetExample, DatasetManifest, FrozenTestManifest, ValidationReport | Source, stable |
| `src/jevroute/datasets/hasher.py` | SHA-256 hashing for files, record sets, example IDs | Source, stable |
| `src/jevroute/datasets/validator.py` | Schema/enum/probability/duplicate/leakage validation | Source, stable |
| `src/jevroute/datasets/splitter.py` | Deterministic 70/15/15 split, seed=42 | Source, stable |
| `src/jevroute/datasets/freeze.py` | Frozen test manifest creation and verification | Source, stable |
| `src/jevroute/datasets/quality.py` | Quality report generator (JSON + CSV) | Source, stable |
| `src/jevroute/datasets/cli.py` | Dataset CLI: validate, inspect, hash, status, quality | Source, stable |

### Provider Readiness Infrastructure (Phase 7)

| Path | Role | Status |
|------|------|--------|
| `src/jevroute/readiness/providers.py` | Per-provider readiness checks (Jev, LLM, generation, dataset) | Source, stable |
| `src/jevroute/readiness/preflight.py` | Benchmark preflight: hard gate before any run | Source, stable |

### Tests

| Path | Role | Status |
|------|------|--------|
| `tests/unit/` | Unit tests — all modules | Source, 157 tests passing |
| `tests/unit/test_datasets.py` | Dataset models, validator, splitter, freeze, leakage (30 tests) | Source, Phase 7 |
| `tests/unit/test_readiness.py` | Provider readiness and preflight (17 tests) | Source, Phase 7 |
| `tests/integration/` | API integration tests | Source, stable |
| `tests/benchmark/` | End-to-end benchmark pipeline tests (includes num_model_calls regression) | Source, stable |
| `tests/fixtures/` | Tiny fixtures for CI | Source, CI only |

---

## Derived Artifacts (generated by benchmark runs; not committed)

| Path | Content | Generated by | Immutable after run? |
|------|---------|-------------|---------------------|
| `results/raw/<exp_id>/<router>.jsonl` | Raw per-example observations | `ResultRecorder` | YES (force=False) |
| `results/aggregate/<exp_id>.csv` | One row per router per run | `_persist_aggregate()` in runner | NO (overwritten each run of same experiment) |
| `results/metadata/<exp_id>.json` | Run metadata, git SHA, env | `_persist_metadata()` in runner | NO (appended each run) |

**Important:** Raw JSONL files are immutable after completion (FileExistsError by default). Aggregate CSV and metadata JSON are updated on each new run.

---

## Current Result Artifacts (present in repository after Phase 2 run)

| Path | Routers | Examples | Date |
|------|---------|----------|------|
| `results/raw/baseline-v1/rules.jsonl` | rules | 10 | 2026-09-20 |
| `results/raw/baseline-v1/mock_jev.jsonl` | mock_jev | 10 | 2026-09-20 |
| `results/aggregate/baseline-v1.csv` | rules, mock_jev | 10 | 2026-09-20 |
| `results/metadata/baseline-v1.json` | rules, mock_jev | 10 | 2026-09-20 |

**These are CI fixture results — not the final research benchmark.**

---

## Documentation Artifacts

| Path | Role | Status |
|------|------|--------|
| `CLAUDE.md` | Strict engineering contract (Level 1) | Authoritative |
| `JevRoute_MVP_Technical_Architecture.md` | Strict technical contract (Level 1) | Authoritative |
| `JevRoute_Project_Documentation.md` | Research context (Level 2) | Reference |
| `README.md` | Project overview, quick start | Current |
| `docs/PHASE_PLAN.md` | Phase definitions | Reference |
| `docs/IMPLEMENTATION_MAP.md` | Module map | Reference |
| `docs/OPEN_QUESTIONS.md` | OQ registry with resolutions | Current |
| `docs/DATASET.md` | Dataset protocol | Current |
| `docs/PHASE5_AUDIT.md` | Contract compliance audit | Current |
| `docs/REPRODUCTION.md` | Reproduction guide | Current |
| `docs/ARTIFACT_MANIFEST.md` | This file | Current (Phase 8) |
| `docs/JEV_API.md` | Jev API contract (with UNKNOWN fields) | Current (Phase 7) |
| `results/RESULT_STATUS.json` | Machine-readable experiment status | Current (Phase 8) |
| `results/READINESS.json` | Live-runnable preflight snapshot | Current (Phase 8) |
| `reports/FINAL_MVP_REPORT.md` | Research report | Current |

---

## Temporary / CI-Only Artifacts

| Path | Role | Keep? |
|------|------|-------|
| `tests/fixtures/` | Small deterministic test data | YES (CI) |
| `src/jevroute/routers/mock_jev.py` | Mock router for CI | YES (CI only, never in research results) |
| `src/jevroute/routers/jev_client.py::FakeJevClient` | Fake Jev client for CI | YES (CI only) |
| `src/jevroute/routers/llm_provider.py::FakeModelClient` | Fake LLM client for CI | YES (CI only) |

---

## Data Source Lineage

```
dashboard (display only)
    └── API (GET /api/v1/experiments/{id}/metrics)
          └── results/aggregate/{experiment_id}.csv
                └── BenchmarkRunner._compute_aggregate()
                      └── evaluation/{quality,latency,cost,throughput,calibration}.py
                            └── results/raw/{experiment_id}/{router}.jsonl
                                  └── BenchmarkRunner._execute_example()
                                        └── router.decide(state)
                                              └── ApplicationState (no ground_truth)
                                              └── PolicyEngine.apply(result)
```

Every number shown in the dashboard is traceable to this chain.
