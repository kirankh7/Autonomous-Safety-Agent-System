"""Agent 4 (conversational part): the Research Assistant.

It answers operator questions from stored event data (short-term memory) and retrieved
historical incidents (long-term memory + RAG). Every answer lists the record IDs used as evidence.
The intent is detected with simple keyword rules so the behaviour is easy to follow.
"""
import re

import os

from backend import llm, memory
from backend import tools as T


def _fmt_type(hazard_type: str) -> str:
    return hazard_type.replace("_", " ")


def _vehicle_from(question: str) -> dict | None:
    q = question.lower()
    m = re.search(r"car-\d{3}", q)
    if m:
        return memory.get_vehicle(m.group(0).upper())
    vehicles = memory.vehicles()
    for v in vehicles:  # full car name, e.g. "Ford Transit"
        if v["name"].lower() in q:
            return v
    for v in vehicles:  # make or model alone, e.g. "the Ford" or "the Prius"
        words = [w for w in v["name"].lower().split() if len(w) > 2 and w not in ("model", "truck")]
        if any(re.search(rf"\b{re.escape(w)}\b", q) for w in words):
            return v
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


ID_PATTERN = re.compile(r"\b(?:HZ|RPT|ALT|INC)-\d{3}\b")


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


def _name(vehicle_id: str) -> str:
    if vehicle_id == T.OPERATOR_ID:
        return "Fleet operator"
    v = memory.get_vehicle(vehicle_id)
    return v["name"] if v else vehicle_id


def _short_reason(e: dict) -> str:
    """Compress a confidence-history reason into a few words."""
    r, who = e["reason"], _name(e.get("report_vehicle", ""))
    if r.startswith("First report"):
        return f"first report · {who}"
    if r.startswith("Independent confirmation"):
        return f"confirmed · {who}"
    if "reports the road is clear" in r:
        return f"road clear · {who}"
    if r.startswith("RAG history"):
        return "RAG history (cold start)"
    if r.startswith("Segment history"):
        return "own segment history"
    if "not independent" in r or "already" in r:
        return f"duplicate, ignored · {who}"
    return r.split(":")[0]


def _confidence_story(a: Answer, h: dict) -> None:
    for e in h["confidence_history"]:
        a.say(f"- {e['delta']:+.2f} → {e['value']:.2f} · {_short_reason(e)}")


LEVEL = {"verified": "VERIFIED ALERT", "caution": "CAUTION ADVISORY",
         "observation_request": "LOOK REQUEST", "all_clear": "ALL CLEAR",
         "escalation": "OPERATOR ESCALATION"}


# ---------- Intent handlers (one headline line + a few fact bullets) ----------

def explain_alert(a: Answer, vehicle: dict | None, h: dict | None) -> None:
    a.tools.append("memory.alerts()")
    alerts = memory.alerts(vehicle_id=vehicle["id"]) if vehicle else memory.alerts()
    if h:
        alerts = [x for x in alerts if x["hazard_id"] == h["id"]] or alerts
    if not alerts:
        a.say(f"No alerts sent to {vehicle['name'] if vehicle else 'any vehicle'} yet.")
        return
    priority = ["verified", "caution", "observation_request", "all_clear"]
    alert = min(alerts, key=lambda x: (priority.index(x["level"]), -x["t"]))
    h = memory.get_hazard(alert["hazard_id"])
    a.tools.append(f"get_vehicle_reports({h['id']})")
    a.say(f"{_name(alert['vehicle_id'])} got a {LEVEL[alert['level']]} "
          f"{a.cite(alert['id'], 'alert', alert['message'])} for the {_fmt_type(h['hazard_type']).lower()} "
          f"{_cite_hazard(a, h)}.")
    if alert["distance_m"]:
        a.say(f"- On its path: {alert['distance_m'] / 1000:.1f} km behind, same direction, ~{alert['eta_s']:.0f} s")
    reports = [r for r in T.get_vehicle_reports(h["id"]) if r["hazard_type"] != "road_clear" and r["t"] <= alert["t"]]
    if reports:
        a.say("- Reported by: " + ", ".join(f"{_name(r['vehicle_id'])} {_cite_report(a, r)}" for r in reports))
    a.say(f"- Confidence {alert['confidence']:.2f} (verified ≥ {T.VERIFIED_AT}, caution ≥ {T.CAUTION_AT})")
    a.say(f"- Severity {h['severity']} · visibility {h['visibility_m']:.0f} m · {h['recommended_action']}")
    used = [i for i in h["retrieved_incidents"] if i["used_for"] == "confidence"]
    if h["retrieval_delta"] and used:
        a.say(f"- History {h['retrieval_delta']:+.2f} from " + ", ".join(
            _cite_incident(a, memory.get_incident(i["id"])) for i in used))


