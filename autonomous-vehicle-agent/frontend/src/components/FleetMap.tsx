import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import type { LatLngBoundsExpression } from "leaflet";
import type { Alert, Hazard, Road, Vehicle } from "../types";
import { VEHICLE_COLOR, alertStatus, decisionStatus, fmtType } from "./ui";

export type Selection = { kind: "vehicle"; id: string } | { kind: "hazard"; id: string } | null;

interface Props {
  roads: Road[];
  vehicles: Vehicle[];
  hazards: Hazard[];
  alerts: Alert[];
  onSelect?: (s: Selection) => void;
  height?: string;
  showResolved?: boolean;
}

const SURFACE = "#1a1a19";

// Fit the view to the road network (falls back to central Dublin, CA before data loads).
function bounds(roads: Road[]): LatLngBoundsExpression {
  const pts = roads.flatMap((r) => r.points);
  if (!pts.length) return [[37.68, -121.97], [37.75, -121.86]];
  const lats = pts.map((p) => p[0]), lngs = pts.map((p) => p[1]);
  return [[Math.min(...lats), Math.min(...lngs)], [Math.max(...lats), Math.max(...lngs)]];
}

export default function FleetMap({ roads, vehicles, hazards, alerts, onSelect, height = "100%", showResolved = true }: Props) {
  // The latest alert per vehicle decides its ring colour.
  const latestAlert = new Map<string, Alert>();
  alerts.forEach((a) => latestAlert.set(a.vehicle_id, a));
  const shownHazards = hazards.filter((h) => showResolved || h.status === "active");

  return (
    <div style={{ height }} className="overflow-hidden rounded-lg border border-hairline">
      <MapContainer bounds={bounds(roads)} boundsOptions={{ padding: [24, 24] }}
                    style={{ height: "100%", width: "100%" }} scrollWheelZoom>
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          className="dark-tiles"
        />
        {roads.map((r) => (
          <Polyline key={r.id} positions={r.points} pathOptions={{ color: "#8a8983", weight: 5, opacity: 0.55 }}>
            <Tooltip permanent direction="center" className="road-label">{r.name}</Tooltip>
          </Polyline>
        ))}

        {shownHazards.map((h) => {
          const st = decisionStatus(h.decision, h.status);
          return (
            <CircleMarker key={h.id} center={[h.lat, h.lng]} radius={13}
                          pathOptions={{ color: SURFACE, weight: 2, fillColor: st.color, fillOpacity: 0.9 }}
                          eventHandlers={{ click: () => onSelect?.({ kind: "hazard", id: h.id }) }}>
              <Tooltip direction="top" offset={[0, -12]}>{h.id}: {fmtType(h.hazard_type)} ({st.label})</Tooltip>
              <Popup>
                <div className="space-y-1 text-xs">
                  <div className="font-semibold">{h.id}: {fmtType(h.hazard_type)}</div>
                  <div>{h.road} {h.direction_label.toLowerCase()}</div>
                  <div>Status: {st.label} - confidence {h.confidence.toFixed(2)}</div>
                  <div>Severity: {h.severity}; reports: {h.report_ids.join(", ")}</div>
                  <div>Alerts: {alerts.filter((a) => a.hazard_id === h.id).length}</div>
                </div>
              </Popup>
            </CircleMarker>
          );
        })}

        {vehicles.map((v) => {
          const alert = latestAlert.get(v.id);
          const ring = alert ? alertStatus(alert.level).color : SURFACE;
          return (
            <CircleMarker key={v.id} center={[v.lat, v.lng]} radius={7}
                          pathOptions={{ color: ring, weight: alert ? 3 : 2, fillColor: VEHICLE_COLOR, fillOpacity: 1 }}
                          eventHandlers={{ click: () => onSelect?.({ kind: "vehicle", id: v.id }) }}>
              <Tooltip permanent direction="right" offset={[8, 0]} className="vehicle-label">
                {v.name.replace("Vehicle ", "")}
              </Tooltip>
              <Popup>
                <div className="space-y-1 text-xs">
                  <div className="font-semibold">{v.name} ({v.id})</div>
                  <div>{v.model} - {v.road} {v.direction_label.toLowerCase()}</div>
                  <div>{Math.round(v.speed_kmh)} km/h - sensors: {v.sensors.join(", ")}</div>
                  {alert && <div>Last message: {alertStatus(alert.level).label} ({alert.id})</div>}
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
}
