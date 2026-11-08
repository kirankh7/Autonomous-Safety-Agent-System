r"""The agent workflow: four agents coordinated as a LangGraph (hybrid: a sequential fast path
plus one conditional, two-way loop).

    report -> [Hazard Analysis] --(hazard event)--> [Verification] --(decision)--> [Alert]
                     |                               |    ^                           |
                     | (clear, nothing to clear)     |    | history reply             v
                     |                    history    v    |              [Research & Memory: update]
                     |                    request [Research & Memory: retrieve]        |
                     \----------------------------------------------------------------> END

- One-way handoffs on the fast path (Analysis -> Verification -> Alert -> Memory): each agent
  passes a typed message to the next and never waits for a reply.
- Two-way validation where evidence is needed: for a new hazard, Verification sends a
  history_request to Research & Memory and loops back when the history_reply arrives. If
  retrieval fails, Research & Memory replies "unavailable" and Verification fails over to the
  rules without history, so an alert is never blocked by the vector database.
- Two-way with the fleet: an observation request from the Alert Agent is answered by a vehicle's
  next report, which Hazard Analysis links back to the request.

Each node follows a ReAct pattern: it states a Thought about the current observation, takes an
Action by calling a tool (through the MCP-style registry, tools.call_tool), and records the
tool's result (Observation), which drives the next step. Decisions are rule-based and
transparent; every step is written to an execution trace and every handoff to a message log.
"""
import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, StateGraph

from backend import memory
from backend import tools as T
from backend.rag import query_text
from backend.tools import ToolError, call_tool

# The four agents, defined once; the API serves this list to the dashboard.
AGENTS = [
    {"number": 1, "name": "Hazard Analysis Agent",
     "role": "Understands each report, locates the hazard and matches it to known events."},
    {"number": 2, "name": "Verification Agent",
     "role": "Scores the evidence with the confidence rules and decides what to do."},
    {"number": 3, "name": "Alert Agent",
     "role": "Finds vehicles approaching the hazard and sends simulated alerts."},
    {"number": 4, "name": "Research & Memory Agent",
     "role": "Retrieves similar past incidents, updates memory and answers operator questions."},
]
HAZARD_ANALYSIS, VERIFICATION, ALERT, RESEARCH_MEMORY = (a["name"] for a in AGENTS)

DECISION_TEXT = {
    "verified": "verified alert",
    "caution": "caution advisory",
    "wait": "wait for more evidence (request observations)",
    "resolved": "resolve hazard",
}
ALERT_LEVEL = {"verified": "verified", "caution": "caution", "wait": "observation_request"}


class AgentState(TypedDict, total=False):
    report: dict            # raw report from a vehicle
    observation: dict       # normalised report
    hazard: dict | None     # hazard event being worked on
    is_new: bool
    retrieved: list         # incidents retrieved by RAG
    history_delta: float
    history_reason: str
    history_source: str     # "rag" (cold start) or "segment" (own history)
    decision: str
    alerts: list
    stored_incident: dict | None
    history_requested: bool  # Verification asked Research & Memory for history (two-way)
    history_ready: bool      # Research & Memory has replied
    escalation: str | None   # reason to hand the hazard to the human fleet operator
    trace: Annotated[list, operator.add]
    messages: Annotated[list, operator.add]   # typed inter-agent messages


def step(agent: str, stage: str, thought: str, action: str, tool: str, result: str,
         confidence: float | None = None, signal: dict | None = None) -> dict:
    return {"agent": agent, "stage": stage, "thought": thought, "action": action,
            "tool": tool, "result": result, "confidence": confidence, "signal": signal}


def msg(sender: str, receiver: str, kind: str, content: str, protocol: str = "one_way",
        **payload) -> dict:
    """A typed message from one agent to another (or to a vehicle).
    protocol: one_way (handoff, no reply expected) | two_way (request or reply)."""
    return {"sender": sender, "receiver": receiver, "kind": kind, "protocol": protocol,
            "content": content, "payload": payload}


def sig(label: str, detail: str = "", tone: str = "neutral") -> dict:
    """The short, machine-readable signal an agent emits for each step (shown first in the UI).
    tone: neutral | info | good | warning | serious | critical"""
    return {"label": label, "detail": detail, "tone": tone}


