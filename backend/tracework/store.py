import json
import sqlite3
from datetime import datetime, timezone

from .config import DB


def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,trigger_json TEXT NOT NULL,result_json TEXT,detail_json TEXT,state TEXT NOT NULL DEFAULT 'queued',error TEXT,revision INTEGER NOT NULL DEFAULT 0,updated_at TEXT);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,case_id TEXT NOT NULL,kind TEXT NOT NULL,title TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS events_case ON events(case_id,id);
        CREATE TABLE IF NOT EXISTS approvals(case_id TEXT NOT NULL,revision INTEGER NOT NULL,action TEXT NOT NULL,route TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(case_id,revision,action));
        CREATE TABLE IF NOT EXISTS discovery(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS llm_cache(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        """)


def now():
    return datetime.now(timezone.utc).isoformat()


def event(case_id, kind, title, payload=None):
    with connect() as c:
        c.execute(
            "INSERT INTO events(case_id,kind,title,payload,created_at) VALUES(?,?,?,?,?)",
            (case_id, kind, title, json.dumps(payload or {}), now()),
        )


def get_case(case_id):
    with connect() as c:
        row = c.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    if not row:
        raise KeyError(case_id)
    d = dict(row)
    for col in ["trigger_json", "result_json", "detail_json"]:
        d[col.replace("_json", "")] = json.loads(d.pop(col)) if d[col] else None
    return d


def save(case_id, answer, detail):
    with connect() as c:
        c.execute(
            "UPDATE cases SET result_json=?,detail_json=?,state='complete',error=NULL,revision=revision+1,updated_at=? WHERE id=?",
            (json.dumps(answer), json.dumps(detail), now(), case_id),
        )


def events(case_id, after=0):
    with connect() as c:
        rows = c.execute(
            "SELECT * FROM events WHERE case_id=? AND id>? ORDER BY id",
            (case_id, after),
        ).fetchall()
    return [{**dict(r), "payload": json.loads(r["payload"])} for r in rows]


def meta(key, default=None):
    with connect() as c:
        r = c.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
    return json.loads(r[0]) if r else default
