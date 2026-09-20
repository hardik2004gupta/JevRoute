# JevRoute — Phased Execution Plan

Four implementation phases after Phase 0. Each phase must end with passing tests, git diff inspection, and a documentation update.

---

## Phase 0 — Contract + Structure (CURRENT)

**Objective:** Establish engineering contract, audit repository, produce planning documents, and scaffold directory structure.

**Deliverables:**
- `CLAUDE.md`
- `docs/IMPLEMENTATION_MAP.md`
- `docs/PHASE_PLAN.md`
- `docs/OPEN_QUESTIONS.md`
- High-level directory scaffold

**Out of scope:** Any production code, real API integration, benchmark execution.

---

## Phase 1 — Foundation + UI Shell

**Objective:** Implement all domain models, the router interface, the policy engine, the dataset loader, and a static UI shell. No real API calls yet.

**Scope:**
- Domain models: `ApplicationState`, `DecisionResult`, enums, `ConfidenceOutput`, error categories
- `DecisionRouter` Protocol (base interface)
- `MockJevRouter` (deterministic, for CI)
- `PolicyEngine` (shared, router-independent)
- `WorkloadLoader` (train/validation/test splits, test-label guard)
- `BenchmarkConfig` (YAML loading, Pydantic Settings)
- `.env.example`
- `pyproject.toml` with all declared dependencies
- Static dashboard HTML shell (light research-instrument visual direction, no fake data)
- 10-example synthetic fixture in `tests/fixtures/`
- FastAPI app skeleton (endpoints stubbed, not wired)

**Files likely to change:**
```
src/jevroute/models/state.py
src/jevroute/models/decision.py
src/jevroute/models/errors.py
src/jevroute/routers/base.py
src/jevroute/routers/mock_jev.py
src/jevroute/policy/engine.py
src/jevroute/benchmark/config.py
src/jevroute/benchmark/loader.py
src/jevroute/config/settings.py
src/jevroute/api/main.py
dashboard/index.html
tests/fixtures/support_fixture.jsonl
tests/unit/test_state.py
tests/unit/test_decision.py
tests/unit/test_policy_engine.py
tests/unit/test_loader.py
pyproject.toml
.env.example
```

**Dependencies:** Phase 0 complete.

**Tests:**
- All unit tests for models, policy engine, loader, config pass.
- `MockJevRouter.decide()` returns a valid `DecisionResult`.
- Policy engine produces correct `Action` for known inputs.

**Acceptance criteria:**
- `pytest tests/unit/` passes with zero failures.
- `MockJevRouter` does not require any external API call.
- Dashboard shell renders without errors (no fake data).
- `pyproject.toml` declares all dependencies.

**Out of scope:**
- Real LLM calls
- Real Jev API calls
- Benchmark runner execution
- Evaluation metrics
- Results storage

---

## Phase 2 — Benchmark Engine

**Objective:** Build the full benchmark execution pipeline: `RulesRouter`, `LLMSingleRouter`, `LLMParallelRouter`, `BenchmarkRunner`, `ResultRecorder`, and all evaluation modules.

**Scope:**
- `RulesRouter` (keyword/regex rules, tuned on train/validation data)
- `LLMSingleRouter` (single structured-output LLM call, full token accounting)
- `LLMParallelRouter` (async concurrent per-decision LLM calls, aggregate cost + wall-clock latency)
- `BenchmarkRunner` (router-agnostic, configurable concurrency, records raw JSONL)
- `ResultRecorder` (append-only JSONL, immutable records)
- Evaluation modules: `quality.py`, `latency.py`, `cost.py`, `calibration.py`, `throughput.py`, `schema_validator.py`
- Experiment configs: `experiments/baseline.yaml`
- FastAPI endpoints wired to runner and results
- Integration tests for runner + routers

**Files likely to change:**
```
src/jevroute/routers/rules.py
src/jevroute/routers/llm_single.py
src/jevroute/routers/llm_parallel.py
src/jevroute/benchmark/runner.py
src/jevroute/benchmark/recorder.py
src/jevroute/evaluation/quality.py
src/jevroute/evaluation/latency.py
src/jevroute/evaluation/cost.py
src/jevroute/evaluation/calibration.py
src/jevroute/evaluation/throughput.py
src/jevroute/evaluation/schema_validator.py
src/jevroute/api/routes/benchmark.py
src/jevroute/api/routes/results.py
experiments/baseline.yaml
tests/integration/test_runner.py
tests/benchmark/test_benchmark_fixture.py
```

**Dependencies:** Phase 1 complete.

