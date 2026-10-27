import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, CircleDashed, Eye, Info } from "lucide-react";

// Status colours carry meaning (danger level) and are always shown with an icon + label.
export const STATUS = {
  critical: "#d03b3b",
  warning: "#fab219",
  serious: "#ec835a",
  good: "#0ca30c",
  muted: "#898781",
};
export const SERIES = ["#3987e5", "#d95926", "#199e70"]; // categorical slots 1-3
export const VEHICLE_COLOR = "#3987e5";

// Agent identity colours (categorical slots); the agent name is always shown next to the dot.
export const AGENT_COLORS: Record<string, string> = {
  "Hazard Analysis Agent": "#3987e5",
  "Research & Memory Agent": "#d95926",
  "Verification Agent": "#199e70",
  "Alert Agent": "#9085e9",
};

type StatusInfo = { color: string; label: string; Icon: typeof Info };

export function decisionStatus(decision?: string | null, status?: string): StatusInfo {
  if (status === "resolved" || decision === "resolved")
    return { color: STATUS.good, label: "Resolved", Icon: CheckCircle2 };
  if (status === "expired") return { color: STATUS.muted, label: "Expired", Icon: CircleDashed };
  switch (decision) {
    case "verified":
      return { color: STATUS.critical, label: "Verified alert", Icon: AlertTriangle };
    case "caution":
      return { color: STATUS.warning, label: "Caution advisory", Icon: Info };
    case "wait":
      return { color: STATUS.serious, label: "Awaiting evidence", Icon: Eye };
    default:
      return { color: STATUS.muted, label: decision ?? "Pending", Icon: CircleDashed };
  }
}

export function alertStatus(level: string): StatusInfo {
  return {
    verified: { color: STATUS.critical, label: "Safety alert", Icon: AlertTriangle },
    caution: { color: STATUS.warning, label: "Caution", Icon: Info },
    observation_request: { color: STATUS.serious, label: "Observation request", Icon: Eye },
    all_clear: { color: STATUS.good, label: "All clear", Icon: CheckCircle2 },
  }[level] ?? { color: STATUS.muted, label: level, Icon: Info };
}

export const fmtType = (t: string) => t.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

export function Panel({ title, action, children, className = "" }: {
  title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`rounded-xl border border-hairline bg-surface p-4 ${className}`}>
      {(title || action) && (
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-ink">{title}</h2>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function StatCard({ label, value, hint, icon }: {
  label: string; value: ReactNode; hint?: string; icon?: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-hairline bg-surface p-4">
      <div className="flex items-center justify-between text-xs text-ink-2">
        {label}
        <span className="text-muted">{icon}</span>
      </div>
      <div className="mt-2 text-3xl font-semibold text-ink">{value}</div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </div>
  );
}

export function StatusBadge({ info }: { info: StatusInfo }) {
  const { color, label, Icon } = info;
  return (
    <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium text-ink"
          style={{ borderColor: color, background: `${color}22` }}>
      <Icon size={12} color={color} />
      {label}
    </span>
  );
}

export function Button({ children, onClick, variant = "primary", disabled, title }: {
  children: ReactNode; onClick?: () => void; variant?: "primary" | "secondary" | "ghost";
  disabled?: boolean; title?: string;
}) {
  const styles = {
    primary: "bg-s1 text-white hover:brightness-110",
    secondary: "border border-hairline bg-surface-2 text-ink hover:bg-axis",
    ghost: "text-ink-2 hover:bg-surface-2",
  }[variant];
  return (
    <button onClick={onClick} disabled={disabled} title={title}
            className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${styles}`}>
      {children}
    </button>
  );
}

/** Horizontal confidence meter with the 0.4 (caution) and 0.6 (verified) thresholds marked. */
export function ConfidenceMeter({ value, decision, status }: { value: number; decision: string; status: string }) {
  const { color } = decisionStatus(decision, status);
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-xs text-ink-2">Confidence</span>
        <span className="text-lg font-semibold tabular">{value.toFixed(2)}</span>
      </div>
      <div className="relative mt-1 h-2 rounded-full bg-surface-2">
        <div className="h-2 rounded-full transition-all" style={{ width: `${value * 100}%`, background: color }} />
        {[0.4, 0.6].map((m) => (
          <div key={m} className="absolute -top-1 h-4 w-px bg-ink-2" style={{ left: `${m * 100}%` }} />
        ))}
      </div>
      <div className="relative mt-1 h-3 text-[10px] text-muted">
        <span className="absolute -translate-x-1/2" style={{ left: "40%" }}>0.4 caution</span>
        <span className="absolute -translate-x-1/2" style={{ left: "60%" }}>0.6 verified</span>
      </div>
    </div>
  );
}
