# JevRoute MVP — Technical Architecture Specification

**Document Type:** MVP Technical Architecture  
**Project:** JevRoute  
**Version:** 1.0  
**Status:** Implementation-ready specification  
**Primary Goal:** Benchmark Jev as a structured decision layer against conventional AI control-plane implementations.

---

## 1. Executive Summary

JevRoute is a controlled benchmark and reference implementation for evaluating whether a specialized System-One decision model can make structured AI control decisions more efficiently than conventional implementations.

The MVP deliberately avoids becoming a general-purpose AI gateway.

The system provides a common execution interface for four decision mechanisms:

1. Deterministic Rules
2. LLM Single-Call Structured Output
3. LLM Parallel Structured Decisions
4. Jev

All four systems receive equivalent application state and produce the same normalized decision object.

The benchmark measures:

- correctness
- precision / recall / F1
- latency
- token usage
- cost
- schema validity
- calibration
- decision throughput
- cost per correct decision
- control-plane tax

The primary workload is an AI customer-support control plane.

---

# 2. MVP Objectives

## 2.1 Primary Objective

Determine:

> For structured software decisions, what does intelligence cost?

Specifically measure whether Jev can achieve comparable decision quality with lower:

- control-plane latency
- control-plane cost
- computational overhead

than conventional LLM-based control logic.

## 2.2 Secondary Objectives

- Measure how decision cost scales as the number of decisions increases.
- Quantify the cost of adding a decision layer to an AI application.
- Identify cases where deterministic rules remain preferable.
- Determine whether a fast deterministic gate should bypass Jev for trivial requests.
- Produce a reproducible open benchmark harness.

---

# 3. Non-Goals

The MVP does **not** include:

- production-scale distributed deployment
- RAG infrastructure
- Redis
- human-review UI
- multi-agent orchestration
- model serving infrastructure
- GPU scheduling
- managed cloud routing products
- RouteLLM integration in the core benchmark
- online reinforcement learning
- automatic prompt optimization
- autonomous policy learning

These belong to future experiments.

---

# 4. Architecture Principles

## 4.1 Fair comparison

Every decision engine must conform to the same interface and receive equivalent state.

## 4.2 Measurement before optimization

The benchmark must record raw observations before deriving aggregate metrics.

## 4.3 No hidden costs

Router latency, router tokens, and router API cost are included in measured control-plane economics.

## 4.4 Frozen test set

No benchmark implementation may tune prompts, rules, thresholds, or policies against the final test set.

## 4.5 Vendor claims are not benchmark results

External published performance numbers may be referenced as background but must not be inserted into measured result tables.

## 4.6 Replaceability

Jev-specific code must be isolated behind an adapter.

---

# 5. High-Level Architecture

```text
                         +----------------------+
                         |   Benchmark Runner   |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         |   Workload Loader    |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         | Application State    |
                         +----------+-----------+
                                    |
             +----------------------+----------------------+
             |                      |                      |
             v                      v                      v
      +-------------+       +--------------+       +-------------+
      | RulesRouter |       | LLM Router   |       |  JevRouter  |
      +------+------+       +------+-------+       +------+------+
             |                       |                     |
             |                +------+------+              |
             |                |             |              |
             |                v             v              |
             |          LLM Single     LLM Parallel        |
             |                |             |              |
             +----------------+-------------+--------------+
                                    |
                                    v
                         +----------------------+
                         | Normalized Decision  |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         | Shared Policy Engine |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         | Evaluation Harness   |
                         +----+------------+----+
                              |            |
                              v            v
                       Raw Metrics    Aggregate Metrics
                              |            |
                              +------+-----+
                                     |
                                     v
                              Reports / Dashboard
```

---

# 6. Core Components

## 6.1 Benchmark Runner

Responsible for:

- loading experiment configuration
- selecting the router
- iterating through examples
- recording timing
- collecting normalized outputs
- persisting raw observations
- triggering evaluation

The runner must be router-agnostic.

---

## 6.2 Workload Loader

Loads a versioned dataset containing:

```text
example_id
customer_tier
product
region
ticket_subject
ticket_body
draft_reply
ground_truth
metadata
```

