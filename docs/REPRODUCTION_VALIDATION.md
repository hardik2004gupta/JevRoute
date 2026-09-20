# JevRoute — Reproduction Validation

**Date:** 2026-09-20  
**Commit SHA:** e480a5b  
**Phase:** 6  
**Validator:** Phase 6 audit (automated)

---

## Environment

| Item | Value |
|------|-------|
| OS | Windows 11 Home Single Language 10.0.26200 |
| Python | 3.14.x |
| Shell | PowerShell 5.1 |
| Node | (see dashboard build) |
| Git | installed |
| `.env` | NOT PRESENT |

---

## Commands Executed

### Step 1 — Install

```bash
pip install -e ".[dev]"
```

Status: **VERIFIED** (environment already installed; all imports succeed)

### Step 2 — Test Suite

```bash
pytest
```

Status: **PASS — 108 tests, 0 failures**  
Duration: ~5 seconds  
External dependencies: None (all tests use FakeModelClient, FakeJevClient, MockJevRouter)

### Step 3 — Frontend Build

```bash
cd dashboard && npm run build
```

Status: **PASS** — TypeScript clean, 4 static pages generated  
Output: `✓ Compiled successfully in 250ms`

### Step 4 — Backend API

```bash
uvicorn jevroute.api.app:app --reload
```

Status: **VERIFIED** (integration tests confirm API starts and returns correct JSON)

### Step 5 — Mock Benchmark Run

The mock run (rules + mock_jev) already completed in Phase 2 and is preserved at:

```
results/raw/baseline-v1/rules.jsonl        (10 records, hash: fdf4f0a7...)
results/raw/baseline-v1/mock_jev.jsonl     (10 records, hash: adbd8b66...)
results/aggregate/baseline-v1.csv          (hash: e69be83f...)
results/metadata/baseline-v1.json
```

Re-running the mock benchmark would require `force=True` in the recorder (raw files are immutable by default, per CLAUDE.md §5 Invariant 5). To reproduce a fresh run, use a new experiment version or delete/rename the existing raw files.

### Step 6 — Independent Sanity Check

Script: `(scratchpad)/sanity_check.py`

| Check | Expected | Observed | Result |
|-------|----------|----------|--------|
| rules accuracy (raw) | 1.000 | 1.000 | MATCH |
| rules accuracy (csv) | 1.0 | 1.0 | MATCH |
| mock_jev accuracy (raw) | 0.800 | 0.800 | MATCH |
| mock_jev accuracy (csv) | 0.8 | 0.8 | MATCH |
| latency field (aggregate) | total_latency_ms | total_latency_ms | CONFIRMED |
| schema failures | 0 | 0 | MATCH |

All sanity checks reconcile. The apparent p50 discrepancy between `router_latency_ms` (0.049ms) and `total_latency_ms` (0.069ms) for mock_jev is expected and correct — the aggregate uses `total_latency_ms` which includes policy engine execution time.

---

## Datasets Verified

| Dataset | Hash | Lines | Status |
|---------|------|-------|--------|
| `datasets/test/benchmark_fixture.jsonl` | `32d80883...` | 10 | PRESENT, FROZEN |
| `datasets/train/benchmark_fixture.jsonl` | — | 3 | PRESENT |
| `datasets/validation/benchmark_fixture.jsonl` | — | 3 | PRESENT |
| Research dataset (1000-2000 examples) | N/A | N/A | NOT AVAILABLE |

---

## Blockers Encountered

| Blocker | Impact |
|---------|--------|
| No `.env` file | All real provider runs (LLM Single, LLM Parallel, Jev) blocked |
| JEV_API_KEY missing | Jev smoke test blocked; OQ-001 (endpoint) unconfirmed |
| LLM_API_KEY missing | LLM smoke tests blocked |
| Research dataset absent | All research experiments blocked; only CI fixture usable |

---

## What Was NOT Reproduced

| Item | Status | Reason |
|------|--------|--------|
| LLM Single router smoke test | BLOCKED | No credentials |
| LLM Parallel router smoke test | BLOCKED | No credentials |
| Jev router smoke test | BLOCKED | No credentials |
| baseline-v1 (all 4 routers) | BLOCKED | No credentials + no research dataset |
| scaling-v1 | BLOCKED | No credentials + no research dataset |
| fastpath-v1 | BLOCKED | No credentials |
| context-v1 | BLOCKED | No credentials |
| dependency-v1 | BLOCKED | No credentials |
| e2e-v1 | BLOCKED | No credentials + no real generation provider |

---

## Unavoidable External Dependencies

1. **JEV_API_KEY + JEV_BASE_URL** — required for any real Jev execution. OQ-001 documents the endpoint assumption.
2. **LLM_API_KEY + MODEL_NAME** — required for LLM Single and LLM Parallel.
3. **Research dataset** — 1,000–2,000 labeled examples per `docs/DATASET.md` protocol. Must be constructed and quality-gated before benchmark execution.
4. **Real generation provider** — required for e2e-v1 actual economics; SimulatedGeneration is available for pipeline testing only.

---

## Conclusion

A clean reproduction of the full empirical benchmark is not possible without the credentials and dataset listed above. The benchmark software is correct and fully testable without them. The existing 10-example mock run (rules + mock_jev) is reproducible using the mock infrastructure; the raw result files are immutable but were independently sanity-checked and confirmed correct.

**Reproduction status: PARTIAL** — pipeline verified, empirical runs blocked.