DECISION_SIGNAL = {"verified": ("VERIFIED", "critical"), "caution": ("CAUTION", "warning"),
                   "wait": ("NEED EVIDENCE", "serious"), "resolved": ("RESOLVED", "good")}
ALERT_SIGNAL = {"verified": ("ALERT", "critical"), "caution": ("CAUTION", "warning"),
                "observation_request": ("LOOK REQUEST", "serious"), "all_clear": ("ALL CLEAR", "good"),
                "escalation": ("ESCALATED", "critical")}
FLEET_OPERATOR = "Fleet operator"


def car_name(vehicle_id: str) -> str:
    if vehicle_id == T.OPERATOR_ID:
        return FLEET_OPERATOR
    v = memory.get_vehicle(vehicle_id)
    return v["name"] if v else vehicle_id
SEVERITY_TONE = {"critical": "critical", "high": "serious", "medium": "warning", "low": "info"}



def decision_for(confidence: float) -> str:
    if confidence >= T.VERIFIED_AT:
        return "verified"
    return "caution" if confidence >= T.CAUTION_AT else "wait"


# ---------- Agent 1: Hazard Analysis ----------

def hazard_analysis(state: AgentState) -> dict:
    raw = state["report"]
    vehicle = memory.get_vehicle(raw["vehicle_id"])
    hazard_type = T.classify_hazard(raw["hazard"], raw.get("description", ""))
    segment = raw.get("road_segment") or vehicle["segment"]
    position = T.hazard_position(vehicle, raw["distance"])
    road, direction = T.road_name(segment), T.direction_label(segment, vehicle["direction"])
    obs = {"vehicle_id": vehicle["id"], "hazard_type": hazard_type, "segment": segment,
           "direction": vehicle["direction"], "position_m": round(position),
           "distance_m": raw["distance"], "weather": raw.get("weather", "clear"),
           "visibility_m": raw.get("visibility", 10000), "sensors": raw.get("sensors", []),
           "description": raw.get("description", ""), "t": raw.get("t", 0)}
    trace = [step(
        HAZARD_ANALYSIS, "observation",
        f"{vehicle['name']} ({vehicle['id']}) reports '{raw['hazard']}' {raw['distance']} m ahead on "
        f"{road} {direction.lower()}; weather {obs['weather'].replace('_', ' ')}, visibility "
        f"{obs['visibility_m']} m. I need to understand the report and locate the hazard.",
        "Classify the hazard type and convert 'distance ahead' into a road position",
        "classify_hazard()",
        f"hazard_type = {hazard_type}; position = {obs['position_m']} m along {segment} "
        f"({direction.lower()} carriageway)",
        signal=sig("CLEAR REPORT" if hazard_type == "road_clear" else "REPORT",
                   f"{vehicle['name']} · {hazard_type.replace('_', ' ')} · {raw['distance']:.0f} m ahead",
                   "good" if hazard_type == "road_clear" else "info"))]

    expired = memory.expire_stale(obs["t"])
    if expired:
        trace.append(step(HAZARD_ANALYSIS, "check_existing",
                          "Some hazards have had no reports for 15 minutes.",
                          "Expire stale hazards", "expire_stale()", f"Expired: {', '.join(expired)}",
                          signal=sig("EXPIRED", ", ".join(expired))))

    is_clear = hazard_type == "road_clear"
    matches = call_tool("find_matching_hazards", segment, obs["direction"], position,
                        None if is_clear else hazard_type)
    trace.append(step(
        HAZARD_ANALYSIS, "check_existing",
        "Does this report describe a hazard we are already tracking?",
        f"Search active hazards within {T.MATCH_RADIUS_M} m on the same carriageway "
        f"({T.RELATED_MATCH_RADIUS_M} m for a related obstruction)",
        f"find_matching_hazards({segment}, {obs['direction']}, {obs['position_m']}"
        f"{'' if is_clear else ', ' + hazard_type})",
        (f"Match found: {matches[0]['id']} (confidence {matches[0]['confidence']:.2f})"
         + (f"; related type {matches[0]['hazard_type'].replace('_', ' ')}, treated as the same "
            "obstruction" if not is_clear and matches[0]["hazard_type"] != hazard_type else ""))
        if matches else "No matching active hazard",
        signal=sig("MATCH", matches[0]["id"]) if matches else sig("NO MATCH", "not tracked yet")))

    if matches:
        hazard = matches[0]
        earlier = call_tool("get_vehicle_reports", hazard["id"])
        trace.append(step(
            HAZARD_ANALYSIS, "check_existing",
            f"This report updates {hazard['id']}. Which vehicles have already reported it?",
            "Load earlier reports for this hazard", f"get_vehicle_reports({hazard['id']})",
            f"{len(earlier)} earlier report(s) from "
            f"{', '.join(sorted({r['vehicle_id'] for r in earlier})) or 'none'}",
            signal=sig("PRIOR REPORTS", f"{len(earlier)} · "
                       + ", ".join(sorted({car_name(r['vehicle_id']) for r in earlier})))))
        messages = []
        asked = [a for a in memory.alerts(hazard_id=hazard["id"])
                 if a["vehicle_id"] == vehicle["id"] and a["level"] == "observation_request"]
        if asked:  # this report answers an earlier observation request (two-way with the fleet)
            messages.append(msg(vehicle["name"], HAZARD_ANALYSIS, "observation_reply",
                                f"Reply to {asked[0]['id']}: {hazard_type.replace('_', ' ')}",
                                "two_way", in_reply_to=asked[0]["id"], hazard_id=hazard["id"]))
        messages.append(msg(HAZARD_ANALYSIS, VERIFICATION, "hazard_update",
                            f"{hazard['id']}: new {'road-clear' if is_clear else 'confirming'} report "
                            f"from {vehicle['name']}", hazard_id=hazard["id"], report_type=hazard_type))
        return {"observation": obs, "hazard": hazard, "is_new": False, "trace": trace,
                "messages": messages}

    if is_clear:
        trace.append(step(HAZARD_ANALYSIS, "check_existing",
                          "A road-clear report with no active hazard here needs no action.",
                          "Record the report only", "-", "Nothing to clear",
                          signal=sig("NOTHING TO CLEAR")))
        return {"observation": obs, "hazard": None, "is_new": False, "trace": trace,
                "messages": [msg(HAZARD_ANALYSIS, RESEARCH_MEMORY, "record_only",
                                 f"Road-clear report from {vehicle['name']}; no hazard to update")]}

    severity, action = T.severity_for(hazard_type, obs["visibility_m"])
    hazard = {
        "id": memory.new_hazard_id(), "hazard_type": hazard_type, "segment": segment,
        "direction": obs["direction"], "position_m": obs["position_m"], "status": "active",
        "decision": "pending", "confidence": 0.0, "max_confidence": 0.0, "severity": severity,
        "recommended_action": action, "weather": obs["weather"], "visibility_m": obs["visibility_m"],
        "description": obs["description"], "report_ids": [], "confirming_vehicles": [],
        "clear_vehicles": [], "confidence_history": [], "retrieved_incidents": [],
        "retrieval_delta": 0.0, "created_t": obs["t"], "last_report_t": obs["t"], "resolution": None}
    trace.append(step(
        HAZARD_ANALYSIS, "check_existing",
        "This is a new hazard, so I will open a new event and look for historical context.",
        "Create hazard event", "create_event()",
        f"Created {hazard['id']}: {hazard_type.replace('_', ' ')}, severity {severity}"
        f"{' (raised for low visibility)' if obs['visibility_m'] < T.LOW_VISIBILITY_M else ''}",
        signal=sig("NEW HAZARD", f"{hazard['id']} · severity {severity}", SEVERITY_TONE[severity])))
    return {"observation": obs, "hazard": hazard, "is_new": True, "trace": trace,
            "messages": [msg(HAZARD_ANALYSIS, VERIFICATION, "new_hazard",
                             f"{hazard['id']}: {hazard_type.replace('_', ' ')} at {obs['position_m']} m, "
                             f"severity {severity}", hazard_id=hazard["id"], severity=severity)]}


