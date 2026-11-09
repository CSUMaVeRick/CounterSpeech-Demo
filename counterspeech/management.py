"""Small configuration mutations shared by admin forms and their checks."""
import copy
import re


def add_author(config, author_id, name, avatar):
    author_id, name = author_id.strip(), name.strip()
    if not author_id or not name or any(a["id"] == author_id for a in config["stimuli"]["authors"]):
        raise ValueError("用户 ID／昵称不能为空，ID 不能重复")
    config["stimuli"]["authors"].append({"id": author_id, "display_name": name, "avatar": avatar, "verified": False, "verified_text": "", "bio": "", "location": "", "followers": 0, "following": 0})


def add_post(config, post_id, source_id, author_id, text):
    post_id = post_id.strip()
    stimuli = config["stimuli"]
    existing_ids = {r["id"] for r in stimuli["posts"] + stimuli["comments"]}
    source = next(p for p in stimuli["posts"] if p["id"] == source_id)
    source_comments = [c for c in stimuli["comments"] if c["post_id"] == source_id]
    new_ids = [f"{post_id}_c{i + 1:02d}" for i in range(len(source_comments))]
    if not post_id or post_id in existing_ids or set(new_ids) & existing_ids or post_id in new_ids:
        raise ValueError("帖子 ID 为空或与已有内容 ID 冲突")
    if author_id not in {a["id"] for a in stimuli["authors"]} or not text.strip():
        raise ValueError("请选择发布者并填写正文")
    created = copy.deepcopy(source)
    created.update(id=post_id, author_id=author_id, text=text.strip())
    stimuli["posts"].append(created)
    for original, new_id in zip(source_comments, new_ids):
        row = copy.deepcopy(original)
        row.update(id=new_id, post_id=post_id)
        stimuli["comments"].append(row)


def set_condition_posts(config, condition_id, post_ids):
    if not post_ids or not set(post_ids) <= {p["id"] for p in config["stimuli"]["posts"]}:
        raise ValueError("每个组合至少选择一个有效帖子")
    condition = next(c for c in config["conditions"] if c["id"] == condition_id)
    comments = config["stimuli"]["comments"]
    selected_ids = {c["id"] for c in comments if c["post_id"] in post_ids}
    layout = [r for r in condition["comment_layout"] if r["comment_id"] in selected_ids]
    present = {r["comment_id"] for r in layout}
    targets = [cid for cid in condition["required_exposure_comment_ids"] if cid in selected_ids]
    for pid in post_ids:
        rows = [c for c in comments if c["post_id"] == pid]
        if not any(c["id"] in present for c in rows):
            layout.extend({"comment_id": c["id"], "parent_id": None, "sibling_order": i + 1} for i, c in enumerate(rows))
            marked = [c["id"] for c in rows if c.get("research_role") == "counter_speech"]
            targets.extend(marked)
    condition.update(post_order=list(post_ids), comment_layout=layout, required_exposure_comment_ids=targets)


def add_condition(config, condition_id, label, source_id):
    condition_id = condition_id.strip()
    if not condition_id or any(c["id"] == condition_id for c in config["conditions"]):
        raise ValueError("条件 ID 不能为空或重复")
    row = copy.deepcopy(next(c for c in config["conditions"] if c["id"] == source_id))
    row.update(id=condition_id, label=label.strip() or condition_id)
    config["conditions"].append(row)


def parse_options(text):
    # A multiline option can contain a comma; a one-line numeric list is also accepted.
    return [s.strip() for s in (text.splitlines() if "\n" in text else re.split(r"[,，]", text)) if s.strip()]


def put_question(config, stage, block_id, question, position, original_id=None):
    blocks = config["flow"][stage]["blocks"]
    if not any(b["id"] == block_id for b in blocks):
        raise ValueError("请选择有效题块")
    existing = {q["id"] for s in ("pre", "post") for b in config["flow"][s]["blocks"] for q in b["questions"]}
    if not question["id"].strip() or question["id"] in existing and question["id"] != original_id:
        raise ValueError("题目 ID 不能为空或重复")
    target = next(b for b in blocks if b["id"] == block_id)
    maximum = len(target["questions"]) + (0 if any(q["id"] == original_id for q in target["questions"]) else 1)
    if type(position) is not int or not 1 <= position <= maximum:
        raise ValueError(f"插入位置应为 1 到 {maximum}")
    for block in blocks:
        block["questions"] = [q for q in block["questions"] if q["id"] != original_id]
    target["questions"].insert(position - 1, copy.deepcopy(question))