The loader must support:

```text
train
validation
test
```

and reject accidental use of test labels during router execution.

---

## 6.3 Router Abstraction

All implementations conform to the same logical interface:

```python
class DecisionRouter(Protocol):
    async def decide(
        self,
        state: "ApplicationState",
    ) -> "DecisionResult":
        ...
```

Implementations:

```text
RulesRouter
LLMSingleRouter
LLMParallelRouter
JevRouter
```

---

# 7. Application State

The state object contains only information legitimately available to the control plane.

Example:

```json
{
  "example_id": "SUP-000123",
  "customer_tier": "enterprise",
  "product": "billing",
  "region": "EU",
  "ticket_subject": "Unexpected duplicate charge",
  "ticket_body": "I was billed twice...",
  "draft_reply": "We are reviewing your transaction..."
}
```

The Jev implementation should not receive unrelated large application state.

---

# 8. Decision Schema

All routers normalize into:

```json
{
  "severity": "P2",
  "category": "Billing",
  "policy_violation": false,
  "hallucination_risk": 0.12,
  "tone_risk": 0.04,
  "action": "SEND"
}
```

Allowed values:

## severity

```text
P1 | P2 | P3 | P4
```

## category

```text
Billing
Bug
Feature
Account
Other
```

## policy_violation

```text
true | false
```

## hallucination_risk

```text
0.0 <= x <= 1.0
```

## tone_risk

```text
0.0 <= x <= 1.0
```

## action

```text
SEND | HOLD | ESCALATE
```

---

# 9. Confidence Representation

Where a router produces confidence or probabilities, normalize them into:

```json
{
  "severity_confidence": 0.91,
  "category_confidence": 0.96,
  "policy_violation_probability": 0.08,
  "hallucination_probability": 0.12,
  "tone_risk_probability": 0.04,
  "action_confidence": 0.93
}
```

Do not manufacture probabilities for systems that do not natively provide them.

A missing probability should be represented as:

```json
null
```

---

# 10. Router Implementations

## 10.1 RulesRouter

Purpose:

Establish a deterministic baseline.

Implementation:

- normalization
- keyword groups
- regex rules
- customer metadata
- policy thresholds
- explicit escalation rules

Example:

```text
"charged twice"
        |
        v
Billing category
        |
        v
severity policy
        |
        v
P1/P2 decision
```

Rules must be tuned using training/validation data only.

---

## 10.2 LLMSingleRouter

One LLM request produces the complete structured decision.

Input:

```text
application state
+
decision instructions
+
schema
```

Output:

```json
{
  "severity": "...",
  "category": "...",
  "policy_violation": false,
  "hallucination_risk": 0.10,
  "tone_risk": 0.04,
  "action": "SEND"
}
```

Requirements:

- strict structured output where supported
- fixed prompt version
- deterministic generation settings where possible
- complete token accounting
- response validation

---

## 10.3 LLMParallelRouter

Each decision is generated by an independent LLM call.

Example:

```text
                    Application State
                           |
          +----------------+----------------+
          |                |                |
          v                v                v
       Severity         Category        Policy Check
          |                |                |
          +----------------+----------------+
                           |
          +----------------+----------------+
          |                |                |
          v                v                v
    Hallucination        Tone            Action Policy
```

Execution uses asynchronous concurrency.

Important:

The benchmark must measure:

- total wall-clock latency
- aggregate token usage
- aggregate cost
- per-call latency

This prevents parallel execution from appearing artificially free.

---

## 10.4 JevRouter

JevRouter is an isolated adapter around the Jev API/client.

Responsibilities:

1. Transform ApplicationState into routing state.
2. Submit the structured decision specification.
3. Parse Jev results.
4. Normalize values into DecisionResult.
5. Record Jev latency and cost metadata.

No downstream policy logic belongs inside the adapter.

---

# 11. Shared Policy Engine

The policy engine must be identical for all routers.

Example:

```python
def apply_policy(decision: DecisionResult) -> Action:
    if decision.policy_violation:
        return Action.HOLD

    if decision.action == Action.ESCALATE:
        return Action.ESCALATE

    if decision.severity == Severity.P1:
        return Action.ESCALATE

    if decision.hallucination_risk >= 0.8:
        return Action.HOLD

    return decision.action
```

