"""Coordination benchmark: every scenario under four coordination configurations
(the Module 5 lab's "benchmark coordination configurations" exercise, on this project's data).

    hybrid      the production graph: sequential fast path, conditional routing, and a two-way
                Verification <-> Research & Memory loop that runs only for new hazards
    one_way     the lab's one-way protocol: the same agents, but Verification never asks for
                history, so every hand-off is fire-and-forget
    sequential  a fixed assembly line: every agent runs on every report (history retrieval
                included), with no conditional routing
    single_pass no verification: any hazard report becomes a verified alert at once and a single
                road-clear report resolves it (the "just forward what vehicles say" baseline)

Metrics per configuration (summed over the scenarios): agent node calls, tool calls, retrieval
calls, inter-agent messages, mean latency per report, verified alerts sent, false verified
alerts (sent in a scenario whose hazard was not real), and how many report decisions match the
hybrid graph. False alerts count verified alerts and false warnings count verified alerts or
caution advisories, in a scenario whose hazard was not real. Runs in a temporary database, so the live dashboard state is never touched.

Run from the project root:  python -m backend.benchmark
"""
import contextlib
import sqlite3
import tempfile
import time
from collections import Counter
from pathlib import Path

from langgraph.graph import END, StateGraph

from backend import agents as A
from backend import database as dbm
from backend import memory
from backend import tools as T
from backend.rag import index as rag_index
from backend.simulation import SCENARIOS, _move

# Ground truth for the synthetic scenarios: was there really a hazard?
HAZARD_IS_REAL = {"fog_truck": True, "accident": True, "flooding": True, "false_report": False,
                  "road_cleared": True, "conflicting_reports": True, "two_hazards": True}

CONFIGS = {
    "hybrid": "Graph with conditional routing and a two-way history loop (production)",
    "one_way": "Same agents, one-way handoffs only: Verification never asks for history",
    "sequential": "Fixed pipeline: every agent on every report, no conditional routing",
    "single_pass": "No verifier: every hazard report is forwarded as a verified alert",
}


# ---------- Alternative graphs ----------

def _skip_if_no_hazard(fn):
    return lambda state: {} if state.get("hazard") is None else fn(state)


def _sequential_retrieve(state):
    """Retrieval runs on every report. For updates the result is unused, but the cost is paid."""
    if state.get("hazard") is None:
        return {}
    out = A.retrieve_history({**state, "hazard": dict(state["hazard"])})
    if state["is_new"]:
        return out
    return {"history_ready": True, "trace": out["trace"], "messages": out["messages"]}


def _verify_one_way(state):
    """one_way: Verification scores at once, without requesting history."""
    return A.verify({**state, "history_ready": True})


def _forward_without_verifying(state):
    """single_pass: keep the bookkeeping, but skip the confidence thresholds."""
    obs = state["observation"]
    result = T.call_tool("verify_hazard", state["hazard"], obs, state["is_new"])
    hazard = result["hazard"]
    decision = "resolved" if obs["hazard_type"] == "road_clear" else "verified"
    hazard.update(decision=decision, status="resolved" if decision == "resolved" else "active")
    if decision == "verified":
        hazard["max_confidence"] = max(hazard["max_confidence"], T.VERIFIED_AT)
    else:
        hazard["resolution"] = f"{obs['vehicle_id']} reported the road clear."
    return {"hazard": hazard, "decision": decision,
            "trace": [A.step(A.VERIFICATION, "verify", "No verification in this configuration.",
                             "Forward the report as-is", "-", A.DECISION_TEXT[decision],
                             hazard["confidence"])],
            "messages": [A.msg(A.HAZARD_ANALYSIS, A.ALERT, "decision", A.DECISION_TEXT[decision])]}


def build(config: str, wrap):
    if config == "hybrid":
        return A.build_graph(wrap)
    g = StateGraph(A.AgentState)
    g.add_node("hazard_analysis", wrap("hazard_analysis", A.hazard_analysis))
    g.add_node("alert", wrap("alert", _skip_if_no_hazard(A.alert)))
    g.add_node("update_memory", wrap("update_memory", A.update_memory))
    g.set_entry_point("hazard_analysis")
    if config == "one_way":
        g.add_node("verify", wrap("verify", _verify_one_way))
        g.add_conditional_edges("hazard_analysis",
                                lambda s: "update_memory" if s["hazard"] is None else "verify",
                                ["verify", "update_memory"])
        g.add_edge("verify", "alert")
        g.add_edge("alert", "update_memory")
    elif config == "sequential":
        g.add_node("retrieve_history", wrap("retrieve_history", _sequential_retrieve))
        g.add_node("verify", wrap("verify", _skip_if_no_hazard(A.verify)))
        for a, b in [("hazard_analysis", "retrieve_history"), ("retrieve_history", "verify"),
                     ("verify", "alert"), ("alert", "update_memory")]:
            g.add_edge(a, b)
    elif config == "single_pass":
        g.add_node("forward", wrap("forward", _forward_without_verifying))
        g.add_conditional_edges("hazard_analysis",
                                lambda s: "update_memory" if s["hazard"] is None else "forward",
                                ["forward", "update_memory"])
        g.add_edge("forward", "alert")
        g.add_edge("alert", "update_memory")
    else:
        raise ValueError(f"Unknown configuration {config!r}")
    g.add_edge("update_memory", END)
    return g.compile()


