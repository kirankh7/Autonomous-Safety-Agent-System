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

from backend import database, llm, memory, research, simulation  # noqa: E402
from backend import tools as T  # noqa: E402
from backend.agents import process_report  # noqa: E402
from backend.rag import EMBEDDINGS, index as rag_index  # noqa: E402

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
        "config": {"llm_provider": llm.provider(), "embeddings": EMBEDDINGS,
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
