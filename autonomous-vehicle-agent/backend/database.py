"""SQLite storage for vehicles, reports, hazards, alerts, incidents and agent traces.

Lists and dicts are stored as JSON text, so each table maps cleanly to a Python dict.
"""
import json
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = Path(os.getenv("DB_PATH", ROOT / "agent.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS vehicles (
    id TEXT PRIMARY KEY, name TEXT, model TEXT, segment TEXT, direction TEXT,
    position_m REAL, speed_kmh REAL, sensors TEXT
);
CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY, hazard_id TEXT, vehicle_id TEXT, hazard_type TEXT, segment TEXT,
    direction TEXT, position_m REAL, distance_m REAL, weather TEXT, visibility_m REAL,
    sensors TEXT, description TEXT, t REAL
);
CREATE TABLE IF NOT EXISTS hazards (
    id TEXT PRIMARY KEY, hazard_type TEXT, segment TEXT, direction TEXT, position_m REAL,
    status TEXT, decision TEXT, confidence REAL, max_confidence REAL, severity TEXT,
    recommended_action TEXT, weather TEXT, visibility_m REAL, description TEXT,
    report_ids TEXT, confirming_vehicles TEXT, clear_vehicles TEXT, confidence_history TEXT,
    retrieved_incidents TEXT, retrieval_delta REAL, created_t REAL, last_report_t REAL,
    resolution TEXT
);
CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY, hazard_id TEXT, vehicle_id TEXT, level TEXT, message TEXT,
    hazard_type TEXT, segment TEXT, severity TEXT, confidence REAL, distance_m REAL,
    eta_s REAL, lat REAL, lng REAL, t REAL
);
CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY, date TEXT, segment TEXT, hazard_type TEXT, road_feature TEXT,
    weather TEXT, visibility_m REAL, outcome TEXT, reports INTEGER, description TEXT,
    lesson TEXT, source TEXT, hazard_id TEXT
);
CREATE TABLE IF NOT EXISTS trace (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, step INTEGER, agent TEXT, stage TEXT,
    thought TEXT, action TEXT, tool TEXT, result TEXT, confidence REAL, t REAL, signal TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, seq INTEGER, sender TEXT, receiver TEXT,
    kind TEXT, protocol TEXT, content TEXT, payload TEXT, t REAL
);
"""

JSON_FIELDS = {"sensors", "report_ids", "confirming_vehicles", "clear_vehicles",
               "confidence_history", "retrieved_incidents", "signal", "payload"}


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


_conn = None


def db() -> sqlite3.Connection:
    """Return a shared connection (the app is single-user, so one is enough)."""
    global _conn
    if _conn is None:
        _conn = connect()
        _conn.executescript(SCHEMA)
        # Older databases: add the trace.signal column if it is missing.
        cols = [r[1] for r in _conn.execute("PRAGMA table_info(trace)")]
        if "signal" not in cols:
            _conn.execute("ALTER TABLE trace ADD COLUMN signal TEXT")
    return _conn


def _encode(row: dict) -> dict:
    return {k: json.dumps(v) if k in JSON_FIELDS else v for k, v in row.items()}


def _decode(row: sqlite3.Row) -> dict:
    d = dict(row)
    for k in JSON_FIELDS & d.keys():
        d[k] = json.loads(d[k]) if d[k] else []
    return d


def upsert(table: str, row: dict) -> None:
    row = _encode(row)
    cols = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    db().execute(f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({marks})", list(row.values()))
    db().commit()


def query(sql: str, params: tuple = ()) -> list[dict]:
    return [_decode(r) for r in db().execute(sql, params).fetchall()]


def get(table: str, row_id: str) -> dict | None:
    rows = query(f"SELECT * FROM {table} WHERE id = ?", (row_id,))
    return rows[0] if rows else None


def next_id(table: str, prefix: str) -> str:
    """Sequential human-readable IDs such as HZ-001 or RPT-014."""
    rows = db().execute(f"SELECT id FROM {table} WHERE id LIKE ?", (f"{prefix}-%",)).fetchall()
    numbers = [int(r[0].split("-")[1]) for r in rows if r[0].split("-")[1].isdigit()]
    return f"{prefix}-{(max(numbers) + 1 if numbers else 1):03d}"


def load_json(name: str) -> dict:
    return json.loads((DATA_DIR / name).read_text())


def reset_short_term() -> None:
    """Clear short-term memory (active scenario state) and reload vehicle positions."""
    for table in ("reports", "hazards", "alerts", "trace", "messages", "vehicles"):
        db().execute(f"DELETE FROM {table}")
    db().commit()
    for v in load_json("vehicles.json")["vehicles"]:
        upsert("vehicles", v)


def reset_long_term() -> None:
    """Restore long-term memory to the 20 seed incidents (forget learned incidents)."""
    db().execute("DELETE FROM incidents")
    db().commit()
    for inc in load_json("incidents.json")["incidents"]:
        upsert("incidents", {**inc, "source": "historical", "hazard_id": None})


def init_db() -> None:
    db()
    if not query("SELECT id FROM vehicles"):
        reset_short_term()
    if not query("SELECT id FROM incidents"):
        reset_long_term()
