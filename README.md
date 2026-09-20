# JevRoute

### Measuring the Economics of System-One Intelligence

Modern AI systems generate with large autoregressive models. But around every generation step sits a second workload: **decide.**

JevRoute benchmarks whether these structured software decisions require generative inference at all — or whether a specialized System-One model can deliver equivalent quality at a lower control-plane cost.

---

## What JevRoute Is

A reproducible benchmark harness and experimental control-plane implementation. It provides a common interface for four decision mechanisms:

| System | Description |
|--------|-------------|
| **Rules** | Deterministic keyword/regex control logic |
| **LLM Single** | One LLM call producing all structured decisions |
| **LLM Parallel** | Independent async LLM call per decision |
| **Jev** | Specialized System-One decision model |

The benchmark measures: latency · cost · correctness · calibration · throughput · control-plane tax.

The goal is not to prove that Jev wins. The goal is to measure when System-One intelligence changes the economics of AI control.

---

## Phase 1 Status

Phase 1 establishes the runnable foundation:

- ✅ Domain models (`ApplicationState`, `DecisionResult`, enums)
- ✅ Router abstraction (`DecisionRouter` Protocol)
- ✅ `MockJevRouter` (deterministic, no API key required)
- ✅ Shared `PolicyEngine` (router-independent)
- ✅ Configuration foundation (Pydantic Settings + `.env`)
- ✅ FastAPI application (`/health`, `/api/v1/status`, `/api/v1/decide`)
- ✅ Next.js dashboard shell (light research-instrument design, no fake data)
- ✅ 29 passing tests (unit + integration)

**Intentionally not implemented yet:**
- Real LLM integration (`LLMSingleRouter`, `LLMParallelRouter`) — Phase 2
- Real Jev API integration (`JevRouter`) — Phase 3
- Benchmark runner and dataset loader — Phase 2
- Experiment execution — Phases 2–3
- Dashboard data wiring — Phase 4

---

## Local Development

**Requirements:** Python 3.11+, Node.js 18+

### Backend

```bash
# Install
pip install -e ".[dev]"

# Run (mock router, no API keys needed)
uvicorn jevroute.api.app:app --reload
# → http://localhost:8000
# → http://localhost:8000/api/docs
```

### Frontend

```bash
cd dashboard
npm install
npm run dev
# → http://localhost:3000
```

### Tests

```bash
pytest
```

### Lint

```bash
ruff check src/ tests/
```

---

## Architecture

```
ApplicationState
      ↓
DecisionRouter (Protocol)
  ├── MockJevRouter   (Phase 1: CI/dev only)
  ├── RulesRouter     (Phase 2)
  ├── LLMSingleRouter (Phase 2)
  ├── LLMParallelRouter (Phase 2)
  └── JevRouter       (Phase 3)
      ↓
DecisionResult (normalized, router-agnostic)
      ↓
PolicyEngine (shared, router-independent)
      ↓
PolicyResult → final action
```

Results storage: raw JSONL → aggregate CSV → dashboard.

---

## Engineering Contract

See [`CLAUDE.md`](CLAUDE.md) and [`JevRoute_MVP_Technical_Architecture.md`](JevRoute_MVP_Technical_Architecture.md) — the strict core engineering authority.

Key invariants:
1. One input state → one normalized `DecisionResult`
2. Policy engine is router-independent
3. Test labels never enter router prompts
4. Evaluation code never modifies predictions
5. Raw benchmark records are immutable
6. All router costs are observable

---

## Configuration

Copy `.env.example` to `.env` and set values as needed. No API keys are required for Phase 1.

```bash
cp .env.example .env
```

---

## Research Question

> **When AI systems spend computation deciding what to do rather than generating what to say, does a System-One decision primitive materially change the economics of the control plane?**

That is the question JevRoute exists to answer.
