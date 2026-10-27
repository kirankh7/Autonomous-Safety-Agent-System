"""Agent 4 (conversational part): the Research Assistant.

It answers operator questions from stored event data (short-term memory) and retrieved
historical incidents (long-term memory + RAG). Every answer lists the record IDs used as evidence.
The intent is detected with simple keyword rules so the behaviour is easy to follow.
"""
import re

from backend import llm, memory
from backend import tools as T


def _fmt_type(hazard_type: str) -> str:
    return hazard_type.replace("_", " ")


def _vehicle_from(question: str) -> dict | None:
    q = question.lower()
    m = re.search(r"car-\d{3}", q)
    if m:
        return memory.get_vehicle(m.group(0).upper())
    m = re.search(r"vehicle ([a-h])\b", q)
    if m:
        name = f"Vehicle {m.group(1).upper()}"
        return next((v for v in memory.vehicles() if v["name"] == name), None)
    return None


def _target_hazard(question: str, vehicle: dict | None) -> dict | None:
    m = re.search(r"hz-\d{3}", question.lower())
    if m:
        return memory.get_hazard(m.group(0).upper())
    if vehicle:
        alerts = memory.alerts(vehicle_id=vehicle["id"])
        if alerts:
            return memory.get_hazard(alerts[-1]["hazard_id"])
    hazards = memory.all_hazards()
    return max(hazards, key=lambda h: (h["last_report_t"], h["id"])) if hazards else None


class Answer:
    """Collects grounded facts and the evidence records behind them."""

    def __init__(self, intent: str):
        self.intent, self.lines, self.records, self.evidence, self.tools = intent, [], [], {}, []

    def cite(self, rid: str, kind: str, summary: str) -> str:
        self.evidence[rid] = {"id": rid, "kind": kind, "summary": summary}
        self.records.append(f"[{rid}] {kind}: {summary}")
        return f"[{rid}]"

    def say(self, text: str) -> None:
        self.lines.append(text)


def _cite_hazard(a: Answer, h: dict) -> str:
    return a.cite(h["id"], "hazard", (
        f"{_fmt_type(h['hazard_type'])} on {T.road_name(h['segment'])} "
        f"{T.direction_label(h['segment'], h['direction']).lower()}, status {h['status']}, "
        f"decision {h['decision']}, confidence {h['confidence']:.2f}, severity {h['severity']}, "
        f"visibility {h['visibility_m']:.0f} m"))


def _cite_report(a: Answer, r: dict) -> str:
    kind = "road-clear report" if r["hazard_type"] == "road_clear" else "hazard report"
    return a.cite(r["id"], "report", f"{kind} from {r['vehicle_id']} at t={r['t']:.0f}s: "
                                      f"{r['description']}")


def _cite_incident(a: Answer, i: dict) -> str:
    return a.cite(i["id"], "incident", (
        f"{_fmt_type(i['hazard_type'])} on {i['segment']} ({i['weather'].replace('_', ' ')}), "
        f"outcome {i['outcome'].replace('_', ' ')}. {i['description']} Lesson: {i['lesson']}"))


def _confidence_story(a: Answer, h: dict) -> None:
    for entry in h["confidence_history"]:
        a.say(f"- t={entry['t']:.0f}s: {entry['delta']:+.2f} -> {entry['value']:.2f} ({entry['reason']})")


# ---------- Intent handlers ----------

