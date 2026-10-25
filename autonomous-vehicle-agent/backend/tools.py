"""Agent tools: plain Python functions the agents call, plus the simple road geometry they use.

The confidence rules here are demonstration rules for a capstone, not automotive safety standards.
"""
import math

from backend import memory
from backend.database import load_json
from backend.rag import index as rag_index

# ---------- Confidence rule set (Checkpoint 3.1) ----------
FIRST_REPORT = 0.5
CONFIRMATION = 0.2
ROAD_CLEAR = -0.3
HISTORY_PER_INCIDENT = 0.05
HISTORY_CAP = 0.15
VERIFIED_AT = 0.6
CAUTION_AT = 0.4
RESOLVE_BELOW = 0.2
CLEAR_REPORTS_TO_RESOLVE = 2
MATCH_RADIUS_M = 50          # reports within 50 m along the road are the same hazard
CONFIRM_WINDOW_S = 120       # a confirmation must arrive within 2 minutes of the last report
ALERT_RANGE_M = 3000         # vehicles up to 3 km behind the hazard are "approaching"
LOW_VISIBILITY_M = 200
COLD_START_INCIDENTS = 3     # segments with fewer resolved incidents use RAG for history

# Severity and recommended action per hazard type (loosely based on public FHWA traffic
# incident management and NWS "Turn Around Don't Drown" guidance; demonstration only).
HAZARD_TABLE = {
    "stopped_truck":   ("high",   "Reduce speed early and prepare to change lanes."),
    "accident":        ("high",   "Slow down and expect lane closures and emergency vehicles."),
    "flooding":        ("high",   "Reroute. Do not drive into standing water."),
    "debris":          ("medium", "Reduce speed and avoid the affected lane."),
    "stopped_vehicle": ("medium", "Slow down and move over if possible."),
    "pothole":         ("low",    "Reduce speed over the affected lane."),
}
SEVERITY_LEVELS = ["low", "medium", "high", "critical"]

# Words a report might use for each hazard type (a tiny rule-based "understanding" step).
SYNONYMS = {
    "stopped_truck": ["stopped truck", "stalled truck", "big rig", "stopped_truck", "truck"],
    "accident": ["accident", "collision", "crash"],
    "flooding": ["flood", "standing water", "water across"],
    "debris": ["debris", "object in lane", "mattress", "ladder", "tire"],
    "stopped_vehicle": ["stopped vehicle", "stalled car", "disabled vehicle", "stopped_vehicle"],
    "pothole": ["pothole"],
    "road_clear": ["road_clear", "road clear", "all clear", "no hazard", "lane clear"],
}


def classify_hazard(hazard: str, description: str = "") -> str:
    """Normalise the reported hazard into one of the known hazard types."""
    text = f"{hazard} {description}".lower().replace("-", " ")
    if hazard in SYNONYMS:
        return hazard
    for hazard_type, words in SYNONYMS.items():
        if any(w in text for w in words):
            return hazard_type
    return "debris"


def severity_for(hazard_type: str, visibility_m: float) -> tuple[str, str]:
    """Look up severity and action; low visibility raises severity one level."""
    severity, action = HAZARD_TABLE.get(hazard_type, ("medium", "Proceed with caution."))
    if visibility_m < LOW_VISIBILITY_M:
        severity = SEVERITY_LEVELS[min(SEVERITY_LEVELS.index(severity) + 1, 3)]
    return severity, action


# ---------- Simple road geometry ----------
ROADS = {s["id"]: s for s in load_json("roads.json")["segments"]}


def _haversine_m(a, b) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (*a, *b))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2)
    return 6_371_000 * 2 * math.asin(math.sqrt(h))


for _road in ROADS.values():
    pts = _road["points"]
    _road["cumulative_m"] = [0.0]
    for p, q in zip(pts, pts[1:]):
        _road["cumulative_m"].append(_road["cumulative_m"][-1] + _haversine_m(p, q))
    _road["length_m"] = round(_road["cumulative_m"][-1])


def point_at(segment: str, position_m: float) -> list[float]:
    """Latitude/longitude of a position along a road segment (linear interpolation)."""
    road = ROADS[segment]
    cum, pts = road["cumulative_m"], road["points"]
    pos = max(0.0, min(position_m, cum[-1]))
    for i in range(len(pts) - 1):
        if pos <= cum[i + 1]:
            f = (pos - cum[i]) / ((cum[i + 1] - cum[i]) or 1)
            return [pts[i][0] + f * (pts[i + 1][0] - pts[i][0]),
                    pts[i][1] + f * (pts[i + 1][1] - pts[i][1])]
    return pts[-1]


