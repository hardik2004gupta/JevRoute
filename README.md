# JevRoute

### Measuring the Economics of System-One Intelligence

Modern AI systems generate with large autoregressive models. But around every generation step sits a second workload: **decide.**

JevRoute benchmarks whether these structured software decisions require generative inference at all — or whether a specialized System-One model can deliver equivalent quality at a lower control-plane cost.

---

## What JevRoute Is

A reproducible benchmark harness and experimental control-plane implementation. It provides a common interface for four decision mechanisms:

| System | Description | Phase |
|--------|-------------|-------|
| **Rules** | Deterministic keyword/regex control logic | ✅ Phase 2 |
| **LLM Single** | One LLM call producing all structured decisions | ✅ Phase 2 |
| **LLM Parallel** | Independent async LLM call per decision | ✅ Phase 2 |
| **Jev** | Specialized System-One decision model | Phase 3 |

The benchmark measures: latency · cost · correctness · calibration · throughput · control-plane tax.

---

## Phase 2 Status

Phase 2 delivers a real, reproducible benchmark engine:

- ✅ `RulesRouter` (deterministic keyword/regex baseline, `rules-v1`)
- ✅ `LLMSingleRouter` (single-call structured output, `llm-single-v1`, prompt `llm-control-v1.0`)
- ✅ `LLMParallelRouter` (6 concurrent independent calls, `llm-parallel-v1`)
- ✅ Generic async LLM provider boundary (any OpenAI-compatible endpoint)
- ✅ `WorkloadLoader` (strict train/validation/test separation, ground truth never in state)
- ✅ `BenchmarkRunner` (router-agnostic, configurable concurrency, asyncio)
- ✅ `ResultRecorder` (append-only JSONL, crash-safe, immutable records)
- ✅ Evaluation engine: quality, latency (p50/p95/p99), cost, throughput, calibration
- ✅ 10-example deterministic CI fixture (train/validation/test splits)
- ✅ `experiments/baseline.yaml` experiment configuration
- ✅ Raw JSONL → aggregate CSV → experiment metadata pipeline
- ✅ 84 passing tests (unit + integration + benchmark)
- ✅ Frontend Phase 1 dashboard remains intact (no fake data)

**Intentionally not implemented yet:**
- Real Jev API integration (`JevRouter`) — Phase 3
- Scaling, fast-path, context, dependency experiments — Phases 3–4
- Dashboard data wiring — Phase 4

---

## Local Development

**Requirements:** Python 3.11+, Node.js 18+

### Installation

```bash
pip install -e ".[dev]"
```

### Backend API

```bash
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

---

## Running Benchmarks

### Local mock benchmark (no API keys required)

Run using `RulesRouter` and `MockJevRouter` against the 10-example CI fixture:

```bash
python -c "
import asyncio
from jevroute.benchmark.config import BenchmarkConfig
from jevroute.benchmark.loader import WorkloadLoader
from jevroute.benchmark.runner import BenchmarkRunner
from jevroute.routers.rules import RulesRouter, ROUTER_NAME, ROUTER_VERSION
from jevroute.routers.mock_jev import MockJevRouter, ROUTER_NAME as MOCK_NAME, ROUTER_VERSION as MOCK_VERSION

cfg = BenchmarkConfig.from_yaml('experiments/baseline.yaml')
runner = BenchmarkRunner(cfg, results_dir='results', datasets_dir='datasets', force=True)
loader = WorkloadLoader('datasets')
examples = loader.load(cfg.experiment.dataset, cfg.experiment.split)

async def run():
    agg = await runner.run(RulesRouter(), ROUTER_NAME, ROUTER_VERSION, examples=examples)
    print('Rules:', agg['accuracy'], agg['p50_latency_ms'], 'ms p50')
    agg2 = await runner.run(MockJevRouter(), MOCK_NAME, MOCK_VERSION, examples=examples)
    print('MockJev:', agg2['accuracy'], agg2['p50_latency_ms'], 'ms p50')

asyncio.run(run())
"
```

### Real LLM benchmark

Configure your provider in `.env`:

```bash
cp .env.example .env
# Edit .env and set:
# LLM_API_KEY=sk-...
# LLM_BASE_URL=https://api.openai.com/v1
# MODEL_NAME=gpt-4o-mini
# MODEL_INPUT_PRICE=0.00015   (per 1K tokens)
# MODEL_OUTPUT_PRICE=0.0006   (per 1K tokens)
```

Then add `llm_single` and `llm_parallel` to the routers list in `experiments/baseline.yaml` and run as above.

This is a benchmark run — results are real but note it is running on the 10-example CI fixture, not the research dataset.

---

## Results Storage

```
results/
├── raw/
│   └── baseline-v1/
│       ├── rules.jsonl          ← immutable raw observations
│       ├── mock_jev.jsonl
│       ├── llm-single.jsonl     ← after LLM run
│       └── llm-parallel.jsonl
├── aggregate/
│   └── baseline-v1.csv         ← one row per router
└── metadata/
    └── baseline-v1.json        ← run metadata, versions, config
```

Raw JSONL records are never modified after write. Each record contains:
- `prediction` (router output)
- `ground_truth` (kept separate; never passed to router)
- `final_action` (after shared policy engine)
- `router_latency_ms`, `total_latency_ms` (perf_counter)
- `input_tokens`, `output_tokens`, `estimated_cost_usd`
- `error_type` (if failed; failures remain in results)

---

## Tests

```bash
pytest
```

```bash
pytest tests/unit/          # domain models, routers, evaluation
pytest tests/integration/   # FastAPI endpoints
pytest tests/benchmark/     # full pipeline with CI fixture
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
  ├── RulesRouter     (Phase 2: deterministic baseline)
  ├── LLMSingleRouter (Phase 2: single-call LLM)
  ├── LLMParallelRouter (Phase 2: 6 concurrent calls)
  ├── MockJevRouter   (CI/dev only, never in published results)
  └── JevRouter       (Phase 3)
      ↓
DecisionResult (normalized, router-agnostic)
      ↓
PolicyEngine (shared, router-independent)
      ↓
BenchmarkRunner → ResultRecorder → raw JSONL
      ↓
Evaluation → aggregate CSV + metadata JSON
```

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

Copy `.env.example` to `.env`. No API keys are required for mock/rules-only runs.

```bash
cp .env.example .env
```

---

## Research Question

> **When AI systems spend computation deciding what to do rather than generating what to say, does a System-One decision primitive materially change the economics of the control plane?**

That is the question JevRoute exists to answer.