def confirmations(a: Answer, h: dict) -> None:
    reports = T.get_vehicle_reports(h["id"])
    a.tools.append(f"get_vehicle_reports({h['id']})")
    hazard_reports = [r for r in reports if r["hazard_type"] != "road_clear"]
    clear = [r for r in reports if r["hazard_type"] == "road_clear"]
    a.say(f"{len(hazard_reports)} vehicle(s) reported {_cite_hazard(a, h)}; "
          f"{max(len(hazard_reports) - 1, 0)} independent confirmation(s).")
    for i, r in enumerate(hazard_reports):
        a.say(f"- {_name(r['vehicle_id'])} {_cite_report(a, r)} · {'first report' if i == 0 else 'confirmed'}")
    for r in clear:
        a.say(f"- {_name(r['vehicle_id'])} {_cite_report(a, r)} · road clear")
    a.say(f"- Now: confidence {h['confidence']:.2f} · {h['status']}")


def confidence(a: Answer, h: dict) -> None:
    a.say(f"{_cite_hazard(a, h)} is at {h['confidence']:.2f} ({h['decision']}).")
    _confidence_story(a, h)
    for r in T.get_vehicle_reports(h["id"]):
        _cite_report(a, r)
    for inc in h["retrieved_incidents"]:
        if inc["used_for"] == "confidence" and memory.get_incident(inc["id"]):
            _cite_incident(a, memory.get_incident(inc["id"]))


def resolution(a: Answer, h: dict) -> None:
    if h["status"] == "active":
        a.say(f"{_cite_hazard(a, h)} is still ACTIVE at {h['confidence']:.2f}.")
        a.say(f"- Resolves after {T.CLEAR_REPORTS_TO_RESOLVE} independent clear reports, "
              f"or a clear report that drops it below {T.RESOLVE_BELOW}")
        return
    clear = [r for r in T.get_vehicle_reports(h["id"]) if r["hazard_type"] == "road_clear"]
    why = (f"{len(h['clear_vehicles'])} independent clear reports" if len(h["clear_vehicles"]) >= 2
           else f"confidence fell below {T.RESOLVE_BELOW}")
    a.say(f"{_cite_hazard(a, h)} was {h['status'].upper()}: {why}.")
    if clear:
        a.say("- Clear reports: " + ", ".join(f"{_name(r['vehicle_id'])} {_cite_report(a, r)}" for r in clear))
    hist = h["confidence_history"]
    if hist:
        a.say(f"- Confidence peaked at {h['max_confidence']:.2f}, ended at {hist[-1]['value']:.2f}")
    for inc in [i for i in memory.incidents() if i["hazard_id"] == h["id"]]:
        a.say(f"- Learned as {_cite_incident(a, inc)} · {inc['outcome'].replace('_', ' ')}")
    all_clear = [x for x in memory.alerts(hazard_id=h["id"]) if x["level"] == "all_clear"]
    if all_clear:
        a.say("- All-clear sent to: " + ", ".join(
            f"{_name(x['vehicle_id'])} {a.cite(x['id'], 'alert', x['message'])}" for x in all_clear))


def escalation(a: Answer, h: dict | None) -> None:
    sent = [x for x in memory.alerts() if x["level"] == "escalation"
            and (h is None or x["hazard_id"] == h["id"])]
    if not sent:
        a.say("No hazard has been escalated to the fleet operator.")
        a.say(f"- A hazard is escalated when at least 2 vehicles confirm it, another reports the road "
              f"clear, and the conflict lasts {T.ESCALATE_AFTER_S} s without being settled")
        return
    for x in sent:
        hz = memory.get_hazard(x["hazard_id"])
        a.say(f"{_cite_hazard(a, hz)} was escalated to the fleet operator "
              f"{a.cite(x['id'], 'alert', x['message'])} because vehicles kept disagreeing.")
        reports = T.get_vehicle_reports(hz["id"])
        a.tools.append(f"get_vehicle_reports({hz['id']})")
        seen = [r for r in reports if r["hazard_type"] != "road_clear"]
        clear = [r for r in reports if r["hazard_type"] == "road_clear"]
        a.say("- Saw the hazard: " + ", ".join(f"{_name(r['vehicle_id'])} {_cite_report(a, r)}" for r in seen))
        a.say("- Reported clear: " + (", ".join(f"{_name(r['vehicle_id'])} {_cite_report(a, r)}"
                                               for r in clear) or "none"))
        a.say(f"- Confidence at escalation {x['confidence']:.2f} (status now {hz['status']}); the agents "
              f"stopped requesting observations after {T.ESCALATE_AFTER_S} s of conflict and handed over")