The exact policy must be frozen before final benchmark execution.

No router gets custom downstream treatment.

---

# 12. Fast-Path Layer

The MVP includes an optional deterministic pre-gate.

```text
                    REQUEST
                       |
                       v
                  Fast Gate
                    /   \
                  /       \
              bypass      |
                |          v
                |         Jev
                |          |
                +----+-----+
                     |
                     v
                Policy Engine
```

Potential bypass candidates:

- exact cache match
- explicit deterministic operation
- invalid/empty request
- explicit model/action selection
- very small fixed-format request

The fast gate must be deterministic.

Its own latency must be recorded.

---

# 13. Evaluation Pipeline

```text
                  Router Output
                       |
                       v
                 Schema Validator
                       |
              +--------+--------+
              |                 |
              v                 v
          Valid Output      Invalid Output
              |                 |
              +--------+--------+
                       |
                       v
                 Ground Truth
                       |
                       v
               Metric Calculator
                       |
                       v
                 Raw Result Row
```

Invalid schema results must not simply disappear.

They are recorded as failures.

---

# 14. Raw Benchmark Record

Each execution should generate a record similar to:

```json
{
  "experiment_id": "baseline-v1",
  "run_id": "run-000123",
  "example_id": "SUP-000123",
  "router": "jev",
  "router_version": "jev-adapter-0.1",
  "decision_schema_version": "1.0",
  "started_at": "2026-09-20T10:00:00Z",
  "router_latency_ms": 184.2,
  "total_latency_ms": 191.7,
  "input_tokens": 233,
  "output_tokens": 0,
  "estimated_cost_usd": 0.0001,
  "schema_valid": true,
  "prediction": {
    "severity": "P2",
    "category": "Billing",
    "policy_violation": false,
    "hallucination_risk": 0.12,
    "tone_risk": 0.04,
    "action": "SEND"
  },
  "ground_truth": {
    "severity": "P2",
    "category": "Billing",
    "policy_violation": false,
    "hallucination_risk": 0.10,
    "tone_risk": 0.05,
    "action": "SEND"
  }
}
```

Raw records must be immutable after the experiment run.

---

# 15. Metrics

## 15.1 Latency

Required:

```text
p50
p95
p99
```

Also retain:

```text
min
max
mean
standard deviation
```

---

## 15.2 Quality

Categorical decisions:

```text
accuracy
precision
recall
F1
confusion matrix
```

Final action:

```text
SEND accuracy
HOLD accuracy
ESCALATE accuracy
```

Safety-sensitive measures:

```text
bad-send rate
over-escalation rate
missed-policy-violation rate
```

---

## 15.3 Token Usage

Record separately:

```text
input tokens
output tokens
total tokens
```

For multi-call systems:

```text
aggregate input tokens
aggregate output tokens
number of model calls
```

---

## 15.4 Cost

Control-plane cost:

```text
input token cost
+
output token cost
+
other explicit router charges
```

End-to-end cost:

```text
control-plane cost
+
generation cost
```

---

# 16. Cost per Correct Decision

Definition:

```text
Cost Per Correct Decision
=
Total Control-Plane Cost
/
Total Correct Decisions
```

Use the sum of all evaluated decisions.

Do not calculate it from rounded display values.

---

# 17. Decision Throughput

Definition:

```text
Decision Throughput
=
Total Correct Decisions
/
Total Wall-Clock Time
```

Report:

```text
decisions / second
```

For distributed or concurrent runs, the benchmark must clearly specify the concurrency level.

---

# 18. Control-Plane Tax

Definition:

```text
Control-Plane Tax
=
Control-Plane Cost
/
Total AI Request Cost
```

For a pure control-plane benchmark without generation, this metric is not applicable.

For end-to-end experiments, it becomes a first-class metric.

---

# 19. Control-Plane Latency Share

Definition:

```text
Control-Plane Latency Share
=
Control-Plane Latency
/
End-to-End Latency
```

This reveals whether control-plane optimization materially affects total request latency.

---

# 20. Calibration

