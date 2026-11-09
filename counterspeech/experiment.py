"""Configuration validation and transactional demo storage (standard library only)."""
import copy
import base64
import hashlib
import json
import mimetypes
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import ROOT
from .records import completed_session_data
from .study import question_order, regions, resolve, validate_answers, validate_study

THEMES = {"weibo", "xiaohongshu", "douyin", "bilibili", "zhihu"}


def asset_url(source):
    path = (ROOT / source).resolve()
    if not path.is_relative_to((ROOT / "assets").resolve()) or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".svg"}:
        raise ValueError("图片必须是 assets 内的 PNG/JPG/WebP/SVG 文件")
    content = path.read_bytes()
    if len(content) > 5 * 1024 * 1024:
        raise ValueError("单张图片不得超过 5MB")
    mime = mimetypes.guess_type(path.name)[0]
    return f"data:{mime};base64,{base64.b64encode(content).decode()}"


def save_draft(path, config):
    validate(config)
    # Resolve all assets before replacing the previous draft.
    public_config(config)
    path = Path(path)
    if path.exists():
        old = normalize_materials(json.loads(path.read_text(encoding="utf-8")))
        if old != config and old["config_version"] == config["config_version"]:
            raise ValueError("配置有变化，请先更新配置版本号")
    write_working_draft(path, config)


def write_working_draft(path, config):
    """Persist presets, including incomplete edits, separately from published config."""
    path = Path(path)
    content = json.dumps(config, ensure_ascii=False, indent=2)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def normalize_materials(config):
    """Convert nested authoring materials to the existing comment bank and layout."""
    stimuli = config["stimuli"]
    if "comments" in stimuli:
        if any("comments" in post for post in stimuli["posts"]):
            raise ValueError("请在帖子内嵌评论和独立评论表之间选择一种格式")
        return config

    comments, layout = [], []

    def collect(rows, post_id, parent_id=None):
        if not isinstance(rows, list):
            raise ValueError("comments 和 replies 须为数组")
        for order, entry in enumerate(rows, 1):
            row = {**entry, "post_id": post_id}
            replies = row.pop("replies", [])
            if "text_by_strategy" in row:
                row.setdefault("text", "")
            comments.append(row)
            layout.append({"comment_id": row["id"], "parent_id": parent_id, "sibling_order": order})
            collect(replies, post_id, row["id"])

    posts = []
    for entry in stimuli["posts"]:
        post = dict(entry)
        collect(post.pop("comments", []), post["id"])
        posts.append(post)

    post_ids = [post["id"] for post in posts]
    comment_posts = {row["id"]: row["post_id"] for row in comments}
    conditions = []
    for entry in config["conditions"]:
        condition = dict(entry)
        selected_posts = set(condition.setdefault("post_order", list(post_ids)))
        condition.setdefault("comment_layout", [dict(row) for row in layout if comment_posts[row["comment_id"]] in selected_posts])
        condition.setdefault("required_exposure_comment_ids", [
            row["id"] for row in comments if row["post_id"] in selected_posts and row.get("research_role") == "counter_speech"
        ])
        conditions.append(condition)
    return {**config, "stimuli": {**stimuli, "posts": posts, "comments": comments}, "conditions": conditions}


