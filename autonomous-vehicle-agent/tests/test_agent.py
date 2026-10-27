"""Basic tests for the agent workflow. Run from the project root:  pytest -q"""
import os
import tempfile

os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["LLM_PROVIDER"] = "mock"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend import database, memory, research, simulation  # noqa: E402
from backend import tools as T  # noqa: E402
from backend.agents import process_report  # noqa: E402
from backend.main import app  # noqa: E402
from backend.rag import index  # noqa: E402

FOG = {"hazard": "stopped_truck", "road_segment": "ROAD-01", "weather": "fog", "visibility": 100,
       "description": "Stopped truck in the right lane"}


@pytest.fixture(autouse=True)
def fresh_state():
    database.reset_short_term()
    database.reset_long_term()
    index.build()
    simulation.state.update(scenario_id=None, index=0, log=[])
    # Put three vehicles on I-580 eastbound and one on the opposite carriageway.
    memory.update_vehicle("CAR-001", segment="ROAD-01", direction="forward", position_m=3000)
    memory.update_vehicle("CAR-002", segment="ROAD-01", direction="forward", position_m=3050)
    memory.update_vehicle("CAR-003", segment="ROAD-01", direction="forward", position_m=2400)
    memory.update_vehicle("CAR-004", segment="ROAD-01", direction="reverse", position_m=4300)


def report(vehicle_id, distance, t=0, **extra):
    return process_report({**FOG, "vehicle_id": vehicle_id, "distance": distance, "t": t, **extra})


def test_hazard_report_is_processed():
    result = report("CAR-001", 500)
    hazard = result["hazard"]
    assert hazard["hazard_type"] == "stopped_truck"
    assert hazard["position_m"] == 3500
    assert hazard["confidence"] == 0.5
    assert hazard["decision"] == "caution"
    stages = [s["stage"] for s in result["trace"]]
    assert stages[0] == "observation" and "verify" in stages and stages[-1] == "memory"


def test_independent_confirmation_increases_confidence():
    report("CAR-001", 500)
    assert report("CAR-002", 450, t=40)["hazard"]["confidence"] == 0.7
    # The same vehicle reporting again is not independent, so nothing changes.
    assert report("CAR-002", 450, t=60)["hazard"]["confidence"] == 0.7


def test_clear_reports_decrease_confidence_and_resolve():
    report("CAR-001", 500)
    report("CAR-002", 450, t=40)
    memory.update_vehicle("CAR-005", segment="ROAD-01", direction="forward", position_m=3400)
    memory.update_vehicle("CAR-006", segment="ROAD-01", direction="forward", position_m=3450)
    first_clear = report("CAR-005", 100, t=600, hazard="road_clear")["hazard"]
    assert first_clear["confidence"] == 0.4 and first_clear["status"] == "active"
    resolved = report("CAR-006", 50, t=660, hazard="road_clear")["hazard"]
    assert resolved["status"] == "resolved"
    learned = [i for i in memory.incidents() if i["source"] == "learned"]
    assert learned and learned[0]["hazard_id"] == resolved["id"]


def test_only_approaching_vehicles_receive_alerts():
    report("CAR-001", 500)
    result = report("CAR-002", 450, t=40)
    alerted = {a["vehicle_id"] for a in result["alerts"]}
    assert alerted == {"CAR-003"}              # behind the hazard, same direction
    assert result["alerts"][0]["level"] == "verified"
    approaching = {x["vehicle"]["id"] for x in T.find_approaching_vehicles(result["hazard"])}
    assert "CAR-004" not in approaching        # opposite carriageway


def test_historical_incidents_can_be_retrieved():
    results = T.retrieve_similar_incidents(
        "flooding | heavy rain [SEP] water across both lanes under the underpass at night",
        hazard_type="flooding", k=3)
    assert {r["id"] for r in results} == {"INC-003", "INC-008", "INC-014"}


def test_retrieval_changes_the_decision_on_a_cold_start_segment():
    simulation.start("flooding")
    status = simulation.next_step()
    step = status["log"][0]
    assert step["confidence"] == 0.65 and step["decision"] == "verified"


def test_research_answers_cite_actual_records():
    report("CAR-001", 500)
    report("CAR-002", 450, t=40)
    answer = research.ask("Why was an alert generated for Ford Transit?")
    ids = {e["id"] for e in answer["evidence"]}
    assert {"RPT-001", "RPT-002"} <= ids
    for rid in ids:                             # every cited ID exists in memory
        assert (memory.get_hazard(rid) or memory.get_incident(rid)
                or database.get("reports", rid) or database.get("alerts", rid))
    assert "[RPT-002]" in answer["answer"]


def test_api_runs_a_full_scenario():
    client = TestClient(app)
    client.post("/api/scenarios/fog_truck/start")
    for _ in range(7):
        status = client.post("/api/simulation/next").json()
    assert status["done"]
    state = client.get("/api/state").json()
    assert state["stats"]["incidents_learned"] == 1
    assert state["hazards"][0]["status"] == "resolved"


def test_claude_research_agent_loop_with_fake_client(monkeypatch):
    """The tool-calling loop runs tools Claude asks for and only accepts citations it has seen."""
    from types import SimpleNamespace as NS

    from backend import research_agent

    report("CAR-001", 500)
    report("CAR-002", 450, t=40)
    turns = [
        NS(stop_reason="tool_use", content=[
            NS(type="text", text="Find the alert first."),
            NS(type="tool_use", id="t1", name="get_alerts",
               input={"vehicle_id": "CAR-003", "hazard_id": ""})]),
        NS(stop_reason="tool_use", content=[
            NS(type="tool_use", id="t2", name="get_vehicle_reports", input={"hazard_id": "HZ-001"})]),
        NS(stop_reason="end_turn", content=[NS(type="text", text=(
            "CAR-003 got [ALT-003] because CAR-001 [RPT-001] and CAR-002 [RPT-002] reported "
            "[HZ-001]. See also [INC-999]."))]),
    ]
    sent = []

    class FakeMessages:
        def create(self, **kwargs):
            sent.append(kwargs)
            return turns[len(sent) - 1]

    class FakeClient:
        beta = NS(messages=FakeMessages())

    monkeypatch.setattr(research_agent, "make_client", lambda: FakeClient())
    result = research_agent.ask("Why was an alert generated for Ford Transit?")

    assert [s["tool"] for s in result["agent_steps"]] == ["get_alerts", "get_vehicle_reports"]
    assert {e["id"] for e in result["evidence"]} == {"ALT-003", "RPT-001", "RPT-002", "HZ-001"}
    assert result["unverified_citations"] == ["INC-999"]      # cited but never returned by a tool
    # messages: question, assistant tool call, tool result for t1, assistant, tool result for t2
    history = sent[-1]["messages"]
    assert [m["content"][0]["tool_use_id"] for m in history[2::2]] == ["t1", "t2"]
