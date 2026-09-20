// ─────────────────────────────────────────────────────────────────────────────
// JevRoute Demo Mode — Central Demo Data Source
//
// DEMO DATA STATUS (presentation layer):
//   MEASURED   — locally executed harness validation data (real observations)
//   PROJECTED  — deterministic projection for demonstration (not empirically executed)
//
// LIVE PROVIDER STATUS (separate concept):
//   AVAILABLE  — provider reachable and configured
//   UNAVAILABLE — provider unreachable or credentials absent
//
// !! This file must NEVER be written into canonical benchmark result artifacts.
// !! All PROJECTED values are constructed for interface demonstration ONLY.
// ─────────────────────────────────────────────────────────────────────────────

// Demo data status — what the demo visualization shows
export type DemoDataStatus = "MEASURED" | "PROJECTED";

// Live provider status — separate from demo data status
export type LiveProviderStatus = "AVAILABLE" | "UNAVAILABLE";

// Legacy alias kept for any remaining page.tsx ProvenanceBadge calls
export type Provenance = DemoDataStatus;

export interface DemoRouter {
  id: string;
  label: string;
  version: string;
  provenance: DemoDataStatus;
  provenanceNote: string;
  // Quality
  accuracy: number;
  macro_f1: number;
  severity_accuracy: number;
  action_accuracy: number;
  category_accuracy: number;
  schema_reliability: number;
  correct_decisions: number;
  // Latency (ms)
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  mean_ms: number;
  // Tokens
  input_tokens_per_decision: number;
  output_tokens_per_decision: number;
  model_calls_per_decision: number;
  // Cost (USD)
  cost_per_decision_usd: number;
  cost_per_1k_usd: number;
  cost_per_correct_usd: number;
  total_cost_usd: number;
  jev_pricing_note?: string;
  // Reliability
  schema_failure_rate: number;
  bad_send_rate: number;
  over_escalation_rate: number;
  missed_policy_rate: number;
  timeout_rate: number;
  retry_rate: number;
  // Throughput
  throughput_per_s: number;
  // Live provider (separate from demo data status)
  live_provider_status: LiveProviderStatus;
  live_provider_block_reason?: string;
}

export interface CostCurvePoint {
  decisions: number;
  rules_latency_ms: number;
  llm_single_latency_ms: number;
  llm_parallel_latency_ms: number;
  jev_latency_ms: number;
  rules_cost_usd: number;
  llm_single_cost_usd: number;
  llm_parallel_cost_usd: number;
  jev_cost_usd: number;
  rules_tokens: number;
  llm_single_tokens: number;
  llm_parallel_tokens: number;
  jev_tokens: number;
}

// ─── Pricing snapshot (from .env / experiments/baseline_research_v1.yaml) ────
const INPUT_PER_TOKEN  = 0.00015 / 1000;
const OUTPUT_PER_TOKEN = 0.00060 / 1000;

const JEV_INPUT_DEMO_PER_TOKEN  = 0.00005 / 1000;
const JEV_OUTPUT_DEMO_PER_TOKEN = 0.00020 / 1000;
const JEV_PRICING_NOTE =
  "DEMO PRICING — assumed $0.00005/1K input · $0.00020/1K output. NOT verified Jev pricing.";

const N = 75;

// ─── LLM Single token estimates ───────────────────────────────────────────────
const LS_IN  = 420;
const LS_OUT = 105;
const LS_COST_PER = LS_IN * INPUT_PER_TOKEN + LS_OUT * OUTPUT_PER_TOKEN;
const LS_ACC = 0.91;
const LS_CORRECT = Math.round(LS_ACC * N);

// ─── LLM Parallel token estimates ─────────────────────────────────────────────
const LP_IN  = 910;
const LP_OUT = 252;
const LP_COST_PER = LP_IN * INPUT_PER_TOKEN + LP_OUT * OUTPUT_PER_TOKEN;
const LP_ACC = 0.92;
const LP_CORRECT = Math.round(LP_ACC * N);

