# JevRoute — Open Questions

Genuine ambiguities discovered between the specification files or the current repository state.

---

## OQ-001: Jev API Client / SDK

**Issue:** Neither specification document describes the Jev API's actual interface — whether it provides an official Python SDK, a REST API, a gRPC API, or another integration mechanism.

**Source:** `JevRoute_MVP_Technical_Architecture.md` §10.4 (JevRouter) describes what the adapter must do but not how to call Jev.

**Why it matters:** The `JevRouter` adapter design depends on whether Jev provides a native Python client or requires raw HTTP calls via `httpx`.

**Current interpretation:** The adapter wraps whatever Jev exposes. The `MockJevRouter` will be the working implementation until the real API credentials and client are available.

**Recommended resolution:** Obtain Jev API documentation and credentials before Phase 3 begins. If Jev provides a Python package, add it to `pyproject.toml`. The adapter interface (ApplicationState → DecisionResult) does not change regardless.

---

## OQ-002: Jev Token / Cost Model

**Issue:** The specification notes `JEV_INPUT_PRICE` and `JEV_OUTPUT_PRICE` environment variables but Jev is described as a "System-One decision model" — it may not use token-based pricing at all.

**Source:** `JevRoute_MVP_Technical_Architecture.md` §29 (Environment Variables).

**Why it matters:** Cost accounting for `JevRouter` must be defined before the baseline experiment runs. If Jev charges per decision rather than per token, the cost formula differs from LLM routers.

**Current interpretation:** Record whatever cost unit Jev exposes (tokens, decisions, API calls) and map it to `estimated_cost_usd`. `output_tokens` may be `0` or `null` for Jev.

**Recommended resolution:** Confirm Jev's pricing model before Phase 3. Update `.env.example` with the correct variables and document the cost formula in `evaluation/cost.py`.

---

## OQ-003: Dataset Source and Construction

**Issue:** Neither specification prescribes exactly how the 1,000–2,000 labeled examples are obtained or constructed. The spec references "synthetic or authorized data" (§46) and recommends a support-style workload, but does not specify a source dataset, annotation methodology, or labeling protocol.

**Source:** `JevRoute_MVP_Technical_Architecture.md` §36 (Synthetic Fixture), §46 (Security); `JevRoute_Project_Documentation.md` §11 (Dataset).

**Why it matters:** Ground truth labels are the foundation of the benchmark. The dataset construction protocol must be documented and reproducible. Label quality directly affects all quality metrics.

**Current interpretation:** Phase 1 provides a 10-example synthetic fixture sufficient for CI. The full 1,000–2,000 example dataset and annotation protocol are deferred to Phase 2/3, with documentation required before the benchmark runs.

**Recommended resolution:** Decide before Phase 2 whether to use (a) a publicly available support ticket dataset with added labels, (b) a fully synthetic generated dataset, or (c) an internally authorized dataset. Document source, construction, labeling process, and exclusions in `docs/dataset_protocol.md`.

---

## OQ-004: Directory Structure Minor Discrepancy

**Issue:** `JevRoute_MVP_Technical_Architecture.md` §28 defines the canonical directory structure under `jevroute/` at the repo root. `JevRoute_Project_Documentation.md` §27 shows a slightly different structure named `decisionplane/` with a `schemas/` directory instead of `src/jevroute/models/`.

**Source:** Technical Architecture §28 vs. Project Documentation §27.

**Why it matters:** The repository must have one canonical layout.

**Current interpretation:** The technical architecture (Level 1 contract) governs. The structure is `src/jevroute/` with `models/`, `routers/`, `policy/`, `benchmark/`, `evaluation/` subdirectories. The `schemas/` directory in the project documentation is superseded by `src/jevroute/models/`.

**Recommended resolution:** No action required — this interpretation is already encoded in `IMPLEMENTATION_MAP.md` and `PHASE_PLAN.md`. Document it here for traceability.

---

## OQ-005: Calibration Participation for Rules Router

