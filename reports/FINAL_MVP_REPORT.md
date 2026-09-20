# JevRoute MVP — Final Research Report

**Version:** 0.1.0 (Benchmark Harness Complete; Research Dataset Pending)  
**Date:** 2026-09-20  
**Status:** HARNESS COMPLETE — EMPIRICAL RESULTS PENDING  
**Commit:** e480a5b (Phase 5+6 hardening)  
**Empirical Status:** EMPIRICALLY PARTIAL — all research experiments BLOCKED (see §4)

> **Important:** This report describes the benchmark system design and methodology. Empirical results sections are marked `[PENDING]` where the full 1,000–2,000 example research dataset and real Jev API access have not yet been obtained. No results have been fabricated.

---

## 1. Research Question

> For structured software decisions in AI control planes, what does intelligence cost?

More specifically: can a specialized System-One decision model (Jev) achieve comparable structured decision quality with lower control-plane latency and cost than conventional implementations (deterministic rules, LLM single-call, LLM parallel-call)?

Secondary questions:

1. How does control-plane cost scale as the number of decisions per request increases?
2. What fraction of end-to-end AI request cost is attributable to the control plane?
3. For which request types does a deterministic fast-path gate eliminate Jev overhead entirely?
4. Does richer application context (more fields) improve decision quality enough to justify token cost?
5. Which decision dimensions are truly independent, and which are structurally dependent?

---

## 2. System Description

JevRoute is a controlled benchmark harness. It is not a production AI gateway.

The harness provides a common execution interface for four decision mechanisms:

| System | Description | Version |
|--------|-------------|---------|
| RULES | Deterministic keyword/regex rules | rules-engine-1.0 |
| LLM SINGLE | One structured-output LLM call | llm-control-v1.0 |
| LLM PARALLEL | Six concurrent per-dimension LLM calls | llm-parallel-v1.0 |
| JEV | Jev System-One decision model (external API) | jev-adapter-0.1 |

All four systems:
- Receive the same `ApplicationState` (no ground truth)
- Produce the same normalized `DecisionResult` schema
- Go through the same shared `PolicyEngine` after decision
- Are evaluated by the same evaluation code

---

## 3. Benchmark Design

### Decision Schema (version 1.0)

```
severity:          P1 | P2 | P3 | P4
category:          Billing | Bug | Feature | Account | Other
policy_violation:  bool
hallucination_risk: 0.0 – 1.0
tone_risk:          0.0 – 1.0
action:            SEND | HOLD | ESCALATE
```

### Measurement Dimensions

| Dimension | Metric(s) |
|-----------|-----------|
| Quality | accuracy, macro F1, per-class F1, bad-send rate, over-escalation rate, missed-policy-violation rate |
| Calibration | Brier score, ECE (only for systems with native probability outputs) |
| Latency | p50, p95, p99, mean (perf_counter, monotonic clock) |
| Token usage | input_tokens, output_tokens, num_model_calls |
| Cost | total cost, cost/1K decisions, cost/correct decision |
| Throughput | correct decisions/second (wall-clock) |
| Reliability | schema failure rate, error type distribution, retry count |
| Economics | control-plane tax (e2e-v1 only), control-latency share (e2e-v1 only) |

### Fairness Guarantees

1. Every system receives identical `ApplicationState` — same fields, same preprocessing.
2. `ApplicationState` contains no ground truth.
3. The shared `PolicyEngine` is applied identically after every router.
4. Benchmark concurrency is identical across all systems (default: 8).
5. Failures are retained in raw results, never dropped.
6. Retries are counted and cost-accounted.
7. Test labels are never used to tune any system.

---

## 4. Dataset

### Current Status

| Dataset | Examples | Hash (SHA-256 prefix) | Status | Use |
|---------|----------|----------------------|--------|-----|
| CI fixture (`benchmark_fixture.jsonl`) | 10 | `32d80883d670...` | PRESENT, FROZEN | Pipeline validation only |
| Research benchmark dataset | 1,000–2,000 | N/A | NOT YET AVAILABLE | Required for research conclusions |

**The 10-example synthetic fixture is sufficient for benchmark pipeline validation. It is not sufficient for any research claim about comparative system quality, cost, or latency.**

**Phase 6 blocker:** No research dataset exists. All empirical benchmark runs are blocked. See `results/RESULT_STATUS.json` and `results/EXPERIMENT_VALIDITY.json`.

### Final Dataset Requirements (OQ-003, unresolved)

The final research dataset must:
- Contain 1,000–2,000 labeled examples from the AI customer-support control plane domain
- Use `train / validation / test` splits
- Have the test split frozen before any system tuning
- Document annotator count, agreement metric, construction protocol
- Use only synthetic or authorized data (no real customer PII)

See [docs/DATASET.md](../docs/DATASET.md) for the full dataset protocol.

---

## 5. Compared Systems

### RULES (Deterministic Baseline)

Zero external cost, zero latency uncertainty. Establishes the lower bound on control-plane economics. Expected to perform well on common cases where subject/body patterns are clear; expected to fail on ambiguous or unusual phrasing.

### LLM SINGLE