**Tests:**
- Benchmark fixture test: all three non-Jev routers run against 10-example fixture.
- Results normalize to the same schema.
- Metrics aggregate correctly (accuracy, p50/p95/p99, cost/correct decision, throughput).
- Schema failures are recorded (not dropped).
- `LLMParallelRouter` aggregate cost == sum of individual call costs.
- `perf_counter()` is used for all duration calculations.

**Acceptance criteria:**
- `pytest tests/` passes.
- Benchmark runner produces valid JSONL output.
- Failed LLM calls produce failure records, not silent drops.
- Token accounting is complete for all LLM calls.
- `cost_per_correct_decision_usd` is computed correctly.

**Out of scope:**
- Jev API integration
- Decision scaling experiment
- Fast-path experiment
- Dashboard data wiring

---

## Phase 3 — Jev + Experiments

**Objective:** Implement `JevRouter` (real Jev API adapter), all experiment runners, and run the baseline comparison experiment.

**Scope:**
- `JevRouter`: full adapter (ApplicationState → Jev API → DecisionResult), handles all failure modes (timeout, rate limit, auth failure, malformed response, retry, cancellation)
- Every outcome logged
- Jev configuration versioning (`jev_schema_version`)
- Fast-gate layer (deterministic pre-gate for fast-path experiment)
- Experiment runners / scripts for:
  - `baseline-v1`: all four systems compared
  - `scaling-v1`: 2→4→6→8→12 decisions
  - `fastpath-v1`: Always-Jev vs Fast-Gate+Jev
  - `context-v1`: minimal vs rich routing state
- Results in `results/raw/` and `results/aggregate/`
- `matplotlib` figures: Intelligence Cost Curve, baseline latency, baseline cost

**Files likely to change:**
```
src/jevroute/routers/jev.py
src/jevroute/benchmark/fast_gate.py
experiments/baseline.yaml
experiments/scaling.yaml
experiments/fast_path.yaml
experiments/context_scaling.yaml
experiments/dependency.yaml
tests/unit/test_jev_router.py
tests/integration/test_jev_adapter.py
results/raw/baseline-v1/
results/aggregate/baseline-v1.csv
results/figures/
```

**Dependencies:** Phase 2 complete. Jev API credentials available.

**Tests:**
- `JevRouter` handles all failure modes without silent drops.
- Retries are bounded and recorded.
- `MockJevRouter` still works and produces consistent fixture results.
- Baseline experiment produces valid aggregate CSV.

**Acceptance criteria:**
- All four systems run against the same test dataset.
- Raw JSONL files exist for each system.
- Aggregate CSV contains all required fields.
- Intelligence Cost Curve figure exists.
- `MockJevRouter` never appears in published results.
- Reproducibility bundle (config + commit SHA + results) is complete.

**Out of scope:**
- Dashboard data wiring
- Shadow oracle (V2)
- Multi-domain extension (V2)

---

## Phase 4 — Research Observatory / Final Dashboard

**Objective:** Wire benchmark results to the dashboard, produce final experiment reports, and complete the research-grade README.

**Scope:**
- Dashboard wired to real result files (no fake data)
- All required panels: system comparison, Intelligence Cost Curve, Quality × Cost Frontier, Control-Plane Economics, Reliability
- Fields not available for a router displayed as `N/A`
- Benchmark status (run complete / pending / failed)
- Experiment history panel
- Research-style README with methodology, results, limitations, conclusions
- Dataset protocol documentation
- Reproduction instructions
- Statistical reporting (sample size, median, p95, confidence intervals where appropriate)

**Files likely to change:**
```
dashboard/index.html
dashboard/ (JS/CSS)
README.md
docs/methodology.md
docs/dataset_protocol.md
docs/limitations.md
results/aggregate/
```

**Dependencies:** Phase 3 complete, at least baseline + scaling experiments executed.

**Tests:**
- Dashboard renders with real data, no JS errors.
- No hardcoded "performance claim" numbers.
- All N/A fields display correctly.
- README includes reproduction instructions that work from a clean checkout.

**Acceptance criteria:**
- Every dashboard number traces to a result file.
- README is research-grade (setup, methodology, results, limitations, conclusions).
- Reproduction instructions verified.
- All prior phases' tests still pass.

**Out of scope:**
- V2 extensions (RouteLLM, multi-domain, shadow oracle, production simulation)
- Production deployment
- Adaptive policies

---

## V2 Boundary (after MVP)

V2 extensions may be added through adapters without changing the core benchmark interface:
- `RouteLLMRouter`
- `BedrockRouter`
- `OpenRouterRouter`
- Traditional ML classifier router
- Additional workload domains
- Shadow oracle experiment
- Production trace replay
- Adaptive policies