Only systems with native probability/confidence outputs participate in probability calibration analysis.

Required metrics:

```text
Brier Score
Expected Calibration Error
```

Optional:

```text
reliability diagram
maximum calibration error
```

Systems without probabilistic outputs are marked:

```text
N/A
```

rather than assigned artificial probabilities.

---

# 21. Experiment: Baseline Comparison

## Objective

Compare the four core implementations.

```text
Rules
LLM Single
LLM Parallel
Jev
```

## Inputs

```text
1,000–2,000 examples
```

## Outputs

```text
accuracy
F1
p50
p95
p99
tokens
cost
cost/correct decision
decision throughput
schema failures
```

Primary report:

```text
benchmark_baseline_v1.csv
benchmark_baseline_v1.json
```

---

# 22. Experiment: Decision Scaling

Keep workload semantics consistent while increasing the number of decisions:

```text
2 decisions
4 decisions
6 decisions
8 decisions
12 decisions
```

Measure:

```text
latency
cost
tokens
accuracy
decision throughput
cost/correct decision
```

Primary graph:

```text
INTELLIGENCE COST CURVE
```

---

# 23. Experiment: Fast-Path

Compare:

```text
Always Jev
```

against:

```text
Fast Gate + Jev
```

Required metrics:

```text
Jev calls avoided
total latency
p50
p95
cost
quality
```

This experiment determines whether Jev should be invoked for every request or only ambiguous requests.

---

# 24. Experiment: Context Scaling

Compare:

```text
Minimal Routing State
```

against:

```text
Rich Routing State
```

Measure:

```text
input tokens
cost
latency
decision quality
quality improvement / additional token
```

Primary question:

> Does additional context produce enough quality improvement to justify its routing cost?

---

# 25. Experiment: Dependency-Aware Control

Create two workload families.

## Independent

```text
category
tone risk
hallucination risk
```

## Dependent

```text
severity
  |
  v
policy
  |
  v
action
```

Measure:

```text
latency
quality
throughput
```

The benchmark must document which decisions were classified as independent and why.

---

# 26. End-to-End Benchmark

This experiment evaluates whether control-plane efficiency materially changes the complete AI application.

```text
USER REQUEST
     |
     v
CONTROL PLANE
     |
     v
POLICY
     |
     v
GENERATION
     |
     v
FINAL RESPONSE
```

Compare:

```text
conventional control plane
vs
Jev control plane
```

Measure:

```text
control-plane cost
generation cost
total cost
control latency
generation latency
total latency
quality
```

---

# 27. Benchmark Configuration

Example:

```yaml
experiment:
  name: baseline-v1
  dataset: support-control-v1
  split: test
  concurrency: 8
  max_examples: 1500

decision_schema:
  version: "1.0"

routers:
  - rules
  - llm_single
  - llm_parallel
  - jev

metrics:
  latency: true
  token_usage: true
  cost: true
  accuracy: true
  f1: true
  calibration: true
```

Configuration must be committed with the benchmark output.

---

# 28. Directory Structure

```text
jevroute/
|
+-- README.md
+-- pyproject.toml
+-- .env.example
|
+-- src/
|   +-- jevroute/
|       +-- models/
|       |   +-- state.py
|       |   +-- decision.py
|       |
|       +-- routers/
|       |   +-- base.py
|       |   +-- rules.py
|       |   +-- llm_single.py
|       |   +-- llm_parallel.py
|       |   +-- jev.py
|       |
|       +-- policy/
|       |   +-- engine.py
|       |
|       +-- benchmark/
|       |   +-- runner.py
|       |   +-- recorder.py
|       |   +-- config.py
|       |
|       +-- evaluation/
|           +-- quality.py
|           +-- latency.py
|           +-- cost.py
|           +-- calibration.py
|           +-- throughput.py
|
+-- datasets/
|   +-- raw/
|   +-- processed/
|   +-- train/
|   +-- validation/
|   +-- test/
|
+-- experiments/
|   +-- baseline.yaml
|   +-- scaling.yaml
|   +-- fast_path.yaml
|   +-- context_scaling.yaml
|
+-- results/
|   +-- raw/
|   +-- aggregate/
|   +-- figures/
|
+-- dashboard/
|
+-- tests/
    +-- unit/
    +-- integration/
    +-- benchmark/
```

