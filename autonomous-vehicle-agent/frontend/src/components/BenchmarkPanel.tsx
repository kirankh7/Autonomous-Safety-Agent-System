import { useState } from "react";
import { Gauge } from "lucide-react";
import type { BenchmarkResult } from "../types";
import { api } from "../api";
import { Button, Panel } from "./ui";

const COLS: { key: keyof BenchmarkResult["summary"][number]; label: string }[] = [
  { key: "node_calls", label: "Agent calls" },
  { key: "tool_calls", label: "Tool calls" },
  { key: "retrieval_calls", label: "RAG calls" },
  { key: "messages", label: "Messages" },
  { key: "mean_latency_ms", label: "ms / report" },
  { key: "verified_alerts", label: "Verified alerts" },
  { key: "false_alerts", label: "False alerts" },
  { key: "false_warnings", label: "False warnings" },
  { key: "escalations", label: "Escalations" },
  { key: "decisions_match_hybrid", label: "Same decisions" },
];

/** Runs the five scenarios under each coordination configuration (in a temporary database). */
export default function BenchmarkPanel() {
  const [result, setResult] = useState<BenchmarkResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setBusy(true); setError(null);
    try { setResult(await api.benchmark()); } catch (e) { setError((e as Error).message); }
    setBusy(false);
  };

  return (
    <Panel title={<span className="flex items-center gap-2"><Gauge size={14} /> Coordination benchmark</span>}
           action={<Button onClick={run} disabled={busy}>{busy ? "Running…" : result ? "Run again" : "Run benchmark"}</Button>}>
      <p className="mb-3 text-xs text-ink-2">
        Every scenario under four coordination strategies (the lab&apos;s one-way vs two-way protocol comparison,
        plus a fixed pipeline and a no-verifier baseline). Runs in a temporary database, so nothing here is affected.
      </p>
      {error && <p className="text-xs text-critical">{error}</p>}
      {result && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-xs tabular">
            <thead>
              <tr className="border-b border-hairline text-left text-muted">
                <th className="py-1.5 pr-3 font-medium">Configuration</th>
                {COLS.map((c) => <th key={c.key} className="py-1.5 pr-3 text-right font-medium">{c.label}</th>)}
              </tr>
            </thead>
            <tbody>
              {result.summary.map((r) => (
                <tr key={r.config} className="border-b border-grid align-top">
                  <td className="py-1.5 pr-3">
                    <div className="font-mono font-semibold">{r.config}</div>
                    <div className="text-[11px] text-muted">{r.description}</div>
                  </td>
                  {COLS.map((c) => (
                    <td key={c.key} className={`py-1.5 pr-3 text-right ${
                      (c.key === "false_alerts" || c.key === "false_warnings") && Number(r[c.key]) > 0
                        ? "font-semibold text-critical" : ""}`}>
                      {String(r[c.key])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-[11px] text-muted">Vector DB: {result.vector_db}. Latency depends on this machine.</p>
        </div>
      )}
    </Panel>
  );
}
