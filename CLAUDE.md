# CLAUDE.md — JevRoute Engineering Contract

This file is the permanent engineering contract for all Claude Code sessions working on JevRoute.

---

## 1. Project Identity

**JevRoute** is a controlled, reproducible benchmark harness and experimental control-plane implementation for measuring the economics of System-One intelligence in AI control-plane workloads.

It is NOT:
- a generic AI gateway
- a chatbot or consumer SaaS product
- a RAG platform
- a general-purpose agent framework
- a production model-routing platform
- a dashboard pretending to be the product

The benchmark harness is the primary artifact. The dashboard is a visualization layer over measured results.

---

## 2. Strict Engineering Contract

The following two files constitute the strict core engineering authority for every implementation decision:

```
CLAUDE.md
JevRoute_MVP_Technical_Architecture.md
```

**Both files are mandatory constraints.** Future implementation must not knowingly violate either.

---

## 3. Contract Precedence

### Level 1 — Strict Engineering Contract (mandatory)
```
CLAUDE.md
JevRoute_MVP_Technical_Architecture.md
```

### Level 2 — Project Context / Research Narrative (must be respected, cannot override Level 1)
```
JevRoute_Project_Documentation.md
```
Provides: product/research context, hypotheses, positioning, experimental intent.

### Level 3 — Implementation Decisions
May be chosen by the engineer/agent only when they do not conflict with Levels 1 or 2.
When genuinely ambiguous, prefer the smallest solution consistent with the technical architecture.

---

## 4. DO NOT Rewrite the Architecture

Do NOT silently simplify or replace `JevRoute_MVP_Technical_Architecture.md`.

Do NOT introduce:
- unnecessary databases (no Redis, no PostgreSQL unless justified)
- microservices or distributed infrastructure
- GPU orchestration
- RAG infrastructure
- multi-agent infrastructure
- production gateway functionality
- Kubernetes or container orchestration
- unrelated cloud services or abstractions

The MVP is intentionally constrained, simple, and benchmark-oriented.

---

## 5. Core Engineering Invariants

Violations of these invariants are engineering bugs:

| # | Invariant |
|---|-----------|
| 1 | One input state → one normalized DecisionResult |
| 2 | Policy engine is router-independent |
| 3 | Test labels never enter router prompts |
| 4 | Evaluation code never modifies predictions |
| 5 | Raw benchmark records are immutable after run |
| 6 | All router costs are observable |

---

## 6. Benchmark Fairness Rules

These rules must be preserved in every implementation phase:

1. Every compared system receives equivalent application state.
2. Every system conforms to the same normalized DecisionResult schema.
3. The four benchmark participants are: Rules, LLM Single, LLM Parallel, Jev.
4. All router token usage, latency, API calls, and retries are counted.
5. The conventional LLM baseline must be a legitimate structured-output implementation (no strawman).
6. Parallel LLM execution must represent a competent async implementation.
7. Test data must never be used to tune prompts, rules, thresholds, or policies.
8. Raw observations must be recorded before deriving aggregate metrics.
9. Failed calls (timeouts, rate limits, schema failures, etc.) remain in results as failures.
10. Never silently drop errors.
11. The implementation must never assume Jev wins.
12. External vendor performance numbers must not be inserted into measured result tables.

---

## 7. Benchmark Validity Rules

A benchmark run is invalid if:
- different test examples were used across systems
- one system had access to additional ground truth
- router costs were omitted
- retries were hidden
- failed requests were dropped
- prompt tuning used test labels
- concurrency differed without documentation
- quality definitions changed between systems
- manual post-processing was applied to only one system

---

## 8. Architectural Boundaries

Clear separation must be maintained between:

```
models/          — ApplicationState, DecisionResult, enums
routers/         — base interface, four implementations + MockJev
policy/          — shared PolicyEngine (router-independent)
benchmark/       — runner, recorder, config (router-agnostic)
evaluation/      — quality, latency, cost, calibration, throughput
experiments/     — YAML configs, experiment runners
datasets/        — raw, processed, train/validation/test splits
results/         — raw JSONL, aggregate CSV, figures
dashboard/       — visualization layer only
tests/           — unit, integration, benchmark
```

Rules:
- Benchmark runner must be router-agnostic.
- Policy engine must be router-independent.
- Jev-specific code must be isolated behind the JevRouter adapter.
- Provider/API-specific logic must not leak into benchmark/evaluation code.
- Cost calculation must be centralized (never hardcoded throughout codebase).
- Latency measurement must use `time.perf_counter()` for duration calculations.
- Configuration must be versioned (YAML, committed with results).
- Results must remain reproducible.

---

## 9. Technology Baseline

Use this stack. Do not replace without a concrete architectural reason.

| Category | Tools |
|----------|-------|
| Language | Python 3.11+ |
| API/Async | FastAPI, asyncio, httpx, Pydantic |
| Data | pandas, pyarrow, JSONL, CSV |
| Evaluation | scikit-learn, NumPy, SciPy |
| Testing | pytest, pytest-asyncio |
| Visualization | matplotlib |
| Configuration | YAML, Pydantic Settings |

---

## 10. Data Rules

- Datasets use `train / validation / test` splits.
- The workload loader must reject accidental use of test labels during router execution.
- Test set is frozen: never use it to tune prompts, rules, or thresholds.
- Raw JSONL records are immutable after a run completes.
- Aggregate results use CSV + experiment metadata JSON.
- A database is NOT required for the MVP.
- Results must include: dataset version, code commit SHA, router version, prompt version, schema version, experiment config, model/provider identifier, benchmark timestamp, concurrency, environment metadata.

