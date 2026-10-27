"""LLM-driven Research Assistant: Claude decides which memory tools to call (tool use / ReAct).

Used when LLM_PROVIDER=anthropic. Claude gets read-only tools over short-term memory, long-term
memory and the RAG index; it cannot send alerts or change confidence, which stay rule-based.
The loop is written out by hand so every tool call can be shown in the dashboard trace.
Every ID cited in the final answer is checked against the records the tools actually returned.
"""
import json
import os
import re
import shlex
import ssl
import subprocess
import time

from backend import memory
from backend import tools as T

MAX_TURNS = 8
ID_PATTERN = re.compile(r"\b(?:HZ|RPT|ALT|INC)-\d{3}\b")

SYSTEM_PROMPT = """You are the Research Assistant for a simulated autonomous-vehicle fleet safety agent \
(a university capstone; all data is synthetic). Operators ask why alerts were sent, how confident the \
system is, what happened before, and what it has learned.

Use the tools to look up facts before answering. Answer only from tool results. Cite the record IDs \
you rely on in square brackets, e.g. [HZ-001], [RPT-002], [ALT-003], [INC-014]. If the records do not \
contain the answer, say so. Never invent vehicles, incidents or numbers.

Background rules you can explain: first report 0.50; independent confirmation +0.20; road-clear report \
-0.30; similar past incidents +/-0.05 each (cap +/-0.15, only on segments with fewer than 3 past \
incidents, otherwise exact segment history); >=0.60 verified alert, 0.40-0.60 caution advisory, \
<0.40 wait and request observations; two independent clear reports resolve a hazard. \
Vehicles have callsigns: Orion = CAR-001, Falcon = CAR-002, Comet = CAR-003, Atlas = CAR-004, \
Nova = CAR-005, Titan = CAR-006, Echo = CAR-007, Pulse = CAR-008. Refer to vehicles by callsign.

Format the answer as signals, not prose:
- Line 1: the direct answer in under 15 words, with the key ID.
- Then at most 3 bullets, each under 12 words, in the style "Orion report [RPT-001] -> 0.50 caution".
- No headings, bold text, background or restating the question. Under 60 words in total."""

TOOLS = [
    {"name": "list_hazards",
     "description": "List hazard events in short-term memory with type, location, status, decision and "
                    "confidence. Use first when the question does not name a hazard ID.",
     "input_schema": {"type": "object", "properties": {
         "status": {"type": "string", "enum": ["active", "all"],
                    "description": "'active' for current hazards only, 'all' to include resolved ones."}},
         "required": ["status"]}},
    {"name": "get_hazard",
     "description": "Full record for one hazard: confidence history with the reason for every change, "
                    "confirming and road-clear vehicles, retrieved incidents, resolution.",
     "input_schema": {"type": "object", "properties": {"hazard_id": {"type": "string"}},
                      "required": ["hazard_id"]}},
    {"name": "get_vehicle_reports",
     "description": "All vehicle reports (hazard and road-clear) linked to a hazard.",
     "input_schema": {"type": "object", "properties": {"hazard_id": {"type": "string"}},
                      "required": ["hazard_id"]}},
    {"name": "get_alerts",
     "description": "Simulated alerts that were sent. Filter by vehicle and/or hazard; pass an empty "
                    "string to skip a filter.",
     "input_schema": {"type": "object", "properties": {
         "vehicle_id": {"type": "string", "description": "e.g. CAR-003, or empty"},
         "hazard_id": {"type": "string", "description": "e.g. HZ-001, or empty"}},
         "required": ["vehicle_id", "hazard_id"]}},
    {"name": "get_vehicle",
     "description": "One vehicle's current road, direction, position, speed and sensors.",
     "input_schema": {"type": "object", "properties": {"vehicle_id": {"type": "string"}},
                      "required": ["vehicle_id"]}},
    {"name": "find_approaching_vehicles",
     "description": "Vehicles currently on the same road and direction behind a hazard, within 3 km.",
     "input_schema": {"type": "object", "properties": {"hazard_id": {"type": "string"}},
                      "required": ["hazard_id"]}},
    {"name": "retrieve_similar_incidents",
     "description": "Semantic search (RAG with MMR) over long-term memory of resolved incidents. "
                    "Returns incidents with outcome (confirmed / false_report), lesson and similarity.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "Natural-language description of the situation."},
         "hazard_type": {"type": "string",
                         "enum": ["any", "stopped_truck", "accident", "flooding", "debris",
                                  "stopped_vehicle", "pothole"]},
         "k": {"type": "integer", "minimum": 1, "maximum": 8}},
         "required": ["query", "hazard_type", "k"]}},
    {"name": "list_learned_incidents",
     "description": "Incidents the agent wrote to long-term memory from feedback during this session.",
     "input_schema": {"type": "object", "properties": {}}},
]


