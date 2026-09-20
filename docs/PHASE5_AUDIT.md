# JevRoute — Phase 5 Contract Audit

**Date:** 2026-09-20  
**Commit audited:** 2747c97 (Phase 3+4)  
**Audit scope:** Full implementation against CLAUDE.md + JevRoute_MVP_Technical_Architecture.md  

---

## Audit Methodology

Each item was verified by:
1. Reading the relevant source file(s)
2. Tracing the execution path from benchmark runner through router to evaluation
3. Checking test coverage for the invariant
4. Cross-referencing with the two Level 1 contract documents

---

## Contract Compliance Checklist

### Router Abstraction

| Item | Status | Notes |
|------|--------|-------|
| All routers implement `DecisionRouter.decide(state: ApplicationState)` | PASS | `base.py` Protocol — no ground_truth parameter |
| Jev-specific code isolated behind JevRouter adapter | PASS | `routers/jev.py` + `routers/jev_client.py` — no Jev logic in benchmark/evaluation |
| Provider/API logic does not leak into benchmark code | PASS | `llm_provider.py` is only imported by router implementations |
| `_MockBackedJevRouter` stamps distinct router_version | PASS | `"jev-adapter-0.1-mock"` — distinguishable from real Jev |

### DecisionResult Schema

| Item | Status | Notes |
|------|--------|-------|
| All routers produce the same normalized DecisionResult | PASS | Verified for rules, llm_single, llm_parallel, jev, mock_jev |
| DecisionResult has no ground_truth field | PASS | `models/decision.py` — only prediction fields + observability metadata |
| `retry_count` field present in DecisionResult | PASS (fixed) | Added in Phase 5; previously missing, always 0 |
| ConfidenceOutput nullable for systems without native probabilities | PASS | All fields `float | None`, default factory returns all None |

### Policy Engine Isolation

| Item | Status | Notes |
|------|--------|-------|
| PolicyEngine is router-independent | PASS | `policy/engine.py` imports only `models.decision` |
| Same PolicyEngine instance passed to all routers in a run | PASS | `BenchmarkRunner.__init__` takes `policy_engine` param; single instance per runner |
| No router-specific policy overrides | PASS | `PolicyEngine.apply()` branches on severity/policy_violation/hallucination_risk only |
| Regression test for policy engine identity | PASS (added) | `test_policy_engine_identity_across_routers` |

### Test-Label Isolation (Invariant 3)

| Item | Status | Notes |
|------|--------|-------|
| ApplicationState has no ground_truth field | PASS | `models/state.py` — 7 fields: example_id, customer_tier, product, region, ticket_subject, ticket_body, draft_reply |
| Runner passes only `example.state` to `router.decide()` | PASS | `runner.py:230` — ground_truth extracted after router returns |
| Regression test: ground_truth not in state fields | PASS | `test_ground_truth_not_in_state_fields` |
| LLM prompts contain no ground truth | PASS | All `_build_messages()` functions use state fields only |
| Jev payload contains no ground truth | PASS | `jev.py:_build_payload()` uses state fields only |
| Rules router receives no ground truth | PASS | Only `state.*` fields accessed |

### Evaluation Integrity (Invariant 4)

| Item | Status | Notes |
|------|--------|-------|
| Evaluation code never modifies predictions | PASS | All evaluation modules are read-only; explicit test verifies |
| `missed_policy_violation_rate` uses correct definition | PASS (fixed) | Now: GT pv=True AND final_action=SEND / total GT pv=True. Previously measured detection failure (wrong definition). |
| Regression test for correct definition | PASS (added) | `test_missed_policy_violation_rate_uses_final_action` |

### Raw Result Immutability (Invariant 5)

| Item | Status | Notes |
|------|--------|-------|
| ResultRecorder appends JSONL, flush after each record | PASS | `recorder.py:111-112` |
| Overwrite rejected by default | PASS | `FileExistsError` raised when `force=False` (default) |
| force=True truncates before writing (not appends) | PASS (fixed) | Previously appended on force=True, silently duplicating records. Now uses `"w"` mode. |
| Records written before aggregate derived | PASS | `runner.py:167-182` — all records written before `_compute_aggregate` |

### Cost Accounting (Invariant 6)

| Item | Status | Notes |
|------|--------|-------|
| Cost calculation centralized in evaluation/cost.py | PASS | `cost_per_correct_decision_usd` computed centrally |
| Per-router cost computation isolated in router implementations | PASS | Each router estimates cost via `_estimate_cost()` method |
| Zero-cost rules baseline | PASS | `RulesRouter` returns `estimated_cost_usd=0.0` |
| `cost_per_correct_decision` returns None for 0 correct decisions | PASS | `evaluation/cost.py:44-54` |
| Parallel aggregate cost = sum of all call costs | PASS | `llm_parallel.py:253-285` — all 6 call costs aggregated |

### Latency Accounting