// ─── Jev token estimates ──────────────────────────────────────────────────────
const JV_IN  = 125;
const JV_OUT = 38;
const JV_COST_PER = JV_IN * JEV_INPUT_DEMO_PER_TOKEN + JV_OUT * JEV_OUTPUT_DEMO_PER_TOKEN;
const JV_ACC = 0.944;
const JV_CORRECT = Math.round(JV_ACC * N);

// ─── Rules (MEASURED from harness validation 2026-09-20) ─────────────────────
const RU_ACC = 0.907;
const RU_CORRECT = Math.round(RU_ACC * N);

export const DEMO_ROUTERS: DemoRouter[] = [
  {
    id:             "rules",
    label:          "RULES",
    version:        "rules-v1",
    provenance:     "MEASURED",
    provenanceNote: "Local RulesRouter harness validation — 75 frozen test examples, 2026-09-20. " +
                    "accuracy = action_accuracy (90.7%). severity=42.7%, category=68.0%.",

    accuracy:           RU_ACC,
    macro_f1:           0.847,
    severity_accuracy:  0.427,
    action_accuracy:    0.907,
    category_accuracy:  0.680,
    schema_reliability: 1.000,
    correct_decisions:  RU_CORRECT,

    p50_ms:  2,
    p95_ms:  5,
    p99_ms:  8,
    mean_ms: 2.4,

    input_tokens_per_decision:  0,
    output_tokens_per_decision: 0,
    model_calls_per_decision:   0,

    cost_per_decision_usd:  0,
    cost_per_1k_usd:        0,
    cost_per_correct_usd:   0,
    total_cost_usd:         0,

    schema_failure_rate:   0.000,
    bad_send_rate:         0.013,
    over_escalation_rate:  0.000,
    missed_policy_rate:    0.013,
    timeout_rate:          0.000,
    retry_rate:            0.000,
    throughput_per_s:      380,

    live_provider_status: "AVAILABLE",
  },
  {
    id:             "llm_single",
    label:          "LLM SINGLE",
    version:        "llm-single-v1 / gpt-4o-mini",
    provenance:     "PROJECTED",
    provenanceNote: "Demo projection. Derived from gpt-4o-mini token model + benchmark config. " +
                    "Live provider UNAVAILABLE (credit_balance_exhausted). NOT empirically measured.",

    accuracy:           LS_ACC,
    macro_f1:           0.893,
    severity_accuracy:  0.880,
    action_accuracy:    0.947,
    category_accuracy:  0.920,
    schema_reliability: 0.987,
    correct_decisions:  LS_CORRECT,

    p50_ms:  420,
    p95_ms:  820,
    p99_ms:  1180,
    mean_ms: 490,

    input_tokens_per_decision:  LS_IN,
    output_tokens_per_decision: LS_OUT,
    model_calls_per_decision:   1,

    cost_per_decision_usd:  LS_COST_PER,
    cost_per_1k_usd:        LS_COST_PER * 1000,
    cost_per_correct_usd:   (LS_COST_PER * N) / LS_CORRECT,
    total_cost_usd:         LS_COST_PER * N,

    schema_failure_rate:   0.013,
    bad_send_rate:         0.027,
    over_escalation_rate:  0.013,
    missed_policy_rate:    0.040,
    timeout_rate:          0.005,
    retry_rate:            0.027,
    throughput_per_s:      17,

    live_provider_status:       "UNAVAILABLE",
    live_provider_block_reason: "credit_balance_exhausted · HTTP 429",
  },
  {
    id:             "llm_parallel",
    label:          "LLM PARALLEL",
    version:        "llm-parallel-v1 / gpt-4o-mini",
    provenance:     "PROJECTED",
    provenanceNote: "Demo projection. 6 concurrent async LLM calls. Parallel wall-clock latency " +
                    "lower than LLM Single despite higher aggregate token cost. Live provider UNAVAILABLE (credit_balance_exhausted).",

    accuracy:           LP_ACC,
    macro_f1:           0.912,
    severity_accuracy:  0.893,
    action_accuracy:    0.960,
    category_accuracy:  0.933,
    schema_reliability: 0.987,
    correct_decisions:  LP_CORRECT,

    p50_ms:  240,
    p95_ms:  490,
    p99_ms:  730,
    mean_ms: 275,

    input_tokens_per_decision:  LP_IN,
    output_tokens_per_decision: LP_OUT,
    model_calls_per_decision:   6,

    cost_per_decision_usd:  LP_COST_PER,
    cost_per_1k_usd:        LP_COST_PER * 1000,
    cost_per_correct_usd:   (LP_COST_PER * N) / LP_CORRECT,
    total_cost_usd:         LP_COST_PER * N,

    schema_failure_rate:   0.013,
    bad_send_rate:         0.013,
    over_escalation_rate:  0.013,
    missed_policy_rate:    0.027,
    timeout_rate:          0.013,
    retry_rate:            0.040,
    throughput_per_s:      14,

    live_provider_status:       "UNAVAILABLE",
    live_provider_block_reason: "credit_balance_exhausted · HTTP 429",
  },
  {
    id:             "jev",
    label:          "JEV",
    version:        "jev-adapter-0.1",
    provenance:     "PROJECTED",
    provenanceNote: "Demo projection. System-One decision primitive. " +
                    JEV_PRICING_NOTE + " Live provider UNAVAILABLE (no JEV_API_KEY, OQ-001/OQ-002 unresolved).",
    jev_pricing_note: JEV_PRICING_NOTE,

    accuracy:           JV_ACC,
    macro_f1:           0.932,
    severity_accuracy:  0.920,
    action_accuracy:    0.973,
    category_accuracy:  0.947,
    schema_reliability: 0.992,
    correct_decisions:  JV_CORRECT,

    p50_ms:  35,
    p95_ms:  88,
    p99_ms:  155,
    mean_ms: 45,

    input_tokens_per_decision:  JV_IN,
    output_tokens_per_decision: JV_OUT,
    model_calls_per_decision:   1,

    cost_per_decision_usd:  JV_COST_PER,
    cost_per_1k_usd:        JV_COST_PER * 1000,
    cost_per_correct_usd:   (JV_COST_PER * N) / JV_CORRECT,
    total_cost_usd:         JV_COST_PER * N,

    schema_failure_rate:   0.008,
    bad_send_rate:         0.013,
    over_escalation_rate:  0.000,
    missed_policy_rate:    0.027,
    timeout_rate:          0.000,
    retry_rate:            0.008,
    throughput_per_s:      85,

    live_provider_status:       "UNAVAILABLE",
    live_provider_block_reason: "JEV_API_KEY not configured · OQ-001 / OQ-002 unresolved",
  },
];

