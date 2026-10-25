"""Read-only queries for the researcher's data browser."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

RECORDS = """
WITH records AS (
  SELECT token_hash AS id,
    COALESCE(json_extract(state,'$.phase'), CASE WHEN json_extract(state,'$.completed')=1
      THEN 'legacy_complete' ELSE 'legacy_interaction' END) AS phase,
    COALESCE(json_extract(state,'$.condition_id'),json_extract(config,'$.conditions[0].id'),'') AS condition_id,
    COALESCE(json_extract(state,'$.mode'),'legacy') AS mode,
    COALESCE(json_extract(state,'$.completion_code'),'') AS completion_code,
    COALESCE(json_extract(config,'$.config_version'),'') AS config_version,
    (SELECT MIN(received_at) FROM events WHERE participant=token_hash) AS first_received,
    (SELECT MAX(received_at) FROM events WHERE participant=token_hash) AS last_received,
    (SELECT COUNT(*) FROM events WHERE participant=token_hash) AS event_count
  FROM sessions
)
"""


@contextmanager
def readonly(path):
    db = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        yield db
    finally:
        db.close()


def list_records(path, *, phase="", condition="", search="", page=1, page_size=20):
    if type(page) is not int or page < 1 or page_size not in {20, 50}:
        raise ValueError("无效分页参数")
    where = "WHERE (?='' OR phase=?) AND (?='' OR condition_id=?) AND (?='' OR instr(lower(id || ' ' || completion_code),lower(?))>0)"
    params = (phase, phase, condition, condition, search, search)
    with readonly(path) as db:
        totals = dict(db.execute(RECORDS + "SELECT COUNT(*) AS total, COALESCE(SUM(phase='submitted'),0) AS submitted FROM records").fetchone())
        count = db.execute(RECORDS + "SELECT COUNT(*) FROM records " + where, params).fetchone()[0]
        rows = db.execute(RECORDS + "SELECT * FROM records " + where + " ORDER BY COALESCE(last_received,'') DESC,id LIMIT ? OFFSET ?", (*params, page_size, (page - 1) * page_size)).fetchall()
    return {**totals, "filtered": count, "rows": [dict(r) for r in rows]}


def record_detail(path, participant):
    with readonly(path) as db:
        row = db.execute("SELECT config,state FROM sessions WHERE token_hash=?", (participant,)).fetchone()
        if row is None:
            raise ValueError("该记录不存在")
        events = [{"received_at": event["received_at"], **json.loads(event["payload"])} for event in db.execute("SELECT received_at,payload FROM events WHERE participant=? ORDER BY rowid", (participant,))]
    return {"config": json.loads(row["config"]), "state": json.loads(row["state"]), "events": events}
