# JevRoute — Dataset Protocol

## Dataset Identity

| Field | Value |
|-------|-------|
| Name | `jevroute-support-control` |
| Version | `0.1.0-synthetic` |
| Status | **Synthetic CI Fixture** — not the final research dataset |
| Examples (current) | 10 |
| Final target | 1,000–2,000 labeled examples |
| Domain | AI customer-support control plane |

---

## Purpose

This dataset provides ground truth for the JevRoute benchmark. Each example is a structured `ApplicationState` paired with a `DecisionResult` label. The benchmark measures whether each router's decision matches the label.

The label is the answer to: *given this application state, what is the correct structured decision?*

---

## Source and Construction (Current — Synthetic Fixture)

The current dataset is a **10-example synthetic CI fixture**. It was constructed manually to cover:

- All four severity levels (P1, P2, P3, P4)
- All five categories (Billing, Bug, Feature, Account, Other)
- Both policy violation states
- All three actions (SEND, HOLD, ESCALATE)
- Edge cases: empty ticket body, high hallucination risk, explicit action pairs

These examples are sufficient for:
- Benchmark engine validation (all routers execute, all results normalize)
- CI test coverage (pytest passes without paid API calls)
- Schema validation

They are **not sufficient for** research conclusions. The benchmark must be re-run on the full dataset before any research claims are made.

---

## Label Definitions

| Field | Type | Definition |
|-------|------|------------|
| `severity` | `P1\|P2\|P3\|P4` | P1 = critical/data loss, P2 = significant functional impact, P3 = minor, P4 = cosmetic/question |
| `category` | enum | Primary ticket category (Billing, Bug, Feature, Account, Other) |
| `policy_violation` | bool | True if the ticket contains content that violates AI system usage policy |
| `hallucination_risk` | float 0–1 | Risk that the ticket contains hallucinated or fabricated claims |
| `tone_risk` | float 0–1 | Risk that the ticket contains hostile, abusive, or unsafe tone |
| `action` | `SEND\|HOLD\|ESCALATE` | Recommended action: SEND (reply), HOLD (queue for human review), ESCALATE (immediate human) |

---

## Decision Schema Version

`decision_schema_version: "1.0"`

Label definitions are frozen at this version. Schema changes require a new version and new benchmark runs.

---

## Split Protocol

| Split | Purpose | Rules |
|-------|---------|-------|
| `train` | Prompt development, rule tuning, threshold calibration | May be used to tune prompts and rules |
| `validation` | Intermediate evaluation during development | May be used to select between configurations |
| `test` | Final benchmark evaluation | **Frozen. Never used to tune any system.** |

Current fixture: `datasets/test/jevroute_support_v01.jsonl` (10 examples — test split only for CI).

---

## Test Set Freeze Rule

The test split is immutable after creation. The following actions are prohibited:

- Using test labels to tune LLM prompts
- Using test labels to adjust rule thresholds
- Using test labels to select policy parameters
- Using test error patterns to guide system design

Violation of this rule invalidates the benchmark. See `CLAUDE.md §6` (Benchmark Fairness Rules, rule 7).

---

## Annotation Procedure (for the Full Research Dataset)

When the full dataset is constructed, the annotation protocol must be documented here, including:

1. **Source**: How examples were obtained (e.g., synthetic generation, public support ticket corpus with added labels, authorized internal data)
2. **Annotators**: Number of annotators, background, inter-annotator agreement metric
3. **Labeling interface**: Tool used (e.g., Label Studio, custom form)
4. **Disagreement resolution**: Majority vote, expert adjudication, or other
5. **Quality control**: Spot-check rate, error rate threshold for re-annotation
6. **Exclusion criteria**: What examples were excluded (PII, duplicates, ambiguous)
7. **Date range**: When annotation was performed

---

## Privacy and Security

- No real customer data is used in this dataset.
- All examples are synthetic or authorized.
- Customer identifiers (if any) are hashed or replaced with synthetic values.
- See `CLAUDE.md §11` (Security Rules).

---

## Limitations

1. The current 10-example fixture is too small for statistical conclusions.
2. All examples cover a single domain (AI customer-support control plane).
3. Results may not generalize to other control-plane workloads.
4. Label quality has not been validated by external annotators.
5. The fixture was constructed to cover edge cases, not to reflect realistic prevalence distributions.

---

## Related Files

| File | Purpose |
|------|---------|
| `datasets/test/jevroute_support_v01.jsonl` | Current test fixture (10 examples) |
| `src/jevroute/benchmark/workload.py` | Workload loader (enforces test split label isolation) |
| `tests/fixtures/` | CI fixtures (subset of the test split) |
| `CLAUDE.md §6` | Benchmark fairness rules |
| `CLAUDE.md §10` | Data rules |