// ─── Intelligence Cost Curve ───────────────────────────────────────────────────
// PROJECTED — scaling-v1 not yet executed
export const COST_CURVE_POINTS: CostCurvePoint[] = [2, 4, 6, 8, 12].map((n) => ({
  decisions:                n,
  rules_latency_ms:         n * 2.4,
  llm_single_latency_ms:    n * 420,
  llm_parallel_latency_ms:  220 + n * 12,
  jev_latency_ms:           n * 38,
  rules_cost_usd:           0,
  llm_single_cost_usd:      n * LS_COST_PER,
  llm_parallel_cost_usd:    n * LP_COST_PER,
  jev_cost_usd:             n * JV_COST_PER,
  rules_tokens:             0,
  llm_single_tokens:        n * (LS_IN + LS_OUT),
  llm_parallel_tokens:      n * (LP_IN + LP_OUT),
  jev_tokens:               n * (JV_IN + JV_OUT),
}));

// ─── Dataset facts (MEASURED) ─────────────────────────────────────────────────
export const DEMO_DATASET = {
  name:                 "synthetic_support_v1",
  source_type:          "SYNTHETIC",
  provenance:           "MEASURED" as DemoDataStatus,
  total_examples:       500,
  train_examples:       350,
  validation_examples:  75,
  test_examples:        75,
  quality_gate:         "PASS",
  leakage_detected:     false,
  frozen_manifest:      "datasets/manifests/frozen_test_synthetic_support_v1.json",
  test_hash_prefix:     "9c6919c5fb883c3a",
  freeze_timestamp:     "2026-09-20T18:00:45.997532+00:00",
  severity_dist:  { P3: 43, P2: 20, P4: 8, P1: 4 },
  action_dist:    { SEND: 63, HOLD: 9, ESCALATE: 3 },
  category_dist:  { Account: 21, Billing: 18, Other: 24, Feature: 8, Bug: 4 },
  limitation:     "Synthetic dataset. Results are not equivalent to results on real operational data.",
};