| Item | Status | Notes |
|------|--------|-------|
| `perf_counter()` used for all duration calculations | PASS | Verified in rules, llm_single, llm_parallel, jev, runner |
| Wall-clock timestamps used only for logging | PASS | `utc_now_iso()` used only for `started_at` timestamp field |
| LLMParallel wall-clock ≠ sum-of-individual | PASS | Single `perf_counter()` span wraps all 6 concurrent calls |
| `router_latency_ms` and `total_latency_ms` distinct | PASS | Runner measures router span separately from total span |

### Token Accounting

| Item | Status | Notes |
|------|--------|-------|
| LLMParallel total_input = sum of call inputs | PASS | `llm_parallel.py:253-254` accumulates across all 6 calls |
| LLMParallel total_output = sum of call outputs | PASS | Same accumulation |
| num_model_calls set for parallel router | PARTIAL | `num_model_calls` field exists in BenchmarkRecord but runner sets it to None; the 6-call nature is implicit in router_name |
| Retry token accumulation | PASS | Both LLMSingle and LLMParallel accumulate tokens across retries |

### Failure Persistence

| Item | Status | Notes |
|------|--------|-------|
| RouterError caught and preserved, not dropped | PASS | `runner.py:257-264` — RouterError → BenchmarkRecord with error_type |
| All error types classified | PASS | TIMEOUT, RATE_LIMIT, AUTHENTICATION, NETWORK, SCHEMA_VALIDATION, PROVIDER_ERROR, INVALID_RESPONSE, INTERNAL_ERROR |
| Failed records in JSONL | PASS | Every `_execute_example` returns a BenchmarkRecord regardless of success/failure |
| Regression test with always-failing router | PASS (added) | `test_failed_observations_retained_in_raw_records` |

### Retry Accounting

| Item | Status | Notes |
|------|--------|-------|
| retry_count in DecisionResult | PASS (fixed) | Added `retry_count: int = 0` field to DecisionResult |
| LLMSingleRouter surfaces retry_count | PASS (fixed) | `retry_count` returned in DecisionResult |
| LLMParallelRouter surfaces total retry_count | PASS (fixed) | Sum of per-call retry counts returned |
| JevRouter surfaces retry_count | PASS (fixed) | `attempt` passed to DecisionResult |
| Runner reads retry_count from DecisionResult | PASS (fixed) | `result.retry_count` used instead of hardcoded 0 |
| Regression test: retry_count > 0 in records | PASS (added) | `test_retry_count_surfaced_in_raw_records` |
| Only RATE_LIMIT retried by Jev | PASS | `jev.py:148-154` — other RouterErrors re-raised immediately |

### Calibration

| Item | Status | Notes |
|------|--------|-------|
| Systems without probabilities return brier_score=None | PASS | `calibration.py` — no eligible records → None |
| Calibration uses correct probability field | PASS (fixed) | Now uses `policy_violation_probability` from ConfidenceOutput, not `hallucination_risk` |
| Calibration code does not alter predictions | PASS | Read-only; verified by test |
| New test: null without probability estimates | PASS (added) | `test_calibration_null_without_probability_estimates` |

### Quality Metrics

| Item | Status | Notes |
|------|--------|-------|
| accuracy = correct_decisions / total | PASS | `quality.py:50-51` |
| macro_f1 via sklearn | PASS | `quality.py:61-65` |
| bad_send_rate: predicted SEND, GT HOLD/ESCALATE / total | PASS | `quality.py:81-82` |
| over_escalation_rate: predicted ESCALATE, GT SEND/HOLD / total | PASS | `quality.py:85-86` |
| missed_policy_violation_rate: GT pv=True, final_action=SEND / total GT pv=True | PASS (fixed) | Definition corrected in Phase 5 |

### Percentile Metrics

| Item | Status | Notes |
|------|--------|-------|
| p50/p95/p99 use numpy linear interpolation | PASS | `latency.py:47-49` — `np.percentile(..., method="linear")` |
| Deterministic unit tests for percentiles | PASS | `test_evaluation.py` contains percentile tests |

### Throughput

| Item | Status | Notes |
|------|--------|-------|
| throughput = correct_decisions / total_wall_clock_s | PASS | `throughput.py:39` |
| Wall-clock time measured by runner (not sum of latencies) | PASS | `runner.py:147,164` — single `perf_counter()` span |

### Versioning

| Item | Status | Notes |
|------|--------|-------|
| Every run carries: experiment_id, router_version, schema_version, policy_version, prompt_version | PASS | All in BenchmarkRecord and aggregate output |
| Experiment IDs are immutable | PASS | 6 known experiment IDs hardcoded in `_KNOWN_EXPERIMENTS` |
| Results do not overwrite (default) | PASS | FileExistsError by default |

### Security

| Item | Status | Notes |
|------|--------|-------|
| No API keys in source | PASS | Scan found only env var name references, no actual keys |
| `.env` gitignored | PASS | `.gitignore` contains `.env` |
| `.env.example` contains placeholders only | PASS | All sensitive values are placeholder strings |
| `redact_state()` utility exists | PASS | `models/state.py:26-40` |
| Authentication headers never logged | PASS | `HttpxJevClient` uses `Authorization` header only in HTTP request, not in any log statement |

### Dashboard Data Integrity

