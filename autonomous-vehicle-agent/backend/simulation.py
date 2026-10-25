"""Step-by-step scenario runner for the dashboard's Hazard Simulation page.

Each "Next Step" either sends one vehicle report through the real agent workflow or asks the
Research Assistant a question. Vehicles only move when a scenario step says so.
"""
from backend import database as dbm
from backend import memory, research
from backend.agents import process_report
from backend.rag import index as rag_index

SCENARIOS = {s["id"]: s for s in dbm.load_json("scenarios.json")["scenarios"]}

# Single-user demo, so the current scenario state lives in this module.
state = {"scenario_id": None, "index": 0, "log": []}


def list_scenarios() -> list[dict]:
    return [{k: s[k] for k in ("id", "title", "summary", "weather", "visibility_m")}
            | {"steps": len(s["steps"])} for s in SCENARIOS.values()]


def _move(moves: dict) -> None:
    for vehicle_id, changes in (moves or {}).items():
        memory.update_vehicle(vehicle_id, **changes)


def start(scenario_id: str) -> dict:
    if scenario_id not in SCENARIOS:
        raise KeyError(scenario_id)
    dbm.reset_short_term()          # clear active hazards, alerts and traces; reload vehicles
    _move(SCENARIOS[scenario_id]["setup"])
    state.update(scenario_id=scenario_id, index=0, log=[])
    return status()


def next_step() -> dict:
    if not state["scenario_id"]:
        raise RuntimeError("Start a scenario first.")
    scenario = SCENARIOS[state["scenario_id"]]
    if state["index"] >= len(scenario["steps"]):
        return status()
    s = scenario["steps"][state["index"]]
    entry = {"index": state["index"], "type": s["type"], "narration": s["narration"]}
    if s["type"] == "report":
        _move(s.get("move"))
        result = process_report({**s["report"], "t": s["t"]})
        h = result["hazard"]
        entry.update(run_id=result["run_id"], decision=result["decision"],
                     hazard_id=h["id"] if h else None,
                     confidence=h["confidence"] if h else None,
                     alerts=result["alerts"], stored_incident=result["stored_incident"],
                     trace=result["trace"])
    else:
        entry.update(question=s["question"], answer=research.ask(s["question"]))
    state["log"].append(entry)
    state["index"] += 1
    return status()


def reset(full: bool = False) -> dict:
    """Reset the current scenario to step 0. full=True also forgets learned incidents."""
    if full:
        dbm.reset_long_term()
        rag_index.build()
    if state["scenario_id"]:
        return start(state["scenario_id"])
    dbm.reset_short_term()
    return status()


def status() -> dict:
    sid = state["scenario_id"]
    if not sid:
        return {"scenario": None, "index": 0, "total": 0, "done": False, "log": []}
    scenario = SCENARIOS[sid]
    steps = [{"type": s["type"], "narration": s["narration"]} for s in scenario["steps"]]
    return {"scenario": {k: scenario[k] for k in ("id", "title", "summary", "weather", "visibility_m")}
            | {"steps": steps},
            "index": state["index"], "total": len(steps),
            "done": state["index"] >= len(steps), "log": state["log"]}