---

# 29. Environment Variables

Example:

```text
JEV_API_KEY=
LLM_API_KEY=
MODEL_NAME=
MODEL_INPUT_PRICE=
MODEL_OUTPUT_PRICE=
JEV_INPUT_PRICE=
JEV_OUTPUT_PRICE=
```

Secrets must never be committed.

---

# 30. Observability

Every router must emit structured logs.

Required fields:

```text
experiment_id
run_id
example_id
router
router_version
timestamp
latency_ms
input_tokens
output_tokens
cost_usd
schema_valid
```

Optional:

```text
request_hash
provider_request_id
model_name
retry_count
error_type
```

Never log secrets.

---

# 31. Error Handling

Router failures must be classified.

Recommended categories:

```text
TIMEOUT
RATE_LIMIT
AUTHENTICATION
NETWORK
SCHEMA_VALIDATION
PROVIDER_ERROR
INVALID_RESPONSE
INTERNAL_ERROR
```

A failed request must remain in the benchmark dataset as a failed observation.

Silently dropping errors invalidates reliability measurements.

---

# 32. Retries

Retries must be:

- explicitly configured
- bounded
- recorded
- included in latency
- included in cost

Example:

```yaml
retry:
  max_attempts: 2
  backoff_ms: 250
```

Never retry indefinitely.

---

# 33. Concurrency

The benchmark supports configurable concurrency:

```text
1
4
8
16
32
```

MVP baseline recommendation:

```text
concurrency = 8
```

Concurrency must be identical across systems unless the experiment explicitly studies concurrency scaling.

---

# 34. Reproducibility

Every result bundle must contain:

```text
dataset version
code commit SHA
router version
prompt version
decision schema version
experiment config
model/provider identifier
benchmark timestamp
concurrency
environment metadata
```

A result without configuration metadata is not considered reproducible.

---

# 35. Testing Strategy

## Unit tests

Cover:

- state validation
- schema validation
- policy rules
- cost calculations
- latency recording
- result aggregation
- calibration calculations

## Integration tests

Cover:

- router adapter
- API error handling
- structured-output parsing
- Jev adapter
- benchmark runner

## Benchmark tests

Use a tiny deterministic fixture:

```text
10 examples
```

to verify:

- all routers execute
- all results normalize
- metrics aggregate correctly

---

# 36. Synthetic Fixture

The repository should include a tiny test fixture separate from the research dataset.

Example:

```json
{
  "example_id": "fixture-001",
  "ticket_subject": "Duplicate charge",
  "ticket_body": "I was charged twice.",
  "draft_reply": "We are checking the transaction.",
  "ground_truth": {
    "severity": "P2",
    "category": "Billing",
    "policy_violation": false,
    "hallucination_risk": 0.05,
    "tone_risk": 0.02,
    "action": "SEND"
  }
}
```

This allows CI to run without paid APIs.

---

# 37. MockJev

A `MockJevRouter` must exist.

Purpose:

- CI
- local development
- deterministic unit tests
- fallback when the external API is unavailable

Example:

```python
class MockJevRouter:
    async def decide(self, state):
        return DecisionResult(...)
```

The mock must never be included in published benchmark results.

---

# 38. Result Storage

Use simple files for the MVP.

Recommended:

```text
raw JSONL
aggregate CSV
experiment metadata JSON
```

Example:

```text
results/
  raw/
    baseline-v1/
      rules.jsonl
      llm-single.jsonl
      llm-parallel.jsonl
      jev.jsonl

  aggregate/
    baseline-v1.csv

  figures/
    baseline_latency.png
    baseline_cost.png
    intelligence_cost_curve.png
```

A database is not required.

---

# 39. Benchmark Output Schema

Aggregate output should contain:

```text
router
examples
decisions
correct_decisions
accuracy
macro_f1
p50_latency_ms
p95_latency_ms
p99_latency_ms
input_tokens
output_tokens
total_cost_usd
cost_per_correct_decision_usd
decision_throughput
schema_failure_rate
brier_score
ece
```

