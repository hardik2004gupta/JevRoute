# JevRoute — Dataset Status

## Current State

**No research benchmark dataset exists.**

The only available dataset is a 10-example synthetic CI fixture used exclusively for pipeline validation.

| Dataset | Examples | Hash | Status |
|---------|----------|------|--------|
| CI fixture (test split) | 10 | `32d80883d67060ff...` | PRESENT — CI only |
| Research benchmark | 1,000–2,000 | N/A | NOT YET AVAILABLE |

## Research Dataset Requirements

See `docs/DATASET.md` for the full protocol. In summary:

- 1,000–2,000 labeled examples from AI customer-support control-plane domain
- `train / validation / test` splits
- Test split frozen before any system tuning
- Annotator count, agreement metric, and construction protocol documented
- Only synthetic or authorized data (no real customer PII)

## Blocker

OQ-003 (Dataset Source and Construction) is unresolved. No research conclusions are possible until this dataset is constructed, quality-gated, and frozen.
