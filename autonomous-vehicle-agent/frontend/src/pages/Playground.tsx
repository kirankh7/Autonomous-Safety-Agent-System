import { useEffect, useMemo, useState } from "react";
import { Dices, MoveRight, RotateCcw, Send } from "lucide-react";
import type { AppState, PlaygroundOptions, PlaygroundReport, RunResult } from "../types";
import { api } from "../api";
import FleetMap from "../components/FleetMap";
import MessageLog from "../components/MessageLog";
import TraceTimeline, { AgentLegend } from "../components/TraceTimeline";
import { AlertRow, SignalStrip } from "../components/Signals";
import { Button, Panel, StatusBadge, decisionStatus, fmtType, recipientName } from "../components/ui";

interface Props {
  state: AppState;
  run: (action: () => Promise<unknown>) => Promise<void>;
  busy: boolean;
}

const field = "w-full rounded-lg border border-hairline bg-surface-2 px-2 py-1.5 text-sm text-ink";
const label = "mb-1 block text-[11px] uppercase tracking-wide text-muted";

/** Free play: send your own reports, move vehicles, or generate random dummy traffic. */
export default function Playground({ state, run, busy }: Props) {
  const names = useMemo(() => Object.fromEntries(state.vehicles.map((v) => [v.id, v.name])), [state.vehicles]);
  const [options, setOptions] = useState<PlaygroundOptions | null>(null);
  const [results, setResults] = useState<RunResult[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [seed, setSeed] = useState("");
  const [report, setReport] = useState<PlaygroundReport>({
    vehicle_id: "CAR-001", hazard: "stopped_truck", distance: 400, weather: "fog", visibility: 150, description: "",
  });
  const vehicle = state.vehicles.find((v) => v.id === report.vehicle_id);
  const [move, setMove] = useState({ segment: "ROAD-01", direction: "forward", position_m: 1000 });

  useEffect(() => { api.playgroundOptions().then(setOptions).catch(() => {}); }, []);
  useEffect(() => {   // the move form starts from where the chosen vehicle is now
    if (vehicle) setMove({ segment: vehicle.segment, direction: vehicle.direction, position_m: Math.round(vehicle.position_m) });
  }, [vehicle?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const add = (items: RunResult[]) => {
    setResults((r) => [...items.slice().reverse(), ...r].slice(0, 60));
    if (items.length) setSelected(items[items.length - 1].run_id);
  };
  const current = results.find((r) => r.run_id === selected) ?? results[0];
  const road = options?.roads.find((r) => r.id === move.segment);

  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-[380px_1fr]">
        <div className="space-y-4">
          <Panel title={<span className="flex items-center gap-2"><Dices size={14} /> Generate dummy traffic</span>}>
            <p className="mb-3 text-xs text-ink-2">
              Random vehicles report random hazards in random weather. Others confirm them or report the road
              clear, so you see verification, alerts, escalations and learning. All data is synthetic.
            </p>
            <div className="flex flex-wrap items-end gap-2">
              {[1, 5, 20].map((n) => (
                <Button key={n} disabled={busy}
                        onClick={() => run(async () => add(await api.randomReports(n, seed ? Number(seed) : undefined)))}>
                  {n === 1 ? "1 random report" : `${n} reports`}
                </Button>
              ))}
              <div className="w-24">
                <span className={label}>Seed</span>
                <input className={field} inputMode="numeric" placeholder="random" value={seed}
                       onChange={(e) => setSeed(e.target.value.replace(/\D/g, ""))} />
              </div>
            </div>
            <div className="mt-3">
              <Button variant="secondary" disabled={busy}
                      onClick={() => confirm("Clear all hazards, alerts and traces and put vehicles back?")
                        && run(async () => { await api.resetPlayground(); setResults([]); setSelected(null); })}>
                <RotateCcw size={14} className="mr-1 inline" /> Reset playground
              </Button>
            </div>
          </Panel>

          <Panel title={<span className="flex items-center gap-2"><Send size={14} /> Send your own report</span>}>
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <span className={label}>Reporting vehicle</span>
                <select className={field} value={report.vehicle_id}
                        onChange={(e) => setReport({ ...report, vehicle_id: e.target.value })}>
                  {state.vehicles.map((v) => <option key={v.id} value={v.id}>{v.name} ({v.id})</option>)}
                </select>
                {vehicle && (
                  <p className="mt-1 text-[11px] text-muted">
                    Now on {vehicle.road} {vehicle.direction_label.toLowerCase()} at {Math.round(vehicle.position_m)} m,
                    {" "}{vehicle.speed_kmh} km/h · sensors: {vehicle.sensors.join(", ")}
                  </p>
                )}
              </div>

              <details className="col-span-2 rounded-lg border border-hairline p-2">
                <summary className="cursor-pointer text-xs text-ink-2">Move this vehicle first (optional)</summary>
                <div className="mt-2 grid grid-cols-3 gap-2">
                  <select className={field} value={move.segment} aria-label="Road"
                          onChange={(e) => setMove({ ...move, segment: e.target.value })}>
                    {options?.roads.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                  </select>
                  <select className={field} value={move.direction} aria-label="Direction"
                          onChange={(e) => setMove({ ...move, direction: e.target.value })}>
                    <option value="forward">{road?.forward_label ?? "forward"}</option>
                    <option value="reverse">{road?.reverse_label ?? "reverse"}</option>
                  </select>
                  <input className={field} type="number" min={0} max={road?.length_m} step={50} aria-label="Position (m)"
                         value={move.position_m} onChange={(e) => setMove({ ...move, position_m: Number(e.target.value) })} />
                </div>
                <div className="mt-2 flex items-center justify-between">
                  <span className="text-[11px] text-muted">Position in metres (road length {road?.length_m ?? "?"} m)</span>
                  <Button variant="secondary" disabled={busy}
                          onClick={() => run(() => api.moveVehicle(report.vehicle_id, move))}>
                    <MoveRight size={14} className="mr-1 inline" /> Move
                  </Button>
                </div>
              </details>

              <div>
                <span className={label}>Hazard</span>
                <select className={field} value={report.hazard} onChange={(e) => setReport({ ...report, hazard: e.target.value })}>
                  {options?.hazard_types.map((h) => <option key={h} value={h}>{fmtType(h)}</option>)}
                </select>
              </div>
              <div>
                <span className={label}>Distance ahead (m)</span>
                <input className={field} type="number" min={10} max={3000} step={10} value={report.distance}
                       onChange={(e) => setReport({ ...report, distance: Number(e.target.value) })} />
              </div>
              <div>
                <span className={label}>Weather</span>
                <select className={field} value={report.weather}
                        onChange={(e) => {
                          const w = options?.weather.find((x) => x.id === e.target.value);
                          setReport({ ...report, weather: e.target.value, visibility: w?.visibility_m ?? report.visibility });
                        }}>
                  {options?.weather.map((w) => <option key={w.id} value={w.id}>{fmtType(w.id)}</option>)}
                </select>
              </div>
              <div>
                <span className={label}>Visibility (m)</span>
                <input className={field} type="number" min={10} step={10} value={report.visibility}
                       onChange={(e) => setReport({ ...report, visibility: Number(e.target.value) })} />
              </div>
              <div className="col-span-2">
                <span className={label}>Description (optional)</span>
                <input className={field} value={report.description} placeholder="e.g. Ladder in the right lane"
                       onChange={(e) => setReport({ ...report, description: e.target.value })} />
              </div>
            </div>
            <div className="mt-3 flex items-center justify-between gap-2">
              <span className="text-[11px] text-muted">Arrives 30 s after the previous report (simulated clock).</span>
              <Button disabled={busy}
                      onClick={() => run(async () => add([await api.sendReport(report)]))}>
                <Send size={14} className="mr-1 inline" /> Send report
              </Button>
            </div>
          </Panel>
        </div>

        <div className="space-y-4">
          <FleetMap roads={state.roads} vehicles={state.vehicles} hazards={state.hazards} alerts={state.alerts} height="360px" />
          <Panel title={`Results (${results.length})`}>
            {!results.length && <p className="text-sm text-muted">Nothing yet. Generate traffic or send a report.</p>}
            <ul className="max-h-64 space-y-1 overflow-y-auto">
              {results.map((r) => (
                <li key={r.run_id}>
                  <button onClick={() => setSelected(r.run_id)}
                          className={`flex w-full flex-wrap items-center justify-between gap-2 rounded-lg border px-2 py-1.5 text-left text-xs ${
                            r.run_id === current?.run_id ? "border-s1 bg-s1/10" : "border-hairline hover:border-axis"}`}>
                    <span className="min-w-0 flex-1">
                      <span className="mr-2 font-mono text-muted">{r.run_id}</span>
                      {r.narration ?? `${names[r.report?.vehicle_id ?? ""] ?? "Custom report"}: ${fmtType(r.hazard?.hazard_type ?? "report")}`}
                    </span>
                    <span className="flex items-center gap-2">
                      {r.hazard && <span className="font-mono">{r.hazard.id} · {r.hazard.confidence.toFixed(2)}</span>}
                      {r.decision ? <StatusBadge info={decisionStatus(r.decision, r.hazard?.status)} />
                        : <span className="text-muted">recorded only</span>}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      </div>

      {current && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel title={`What the agents did · ${current.run_id}`}>
            <div className="mb-2"><AgentLegend /></div>
            <SignalStrip steps={current.trace} />
            <div className="mt-4 text-[11px] uppercase tracking-wide text-muted">Alerts sent</div>
            <div className="mt-1 grid gap-1.5">
              {current.alerts.length
                ? current.alerts.map((a) => <AlertRow key={a.id} alert={a} name={recipientName(a.vehicle_id, names)} />)
                : <span className="text-xs text-muted">None</span>}
            </div>
            <div className="mt-4 text-[11px] uppercase tracking-wide text-muted">Agent messages</div>
            <div className="mt-1"><MessageLog messages={current.messages} /></div>
          </Panel>
          <Panel title="ReAct trace" action={<span className="text-xs text-muted">click a step for reasoning</span>}>
            <TraceTimeline steps={current.trace} />
          </Panel>
        </div>
      )}
    </div>
  );
}