def _hazard_summary(h: dict) -> dict:
    keys = ("id", "hazard_type", "segment", "direction", "position_m", "status", "decision",
            "confidence", "severity", "weather", "visibility_m")
    return {k: h[k] for k in keys} | {"road": T.road_name(h["segment"])}


def run_tool(name: str, args: dict):
    """Execute one tool call against memory. Raises ValueError for bad input."""
    if name == "list_hazards":
        hazards = memory.all_hazards() if args.get("status") == "all" else memory.active_hazards()
        return [_hazard_summary(h) for h in hazards]
    if name in ("get_hazard", "get_vehicle_reports", "find_approaching_vehicles"):
        h = memory.get_hazard(str(args.get("hazard_id", "")).upper())
        if not h:
            raise ValueError(f"No hazard {args.get('hazard_id')!r}. Call list_hazards to see IDs.")
        if name == "get_hazard":
            own = memory.segment_history_count(h["segment"])
            rule = (f"{h['segment']} had {own} past incidents. "
                    + ("Cold start (<3): retrieved similar incidents adjusted confidence."
                       if own < T.COLD_START_INCIDENTS else
                       "Not cold start (>=3): only this segment's own history of the same hazard type "
                       "adjusted confidence; retrieved incidents from other roads are context only."))
            return {k: v for k, v in h.items() if k != "created_t"} | {"history_rule": rule}
        if name == "get_vehicle_reports":
            return T.get_vehicle_reports(h["id"])
        return [{"vehicle_id": x["vehicle"]["id"], "distance_m": x["distance_m"], "eta_s": x["eta_s"]}
                for x in T.find_approaching_vehicles(h)]
    if name == "get_alerts":
        return memory.alerts(hazard_id=args.get("hazard_id") or None,
                             vehicle_id=args.get("vehicle_id") or None)
    if name == "get_vehicle":
        v = memory.get_vehicle(str(args.get("vehicle_id", "")).upper())
        if not v:
            raise ValueError(f"No vehicle {args.get('vehicle_id')!r}. IDs are CAR-001 to CAR-008.")
        return v | {"road": T.road_name(v["segment"]),
                    "direction_label": T.direction_label(v["segment"], v["direction"])}
    if name == "retrieve_similar_incidents":
        hazard_type = args.get("hazard_type")
        results = T.retrieve_similar_incidents(
            str(args.get("query", "")), hazard_type=None if hazard_type in (None, "any") else hazard_type,
            k=int(args.get("k", 5)), use_mmr=True)
        return [{k: i[k] for k in ("id", "segment", "hazard_type", "weather", "outcome", "description",
                                   "lesson", "score")} for i in results]
    if name == "list_learned_incidents":
        return [i for i in memory.incidents() if i["source"] == "learned"]
    raise ValueError(f"Unknown tool {name}")


def _brief(result) -> str:
    """One-line summary of a tool result for the visible trace."""
    if isinstance(result, list):
        ids = [r.get("id") or r.get("vehicle_id") for r in result if isinstance(r, dict)]
        return f"{len(result)} record(s)" + (f": {', '.join(i for i in ids if i)}" if ids else "")
    if isinstance(result, dict):
        return f"record {result.get('id', '')}".strip()
    return str(result)[:120]


_token_cache: dict = {}