def direction_label(segment: str, direction: str) -> str:
    return ROADS[segment][f"{direction}_label"]


def road_name(segment: str) -> str:
    return f"{ROADS[segment]['name']} ({segment})"


def hazard_position(vehicle: dict, distance_m: float) -> float:
    """Where the hazard is: distance_m ahead of the reporting vehicle in its travel direction."""
    sign = 1 if vehicle["direction"] == "forward" else -1
    pos = vehicle["position_m"] + sign * distance_m
    return max(0.0, min(pos, ROADS[vehicle["segment"]]["length_m"]))


def distance_ahead(vehicle: dict, hazard: dict) -> float:
    """Along-road distance from a vehicle to a hazard in the vehicle's travel direction."""
    gap = hazard["position_m"] - vehicle["position_m"]
    return gap if vehicle["direction"] == "forward" else -gap


# ---------- Agent tools ----------

def get_vehicle_reports(hazard_id: str) -> list[dict]:
    """Tool: all vehicle reports already linked to a hazard event (short-term memory)."""
    return memory.reports_for(hazard_id)


def find_matching_hazards(segment: str, direction: str, position_m: float,
                          hazard_type: str | None = None) -> list[dict]:
    """Tool: active hazards on the same segment and carriageway within MATCH_RADIUS_M.
    hazard_type=None matches any type (used for road-clear reports)."""
    matches = []
    for h in memory.active_hazards():
        same_place = (h["segment"] == segment and h["direction"] == direction
                      and abs(h["position_m"] - position_m) <= MATCH_RADIUS_M)
        if same_place and (hazard_type is None or h["hazard_type"] == hazard_type):
            matches.append(h)
    return sorted(matches, key=lambda h: abs(h["position_m"] - position_m))


def retrieve_similar_incidents(query: str, hazard_type: str | None = None, k: int = 3,
                               use_mmr: bool = False) -> list[dict]:
    """Tool: semantic search over long-term memory (RAG)."""
    return rag_index.search(query, k=k, hazard_type=hazard_type, use_mmr=use_mmr)


def history_adjustment(incidents: list[dict]) -> tuple[float, list[str]]:
    """+0.05 per similar confirmed incident, -0.05 per similar false report, capped at +/-0.15."""
    delta, notes = 0.0, []
    for inc in incidents:
        step = HISTORY_PER_INCIDENT if inc["outcome"] == "confirmed" else -HISTORY_PER_INCIDENT
        delta += step
        notes.append(f"{inc['id']} ({inc['outcome'].replace('_', ' ')}) {step:+.2f}")
    return max(-HISTORY_CAP, min(HISTORY_CAP, round(delta, 2))), notes


