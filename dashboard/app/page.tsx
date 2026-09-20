"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Activity, AlertCircle, BarChart2, CheckCircle2, Circle,
  Clock, Database, DollarSign, FileText, FlaskConical,
  Server, Shield, TrendingUp, Zap, Info
} from "lucide-react";
import {
  DEMO_ROUTERS, COST_CURVE_POINTS, DEMO_DATASET, DEMO_EXPERIMENT,
  FASTPATH_DEMO, E2E_DEMO, type DemoRouter, type Provenance,
} from "./demo/benchmarkDemoData";

// ── Types ──────────────────────────────────────────────────────────────────────

interface ApiStatus {
  status: string;
  environment: string;
  app_version: string;
  schema_version: string;
  policy_version: string;
  active_router: string;
  benchmark_results_available: boolean;
}

interface RouterRow {
  router: string;
  router_version: string | null;
  experiment_id: string;
  examples: number | null;
  decisions: number | null;
  correct_decisions: number | null;
  accuracy: number | null;
  macro_f1: number | null;
  bad_send_rate: number | null;
  over_escalation_rate: number | null;
  missed_policy_violation_rate: number | null;
  schema_failure_rate: number | null;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  p99_latency_ms: number | null;
  mean_latency_ms: number | null;
  total_cost_usd: number | null;
  cost_per_1k_decisions_usd: number | null;
  cost_per_correct_decision_usd: number | null;
  decision_throughput_per_s: number | null;
  brier_score: number | null;
  ece: number | null;
}

interface ExperimentSummary {
  experiment_id: string;
  status: "NOT_RUN" | "RUNNING" | "COMPLETE" | "FAILED";
  dataset: string | null;
  split: string | null;
  num_runs: number;
  routers: string[];
  last_run_at: string | null;
}

interface Dataset {
  name: string;
  split: string;
  path: string;
  examples: number;
}

type Tab = "overview" | "comparison" | "cost_curve" | "economics" | "reliability" | "runs" | "dataset" | "methodology" | "reproducibility";
type ConnectionState = "connecting" | "ok" | "error";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const ALL_EXPERIMENTS = [
  { id: "baseline-v1",   label: "Baseline Comparison",    icon: BarChart2 },
  { id: "scaling-v1",    label: "Decision Scaling",        icon: TrendingUp },
  { id: "fastpath-v1",   label: "Fast-Path Bypass",        icon: Zap },
  { id: "context-v1",    label: "Context Scaling",         icon: FileText },
  { id: "dependency-v1", label: "Dependency Analysis",     icon: Server },
  { id: "e2e-v1",        label: "End-to-End Economics",    icon: DollarSign },
];

const ROUTER_DISPLAY: Record<string, string> = {
  rules: "RULES",
  llm_single: "LLM SINGLE",
  llm_parallel: "LLM PARALLEL",
  jev: "JEV",
  mock_jev: "MOCK JEV",
};

// ── Provenance system ─────────────────────────────────────────────────────────

const PROVENANCE_CONFIG: Record<Provenance, { label: string; color: string; symbol: string; bg: string }> = {
  MEASURED:  { label: "MEASURED",  color: "#22C55E", symbol: "●", bg: "#F0FDF4" },
  ESTIMATED: { label: "ESTIMATED", color: "#F59E0B", symbol: "◌", bg: "#FFFBEB" },
  BLOCKED:   { label: "BLOCKED",   color: "#EF4444", symbol: "△", bg: "#FEF2F2" },
};

function ProvenanceBadge({ p, note }: { p: Provenance; note?: string }) {
  const cfg = PROVENANCE_CONFIG[p];
  return (
    <span
      className="mono text-[9px] font-semibold px-1.5 py-0.5 rounded border cursor-default"
      style={{ color: cfg.color, background: cfg.bg, borderColor: cfg.color + "40" }}
      title={note ?? cfg.label}>
      {cfg.symbol} {cfg.label}
    </span>
  );
}

// ── Demo Banner ───────────────────────────────────────────────────────────────

function DemoBanner() {
  return (
    <div className="w-full px-6 py-2.5 flex items-center justify-between gap-4 flex-wrap"
      style={{ background: "#FFF8F5", borderBottom: "1px solid #F5C4B0" }}>
      <div className="flex items-center gap-2">
        <span className="mono text-[10px] font-bold px-2 py-0.5 rounded"
          style={{ background: "#E85B35", color: "#fff" }}>DEMO VERSION</span>
        <span className="mono text-[11px]" style={{ color: "#92400E" }}>
          Based on actual executed empirical values locally
        </span>
      </div>
      <span className="mono text-[10px]" style={{ color: "#B45309" }}>
        <ProvenanceBadge p="MEASURED" /> = locally executed harness · {" "}
        <ProvenanceBadge p="ESTIMATED" /> = deterministic projection · {" "}
        <ProvenanceBadge p="BLOCKED" /> = provider unavailable
      </span>
    </div>
  );
}

// ── Utility functions ─────────────────────────────────────────────────────────

function fmt(v: number | null | undefined, digits = 3): string {
  if (v === null || v === undefined) return "—";
  return v.toFixed(digits);
}

function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return (v * 100).toFixed(1) + "%";
}

function fmtCost(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  if (v === 0) return "$0.000";
  if (v < 0.0001) return "$" + v.toExponential(2);
  return "$" + v.toFixed(6);
}

function fmtMs(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return v.toFixed(2) + " ms";
}

function statusLabel(s: string) {
  const m: Record<string, string> = {
    NOT_RUN: "NOT RUN", RUNNING: "RUNNING", COMPLETE: "COMPLETE", FAILED: "FAILED"
  };
  return m[s] ?? s;
}

function statusColor(s: string): string {
  const m: Record<string, string> = {
    NOT_RUN: "var(--status-none)",
    RUNNING: "var(--status-warn)",
    COMPLETE: "var(--status-ok)",
    FAILED: "var(--status-err)",
  };
  return m[s] ?? "var(--text-muted)";
}

// ── SVG Charts ────────────────────────────────────────────────────────────────

const ROUTER_COLORS: Record<string, string> = {
  rules:        "#6F736F",
  llm_single:   "#3B82F6",
  llm_parallel: "#8B5CF6",
  jev:          "#E85B35",
};

function LatencyBarChart({ routers }: { routers: DemoRouter[] }) {
  const max = Math.max(...routers.map(r => r.p95_ms));
  const W = 480; const H = 180; const BAR_H = 28; const GAP = 12; const LABEL_W = 100;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 200 }}>
      {routers.map((r, i) => {
        const y = i * (BAR_H + GAP) + 10;
        const barW = Math.max(4, (r.p95_ms / max) * (W - LABEL_W - 60));
        const color = ROUTER_COLORS[r.id] ?? "#999";
        return (
          <g key={r.id}>
            <text x={LABEL_W - 6} y={y + BAR_H / 2 + 4} textAnchor="end"
              style={{ fontSize: 10, fill: "var(--text-secondary)", fontFamily: "monospace" }}>
              {r.label}
            </text>
            <rect x={LABEL_W} y={y} width={barW} height={BAR_H} rx={3} fill={color} opacity={0.85} />
            <text x={LABEL_W + barW + 6} y={y + BAR_H / 2 + 4}
              style={{ fontSize: 10, fill: "var(--text-secondary)", fontFamily: "monospace" }}>
              {r.p95_ms}ms
            </text>
          </g>
        );
      })}
    </svg>
  );
}

type CurveAxis = "latency" | "cost" | "tokens";

