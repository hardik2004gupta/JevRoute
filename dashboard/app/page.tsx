"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Activity, AlertCircle, BarChart2, CheckCircle2, Circle,
  Clock, Database, DollarSign, FileText, FlaskConical,
  Server, Shield, TrendingUp, Zap, Info
} from "lucide-react";

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

function EmptyMetric() {
  return <span className="mono text-sm" style={{ color: "var(--text-muted)" }}>—</span>;
}

function NA({ title = "N/A — not applicable or not run" }: { title?: string }) {
  return (
    <span className="mono text-xs" style={{ color: "var(--text-muted)" }} title={title}>N/A</span>
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

  const completedCount = experiments.filter(e => e.status === "COMPLETE").length;
  const baselineExp = experiments.find(e => e.experiment_id === "baseline-v1");
  const totalDecisions = baselineMetrics.reduce((sum, r) => sum + (r.decisions ?? 0), 0);

  // ── Render tabs ──────────────────────────────────────────────────────────────

  function renderOverview() {
    return (
      <div className="space-y-8">
        {/* Hero */}
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

        {/* KPIs */}
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

        {/* Experiment status */}
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

        {/* Backend connection */}
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
              Brier score and ECE are N/A for systems without native probability estimates.
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
              <div className="mt-4 grid grid-cols-5 gap-2">
                {[2, 4, 6, 8, 12].map(n => (
                  <div key={n} className="text-center py-3 rounded"
                    style={{ background: "var(--surface-alt)", border: "1px solid var(--border)" }}>
                    <p className="mono text-xs font-medium" style={{ color: "var(--text-secondary)" }}>{n}</p>
                    <p className="mono text-[10px]" style={{ color: "var(--text-muted)" }}>decisions</p>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              Scaling data available — chart visualization pending Phase 4 chart implementation.
            </p>
          )}
        </Card>
        <Card>
          <p className="text-sm font-medium mb-3" style={{ color: "var(--text-primary)" }}>
            Quality × Cost Frontier
          </p>
          <p className="text-xs mb-4" style={{ color: "var(--text-secondary)" }}>
            Router position on the accuracy vs. cost tradeoff space. No system is labelled "best."
          </p>
          {baselineMetrics.length === 0 ? (
            <AwaitingData label="baseline-v1" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    {["Router", "Accuracy", "Cost / 1K", "F1", "Throughput"].map(h => (
                      <th key={h} className="text-right py-2 px-3 first:text-left mono text-[10px] uppercase tracking-wider font-medium"
                        style={{ color: "var(--text-muted)" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {baselineMetrics.map(r => (
                    <tr key={r.router} style={{ borderBottom: "1px solid var(--border)" }}
                      className="hover:bg-[var(--surface-alt)] transition-colors">
                      <td className="py-2.5 pl-0 pr-3 mono text-xs font-medium" style={{ color: "var(--text-primary)" }}>
                        {ROUTER_DISPLAY[r.router] ?? r.router.toUpperCase()}
                      </td>
                      <td className="py-2.5 px-3 text-right mono text-xs" style={{ color: "var(--text-primary)" }}>{fmtPct(r.accuracy)}</td>
                      <td className="py-2.5 px-3 text-right mono text-xs" style={{ color: "var(--text-primary)" }}>{fmtCost(r.cost_per_1k_decisions_usd)}</td>
                      <td className="py-2.5 px-3 text-right mono text-xs" style={{ color: "var(--text-primary)" }}>{fmt(r.macro_f1, 3)}</td>
                      <td className="py-2.5 px-3 text-right mono text-xs" style={{ color: "var(--text-primary)" }}>
                        {r.decision_throughput_per_s !== null ? fmt(r.decision_throughput_per_s, 1) + " /s" : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="text-xs mt-3" style={{ color: "var(--text-muted)" }}>
            Values sourced from baseline-v1 measured results. No values fabricated.
          </p>
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
            Latency share = control-plane latency / end-to-end latency.
          </p>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: "Control-Plane Cost", sub: "per 1K decisions" },
            { label: "Total AI Cost",      sub: "control + generation" },
            { label: "Control-Plane Tax",  sub: "cp cost / total cost" },
            { label: "Latency Share",      sub: "cp latency / total" },
          ].map(({ label, sub }) => (
            <Card key={label}>
              <p className="mono text-[10px] uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>{label}</p>
              <p className="mono text-2xl font-medium" style={{ color: "var(--text-primary)" }}>—</p>
              <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>{sub}</p>
            </Card>
          ))}
        </div>
        <Card>
          <p className="text-sm font-medium mb-2" style={{ color: "var(--text-primary)" }}>End-to-End Benchmark</p>
          <p className="text-xs mb-4" style={{ color: "var(--text-secondary)" }}>
            e2e-v1 compares control-plane cost against total AI request cost including simulated generation.
          </p>
          <div className="flex items-center gap-2 mb-4">
            <StatusDot state={e2eExp?.status ?? "NOT_RUN"} />
            <span className="mono text-xs" style={{ color: "var(--text-muted)" }}>
              e2e-v1: {statusLabel(e2eExp?.status ?? "NOT_RUN")}
            </span>
          </div>
          <AwaitingData label="e2e-v1" />
          <p className="text-xs mt-3" style={{ color: "var(--text-muted)" }}>
            Control-plane tax is only meaningful in the context of the full generation workload.
            Pure control-plane benchmarks show N/A for this metric.
          </p>
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
            Failures are never dropped from results.
          </p>
        </div>
        {!hasData ? (
          <AwaitingData label="baseline-v1" />
        ) : (
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
                    { label: "Brier score",                  format: (r: RouterRow) => r.brier_score !== null ? fmt(r.brier_score, 4) : "N/A" },
                    { label: "ECE",                          format: (r: RouterRow) => r.ece !== null ? fmt(r.ece, 4) : "N/A" },
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
            <p className="text-xs mt-4" style={{ color: "var(--text-muted)" }}>
              N/A = metric not applicable (e.g. Brier score requires native probability estimates).
              All failures are recorded; none are dropped from results.
            </p>
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
            Each run is an immutable benchmark execution. Raw JSONL records and aggregate CSV
            are preserved after completion.
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
            Benchmark fixtures and dataset metadata. See docs/DATASET.md for construction protocol.
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
              <p className="text-sm font-medium mb-4" style={{ color: "var(--text-primary)" }}>Dataset Files</p>
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
            <Card>
              <div className="flex items-start gap-2">
                <Info size={14} className="flex-shrink-0 mt-0.5" style={{ color: "var(--text-muted)" }} />
                <div>
                  <p className="text-sm font-medium mb-1" style={{ color: "var(--text-primary)" }}>Dataset Status</p>
                  <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                    The current dataset is a <strong>10-example synthetic CI fixture</strong> sufficient for
                    benchmark engine validation. It is not the final research dataset. Labels are
                    synthetic — see <span className="mono">docs/DATASET.md</span> for the construction protocol
                    and limitations. The test split is frozen and must not be used to tune prompts, rules,
                    thresholds, or policies.
                  </p>
                </div>
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
              { name: "JEV",          version: "jev-adapter-0.1",   desc: "Specialized System-One decision model. The system under study." },
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
              "Current dataset is a 10-example synthetic CI fixture, not the final research dataset.",
              "Results may not generalize to other workload types.",
              "Brier score and ECE are N/A for systems without native probability estimates.",
              "Real Jev API benchmarks require external credentials (see OQ-001).",
              "Network latency effects are not isolated in the current setup.",
              "Generation-dominant workloads may dilute control-plane differences.",
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
    const hasRun = baselineMetrics.length > 0;
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold mb-1" style={{ color: "var(--text-primary)" }}>Reproducibility</h2>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Every benchmark run is traceable to its configuration. Results without sufficient metadata
            are not considered reproducible.
          </p>
        </div>
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
{`pytest                          # 100+ tests, no network
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
# Run baseline experiment
python -m jevroute.benchmark.runner --config experiments/baseline.yaml`}
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
│       ├── mock_jev.jsonl
│       └── jev.jsonl
├── aggregate/
│   └── baseline-v1.csv     ← one row per router
└── metadata/
    └── baseline-v1.json    ← run config, env, versions`}
          </pre>
          <p className="text-xs mt-3" style={{ color: "var(--text-muted)" }}>
            Raw JSONL records are never modified after a run completes.
            Aggregate results are derived, never manually edited.
          </p>
        </Card>
      </div>
    );
  }

  const tabContent: Record<Tab, () => React.ReactNode> = {
    overview:        renderOverview,
    comparison:      renderComparison,
    cost_curve:      renderCostCurve,
    economics:       renderEconomics,
    reliability:     renderReliability,
    runs:            renderRuns,
    dataset:         renderDataset,
    methodology:     renderMethodology,
    reproducibility: renderReproducibility,
  };

  return (
    <div className="min-h-dvh" style={{ background: "var(--bg)" }}>

      {/* ── Header ──────────────────────────────────────────────────────────── */}
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
            <span className="flex items-center gap-1.5 mono text-[10px]"
              style={{ color: connection === "ok" ? "var(--status-ok)" : connection === "error" ? "var(--status-err)" : "var(--text-muted)" }}>
              {connection === "ok" ? <CheckCircle2 size={11} /> : connection === "error" ? <AlertCircle size={11} /> : <Circle size={11} />}
              {connection === "ok" ? "API OK" : connection === "error" ? "API UNREACHABLE" : "CONNECTING"}
            </span>
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

      {/* ── Footer ────────────────────────────────────────────────────────────── */}
      <footer className="mt-12" style={{ borderTop: "1px solid var(--border)" }}>
        <div className="max-w-7xl mx-auto px-6 py-5 flex items-center justify-between flex-wrap gap-3">
          <p className="mono text-[11px]" style={{ color: "var(--text-muted)" }}>
            JEVROUTE · PHASE 3+4 · RESEARCH OBSERVATORY
          </p>
          <p className="mono text-[11px]" style={{ color: "var(--text-muted)" }}>
            No benchmark data has been fabricated. All metrics sourced from measured results.
          </p>
        </div>
      </footer>

    </div>
  );
}
