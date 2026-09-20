# Jev API Contract Documentation

**Status as of Phase 7: PARTIALLY KNOWN — see UNKNOWN fields below.**

This document records what is known and unknown about the Jev API based on information available during implementation. Fields marked **UNKNOWN** must be confirmed before any empirical benchmark run involving the JevRouter.

---

## Open Questions

| ID     | Question                                  | Status     |
|--------|-------------------------------------------|------------|
| OQ-001 | HTTP endpoint path and method             | UNRESOLVED |
| OQ-002 | Token pricing (input / output per token)  | UNRESOLVED |

---

## Assumed Request Contract

The following is **assumed** from context. Not confirmed.

```
POST {JEV_BASE_URL}/v1/decide
Authorization: Bearer {JEV_API_KEY}
Content-Type: application/json

{
  "customer_tier": "...",
  "product": "...",
  "region": "...",
  "ticket_subject": "...",
  "ticket_body": "...",
  "draft_reply": "..."
}
```

**UNKNOWN:** Whether the path is `/v1/decide`, `/decide`, `/api/decide`, or something else.
**UNKNOWN:** Whether authentication uses `Bearer` token, API key header (`X-API-Key`), or another mechanism.

---

## Assumed Response Contract

The JevRouter implementation parses the following fields from the response body:

| Field              | Type    | Description                                      | Status   |
|--------------------|---------|--------------------------------------------------|----------|
| `severity`         | string  | P1/P2/P3/P4                                      | ASSUMED  |
| `category`         | string  | Billing/Bug/Feature/Account/Other                | ASSUMED  |
| `policy_violation` | bool    | Whether the draft violates policy                | ASSUMED  |
| `hallucination_risk` | float | [0.0, 1.0]                                      | ASSUMED  |
| `tone_risk`        | float   | [0.0, 1.0]                                       | ASSUMED  |
| `action`           | string  | SEND/HOLD/ESCALATE                               | ASSUMED  |
| `confidence`       | float   | [0.0, 1.0] — may be absent                      | UNKNOWN  |
| `input_tokens`     | int     | Reported by Jev for cost calculation             | UNKNOWN  |
| `output_tokens`    | int     | Reported by Jev for cost calculation             | UNKNOWN  |

**UNKNOWN:** Whether Jev reports token counts at all, or whether they must be estimated.
**UNKNOWN:** Whether response envelope wraps the above in a `result` or `data` key.

---

## Pricing

| Parameter         | Default | Status   |
|-------------------|---------|----------|
| Input price/token | $0.00   | UNKNOWN — placeholder |
| Output price/token | $0.00  | UNKNOWN — placeholder |

Set `JEV_INPUT_PRICE` and `JEV_OUTPUT_PRICE` environment variables once confirmed.

Until OQ-002 is resolved, all Jev cost figures in benchmark results will be reported as `$0.00` and flagged as UNCONFIRMED.

---

## Error Handling

The JevRouter implementation handles HTTP errors with retry logic (max 2 attempts, 250ms backoff). The following error classifications are used:

- `TIMEOUT`: request timeout
- `RATE_LIMIT`: HTTP 429
- `AUTHENTICATION`: HTTP 401/403
- `NETWORK`: connection error
- `SCHEMA_VALIDATION`: response does not match expected schema
- `PROVIDER_ERROR`: HTTP 5xx
- `INVALID_RESPONSE`: non-JSON or unexpected structure

---

## Configuration

```env
JEV_API_KEY=<your-api-key>
JEV_BASE_URL=<base-url>          # e.g. https://api.jev.ai
JEV_INPUT_PRICE=0.000001         # per token, once confirmed
JEV_OUTPUT_PRICE=0.000002        # per token, once confirmed
```

---

## Benchmark Validity Note

Per CLAUDE.md §6 Benchmark Fairness Rules and §7 Benchmark Validity Rules:

> All router token usage, latency, API calls, and retries are counted.

Until OQ-001 (endpoint) and OQ-002 (pricing) are resolved, any benchmark run using JevRouter produces results with:
- `estimated_cost_usd = 0.00` (not a valid economic measurement)
- `num_model_calls` = correct (attempt count is tracked regardless)
- `latency_ms` = correct (wall-clock measured with `time.perf_counter()`)

Any publication of Jev benchmark results must disclose which open questions were unresolved at the time of measurement.
