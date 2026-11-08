import { ChevronRight } from "lucide-react";
import type { Alert, Signal, TraceStep } from "../types";
import { AGENT_COLORS, AGENT_NUMBER, OPERATOR_ID, STATUS, StatusBadge, alertStatus } from "./ui";

// Tone -> colour. Status tones carry meaning; "info" uses the vehicle/series blue.
const TONE: Record<string, string> = {
  critical: STATUS.critical, serious: STATUS.serious, warning: STATUS.warning, good: STATUS.good,
  info: "#3987e5", neutral: "#898781",
};

export function SignalChip({ signal, big }: { signal: Signal; big?: boolean }) {
  const color = TONE[signal.tone] ?? TONE.neutral;
  return (
    <span className={`inline-flex max-w-full items-center gap-1.5 whitespace-nowrap rounded-md border font-mono ${big ? "px-2.5 py-1 text-sm" : "px-2 py-0.5 text-[11px]"}`}
          style={{ borderColor: `${color}99`, background: `${color}1f` }}
          title={`${signal.label} ${signal.detail}`.trim()}>
      <span className="shrink-0 font-semibold tracking-wide" style={{ color: signal.tone === "neutral" ? "#c3c2b7" : color }}>
        {signal.label}
      </span>
      {signal.detail && <span className="min-w-0 truncate text-ink-2">{signal.detail}</span>}
    </span>
  );
}

/** One run as a left-to-right strip of agent signals, in workflow order. */
export function SignalStrip({ steps, skip = [] }: { steps: TraceStep[]; skip?: string[] }) {
  const shown = steps.filter((s) => s.signal && !skip.includes(s.signal.label));
  return (
    <div className="flex flex-wrap items-center gap-1">
      {shown.map((s, i) => (
        <span key={`${s.run_id}-${s.step}`} className="inline-flex items-center gap-1">
          <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full text-[9px] font-bold text-white"
                title={s.agent} style={{ background: AGENT_COLORS[s.agent] }}>{AGENT_NUMBER[s.agent]}</span>
          <SignalChip signal={s.signal!} />
          {i < shown.length - 1 && <ChevronRight size={12} className="text-axis" />}
        </span>
      ))}
    </div>
  );
}

/** A compact alert line: level, receiving vehicle, distance and ETA. */
export function AlertRow({ alert, name }: { alert: Alert; name: string }) {
  return (
    <div className="flex items-center justify-between gap-2 rounded-lg border border-hairline bg-surface-2 px-2 py-1.5 text-xs"
         title={alert.message}>
      <div className="flex items-center gap-2">
        <StatusBadge info={alertStatus(alert.level)} />
        <span className="font-semibold text-ink">{alert.vehicle_id === OPERATOR_ID ? "Fleet operator" : name}</span>
      </div>
      <span className="tabular text-ink-2">
        {alert.distance_m ? `${(alert.distance_m / 1000).toFixed(1)} km · ${alert.eta_s} s` : alert.id}
      </span>
    </div>
  );
}
