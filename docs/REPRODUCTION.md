# JevRoute — Reproduction Guide

**Objective:** Document exactly what is reproducible today, what requires external credentials, and what requires a full research dataset.

---

## Environment Requirements

| Requirement | Minimum | Notes |
|-------------|---------|-------|
| Python | 3.11+ | 3.14 tested |
| OS | Any (Windows, macOS, Linux) | Tested on Windows 11 |
| Network | None (mock mode) | Required for real LLM/Jev runs |
| Git | Any | For commit SHA in metadata |

---

## Step 1 — Clone and Install

```bash
git clone <repo-url> jevroute
cd jevroute
pip install -e ".[dev]"
```

The project uses a standard `pyproject.toml`. All dependencies are pinned in `requirements*.txt` if present, otherwise installed from `pyproject.toml`.

---

## Step 2 — Configure Credentials

```bash
cp .env.example .env
# Edit .env with your credentials (never commit .env)
```

The `.env.example` file documents every required variable. Variables required for mock-only runs:

```
# No credentials required for mock mode
```

Variables required for real LLM runs:

```
LLM_API_KEY=...
MODEL_NAME=...
```

Variables required for real Jev runs:

```
JEV_API_KEY=...
JEV_BASE_URL=https://api.jev.ai   # assumption — verify against actual API docs
```

---

## Step 3 — Run Tests (No Credentials Required)

```bash
pytest
```

Expected result: **108 tests pass, 0 fail** (as of Phase 5 commit).

Tests use `FakeModelClient`, `FakeJevClient`, and `MockJevRouter` — no network access, no paid API calls.

---

## Step 4 — Start the Backend API

```bash
uvicorn jevroute.api.app:app --reload
```

Visit: `http://localhost:8000/api/docs` for the OpenAPI documentation.

---

## Step 5 — Start the Dashboard

```bash
cd dashboard
npm install
npm run dev
```

Visit: `http://localhost:3000`

The dashboard will show all experiments as `NOT_RUN` until benchmark runs complete.

---

## Step 6 — Run a Benchmark (Mock Mode, No Credentials)

The baseline experiment uses `mock_jev` and `rules` by default when real credentials are unavailable:

```bash
python -m jevroute.benchmark.runner --config experiments/baseline.yaml
```

Results are written to:
```
results/raw/baseline-v1/rules.jsonl
results/raw/baseline-v1/mock_jev.jsonl
results/aggregate/baseline-v1.csv
results/metadata/baseline-v1.json
```

After running, reload the dashboard to see the `baseline-v1` experiment as `COMPLETE`.

---

## Step 7 — Run with Real LLM Providers (Requires Credentials)

With `LLM_API_KEY` and `MODEL_NAME` set in `.env`, the LLM routers are available:

```bash
# The config specifies which routers to use
python -m jevroute.benchmark.runner --config experiments/baseline.yaml
```

To include all four benchmark participants, add `llm_single` and `llm_parallel` to the experiment config's `routers` list, or create a new experiment config.

---

## Step 8 — Run with Real Jev (Requires Credentials + API Documentation)

See [docs/OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) OQ-001 and OQ-002 for the current status of Jev API integration. The `HttpxJevClient` assumes `POST {JEV_BASE_URL}/v1/decide` — verify this against actual Jev API documentation before running.

With credentials and correct endpoint:
```bash
# JEV_API_KEY must be set in .env
python -m jevroute.benchmark.runner --config experiments/baseline.yaml
```

---

## What Is and Is Not Reproducible Today

| Item | Reproducible? | Blocker |
|------|--------------|---------|
| All 108 unit/integration tests | YES | None |
| Mock benchmark run (rules + mock_jev) | YES | None |
| Dashboard rendering (empty states) | YES | None |
| LLM Single / LLM Parallel runs | BLOCKED | Requires LLM_API_KEY + MODEL_NAME |
| Real Jev runs | BLOCKED | Requires JEV_API_KEY + confirmed API interface (OQ-001) |
| Full 1,000–2,000 example benchmark | BLOCKED | Research dataset not yet constructed (OQ-003) |
| Intelligence Cost Curve (scaling-v1) | BLOCKED | Requires real provider for meaningful results |
| Control-Plane Tax (e2e-v1) | PARTIAL | SimulatedGeneration only; real provider needed for actual economics |
| Fast-path bypass study | BLOCKED | Requires real Jev for meaningful comparison |

---

## Reproducibility Metadata

Every benchmark run records:

```json
{
  "dataset_version": "0.1.0-synthetic",
  "dataset": "benchmark_fixture",
  "split": "test",
  "concurrency": 8,
  "router": "rules",
  "router_version": "rules-engine-1.0",
  "decision_schema_version": "1.0",
  "policy_version": "support-policy-1.0",
  "prompt_version": null,
  "experiment_id": "baseline-v1",
  "run_id": "baseline-v1__rules__20260920T120000Z",
  "git_sha": "2747c97",
  "python_version": "3.14.x",
  "platform": "...",
  "timestamp": "2026-09-20T12:00:00+00:00"
}
```

All fields required by CLAUDE.md §10 are present in every run bundle.

---

## Known Reproduction Limitations

1. The test fixture (10 examples) is insufficient for statistically meaningful conclusions.
2. `num_model_calls` is not populated for LLMParallelRouter (known gap; see PHASE5_AUDIT.md).
3. Exact latency values will differ between machines; aggregate statistics should be similar.
4. `FakeModelClient` and `FakeJevClient` produce deterministic outputs that do not represent real model behavior.
5. The `SimulatedGeneration` in `e2e-v1` uses fixed token counts and latency — real generation costs and latencies will differ.
