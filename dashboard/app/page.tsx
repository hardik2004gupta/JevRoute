"use client";

import { useEffect, useState } from "react";
import { Activity, AlertCircle, BarChart2, CheckCircle2, Circle, Clock, DollarSign, FlaskConical, Server, Zap } from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────

interface ApiStatus {
  status: string;
  environment: string;
  app_version: string;
  schema_version: string;
  policy_version: string;
  active_router: string;
  benchmark_results_available: boolean;
}

type ConnectionState = "connecting" | "ok" | "error";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const EXPERIMENTS = [
  { id: "baseline-v1",    label: "Baseline Comparison" },
  { id: "scaling-v1",     label: "Decision Scaling" },
  { id: "fastpath-v1",    label: "Fast-Path Bypass" },
  { id: "context-v1",     label: "Context Scaling" },
  { id: "dependency-v1",  label: "Dependency Analysis" },
  { id: "e2e-v1",         label: "End-to-End Economics" },
];

const ROUTERS = ["RULES", "LLM SINGLE", "LLM PARALLEL", "JEV"];
const METRICS = [
  { key: "p50",           label: "p50 latency" },
  { key: "p95",           label: "p95 latency" },
  { key: "cost_1k",       label: "cost / 1K" },
  { key: "accuracy",      label: "accuracy" },
  { key: "f1",            label: "macro F1" },
  { key: "cost_correct",  label: "cost / correct" },
  { key: "throughput",    label: "throughput" },
];

// ── Sub-components ─────────────────────────────────────────────────────────