def route_after_analysis(state: AgentState) -> str:
    return "update_memory" if state["hazard"] is None else "verify"


# ---------- Agent 4 (part 1): Research & Memory - retrieve history ----------

def retrieve_history(state: AgentState) -> dict:
    obs, hazard = state["observation"], dict(state["hazard"])
    query = query_text(obs["hazard_type"], obs["weather"], obs["description"])
    try:
        retrieved = call_tool("retrieve_similar_incidents", query, hazard_type=obs["hazard_type"], k=3)
    except ToolError as exc:
        return _history_failover(hazard, str(exc))
    trace = [step(
        RESEARCH_MEMORY, "retrieve",
        "Have similar hazards happened before, and were those reports real?",
        "Semantic search of long-term memory (pre-filtered to the same hazard type, top 3)",
        f"retrieve_similar_incidents(hazard_type={obs['hazard_type']}, k=3)",
        ", ".join(f"{i['id']} ({i['outcome'].replace('_', ' ')}, sim {i['score']:.2f})" for i in retrieved)
        or "No sufficiently similar incidents",
        signal=sig("RAG", f"{len(retrieved)} similar · "
                   + " ".join(f"{i['id']}{'✓' if i['outcome'] == 'confirmed' else '✗'}" for i in retrieved)))]

    own = memory.segment_history_count(obs["segment"])
    if own < T.COLD_START_INCIDENTS:
        delta, notes = call_tool("history_adjustment", retrieved)
        source = "rag"
        reason = (f"RAG history (cold start, {obs['segment']} has {own} past incident(s)): "
                  f"{'; '.join(notes) or 'none'} => {delta:+.2f}")
        thought = (f"{obs['segment']} has only {own} incident(s) of its own (cold start), so retrieved "
                   "incidents from other roads set a small, capped prior.")
        used = retrieved
    else:
        local = [i for i in memory.incidents()
                 if i["segment"] == obs["segment"] and i["hazard_type"] == obs["hazard_type"]]
        delta, notes = call_tool("history_adjustment", local)
        source = "segment"
        reason = (f"Segment history ({obs['segment']}, exact lookup): "
                  f"{'; '.join(notes) or 'no past ' + obs['hazard_type'].replace('_', ' ') + ' here'}"
                  f" => {delta:+.2f}")
        thought = (f"{obs['segment']} has {own} incidents of its own, so I use an exact lookup of that "
                   "segment's history. Retrieved incidents are kept as research context only.")
        used = local
    trace.append(step(RESEARCH_MEMORY, "retrieve", thought,
                      "Compute the bounded history adjustment (+/-0.05 per incident, cap +/-0.15)",
                      "history_adjustment()", reason,
                      signal=sig(f"HISTORY {delta:+.2f}",
                                 "cold start · RAG" if source == "rag" else "own segment history",
                                 "good" if delta > 0 else "serious" if delta < 0 else "neutral")))

    used_ids = {i["id"] for i in used}
    hazard["retrieved_incidents"] = (
        [{"id": i["id"], "score": i.get("score"), "outcome": i["outcome"], "used_for": "confidence"}
         for i in used]
        + [{"id": i["id"], "score": i["score"], "outcome": i["outcome"], "used_for": "context"}
           for i in retrieved if i["id"] not in used_ids])
    hazard["retrieval_delta"] = delta
    reply = msg(RESEARCH_MEMORY, VERIFICATION, "history_reply",
                f"{hazard['id']}: history adjustment {delta:+.2f} "
                f"({'cold start, RAG' if source == 'rag' else 'own segment history'})",
                "two_way", hazard_id=hazard["id"], delta=delta, source=source,
                incidents=[i["id"] for i in used])
    return {"hazard": hazard, "retrieved": retrieved, "history_delta": delta,
            "history_reason": reason, "history_source": source, "history_ready": True,
            "trace": trace, "messages": [reply]}


