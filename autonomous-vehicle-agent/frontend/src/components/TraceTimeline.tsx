import { useState } from "react";
import { ChevronRight, Wrench } from "lucide-react";
import type { TraceStep } from "../types";
import { SignalChip } from "./Signals";
import { AGENT_COLORS, AGENT_NUMBER } from "./ui";

export { AGENT_COLORS };

// The workflow stages in the order the LangGraph runs them.
export const STAGES = [
  { key: "observation", label: "Observation Received" },
  { key: "check_existing", label: "Check Existing Hazards" },
  { key: "retrieve", label: "Retrieve Historical Context" },
  { key: "verify", label: "Verify Hazard" },
  { key: "identify_vehicles", label: "Identify Approaching Vehicles" },
  { key: "alert", label: "Generate Alert" },
  { key: "memory", label: "Update Memory" },
];


/** Proper agent name with its number and identity colour, e.g. "2 · Verification Agent". */
export function AgentTag({ agent }: { agent: string }) {
  return (
    <span className="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap text-xs font-medium text-ink">
      <span className="flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-bold text-white"
            style={{ background: AGENT_COLORS[agent] ?? "#898781" }}>
        {AGENT_NUMBER[agent] ?? "?"}
      </span>
      {agent}
    </span>
  );
}

/** Colour key for the agent dots used in signal strips. */
export function AgentLegend() {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1">
      {Object.keys(AGENT_NUMBER).map((name) => <AgentTag key={name} agent={name} />)}
    </div>
  );
}

export function Pipeline({ steps, selected, onSelect }: {
  steps: TraceStep[]; selected?: string | null; onSelect?: (stage: string | null) => void;
}) {
  const ran = new Set(steps.map((s) => s.stage));
  return (
    <div className="flex flex-wrap items-center gap-1">
      {STAGES.map((stage, i) => {
        const active = ran.has(stage.key);
        const isSel = selected === stage.key;
        return (
          <div key={stage.key} className="flex items-center gap-1">
            <button
              disabled={!active}
              onClick={() => onSelect?.(isSel ? null : stage.key)}
              className={`rounded-lg border px-2.5 py-1.5 text-xs transition ${
                isSel ? "border-s1 bg-s1/20 text-ink"
                  : active ? "border-hairline bg-surface-2 text-ink hover:border-s1"
                  : "border-dashed border-hairline text-muted"}`}
              title={active ? "Show this stage" : "Skipped in this run"}>
              <span className="mr-1 text-muted">{i + 1}</span>{stage.label}
            </button>
            {i < STAGES.length - 1 && <ChevronRight size={14} className="text-muted" />}
          </div>
        );
      })}
    </div>
  );
}

export default function TraceTimeline({ steps, stageFilter, expandAll = false }: {
  steps: TraceStep[]; stageFilter?: string | null; expandAll?: boolean;
}) {
  const [open, setOpen] = useState<number | null>(null);
  const shown = stageFilter ? steps.filter((s) => s.stage === stageFilter) : steps;
  const label = (key: string) => STAGES.find((s) => s.key === key)?.label ?? key;

  return (
    <ol className="relative space-y-1.5 border-l border-axis pl-4">
      {shown.map((s) => {
        const expanded = expandAll || open === s.step;
        return (
          <li key={`${s.run_id}-${s.step}`} className="relative">
            <span className="absolute -left-[21px] top-3 h-2.5 w-2.5 rounded-full border-2 border-surface"
                  style={{ background: AGENT_COLORS[s.agent] ?? "#898781" }} />
            <button onClick={() => setOpen(open === s.step ? null : s.step)}
                    className="w-full rounded-lg border border-hairline bg-surface-2 px-3 py-2 text-left hover:border-axis">
              <div className="flex items-center gap-3">
                <span className="w-4 shrink-0 text-xs text-muted tabular">{s.step}</span>
                <span className="w-32 shrink-0 text-[11px] font-semibold uppercase leading-tight tracking-wide text-ink-2">{label(s.stage)}</span>
                <span className="flex min-w-0 flex-1 overflow-hidden">
                  {s.signal ? <SignalChip signal={s.signal} /> : <span className="truncate text-xs text-ink-2">{s.result}</span>}
                </span>
                <span className="w-48 shrink-0"><AgentTag agent={s.agent} /></span>
              </div>
              {expanded && (
                <div className="mt-2 grid gap-1.5 border-t border-hairline pt-2 text-sm">
                  <Row label="Reason" text={s.thought} />
                  <Row label="Action" text={s.action} />
                  <div className="flex gap-2">
                    <span className="w-16 shrink-0 text-xs text-muted">Tool</span>
                    <code className="inline-flex items-center gap-1 text-xs text-s1">
                      <Wrench size={12} />{s.tool}
                    </code>
                  </div>
                  <Row label="Result" text={s.result} strong />
                </div>
              )}
            </button>
          </li>
        );
      })}
    </ol>
  );
}

function Row({ label, text, strong }: { label: string; text: string; strong?: boolean }) {
  return (
    <div className="flex gap-2">
      <span className="w-16 shrink-0 text-xs text-muted">{label}</span>
      <span className={`text-xs leading-relaxed ${strong ? "text-ink" : "text-ink-2"}`}>{text}</span>
    </div>
  );
}
