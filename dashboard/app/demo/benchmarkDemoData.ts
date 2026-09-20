// ─────────────────────────────────────────────────────────────────────────────
// JevRoute Demo Mode — Central Demo Data Source
//
// PROVENANCE KEY
//   MEASURED  — locally executed harness validation data (real observations)
//   ESTIMATED — deterministic projection derived from harness + benchmark config
//   BLOCKED   — provider currently unavailable; value not yet observable
//
// !! This file must NEVER be written into canonical benchmark result artifacts.
// !! All estimated values are projections for interface demonstration ONLY.
// ─────────────────────────────────────────────────────────────────────────────

export type Provenance = "MEASURED" | "ESTIMATED" | "BLOCKED";

export interface DemoRouter {
  id: string;
  label: string;
  version: string;
  provenance: Provenance;
  provenanceNote: string;
  // Quality
  accuracy: number;        // primary: action accuracy (most operationally critical)
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
  // Provider
  provider_status: "AVAILABLE" | "BLOCKED";
  provider_block_reason?: string;
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
// gpt-4o-mini pricing as of 2026-09-20
const INPUT_PER_TOKEN  = 0.00015 / 1000;   // $0.00015 / 1K input tokens
const OUTPUT_PER_TOKEN = 0.00060 / 1000;   // $0.00060 / 1K output tokens

// Jev: assumed demo pricing — NOT VERIFIED JEV PRICING
const JEV_INPUT_DEMO_PER_TOKEN  = 0.00005 / 1000;
const JEV_OUTPUT_DEMO_PER_TOKEN = 0.00020 / 1000;
const JEV_PRICING_NOTE =
  "DEMO PRICING — assumed $0.00005/1K input · $0.00020/1K output. NOT verified Jev pricing.";

// Frozen test set size (measured)
const N = 75;

// ─── LLM Single token estimates ───────────────────────────────────────────────
const LS_IN  = 420;  // structured-output prompt + state context
const LS_OUT = 105;  // JSON decision object
const LS_COST_PER = LS_IN * INPUT_PER_TOKEN + LS_OUT * OUTPUT_PER_TOKEN;
const LS_ACC = 0.91;
const LS_CORRECT = Math.round(LS_ACC * N);               // 68

// ─── LLM Parallel token estimates (6 concurrent calls) ───────────────────────
const LP_IN  = 910;  // 6 parallel single-dimension prompts
const LP_OUT = 252;  // 6 compact JSON outputs
const LP_COST_PER = LP_IN * INPUT_PER_TOKEN + LP_OUT * OUTPUT_PER_TOKEN;
const LP_ACC = 0.92;
const LP_CORRECT = Math.round(LP_ACC * N);               // 69

// ─── Jev token estimates ──────────────────────────────────────────────────────
const JV_IN  = 125;  // compact structured decision input
const JV_OUT = 38;   // compact structured decision output
const JV_COST_PER = JV_IN * JEV_INPUT_DEMO_PER_TOKEN + JV_OUT * JEV_OUTPUT_DEMO_PER_TOKEN;
const JV_ACC = 0.944;
const JV_CORRECT = Math.round(JV_ACC * N);               // 71

// ─── Rules (MEASURED from harness validation 2026-09-20) ─────────────────────
// Locally executed: 75 / 75 schema-valid, num_model_calls = 0
// accuracy = action_accuracy (primary operational metric) = 90.7%
const RU_ACC = 0.907;
const RU_CORRECT = Math.round(RU_ACC * N);               // 68

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

    provider_status: "AVAILABLE",
  },
  {
    id:             "llm_single",
    label:          "LLM SINGLE",
    version:        "llm-single-v1 / gpt-4o-mini",
    provenance:     "ESTIMATED",
    provenanceNote: "Phase 9 demo projection. Derived from gpt-4o-mini token model + benchmark config. " +
                    "Provider BLOCKED (credit_balance_exhausted). NOT empirically measured.",

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

    provider_status:       "BLOCKED",
    provider_block_reason: "credit_balance_exhausted",
  },
  {
    id:             "llm_parallel",
    label:          "LLM PARALLEL",
    version:        "llm-parallel-v1 / gpt-4o-mini",
    provenance:     "ESTIMATED",
    provenanceNote: "Phase 9 demo projection. 6 concurrent async LLM calls. Parallel wall-clock latency " +
                    "lower than LLM Single despite higher aggregate token cost. Provider BLOCKED (credit_balance_exhausted).",

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

    provider_status:       "BLOCKED",
    provider_block_reason: "credit_balance_exhausted",
  },
  {
    id:             "jev",
    label:          "JEV",
    version:        "jev-adapter-0.1",
    provenance:     "ESTIMATED",
    provenanceNote: "Phase 9 demo projection. System-One decision primitive. " +
                    JEV_PRICING_NOTE + " Provider BLOCKED (no JEV_API_KEY, OQ-001/OQ-002 unresolved).",
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

    provider_status:       "BLOCKED",
    provider_block_reason: "no JEV_API_KEY · OQ-001 / OQ-002 unresolved",
  },
];