function MetaChip({ children }: { children: React.ReactNode }) {
  return (
    <span className="mono text-[10px] font-medium px-2 py-0.5 rounded border"
      style={{ color: "var(--text-muted)", borderColor: "var(--border)", background: "var(--surface-alt)" }}>
      {children}
    </span>
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

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg p-5 ${className}`}
      style={{ background: "var(--surface)", border: "1px solid var(--border)", boxShadow: "var(--shadow-sm)" }}>
      {children}
    </div>
  );
}

function EmptyCell() {
  return <span className="mono text-sm" style={{ color: "var(--text-muted)" }}>—</span>;
}

function StatusDot({ state }: { state: "NOT_RUN" | "RUNNING" | "COMPLETE" | "ERROR" }) {
  const colors: Record<string, string> = {
    NOT_RUN: "var(--status-none)",
    RUNNING: "var(--status-warn)",
    COMPLETE: "var(--status-ok)",
    ERROR: "var(--status-err)",
  };
  return (
    <span className="inline-block w-1.5 h-1.5 rounded-full mr-2"
      style={{ background: colors[state], marginBottom: 1 }} />
  );
}

// ── Main page ──────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [apiStatus, setApiStatus] = useState<ApiStatus | null>(null);
  const [lastChecked, setLastChecked] = useState<string>("");

  useEffect(() => {
    async function fetchStatus() {
      try {
        const res = await fetch(`${API_BASE}/api/v1/status`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: ApiStatus = await res.json();
        setApiStatus(data);
        setConnection("ok");
        setLastChecked(new Date().toLocaleTimeString());
      } catch {
        setConnection("error");
      }
    }
    fetchStatus();
    const t = setInterval(fetchStatus, 30_000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="min-h-dvh" style={{ background: "var(--bg)" }}>

      {/* ── Header ──────────────────────────────────────────────────────── */}
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
            <MetaChip>
              {apiStatus?.environment?.toUpperCase() ?? "LOCAL DEVELOPMENT"}
            </MetaChip>

            {/* Connection indicator */}
            <span className="flex items-center gap-1.5 mono text-[10px]"
              style={{ color: connection === "ok" ? "var(--status-ok)" : connection === "error" ? "var(--status-err)" : "var(--text-muted)" }}>
              {connection === "ok"
                ? <CheckCircle2 size={11} />
                : connection === "error"
                ? <AlertCircle size={11} />
                : <Circle size={11} />}
              {connection === "ok" ? "API OK" : connection === "error" ? "API UNREACHABLE" : "CONNECTING"}
            </span>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">

        {/* ── Hero ──────────────────────────────────────────────────────── */}
        <section className="py-6">
          <h2 className="text-2xl font-semibold tracking-tight mb-2"
            style={{ color: "var(--text-primary)" }}>
            Measuring the Economics of System-One Intelligence
          </h2>
          <p className="text-sm max-w-2xl leading-relaxed" style={{ color: "var(--text-secondary)" }}>
            AI systems do more than generate. They decide. JevRoute benchmarks whether structured
            software decisions require autoregressive inference — or whether a specialized
            System-One model can deliver equivalent quality at a lower control-plane cost.
          </p>
          <div className="mt-4 flex gap-3 flex-wrap">
            <span className="mono text-xs px-3 py-1 rounded-full"
              style={{ background: "var(--accent-dim)", color: "var(--accent)", border: "1px solid #F5D0C5" }}>
              ACTIVE ROUTER: {apiStatus?.active_router?.toUpperCase() ?? "MOCK_JEV"}
            </span>
            <span className="mono text-xs px-3 py-1 rounded-full"
              style={{ background: "var(--surface-alt)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>
              POLICY: {apiStatus?.policy_version ?? "support-policy-1.0"}
            </span>
          </div>
        </section>

        {/* ── Overview KPIs ─────────────────────────────────────────────── */}
        <section>
          <SectionLabel>System Overview</SectionLabel>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { icon: <Server size={14} />, label: "Benchmark Runs", value: "0", sub: "No runs yet" },
              { icon: <BarChart2 size={14} />, label: "Total Decisions", value: "—", sub: "Awaiting Phase 2" },
              { icon: <Clock size={14} />, label: "p95 Latency", value: "—", sub: "No benchmark data" },
              { icon: <DollarSign size={14} />, label: "Cost / Correct", value: "—", sub: "No benchmark data" },
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

        {/* ── System Comparison ─────────────────────────────────────────── */}
        <section>
          <SectionLabel>System Comparison</SectionLabel>
          <Card>
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                Router Performance
              </p>
              <span className="mono text-[10px] px-2 py-1 rounded"
                style={{ background: "var(--surface-alt)", color: "var(--text-muted)", border: "1px solid var(--border)" }}>
                AWAITING BENCHMARK DATA
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    <th className="text-left py-2 pr-6 mono text-[10px] uppercase tracking-wider font-medium"
                      style={{ color: "var(--text-muted)" }}>
                      Metric
                    </th>
                    {ROUTERS.map(r => (
                      <th key={r} className="text-right py-2 px-4 mono text-[10px] uppercase tracking-wider font-medium"
                        style={{ color: "var(--text-muted)" }}>
                        {r}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {METRICS.map(({ key, label }) => (
                    <tr key={key} style={{ borderBottom: "1px solid var(--border)" }}
                      className="transition-colors duration-150 hover:bg-[var(--surface-alt)]">
                      <td className="py-2.5 pr-6 mono text-xs" style={{ color: "var(--text-secondary)" }}>
                        {label}
                      </td>
                      {ROUTERS.map(r => (
                        <td key={r} className="py-2.5 px-4 text-right">
                          <EmptyCell />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="text-xs mt-4" style={{ color: "var(--text-muted)" }}>
              All values will be populated after <span className="mono">baseline-v1</span> executes.
              No benchmark data has been fabricated.
            </p>
          </Card>
        </section>

        {/* ── Intelligence Cost Curve ────────────────────────────────────── */}
        <section>
          <SectionLabel>Intelligence Cost Curve</SectionLabel>
          <Card>
            <div className="flex items-start justify-between mb-3">
              <div>
                <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                  Cost vs. Decision Count
                </p>
                <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
                  Scaling experiment: 2 → 4 → 6 → 8 → 12 structured decisions per request
                </p>
              </div>
              <Zap size={16} style={{ color: "var(--accent)", flexShrink: 0 }} />
            </div>

            {/* Empty state — polished, no fake curves */}
            <div className="rounded-md flex flex-col items-center justify-center py-14 my-2"
              style={{ background: "var(--surface-alt)", border: "1px dashed var(--border-strong)" }}>
              <FlaskConical size={22} style={{ color: "var(--text-muted)" }} className="mb-3" />
              <p className="mono text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                No scaling experiment has been executed yet.
              </p>
              <p className="mono text-[11px] mt-1" style={{ color: "var(--text-muted)" }}>
                Run <span style={{ color: "var(--text-secondary)" }}>scaling-v1</span> to populate this visualization.
              </p>

              {/* Placeholder axis labels only */}
              <div className="flex gap-6 mt-6 mono text-[10px]" style={{ color: "var(--text-muted)" }}>
                {[2, 4, 6, 8, 12].map(n => (
                  <span key={n}>{n} decisions</span>
                ))}
              </div>
            </div>

            <p className="text-xs mt-3" style={{ color: "var(--text-muted)" }}>
              The chart will show measured cost curves for Rules, LLM Single, LLM Parallel, and Jev.
              No winner is implied before results exist.
            </p>
          </Card>
        </section>

        {/* ── Control-Plane Economics ────────────────────────────────────── */}
        <section>
          <SectionLabel>Control-Plane Economics</SectionLabel>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: "Control-Plane Cost",      sub: "per 1K decisions" },
              { label: "Total AI Cost",            sub: "control + generation" },
              { label: "Control-Plane Tax",        sub: "cp cost / total ai cost" },
              { label: "Latency Share",            sub: "cp latency / total latency" },
            ].map(({ label, sub }) => (
              <Card key={label}>
                <p className="mono text-[10px] uppercase tracking-wider mb-2" style={{ color: "var(--text-muted)" }}>
                  {label}
                </p>
                <p className="mono text-2xl font-medium" style={{ color: "var(--text-primary)" }}>—</p>
                <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>{sub}</p>
              </Card>
            ))}
          </div>
        </section>

        {/* ── Experiment Status ──────────────────────────────────────────── */}
        <section>
          <SectionLabel>Experiment Status</SectionLabel>
          <Card>
            <div className="space-y-0">
              {EXPERIMENTS.map(({ id, label }, i) => (
                <div key={id}
                  className="flex items-center justify-between py-3"
                  style={{ borderBottom: i < EXPERIMENTS.length - 1 ? "1px solid var(--border)" : "none" }}>
                  <div className="flex items-center gap-3">
                    <StatusDot state="NOT_RUN" />
                    <div>
                      <p className="mono text-xs font-medium" style={{ color: "var(--text-primary)" }}>{id}</p>
                      <p className="text-xs" style={{ color: "var(--text-muted)" }}>{label}</p>
                    </div>
                  </div>
                  <span className="mono text-[10px] px-2 py-0.5 rounded"
                    style={{ background: "var(--surface-alt)", color: "var(--text-muted)", border: "1px solid var(--border)" }}>
                    NOT RUN
                  </span>
                </div>
              ))}
            </div>
          </Card>
        </section>

        {/* ── API Health ─────────────────────────────────────────────────── */}
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

      </main>

      {/* ── Footer ────────────────────────────────────────────────────────── */}
      <footer className="mt-12" style={{ borderTop: "1px solid var(--border)" }}>
        <div className="max-w-7xl mx-auto px-6 py-5 flex items-center justify-between flex-wrap gap-3">
          <p className="mono text-[11px]" style={{ color: "var(--text-muted)" }}>
            JEVROUTE · PHASE 1 · FOUNDATION SHELL
          </p>
          <p className="mono text-[11px]" style={{ color: "var(--text-muted)" }}>
            No benchmark data has been fabricated. All metric fields awaiting Phase 2.
          </p>
        </div>
      </footer>

    </div>
  );
}