def explain_alert(a: Answer, vehicle: dict | None, h: dict | None) -> None:
    a.tools.append("memory.alerts()")
    alerts = memory.alerts(vehicle_id=vehicle["id"]) if vehicle else memory.alerts()
    if h:
        alerts = [x for x in alerts if x["hazard_id"] == h["id"]] or alerts
    if not alerts:
        who = f"{vehicle['name']} ({vehicle['id']})" if vehicle else "any vehicle"
        a.say(f"No alerts have been sent to {who} in the current scenario.")
        return
    priority = ["verified", "caution", "observation_request", "all_clear"]
    alert = min(alerts, key=lambda x: (priority.index(x["level"]), -x["t"]))
    h = memory.get_hazard(alert["hazard_id"])
    v = memory.get_vehicle(alert["vehicle_id"])
    reports = T.get_vehicle_reports(h["id"])
    a.tools.append(f"get_vehicle_reports({h['id']})")
    level_text = {"verified": "a verified safety alert", "caution": "a caution advisory",
                  "observation_request": "an observation request", "all_clear": "an all-clear notice"}
    a.say(f"{v['name']} ({v['id']}) received {level_text[alert['level']]} {a.cite(alert['id'], 'alert', alert['message'])} "
          f"for {_fmt_type(h['hazard_type'])} {_cite_hazard(a, h)}.")
    if alert["distance_m"]:
        a.say(f"It was {alert['distance_m']:.0f} m behind the hazard on the same carriageway "
              f"(about {alert['eta_s']:.0f} s away), so it was on an affected path.")
    hazard_reports = [r for r in reports if r["hazard_type"] != "road_clear" and r["t"] <= alert["t"]]
    if hazard_reports:
        a.say("Evidence at the time: " + ", ".join(
            f"{r['vehicle_id']} {_cite_report(a, r)}" for r in hazard_reports) + ".")
    at_alert = [e for e in h["confidence_history"] if e["t"] <= alert["t"]]
    if at_alert:
        a.say("How the confidence score was built:")
        for e in at_alert:
            a.say(f"- {e['delta']:+.2f} -> {e['value']:.2f} ({e['reason']})")
    thresholds = {"verified": f"at or above the {T.VERIFIED_AT} verified-alert threshold",
                  "caution": f"between {T.CAUTION_AT} and {T.VERIFIED_AT} (caution band)",
                  "observation_request": f"below {T.CAUTION_AT}, so the agent asked for observations",
                  "all_clear": "after the hazard was resolved"}
    a.say(f"The alert was sent at confidence {alert['confidence']:.2f}, {thresholds[alert['level']]}. "
          f"Severity is {h['severity']} (visibility {h['visibility_m']:.0f} m). "
          f"Recommended action: {h['recommended_action']}")
    for inc in h["retrieved_incidents"]:
        if inc["used_for"] == "confidence":
            full = memory.get_incident(inc["id"])
            if full:
                _cite_incident(a, full)
    if h["retrieval_delta"]:
        ids = ", ".join(f"[{i['id']}]" for i in h["retrieved_incidents"] if i["used_for"] == "confidence")
        a.say(f"Historical incidents {ids} adjusted confidence by {h['retrieval_delta']:+.2f}.")


def confirmations(a: Answer, h: dict) -> None:
    reports = T.get_vehicle_reports(h["id"])
    a.tools.append(f"get_vehicle_reports({h['id']})")
    hazard_reports = [r for r in reports if r["hazard_type"] != "road_clear"]
    clear = [r for r in reports if r["hazard_type"] == "road_clear"]
    first = hazard_reports[0] if hazard_reports else None
    confirms = hazard_reports[1:]
    a.say(f"{_cite_hazard(a, h)} was first reported by {first['vehicle_id']} {_cite_report(a, first)}."
          if first else f"{_cite_hazard(a, h)} has no hazard reports.")
    if confirms:
        a.say(f"{len(confirms)} independent vehicle(s) confirmed it: " + ", ".join(
            f"{r['vehicle_id']} {_cite_report(a, r)}" for r in confirms) + ".")
    else:
        a.say("No other vehicle has confirmed it yet.")
    if clear:
        a.say(f"{len(clear)} vehicle(s) later reported the road clear: " + ", ".join(
            f"{r['vehicle_id']} {_cite_report(a, r)}" for r in clear) + ".")
    a.say(f"Current confidence: {h['confidence']:.2f} (status {h['status']}).")