# ---------- Isolation ----------

@contextlib.contextmanager
def isolated_database():
    """Swap in a temporary SQLite database, then restore the live one and resync the vector DB."""
    live = dbm.db()
    tmp = Path(tempfile.mkdtemp()) / "benchmark.db"
    conn = sqlite3.connect(tmp, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(dbm.SCHEMA)
    dbm._conn = conn
    try:
        dbm.reset_short_term()
        dbm.reset_long_term()
        yield
    finally:
        dbm.reset_long_term()     # drop incidents learned during the benchmark from the vector DB
        rag_index.build()
        conn.close()
        dbm._conn = live
        rag_index.build()


# ---------- Runner ----------

def run_scenario(config: str, scenario_id: str) -> dict:
    scenario = SCENARIOS[scenario_id]
    dbm.reset_short_term()
    dbm.reset_long_term()
    rag_index.build()
    _move(scenario["setup"])
    node_calls: Counter = Counter()

    def wrap(name, fn):
        def counted(state):
            node_calls[name] += 1
            return fn(state)
        return counted

    graph = build(config, wrap)
    tools_before = T.TOOL_CALLS.copy()
    decisions, latencies, messages = [], [], []
    for s in scenario["steps"]:
        if s["type"] != "report":
            continue
        _move(s.get("move"))
        start = time.perf_counter()
        result = A.process_report({**s["report"], "t": s["t"]}, graph=graph)
        latencies.append((time.perf_counter() - start) * 1000)
        decisions.append(result["decision"])
        messages += result["messages"]
    tools = T.TOOL_CALLS - tools_before
    everything = memory.alerts()
    escalations = [a for a in everything if a["level"] == "escalation"]
    sent = [a for a in everything if a["vehicle_id"] != T.OPERATOR_ID]
    verified = [a for a in sent if a["level"] == "verified"]
    real = HAZARD_IS_REAL[scenario_id]
    return {
        "scenario": scenario_id, "reports": len(decisions), "decisions": decisions,
        "node_calls": sum(node_calls.values()), "tool_calls": sum(tools.values()),
        "retrieval_calls": tools["retrieve_similar_incidents"],
        "messages": len(messages), "two_way_messages": sum(m["protocol"] == "two_way" for m in messages),
        "latency_ms": latencies, "verified_alerts": len(verified),
        "false_alerts": 0 if real else len(verified),
        # Any warning (verified alert or caution advisory) about a hazard that was not real.
        "false_warnings": 0 if real else sum(a["level"] in ("verified", "caution") for a in sent),
        "escalations": len(escalations),
        "warned_vehicles": len({a["vehicle_id"] for a in sent if a["level"] != "all_clear"}) if real else 0,
    }


def run(configs: list[str] | None = None) -> dict:
    configs = configs or list(CONFIGS)
    with isolated_database():
        per = {c: [run_scenario(c, sid) for sid in SCENARIOS] for c in configs}
    baseline = {r["scenario"]: r["decisions"] for r in per.get("hybrid", [])}
    summary = []
    for c, rows in per.items():
        lat = [x for r in rows for x in r["latency_ms"]]
        same = sum(a == b for r in rows for a, b in zip(r["decisions"], baseline.get(r["scenario"], [])))
        summary.append({
            "config": c, "description": CONFIGS[c], "reports": sum(r["reports"] for r in rows),
            **{k: sum(r[k] for r in rows) for k in ("node_calls", "tool_calls", "retrieval_calls",
                                                     "messages", "two_way_messages", "verified_alerts",
                                                     "false_alerts", "false_warnings", "escalations",
                                                     "warned_vehicles")},
            "mean_latency_ms": round(sum(lat) / len(lat), 1) if lat else 0.0,
            "decisions_match_hybrid": f"{same}/{sum(r['reports'] for r in rows)}" if baseline else "-",
        })
    for rows in per.values():
        for r in rows:
            r["latency_ms"] = round(sum(r["latency_ms"]) / max(len(r["latency_ms"]), 1), 1)
    return {"summary": summary, "scenarios": per, "vector_db": rag_index.name}


def format_table(result: dict) -> str:
    cols = [("config", "Config"), ("node_calls", "Agent calls"), ("tool_calls", "Tool calls"),
            ("retrieval_calls", "RAG calls"), ("messages", "Messages"), ("two_way_messages", "Two-way"),
            ("mean_latency_ms", "ms/report"), ("verified_alerts", "Verified alerts"),
            ("false_alerts", "False alerts"), ("false_warnings", "False warnings"),
            ("escalations", "Escalations"),
            ("warned_vehicles", "Vehicles warned"),
            ("decisions_match_hybrid", "Same decisions")]
    rows = [[str(r[k]) for k, _ in cols] for r in result["summary"]]
    widths = [max(len(h), *(len(row[i]) for row in rows)) for i, (_, h) in enumerate(cols)]
    line = lambda vals: "  ".join(v.ljust(w) for v, w in zip(vals, widths))  # noqa: E731
    return "\n".join([line([h for _, h in cols]), line(["-" * w for w in widths]), *map(line, rows)])


if __name__ == "__main__":
    from backend.database import init_db
    init_db()
    rag_index.build()
    out = run()
    print(f"Vector DB: {out['vector_db']}  ·  {len(SCENARIOS)} scenarios\n")
    print(format_table(out))