def _history_failover(hazard: dict, error: str) -> dict:
    """Retrieval failed: reply 'unavailable' so Verification scores on the rules alone."""
    hazard["retrieval_delta"] = 0.0
    reason = "History unavailable (retrieval failed) => +0.00"
    trace = [step(RESEARCH_MEMORY, "retrieve", "Have similar hazards happened before?",
                  "Semantic search of long-term memory", "retrieve_similar_incidents()",
                  f"{error}. Failing over: no history adjustment, the confidence rules still apply.",
                  signal=sig("RAG UNAVAILABLE", "failover · history +0.00", "serious"))]
    reply = msg(RESEARCH_MEMORY, VERIFICATION, "history_reply",
                f"{hazard['id']}: history unavailable, continue without it", "two_way",
                hazard_id=hazard["id"], delta=0.0, source="unavailable", error=error)
    return {"hazard": hazard, "retrieved": [], "history_delta": 0.0, "history_reason": reason,
            "history_source": "unavailable", "history_ready": True, "trace": trace,
            "messages": [reply]}


# ---------- Agent 2: Verification ----------

def verify(state: AgentState) -> dict:
    obs = state["observation"]
    if state["is_new"] and not state.get("history_ready"):
        # Two-way: a brand-new hazard has a single report, so ask Research & Memory for history
        # before scoring. route_after_verify sends the workflow there and back.
        hazard = state["hazard"]
        return {"history_requested": True, "trace": [step(
            VERIFICATION, "verify",
            f"{hazard['id']} is new, with only one report. Is there history that should shift the "
            "starting confidence?",
            "Ask the Research & Memory Agent for similar past incidents", "history_request",
            "Request sent; waiting for the reply before scoring",
            signal=sig("ASK HISTORY", f"→ {RESEARCH_MEMORY}", "info"))],
            "messages": [msg(VERIFICATION, RESEARCH_MEMORY, "history_request",
                             f"{hazard['id']}: similar past {hazard['hazard_type'].replace('_', ' ')} "
                             f"incidents in {hazard['weather'].replace('_', ' ')}?", "two_way",
                             hazard_id=hazard["id"])]}
    result = call_tool("verify_hazard", state["hazard"], obs, state["is_new"],
                             state.get("history_delta", 0.0), state.get("history_reason", ""))
    hazard, decision = result["hazard"], result["decision"]
    reasons = "; ".join(r for _, r in result["changes"])
    detail = f"{reasons}. Confidence {hazard['confidence']:.2f} -> {DECISION_TEXT[decision]}"
    if result["safety_exception"]:
        detail += " (safety exception: severe hazard in low visibility always gets a caution)"
    if result["escalation"]:
        detail += f". Escalating to the fleet operator: {result['escalation']}"
    if state["is_new"] and state.get("history_source") == "rag" and state.get("history_delta"):
        detail += (f". Without retrieval the score would be {T.FIRST_REPORT:.2f} "
                   f"({DECISION_TEXT[decision_for(T.FIRST_REPORT)]})")
    before = state["hazard"]["confidence"]
    label, tone = DECISION_SIGNAL[decision]
    trace = [step(VERIFICATION, "verify",
                  f"How reliable is {hazard['id']} after the report from {obs['vehicle_id']}?",
                  "Apply the confidence rules and choose an action", "verify_hazard()",
                  detail, hazard["confidence"],
                  signal=sig(label, f"start {hazard['confidence']:.2f}" if state["is_new"]
                             else f"{before:.2f} → {hazard['confidence']:.2f}", tone))]
    handoff = msg(VERIFICATION, ALERT, "decision",
                  f"{hazard['id']}: {DECISION_TEXT[decision]} at confidence {hazard['confidence']:.2f}",
                  hazard_id=hazard["id"], decision=decision, confidence=hazard["confidence"])
    messages = [handoff]
    if result["escalation"]:
        messages.append(msg(VERIFICATION, ALERT, "escalate", f"{hazard['id']}: {result['escalation']}",
                            hazard_id=hazard["id"]))
    return {"hazard": hazard, "decision": decision, "trace": trace, "messages": messages,
            "escalation": result["escalation"]}