def verify_hazard(hazard: dict, report: dict, is_new: bool, history_delta: float = 0.0,
                  history_reason: str = "") -> dict:
    """Tool: apply the confidence rules to one new report and decide what to do.

    Returns the updated hazard plus a list of (delta, reason) entries explaining the score.
    """
    h = dict(hazard)
    h["confirming_vehicles"] = list(h["confirming_vehicles"])
    h["clear_vehicles"] = list(h["clear_vehicles"])
    vid, t = report["vehicle_id"], report["t"]
    changes: list[tuple[float, str]] = []

    if is_new:
        changes.append((FIRST_REPORT, f"First report from {vid}: starting confidence 0.50"))
        h["confirming_vehicles"].append(vid)
        if history_delta:
            changes.append((history_delta, history_reason))
    elif report["hazard_type"] == "road_clear":
        if vid in h["clear_vehicles"]:
            changes.append((0.0, f"{vid} already reported clear; not independent"))
        else:
            h["clear_vehicles"].append(vid)
            changes.append((ROAD_CLEAR, f"{vid} reports the road is clear: -0.30"))
    elif vid in h["confirming_vehicles"]:
        changes.append((0.0, f"{vid} already reported this hazard; not an independent confirmation"))
    elif t - h["last_report_t"] > CONFIRM_WINDOW_S:
        changes.append((0.0, f"{vid} report arrived more than {CONFIRM_WINDOW_S} s after the last one; "
                             "too old to corroborate"))
        h["confirming_vehicles"].append(vid)
    else:
        h["confirming_vehicles"].append(vid)
        changes.append((CONFIRMATION, f"Independent confirmation from {vid}: +0.20"))

    confidence = 0.0 if is_new else h["confidence"]
    for delta, reason in changes:
        confidence = round(max(0.0, min(1.0, confidence + delta)), 2)
        h["confidence_history"] = h["confidence_history"] + [
            {"t": t, "delta": delta, "value": confidence, "reason": reason, "report_vehicle": vid}]
    h["confidence"] = confidence
    h["max_confidence"] = max(h.get("max_confidence") or 0.0, confidence)

    # Decision
    exception = False
    if len(h["clear_vehicles"]) >= CLEAR_REPORTS_TO_RESOLVE:
        decision = "resolved"
        h["resolution"] = (f"{len(h['clear_vehicles'])} independent vehicles "
                           f"({', '.join(h['clear_vehicles'])}) reported the road clear.")
    elif h["clear_vehicles"] and confidence < RESOLVE_BELOW:
        decision = "resolved"
        h["resolution"] = (f"Confidence fell to {confidence:.2f} (below {RESOLVE_BELOW}) after "
                           f"{', '.join(h['clear_vehicles'])} reported the road clear.")
    elif confidence >= VERIFIED_AT:
        decision = "verified"
    elif confidence >= CAUTION_AT:
        decision = "caution"
    else:
        decision = "wait"
        # Safety exception: a severe hazard in low visibility always gets at least a caution.
        if h["severity"] in ("high", "critical") and h["visibility_m"] < LOW_VISIBILITY_M:
            decision, exception = "caution", True
    h["decision"] = decision
    if decision == "resolved":
        h["status"] = "resolved"
    return {"hazard": h, "changes": changes, "decision": decision, "safety_exception": exception}


def find_approaching_vehicles(hazard: dict, exclude: list[str] | None = None) -> list[dict]:
    """Tool: vehicles on the same segment and direction, behind the hazard, within ALERT_RANGE_M."""
    exclude = set(exclude or [])
    found = []
    for v in memory.vehicles():
        if v["id"] in exclude or v["segment"] != hazard["segment"] or v["direction"] != hazard["direction"]:
            continue
        d = distance_ahead(v, hazard)
        if 0 < d <= ALERT_RANGE_M:
            eta = d / (max(v["speed_kmh"], 1) / 3.6)
            found.append({"vehicle": v, "distance_m": round(d), "eta_s": round(eta)})
    return sorted(found, key=lambda x: x["distance_m"])


ALERT_TEMPLATES = {
    "verified": "SAFETY ALERT: {type} {dist} m ahead on {road} {dir}. Severity {sev}. {action}",
    "caution": "CAUTION: possible {type} about {dist} m ahead on {road} {dir} (unverified, "
               "confidence {conf:.2f}). Reduce speed and stay alert.",
    "observation_request": "OBSERVATION REQUEST: unconfirmed {type} reported {dist} m ahead on "
                           "{road} {dir}. Please report what your sensors see.",
    "all_clear": "ALL CLEAR: the {type} on {road} {dir} has been cleared.",
}


def send_mock_alert(hazard: dict, vehicle_id: str, level: str, distance_m: float | None,
                    eta_s: float | None, t: float) -> dict:
    """Tool: deliver a simulated alert to one vehicle (stored, never sent to a real car)."""
    message = ALERT_TEMPLATES[level].format(
        type=hazard["hazard_type"].replace("_", " "), dist=round(distance_m or 0),
        road=road_name(hazard["segment"]), dir=direction_label(hazard["segment"], hazard["direction"]).lower(),
        sev=hazard["severity"], action=hazard["recommended_action"], conf=hazard["confidence"])
    lat, lng = point_at(hazard["segment"], hazard["position_m"])
    return memory.save_alert({
        "hazard_id": hazard["id"], "vehicle_id": vehicle_id, "level": level, "message": message,
        "hazard_type": hazard["hazard_type"], "segment": hazard["segment"],
        "severity": hazard["severity"], "confidence": hazard["confidence"],
        "distance_m": distance_m, "eta_s": eta_s, "lat": lat, "lng": lng, "t": t})


def update_hazard_memory(hazard: dict) -> dict | None:
    """Tool: save the hazard to short-term memory; if resolved, write it to long-term memory
    and rebuild the RAG index so future reports can retrieve it. Returns the stored incident."""
    memory.save_hazard(hazard)
    if hazard["status"] != "resolved":
        return None
    incident = memory.store_incident(hazard)
    rag_index.build()
    return incident
