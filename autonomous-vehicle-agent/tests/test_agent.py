"""Basic tests for the agent workflow. Run from the project root:  pytest -q"""
import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DB_PATH"] = os.path.join(_tmp, "test.db")
os.environ["CHROMA_PATH"] = os.path.join(_tmp, "chroma")
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


def test_new_hazard_uses_two_way_history_loop():
    result = report("CAR-001", 500)
    kinds = [(m["sender"], m["receiver"], m["kind"], m["protocol"]) for m in result["messages"]]
    assert kinds[0][2] == "new_hazard" and kinds[0][3] == "one_way"
    assert ("Verification Agent", "Research & Memory Agent", "history_request", "two_way") in kinds
    assert ("Research & Memory Agent", "Verification Agent", "history_reply", "two_way") in kinds
    # The reply arrives before Verification scores and hands the decision to the Alert Agent.
    order = [k[2] for k in kinds]
    assert order.index("history_request") < order.index("history_reply") < order.index("decision")
    agents = [s["agent"] for s in result["trace"]]
    assert agents.index("Research & Memory Agent") < len(agents) - agents[::-1].index("Verification Agent")
    assert memory.messages(result["run_id"])           # persisted


def test_updates_skip_the_history_loop():
    report("CAR-001", 500)
    update = report("CAR-002", 450, t=40)
    assert not [m for m in update["messages"] if m["kind"].startswith("history")]
    assert [m["kind"] for m in update["messages"]][0] == "hazard_update"


def test_retrieval_failure_fails_over_to_rules(monkeypatch):
    def broken(*a, **k):
        raise RuntimeError("vector database offline")
    monkeypatch.setitem(T.TOOLS, "retrieve_similar_incidents", broken)
    result = report("CAR-001", 500)
    assert result["hazard"]["confidence"] == 0.5 and result["decision"] == "caution"
    assert {a["level"] for a in result["alerts"]} == {"caution"}   # the alert is not blocked
    reply = next(m for m in result["messages"] if m["kind"] == "history_reply")
    assert reply["payload"]["source"] == "unavailable"


def test_tool_registry_validates_calls():
    with pytest.raises(T.ToolError, match="Unknown tool"):
        T.call_tool("launch_rocket")
    with pytest.raises(T.ToolError, match="Invalid arguments"):
        T.call_tool("find_matching_hazards", segment="ROAD-01")


def test_observation_reply_is_linked_to_the_request():
    simulation.start("false_report")
    status = simulation.next_step()
    request = status["log"][0]["alerts"][0]
    assert request["level"] == "observation_request"
    status = simulation.next_step()
    reply = next(m for m in status["log"][1]["messages"] if m["kind"] == "observation_reply")
    assert reply["protocol"] == "two_way" and reply["payload"]["in_reply_to"] == request["id"]


def test_related_obstruction_matches_within_150_m():
    report("CAR-001", 500)                                  # stopped truck at 3500 m
    debris = report("CAR-002", 530, t=30, hazard="debris")  # debris at 3580 m, 80 m away
    assert debris["hazard"]["id"] == "HZ-001" and debris["hazard"]["confidence"] == 0.7
    far = report("CAR-003", 1300, t=50, hazard="debris")    # 3700 m: 200 m away, new event
    assert far["hazard"]["id"] == "HZ-002"


def test_benchmark_compares_coordination_configs():
    from backend import benchmark
    before = len(memory.vehicles()), memory.get_vehicle("CAR-001")["position_m"]
    result = benchmark.run()
    rows = {r["config"]: r for r in result["summary"]}
    assert rows["hybrid"]["false_alerts"] == 0 and rows["single_pass"]["false_alerts"] > 0
    assert rows["sequential"]["retrieval_calls"] > rows["hybrid"]["retrieval_calls"]
    same, total = rows["sequential"]["decisions_match_hybrid"].split("/")
    assert same == total                                    # same decisions, more retrieval
    assert rows["one_way"]["retrieval_calls"] == 0 and rows["one_way"]["false_warnings"] > 0
    # The live database is untouched.
    assert (len(memory.vehicles()), memory.get_vehicle("CAR-001")["position_m"]) == before


def test_conflicting_reports_escalate_to_the_fleet_operator():
    simulation.start("conflicting_reports")
    log = [simulation.next_step()["log"][-1] for _ in range(7)]
    reports = [e for e in log if e["type"] == "report"]
    assert [r["confidence"] for r in reports] == [0.5, 0.7, 0.4, 0.4, 0.1]
    escalations = [a for r in reports for a in r["alerts"] if a["level"] == "escalation"]
    assert len(escalations) == 1 and escalations[0]["vehicle_id"] == T.OPERATOR_ID
    assert reports[3]["alerts"] == escalations                   # escalated at the 4th report only
    assert reports[-1]["decision"] == "resolved"
    answer = log[4]["answer"]
    assert answer["intent"] == "escalation" and escalations[0]["id"] in {e["id"] for e in answer["evidence"]}


def test_no_escalation_when_clear_reports_settle_the_conflict():
    simulation.start("fog_truck")
    while not simulation.status()["done"]:
        simulation.next_step()
    assert not [a for a in memory.alerts() if a["level"] == "escalation"]


def test_two_hazards_are_tracked_separately():
    simulation.start("two_hazards")
    while not simulation.status()["done"]:
        simulation.next_step()
    hazards = {h["id"]: h for h in memory.all_hazards()}
    assert len(hazards) == 3
    assert hazards["HZ-001"]["segment"] != hazards["HZ-002"]["segment"]
    assert hazards["HZ-002"]["direction"] != hazards["HZ-003"]["direction"]   # opposite carriageway


def test_playground_random_traffic_is_reproducible_and_valid():
    from backend import playground

    def run():
        database.reset_short_term()                              # default vehicle positions
        database.reset_long_term()                               # forget incidents learned before
        index.build()
        return [(r["hazard"]["id"] if r["hazard"] else None, r["decision"])
                for r in playground.generate(12, seed=7)]

    first = run()
    times = [r["t"] for r in database.query("SELECT t FROM reports ORDER BY t")]
    assert run() == first and len(first) == 12                   # same seed, same traffic
    assert times == sorted(set(times))                           # the simulated clock moves forward
    assert {d for _, d in first} & {"verified", "caution", "wait", "resolved"}


def test_playground_api_custom_report_and_move():
    client = TestClient(app)
    moved = client.post("/api/vehicles/CAR-007/move",
                        json={"segment": "ROAD-03", "direction": "forward", "position_m": 500}).json()
    assert moved["segment"] == "ROAD-03" and moved["position_m"] == 500
    client.post("/api/vehicles/CAR-003/move", json={"segment": "ROAD-03", "direction": "forward", "position_m": 600})
    first = client.post("/api/playground/report",
                        json={"vehicle_id": "CAR-007", "hazard": "flooding", "distance": 300,
                              "weather": "heavy_rain", "visibility": 800}).json()
    second = client.post("/api/playground/report",
                         json={"vehicle_id": "CAR-003", "hazard": "flooding", "distance": 200}).json()
    assert first["hazard"]["hazard_type"] == "flooding" and first["hazard"]["position_m"] == 800
    assert second["hazard"]["id"] == first["hazard"]["id"]       # CAR-003 is at 600 m: confirms it
    assert client.get("/api/playground/options").json()["hazard_types"]
    assert "retrieve_history" in client.get("/api/graph").json()["mermaid"]
    assert client.post("/api/playground/reset").json()["ok"] and not memory.all_hazards()
