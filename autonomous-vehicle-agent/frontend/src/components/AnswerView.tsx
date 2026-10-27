import { useState } from "react";
import { Database, FileText, Bell, TriangleAlert, Wrench } from "lucide-react";
import type { Evidence, ResearchAnswer } from "../types";

const KIND_ICON: Record<string, typeof FileText> = {
  incident: Database, report: FileText, alert: Bell, hazard: TriangleAlert,
};

/** Renders a Research Assistant answer with clickable [ID] citations and the evidence list. */
export default function AnswerView({ answer }: { answer: ResearchAnswer }) {
  const [focus, setFocus] = useState<string | null>(null);
  const byId = new Map(answer.evidence.map((e) => [e.id, e]));

  return (
    <div className="space-y-3">
      <div className="space-y-1 text-sm leading-relaxed text-ink">
        {answer.answer.split("\n").map((line, i) => (
          <p key={i} className={line.startsWith("- ") ? "pl-3 text-ink-2" : ""}>
            {line.split(/\b((?:HZ|RPT|ALT|INC)-\d{3})\b/g).map((part, j) => {
              const id = /^(?:HZ|RPT|ALT|INC)-\d{3}$/.test(part) ? part : undefined;
              if (!id) return <span key={j}>{part}</span>;
              return (
                <button key={j} onClick={() => setFocus(focus === id ? null : id)}
                        className={`mx-0.5 rounded px-1 font-mono text-xs ${
                          focus === id ? "bg-s1 text-white" : "bg-s1/20 text-s1 hover:bg-s1/30"}`}>
                  {id}
                </button>
              );
            })}
          </p>
        ))}
      </div>
      {focus && byId.get(focus) && <EvidenceCard e={byId.get(focus)!} highlight />}

      {answer.unverified_citations && answer.unverified_citations.length > 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-warning/60 bg-warning/10 p-2 text-xs">
          <TriangleAlert size={14} color="#fab219" />
          Citation check: {answer.unverified_citations.join(", ")} did not appear in any tool result.
        </div>
      )}

      {answer.agent_steps && answer.agent_steps.length > 0 && (
        <details open className="rounded-lg border border-hairline bg-page/50 p-2">
          <summary className="cursor-pointer text-xs font-medium text-ink-2">
            Claude's tool calls ({answer.agent_steps.length}): reason, act, observe
          </summary>
          <ol className="mt-2 space-y-1.5">
            {answer.agent_steps.map((s, i) => (
              <li key={i} className="text-xs">
                {s.reason && <div className="text-ink-2">{s.reason}</div>}
                <code className="text-s1">{i + 1}. {s.tool}({Object.entries(s.input).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")})</code>
                <span className="text-muted"> &rarr; {s.result}</span>
              </li>
            ))}
          </ol>
        </details>
      )}

      <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
        <span className="rounded bg-page px-2 py-0.5">answer mode: {answer.mode}</span>
        <span className="rounded bg-page px-2 py-0.5">intent: {answer.intent}</span>
        {answer.tools_used.map((t) => (
          <span key={t} className="inline-flex items-center gap-1 rounded bg-page px-2 py-0.5">
            <Wrench size={11} />{t}
          </span>
        ))}
      </div>

      {answer.evidence.length > 0 && (
        <details className="rounded-lg border border-hairline bg-page/50 p-2">
          <summary className="cursor-pointer text-xs font-medium text-ink-2">
            Evidence used ({answer.evidence.length} records)
          </summary>
          <div className="mt-2 grid gap-2">
            {answer.evidence.map((e) => <EvidenceCard key={e.id} e={e} />)}
          </div>
        </details>
      )}
    </div>
  );
}

function EvidenceCard({ e, highlight }: { e: Evidence; highlight?: boolean }) {
  const Icon = KIND_ICON[e.kind] ?? FileText;
  return (
    <div className={`flex gap-2 rounded-lg border p-2 text-xs ${highlight ? "border-s1 bg-s1/10" : "border-hairline bg-surface-2"}`}>
      <Icon size={14} className="mt-0.5 shrink-0 text-ink-2" />
      <div>
        <span className="font-mono font-semibold text-ink">{e.id}</span>
        <span className="ml-2 uppercase tracking-wide text-muted">{e.kind}</span>
        <div className="mt-0.5 text-ink-2">{e.summary}</div>
      </div>
    </div>
  );
}