**Issue:** The specification states that calibration (Brier Score, ECE) applies only to "systems with native probability/confidence outputs." The `RulesRouter` may produce `hallucination_risk` and `tone_risk` as continuous values derived from heuristics rather than true probabilities.

**Source:** `JevRoute_MVP_Technical_Architecture.md` §20 (Calibration).

**Why it matters:** If heuristic-derived continuous outputs from `RulesRouter` are included in calibration analysis without qualification, it could misrepresent the nature of the rules baseline.

**Current interpretation:** `RulesRouter` continuous outputs are labeled as "heuristic scores" in the benchmark, not calibrated probabilities. Calibration analysis is performed only for systems that natively produce probabilistic outputs. `brier_score` and `ece` are `null` for `RulesRouter` unless it genuinely estimates probabilities.

**Recommended resolution:** Confirm this interpretation during Phase 2 when `RulesRouter` is implemented. Document it explicitly in evaluation methodology.

---

---

## OQ-001 Resolution (Phase 3)

**Resolution:** Jev API unknown → minimal adapter boundary.

`HttpxJevClient` assumes `POST {base_url}/v1/decide` with a JSON payload containing the structured application state. This assumption is documented in `src/jevroute/routers/jev_client.py`. The `JevClient` Protocol isolates all transport logic: if the real API uses a different endpoint, auth scheme, or SDK, only `HttpxJevClient` changes. The benchmark/evaluation code is unaffected.

`FakeJevClient` enables all unit tests and CI without network access or credentials. All 20 Jev unit tests pass with no network calls.

**Status:** Documented assumption. Update `HttpxJevClient` when real Jev API documentation is available.

---

## OQ-002 Resolution (Phase 3)

**Resolution:** Jev pricing model unknown → per-token configurable, default 0.0.

`JevRouter` accepts `model_input_price_per_1k` and `model_output_price_per_1k` constructor parameters (also settable via `JEV_INPUT_PRICE` and `JEV_OUTPUT_PRICE` env vars). Both default to `0.0`, so all cost accounting is non-distorting when prices are unknown. The formula is documented as an assumption in `jev_client.py`: "per-token pricing assumed — update if Jev charges per-decision."

If Jev is per-decision, set both price variables to `0.0` and add a separate `jev_decision_price` variable to represent the flat fee.

**Status:** Documented assumption. Confirm and update `.env.example` when real Jev pricing is available.

---

## Phase 8 Audit (2026-09-20)

**OQ-001 — Jev API Contract:** UNRESOLVED.

Phase 8 confirmed: no authoritative Jev API documentation is available in the repository or development environment. The `HttpxJevClient` implementation uses a documented assumption (`POST {base_url}/v1/decide`). This assumption must be replaced with a confirmed contract before any research benchmark run involving JevRouter. The adapter boundary is cleanly isolated so only `HttpxJevClient` changes when the real contract is obtained.

**OQ-002 — Jev Pricing:** UNRESOLVED.

Phase 8 confirmed: no official Jev pricing information is available. Cost fields for JevRouter default to `$0.00`. Any benchmark results involving Jev must disclose that cost figures are unconfirmed placeholders.

**OQ-003 — Research Dataset:** NOT AVAILABLE.

Phase 8 confirmed: only the 10-example CI fixture (`datasets/test/benchmark_fixture.jsonl`) exists. No 1,000–2,000 example labeled research dataset has been provided or sourced. Dataset infrastructure (validator, splitter, freeze, quality gate, CLI) is fully implemented and ready to process a legitimate dataset once one is provided.

**OQ-004 and OQ-005:** No change from previous assessment.

**Phase 8 outcome:** All six experiments (baseline-v1, scaling-v1, fastpath-v1, context-v1, dependency-v1, e2e-v1) remain BLOCKED. Repository is at BENCHMARK_READY (pre-empirical) state. Benchmark can execute the moment external inputs are supplied.

## No Further Ambiguities Identified

The two specification files are broadly consistent. The five items above represent genuine gaps where implementation decisions are required but not fully specified by the current documents.