def validate(config):
    def require(ok, message):
        if not ok:
            raise ValueError(message)

    env, stimuli = config["environment"], config["stimuli"]
    require(isinstance(config["config_version"], str) and bool(config["config_version"].strip()), "配置版本号不能为空")
    require(env["theme"] in THEMES, "未知主题")
    completion_mode = env.get("completion_mode", "exposure")
    require(completion_mode in ("exposure", "post_read"), "未知浏览完成条件")
    show_completion_data = env.get("show_completion_data", False)
    require(type(show_completion_data) is bool, "完成页数据显示须为布尔值")
    require(not show_completion_data or "flow" in config, "显示完成数据需要前后测流程")
    require(type(env.get("mask_background_reaction_counts", False)) is bool, "背景赞踩数遮挡设置须为布尔值")
    feedback_levels = config.get("counter_feedback_levels", {})
    require(isinstance(feedback_levels, dict), "反驳赞踩档位须为对象")
    for level_id, feedback in feedback_levels.items():
        require(isinstance(level_id, str) and level_id.strip() and isinstance(feedback, dict), "无效的反驳赞踩档位")
        label = feedback.get("label")
        require(isinstance(label, str) and label.strip(), "反驳赞踩档位名称不能为空")
        for field in ("initial_likes", "initial_dislikes"):
            count = feedback.get(field)
            require(type(count) is int and count >= 0, "反驳赞踩数须为非负整数")
    require(set(env["enabled_actions"]) <= {"like", "dislike", "comment", "reply"}, "未知交互")
    require(type(env["max_comment_characters"]) is int and env["max_comment_characters"] > 0, "无效字数限制")
    exposure = env["exposure"]
    require(0 < exposure["minimum_visible_fraction"] <= 1, "无效可见比例")
    require(type(exposure["continuous_visible_ms"]) is int and exposure["continuous_visible_ms"] > 0, "无效展示时长")
    maps = {}
    for group in ("authors", "posts", "comments"):
        rows = stimuli[group]
        maps[group] = {row["id"]: row for row in rows}
        require(len(maps[group]) == len(rows), f"{group} ID 重复")
        require(all(isinstance(row["id"], str) and row["id"] for row in rows), "ID 须为非空字符串")
    require(not (maps["posts"].keys() & maps["comments"].keys()), "帖子与评论 ID 不可重叠")
    for author in stimuli["authors"]:
        require(isinstance(author["display_name"], str) and bool(author["display_name"].strip()), "昵称不能为空")
        for field in ("avatar", "bio", "location", "verified_text"):
            require(isinstance(author.get(field, ""), str), f"{field} 须为文本")
        require(type(author.get("verified", False)) is bool, "认证状态须为布尔值")
        for field in ("followers", "following"):
            require(type(author.get(field, 0)) is int and author.get(field, 0) >= 0, "关注／粉丝数须为非负整数")
    for row in stimuli["posts"] + stimuli["comments"]:
        require(row["author_id"] in maps["authors"], "作者不存在")
        require(isinstance(row["text"], str), "正文须为文本")
        require(type(row["initial_likes"]) is int and row["initial_likes"] >= 0, "赞数须为非负整数")
        dislikes = row.get("initial_dislikes", 0)
        require(type(dislikes) is int and dislikes >= 0, "踩数须为非负整数")
    for row in stimuli["comments"]:
        require(row["post_id"] in maps["posts"], "评论帖子不存在")
        if "text_by_strategy" in row:
            variants = row["text_by_strategy"]
            require(isinstance(variants, dict) and bool(variants) and all(
                isinstance(strategy, str) and strategy.strip() and isinstance(text, str) and text.strip()
                for strategy, text in variants.items()
            ), "反驳文案须按策略提供非空文本")
        minutes = row.get("relative_time_minutes", 0)
        require(type(minutes) is int and minutes >= 0, "评论相对时间须为非负整数分钟")
        age = maps["posts"][row["post_id"]].get("age_minutes")
        require(age is None or type(age) is int and minutes <= age, "评论不能晚于模拟浏览时点")
    for post in stimuli["posts"]:
        require("age_minutes" not in post or type(post["age_minutes"]) is int and post["age_minutes"] >= 0, "帖子发布时长须为非负整数分钟")
        require(isinstance(post.get("source", ""), str), "发布来源须为文本")
        for media in post.get("media", []):
            require(isinstance(media, dict) and isinstance(media.get("src"), str) and isinstance(media.get("alt"), str), "图片需要 src 和 alt")
    conditions = config["conditions"]
    require(bool(conditions) and len({c["id"] for c in conditions}) == len(conditions), "条件为空或重复")
    for condition in conditions:
        if "counter_feedback" in condition:
            level_id = condition["counter_feedback"]
            require(isinstance(level_id, str) and level_id in feedback_levels, f"条件 {condition['id']} 的反驳赞踩档位不存在")
        posts = condition["post_order"]
        require(bool(posts) and len(set(posts)) == len(posts) and set(posts) <= maps["posts"].keys(), "帖子顺序无效")
        layout = condition["comment_layout"]
        by_id = {r["comment_id"]: r for r in layout}
        expected = {c["id"] for c in stimuli["comments"] if c["post_id"] in posts}
        require(len(by_id) == len(layout) and set(by_id) == expected, "评论布局缺失或重复")
        siblings = set()
        for row in layout:
            cid, parent = row["comment_id"], row["parent_id"]
            require(parent is None or parent in by_id, "父评论不存在")
            post_id = maps["comments"][cid]["post_id"]
            variants = maps["comments"][cid].get("text_by_strategy")
            if variants is not None:
                strategy = condition.get("counter_strategy")
                require(isinstance(strategy, str) and strategy in variants, f"条件 {condition['id']} 缺少评论 {cid} 的反驳策略")
            require(parent is None or maps["comments"][parent]["post_id"] == post_id, "不能跨帖回复")
            require(parent is None or maps["comments"][cid].get("relative_time_minutes", 0) >= maps["comments"][parent].get("relative_time_minutes", 0), "回复时间不能早于父评论")
            order = row["sibling_order"]
            require(type(order) is int and order > 0, "同级顺序须为正整数")
            key = (post_id, parent, order)
            require(key not in siblings, "同级顺序重复")
            siblings.add(key)
            visited = {cid}
            while parent is not None:
                require(parent not in visited, "评论树存在循环")
                visited.add(parent)
                parent = by_id[parent]["parent_id"]
        targets = condition["required_exposure_comment_ids"]
        require(set(targets) <= by_id.keys(), "必展示评论缺失")
        if completion_mode == "exposure":
            for pid in posts:
                require(any(maps["comments"][cid]["post_id"] == pid for cid in targets), "每帖至少指定一个必展示目标")
    validate_study(config)
    return config