// ─── Experiment config ────────────────────────────────────────────────────────
export const DEMO_EXPERIMENT = {
  id:             "baseline-research-v1",
  dataset:        "synthetic_support_v1",
  split:          "test",
  examples:       75,
  concurrency:    8,
  model:          "gpt-4o-mini",
  prompt_version: "llm-control-v1.0",
  schema_version: "1.0",
  policy_version: "support-policy-1.0",
  decision_schema_version: "1.0",
  code_sha:       "b17ad97",
  timestamp:      "2026-09-20T18:00:00Z",
  validity_note:  "PARTIAL — RulesRouter locally measured. LLM/Jev are demo projections. " +
                  "Live providers currently unavailable. Full empirical benchmark pending.",
};

// ─── Fastpath demo projection (PROJECTED) ─────────────────────────────────────
export const FASTPATH_DEMO = {
  provenance: "PROJECTED" as DemoDataStatus,
  always_jev: {
    calls_per_1k: 1000,
    latency_p50_ms: 35,
    cost_per_1k_usd: JV_COST_PER * 1000,
  },
  fast_gate_plus_jev: {
    bypass_rate: 0.30,
    calls_per_1k: 700,
    latency_p50_ms: 28,
    cost_per_1k_usd: JV_COST_PER * 700,
    quality_delta: +0.003,
  },
};

// ─── E2E projection (PROJECTED — live providers unavailable) ──────────────────
export const E2E_DEMO = {
  provenance: "PROJECTED" as DemoDataStatus,
  generation_unavailable: true,
  generation_unavailable_reason: "Generation provider not configured. e2e-v1 experiment not yet executed.",
  assumed_generation_cost_per_request_usd: 0.0030,
  assumed_generation_latency_ms: 1200,
  systems: [
    { id: "rules",        control_cost: 0,           gen_cost: 0.0030, total_cost: 0.0030,  control_latency: 2,   gen_latency: 1200, total_latency: 1202, tax_pct: 0.00 },
    { id: "llm_single",   control_cost: LS_COST_PER, gen_cost: 0.0030, total_cost: LS_COST_PER + 0.0030, control_latency: 420, gen_latency: 1200, total_latency: 1620, tax_pct: LS_COST_PER / (LS_COST_PER + 0.0030) },
    { id: "llm_parallel", control_cost: LP_COST_PER, gen_cost: 0.0030, total_cost: LP_COST_PER + 0.0030, control_latency: 240, gen_latency: 1200, total_latency: 1440, tax_pct: LP_COST_PER / (LP_COST_PER + 0.0030) },
    { id: "jev",          control_cost: JV_COST_PER, gen_cost: 0.0030, total_cost: JV_COST_PER + 0.0030, control_latency: 35,  gen_latency: 1200, total_latency: 1235, tax_pct: JV_COST_PER / (JV_COST_PER + 0.0030) },
  ],
};
