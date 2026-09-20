# JevRoute — Release Package

**Version:** 0.1.0-harness-complete  
**Date:** 2026-09-20  
**Commit:** e480a5b  
**Status:** EMPIRICALLY PARTIAL — benchmark harness complete, empirical runs blocked

---

## What JevRoute Measures

JevRoute is a controlled benchmark harness for measuring the economics of System-One intelligence in AI control-plane workloads.

It compares four decision systems on the same structured decision task:

| System | Description |
|--------|-------------|
| RULES | Deterministic keyword/regex rules |
| LLM SINGLE | One structured-output LLM call |
| LLM PARALLEL | Six concurrent per-dimension LLM calls |
| JEV | Jev System-One decision model |

Measurement dimensions: quality, latency, token usage, cost, throughput, reliability, calibration, and control-plane economics.

---

## What Dataset Was Used

**Current state:** Only the 10-example synthetic CI fixture (`datasets/test/benchmark_fixture.jsonl`) has been used. This is for pipeline validation only.

**Required for research conclusions:** A 1,000–2,000 example labeled dataset following the protocol in `docs/DATASET.md`. This dataset does not yet exist.

**No research results from this release are based on a real benchmark dataset.**

---

## What Systems Were Compared

The mock run in `results/raw/baseline-v1/` contains:
- `rules` — deterministic rules baseline (real implementation)
- `mock_jev` — **synthetic mock**, NOT real Jev performance

`llm_single`, `llm_parallel`, and real `jev` were not run (credentials unavailable).

---

## How to Reproduce

### Prerequisites
```
Python 3.11+
pip install -e ".[dev]"
```

### Run tests (no credentials required)
```bash
pytest
```
Expected: 108 passed, 0 failed

### Run dashboard
```bash
cd dashboard && npm install && npm run dev
```
Visit: http://localhost:3000

### Run mock benchmark (no credentials required)
```bash
python -m jevroute.benchmark.runner --config experiments/baseline.yaml
```

### Run with real providers (requires credentials)
Configure `.env` with `LLM_API_KEY`, `MODEL_NAME`, `JEV_API_KEY`, `JEV_BASE_URL`  
See `docs/REPRODUCTION.md` for full instructions.

---

## What Experiments Were Run

| Experiment | Status | Note |
|------------|--------|------|
| baseline-v1 | PARTIAL (mock) | rules + mock_jev on 10 examples |
| scaling-v1 | BLOCKED | Requires real provider + dataset |
| fastpath-v1 | BLOCKED | Requires real Jev |
| context-v1 | BLOCKED | Requires real provider + dataset |
| dependency-v1 | BLOCKED | Requires real provider |
| e2e-v1 | BLOCKED | Requires real generation provider |

---

## What Remains Blocked

1. **Real Jev API** — JEV_API_KEY + confirmed endpoint (OQ-001)
2. **Real LLM** — LLM_API_KEY + MODEL_NAME
3. **Research dataset** — 1,000–2,000 labeled examples (OQ-003)
4. **Real generation provider** — for e2e economics (e2e-v1)

---

## Limitations

1. No empirical results exist for the research benchmark
2. All displayed numbers in the dashboard for LLM/Jev rows are `N/A` (not fabricated)
3. The mock_jev results exist to validate pipeline correctness, not to represent Jev performance
4. The 10-example fixture results are not statistically meaningful for any research claim
5. Jev API endpoint assumed to be `POST /v1/decide` (unconfirmed per OQ-001)
6. Jev pricing assumed at $0.00/token (unconfirmed per OQ-002)

---

## Security

No API keys, credentials, or authentication headers are present in this release package.  
`.env` is not included.