Fields unavailable for a given router are `null` or `N/A`.

---

# 40. Statistical Reporting

For each metric, report enough information to avoid over-interpreting a tiny sample.

At minimum:

```text
sample size
median
p95 where appropriate
mean where useful
```

For proportions:

```text
numerator
denominator
percentage
```

Where appropriate, add bootstrap confidence intervals in a later iteration.

Do not report excessive decimal precision.

---

# 41. Primary Acceptance Criteria

The MVP is complete when:

## Engineering

- all four routers conform to the same interface
- all outputs normalize to one schema
- benchmark runs end-to-end
- raw observations are persisted
- failed calls are recorded
- mock mode runs without paid APIs
- tests pass

## Measurement

- latency is measured at p50/p95/p99
- token usage is captured
- router cost is captured
- quality is measured against frozen labels
- cost per correct decision is computed
- decision throughput is computed
- fast-path experiment runs
- scaling experiment runs

## Documentation

- benchmark methodology is documented
- dataset construction is documented
- configuration is versioned
- limitations are documented
- results can be reproduced from a clean checkout

---

# 42. Definition of Done for Jev Adapter

The Jev integration is considered complete when:

```text
ApplicationState
      |
      v
JevRouter
      |
      v
Jev API
      |
      v
typed output
      |
      v
DecisionResult
```

works for:

- valid response
- timeout
- rate limit
- malformed response
- authentication failure
- retry
- cancellation

and every outcome is logged.

---

# 43. Definition of Done for Benchmark

A benchmark run is valid only if:

```text
same test dataset
same decision schema
same evaluation labels
same concurrency
same policy engine
same measurement definitions
```

are used across compared systems.

---

# 44. Recommended Build Order

## Phase 1

Build:

```text
models
router interface
result object
dataset loader
policy engine
```

## Phase 2

Build:

```text
RulesRouter
MockJevRouter
benchmark runner
metrics recorder
```

## Phase 3

Build:

```text
LLMSingleRouter
LLMParallelRouter
```

## Phase 4

Build:

```text
JevRouter
```

## Phase 5

Implement:

```text
quality metrics
latency metrics
cost metrics
calibration
```

## Phase 6

Run:

```text
baseline experiment
```

## Phase 7

Run:

```text
decision scaling
fast path
context scaling
```

## Phase 8

Build:

```text
dashboard
README results
research report
```

---

# 45. MVP Technology Stack

## Language

```text
Python 3.11+
```

## API / orchestration

```text
FastAPI
asyncio
httpx
Pydantic
```

## Data

```text
pandas
pyarrow
JSONL
CSV
```

## Evaluation

```text
scikit-learn
NumPy
SciPy
```

## Testing

```text
pytest
pytest-asyncio
```

## Visualization

```text
matplotlib
```

## Configuration

```text
YAML
Pydantic Settings
```

---

# 46. Security Requirements

The benchmark may process support-style data.

Therefore:

- do not commit API keys
- hash or remove customer identifiers
- do not store authentication headers
- sanitize logs
- keep synthetic/authorized data only
- avoid storing unnecessary personal information
- provide a `redact_state()` utility

Example:

```python
def redact_state(state):
    return {
        "customer_tier": state.customer_tier,
        "product": state.product,
        "region": state.region,
        "ticket_text": "[REDACTED]"
    }
```

---

# 47. Performance Instrumentation

Use a monotonic timer for latency.

Conceptually:

```python
start = perf_counter()

result = await router.decide(state)

elapsed = (perf_counter() - start) * 1000
```

Wall-clock timestamps may be used for logging but should not be the source of duration calculations.

---

# 48. Cache Policy for MVP

Do not introduce a production cache layer.

A cache may exist only as part of the fast-path experiment.

If present:

```text
key = deterministic_hash(normalized_state)
```

The cache must be reported separately from Jev's contribution.

---

# 49. Policy Versioning

Every decision result must reference:

```text
policy_version
```

Example:

```text
policy_version = "support-policy-1.0"
```

This prevents a policy change from silently invalidating historical benchmark results.

---

# 50. Prompt Versioning

Every LLM benchmark must reference:

```text
prompt_version
```