def confidence(a: Answer, h: dict) -> None:
    a.say(f"Confidence history for {_cite_hazard(a, h)}:")
    _confidence_story(a, h)
    for r in T.get_vehicle_reports(h["id"]):
        _cite_report(a, r)
    used = [i for i in h["retrieved_incidents"] if i["used_for"] == "confidence"]
    for inc in used:
        full = memory.get_incident(inc["id"])
        if full:
            _cite_incident(a, full)
    a.say(f"Rules: first report 0.50, independent confirmation +0.20, road-clear report -0.30, "
          f"each similar past incident +/-0.05 (max +/-0.15). Current value {h['confidence']:.2f} "
          f"-> {h['decision']}.")


def resolution(a: Answer, h: dict) -> None:
    if h["status"] == "active":
        a.say(f"{_cite_hazard(a, h)} is still active at confidence {h['confidence']:.2f}. It resolves "
              f"after {T.CLEAR_REPORTS_TO_RESOLVE} independent road-clear reports, or when a clear "
              f"report pushes confidence below {T.RESOLVE_BELOW}.")
        return
    a.say(f"{_cite_hazard(a, h)} was {h['status']}: {h['resolution']}")
    clear = [r for r in T.get_vehicle_reports(h["id"]) if r["hazard_type"] == "road_clear"]
    if clear:
        a.say("Road-clear reports: " + ", ".join(f"{r['vehicle_id']} {_cite_report(a, r)}" for r in clear) + ".")
    _confidence_story(a, h)
    stored = [i for i in memory.incidents() if i["hazard_id"] == h["id"]]
    for inc in stored:
        a.say(f"The outcome was stored in long-term memory as {_cite_incident(a, inc)} "
              f"(outcome: {inc['outcome'].replace('_', ' ')}), so future reports can retrieve it.")
    all_clear = [x for x in memory.alerts(hazard_id=h["id"]) if x["level"] == "all_clear"]
    if all_clear:
        a.say("All-clear notices sent to: " + ", ".join(
            f"{x['vehicle_id']} {a.cite(x['id'], 'alert', x['message'])}" for x in all_clear) + ".")


def similar(a: Answer, question: str, h: dict | None) -> None:
    if h:
        query = f"{_fmt_type(h['hazard_type'])} {h['weather'].replace('_', ' ')} {h['description']}"
        results = T.retrieve_similar_incidents(query, hazard_type=h["hazard_type"], k=5, use_mmr=True)
        a.tools.append(f"retrieve_similar_incidents(hazard_type={h['hazard_type']}, k=5, MMR lambda=0.5)")
        a.say(f"Incidents similar to {_cite_hazard(a, h)}, retrieved from long-term memory (MMR for variety):")
    else:
        results = T.retrieve_similar_incidents(question, k=5, use_mmr=True)
        a.tools.append("retrieve_similar_incidents(k=5, MMR lambda=0.5)")
        a.say("Most relevant incidents in long-term memory:")
    if not results:
        a.say("No sufficiently similar incidents were found.")
    for inc in results:
        a.say(f"- {_cite_incident(a, inc)} {inc['segment']}, {inc['weather'].replace('_', ' ')}, "
              f"{inc['outcome'].replace('_', ' ')} (similarity {inc['score']:.2f}): {inc['lesson']}")
    if h:
        used = [i for i in h["retrieved_incidents"] if i["used_for"] == "confidence"]
        if used and h["retrieval_delta"]:
            a.say(f"For scoring, the agent used {', '.join('[' + i['id'] + ']' for i in used)}, "
                  f"which adjusted confidence by {h['retrieval_delta']:+.2f}.")
            for inc in used:
                full = memory.get_incident(inc["id"])
                if full and full["id"] not in a.evidence:
                    _cite_incident(a, full)