def _api_key() -> str | None:
    """API key from ANTHROPIC_API_KEY, or from a helper command (e.g. a company gateway's token
    helper) set in ANTHROPIC_API_KEY_HELPER. Helper tokens are cached for five minutes."""
    helper = os.getenv("ANTHROPIC_API_KEY_HELPER")
    if not helper:
        return None  # the SDK reads ANTHROPIC_API_KEY itself
    if _token_cache.get("expires", 0) < time.time():
        out = subprocess.run(shlex.split(helper), capture_output=True, text=True, timeout=30)
        if out.returncode != 0 or not out.stdout.strip():
            raise RuntimeError("API key helper failed; check that you are signed in.")
        _token_cache.update(token=out.stdout.strip(), expires=time.time() + 300)
    return _token_cache["token"]


def make_client():
    """Anthropic client. ANTHROPIC_BASE_URL and ANTHROPIC_CA_BUNDLE support API gateways."""
    import anthropic

    kwargs = {}
    key = _api_key()
    if key:
        kwargs["api_key"] = key
    if os.getenv("ANTHROPIC_BASE_URL"):
        kwargs["base_url"] = os.getenv("ANTHROPIC_BASE_URL")
    if os.getenv("ANTHROPIC_CA_BUNDLE"):
        ca = ssl.create_default_context(cafile=os.getenv("ANTHROPIC_CA_BUNDLE"))
        kwargs["http_client"] = anthropic.DefaultHttpxClient(verify=ca)
    return anthropic.Anthropic(**kwargs)


def ask(question: str) -> dict:
    client = make_client()
    model = os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5")
    messages = [{"role": "user", "content": question}]
    steps, seen_ids, records = [], set(), {}

    for _ in range(MAX_TURNS):
        response = client.beta.messages.create(
            model=model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
            output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("The model declined to answer.")
        calls = [b for b in response.content if b.type == "tool_use"]
        if response.stop_reason != "tool_use" or not calls:
            break

        # Keep the full assistant turn (including any thinking blocks) in the history.
        messages.append({"role": "assistant", "content": response.content})
        reason = " ".join(b.text for b in response.content if b.type == "text").strip()
        results = []
        for call in calls:
            try:
                result = run_tool(call.name, call.input)
                text = json.dumps(result, default=str)
                seen_ids.update(ID_PATTERN.findall(text))
                _collect(result, records)
                results.append({"type": "tool_result", "tool_use_id": call.id, "content": text})
                steps.append({"reason": reason, "tool": call.name, "input": call.input,
                              "result": _brief(result)})
            except ValueError as exc:
                results.append({"type": "tool_result", "tool_use_id": call.id,
                                "content": f"Error: {exc}", "is_error": True})
                steps.append({"reason": reason, "tool": call.name, "input": call.input,
                              "result": f"Error: {exc}"})
            reason = ""
        messages.append({"role": "user", "content": results})
    else:
        raise RuntimeError(f"No final answer after {MAX_TURNS} turns.")

    answer = "".join(b.text for b in response.content if b.type == "text").strip()
    cited = list(dict.fromkeys(ID_PATTERN.findall(answer)))
    unverified = [c for c in cited if c not in seen_ids]
    evidence = [records.get(c, {"id": c, "kind": _kind(c), "summary": "Returned by a tool call."})
                for c in cited if c in seen_ids]
    return {"answer": answer, "evidence": evidence, "agent_steps": steps,
            "unverified_citations": unverified,
            "tools_used": list(dict.fromkeys(s["tool"] for s in steps)), "model": model}


def _kind(record_id: str) -> str:
    return {"HZ": "hazard", "RPT": "report", "ALT": "alert", "INC": "incident"}[record_id.split("-")[0]]


def _collect(result, records: dict) -> None:
    """Remember a short summary of every record a tool returned, for the evidence panel."""
    for r in result if isinstance(result, list) else [result]:
        if not isinstance(r, dict) or not ID_PATTERN.fullmatch(str(r.get("id", ""))):
            continue
        rid = r["id"]
        summary = (r.get("message") or r.get("description") or
                   f"{r.get('hazard_type', '').replace('_', ' ')} on {r.get('segment', '')}, "
                   f"status {r.get('status', '')}, confidence {r.get('confidence', '')}")
        if r.get("outcome"):
            summary += f" Outcome: {r['outcome'].replace('_', ' ')}."
        records[rid] = {"id": rid, "kind": _kind(rid), "summary": summary}