One structured-output LLM call producing the complete decision. Represents current common practice. Cost: input + output tokens for one call. Latency: one sequential inference request.

### LLM PARALLEL

Six independent concurrent LLM calls, one per decision dimension. Best-case latency for multi-dimension LLM workloads. Cost: sum of all six calls (parallelism does not hide cost). Aggregate tokens = sum of all six calls.

### JEV

Specialized System-One decision model via external API. Primary subject under study. Interface: `POST {JEV_BASE_URL}/v1/decide` (see OQ-001). Cost: per-token configurable, default 0.0 (see OQ-002).

---

## 6. Measurement Methodology

### Latency

All durations computed via `time.perf_counter()`. Wall-clock timestamps (`utc_now_iso()`) used only for run identification — never for duration calculations.

`router_latency_ms`: time from first router call to DecisionResult return (includes retries)  
`total_latency_ms`: time from start of `_execute_example` to end (includes policy engine)

For LLM Parallel: `router_latency_ms` = wall-clock span of all 6 concurrent calls (not sum of individual latencies).

### Cost

```
cost = (input_tokens / 1000) × input_price_per_1k
     + (output_tokens / 1000) × output_price_per_1k
```

Rules: 0.0 (no API call).  
Jev: price configurable via `JEV_INPUT_PRICE` / `JEV_OUTPUT_PRICE` (default 0.0 until OQ-002 resolved).

Cost is accumulated across retries. A request that fails on attempt 1 and succeeds on attempt 2 pays for both calls.

### Quality

`accuracy` = correct `action` decisions / total decisions  
`macro_f1` = sklearn macro F1 over {SEND, HOLD, ESCALATE}  
`bad_send_rate` = predicted SEND when GT is HOLD or ESCALATE, / total  
`over_escalation_rate` = predicted ESCALATE when GT is SEND or HOLD, / total  
`missed_policy_violation_rate` = GT `policy_violation=True` AND `final_action=SEND`, / total GT pv=True

### Control-Plane Tax (e2e-v1 only)

```
control_plane_tax = control_plane_cost / (control_plane_cost + generation_cost)
```

Only meaningful where an end-to-end workload exists. N/A for pure control-plane experiments.

---

## 7. Baseline Results (baseline-v1)

**Dataset:** 10-example synthetic CI fixture (NOT the research dataset)  
**Status: PARTIAL** — rules and mock_jev only. LLM Single, LLM Parallel, and real Jev require external credentials.

| Router | Examples | Accuracy | Macro F1 | p95 Latency | Cost/1K |
|--------|----------|----------|----------|-------------|---------|
| RULES | 10 | 1.000 | ~0.88 | < 1ms | $0 |
| MOCK JEV | 10 | 0.800 | ~0.73 | < 1ms | $0 |
| LLM SINGLE | — | [PENDING] | [PENDING] | [PENDING] | [PENDING] |
| LLM PARALLEL | — | [PENDING] | [PENDING] | [PENDING] | [PENDING] |
| JEV | — | [PENDING] | [PENDING] | [PENDING] | [PENDING] |

**Note:** RULES accuracy of 1.0 on 10 synthetic examples is not a research result — these examples were designed to be easily handled by keyword rules. MOCK JEV intentionally introduces synthetic variance to test the evaluation pipeline.

**Sanity check (Phase 6):** Independent calculation from raw JSONL confirmed aggregate metrics are correct. rules accuracy=1.000 reconciled; mock_jev accuracy=0.800 reconciled. Aggregate uses `total_latency_ms` (includes policy engine). No integrity issues found.

**File hashes (immutable raw results):**  
- `rules.jsonl`: `fdf4f0a78917e6aa02d4e356511a2908830d13bfeb59bf9e4c3d70c607079607`  
- `mock_jev.jsonl`: `adbd8b66e1ebd8cc325289acb7b71be98c05b082e70adfd31645513f420e3d18`

---

## 8. Decision Scaling (scaling-v1)

**Status: NOT_RUN** — [PENDING]

The scaling experiment measures cost and latency across 2, 4, 6, 8, and 12 decision dimensions per request. The Intelligence Cost Curve will plot `total_control_plane_cost_per_request` vs. `decision_count`.

Expected findings (not predetermined):
- Rules: flat cost regardless of decision count (deterministic, no inference)
- LLM Single: near-flat cost (one call, more output tokens)
- LLM Parallel: linear cost (N calls for N decisions)
- Jev: unknown until measured

---

## 9. Fast-Path Bypass (fastpath-v1)

**Status: NOT_RUN** — [PENDING]

Compares "always route to Jev" vs. "run deterministic FastGate, only send non-trivial requests to Jev."

FastGate rules (deterministic, no ML):
1. `exact_match`: SHA-256 hash matches a known-good template
2. `empty_request`: ticket body < 5 characters → HOLD
3. `explicit_action`: customer_tier × product in fixed policy map

Gate latency is recorded separately and never attributed to Jev.

---

## 10. Context Scaling (context-v1)

**Status: NOT_RUN** — [PENDING]