def learned(a: Answer) -> None:
    incidents = memory.incidents()
    new = [i for i in incidents if i["source"] == "learned"]
    a.tools.append("memory.incidents()")
    a.say(f"Long-term memory holds {len(incidents)} incidents: {len(incidents) - len(new)} historical "
          f"and {len(new)} learned from feedback in this session.")
    for inc in new:
        a.say(f"- {_cite_incident(a, inc)} from hazard {inc['hazard_id']}: {inc['lesson']}")
    if new:
        a.say("These are now in the RAG index, so similar future reports are scored with this outcome.")


def active(a: Answer) -> None:
    hazards = memory.active_hazards()
    if not hazards:
        a.say("There are no active hazards right now.")
    for h in hazards:
        a.say(f"- {_cite_hazard(a, h)}: {_fmt_type(h['hazard_type'])}, confidence {h['confidence']:.2f}, "
              f"{h['decision']}")


def list_alerts(a: Answer) -> None:
    alerts = memory.alerts()
    if not alerts:
        a.say("No alerts have been sent yet.")
    for x in alerts[-8:]:
        a.say(f"- {a.cite(x['id'], 'alert', x['message'])} to {x['vehicle_id']} ({x['level'].replace('_', ' ')})")


# ---------- Entry point ----------

def ask(question: str) -> dict:
    """Answer a question. With LLM_PROVIDER=anthropic and an API key, Claude runs as a
    tool-calling agent (research_agent.py); otherwise the rule-based assistant below answers."""
    if llm.provider() == "anthropic" and llm.has_credentials():
        from backend import research_agent
        try:
            result = research_agent.ask(question)
            return {"question": question, "mode": f"anthropic agent ({result['model']})",
                    "intent": "llm_tool_use", **result}
        except Exception as exc:  # fall back to the rule-based assistant
            fallback = rule_based_ask(question)
            fallback["answer"] += f"\n\n(Claude agent unavailable: {type(exc).__name__}: {exc}. Showing the rule-based answer.)"
            return fallback
    return rule_based_ask(question)


def rule_based_ask(question: str) -> dict:
    q = question.lower()
    vehicle = _vehicle_from(question)
    hazard = _target_hazard(question, vehicle)

    if "why" in q and ("alert" in q or "warn" in q):
        a = Answer("explain_alert")
        explain_alert(a, vehicle, hazard)
    elif "how many" in q and hazard:
        a = Answer("confirmations")
        confirmations(a, hazard)
    elif ("resolv" in q or "clear" in q) and hazard:
        a = Answer("resolution")
        resolution(a, hazard)
    elif ("confidence" in q or "score" in q) and hazard:
        a = Answer("confidence")
        confidence(a, hazard)
    elif any(w in q for w in ("similar", "previous", "past", "histor", "before")):
        a = Answer("similar_incidents")
        similar(a, question, hazard if "hz-" in q or not any(
            w in q for w in ("flood", "fog", "debris", "accident", "truck", "pothole")) else None)
    elif any(w in q for w in ("learn", "long-term", "memory", "feedback")):
        a = Answer("memory")
        learned(a)
    elif "alert" in q:
        a = Answer("alerts")
        list_alerts(a)
    elif any(w in q for w in ("current", "active", "hazard")):
        a = Answer("active_hazards")
        active(a)
    else:
        a = Answer("search")
        similar(a, question, None)

    mock_answer = "\n".join(a.lines)
    mode = llm.provider()
    answer = None
    if mode == "openai" and llm.has_credentials():
        try:
            answer = llm.generate(question, a.records + a.lines)
        except Exception as exc:  # fall back to the grounded mock answer
            mock_answer += f"\n\n(LLM call failed: {type(exc).__name__}; showing the mock answer.)"
    return {
        "question": question,
        "answer": answer or mock_answer,
        "mode": mode if answer else "mock",
        "intent": a.intent,
        "evidence": list(a.evidence.values()),
        "tools_used": a.tools,
        "agent_steps": [],
    }