def similar(a: Answer, question: str, h: dict | None) -> None:
    if h:
        query = f"{_fmt_type(h['hazard_type'])} {h['weather'].replace('_', ' ')} {h['description']}"
        results = T.retrieve_similar_incidents(query, hazard_type=h["hazard_type"], k=5, use_mmr=True)
        a.tools.append(f"retrieve_similar_incidents(hazard_type={h['hazard_type']}, k=5, MMR)")
        a.say(f"{len(results)} similar past incident(s) for {_cite_hazard(a, h)}:")
    else:
        results = T.retrieve_similar_incidents(question, k=5, use_mmr=True)
        a.tools.append("retrieve_similar_incidents(k=5, MMR)")
        a.say(f"{len(results)} relevant past incident(s):")
    for inc in results:
        a.say(f"- {_cite_incident(a, inc)} {_fmt_type(inc['hazard_type']).lower()} · {inc['segment']} · "
              f"{inc['outcome'].replace('_', ' ')} · sim {inc['score']:.2f}")
    if h:
        used = [i for i in h["retrieved_incidents"] if i["used_for"] == "confidence"]
        if used and h["retrieval_delta"]:
            a.say(f"- Used for scoring: {', '.join('[' + i['id'] + ']' for i in used)} → "
                  f"{h['retrieval_delta']:+.2f}")
            for inc in used:
                full = memory.get_incident(inc["id"])
                if full and full["id"] not in a.evidence:
                    _cite_incident(a, full)


def learned(a: Answer) -> None:
    incidents = memory.incidents()
    new = [i for i in incidents if i["source"] == "learned"]
    a.tools.append("memory.incidents()")
    a.say(f"Long-term memory: {len(incidents)} incidents ({len(incidents) - len(new)} seed + {len(new)} learned).")
    for inc in new:
        a.say(f"- {_cite_incident(a, inc)} {_fmt_type(inc['hazard_type']).lower()} · {inc['segment']} · "
              f"{inc['outcome'].replace('_', ' ')}")


def active(a: Answer) -> None:
    hazards = memory.active_hazards()
    a.say(f"{len(hazards)} active hazard(s)." if hazards else "No active hazards.")
    for h in hazards:
        a.say(f"- {_cite_hazard(a, h)} {_fmt_type(h['hazard_type']).lower()} · {h['confidence']:.2f} · {h['decision']}")


def list_alerts(a: Answer) -> None:
    alerts = memory.alerts()
    a.say(f"{len(alerts)} alert(s) sent." if alerts else "No alerts sent yet.")
    for x in alerts[-8:]:
        a.say(f"- {a.cite(x['id'], 'alert', x['message'])} {LEVEL[x['level']]} → {_name(x['vehicle_id'])}")


# ---------- Entry point ----------

def ask(question: str) -> dict:
    """Answer a question. With LLM_PROVIDER=anthropic and an API key, Claude (or with LLM_PROVIDER=ollama a local
    model) runs as a tool-calling agent (research_agent.py); otherwise the rule-based assistant below answers."""
    if llm.provider() == "anthropic" and llm.has_credentials():
        from backend import research_agent
        try:
            result = research_agent.ask(question)
            return {"question": question, "agent": "Research & Memory Agent",
                    "mode": f"anthropic agent ({result['model']})",
                    "intent": "llm_tool_use", **result}
        except Exception as exc:  # fall back to the rule-based assistant
            fallback = rule_based_ask(question)
            fallback["answer"] += f"\n\n(Claude agent unavailable: {type(exc).__name__}: {exc}. Showing the rule-based answer.)"
            return fallback
    if llm.provider() == "ollama" and os.getenv("OLLAMA_MODE") == "agent":
        from backend import research_agent
        try:
            result = research_agent.ask_local(question)
            return {"question": question, "agent": "Research & Memory Agent",
                    "mode": f"ollama agent ({result['model']})",
                    "intent": "llm_tool_use", **result}
        except Exception as exc:  # e.g. Ollama not running: fall back to the rule-based assistant
            fallback = rule_based_ask(question)
            fallback["answer"] += f"\n\n(Local model unavailable: {type(exc).__name__}. Showing the rule-based answer.)"
            return fallback
    return rule_based_ask(question)


def rule_based_ask(question: str) -> dict:
    q = question.lower()
    vehicle = _vehicle_from(question)
    hazard = _target_hazard(question, vehicle)

    if "escalat" in q or "operator" in q:
        a = Answer("escalation")
        escalation(a, hazard if "hz-" in q else None)
    elif "why" in q and ("alert" in q or "warn" in q):
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
    if mode in ("openai", "ollama") and llm.has_credentials():
        try:
            answer = llm.generate(question, a.records + a.lines)
            known = set(ID_PATTERN.findall(" ".join(a.records + a.lines)))
            if answer and not set(ID_PATTERN.findall(answer)) <= known:
                answer = None  # the model cited an ID it was not given: use the grounded answer
        except Exception as exc:  # fall back to the grounded mock answer
            mock_answer += f"\n\n(LLM call failed: {type(exc).__name__}; showing the mock answer.)"
    return {
        "question": question,
        "agent": "Research & Memory Agent",
        "answer": answer or mock_answer,
        "mode": f"{mode} (local)" if answer and mode == "ollama" else (mode if answer else "mock"),
        "intent": a.intent,
        "evidence": list(a.evidence.values()),
        "tools_used": a.tools,
        "agent_steps": [],
    }