Example:

```text
prompt_version = "llm-control-v1.2"
```

Prompt changes require a new experiment version.

---

# 51. Jev Configuration Versioning

Jev question definitions must be versioned.

Example:

```text
jev_schema_version = "jev-support-v1"
```

Any modification to:

- questions
- context
- decision options
- confidence interpretation

requires a new benchmark version.

---

# 52. Benchmark Naming

Use immutable experiment identifiers:

```text
baseline-v1
scaling-v1
fastpath-v1
context-v1
dependency-v1
e2e-v1
```

Do not overwrite results.

---

# 53. Core Engineering Invariants

The following must always hold:

### Invariant 1

```text
One input state -> one normalized DecisionResult
```

### Invariant 2

```text
Policy engine is router-independent
```

### Invariant 3

```text
Test labels never enter router prompts
```

### Invariant 4

```text
Evaluation code never modifies predictions
```

### Invariant 5

```text
Raw benchmark records are immutable
```

### Invariant 6

```text
All router costs are observable
```

---

# 54. Failure Conditions

The benchmark should be marked invalid if:

- different test examples were used
- one system had access to additional ground truth
- router costs were omitted
- retries were hidden
- failed requests were dropped
- prompt tuning used test labels
- concurrency differed without documentation
- quality definitions changed between systems
- manual post-processing was applied to only one system

---

# 55. Primary Dashboard Contract

The dashboard must show only measured data.

Required panels:

## System Comparison

```text
Rules
LLM Single
LLM Parallel
Jev
```

Metrics:

```text
p50
p95
cost
accuracy
F1
cost/correct
throughput
```

## Intelligence Cost Curve

```text
2 → 4 → 6 → 8 → 12 decisions
```

## Control-Plane Economics

```text
control-plane cost
total AI cost
control-plane tax
```

## Reliability

```text
schema failures
bad-send rate
over-escalation rate
```

---

# 56. Research Output

The final MVP should be able to generate a compact report containing:

```text
1. Experimental setup
2. Dataset
3. Baselines
4. Methodology
5. Latency results
6. Cost results
7. Quality results
8. Decision scaling
9. Fast-path analysis
10. Limitations
11. Conclusions
```

---

# 57. Expected Final Result Format

Do not hardcode any expected winner.

Use a template:

```text
At the selected quality threshold:

Jev:
- control-plane latency: X ms p95
- control-plane cost: $X / 1K decisions
- decision throughput: X decisions/s
- cost per correct decision: $X

Conventional LLM:
- control-plane latency: X ms p95
- control-plane cost: $X / 1K decisions
- decision throughput: X decisions/s
- cost per correct decision: $X
```

The numbers are populated only after the benchmark executes.

---

# 58. Engineering Interpretation

The project should distinguish:

### Model-level result

```text
Jev itself is faster/cheaper at the decision task.
```

from:

### System-level result

```text
Using Jev changed the economics of the complete AI application.
```

A model-level advantage does not automatically imply a system-level advantage.

This distinction is central to JevRoute.

---

# 59. V2 Boundary

After MVP completion, the architecture can be extended through adapters.

Possible additions:

```text
RouteLLMRouter
BedrockRouter
OpenRouterRouter
Traditional ML classifier
additional workloads
shadow oracle
production trace replay
```

These must be added without changing the core benchmark interface.

---

# 60. Final Technical Principle

JevRoute is fundamentally an **experimental measurement system**.

The architecture is intentionally simple:

```text
STATE
  |
  v
ROUTER
  |
  v
DECISION
  |
  v
SHARED POLICY
  |
  v
EVALUATION
  |
  v
MEASUREMENT
```

The project succeeds when this loop can be executed reproducibly across multiple decision architectures and the resulting tradeoffs can be expressed in measurable engineering terms.

---

# 61. Final MVP Statement

> **JevRoute is a controlled, reproducible benchmark for measuring whether Jev can perform structured AI control decisions with a lower cost and latency footprint than conventional LLM-based control logic while maintaining an explicitly defined quality threshold.**

The benchmark does not assume that Jev is revolutionary.

It provides the instrumentation required to determine whether the underlying architectural hypothesis is true.