def route_after_verify(state: AgentState) -> str:
    if state.get("history_requested") and not state.get("history_ready"):
        return "retrieve_history"
    return "alert"


# ---------- Agent 3: Alert ----------

def alert(state: AgentState) -> dict:
    hazard, decision, obs = state["hazard"], state["decision"], state["observation"]
    trace, sent = [], []
    previous = memory.alerts(hazard_id=hazard["id"])

    if decision == "resolved":
        targets = [{"vehicle": {"id": vid}, "distance_m": None, "eta_s": None}
                   for vid in dict.fromkeys(a["vehicle_id"] for a in previous)]
        level = "all_clear"
        trace.append(step(ALERT, "identify_vehicles",
                          "The hazard is resolved. Which vehicles were warned earlier?",
                          "Find vehicles that received alerts for this hazard",
                          f"memory.alerts({hazard['id']})",
                          ", ".join(t["vehicle"]["id"] for t in targets) or "None",
                          signal=sig("NOTIFY", ", ".join(car_name(t["vehicle"]["id"]) for t in targets)
                                     or "nobody")))
    else:
        reporters = hazard["confirming_vehicles"] + hazard["clear_vehicles"] + [obs["vehicle_id"]]
        targets = call_tool("find_approaching_vehicles", hazard, exclude=reporters)
        level = ALERT_LEVEL[decision]
        others = [v for v in memory.vehicles() if v["segment"] == hazard["segment"]
                  and v["id"] not in reporters and v["id"] not in {t["vehicle"]["id"] for t in targets}]
        skipped = [f"{v['id']} ({'opposite direction' if v['direction'] != hazard['direction'] else 'already past or out of range'})"
                   for v in others]
        result = ", ".join(f"{t['vehicle']['id']} {t['distance_m']} m away (~{t['eta_s']} s)"
                           for t in targets) or "No approaching vehicles"
        if skipped:
            result += f". Not alerted: {', '.join(skipped)}"
        trace.append(step(ALERT, "identify_vehicles",
                          f"Which vehicles are heading toward {hazard['id']} on the same carriageway?",
                          f"Find vehicles behind the hazard within {T.ALERT_RANGE_M} m, same direction",
                          f"find_approaching_vehicles({hazard['id']})", result,
                          signal=sig("APPROACHING", " · ".join(
                              f"{t['vehicle']['name']} {t['distance_m'] / 1000:.1f} km" for t in targets)
                              or "none")))

    already = {(a["vehicle_id"], a["level"]) for a in previous}
    for target in targets:
        vid = target["vehicle"]["id"]
        if (vid, level) in already:
            continue
        sent.append(call_tool("send_mock_alert", hazard, vid, level, target["distance_m"],
                              target["eta_s"], obs["t"]))
    escalated = None
    if state.get("escalation") and (T.OPERATOR_ID, "escalation") not in already:
        escalated = call_tool("send_mock_alert", hazard, T.OPERATOR_ID, "escalation", None, None, obs["t"])
        trace.append(step(ALERT, "alert",
                          "Vehicles keep disagreeing and more observation requests have not settled it.",
                          "Hand the hazard to the human fleet operator (failover)", "send_mock_alert()",
                          f"{escalated['id']} -> {FLEET_OPERATOR}: {state['escalation']}",
                          hazard["confidence"],
                          signal=sig("ESCALATED →", FLEET_OPERATOR, "critical")))
    trace.append(step(
        ALERT, "alert",
        f"Decision is '{DECISION_TEXT[decision]}', so the message type is '{level.replace('_', ' ')}'.",
        "Send simulated alerts (skipping vehicles already sent this message type)",
        "send_mock_alert()",
        " | ".join(f"{a['id']} -> {a['vehicle_id']}: {a['message']}" for a in sent)
        or "No new alerts needed", hazard["confidence"],
        signal=sig(f"{ALERT_SIGNAL[level][0]} →", ", ".join(car_name(a["vehicle_id"]) for a in sent),
                   ALERT_SIGNAL[level][1]) if sent else sig("NO NEW ALERTS")))
    messages = [msg(ALERT, car_name(a["vehicle_id"]), level, a["message"],
                    "two_way" if level == "observation_request" else "one_way",
                    alert_id=a["id"], hazard_id=hazard["id"]) for a in sent]
    if escalated:
        messages.append(msg(ALERT, FLEET_OPERATOR, "escalation", escalated["message"], "two_way",
                            alert_id=escalated["id"], hazard_id=hazard["id"]))
        sent.append(escalated)
    messages.append(msg(ALERT, RESEARCH_MEMORY, "alerts_sent",
                        f"{hazard['id']}: {len(sent)} new {level.replace('_', ' ')} message(s)",
                        hazard_id=hazard["id"], alert_ids=[a["id"] for a in sent]))
    return {"alerts": sent, "trace": trace, "messages": messages}


