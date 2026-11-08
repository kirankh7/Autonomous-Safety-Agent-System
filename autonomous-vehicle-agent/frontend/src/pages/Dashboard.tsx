import { Bell, Car, Database, ShieldCheck, TriangleAlert } from "lucide-react";
import type { AppState, Run } from "../types";
import { ConfidenceChart, HazardTypeChart } from "../components/Charts";
import { AlertRow, SignalStrip } from "../components/Signals";
import { AgentLegend } from "../components/TraceTimeline";
import BenchmarkPanel from "../components/BenchmarkPanel";
import { Panel, StatCard, StatusBadge, decisionStatus, fmtType } from "../components/ui";

// Routine bookkeeping signals hidden from the summary view.
const QUIET = ["NO MATCH", "PRIOR REPORTS", "SAVED", "MATCH", "RAG", "ASK HISTORY"];

export default function Dashboard({ state, runs, go }: { state: AppState; runs: Run[]; go: (page: string) => void }) {
  const { stats, hazards, alerts, simulation } = state;
  const names = Object.fromEntries(state.vehicles.map((v) => [v.id, v.name]));

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <StatCard label="Total vehicles" value={stats.total_vehicles} hint="Simulated fleet" icon={<Car size={16} />} />
        <StatCard label="Active hazards" value={stats.active_hazards} hint={`${stats.resolved_hazards} resolved`} icon={<TriangleAlert size={16} />} />
        <StatCard label="Verified hazards" value={stats.verified_hazards} hint="Reached confidence 0.6" icon={<ShieldCheck size={16} />} />
        <StatCard label="Alerts generated" value={stats.alerts_generated} hint="Simulated messages" icon={<Bell size={16} />} />
        <StatCard label="Long-term memory" value={stats.incidents_total} hint={`${stats.incidents_learned} learned from feedback`} icon={<Database size={16} />} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Hazard confidence over time (current scenario)">
          <ConfidenceChart hazards={hazards} />
        </Panel>
        <Panel title="Incidents in long-term memory by hazard type">
          <HazardTypeChart counts={state.incident_types} />
        </Panel>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Recent agent signals" className="lg:col-span-2"
               action={<button onClick={() => go("activity")} className="text-xs text-s1 hover:underline">Open timeline</button>}>
          <div className="mb-2"><AgentLegend /></div>
          {runs.length === 0 && <p className="text-sm text-muted">No agent activity yet. Start a scenario on the Hazard Simulation page.</p>}
          <ul className="divide-y divide-grid">
            {runs.slice(-6).reverse().map((r) => (
              <li key={r.run_id} className="flex items-start gap-3 py-2">
                <span className="mt-0.5 w-16 shrink-0 font-mono text-xs text-muted">{r.run_id}</span>
                <SignalStrip steps={r.steps} skip={QUIET} />
              </li>
            ))}
          </ul>
        </Panel>

        <div className="space-y-4">
          <Panel title="Current scenario"
                 action={<button onClick={() => go("simulation")} className="text-xs text-s1 hover:underline">Go to simulation</button>}>
            {simulation.scenario ? (
              <div className="space-y-1 text-sm">
                <div className="font-medium">{simulation.scenario.title}</div>
                <div className="text-ink-2">Step {simulation.index} of {simulation.total}{simulation.done ? " (complete)" : ""}</div>
              </div>
            ) : <p className="text-sm text-muted">No scenario running.</p>}
          </Panel>
          <Panel title="Hazards">
            {hazards.length === 0 && <p className="text-sm text-muted">No hazards reported.</p>}
            <ul className="space-y-2">
              {hazards.map((h) => (
                <li key={h.id} className="flex items-center justify-between gap-2 text-sm">
                  <span><span className="font-mono text-xs text-muted">{h.id}</span> {fmtType(h.hazard_type)}</span>
                  <StatusBadge info={decisionStatus(h.decision, h.status)} />
                </li>
              ))}
            </ul>
          </Panel>
          <Panel title="Latest alerts">
            {alerts.length === 0 && <p className="text-sm text-muted">No alerts sent.</p>}
            <div className="grid gap-1.5">
              {alerts.slice(-5).reverse().map((a) => <AlertRow key={a.id} alert={a} name={names[a.vehicle_id] ?? a.vehicle_id} />)}
            </div>
          </Panel>
        </div>
      </div>

      <BenchmarkPanel />
    </div>
  );
}