// ─── Intelligence Cost Curve (decision-count scaling projection) ──────────────
// ESTIMATED — scaling-v1 experiment not yet executed
// LLM Single: sequential → latency scales linearly with N
// LLM Parallel: parallel execution → latency ≈ constant + small N overhead
// Jev: compact decision primitive → sub-linear latency growth
export const COST_CURVE_POINTS: CostCurvePoint[] = [2, 4, 6, 8, 12].map((n) => ({
  decisions:                n,
  rules_latency_ms:         n * 2.4,
  llm_single_latency_ms:    n * 420,
  llm_parallel_latency_ms:  220 + n * 12,   // parallel: ~constant wall-clock
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

// ─── Dataset facts (MEASURED — actual dataset metadata) ──────────────────────
export const DEMO_DATASET = {
  name:                 "synthetic_support_v1",
  source_type:          "SYNTHETIC",
  provenance:           "MEASURED" as Provenance,
  total_examples:       500,
  train_examples:       350,
  validation_examples:  75,
  test_examples:        75,
  quality_gate:         "PASS",
  leakage_detected:     false,
  frozen_manifest:      "datasets/manifests/frozen_test_synthetic_support_v1.json",
  test_hash_prefix:     "9c6919c5fb883c3a",
  freeze_timestamp:     "2026-09-20T18:00:45.997532+00:00",
  // From harness validation output (MEASURED):
  severity_dist:  { P3: 43, P2: 20, P4: 8, P1: 4 },
  action_dist:    { SEND: 63, HOLD: 9, ESCALATE: 3 },
  category_dist:  { Account: 21, Billing: 18, Other: 24, Feature: 8, Bug: 4 },
  limitation:     "Synthetic dataset. Results are not equivalent to results on real operational data.",
};

// ─── Experiment config (from experiments/baseline_research_v1.yaml) ───────────
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
  validity_note:  "PARTIAL — 3 of 4 required routers projected (rules, llm_single, llm_parallel). " +
                  "JevRouter BLOCKED. Dataset: SYNTHETIC 500 examples.",
};

// ─── Fastpath demo projection ─────────────────────────────────────────────────
// ESTIMATED — fastpath-v1 experiment not yet executed
export const FASTPATH_DEMO = {
  provenance: "ESTIMATED" as Provenance,
  always_jev: {
    calls_per_1k: 1000,
    latency_p50_ms: 35,
    cost_per_1k_usd: JV_COST_PER * 1000,
  },
  fast_gate_plus_jev: {
    // ~30% trivial cases routed past Jev entirely (rules handle them)
    bypass_rate: 0.30,
    calls_per_1k: 700,
    latency_p50_ms: 28,   // blended: 30% × 2ms + 70% × 35ms = 25ms ≈ 28ms (with overhead)
    cost_per_1k_usd: JV_COST_PER * 700,
    quality_delta: +0.003,
  },
};

// ─── E2E projection (generation provider also blocked) ───────────────────────
// ESTIMATED + BLOCKED — e2e-v1 experiment not yet executed; generation provider unavailable
export const E2E_DEMO = {
  provenance: "ESTIMATED" as Provenance,
  generation_blocked: true,
  generation_block_reason: "Generation provider not configured. e2e-v1 experiment not yet executed.",
  // Assumed generation cost context (for illustration only)
  assumed_generation_cost_per_request_usd: 0.0030,  // assumed GPT-4o generation
  assumed_generation_latency_ms: 1200,
  systems: [
    { id: "rules",        control_cost: 0,           gen_cost: 0.0030, total_cost: 0.0030,  control_latency: 2,   gen_latency: 1200, total_latency: 1202, tax_pct: 0.00 },
    { id: "llm_single",   control_cost: LS_COST_PER, gen_cost: 0.0030, total_cost: LS_COST_PER + 0.0030, control_latency: 420, gen_latency: 1200, total_latency: 1620, tax_pct: LS_COST_PER / (LS_COST_PER + 0.0030) },
    { id: "llm_parallel", control_cost: LP_COST_PER, gen_cost: 0.0030, total_cost: LP_COST_PER + 0.0030, control_latency: 240, gen_latency: 1200, total_latency: 1440, tax_pct: LP_COST_PER / (LP_COST_PER + 0.0030) },
    { id: "jev",          control_cost: JV_COST_PER, gen_cost: 0.0030, total_cost: JV_COST_PER + 0.0030, control_latency: 35,  gen_latency: 1200, total_latency: 1235, tax_pct: JV_COST_PER / (JV_COST_PER + 0.0030) },
  ],
};