# ---------- Agent 4 (part 2): Research & Memory - update memory ----------

def update_memory(state: AgentState) -> dict:
    obs, hazard = state["observation"], state.get("hazard")
    report = memory.add_report({**obs, "hazard_id": hazard["id"] if hazard else None})
    if hazard is None:
        result = f"Stored {report['id']} (no hazard to update)"
        return {"stored_incident": None, "trace": [step(
            RESEARCH_MEMORY, "memory", "Keep a record of every observation.",
            "Store the report in short-term memory", "update_hazard_memory()", result,
            signal=sig("SAVED", report["id"]))]}

    hazard = {**hazard, "report_ids": hazard["report_ids"] + [report["id"]],
              "last_report_t": obs["t"]}
    incident = call_tool("update_hazard_memory", hazard)
    result = (f"Saved {report['id']} and {hazard['id']} (status {hazard['status']}, confidence "
              f"{hazard['confidence']:.2f}) to short-term memory")
    if incident:
        result += (f". Resolved hazard written to long-term memory as {incident['id']} "
                   f"(outcome: {incident['outcome'].replace('_', ' ')}); vector database now holds "
                   f"{len(memory.incidents())} incidents")
    trace = [step(RESEARCH_MEMORY, "memory",
                  "Remember what happened so later questions and future reports can use it.",
                  "Update short-term memory and, if resolved, long-term memory",
                  "update_hazard_memory()", result, hazard["confidence"],
                  signal=sig("LEARNED", f"{incident['id']} · {incident['outcome'].replace('_', ' ')}", "good")
                  if incident else sig("SAVED", f"{report['id']} → {hazard['id']}"))]
    messages = [msg(RESEARCH_MEMORY, "Long-term memory", "lesson_learned",
                    f"{incident['id']}: {incident['lesson']}", incident_id=incident["id"],
                    outcome=incident["outcome"])] if incident else []
    return {"hazard": hazard, "stored_incident": incident, "trace": trace, "messages": messages}