Compares minimal context (4 fields) vs. rich context (6 fields: adds `ticket_body`, `draft_reply`).

Measures: token cost increase, quality improvement, quality-per-additional-token.

---

## 11. Dependency Analysis (dependency-v1)

**Status: NOT_RUN** — [PENDING]

Independent dimensions: `category`, `hallucination_risk`, `tone_risk`  
Dependent dimensions: `severity`, `policy_violation`, `action` (chain: severity → policy_violation → action)

Rationale documented in `experiments/dependency.yaml`.

---

## 12. End-to-End Economics (e2e-v1)

**Status: NOT_RUN (SimulatedGeneration only)** — [PENDING REAL PROVIDER]

The e2e experiment adds a simulated downstream generation step:
- Input tokens: 400 (configurable)
- Output tokens: 180 (configurable)
- Pricing: $0.00015/1K input, $0.0006/1K output (configurable)
- Latency: 1,200ms (configurable)

**These are assumed values, not measured from any provider.**

The dashboard will clearly label all e2e metrics as `SIMULATED` until a real provider is configured.

---

## 13. Reliability

**Current status (10-example CI fixture only):**
- Schema failure rate: 0.0 for rules and mock_jev (expected — deterministic mocks never fail schema)
- Error type distribution: no failures observed in CI fixture run
- Retry distribution: 0 retries (deterministic mocks never need retries)

**Full reliability analysis requires real provider runs**, where network failures, rate limits, and provider errors occur naturally.

---

## 14. Calibration

**Current status: N/A for all current results**

Rules, LLM Single, LLM Parallel, and MockJevRouter do not produce `policy_violation_probability` in their `ConfidenceOutput`. Calibration metrics (Brier score, ECE) return `None` for all current benchmark participants.

When real Jev produces `policy_violation_probability` in its response, calibration metrics will be populated for Jev only.

---

## 15. Limitations

1. **Single domain** — all workloads are AI customer-support control plane. Results may not generalize to other control-plane workloads (content moderation, fraud detection, medical triage, etc.).

2. **Dataset not yet constructed** — the 10-example CI fixture is not the research benchmark. No research conclusion is possible until a 1,000–2,000 example labeled dataset with proper annotation and frozen test split is available.

3. **Jev API not externally validated** — the `HttpxJevClient` assumes `POST {base_url}/v1/decide`. This assumption is documented but not confirmed against actual Jev API behavior (OQ-001).

4. **Jev pricing unknown** — cost comparisons involving Jev default to $0.00/token until OQ-002 is resolved. Cost curves will be invalid until actual Jev pricing is known.

5. **Network variability not isolated** — latency measurements include network round-trip to LLM and Jev providers. Results depend on network conditions at measurement time.

6. **Calibration limited** — calibration analysis is only available for systems with `policy_violation_probability` output. Most current routers do not provide this.

7. **Rules strength on constrained cases** — the deterministic rules baseline performs strongly on the synthetic CI fixture because the fixture was designed with clear patterns. Real-world performance may differ.

8. **`num_model_calls` not populated** — LLMParallelRouter's 6-call nature is not reflected in the `num_model_calls` field of BenchmarkRecord (always None). This is a minor observability gap documented in PHASE5_AUDIT.md.

9. **Generation-dominant workloads** — in end-to-end workloads where generation costs dwarf control-plane costs, differences between routers may fall below practical significance even if statistically significant.

10. **Prompt and model version dependence** — LLM Single and LLM Parallel results depend on the specific model version and prompt version. Version changes require new experiment runs.

---

## 16. Reproducibility

See [docs/REPRODUCTION.md](../docs/REPRODUCTION.md) for step-by-step instructions.

**Reproducible today (no credentials required):**
- 108 unit, integration, and benchmark tests
- Mock benchmark run (rules + mock_jev, 10 examples)
- Dashboard with proper empty states

**Blocked until credentials available:**
- LLM Single / LLM Parallel runs
- Real Jev runs
- Full scaling, fast-path, context, dependency, e2e experiments

Every benchmark run records: dataset version, git SHA, router version, prompt version, schema version, policy version, experiment config, concurrency, and environment metadata. All fields required by CLAUDE.md §10 are present.

---

## 17. Conclusions

**No research conclusions can be drawn from the current data.**

The benchmark harness is complete, validated, and internally consistent. The measurement methodology is sound. But the absence of:
- the full 1,000–2,000 example labeled research dataset
- real Jev API access and confirmed pricing
- real LLM provider runs

means no comparative claim about Jev vs. Rules vs. LLM Single vs. LLM Parallel is empirically supported.

**This report will be updated when those prerequisites are met.**

The benchmark is designed not to predetermine an outcome. Possible empirical outcomes include:
- Jev shows a quality-adjusted cost advantage at high decision counts
- Jev shows no meaningful advantage over LLM Single for single-decision requests
- Rules outperforms all neural systems on constrained, predictable workloads
- LLM Parallel reduces latency gaps at the expense of cost
- Fast-path bypass eliminates Jev overhead for a significant fraction of requests
- Control-plane differences become negligible in generation-dominant end-to-end workloads

Only measured data will answer these questions.
