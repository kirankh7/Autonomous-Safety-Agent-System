import { useState } from "react";
import type { AppState } from "../types";
import FleetMap, { type Selection } from "../components/FleetMap";
import { AlertRow } from "../components/Signals";
import {
  ConfidenceMeter, Panel, STATUS, StatusBadge, VEHICLE_COLOR, alertStatus, decisionStatus, fmtType,
} from "../components/ui";

export default function MapPage({ state }: { state: AppState }) {
  const [selected, setSelected] = useState<Selection>(null);
  const vehicle = selected?.kind === "vehicle" ? state.vehicles.find((v) => v.id === selected.id) : undefined;
  const hazard = selected?.kind === "hazard" ? state.hazards.find((h) => h.id === selected.id) : undefined;

  return (
    <div className="grid h-[calc(100vh-9rem)] gap-4 lg:grid-cols-[1fr_340px]">
      <FleetMap roads={state.roads} vehicles={state.vehicles} hazards={state.hazards}
                alerts={state.alerts} onSelect={setSelected} />
      <div className="space-y-4 overflow-y-auto">
        <Panel title="Legend">
          <ul className="space-y-1.5 text-xs text-ink-2">
            <li className="flex items-center gap-2"><Dot color={VEHICLE_COLOR} /> Vehicle (label = car name)</li>
            <li className="flex items-center gap-2"><Ring color={STATUS.critical} /> Vehicle ring = last message received</li>
            {["verified", "caution", "wait", "resolved"].map((d) => {
              const s = decisionStatus(d, d === "resolved" ? "resolved" : "active");
              return <li key={d} className="flex items-center gap-2"><Dot color={s.color} big /> <s.Icon size={12} color={s.color} /> Hazard: {s.label}</li>;
            })}
          </ul>
        </Panel>

        {!vehicle && !hazard && (
          <Panel title="Details"><p className="text-sm text-muted">Click a vehicle or hazard on the map.</p></Panel>
        )}

        {vehicle && (
          <Panel title={`${vehicle.name} · ${vehicle.model}`}>
            <dl className="grid grid-cols-2 gap-y-1 text-sm">
              <dt className="text-muted">Model</dt><dd>{vehicle.model}</dd>
              <dt className="text-muted">Road</dt><dd>{vehicle.road} ({vehicle.segment})</dd>
              <dt className="text-muted">Direction</dt><dd>{vehicle.direction_label}</dd>
              <dt className="text-muted">Position</dt><dd className="tabular">{Math.round(vehicle.position_m)} m</dd>
              <dt className="text-muted">Speed</dt><dd className="tabular">{Math.round(vehicle.speed_kmh)} km/h</dd>
              <dt className="text-muted">Sensors</dt><dd>{vehicle.sensors.join(", ")}</dd>
            </dl>
            <h3 className="mt-3 mb-1 text-xs font-semibold text-ink-2">Messages received</h3>
            <div className="grid gap-1.5">
              {state.alerts.filter((a) => a.vehicle_id === vehicle.id).map((a) => (
                <AlertRow key={a.id} alert={a} name={a.hazard_id} />
              ))}
            </div>
            {!state.alerts.some((a) => a.vehicle_id === vehicle.id) && <p className="text-xs text-muted">None</p>}
          </Panel>
        )}

        {hazard && (
          <Panel title={`${hazard.id}: ${fmtType(hazard.hazard_type)}`}
                 action={<StatusBadge info={decisionStatus(hazard.decision, hazard.status)} />}>
            <ConfidenceMeter value={hazard.confidence} decision={hazard.decision} status={hazard.status} />
            <dl className="mt-3 grid grid-cols-2 gap-y-1 text-sm">
              <dt className="text-muted">Location</dt><dd>{hazard.road} {hazard.direction_label.toLowerCase()}, {hazard.position_m} m</dd>
              <dt className="text-muted">Severity</dt><dd>{hazard.severity}</dd>
              <dt className="text-muted">Weather</dt><dd>{hazard.weather.replace("_", " ")}, {hazard.visibility_m} m</dd>
              <dt className="text-muted">Reports</dt><dd>{hazard.report_ids.join(", ")}</dd>
              <dt className="text-muted">Confirmed by</dt><dd>{hazard.confirming_vehicles.join(", ")}</dd>
              <dt className="text-muted">Clear reports</dt><dd>{hazard.clear_vehicles.join(", ") || "None"}</dd>
            </dl>
            <h3 className="mt-3 mb-1 text-xs font-semibold text-ink-2">Confidence history</h3>
            <ul className="space-y-1 text-xs text-ink-2">
              {hazard.confidence_history.map((e, i) => (
                <li key={i} className="tabular">{e.delta >= 0 ? "+" : ""}{e.delta.toFixed(2)} &rarr; {e.value.toFixed(2)}: {e.reason}</li>
              ))}
            </ul>
            <h3 className="mt-3 mb-1 text-xs font-semibold text-ink-2">Alert status</h3>
            <ul className="space-y-1 text-xs">
              {state.alerts.filter((a) => a.hazard_id === hazard.id).map((a) => (
                <li key={a.id} className="flex items-center gap-2"><StatusBadge info={alertStatus(a.level)} /> {state.vehicles.find((v) => v.id === a.vehicle_id)?.name ?? a.vehicle_id}</li>
              ))}
            </ul>
            {hazard.resolution && <p className="mt-2 text-xs text-ink-2">Resolution: {hazard.resolution}</p>}
          </Panel>
        )}
      </div>
    </div>
  );
}

const Dot = ({ color, big }: { color: string; big?: boolean }) => (
  <span className={`inline-block rounded-full ${big ? "h-3.5 w-3.5" : "h-3 w-3"}`} style={{ background: color }} />
);
const Ring = ({ color }: { color: string }) => (
  <span className="inline-block h-3 w-3 rounded-full border-[3px]" style={{ borderColor: color, background: VEHICLE_COLOR }} />
);
