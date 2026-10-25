"""Agent memory.

Short-term memory: the live situation (vehicles, reports, active hazards, alerts sent, traces).
It is cleared when a scenario is reset.

Long-term memory: resolved incidents (20 historical seeds plus anything the agent learns
from feedback). It persists across scenarios and is what the RAG index searches.
"""
from backend import database as dbm

# A hazard with no new reports for this long expires (simulated seconds).
EXPIRY_S = 15 * 60


# ---------- Short-term memory ----------

def vehicles() -> list[dict]:
    return dbm.query("SELECT * FROM vehicles ORDER BY id")


def get_vehicle(vehicle_id: str) -> dict | None:
    return dbm.get("vehicles", vehicle_id)


def update_vehicle(vehicle_id: str, **changes) -> None:
    v = get_vehicle(vehicle_id)
    if v:
        dbm.upsert("vehicles", {**v, **changes})


def add_report(report: dict) -> dict:
    report = {**report, "id": dbm.next_id("reports", "RPT")}
    dbm.upsert("reports", report)
    return report


def reports_for(hazard_id: str) -> list[dict]:
    return dbm.query("SELECT * FROM reports WHERE hazard_id = ? ORDER BY t, id", (hazard_id,))


def active_hazards() -> list[dict]:
    return dbm.query("SELECT * FROM hazards WHERE status = 'active' ORDER BY id")


def all_hazards() -> list[dict]:
    return dbm.query("SELECT * FROM hazards ORDER BY id")


def get_hazard(hazard_id: str) -> dict | None:
    return dbm.get("hazards", hazard_id)


def new_hazard_id() -> str:
    """Hazard IDs stay unique across scenarios because long-term memory refers to them."""
    used = [h["id"] for h in all_hazards()] + [i["hazard_id"] for i in incidents() if i["hazard_id"]]
    numbers = [int(x.split("-")[1]) for x in used]
    return f"HZ-{(max(numbers) + 1 if numbers else 1):03d}"


def save_hazard(hazard: dict) -> None:
    dbm.upsert("hazards", hazard)


def save_alert(alert: dict) -> dict:
    alert = {**alert, "id": dbm.next_id("alerts", "ALT")}
    dbm.upsert("alerts", alert)
    return alert


def alerts(hazard_id: str | None = None, vehicle_id: str | None = None) -> list[dict]:
    sql, params = "SELECT * FROM alerts WHERE 1=1", []
    if hazard_id:
        sql += " AND hazard_id = ?"
        params.append(hazard_id)
    if vehicle_id:
        sql += " AND vehicle_id = ?"
        params.append(vehicle_id)
    return dbm.query(sql + " ORDER BY t, id", tuple(params))


def add_trace(entry: dict) -> None:
    cols = ("run_id", "step", "agent", "stage", "thought", "action", "tool", "result", "confidence", "t")
    dbm.db().execute(
        f"INSERT INTO trace ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
        [entry.get(c) for c in cols],
    )
    dbm.db().commit()


def traces() -> list[dict]:
    return dbm.query("SELECT * FROM trace ORDER BY id")


def expire_stale(now_t: float) -> list[str]:
    """Mark active hazards with no reports for EXPIRY_S seconds as expired."""
    expired = []
    for h in active_hazards():
        if now_t - h["last_report_t"] > EXPIRY_S:
            h.update(status="expired", decision="expired",
                     resolution=f"No new reports for {EXPIRY_S // 60} minutes.")
            save_hazard(h)
            expired.append(h["id"])
    return expired


# ---------- Long-term memory ----------

def incidents() -> list[dict]:
    return dbm.query("SELECT * FROM incidents ORDER BY id")


def get_incident(incident_id: str) -> dict | None:
    return dbm.get("incidents", incident_id)


def segment_history_count(segment: str) -> int:
    """How many resolved incidents long-term memory holds for this road segment."""
    return len(dbm.query("SELECT id FROM incidents WHERE segment = ?", (segment,)))


def store_incident(hazard: dict, road_feature: str = "lane") -> dict:
    """Write a resolved hazard to long-term memory so future retrieval can use it."""
    was_real = hazard["max_confidence"] >= 0.6
    outcome = "confirmed" if was_real else "false_report"
    n_reports = len(hazard["report_ids"])
    if was_real:
        lesson = (f"{hazard['hazard_type'].replace('_', ' ').title()} reported by "
                  f"{len(hazard['confirming_vehicles'])} vehicles was real and cleared after "
                  f"{len(hazard['clear_vehicles'])} road-clear reports.")
    else:
        lesson = (f"{hazard['hazard_type'].replace('_', ' ').title()} report was not confirmed; "
                  f"passing vehicles reported the road clear.")
    incident = {
        "id": dbm.next_id("incidents", "INC"),
        "date": "simulated",
        "segment": hazard["segment"],
        "hazard_type": hazard["hazard_type"],
        "road_feature": road_feature,
        "weather": hazard["weather"],
        "visibility_m": hazard["visibility_m"],
        "outcome": outcome,
        "reports": n_reports,
        "description": hazard["description"],
        "lesson": lesson,
        "source": "learned",
        "hazard_id": hazard["id"],
    }
    dbm.upsert("incidents", incident)
    return incident
