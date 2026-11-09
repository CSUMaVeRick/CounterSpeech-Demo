"""Read-only queries and summaries for experiment records."""
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


def session_events(db, participant):
    rows = db.execute("SELECT received_at,payload FROM events WHERE participant=? ORDER BY rowid", (participant,))
    return [{**json.loads(payload), "received_at": received_at} for received_at, payload in rows]


def record_detail(path, participant):
    with readonly(path) as db:
        row = db.execute("SELECT config,state FROM sessions WHERE token_hash=?", (participant,)).fetchone()
        if row is None:
            raise ValueError("该记录不存在")
        events = session_events(db, participant)
    return {"config": json.loads(row["config"]), "state": json.loads(row["state"]), "events": events}


def completed_session_data(db, participant, config, state):
    condition = config["conditions"][0]
    likes = state["likes"]
    dislikes = state.get("dislikes", {})
    read_posts = state.get("read_posts", {})
    submitted = {}
    for response in state["comments"]:
        submitted.setdefault(response["target"], []).append({"id": response["id"], "text": response["text"]})

    comments = {row["id"]: row for row in config["stimuli"]["comments"]}
    by_post = {post_id: [] for post_id in condition["post_order"]}
    for row in condition["comment_layout"]:
        comment_id = row["comment_id"]
        comment = comments[comment_id]
        by_post[comment["post_id"]].append({
            "comment_id": comment_id, "parent_id": row["parent_id"], "text": comment["text"],
            "initial_likes": comment["initial_likes"], "initial_dislikes": comment.get("initial_dislikes", 0),
            "liked": likes.get(comment_id), "disliked": dislikes.get(comment_id),
            "submitted_replies": submitted.get(comment_id, []),
        })

    posts = {row["id"]: row for row in config["stimuli"]["posts"]}
    factors = {}
    if "counter_strategy" in condition:
        factors["counter_strategy"] = condition["counter_strategy"]
    if "counter_feedback" in condition:
        level_id = condition["counter_feedback"]
        factors["counter_feedback"] = {"id": level_id, **config["counter_feedback_levels"][level_id]}
    interaction_types = {"post_open", "post_leave", "post_read", "like", "dislike", "comment", "exposure_met", "exposure_interval"}
    interaction_fields = ("event_id", "received_at", "type", "target", "checked", "liked", "disliked", "cleared_reaction", "text", "duration_ms")
    return {
        "experiment_id": config["experiment_id"],
        "config_version": config["config_version"],
        "condition_id": condition["id"],
        "factors": factors,
        "completion_code": state["completion_code"],
        "submitted_at": state["submitted_at"],
        "pre_answers": state["pre_answers"],
        "post_answers": state["post_answers"],
        "posts": [
            {"post_id": post_id, "text": posts[post_id]["text"], "read": read_posts.get(post_id),
             "initial_likes": posts[post_id]["initial_likes"], "initial_dislikes": posts[post_id].get("initial_dislikes", 0),
             "liked": likes.get(post_id), "disliked": dislikes.get(post_id),
             "submitted_comments": submitted.get(post_id, []), "comments": by_post[post_id]}
            for post_id in condition["post_order"]
        ],
        "interactions": [
            {field: event[field] for field in interaction_fields if field in event}
            for event in session_events(db, participant) if event["type"] in interaction_types
        ],
    }