function LineCurveChart({ axis }: { axis: CurveAxis }) {
  const pts = COST_CURVE_POINTS;
  const routers: { id: string; label: string; values: number[] }[] = [
    { id: "rules",        label: "RULES",        values: pts.map(p => axis === "latency" ? p.rules_latency_ms        : axis === "cost" ? p.rules_cost_usd        * 1e6 : p.rules_tokens) },
    { id: "llm_single",   label: "LLM SINGLE",   values: pts.map(p => axis === "latency" ? p.llm_single_latency_ms   : axis === "cost" ? p.llm_single_cost_usd   * 1e6 : p.llm_single_tokens) },
    { id: "llm_parallel", label: "LLM PARALLEL", values: pts.map(p => axis === "latency" ? p.llm_parallel_latency_ms : axis === "cost" ? p.llm_parallel_cost_usd * 1e6 : p.llm_parallel_tokens) },
    { id: "jev",          label: "JEV",          values: pts.map(p => axis === "latency" ? p.jev_latency_ms          : axis === "cost" ? p.jev_cost_usd          * 1e6 : p.jev_tokens) },
  ];
  const W = 480; const H = 200; const PAD = { t: 12, r: 20, b: 36, l: 52 };
  const xs = pts.map((_, i) => PAD.l + (i / (pts.length - 1)) * (W - PAD.l - PAD.r));
  const maxV = Math.max(...routers.flatMap(r => r.values));
  const yScale = (v: number) => PAD.t + (1 - v / maxV) * (H - PAD.t - PAD.b);
  const path = (vals: number[]) => vals.map((v, i) => `${i === 0 ? "M" : "L"}${xs[i].toFixed(1)},${yScale(v).toFixed(1)}`).join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 220 }}>
      {/* Grid lines */}
      {[0, 0.25, 0.5, 0.75, 1].map(f => {
        const y = PAD.t + f * (H - PAD.t - PAD.b);
        return <line key={f} x1={PAD.l} x2={W - PAD.r} y1={y} y2={y} stroke="var(--border)" strokeWidth={1} />;
      })}
      {/* X axis labels */}
      {pts.map((p, i) => (
        <text key={p.decisions} x={xs[i]} y={H - PAD.b + 14} textAnchor="middle"
          style={{ fontSize: 9, fill: "var(--text-muted)", fontFamily: "monospace" }}>
          {p.decisions}
        </text>
      ))}
      <text x={W / 2} y={H - 2} textAnchor="middle"
        style={{ fontSize: 9, fill: "var(--text-muted)", fontFamily: "monospace" }}>
        decisions / request
      </text>
      {/* Lines */}
      {routers.map(r => (
        <path key={r.id} d={path(r.values)} fill="none"
          stroke={ROUTER_COLORS[r.id] ?? "#999"} strokeWidth={2} strokeLinejoin="round" />
      ))}
      {/* Points */}
      {routers.map(r => r.values.map((v, i) => (
        <circle key={`${r.id}-${i}`} cx={xs[i]} cy={yScale(v)} r={3}
          fill={ROUTER_COLORS[r.id] ?? "#999"} />
      )))}
      {/* Legend */}
      {routers.map((r, i) => (
        <g key={r.id} transform={`translate(${PAD.l + i * 110}, ${H - PAD.b + 24})`}>
          <rect width={8} height={3} y={4} rx={1} fill={ROUTER_COLORS[r.id] ?? "#999"} />
          <text x={12} y={9} style={{ fontSize: 9, fill: "var(--text-secondary)", fontFamily: "monospace" }}>{r.label}</text>
        </g>
      ))}
    </svg>
  );
}

