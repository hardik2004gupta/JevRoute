# JevRoute — Methodology

## Decision Schema (version 1.0)

| Field | Type | Values |
|-------|------|--------|
| severity | enum | P1, P2, P3, P4 |
| category | enum | Billing, Bug, Feature, Account, Other |
| policy_violation | bool | true/false |
| hallucination_risk | float | 0.0–1.0 |
| tone_risk | float | 0.0–1.0 |
| action | enum | SEND, HOLD, ESCALATE |

## Fairness Guarantees

1. All routers receive identical `ApplicationState` (no ground truth)
2. Shared `PolicyEngine` applied identically after each router
3. Benchmark concurrency identical across all systems (concurrency=8)
4. Failures retained in raw results, never dropped
5. Retries counted and cost-accounted
6. Test labels never used to tune any system

## Latency Measurement

All durations via `time.perf_counter()`. Wall-clock timestamps for run identification only.

- `router_latency_ms`: router call span (includes retries)
- `total_latency_ms`: full example span (includes policy engine)
- LLM Parallel: wall-clock span of all concurrent calls

## Cost Measurement

```
cost = (input_tokens / 1000) × input_price_per_1k
     + (output_tokens / 1000) × output_price_per_1k
```

- Rules: $0.00 (no API call)
- Jev: configurable via JEV_INPUT_PRICE / JEV_OUTPUT_PRICE (default $0.00 — OQ-002)
- Cost accumulated across retries

## Quality Metrics

- `accuracy` = correct action / total
- `macro_f1` = sklearn macro F1 over {SEND, HOLD, ESCALATE}
- `bad_send_rate` = predicted SEND when GT is HOLD/ESCALATE / total
- `over_escalation_rate` = predicted ESCALATE when GT is SEND/HOLD / total
- `missed_policy_violation_rate` = GT pv=True AND final_action=SEND / total GT pv=True

## Calibration

Brier score and ECE apply only to systems with `policy_violation_probability` output.  
Rules, LLM Single/Parallel: N/A (no native probability output).