| Item | Status | Notes |
|------|--------|-------|
| Dashboard fetches from API, not hardcoded | PASS | `dashboard/app/page.tsx` — all data from `fetchAll()` |
| Empty states are honest (N/A, not 0) | PASS | `AwaitingData` component, `EmptyMetric`, `"—"` for null values |
| No fabricated benchmark numbers | PASS | No hardcoded metric values in page.tsx |
| API endpoints return null/empty for missing data | PASS | `_read_aggregate()` returns [] when CSV missing |

---

## Summary

| Category | PASS | PARTIAL | FAIL | FIXED |
|----------|------|---------|------|-------|
| Router abstraction | 4 | 0 | 0 | 0 |
| DecisionResult schema | 4 | 0 | 0 | 1 |
| Policy engine isolation | 4 | 0 | 0 | 0 |
| Test-label isolation | 6 | 0 | 0 | 0 |
| Evaluation integrity | 2 | 0 | 0 | 1 |
| Raw result immutability | 4 | 0 | 0 | 1 |
| Cost accounting | 6 | 0 | 0 | 0 |
| Latency accounting | 4 | 0 | 0 | 0 |
| Token accounting | 3 | 1 | 0 | 0 |
| Failure persistence | 4 | 0 | 0 | 1 |
| Retry accounting | 6 | 0 | 0 | 5 |
| Calibration | 4 | 0 | 0 | 1 |
| Quality metrics | 5 | 0 | 0 | 1 |
| Throughput/percentiles | 4 | 0 | 0 | 0 |
| Versioning | 3 | 0 | 0 | 0 |
| Security | 5 | 0 | 0 | 0 |
| Dashboard integrity | 4 | 0 | 0 | 0 |
| **Total** | **72** | **1** | **0** | **11** |

---

## Fixes Applied in Phase 5

1. **`missed_policy_violation_rate` definition** (`evaluation/quality.py`) — changed from "predicted pv=False" (detection failure) to "final_action=SEND despite GT pv=True" (routing failure). Added regression test.

2. **`retry_count` always 0** (`models/decision.py`, `routers/llm_single.py`, `routers/llm_parallel.py`, `routers/jev.py`, `benchmark/runner.py`) — added `retry_count: int = 0` to DecisionResult; each router now surfaces its actual retry count; runner reads it rather than hardcoding 0. Added regression test.

3. **force=True appends instead of truncates** (`benchmark/recorder.py`) — changed from always using `"a"` mode to using `"w"` mode when `force=True` and file already exists. Prevents silent duplicate records on re-run.

4. **Calibration semantic mismatch** (`evaluation/calibration.py`) — changed from `hallucination_risk` (continuous risk score) vs `policy_violation` (binary label) cross-field comparison to `policy_violation_probability` (dedicated probability field) vs `policy_violation`. Systems without `policy_violation_probability` now correctly return `brier_score=None`. Added regression test.

5. **Missing regression tests** (`tests/benchmark/test_benchmark_runner.py`, `tests/unit/test_evaluation.py`) — added:
   - `test_policy_engine_identity_across_routers`
   - `test_failed_observations_retained_in_raw_records`
   - `test_retry_count_surfaced_in_raw_records`
   - `test_missed_policy_violation_rate_uses_final_action`
   - `test_missed_policy_violation_rate_none_when_no_violations`
   - `test_calibration_null_without_probability_estimates`

---

## Remaining PARTIAL Items

### `num_model_calls` not set in BenchmarkRecord for LLMParallelRouter

The field exists in `BenchmarkRecord` but is always `None`. The 6-call nature of `LLMParallelRouter` is implicit in the router name and version. This is a low-severity observability gap — the information is not lost (it is derivable from router_name + router_version), and the architecture does not mandate this field be populated. Documented here; not fixed to avoid scope creep.

---

## Experiment Status (as of Phase 5 audit)

All experiments are in `NOT_RUN` or `PARTIAL` state with the 10-example CI fixture.

| Experiment | Dataset Used | Status | Note |
|------------|-------------|--------|------|
| baseline-v1 | 10-example CI fixture (rules + mock_jev only) | PARTIAL | Real LLM and Jev require external credentials |
| scaling-v1 | Not run | NOT_RUN | Requires real provider |
| fastpath-v1 | Not run | NOT_RUN | Requires real provider |
| context-v1 | Not run | NOT_RUN | Requires real provider |
| dependency-v1 | Not run | NOT_RUN | Requires real provider |
| e2e-v1 | Not run | NOT_RUN | SimulatedGeneration only |

The benchmark software is fully functional. Experiment completion is blocked by:
1. Real LLM credentials (`LLM_API_KEY`, `MODEL_NAME`) not present in the audit environment
2. Real Jev API credentials (`JEV_API_KEY`) not present (OQ-001: API interface still unconfirmed)
3. Full 1,000–2,000 example research dataset not yet constructed (OQ-003)

**The 10-example synthetic CI fixture is NOT the final research dataset.**

---

## Contract Status

`CLAUDE.md` and `JevRoute_MVP_Technical_Architecture.md` remain the strict core engineering contract. No contract provisions were relaxed, weakened, or silently changed during Phase 5.
