import { Bell, Car, Database, ShieldCheck, TriangleAlert } from "lucide-react";
import type { AppState, Run } from "../types";
import { ConfidenceChart, HazardTypeChart } from "../components/Charts";
import { AgentTag, STAGES } from "../components/TraceTimeline";
import { Panel, StatCard, StatusBadge, alertStatus, decisionStatus, fmtType } from "../components/ui";

export default function Dashboard({ state, runs, go }: { state: AppState; runs: Run[]; go: (page: string) => void }) {
  const { stats, hazards, alerts, simulation } = state;
  const recent = runs.flatMap((r) => r.steps).slice(-8).reverse();
  const stageLabel = (k: string) => STAGES.find((s) => s.key === k)?.label ?? k;

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
        <Panel title="Recent agent activity" className="lg:col-span-2"
               action={<button onClick={() => go("activity")} className="text-xs text-s1 hover:underline">Open timeline</button>}>
          {recent.length === 0 && <p className="text-sm text-muted">No agent activity yet. Start a scenario on the Hazard Simulation page.</p>}
          <ul className="divide-y divide-grid">
            {recent.map((s) => (
              <li key={`${s.run_id}-${s.step}`} className="flex flex-col gap-1 py-2">
                <div className="flex items-center gap-3 text-xs">
                  <span className="font-mono text-muted">{s.run_id}</span>
                  <AgentTag agent={s.agent} />
                  <span className="text-ink-2">{stageLabel(s.stage)}</span>
                </div>
                <div className="truncate text-sm text-ink-2">{s.result}</div>
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
            <ul className="space-y-2">
              {alerts.slice(-4).reverse().map((a) => (
                <li key={a.id} className="space-y-1 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-muted">{a.id} to {a.vehicle_id}</span>
                    <StatusBadge info={alertStatus(a.level)} />
                  </div>
                  <div className="text-ink-2">{a.message}</div>
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      </div>
    </div>
  );
}