function ScatterChart({ routers }: { routers: DemoRouter[] }) {
  const W = 400; const H = 240; const PAD = { t: 20, r: 60, b: 50, l: 60 };
  const maxCost = Math.max(...routers.map(r => r.cost_per_1k_usd)) || 1;
  const minAcc = Math.min(...routers.map(r => r.accuracy));
  const maxAcc = Math.max(...routers.map(r => r.accuracy));
  const accRange = maxAcc - minAcc || 0.01;

  const cx = (r: DemoRouter) => PAD.l + (r.cost_per_1k_usd / maxCost) * (W - PAD.l - PAD.r);
  const cy = (r: DemoRouter) => H - PAD.b - ((r.accuracy - minAcc) / accRange) * (H - PAD.t - PAD.b);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 260 }}>
      {/* Axes */}
      <line x1={PAD.l} x2={PAD.l} y1={PAD.t} y2={H - PAD.b} stroke="var(--border)" strokeWidth={1} />
      <line x1={PAD.l} x2={W - PAD.r} y1={H - PAD.b} y2={H - PAD.b} stroke="var(--border)" strokeWidth={1} />
      {/* Points */}
      {routers.map(r => {
        const x = cx(r); const y = cy(r);
        const color = ROUTER_COLORS[r.id] ?? "#999";
        return (
          <g key={r.id}>
            <circle cx={x} cy={y} r={7} fill={color} opacity={0.85} />
            <text x={x + 10} y={y + 4}
              style={{ fontSize: 9, fill: "var(--text-secondary)", fontFamily: "monospace" }}>
              {r.label}
            </text>
          </g>
        );
      })}
      {/* Axis labels */}
      <text x={W / 2} y={H - 8} textAnchor="middle"
        style={{ fontSize: 9, fill: "var(--text-muted)", fontFamily: "monospace" }}>
        cost / 1K decisions (USD)
      </text>
      <text x={14} y={H / 2} textAnchor="middle" transform={`rotate(-90, 14, ${H / 2})`}
        style={{ fontSize: 9, fill: "var(--text-muted)", fontFamily: "monospace" }}>
        accuracy
      </text>
    </svg>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg p-5 ${className}`}
      style={{ background: "var(--surface)", border: "1px solid var(--border)", boxShadow: "var(--shadow-sm)" }}>
      {children}
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="mono text-[10px] font-medium tracking-widest uppercase mb-4"
      style={{ color: "var(--text-muted)" }}>
      {children}
    </p>
  );
}

function MetaChip({ children }: { children: React.ReactNode }) {
  return (
    <span className="mono text-[10px] font-medium px-2 py-0.5 rounded border"
      style={{ color: "var(--text-muted)", borderColor: "var(--border)", background: "var(--surface-alt)" }}>
      {children}
    </span>
  );
}

function StatusDot({ state }: { state: string }) {
  return (
    <span className="inline-block w-1.5 h-1.5 rounded-full mr-2 flex-shrink-0"
      style={{ background: statusColor(state), marginBottom: 1 }} />
  );
}

function AwaitingData({ label }: { label: string }) {
  return (
    <div className="rounded-md flex flex-col items-center justify-center py-12"
      style={{ background: "var(--surface-alt)", border: "1px dashed var(--border-strong)" }}>
      <FlaskConical size={20} style={{ color: "var(--text-muted)" }} className="mb-3" />
      <p className="mono text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
        No data available
      </p>
      <p className="mono text-[11px] mt-1" style={{ color: "var(--text-muted)" }}>
        Run <span style={{ color: "var(--text-secondary)" }}>{label}</span> to populate this view.
      </p>
      <p className="text-[11px] mt-2" style={{ color: "var(--text-muted)" }}>
        No benchmark data has been fabricated.
      </p>
    </div>
  );
}

// ── Tab navigation ─────────────────────────────────────────────────────────────

const TABS: { id: Tab; label: string }[] = [
  { id: "overview",        label: "Overview" },
  { id: "comparison",      label: "Comparison" },
  { id: "cost_curve",      label: "Cost Curve" },
  { id: "economics",       label: "Economics" },
  { id: "reliability",     label: "Reliability" },
  { id: "runs",            label: "Runs" },
  { id: "dataset",         label: "Dataset" },
  { id: "methodology",     label: "Methodology" },
  { id: "reproducibility", label: "Reproducibility" },
];

// ── Main component ────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [apiStatus, setApiStatus] = useState<ApiStatus | null>(null);
  const [experiments, setExperiments] = useState<ExperimentSummary[]>([]);
  const [baselineMetrics, setBaselineMetrics] = useState<RouterRow[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [lastChecked, setLastChecked] = useState<string>("");
  const [demoMode, setDemoMode] = useState<boolean>(false);
  const [curveAxis, setCurveAxis] = useState<CurveAxis>("latency");

  // Load demo mode preference from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem("jevroute_demo_mode");
      if (stored === "true") setDemoMode(true);
    } catch { /* ignore */ }
  }, []);

  const toggleDemo = () => {
    setDemoMode(prev => {
      const next = !prev;
      try { localStorage.setItem("jevroute_demo_mode", String(next)); } catch { /* ignore */ }
      return next;
    });
  };

  const fetchAll = useCallback(async () => {
    try {
      const [statusRes, expRes, metricsRes, dsRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/status`),
        fetch(`${API_BASE}/api/v1/experiments`),
        fetch(`${API_BASE}/api/v1/experiments/baseline-v1/metrics`),
        fetch(`${API_BASE}/api/v1/datasets`),
      ]);
      if (!statusRes.ok) throw new Error(`status ${statusRes.status}`);
      const status = await statusRes.json();
      setApiStatus(status);
      setConnection("ok");
      setLastChecked(new Date().toLocaleTimeString());

      if (expRes.ok) {
        const ed = await expRes.json();
        setExperiments(ed.experiments ?? []);
      }
      if (metricsRes.ok) {
        const md = await metricsRes.json();
        setBaselineMetrics(Array.isArray(md) ? md : []);
      }
      if (dsRes.ok) {
        const dd = await dsRes.json();
        setDatasets(dd.datasets ?? []);
      }
    } catch {
      setConnection("error");
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 30_000);
    return () => clearInterval(t);
  }, [fetchAll]);

  const completedCount = demoMode ? 1 : experiments.filter(e => e.status === "COMPLETE").length;
  const totalDecisions = demoMode
    ? DEMO_ROUTERS.reduce((s, r) => s + r.correct_decisions, 0)
    : baselineMetrics.reduce((sum, r) => sum + (r.decisions ?? 0), 0);

  // ── Demo tab renderers ────────────────────────────────────────────────────

  function renderDemoOverview() {
    const rulesRouter = DEMO_ROUTERS.find(r => r.id === "rules")!;
    return (
      <div className="space-y-8">
        <section className="py-4">
          <h2 className="text-2xl font-semibold tracking-tight mb-3" style={{ color: "var(--text-primary)" }}>
            Measuring the Economics<br />of System-One Intelligence
          </h2>
          <p className="text-sm max-w-2xl leading-relaxed" style={{ color: "var(--text-secondary)" }}>
            AI systems generate. But around every generation step sits another workload:{" "}
            <strong style={{ color: "var(--text-primary)" }}>decide.</strong> JevRoute benchmarks
            whether structured software decisions require autoregressive inference — or whether
            a specialized System-One model can deliver equivalent quality at a lower control-plane cost.
          </p>
          <p className="text-xs mt-3 max-w-xl" style={{ color: "var(--text-muted)" }}>
            No winner is assumed. The benchmark measures where Jev helps, where it does not,
            how much it costs, and whether any local advantage survives end-to-end.
          </p>
        </section>

        <section>
          <SectionLabel>System Overview — Demo Projection</SectionLabel>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              {
                label: "Experiments Run", value: `1 / ${ALL_EXPERIMENTS.length}`,
                sub: "rules harness validated",
                provenance: "MEASURED" as Provenance,
              },
              {
                label: "Test Examples", value: "75",
                sub: "frozen test set · synthetic_support_v1",
                provenance: "MEASURED" as Provenance,
              },
              {
                label: "p95 Latency (Rules)", value: fmtMs(rulesRouter.p95_ms),
                sub: "deterministic · 0 model calls",
                provenance: "MEASURED" as Provenance,
              },
              {
                label: "Est. Cost / 1K (Jev)", value: fmtCost(DEMO_ROUTERS.find(r => r.id === "jev")!.cost_per_1k_usd),
                sub: "demo pricing — not verified",
                provenance: "ESTIMATED" as Provenance,
              },
            ].map(({ label, value, sub, provenance }) => (
              <Card key={label}>
                <div className="flex items-center justify-between mb-2">
                  <span className="mono text-[10px] uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>{label}</span>
                  <ProvenanceBadge p={provenance} />
                </div>
                <p className="mono text-2xl font-medium" style={{ color: "var(--text-primary)" }}>{value}</p>
                <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>{sub}</p>
              </Card>
            ))}
          </div>
        </section>

        <section>
          <SectionLabel>Experiment Status (Demo)</SectionLabel>
          <Card>
            <div className="space-y-0">
              {ALL_EXPERIMENTS.map(({ id, label, icon: Icon }, i) => {
                const isRules = id === "baseline-v1";
                const state = isRules ? "COMPLETE" : "NOT_RUN";
                return (
                  <div key={id} className="flex items-center justify-between py-3"
                    style={{ borderBottom: i < ALL_EXPERIMENTS.length - 1 ? "1px solid var(--border)" : "none" }}>
                    <div className="flex items-center gap-3">
                      <StatusDot state={state} />
                      <Icon size={13} style={{ color: "var(--text-muted)" }} />
                      <div>
                        <p className="mono text-xs font-medium" style={{ color: "var(--text-primary)" }}>{id}</p>
                        <p className="text-xs" style={{ color: "var(--text-muted)" }}>{label}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {isRules && <ProvenanceBadge p="MEASURED" note="RulesRouter harness validation — 75 examples" />}
                      {!isRules && <ProvenanceBadge p="BLOCKED" note="Provider credentials unavailable" />}
                      <span className="mono text-[10px] px-2 py-0.5 rounded"
                        style={{ background: "var(--surface-alt)", color: statusColor(state), border: "1px solid var(--border)" }}>
                        {isRules ? "VALIDATED" : "BLOCKED"}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        </section>

        <section>
          <SectionLabel>Provider Status</SectionLabel>
          <Card>
            <div className="space-y-3">
              {[
                { label: "Rules (deterministic)", status: "AVAILABLE", note: "Harness validated — 75/75 schema valid" },
                { label: "OpenAI gpt-4o-mini", status: "BLOCKED", note: "credit_balance_exhausted · HTTP 429" },
                { label: "Jev API", status: "BLOCKED", note: "JEV_API_KEY not configured · OQ-001 / OQ-002 unresolved" },
              ].map(({ label, status, note }) => (
                <div key={label} className="flex items-center justify-between gap-4">
                  <div>
                    <p className="mono text-xs font-medium" style={{ color: "var(--text-primary)" }}>{label}</p>
                    <p className="text-xs" style={{ color: "var(--text-muted)" }}>{note}</p>
                  </div>
                  <ProvenanceBadge p={status === "AVAILABLE" ? "MEASURED" : "BLOCKED"} />
                </div>
              ))}
            </div>
          </Card>
        </section>
      </div>
    );
  }

  function renderDemoComparison() {
    const COMP_ROWS: { label: string; format: (r: DemoRouter) => string; provNote?: string }[] = [
      { label: "p50 latency",          format: r => fmtMs(r.p50_ms) },
      { label: "p95 latency",          format: r => fmtMs(r.p95_ms) },
      { label: "p99 latency",          format: r => fmtMs(r.p99_ms) },
      { label: "accuracy (action)",    format: r => fmtPct(r.action_accuracy) },
      { label: "accuracy (overall)",   format: r => fmtPct(r.accuracy) },
      { label: "macro F1",             format: r => fmt(r.macro_f1, 3) },
      { label: "cost / 1K decisions",  format: r => fmtCost(r.cost_per_1k_usd) },
      { label: "cost / correct",       format: r => fmtCost(r.cost_per_correct_usd) },
      { label: "throughput",           format: r => `${r.throughput_per_s} /s` },
      { label: "model calls / decision", format: r => r.model_calls_per_decision.toString() },
      { label: "schema reliability",   format: r => fmtPct(r.schema_reliability) },
    ];

    return (
      <div className="space-y-6">
        <div>
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <h2 className="text-lg font-semibold mb-1" style={{ color: "var(--text-primary)" }}>System Comparison</h2>
              <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                Demo projection — Rules measured, LLM/Jev estimated. baseline-v1 · 75 test examples.
              </p>
            </div>
            <div className="flex gap-2 flex-wrap items-center">
              <ProvenanceBadge p="MEASURED" note="Locally executed harness validation" />
              <ProvenanceBadge p="ESTIMATED" note="Deterministic projection from benchmark config" />
              <ProvenanceBadge p="BLOCKED" note="Provider unavailable" />
            </div>
          </div>
        </div>

        <Card>
          <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
            <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Latency Comparison (p95)</p>
            <MetaChip>ESTIMATED — providers blocked</MetaChip>
          </div>
          <LatencyBarChart routers={DEMO_ROUTERS} />
        </Card>

        <Card>
          <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
            <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Router Performance Matrix</p>
            <MetaChip>baseline-v1 · {DEMO_EXPERIMENT.examples} examples</MetaChip>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  <th className="text-left py-2 pr-4 mono text-[10px] uppercase tracking-wider font-medium"
                    style={{ color: "var(--text-muted)" }}>Metric</th>
                  {DEMO_ROUTERS.map(r => (
                    <th key={r.id} className="text-right py-2 px-3 mono text-[10px] uppercase tracking-wider font-medium"
                      style={{ color: "var(--text-muted)" }}>
                      <div>{r.label}</div>
                      <ProvenanceBadge p={r.provenance} />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {COMP_ROWS.map(({ label, format }) => (
                  <tr key={label} style={{ borderBottom: "1px solid var(--border)" }}
                    className="hover:bg-[var(--surface-alt)] transition-colors">
                    <td className="py-2.5 pr-4 mono text-xs" style={{ color: "var(--text-secondary)" }}>{label}</td>
                    {DEMO_ROUTERS.map(r => (
                      <td key={r.id} className="py-2.5 px-3 text-right mono text-xs"
                        style={{ color: "var(--text-primary)" }}>
                        {format(r)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs mt-4" style={{ color: "var(--text-muted)" }}>
            Rules values are MEASURED from local harness validation. LLM/Jev values are ESTIMATED projections.
            These are not empirical benchmark results. No providers were unblocked to produce these numbers.
          </p>
        </Card>

        <Card>
          <p className="text-sm font-medium mb-3" style={{ color: "var(--text-primary)" }}>Quality × Cost Frontier</p>
          <p className="text-xs mb-4" style={{ color: "var(--text-secondary)" }}>
            Demo projection — router position on the accuracy vs. cost tradeoff space.
          </p>
          <ScatterChart routers={DEMO_ROUTERS} />
          <p className="text-xs mt-2" style={{ color: "var(--text-muted)" }}>
            Rules: $0 cost (deterministic). LLM/Jev costs are projections. Accuracy = action accuracy (primary metric).
          </p>
        </Card>
      </div>
    );
  }

  function renderDemoCostCurve() {
    const axisOptions: { value: CurveAxis; label: string }[] = [
      { value: "latency", label: "Latency (ms)" },
      { value: "cost",    label: "Cost (µUSD)" },
      { value: "tokens",  label: "Tokens" },
    ];
    return (
      <div className="space-y-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-lg font-semibold mb-1" style={{ color: "var(--text-primary)" }}>Intelligence Cost Curve</h2>
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
              How does control-plane cost scale as the number of structured decisions per request increases?
            </p>
            <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
              Scaling projection for 2 → 4 → 6 → 8 → 12 decisions per request.{" "}
              <ProvenanceBadge p="ESTIMATED" note="scaling-v1 experiment not yet executed" />
            </p>
          </div>
          <div className="flex gap-1">
            {axisOptions.map(opt => (
              <button key={opt.value} onClick={() => setCurveAxis(opt.value)}
                className="mono text-[10px] px-3 py-1.5 rounded border transition-colors"
                style={{
                  background: curveAxis === opt.value ? "var(--text-primary)" : "var(--surface-alt)",
                  color: curveAxis === opt.value ? "var(--surface)" : "var(--text-secondary)",
                  borderColor: curveAxis === opt.value ? "var(--text-primary)" : "var(--border)",
                  cursor: "pointer",
                }}>
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <Card>
          <p className="text-sm font-medium mb-4" style={{ color: "var(--text-primary)" }}>
            {axisOptions.find(a => a.value === curveAxis)?.label} vs. Decision Count
          </p>
          <LineCurveChart axis={curveAxis} />
          <p className="text-xs mt-3" style={{ color: "var(--text-muted)" }}>
            LLM Single: sequential — latency scales linearly. LLM Parallel: parallel async — wall-clock ≈ constant.
            Jev: compact decision primitive — sub-linear. Rules: deterministic — near-zero.
          </p>
        </Card>

        <Card>
          <p className="text-sm font-medium mb-3" style={{ color: "var(--text-primary)" }}>Scaling Data Table</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {["N Decisions", "Rules (ms)", "LLM Single (ms)", "LLM Parallel (ms)", "Jev (ms)"].map(h => (
                    <th key={h} className="text-right py-2 px-3 first:text-left mono text-[10px] uppercase tracking-wider font-medium"
                      style={{ color: "var(--text-muted)" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {COST_CURVE_POINTS.map(p => (
                  <tr key={p.decisions} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td className="py-2 px-3 mono text-xs font-medium" style={{ color: "var(--text-primary)" }}>{p.decisions}</td>
                    <td className="py-2 px-3 text-right mono text-xs" style={{ color: "var(--text-primary)" }}>{p.rules_latency_ms.toFixed(1)}</td>
                    <td className="py-2 px-3 text-right mono text-xs" style={{ color: "var(--text-primary)" }}>{p.llm_single_latency_ms}</td>
                    <td className="py-2 px-3 text-right mono text-xs" style={{ color: "var(--text-primary)" }}>{p.llm_parallel_latency_ms}</td>
                    <td className="py-2 px-3 text-right mono text-xs" style={{ color: "var(--text-primary)" }}>{p.jev_latency_ms}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs mt-3" style={{ color: "var(--text-muted)" }}>
            All values ESTIMATED. scaling-v1 experiment not yet executed. Provider blocked.
          </p>
        </Card>
      </div>
    );
  }

  function renderDemoEconomics() {
    const e2d = E2E_DEMO;
    const genCost = e2d.assumed_generation_cost_per_request_usd;
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold mb-1" style={{ color: "var(--text-primary)" }}>Control-Plane Economics</h2>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Control-plane tax = control-plane cost / total AI request cost.
            Latency share = control-plane latency / end-to-end latency.
          </p>
          <p className="text-xs mt-1 flex items-center gap-2" style={{ color: "var(--text-muted)" }}>
            <ProvenanceBadge p="ESTIMATED" note="e2e-v1 not executed; generation provider BLOCKED" />
            Generation cost: assumed ${genCost.toFixed(4)}/request (GPT-4o generation — not measured)
          </p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {e2d.systems.slice(1).map(sys => {
            const r = DEMO_ROUTERS.find(d => d.id === sys.id)!;
            return (
              <Card key={sys.id}>
                <div className="flex items-center justify-between mb-2">
                  <p className="mono text-[10px] uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>{r.label}</p>
                  <ProvenanceBadge p="ESTIMATED" />
                </div>
                <p className="mono text-xl font-medium" style={{ color: "var(--text-primary)" }}>
                  {(sys.tax_pct * 100).toFixed(1)}%
                </p>
                <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>control-plane tax</p>
                <p className="mono text-[10px] mt-1" style={{ color: "var(--text-muted)" }}>
                  {fmtCost(sys.control_cost)} ctrl · {fmtCost(sys.total_cost)} total
                </p>
              </Card>
            );
          })}
        </div>

        <Card>
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>End-to-End Breakdown</p>
            <div className="flex items-center gap-2">
              <ProvenanceBadge p="BLOCKED" note="Generation provider not configured" />
              <MetaChip>e2e-v1: BLOCKED</MetaChip>
            </div>
          </div>
          <p className="text-xs mb-4" style={{ color: "var(--status-err)" }}>
            ⚠ Generation provider not configured. e2e-v1 experiment not yet executed.
            These projections use an assumed generation cost and must not be presented as real end-to-end economics.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {["System", "Ctrl Cost", "Gen Cost", "Total", "Ctrl Latency", "Total Latency", "Tax %"].map(h => (
                    <th key={h} className="text-right py-2 px-2 first:text-left mono text-[10px] uppercase tracking-wider font-medium"
                      style={{ color: "var(--text-muted)" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {e2d.systems.map(sys => {
                  const r = DEMO_ROUTERS.find(d => d.id === sys.id)!;
                  return (
                    <tr key={sys.id} style={{ borderBottom: "1px solid var(--border)" }}>
                      <td className="py-2 px-2 mono text-xs font-medium" style={{ color: "var(--text-primary)" }}>{r.label}</td>
                      <td className="py-2 px-2 text-right mono text-xs" style={{ color: "var(--text-primary)" }}>{fmtCost(sys.control_cost)}</td>
                      <td className="py-2 px-2 text-right mono text-xs" style={{ color: "var(--text-muted)" }}>{fmtCost(sys.gen_cost)}</td>
                      <td className="py-2 px-2 text-right mono text-xs" style={{ color: "var(--text-primary)" }}>{fmtCost(sys.total_cost)}</td>
                      <td className="py-2 px-2 text-right mono text-xs" style={{ color: "var(--text-primary)" }}>{sys.control_latency}ms</td>
                      <td className="py-2 px-2 text-right mono text-xs" style={{ color: "var(--text-primary)" }}>{sys.total_latency}ms</td>
                      <td className="py-2 px-2 text-right mono text-xs font-medium"
                        style={{ color: sys.tax_pct === 0 ? "var(--status-ok)" : "var(--text-primary)" }}>
                        {(sys.tax_pct * 100).toFixed(1)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>

        <Card>
          <p className="text-sm font-medium mb-3" style={{ color: "var(--text-primary)" }}>Fast-Path Projection</p>
          <p className="text-xs mb-3" style={{ color: "var(--text-secondary)" }}>
            FastGate bypasses Jev for trivially classifiable cases (estimated ~30% bypass rate).
          </p>
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: "Always Jev", cost: FASTPATH_DEMO.always_jev.cost_per_1k_usd, latency: FASTPATH_DEMO.always_jev.latency_p50_ms },
              { label: "FastGate + Jev", cost: FASTPATH_DEMO.fast_gate_plus_jev.cost_per_1k_usd, latency: FASTPATH_DEMO.fast_gate_plus_jev.latency_p50_ms },
              { label: "Bypass Rate", cost: null, latency: null, extra: `${(FASTPATH_DEMO.fast_gate_plus_jev.bypass_rate * 100).toFixed(0)}%` },
            ].map(({ label, cost, latency, extra }) => (
              <div key={label} className="p-3 rounded" style={{ background: "var(--surface-alt)", border: "1px solid var(--border)" }}>
                <p className="mono text-[10px] uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>{label}</p>
                {extra ? (
                  <p className="mono text-xl font-medium" style={{ color: "var(--text-primary)" }}>{extra}</p>
                ) : (
                  <>
                    <p className="mono text-sm font-medium" style={{ color: "var(--text-primary)" }}>{fmtCost(cost ?? 0)} / 1K</p>
                    <p className="mono text-xs" style={{ color: "var(--text-muted)" }}>p50 {latency}ms</p>
                  </>
                )}
                <ProvenanceBadge p="ESTIMATED" />
              </div>
            ))}
          </div>
        </Card>
      </div>
    );
  }

  function renderDemoReliability() {
    const REL_ROWS: { label: string; format: (r: DemoRouter) => string }[] = [
      { label: "Schema failure rate",          format: r => fmtPct(r.schema_failure_rate) },
      { label: "Bad-send rate",                format: r => fmtPct(r.bad_send_rate) },
      { label: "Over-escalation rate",         format: r => fmtPct(r.over_escalation_rate) },
      { label: "Missed policy violation rate", format: r => fmtPct(r.missed_policy_rate) },
      { label: "Timeout rate",                 format: r => fmtPct(r.timeout_rate) },
      { label: "Retry rate",                   format: r => fmtPct(r.retry_rate) },
      { label: "Schema reliability",           format: r => fmtPct(r.schema_reliability) },
    ];

    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold mb-1" style={{ color: "var(--text-primary)" }}>Reliability</h2>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Schema failures, safety-sensitive error rates, and provider reliability.
            Failures are never dropped from results.
          </p>
        </div>
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  <th className="text-left py-2 pr-4 mono text-[10px] uppercase tracking-wider font-medium"
                    style={{ color: "var(--text-muted)" }}>Metric</th>
                  {DEMO_ROUTERS.map(r => (
                    <th key={r.id} className="text-right py-2 px-3 mono text-[10px] uppercase tracking-wider font-medium"
                      style={{ color: "var(--text-muted)" }}>
                      <div>{r.label}</div>
                      <ProvenanceBadge p={r.provenance} />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {REL_ROWS.map(({ label, format }) => (
                  <tr key={label} style={{ borderBottom: "1px solid var(--border)" }}
                    className="hover:bg-[var(--surface-alt)] transition-colors">
                    <td className="py-2.5 pr-4 mono text-xs" style={{ color: "var(--text-secondary)" }}>{label}</td>
                    {DEMO_ROUTERS.map(r => (
                      <td key={r.id} className="py-2.5 px-3 text-right mono text-xs" style={{ color: "var(--text-primary)" }}>
                        {format(r)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs mt-4" style={{ color: "var(--text-muted)" }}>
            Rules values MEASURED from harness validation. LLM/Jev values ESTIMATED from benchmark config.
            Failures remain in results — none are dropped.
          </p>
        </Card>
      </div>
    );
  }

  function renderDemoRuns() {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold mb-1" style={{ color: "var(--text-primary)" }}>Run Explorer (Demo)</h2>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            One harness validation run executed (rules-only). Full 4-router run blocked pending credentials.
          </p>
        </div>
        <Card>
          <div className="flex items-start justify-between gap-4 mb-3">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: "var(--status-ok)" }} />
                <p className="mono text-xs font-medium" style={{ color: "var(--text-primary)" }}>
                  harness-validation-rules-only · 2026-09-20
                </p>
              </div>
              <div className="flex gap-2 flex-wrap mt-2">
                <MetaChip>dataset: synthetic_support_v1</MetaChip>
                <MetaChip>split: test</MetaChip>
                <MetaChip>75 examples</MetaChip>
                <MetaChip>RULES</MetaChip>
              </div>
            </div>
            <div className="flex gap-2">
              <ProvenanceBadge p="MEASURED" note="Local RulesRouter harness validation" />
              <span className="mono text-[10px] px-2 py-0.5 rounded"
                style={{ background: "var(--surface-alt)", color: "var(--status-ok)", border: "1px solid var(--border)" }}>
                DEMO RUN
              </span>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3 mt-3">
            {[
              { label: "Action Accuracy", value: "90.7%", note: "MEASURED" },
              { label: "Severity Accuracy", value: "42.7%", note: "MEASURED" },
              { label: "Category Accuracy", value: "68.0%", note: "MEASURED" },
            ].map(({ label, value, note }) => (
              <div key={label} className="p-3 rounded" style={{ background: "var(--surface-alt)", border: "1px solid var(--border)" }}>
                <p className="mono text-[10px] uppercase tracking-wider mb-1" style={{ color: "var(--text-muted)" }}>{label}</p>
                <p className="mono text-lg font-semibold" style={{ color: "var(--text-primary)" }}>{value}</p>
                <ProvenanceBadge p="MEASURED" />
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <div className="flex items-center gap-2 mb-2">
            <AlertCircle size={14} style={{ color: "var(--status-warn)" }} />
            <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Blocked Runs</p>
          </div>
          <p className="text-xs mb-3" style={{ color: "var(--text-secondary)" }}>
            The following runs cannot execute until external credentials are provided:
          </p>
          <div className="space-y-2">
            {["LLM SINGLE", "LLM PARALLEL", "JEV"].map(router => (
              <div key={router} className="flex items-center justify-between py-2 px-3 rounded"
                style={{ background: "var(--surface-alt)", border: "1px solid var(--border)" }}>
                <span className="mono text-xs" style={{ color: "var(--text-secondary)" }}>{router}</span>
                <ProvenanceBadge p="BLOCKED" note="Provider credentials unavailable" />
              </div>
            ))}
          </div>
        </Card>
      </div>
    );
  }

  function renderDemoDataset() {
    const ds = DEMO_DATASET;
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold mb-1" style={{ color: "var(--text-primary)" }}>Dataset</h2>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Benchmark dataset metadata. See docs/DATASET.md for construction protocol.
          </p>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: "Total Examples", value: ds.total_examples.toString() },
            { label: "Train", value: ds.train_examples.toString() },
            { label: "Validation", value: ds.validation_examples.toString() },
            { label: "Test (Frozen)", value: ds.test_examples.toString() },
          ].map(({ label, value }) => (
            <Card key={label}>
              <div className="flex items-center justify-between mb-1">
                <p className="mono text-[10px] uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>{label}</p>
                <ProvenanceBadge p="MEASURED" />
              </div>
              <p className="mono text-xl font-medium" style={{ color: "var(--text-primary)" }}>{value}</p>
            </Card>
          ))}
        </div>
        <Card>
          <p className="text-sm font-medium mb-3" style={{ color: "var(--text-primary)" }}>Dataset Metadata</p>
          <div className="grid grid-cols-2 gap-x-8 gap-y-2">
            {[
              ["Name", ds.name],
              ["Source Type", ds.source_type],
              ["Quality Gate", ds.quality_gate],
              ["Leakage Detected", ds.leakage_detected ? "YES ⚠" : "None"],
              ["Test Hash Prefix", ds.test_hash_prefix],
              ["Frozen", ds.freeze_timestamp.split("T")[0]],
            ].map(([k, v]) => (
              <div key={k} className="flex items-center gap-3">
                <span className="mono text-[10px] uppercase tracking-wider w-28 flex-shrink-0"
                  style={{ color: "var(--text-muted)" }}>{k}</span>
                <span className="mono text-xs" style={{ color: "var(--text-primary)" }}>{v}</span>
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <p className="text-sm font-medium mb-3" style={{ color: "var(--text-primary)" }}>Label Distribution (Test Set — MEASURED)</p>
          <div className="grid grid-cols-3 gap-4">
            {[
              { title: "Action", data: ds.action_dist },
              { title: "Severity", data: ds.severity_dist },
              { title: "Category", data: ds.category_dist },
            ].map(({ title, data }) => (
              <div key={title}>
                <p className="mono text-[10px] uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>{title}</p>
                <div className="space-y-1">
                  {Object.entries(data).map(([k, v]) => (
                    <div key={k} className="flex items-center justify-between">
                      <span className="mono text-xs" style={{ color: "var(--text-secondary)" }}>{k}</span>
                      <span className="mono text-xs font-medium" style={{ color: "var(--text-primary)" }}>{v}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <div className="flex items-start gap-2">
            <Info size={14} className="flex-shrink-0 mt-0.5" style={{ color: "var(--text-muted)" }} />
            <div>
              <p className="text-sm font-medium mb-1" style={{ color: "var(--text-primary)" }}>Dataset Limitation</p>
              <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                {ds.limitation} Labels are rule-based deterministic — not from human annotation.
                The test split is frozen and must not be used to tune prompts, rules, thresholds, or policies.
              </p>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  // ── Live tab renderers ────────────────────────────────────────────────────

  function renderOverview() {
    return (
      <div className="space-y-8">
        <section className="py-4">
          <h2 className="text-2xl font-semibold tracking-tight mb-3"
            style={{ color: "var(--text-primary)" }}>
            Measuring the Economics<br />of System-One Intelligence
          </h2>
          <p className="text-sm max-w-2xl leading-relaxed" style={{ color: "var(--text-secondary)" }}>
            AI systems generate. But around every generation step sits another workload:{" "}
            <strong style={{ color: "var(--text-primary)" }}>decide.</strong> JevRoute benchmarks
            whether structured software decisions require autoregressive inference — or whether
            a specialized System-One model can deliver equivalent quality at a lower control-plane cost.
          </p>
          <p className="text-xs mt-3 max-w-xl" style={{ color: "var(--text-muted)" }}>
            No winner is assumed. The benchmark measures where Jev helps, where it does not,
            how much it costs, and whether any local advantage survives end-to-end.
          </p>
        </section>

        <section>
          <SectionLabel>System Overview</SectionLabel>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              {
                icon: <Server size={14} />, label: "Experiments Run",
                value: `${completedCount} / ${ALL_EXPERIMENTS.length}`,
                sub: completedCount === 0 ? "No runs yet" : `${completedCount} complete`
              },
              {
                icon: <BarChart2 size={14} />, label: "Total Decisions",
                value: totalDecisions > 0 ? totalDecisions.toString() : "—",
                sub: totalDecisions > 0 ? "baseline-v1" : "Awaiting data"
              },
              {
                icon: <Clock size={14} />, label: "p95 Latency",
                value: baselineMetrics.length > 0
                  ? fmtMs(Math.min(...baselineMetrics.filter(r => r.p95_latency_ms !== null).map(r => r.p95_latency_ms!)))
                  : "—",
                sub: baselineMetrics.length > 0 ? "best across routers" : "No benchmark data"
              },
              {
                icon: <DollarSign size={14} />, label: "Cost / Correct",
                value: baselineMetrics.length > 0
                  ? fmtCost(Math.min(...baselineMetrics.filter(r => r.cost_per_correct_decision_usd !== null).map(r => r.cost_per_correct_decision_usd!)))
                  : "—",
                sub: baselineMetrics.length > 0 ? "best across routers" : "No benchmark data"
              },
            ].map(({ icon, label, value, sub }) => (
              <Card key={label}>
                <div className="flex items-center gap-1.5 mb-2" style={{ color: "var(--text-muted)" }}>
                  {icon}
                  <span className="mono text-[10px] uppercase tracking-wider">{label}</span>
                </div>
                <p className="mono text-2xl font-medium" style={{ color: "var(--text-primary)" }}>{value}</p>
                <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>{sub}</p>
              </Card>
            ))}
          </div>
        </section>

        <section>
          <SectionLabel>Experiment Status</SectionLabel>
          <Card>
            <div className="space-y-0">
              {ALL_EXPERIMENTS.map(({ id, label, icon: Icon }, i) => {
                const exp = experiments.find(e => e.experiment_id === id);
                const state = exp?.status ?? "NOT_RUN";
                return (
                  <div key={id}
                    className="flex items-center justify-between py-3"
                    style={{ borderBottom: i < ALL_EXPERIMENTS.length - 1 ? "1px solid var(--border)" : "none" }}>
                    <div className="flex items-center gap-3">
                      <StatusDot state={state} />
                      <Icon size={13} style={{ color: "var(--text-muted)" }} />
                      <div>
                        <p className="mono text-xs font-medium" style={{ color: "var(--text-primary)" }}>{id}</p>
                        <p className="text-xs" style={{ color: "var(--text-muted)" }}>{label}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      {exp && exp.routers.length > 0 && (
                        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                          {exp.routers.map(r => ROUTER_DISPLAY[r] ?? r.toUpperCase()).join(", ")}
                        </span>
                      )}
                      <span className="mono text-[10px] px-2 py-0.5 rounded"
                        style={{ background: "var(--surface-alt)", color: statusColor(state), border: "1px solid var(--border)" }}>
                        {statusLabel(state)}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        </section>

        <section>
          <SectionLabel>Backend Connection</SectionLabel>
          <Card>
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div className="flex items-center gap-3">
                <Activity size={16} style={{ color: connection === "ok" ? "var(--status-ok)" : "var(--status-err)" }} />
                <div>
                  <p className="mono text-xs font-medium" style={{ color: "var(--text-primary)" }}>
                    {API_BASE}/api/v1/status
                  </p>
                  <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                    {connection === "ok"
                      ? `Connected · last checked ${lastChecked}`
                      : connection === "error"
                      ? "Cannot reach backend — run: uvicorn jevroute.api.app:app --reload"
                      : "Connecting…"}
                  </p>
                </div>
              </div>
              {apiStatus && (
                <div className="flex gap-2 flex-wrap">
                  <MetaChip>router: {apiStatus.active_router}</MetaChip>
                  <MetaChip>env: {apiStatus.environment}</MetaChip>
                  <MetaChip>results: {apiStatus.benchmark_results_available ? "available" : "none"}</MetaChip>
                </div>
              )}
            </div>
          </Card>
        </section>
      </div>
    );
  }

  function renderComparison() {
    const ROUTERS_ORDER = ["rules", "llm_single", "llm_parallel", "jev", "mock_jev"];
    const sorted = [...baselineMetrics].sort(
      (a, b) => ROUTERS_ORDER.indexOf(a.router) - ROUTERS_ORDER.indexOf(b.router)
    );
    const hasData = sorted.length > 0;

    const columns = sorted.map(r => ROUTER_DISPLAY[r.router] ?? r.router.toUpperCase());

    const rows: { label: string; key: keyof RouterRow; format: (v: RouterRow) => string }[] = [
      { label: "p50 latency",          key: "p50_latency_ms",              format: r => fmtMs(r.p50_latency_ms) },
      { label: "p95 latency",          key: "p95_latency_ms",              format: r => fmtMs(r.p95_latency_ms) },
      { label: "p99 latency",          key: "p99_latency_ms",              format: r => fmtMs(r.p99_latency_ms) },
      { label: "accuracy",             key: "accuracy",                    format: r => fmtPct(r.accuracy) },
      { label: "macro F1",             key: "macro_f1",                    format: r => fmt(r.macro_f1, 3) },
      { label: "cost / 1K decisions",  key: "cost_per_1k_decisions_usd",   format: r => fmtCost(r.cost_per_1k_decisions_usd) },
      { label: "cost / correct",       key: "cost_per_correct_decision_usd",format: r => fmtCost(r.cost_per_correct_decision_usd) },
      { label: "throughput",           key: "decision_throughput_per_s",   format: r => r.decision_throughput_per_s !== null ? fmt(r.decision_throughput_per_s, 1) + " /s" : "—" },
      { label: "schema failures",      key: "schema_failure_rate",         format: r => fmtPct(r.schema_failure_rate) },
      { label: "bad-send rate",        key: "bad_send_rate",               format: r => fmtPct(r.bad_send_rate) },
      { label: "over-escalation rate", key: "over_escalation_rate",        format: r => fmtPct(r.over_escalation_rate) },
      { label: "Brier score",          key: "brier_score",                 format: r => r.brier_score !== null ? fmt(r.brier_score, 4) : "N/A" },
      { label: "ECE",                  key: "ece",                         format: r => r.ece !== null ? fmt(r.ece, 4) : "N/A" },
    ];

    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold mb-1" style={{ color: "var(--text-primary)" }}>System Comparison</h2>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Measured performance across all four benchmark participants. baseline-v1 dataset.
          </p>
        </div>

        {!hasData ? (
          <AwaitingData label="baseline-v1" />
        ) : (
          <Card>
            <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
              <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Router Performance</p>
              <MetaChip>baseline-v1 · {sorted[0]?.examples ?? "?"} examples</MetaChip>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    <th className="text-left py-2 pr-6 mono text-[10px] uppercase tracking-wider font-medium"
                      style={{ color: "var(--text-muted)" }}>Metric</th>
                    {columns.map(c => (
                      <th key={c} className="text-right py-2 px-4 mono text-[10px] uppercase tracking-wider font-medium"
                        style={{ color: "var(--text-muted)" }}>{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map(({ label, format }) => (
                    <tr key={label} style={{ borderBottom: "1px solid var(--border)" }}
                      className="transition-colors duration-100 hover:bg-[var(--surface-alt)]">
                      <td className="py-2.5 pr-6 mono text-xs" style={{ color: "var(--text-secondary)" }}>{label}</td>
                      {sorted.map(r => (
                        <td key={r.router} className="py-2.5 px-4 text-right mono text-xs"
                          style={{ color: "var(--text-primary)" }}>
                          {format(r)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs mt-4" style={{ color: "var(--text-muted)" }}>
              All values sourced from measured benchmark results. No values have been fabricated.
            </p>
          </Card>
        )}
      </div>
    );
  }

  function renderCostCurve() {
    const scalingExp = experiments.find(e => e.experiment_id === "scaling-v1");
    const hasData = scalingExp?.status === "COMPLETE";
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold mb-1" style={{ color: "var(--text-primary)" }}>Intelligence Cost Curve</h2>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            How does control-plane cost scale as the number of structured decisions per request increases?
          </p>
          <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
            scaling-v1 experiment: 2 → 4 → 6 → 8 → 12 decisions per request.
          </p>
        </div>
        <Card>
          {!hasData ? (
            <>
              <div className="flex items-center justify-between mb-4">
                <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Cost vs. Decision Count</p>
                <span className="mono text-[10px] px-2 py-1 rounded"
                  style={{ background: "var(--surface-alt)", color: "var(--text-muted)", border: "1px solid var(--border)" }}>
                  scaling-v1: {statusLabel(scalingExp?.status ?? "NOT_RUN")}
                </span>
              </div>
              <AwaitingData label="scaling-v1" />
            </>
          ) : (
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              Scaling data available — enable demo mode to see projections.
            </p>
          )}
        </Card>
      </div>
    );
  }

  function renderEconomics() {
    const e2eExp = experiments.find(e => e.experiment_id === "e2e-v1");
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold mb-1" style={{ color: "var(--text-primary)" }}>Control-Plane Economics</h2>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Control-plane tax = control-plane cost / total AI request cost.
          </p>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {["Control-Plane Cost", "Total AI Cost", "Control-Plane Tax", "Latency Share"].map(label => (
            <Card key={label}>
              <p className="mono text-[10px] uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>{label}</p>
              <p className="mono text-2xl font-medium" style={{ color: "var(--text-primary)" }}>—</p>
            </Card>
          ))}
        </div>
        <Card>
          <div className="flex items-center gap-2 mb-2">
            <StatusDot state={e2eExp?.status ?? "NOT_RUN"} />
            <span className="mono text-xs" style={{ color: "var(--text-muted)" }}>
              e2e-v1: {statusLabel(e2eExp?.status ?? "NOT_RUN")}
            </span>
          </div>
          <AwaitingData label="e2e-v1" />
        </Card>
      </div>
    );
  }

  function renderReliability() {
    const hasData = baselineMetrics.length > 0;
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold mb-1" style={{ color: "var(--text-primary)" }}>Reliability</h2>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Schema failures, safety-sensitive error rates, and provider reliability.
          </p>
        </div>
        {!hasData ? <AwaitingData label="baseline-v1" /> : (
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    <th className="text-left py-2 pr-6 mono text-[10px] uppercase tracking-wider font-medium"
                      style={{ color: "var(--text-muted)" }}>Metric</th>
                    {baselineMetrics.map(r => (
                      <th key={r.router} className="text-right py-2 px-4 mono text-[10px] uppercase tracking-wider font-medium"
                        style={{ color: "var(--text-muted)" }}>
                        {ROUTER_DISPLAY[r.router] ?? r.router.toUpperCase()}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[
                    { label: "Schema failure rate",          format: (r: RouterRow) => fmtPct(r.schema_failure_rate) },
                    { label: "Bad-send rate",                format: (r: RouterRow) => fmtPct(r.bad_send_rate) },
                    { label: "Over-escalation rate",         format: (r: RouterRow) => fmtPct(r.over_escalation_rate) },
                    { label: "Missed policy violation rate", format: (r: RouterRow) => fmtPct(r.missed_policy_violation_rate) },
                  ].map(({ label, format }) => (
                    <tr key={label} style={{ borderBottom: "1px solid var(--border)" }}
                      className="hover:bg-[var(--surface-alt)] transition-colors">
                      <td className="py-2.5 pr-6 mono text-xs" style={{ color: "var(--text-secondary)" }}>{label}</td>
                      {baselineMetrics.map(r => (
                        <td key={r.router} className="py-2.5 px-4 text-right mono text-xs" style={{ color: "var(--text-primary)" }}>
                          {format(r)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    );
  }

  function renderRuns() {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold mb-1" style={{ color: "var(--text-primary)" }}>Run Explorer</h2>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Each run is an immutable benchmark execution.
          </p>
        </div>
        {experiments.filter(e => e.status === "COMPLETE").length === 0 ? (
          <AwaitingData label="any experiment" />
        ) : (
          <div className="space-y-3">
            {experiments.filter(e => e.status === "COMPLETE").map(exp => (
              <Card key={exp.experiment_id}>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <StatusDot state={exp.status} />
                      <p className="mono text-xs font-medium" style={{ color: "var(--text-primary)" }}>
                        {exp.experiment_id}
                      </p>
                    </div>
                    <div className="flex gap-3 flex-wrap mt-2">
                      {exp.dataset && <MetaChip>dataset: {exp.dataset}</MetaChip>}
                      {exp.split && <MetaChip>split: {exp.split}</MetaChip>}
                      <MetaChip>{exp.num_runs} run{exp.num_runs !== 1 ? "s" : ""}</MetaChip>
                      {exp.routers.map(r => <MetaChip key={r}>{ROUTER_DISPLAY[r] ?? r}</MetaChip>)}
                    </div>
                  </div>
                  {exp.last_run_at && (
                    <p className="mono text-[10px] flex-shrink-0" style={{ color: "var(--text-muted)" }}>
                      {new Date(exp.last_run_at).toLocaleString()}
                    </p>
                  )}
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    );
  }

  function renderDataset() {
    const totalExamples = datasets.reduce((sum, d) => sum + d.examples, 0);
    const splitCounts: Record<string, number> = {};
    datasets.forEach(d => { splitCounts[d.split] = (splitCounts[d.split] ?? 0) + d.examples; });

    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold mb-1" style={{ color: "var(--text-primary)" }}>Dataset</h2>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Benchmark fixtures and dataset metadata.
          </p>
        </div>
        {datasets.length === 0 ? (
          <AwaitingData label="dataset files" />
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Card>
                <p className="mono text-[10px] uppercase tracking-wider mb-1" style={{ color: "var(--text-muted)" }}>Total Examples</p>
                <p className="mono text-xl font-medium" style={{ color: "var(--text-primary)" }}>{totalExamples}</p>
              </Card>
              {["train", "validation", "test"].map(split => (
                <Card key={split}>
                  <p className="mono text-[10px] uppercase tracking-wider mb-1" style={{ color: "var(--text-muted)" }}>{split}</p>
                  <p className="mono text-xl font-medium" style={{ color: "var(--text-primary)" }}>{splitCounts[split] ?? 0}</p>
                </Card>
              ))}
            </div>
            <Card>
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border)" }}>
                      {["Name", "Split", "Examples", "Path"].map(h => (
                        <th key={h} className="text-left py-2 px-3 mono text-[10px] uppercase tracking-wider font-medium"
                          style={{ color: "var(--text-muted)" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {datasets.map((d, i) => (
                      <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}
                        className="hover:bg-[var(--surface-alt)] transition-colors">
                        <td className="py-2.5 px-3 mono text-xs" style={{ color: "var(--text-primary)" }}>{d.name}</td>
                        <td className="py-2.5 px-3 mono text-xs" style={{ color: "var(--text-secondary)" }}>{d.split}</td>
                        <td className="py-2.5 px-3 mono text-xs" style={{ color: "var(--text-primary)" }}>{d.examples}</td>
                        <td className="py-2.5 px-3 mono text-xs" style={{ color: "var(--text-muted)" }}>{d.path}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </>
        )}
      </div>
    );
  }

  function renderMethodology() {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold mb-1" style={{ color: "var(--text-primary)" }}>Methodology</h2>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Research question, benchmark design, fairness rules, and measurement definitions.
          </p>
        </div>
        <Card>
          <p className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Research Question</p>
          <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
            When AI systems spend computation deciding what to do rather than generating what to say,
            does a System-One decision primitive materially change the economics of the control plane?
          </p>
        </Card>
        <Card>
          <p className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Benchmark Participants</p>
          <div className="space-y-3">
            {[
              { name: "RULES",        version: "rules-v1",         desc: "Deterministic keyword/regex baseline. Establishes a zero-cost lower bound on control-plane latency." },
              { name: "LLM SINGLE",   version: "llm-single-v1",    desc: "One LLM call producing the complete structured decision. Represents the current common practice." },
              { name: "LLM PARALLEL", version: "llm-parallel-v1",  desc: "Six independent async LLM calls, one per decision dimension. Best-case latency for multi-decision LLM workloads." },
              { name: "JEV",          version: "jev-adapter-0.1",  desc: "Specialized System-One decision model. The system under study." },
            ].map(({ name, version, desc }) => (
              <div key={name} className="flex gap-3">
                <div className="flex-shrink-0">
                  <p className="mono text-xs font-semibold" style={{ color: "var(--text-primary)" }}>{name}</p>
                  <p className="mono text-[10px]" style={{ color: "var(--text-muted)" }}>{version}</p>
                </div>
                <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>{desc}</p>
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <p className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Fairness Rules</p>
          <ul className="space-y-1.5">
            {[
              "Every router receives equivalent application state.",
              "Every router produces the same normalized DecisionResult schema.",
              "All token usage, latency, API calls, and retries are counted.",
              "Failed calls remain in results as failed observations.",
              "Test data is never used to tune prompts, rules, thresholds, or policies.",
              "Raw observations are recorded before aggregate metrics are derived.",
              "The benchmark does not assume Jev wins.",
            ].map(rule => (
              <li key={rule} className="flex items-start gap-2">
                <CheckCircle2 size={12} className="flex-shrink-0 mt-0.5" style={{ color: "var(--status-ok)" }} />
                <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{rule}</p>
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <p className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Decision Schema</p>
          <pre className="mono text-xs p-3 rounded overflow-x-auto"
            style={{ background: "var(--surface-alt)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>
{`{
  "severity":          "P1 | P2 | P3 | P4",
  "category":          "Billing | Bug | Feature | Account | Other",
  "policy_violation":  "true | false",
  "hallucination_risk":"0.0 – 1.0",
  "tone_risk":         "0.0 – 1.0",
  "action":            "SEND | HOLD | ESCALATE"
}`}
          </pre>
        </Card>
        <Card>
          <p className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Limitations</p>
          <ul className="space-y-1.5">
            {[
              "Single-domain workload (AI customer-support control plane).",
              "Current dataset is synthetic (rule-based labels), not the final research dataset.",
              "Results may not generalize to other workload types.",
              "Real Jev API benchmarks require external credentials (see OQ-001).",
              "Network latency effects are not isolated in the current setup.",
              "Vendor pricing changes would affect cost comparisons.",
            ].map(lim => (
              <li key={lim} className="flex items-start gap-2">
                <AlertCircle size={12} className="flex-shrink-0 mt-0.5" style={{ color: "var(--text-muted)" }} />
                <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{lim}</p>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    );
  }

  function renderReproducibility() {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold mb-1" style={{ color: "var(--text-primary)" }}>Reproducibility</h2>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Every benchmark run is traceable to its configuration.
          </p>
        </div>
        {demoMode && (
          <Card>
            <p className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Demo Experiment Metadata</p>
            <div className="grid grid-cols-2 gap-x-8 gap-y-2">
              {[
                ["Experiment ID", DEMO_EXPERIMENT.id],
                ["Dataset", DEMO_EXPERIMENT.dataset],
                ["Split", DEMO_EXPERIMENT.split],
                ["Examples", DEMO_EXPERIMENT.examples.toString()],
                ["Concurrency", DEMO_EXPERIMENT.concurrency.toString()],
                ["Model", DEMO_EXPERIMENT.model],
                ["Prompt Version", DEMO_EXPERIMENT.prompt_version],
                ["Schema Version", DEMO_EXPERIMENT.schema_version],
                ["Policy Version", DEMO_EXPERIMENT.policy_version],
                ["Code SHA", DEMO_EXPERIMENT.code_sha],
                ["Timestamp", DEMO_EXPERIMENT.timestamp.split("T")[0]],
              ].map(([k, v]) => (
                <div key={k} className="flex items-center gap-3">
                  <span className="mono text-[10px] uppercase tracking-wider w-32 flex-shrink-0"
                    style={{ color: "var(--text-muted)" }}>{k}</span>
                  <span className="mono text-xs" style={{ color: "var(--text-primary)" }}>{v}</span>
                </div>
              ))}
            </div>
            <p className="mono text-xs mt-4 p-2 rounded" style={{ background: "var(--surface-alt)", color: "var(--status-warn)", border: "1px solid var(--border)" }}>
              ⚠ {DEMO_EXPERIMENT.validity_note}
            </p>
          </Card>
        )}
        <Card>
          <p className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Required Metadata per Run</p>
          <div className="grid grid-cols-2 gap-x-8 gap-y-1.5">
            {[
              ["dataset version", "decision_schema_version"],
              ["code commit SHA", "policy_version"],
              ["router version", "prompt_version (LLM)"],
              ["experiment config", "model/provider identifier"],
              ["benchmark timestamp", "concurrency"],
              ["environment metadata", ""],
            ].map(([a, b], i) => (
              <div key={i} className="flex gap-6">
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 size={10} style={{ color: "var(--status-ok)" }} />
                  <span className="mono text-[10px]" style={{ color: "var(--text-secondary)" }}>{a}</span>
                </div>
                {b && (
                  <div className="flex items-center gap-1.5">
                    <CheckCircle2 size={10} style={{ color: "var(--status-ok)" }} />
                    <span className="mono text-[10px]" style={{ color: "var(--text-secondary)" }}>{b}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <p className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Run Commands</p>
          <div className="space-y-4">
            <div>
              <p className="mono text-[10px] uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>
                Mock benchmark (no API keys required)
              </p>
              <pre className="mono text-xs p-3 rounded overflow-x-auto"
                style={{ background: "var(--surface-alt)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>
{`pytest                          # 157 tests, no network
uvicorn jevroute.api.app:app --reload  # backend`}
              </pre>
            </div>
            <div>
              <p className="mono text-[10px] uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>
                Full benchmark run
              </p>
              <pre className="mono text-xs p-3 rounded overflow-x-auto"
                style={{ background: "var(--surface-alt)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>
{`# Configure credentials in .env
cp .env.example .env
# Add OpenAI billing credits + JEV_API_KEY
python -m jevroute.benchmark.runner --config experiments/baseline_research_v1.yaml`}
              </pre>
            </div>
          </div>
        </Card>
        <Card>
          <p className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Result Storage</p>
          <pre className="mono text-xs p-3 rounded overflow-x-auto"
            style={{ background: "var(--surface-alt)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>
{`results/
├── raw/
│   └── baseline-v1/
│       ├── rules.jsonl      ← immutable raw observations
│       ├── llm_single.jsonl
│       ├── llm_parallel.jsonl
│       └── jev.jsonl
├── aggregate/
│   └── baseline-v1.csv     ← one row per router
└── metadata/
    └── baseline-v1.json    ← run config, env, versions`}
          </pre>
        </Card>
      </div>
    );
  }

  // ── Route tabs through demo/live ──────────────────────────────────────────

  const tabContent: Record<Tab, () => React.ReactNode> = {
    overview:        demoMode ? renderDemoOverview        : renderOverview,
    comparison:      demoMode ? renderDemoComparison      : renderComparison,
    cost_curve:      demoMode ? renderDemoCostCurve       : renderCostCurve,
    economics:       demoMode ? renderDemoEconomics       : renderEconomics,
    reliability:     demoMode ? renderDemoReliability     : renderReliability,
    runs:            demoMode ? renderDemoRuns            : renderRuns,
    dataset:         demoMode ? renderDemoDataset         : renderDataset,
    methodology:     renderMethodology,
    reproducibility: renderReproducibility,
  };

  return (
    <div className="min-h-dvh" style={{ background: "var(--bg)" }}>

      {/* ── Demo Banner ────────────────────────────────────────────────────── */}
      {demoMode && <DemoBanner />}

      {/* ── Header ────────────────────────────────────────────────────────── */}
      <header style={{ borderBottom: "1px solid var(--border)", background: "var(--surface)" }}>
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h1 className="mono text-sm font-semibold tracking-widest uppercase"
              style={{ color: "var(--text-primary)" }}>
              JEVROUTE
            </h1>
            <p className="mono text-[11px] tracking-wider mt-0.5"
              style={{ color: "var(--text-muted)" }}>
              SYSTEM-ONE CONTROL PLANE BENCHMARK
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <MetaChip>v{apiStatus?.app_version ?? "0.1.0"}</MetaChip>
            <MetaChip>SCHEMA {apiStatus?.schema_version ?? "—"}</MetaChip>
            <MetaChip>{apiStatus?.environment?.toUpperCase() ?? "LOCAL DEVELOPMENT"}</MetaChip>
            {!demoMode && (
              <span className="flex items-center gap-1.5 mono text-[10px]"
                style={{ color: connection === "ok" ? "var(--status-ok)" : connection === "error" ? "var(--status-err)" : "var(--text-muted)" }}>
                {connection === "ok" ? <CheckCircle2 size={11} /> : connection === "error" ? <AlertCircle size={11} /> : <Circle size={11} />}
                {connection === "ok" ? "API OK" : connection === "error" ? "API UNREACHABLE" : "CONNECTING"}
              </span>
            )}
            {/* LIVE / DEMO toggle */}
            <button
              onClick={toggleDemo}
              className="mono text-[10px] px-3 py-1.5 rounded border font-semibold transition-colors"
              style={{
                background: demoMode ? "#E85B35" : "var(--surface-alt)",
                color: demoMode ? "#fff" : "var(--text-secondary)",
                borderColor: demoMode ? "#E85B35" : "var(--border)",
                cursor: "pointer",
              }}>
              {demoMode ? "DEMO" : "LIVE"}
            </button>
          </div>
        </div>

        {/* Tab navigation */}
        <div className="max-w-7xl mx-auto px-6 overflow-x-auto">
          <nav className="flex gap-0 min-w-max">
            {TABS.map(({ id, label }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className="mono text-[11px] px-4 py-3 transition-colors duration-100"
                style={{
                  color: activeTab === id ? "var(--text-primary)" : "var(--text-muted)",
                  borderBottom: activeTab === id ? "2px solid var(--text-primary)" : "2px solid transparent",
                  background: "none",
                  cursor: "pointer",
                  fontWeight: activeTab === id ? "600" : "400",
                }}>
                {label.toUpperCase()}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {tabContent[activeTab]()}
      </main>

      {/* ── Footer ────────────────────────────────────────────────────────── */}
      <footer className="mt-12" style={{ borderTop: "1px solid var(--border)" }}>
        <div className="max-w-7xl mx-auto px-6 py-5 flex items-center justify-between flex-wrap gap-3">
          <p className="mono text-[11px]" style={{ color: "var(--text-muted)" }}>
            JEVROUTE · PHASE 9 · SYSTEM-ONE BENCHMARK
          </p>
          <p className="mono text-[11px]" style={{ color: "var(--text-muted)" }}>
            {demoMode
              ? "DEMO MODE — Rules: MEASURED · LLM/Jev: ESTIMATED projections only · No empirical results fabricated"
              : "No benchmark data has been fabricated. All metrics sourced from measured results."}
          </p>
        </div>
      </footer>

    </div>
  );
}
