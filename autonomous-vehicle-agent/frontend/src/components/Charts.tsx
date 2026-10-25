import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import type { Hazard } from "../types";
import { SERIES, fmtType } from "./ui";

const AXIS = { stroke: "#383835", tick: { fill: "#898781", fontSize: 11 } };
const TOOLTIP = {
  contentStyle: { background: "#232321", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, fontSize: 12 },
  labelStyle: { color: "#c3c2b7" },
  itemStyle: { color: "#f0efec" },
};

/** One series, one colour: incidents in long-term memory per hazard type. */
export function HazardTypeChart({ counts }: { counts: Record<string, number> }) {
  const data = Object.entries(counts)
    .map(([type, count]) => ({ type: fmtType(type), count }))
    .sort((a, b) => b.count - a.count);
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -20, bottom: 0 }} barCategoryGap={8}>
        <CartesianGrid vertical={false} stroke="#2c2c2a" />
        <XAxis dataKey="type" {...AXIS} interval={0} tickLine={false} />
        <YAxis {...AXIS} allowDecimals={false} tickLine={false} axisLine={false} />
        <Tooltip {...TOOLTIP} cursor={{ fill: "rgba(255,255,255,0.04)" }} formatter={(v) => [v, "Incidents"]} />
        <Bar dataKey="count" fill={SERIES[0]} radius={[4, 4, 0, 0]} maxBarSize={36} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Confidence over simulated time, one step line per hazard, with decision thresholds. */
export function ConfidenceChart({ hazards }: { hazards: Hazard[] }) {
  // Colour follows the hazard (fixed by ID order), never its rank; at most 3 series.
  const shown = [...hazards].sort((a, b) => a.id.localeCompare(b.id)).slice(-3);
  if (!shown.length) {
    return <div className="flex h-[220px] items-center justify-center text-sm text-muted">
      Run a scenario to see confidence change step by step.
    </div>;
  }
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart margin={{ top: 8, right: 16, left: -20, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="#2c2c2a" />
        <XAxis type="number" dataKey="t" {...AXIS} tickLine={false} unit="s"
               domain={[0, "dataMax"]} allowDuplicatedCategory={false} />
        <YAxis domain={[0, 1]} ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]} {...AXIS} tickLine={false} axisLine={false} />
        <Tooltip {...TOOLTIP} labelFormatter={(t) => `t = ${t}s`}
                 formatter={(v, name) => [Number(v).toFixed(2), name]} />
        <ReferenceLine y={0.6} stroke="#898781" strokeDasharray="4 4"
                       label={{ value: "verified 0.6", fill: "#898781", fontSize: 10, position: "insideTopRight" }} />
        <ReferenceLine y={0.4} stroke="#898781" strokeDasharray="4 4"
                       label={{ value: "caution 0.4", fill: "#898781", fontSize: 10, position: "insideBottomRight" }} />
        {shown.length > 1 && <Legend wrapperStyle={{ fontSize: 12, color: "#c3c2b7" }} />}
        {shown.map((h, i) => (
          <Line key={h.id} name={`${h.id} ${fmtType(h.hazard_type)}`} type="stepAfter"
                data={collapse(h)} dataKey="value" stroke={SERIES[i]} strokeWidth={2}
                dot={{ r: 4, fill: SERIES[i], stroke: "#1a1a19", strokeWidth: 2 }} isAnimationActive={false} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

// Several rule entries can share one timestamp (first report + history); keep the last value.
function collapse(h: Hazard) {
  const byT = new Map<number, number>();
  h.confidence_history.forEach((e) => byT.set(e.t, e.value));
  return [...byT.entries()].map(([t, value]) => ({ t, value }));
}