# ---------- Graph ----------

def build_graph(wrap=lambda name, fn: fn):
    """The production coordination graph. `wrap` lets the benchmark instrument each node."""
    g = StateGraph(AgentState)
    for name, fn in (("hazard_analysis", hazard_analysis), ("retrieve_history", retrieve_history),
                     ("verify", verify), ("alert", alert), ("update_memory", update_memory)):
        g.add_node(name, wrap(name, fn))
    g.set_entry_point("hazard_analysis")
    g.add_conditional_edges("hazard_analysis", route_after_analysis, ["verify", "update_memory"])
    g.add_conditional_edges("verify", route_after_verify, ["retrieve_history", "alert"])
    g.add_edge("retrieve_history", "verify")      # the history reply returns to Verification
    g.add_edge("alert", "update_memory")
    g.add_edge("update_memory", END)
    return g.compile()


GRAPH = build_graph()


def process_report(report: dict, graph=None) -> dict:
    """Run one vehicle report through the agent workflow and persist its trace and messages."""
    run_number = len({t["run_id"] for t in memory.traces()}) + 1
    run_id = f"RUN-{run_number:03d}"
    final = (graph or GRAPH).invoke({"report": report, "trace": [], "messages": []})
    for i, entry in enumerate(final["trace"], start=1):
        memory.add_trace({**entry, "run_id": run_id, "step": i, "t": report.get("t", 0)})
    for i, entry in enumerate(final["messages"], start=1):
        memory.add_message({**entry, "run_id": run_id, "seq": i, "t": report.get("t", 0)})
    hazard = final.get("hazard")
    return {
        "run_id": run_id,
        "hazard": memory.get_hazard(hazard["id"]) if hazard else None,
        "decision": final.get("decision"),
        "alerts": final.get("alerts", []),
        "stored_incident": final.get("stored_incident"),
        "trace": [{**e, "step": i} for i, e in enumerate(final["trace"], start=1)],
        "messages": [{**m, "seq": i} for i, m in enumerate(final["messages"], start=1)],
    }
