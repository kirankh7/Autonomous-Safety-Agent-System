"""Playground: send your own reports or generate random dummy traffic through the real agents.

Everything is synthetic. A random report is either
  - a follow-up on an active hazard: another vehicle is placed 60-400 m behind it on the same
    carriageway and confirms it (70%) or reports the road clear (30%), or
  - a new hazard: a random vehicle reports a random hazard type ahead of it in random weather,
    and with 60% probability another vehicle is placed behind it so someone can be alerted.
Reports get a simulated clock: each one arrives 20-90 s after the previous report.
"""
import random

from backend import database as dbm
from backend import memory
from backend import tools as T
from backend.agents import process_report

WEATHER = [  # (weather, visibility in metres)
    ("clear", 9000), ("rain", 3000), ("heavy_rain", 800), ("fog", 150), ("night", 1500), ("snow", 600)]

DESCRIPTIONS = {
    "stopped_truck": ["Stopped truck in the right lane, hazard lights on", "Big rig stalled across the lane"],
    "accident": ["Two-car collision blocking the left lane", "Crash with debris on the shoulder"],
    "flooding": ["Standing water across both lanes", "Water across the road at the underpass"],
    "debris": ["Ladder lying in the middle lane", "Tire tread debris in the right lane"],
    "stopped_vehicle": ["Disabled car stopped in the right lane", "Stalled car on the shoulder, partly in lane"],
    "pothole": ["Deep pothole in the left lane", "Large pothole near the lane marking"],
    "road_clear": ["Lane is clear, no hazard visible", "Road clear, traffic moving normally"],
}
HAZARD_TYPES = [h for h in T.HAZARD_TABLE]


def clock(gap: float = 30) -> float:
    """Simulated time for the next report: gap seconds after the latest report."""
    latest = max((r["t"] for r in dbm.query("SELECT t FROM reports")), default=None)
    return 0.0 if latest is None else latest + gap


def submit(report: dict) -> dict:
    """Run a user-written report; t defaults to the simulated clock."""
    if report.get("t") is None:
        report = {**report, "t": clock()}
    return process_report(report)


def _place_behind(vehicle: dict, segment: str, direction: str, target_m: float, gap_m: float) -> float:
    """Move a vehicle gap_m behind a road position on the given carriageway; return its position."""
    sign = 1 if direction == "forward" else -1
    pos = max(0.0, min(target_m - sign * gap_m, T.ROADS[segment]["length_m"]))
    memory.update_vehicle(vehicle["id"], segment=segment, direction=direction, position_m=round(pos))
    return pos


def random_report(rng: random.Random) -> tuple[dict, str]:
    """Build one plausible random report (and move vehicles as needed). Returns (report, narration)."""
    vehicles = memory.vehicles()
    active = memory.active_hazards()
    t = clock(rng.randint(20, 90))

    if active and rng.random() < 0.55:
        h = rng.choice(active)
        helpers = [v for v in vehicles
                   if v["id"] not in h["confirming_vehicles"] + h["clear_vehicles"]]
        if helpers:
            v = rng.choice(helpers)
            gap = rng.randint(60, 400)
            _place_behind(v, h["segment"], h["direction"], h["position_m"], gap)
            clear = rng.random() < 0.3
            kind = "road_clear" if clear else h["hazard_type"]
            report = {"vehicle_id": v["id"], "hazard": kind, "road_segment": h["segment"],
                      "distance": gap, "weather": h["weather"], "visibility": h["visibility_m"],
                      "sensors": v["sensors"], "description": rng.choice(DESCRIPTIONS[kind]), "t": t}
            verb = "reports the road clear at" if clear else "confirms"
            return report, f"{v['name']} {verb} {h['id']} ({h['hazard_type'].replace('_', ' ')})"

    v = rng.choice(vehicles)
    kind = rng.choice(HAZARD_TYPES)
    weather, visibility = rng.choice(WEATHER)
    length = T.ROADS[v["segment"]]["length_m"]
    room = (length - v["position_m"]) if v["direction"] == "forward" else v["position_m"]
    if room < 200:  # too close to the end of the road: turn the vehicle around
        v["direction"] = "reverse" if v["direction"] == "forward" else "forward"
        memory.update_vehicle(v["id"], direction=v["direction"])
        room = (length - v["position_m"]) if v["direction"] == "forward" else v["position_m"]
    distance = rng.randint(120, max(121, min(700, int(room) - 50)))
    hazard_pos = T.hazard_position(v, distance)
    if rng.random() < 0.6:  # put someone behind the hazard so the Alert Agent has a target
        others = [o for o in vehicles if o["id"] != v["id"]]
        if others:
            _place_behind(rng.choice(others), v["segment"], v["direction"], hazard_pos,
                          distance + rng.randint(300, 1500))
    report = {"vehicle_id": v["id"], "hazard": kind, "road_segment": v["segment"], "distance": distance,
              "weather": weather, "visibility": visibility, "sensors": v["sensors"],
              "description": rng.choice(DESCRIPTIONS[kind]), "t": t}
    return report, (f"{v['name']} reports {kind.replace('_', ' ')} {distance} m ahead on "
                    f"{T.ROADS[v['segment']]['name']} ({weather.replace('_', ' ')})")


def generate(count: int = 1, seed: int | None = None) -> list[dict]:
    """Send `count` random reports through the agents. A seed makes the traffic reproducible."""
    rng = random.Random(seed)
    results = []
    for _ in range(max(1, min(count, 50))):
        report, narration = random_report(rng)
        result = process_report(report)
        results.append({**result, "report": report, "narration": narration})
    return results


def options() -> dict:
    """Choices for the Playground form."""
    return {"hazard_types": HAZARD_TYPES + ["road_clear"],
            "weather": [{"id": w, "visibility_m": vis} for w, vis in WEATHER],
            "roads": [{"id": r["id"], "name": r["name"], "length_m": r["length_m"],
                       "forward_label": r["forward_label"], "reverse_label": r["reverse_label"]}
                      for r in T.ROADS.values()]}
