"""FastAPI backend for the Autonomous Vehicle Intercommunication Safety Agent System.

Run from the project root:  uvicorn backend.main:app --reload
"""
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from backend import database, llm, memory, playground, research, simulation  # noqa: E402
from backend import tools as T  # noqa: E402
from backend.agents import AGENTS, GRAPH, process_report  # noqa: E402
from backend.rag import index as rag_index  # noqa: E402

app = FastAPI(title="AV Intercommunication Safety Agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

database.init_db()
rag_index.build()


class ReportIn(BaseModel):
    vehicle_id: str
    hazard: str
    road_segment: str | None = None
    distance: float
    weather: str = "clear"
    visibility: float = 10000
    sensors: list[str] = []
    description: str = ""
    t: float = 0


class PlaygroundReportIn(BaseModel):
    vehicle_id: str
    hazard: str
    distance: float
    weather: str = "clear"
    visibility: float = 10000
    sensors: list[str] | None = None
    description: str = ""
    t: float | None = None      # default: the simulated clock (30 s after the last report)


class MoveIn(BaseModel):
    segment: str
    direction: str = "forward"
    position_m: float
    speed_kmh: float | None = None


class QuestionIn(BaseModel):
    question: str


def _with_location(item: dict) -> dict:
    lat, lng = T.point_at(item["segment"], item["position_m"])
    return {**item, "lat": lat, "lng": lng,
            "road": T.ROADS[item["segment"]]["name"],
            "direction_label": T.direction_label(item["segment"], item["direction"])}


@app.get("/api/state")
def get_state():
    hazards = [_with_location(h) for h in memory.all_hazards()]
    alerts = memory.alerts()
    incidents = memory.incidents()
    return {
        "vehicles": [_with_location(v) for v in memory.vehicles()],
        "roads": [{k: r[k] for k in ("id", "name", "points", "length_m", "forward_label", "reverse_label")}
                  for r in T.ROADS.values()],
        "hazards": hazards,
        "alerts": alerts,
        "stats": {
            "total_vehicles": len(memory.vehicles()),
            "active_hazards": sum(h["status"] == "active" for h in hazards),
            "verified_hazards": sum(h["max_confidence"] >= T.VERIFIED_AT for h in hazards),
            "alerts_generated": len(alerts),
            "resolved_hazards": sum(h["status"] == "resolved" for h in hazards),
            "incidents_total": len(incidents),
            "incidents_learned": sum(i["source"] == "learned" for i in incidents),
        },
        "incident_types": _count(incidents, "hazard_type"),
        "simulation": simulation.status(),
        "agents": AGENTS,
        "config": {"llm_provider": llm.status(), "vector_db": rag_index.name,
                   "rules": {"first_report": T.FIRST_REPORT, "confirmation": T.CONFIRMATION,
                             "road_clear": T.ROAD_CLEAR, "history_per_incident": T.HISTORY_PER_INCIDENT,
                             "history_cap": T.HISTORY_CAP, "verified_at": T.VERIFIED_AT,
                             "caution_at": T.CAUTION_AT}},
    }


def _count(rows: list[dict], key: str) -> dict:
    out: dict = {}
    for r in rows:
        out[r[key]] = out.get(r[key], 0) + 1
    return out


@app.get("/api/scenarios")
def get_scenarios():
    return simulation.list_scenarios()


@app.post("/api/scenarios/{scenario_id}/start")
def start_scenario(scenario_id: str):
    try:
        return simulation.start(scenario_id)
    except KeyError:
        raise HTTPException(404, f"Unknown scenario {scenario_id}")


@app.post("/api/simulation/next")
def next_step():
    try:
        return simulation.next_step()
    except RuntimeError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/simulation/reset")
def reset(full: bool = False):
    return simulation.reset(full=full)


@app.post("/api/reports")
def submit_report(report: ReportIn):
    if not memory.get_vehicle(report.vehicle_id):
        raise HTTPException(404, f"Unknown vehicle {report.vehicle_id}")
    return process_report(report.model_dump())


@app.get("/api/trace")
def get_trace():
    runs: dict = {}
    for entry in memory.traces():
        runs.setdefault(entry["run_id"], []).append(entry)
    return [{"run_id": rid, "steps": steps} for rid, steps in runs.items()]


@app.get("/api/playground/options")
def playground_options():
    return playground.options()


@app.post("/api/playground/report")
def playground_report(report: PlaygroundReportIn):
    vehicle = memory.get_vehicle(report.vehicle_id)
    if not vehicle:
        raise HTTPException(404, f"Unknown vehicle {report.vehicle_id}")
    body = report.model_dump()
    body["sensors"] = body["sensors"] if body["sensors"] is not None else vehicle["sensors"]
    return playground.submit(body)


@app.post("/api/playground/random")
def playground_random(count: int = 1, seed: int | None = None):
    """Generate random dummy reports (new hazards, confirmations, clear reports)."""
    return playground.generate(count, seed)


@app.post("/api/playground/reset")
def playground_reset():
    """Clear short-term memory (hazards, alerts, traces) and put vehicles back at the start."""
    simulation.state.update(scenario_id=None, index=0, log=[])
    database.reset_short_term()
    return {"ok": True}


@app.post("/api/vehicles/{vehicle_id}/move")
def move_vehicle(vehicle_id: str, move: MoveIn):
    if not memory.get_vehicle(vehicle_id):
        raise HTTPException(404, f"Unknown vehicle {vehicle_id}")
    if move.segment not in T.ROADS or move.direction not in ("forward", "reverse"):
        raise HTTPException(400, "Unknown road segment or direction")
    position = max(0.0, min(move.position_m, T.ROADS[move.segment]["length_m"]))
    changes = {"segment": move.segment, "direction": move.direction, "position_m": round(position)}
    if move.speed_kmh is not None:
        changes["speed_kmh"] = move.speed_kmh
    memory.update_vehicle(vehicle_id, **changes)
    return _with_location(memory.get_vehicle(vehicle_id))


@app.get("/api/graph")
def get_graph():
    """The compiled LangGraph as a Mermaid diagram (as the lab draws it with get_graph())."""
    return {"mermaid": GRAPH.get_graph().draw_mermaid()}


@app.get("/api/messages")
def get_messages(run_id: str | None = None):
    """Typed inter-agent messages (one-way handoffs and two-way requests/replies)."""
    return memory.messages(run_id)


@app.get("/api/tools")
def get_tools():
    """The MCP-style tool registry the agents call through, with call counts."""
    return [{**t, "calls": T.TOOL_CALLS[t["name"]]} for t in T.tool_catalog()]


@app.post("/api/benchmark")
def run_benchmark():
    """Run the five scenarios under each coordination configuration (temporary database)."""
    from backend import benchmark
    return benchmark.run()


@app.get("/api/incidents")
def get_incidents():
    return memory.incidents()


@app.post("/api/research")
def ask(q: QuestionIn):
    return research.ask(q.question)


# Serve the built dashboard (frontend/dist) if it exists, so one server runs everything.
DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="dashboard")