---

## 11. Security Rules

- Never commit API keys or secrets.
- Hash or remove customer identifiers from datasets.
- Never log authentication headers or secrets.
- Sanitize logs before persistence.
- Use only synthetic or authorized data.
- Implement `redact_state()` utility.
- Environment variables: `JEV_API_KEY`, `LLM_API_KEY`, `MODEL_NAME`, pricing vars — all in `.env` (gitignored).

---

## 12. Testing Rules

Every phase must include tests before completion.

- **Unit tests**: state validation, schema validation, policy rules, cost calculations, latency recording, result aggregation, calibration calculations.
- **Integration tests**: router adapters, API error handling, structured-output parsing, benchmark runner.
- **Benchmark tests**: tiny deterministic fixture (10 examples), all routers execute, all results normalize, metrics aggregate correctly.
- `MockJevRouter` must exist for CI and local development. It must never appear in published benchmark results.
- Synthetic fixtures in `tests/fixtures/` allow CI to run without paid APIs.
- Tests must pass before any phase is declared complete.

---

## 13. UI / Dashboard Rules

The dashboard is a visualization layer, not the product.

**Visual direction**: Linear + Vercel + modern observability platform + research instrumentation console — restrained light theme.

**Use:**
- warm off-white / very light gray background
- white surfaces
- graphite / near-black typography
- subtle borders, restrained shadows
- generous whitespace, precise spacing
- monospace typography for metrics and configuration
- clean charts, minimal visual noise

**Avoid:**
- dark cyberpunk aesthetics, neon, purple/blue AI gradients
- glassmorphism everywhere
- excessive rounded cards, cartoon graphics, robot/AI imagery
- decorative 3D elements, meaningless animations
- fake metrics, excessive dashboard chrome

**Information hierarchy:**
1. Benchmark status
2. System comparison (Rules / LLM Single / LLM Parallel / Jev)
3. Intelligence Cost Curve (central visual concept)
4. Quality × Cost Frontier
5. Control-Plane Economics
6. Reliability
7. Experiment history
8. Methodology / reproducibility

**Data integrity rule:** The frontend must never invent benchmark data. All numbers must originate from the benchmark result layer. Unavailable fields are `null` or `N/A`.

---

## 14. Development Rules

- Implement only the phase you are currently assigned unless explicitly instructed otherwise.
- Do not make unrelated refactors during feature implementation.
- Do not silently expand scope.
- Do not modify benchmark methodology while implementing UI.
- Do not modify architecture merely for convenience.
- Prefer the smallest solution consistent with the technical architecture.
- Do not create unnecessary files to make the tree look complete.

---

## 15. Phase Completion Rules

Every phase must end with:
1. Tests passing
2. Validation of benchmark invariants
3. `git diff` inspection and summary
4. Documentation update (IMPLEMENTATION_MAP.md if needed)

---

## 16. Phase Discipline

Phases defined in `docs/PHASE_PLAN.md`:

- **Phase 1**: Foundation + UI Shell
- **Phase 2**: Benchmark Engine
- **Phase 3**: Jev + Experiments
- **Phase 4**: Research Observatory / Final Dashboard

Do not implement Phase N+1 while working on Phase N unless explicitly instructed.

---

## 17. Versioning Rules

Every benchmark run must carry:
- `prompt_version` (e.g., `"llm-control-v1.2"`) — prompt changes require new experiment version
- `policy_version` (e.g., `"support-policy-1.0"`) — policy changes invalidate historical comparisons
- `jev_schema_version` (e.g., `"jev-support-v1"`) — Jev question definition changes require new benchmark version
- `decision_schema_version` (e.g., `"1.0"`)
- Experiment IDs are immutable: `baseline-v1`, `scaling-v1`, `fastpath-v1`, etc.
- Do not overwrite results — use new experiment versions.

---

## 18. Performance Instrumentation Rule

Always use `time.perf_counter()` for latency duration calculations.

```python
start = perf_counter()
result = await router.decide(state)
elapsed_ms = (perf_counter() - start) * 1000
```

Wall-clock timestamps are for logging only, never for duration calculations.

---

## 19. Concurrency Rules

- Benchmark concurrency must be identical across compared systems unless the experiment explicitly studies concurrency scaling.
- MVP baseline recommendation: `concurrency = 8`.
- Concurrency must be documented in every result bundle.
- `LLMParallelRouter` uses async concurrency; total wall-clock latency, aggregate tokens, and aggregate cost must all be measured (parallel execution is not free).

---

## 20. Error Handling Rules

Router failures are classified:
```
TIMEOUT | RATE_LIMIT | AUTHENTICATION | NETWORK | SCHEMA_VALIDATION | PROVIDER_ERROR | INVALID_RESPONSE | INTERNAL_ERROR
```

Failed requests remain in results as failed observations. Retries are:
- explicitly configured
- bounded (max 2 attempts, 250ms backoff recommended)
- recorded in latency and cost

---

## 21. Core Optimization Directive

Optimize for:
- correctness
- reproducibility
- measurement integrity
- architectural clarity
- testability
- observability
- maintainability
- UI clarity

Not for:
- feature count
- infrastructure complexity
- visual gimmicks
- premature optimization

The benchmark must remain scientifically defensible. The UI must make evidence easier to understand, never manufacture or distort evidence.