def load_config(path):
    return validate(normalize_materials(json.loads(Path(path).read_text(encoding="utf-8"))))


def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=15)
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY, config TEXT NOT NULL, state TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events (
            participant TEXT NOT NULL REFERENCES sessions(token_hash),
            event_id TEXT NOT NULL, received_at TEXT NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY (participant, event_id)
        );
    """)
    return db


def exchange(path, config, packet, *, mode="preview", condition_id=None):
    token = packet.get("token", "")
    if not isinstance(token, str) or len(token) != 64 or any(c not in "0123456789abcdef" for c in token):
        raise ValueError("无效恢复令牌")
    participant = hashlib.sha256(token.encode()).hexdigest()
    incoming = packet.get("events", [])
    if not isinstance(incoming, list) or len(incoming) > 500:
        raise ValueError("无效事件批次")
    db = connect(path)
    eid = None
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            saved = db.execute("SELECT config, state FROM sessions WHERE token_hash=?", (participant,)).fetchone()
            if saved:
                config, state = map(json.loads, saved)
            else:
                validate(config)
                if mode not in {"live", "demo", "preview"}:
                    raise ValueError("未知入口")
                choices = config["conditions"]
                selected = secrets.choice(choices) if mode == "live" else next((c for c in choices if c["id"] == condition_id), choices[0] if condition_id is None else None)
                if selected is None:
                    raise ValueError("演示条件不存在")
                config = copy.deepcopy(config)
                config["conditions"] = [copy.deepcopy(selected)]
                selected_posts = set(selected["post_order"])
                feedback = config.get("counter_feedback_levels", {}).get(selected.get("counter_feedback"))
                for comment in config["stimuli"]["comments"]:
                    variants = comment.pop("text_by_strategy", None)
                    if comment["post_id"] not in selected_posts:
                        continue
                    if variants:
                        comment["text"] = variants[selected["counter_strategy"]]
                    if feedback is not None and comment.get("research_role") == "counter_speech":
                        comment["initial_likes"] = feedback["initial_likes"]
                        comment["initial_dislikes"] = feedback["initial_dislikes"]
                state = {"likes": {}, "comments": [], "exposed": [], "completed": False, "mode": mode, "condition_id": selected["id"]}
                if "flow" in config:
                    state.update(phase="pre", question_order=question_order(config), pre_answers={}, post_answers={}, resolved_variables={})
                db.execute("INSERT INTO sessions VALUES (?, ?, ?)", (participant, json.dumps(config, ensure_ascii=False), json.dumps(state)))
            condition = config["conditions"][0]
            posts = set(condition["post_order"])
            rows = {r["id"]: r for r in config["stimuli"]["posts"] + config["stimuli"]["comments"]}
            allowed = posts | {r["comment_id"] for r in condition["comment_layout"]}
            targets = set(condition["required_exposure_comment_ids"])
            manual_read = config["environment"].get("completion_mode") == "post_read"
            ack = []
            for event in incoming:
                eid = event.get("event_id")
                if not isinstance(eid, str) or not 1 <= len(eid) <= 100:
                    raise ValueError("无效事件 ID")
                if db.execute("SELECT 1 FROM events WHERE participant=? AND event_id=?", (participant, eid)).fetchone():
                    ack.append(eid)
                    continue
                kind, target = event.get("type"), event.get("target")
                if state["completed"] and not (kind == "post_submit" and state.get("phase") == "post"):
                    raise ValueError("此环节已完成，不能再提交操作")
                if target is not None and target not in allowed:
                    raise ValueError("目标不属于当前条件")
                if "flow" in config and kind not in {"pre_submit", "post_submit", "session_start"} and state.get("phase") != "interaction":
                    raise ValueError("当前阶段不能进行此操作")
                if kind == "pre_submit":
                    if state.get("phase") != "pre":
                        raise ValueError("前测已确认，不能修改")
                    answers = validate_answers(config, "pre", event.get("answers"))
                    config, values, templates = resolve(config, answers)
                    state.update(pre_answers=answers, resolved_variables=values, template_texts=templates, phase="interaction")
                elif kind == "post_submit":
                    if state.get("phase") != "post":
                        raise ValueError("请先完成交互")
                    answers = validate_answers(config, "post", event.get("answers"))
                    state.update(post_answers=answers, phase="submitted", completion_code=secrets.token_hex(6), submitted_at=datetime.now(timezone.utc).isoformat())
                elif kind in {"like", "dislike"}:
                    field = "liked" if kind == "like" else "disliked"
                    active = event.get(field)
                    if kind not in config["environment"]["enabled_actions"] or target not in allowed or type(active) is not bool:
                        raise ValueError("无效点赞操作" if kind == "like" else "无效点踩操作")
                    reactions = state.setdefault(kind + "s", {})
                    other_kind = "dislike" if kind == "like" else "like"
                    other_reactions = state.get(other_kind + "s", {})
                    reactions[target] = active
                    if active and other_reactions.get(target):
                        other_reactions[target] = False
                        event = {**event, "cleared_reaction": other_kind}
                elif kind == "post_read":
                    if not manual_read or target not in posts or type(event.get("checked")) is not bool:
                        raise ValueError("无效的帖子阅读确认")
                    state.setdefault("read_posts", {})[target] = event["checked"]
                elif kind == "comment":
                    text = event.get("text", "")
                    if target not in allowed or not isinstance(text, str) or not text.strip() or len(text) > config["environment"]["max_comment_characters"]:
                        raise ValueError("回复为空、过长或对象无效")
                    action = "comment" if target in posts else "reply"
                    if action not in config["environment"]["enabled_actions"]:
                        raise ValueError("此交互未启用")
                    state["comments"].append({"id": eid, "target": target, "text": text.strip(), "post_id": target if target in posts else rows[target]["post_id"]})
                elif kind in {"exposure_met", "exposure_interval"}:
                    exposure = config["environment"]["exposure"]
                    duration = event.get("duration_ms")
                    if target not in targets or type(duration) not in {float, int} or not 0 <= duration <= 86400000:
                        raise ValueError("无效展示记录")
                    if kind == "exposure_met":
                        if duration < exposure["continuous_visible_ms"]:
                            raise ValueError("展示时长不足")
                        if target not in state["exposed"]:
                            state["exposed"].append(target)
                elif kind == "complete":
                    if manual_read:
                        read_posts = state.get("read_posts", {})
                        if not all(read_posts.get(post_id, False) for post_id in posts):
                            raise ValueError("请先勾选所有帖子的“已阅读”")
                    elif not targets <= set(state["exposed"]):
                        raise ValueError("请继续浏览评论后完成本环节")
                    state["completed"] = True
                    if "flow" in config:
                        state["phase"] = "post"
                elif kind not in {"session_start", "post_open", "post_leave"}:
                    raise ValueError("未知事件")
                event = {**event, "condition_id": state.get("condition_id", condition["id"]), "mode": state.get("mode", "preview"), "config_version": config["config_version"]}
                encoded = json.dumps(event, ensure_ascii=False, allow_nan=False)
                if len(encoded) > 12000:
                    raise ValueError("事件过大")
                db.execute("INSERT INTO events VALUES (?, ?, ?, ?)", (participant, eid, datetime.now(timezone.utc).isoformat(), encoded))
                ack.append(eid)
            db.execute("UPDATE sessions SET config=?,state=? WHERE token_hash=?", (json.dumps(config, ensure_ascii=False), json.dumps(state, ensure_ascii=False), participant))
        result = {"config": config, "state": state, "ack": ack}
        if state.get("phase") == "submitted" and config["environment"].get("show_completion_data"):
            result["completion_data"] = completed_session_data(db, participant, config, state)
        return result
    except ValueError as error:
        error.event_id = eid
        raise
    finally:
        db.close()


def public_config(config):
    result = copy.deepcopy(config)
    mask_counts = result["environment"].pop("mask_background_reaction_counts", False)
    for author in result["stimuli"]["authors"]:
        author["avatar"] = asset_url(author.get("avatar") or "assets/avatar-default.svg")
    for post in result["stimuli"]["posts"]:
        if mask_counts:
            post["mask_reaction_counts"] = True
        for media in post.get("media", []):
            media["src"] = asset_url(media["src"])
    for comment in result["stimuli"]["comments"]:
        if mask_counts and comment.get("research_role") != "counter_speech":
            comment["mask_reaction_counts"] = True
        comment.pop("research_role", None)
        comment.pop("text_by_strategy", None)
        comment.pop("fact_source", None)
    result["stimuli"].pop("material_status", None)
    if "flow" in result:
        result["regions"] = regions()
    result.pop("variables", None)
    result.pop("counter_feedback_levels", None)
    for condition in result["conditions"]:
        condition.pop("variable_rules", None)
        condition.pop("counter_strategy", None)
        condition.pop("counter_feedback", None)
    return result
