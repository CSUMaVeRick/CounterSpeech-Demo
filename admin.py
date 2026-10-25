"""Local researcher editor. Run separately from the participant application."""
import copy
import hashlib
import json
import logging
import os
import sqlite3
from pathlib import Path

import streamlit as st

from experiment import exchange, load_config, public_config, save_draft, validate, write_working_draft
from social_ui import component
from participant_ui import configured_path
from study_admin import conditions_editor, questionnaire_editor, variables_editor
from management import add_author, add_post
from study import profile_location_mode

ROOT = Path(__file__).parent
DRAFT = ROOT / "data/study.draft.json"
WORKING = Path(os.environ.get("ADMIN_WORKING_CONFIG", ROOT / "data/admin.work.json"))
st.set_page_config(page_title="微博实验配置", layout="wide")
st.title("微博实验配置")
st.caption("新增／应用编辑后会自动保存工作草稿，刷新或重启不会丢失。校验并发布后才供演示和正式入口使用；预览使用当前工作草稿。")
if "config" not in st.session_state:
    try:
        st.session_state.config = json.loads(WORKING.read_text(encoding="utf-8")) if WORKING.exists() else load_config(configured_path())
    except (OSError, ValueError, KeyError, TypeError) as error:
        st.error(f"工作草稿无法读取，原文件未被覆盖：{error}")
        st.stop()
config = st.session_state.config
try:
    write_working_draft(WORKING, config)
except (OSError, TypeError) as error:
    st.error(f"工作草稿未能保存：{error}")
    st.stop()

version, save = st.columns([3, 1])
config["config_version"] = version.text_input("配置版本", config["config_version"])
if save.button("校验并发布配置", type="primary", width="stretch"):
    try:
        save_draft(DRAFT, config)
        st.session_state.saved_config = json.dumps(config, sort_keys=True, ensure_ascii=False)
    except (ValueError, KeyError, TypeError, OSError) as error:
        st.error(str(error))
if st.session_state.get("saved_config") == json.dumps(config, sort_keys=True, ensure_ascii=False):
    st.success("已保存。参与者应用中的新会话将使用此配置；已有参与者仍用原快照。")

profiles, posts, comments, environment, variables, questionnaires, combinations, preview = st.tabs(["发布者资料", "帖子", "评论与回复树", "浏览完成条件", "实验变量", "前后测题目", "条件组合", "预览"])
with variables:
    variables_editor(config)
with questionnaires:
    questionnaire_editor(config)
with combinations:
    conditions_editor(config)
with profiles:
    with st.expander("新增用户"):
        with st.form("new-author", clear_on_submit=True):
            new_author_id = st.text_input("新用户 ID", help="用于帖子和评论引用，不能与已有用户重复。")
            new_author_name = st.text_input("新用户昵称")
            new_avatar = st.selectbox("新用户头像", ["assets/avatars/" + name + "-192.jpg" for name in ("city", "cat", "dog", "mountain", "plant")])
            if st.form_submit_button("新增用户"):
                try:
                    add_author(config, new_author_id, new_author_name, new_avatar)
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
    authors = {a["id"]: a for a in config["stimuli"]["authors"]}
    author_labels = {key: f"{key} · {row['display_name']}" for key, row in authors.items()}
    aid = st.selectbox("选择用户", list(authors), format_func=author_labels.__getitem__, key="selected_author")
    original = authors[aid]
    location_modes = {"literal": "固定地名", "answer": "前测字段", "variable": "注册变量", "template": "文本模板"}
    original_mode = profile_location_mode(original)
    location_mode = st.selectbox("IP 属地显示方式", list(location_modes), index=list(location_modes).index(original_mode), format_func=location_modes.__getitem__, key="location-mode-" + aid)
    st.caption("这是模拟账户显示的属地，不采集真实网络 IP。选择“前测字段 → province”会显示被试前测省份；“注册变量”则随所分配条件的变量规则变化。")
    with st.form(f"profile-{aid}"):
        edited = copy.deepcopy(original)
        edited["display_name"] = st.text_input("昵称", original["display_name"])
        edited["avatar"] = st.text_input("头像路径", original.get("avatar", "assets/avatar-default.svg"))
        edited["bio"] = st.text_area("简介", original.get("bio", ""))
        edited["location_mode"] = location_mode
        if location_mode == "answer":
            sources = ["province", "city", "district"] + [q["id"] for b in config.get("flow", {}).get("pre", {}).get("blocks", []) for q in b["questions"] if q["type"] != "location"]
            edited["location"] = st.selectbox("属地来源字段", sources, index=sources.index(original.get("location")) if original.get("location") in sources else 0)
        elif location_mode == "variable":
            names = [v["name"] for v in config.get("variables", [])]
            edited["location"] = st.selectbox("属地变量", names, index=names.index(original.get("location")) if original.get("location") in names else 0) if names else ""
            if not names:
                st.info("请先在实验变量中注册一个变量。")
        else:
            edited["location"] = st.text_input("IP 属地模板" if location_mode == "template" else "IP 属地（固定地名）", original.get("location", "") if location_mode == original_mode else "", help="模板可写 {province} 或 {展示地名}；固定地名直接填上海等文字。")
        edited["verified"] = st.checkbox("已认证", original.get("verified", False))
        edited["verified_text"] = st.text_input("认证说明", original.get("verified_text", ""))
        left, right = st.columns(2)
        edited["followers"] = left.number_input("粉丝数", min_value=0, value=original.get("followers", 0), step=1)
        edited["following"] = right.number_input("关注数", min_value=0, value=original.get("following", 0), step=1)
        if st.form_submit_button("应用资料编辑"):
            if location_mode != "literal" and not edited["location"]:
                st.error("请选择属地来源或填写模板")
            else:
                original.update(edited)
                st.success("资料已应用到当前草稿。")

with posts:
    with st.expander("新增帖子"):
        st.caption("从现有帖子复制一份独立材料及其 10 条评论，之后可以分别编辑。创建后在“条件组合”中勾选，才会展示给被试；新加入组合的评论先按顶层排列，可继续修改回复树。")
        with st.form("new-post", clear_on_submit=True):
            new_post_id = st.text_input("新帖子 ID")
            post_source_id = st.selectbox("复制材料来源", [p["id"] for p in config["stimuli"]["posts"]])
            new_post_author = st.selectbox("新帖发布者", [a["id"] for a in config["stimuli"]["authors"]])
            new_post_text = st.text_area("新帖子正文")
            if st.form_submit_button("新增帖子"):
                try:
                    add_post(config, new_post_id, post_source_id, new_post_author, new_post_text)
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
    post_map = {p["id"]: p for p in config["stimuli"]["posts"]}
    pid = st.selectbox("选择帖子", list(post_map))
    original_post = post_map[pid]
    with st.form(f"post-{pid}"):
        edited_post = copy.deepcopy(original_post)
        edited_post["author_id"] = st.selectbox("发布者", list(authors), index=list(authors).index(original_post["author_id"]))
        edited_post["text"] = st.text_area("帖子正文", original_post["text"], height=140)
        edited_post["display_time"] = st.text_input("显示时间", original_post["display_time"])
        edited_post["age_minutes"] = st.number_input("帖子已发布时长（分钟）", min_value=0, value=original_post.get("age_minutes", 60), step=1, help="固定的模拟浏览时点。例如 60 表示原帖显示为 1 小时前；评论晚于原帖 5 分钟发布，则显示为 55 分钟前。设置后优先使用此时长，上方显示时间仅用于旧配置。")
        edited_post["source"] = st.text_input("发布来源", original_post.get("source", ""))
        edited_post["initial_likes"] = st.number_input("帖子初始赞数", min_value=0, value=original_post["initial_likes"], step=1)
        media = st.data_editor(original_post.get("media") or [{"src": "", "alt": ""}], num_rows="dynamic", width="stretch", key=f"media-{pid}")
        if st.form_submit_button("应用帖子编辑"):
            edited_post["media"] = [m for m in media if m.get("src", "").strip()]
            original_post.update(edited_post)
            st.success("帖子已应用到当前草稿。")
    st.caption("图片引用 assets 内文件；可在下方上传 JPG、PNG 或 WebP 后复制路径。")
    upload = st.file_uploader("上传头像或配图", type=["jpg", "jpeg", "png", "webp"])
    if upload and st.button("保存图片到 assets"):
        from io import BytesIO
        from PIL import Image

        content = upload.getvalue()
        try:
            if len(content) > 5 * 1024 * 1024:
                raise ValueError("图片不得超过 5MB")
            with Image.open(BytesIO(content)) as image:
                image.verify()
                suffix = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}.get(image.format)
            if not suffix:
                raise ValueError("仅支持 JPG、PNG、WebP")
            target = ROOT / "assets" / (hashlib.sha256(content).hexdigest() + suffix)
            target.write_bytes(content)
            st.code("assets/" + target.name, language=None)
        except (OSError, ValueError, Image.DecompressionBombError) as error:
            st.error(f"图片无法保存：{error}")

with comments:
    condition_ids = [c["id"] for c in config["conditions"]]
    condition_id = st.selectbox("实验条件", condition_ids)
    condition = next(c for c in config["conditions"] if c["id"] == condition_id)
    comment_map = {c["id"]: c for c in config["stimuli"]["comments"]}
    rows = [{"relative_time_minutes": 0, **comment_map[r["comment_id"]], "parent_id": r["parent_id"], "sibling_order": r["sibling_order"]} for r in condition["comment_layout"]]
    st.caption("评论 ID／帖子 ID 用于引用，不随文案变化。父评论留空表示顶层；同级顺序只控制同一父级下的排列，和时间、赞数互不影响。每帖 10 条，包含回复。")
    st.info("时间字段记录原帖发布后多少分钟：5 表示原帖发布 5 分钟后发出的评论。它不是真实时间戳；回复时间应不早于父评论，且不能晚于模拟浏览时点。研究角色 counter_speech 只给研究者看。")
    with st.form(f"comments-{condition_id}"):
        changed = st.data_editor(rows, disabled=["id", "post_id"], column_config={"relative_time_minutes": st.column_config.NumberColumn("晚于原帖（分钟）", min_value=0, step=1, required=True), "parent_id": st.column_config.TextColumn("父评论 ID"), "sibling_order": st.column_config.NumberColumn("同级顺序", min_value=1, step=1), "text": st.column_config.TextColumn("评论正文"), "author_id": st.column_config.SelectboxColumn("作者 ID", options=list(authors)), "initial_likes": st.column_config.NumberColumn("初始赞数", min_value=0, step=1), "research_role": st.column_config.TextColumn("研究角色")}, width="stretch", hide_index=True, key=f"comments-table-{condition_id}")
        targets = st.multiselect("必展示评论", [r["id"] for r in rows], default=condition["required_exposure_comment_ids"])
        if st.form_submit_button("应用评论编辑"):
            candidate = copy.deepcopy(config)
            candidate_comments = {c["id"]: c for c in candidate["stimuli"]["comments"]}
            candidate_condition = next(c for c in candidate["conditions"] if c["id"] == condition_id)
            candidate_condition["comment_layout"] = []
            for row in changed:
                candidate_comments[row["id"]].update({key: value for key, value in row.items() if key not in {"parent_id", "sibling_order"}})
                candidate_condition["comment_layout"].append({"comment_id": row["id"], "parent_id": row["parent_id"] or None, "sibling_order": row["sibling_order"]})
            candidate_condition["required_exposure_comment_ids"] = targets
            try:
                validate(candidate)
                st.session_state.config = candidate
                st.rerun()
            except (ValueError, KeyError, TypeError) as error:
                st.error(str(error))

with environment:
    st.info("浏览完成条件决定何时允许从微博交互进入后测。它不会置顶或移动评论，只检查“评论与回复树”中指定的必展示评论是否进入视野。每个指定目标都须达标。")
    st.caption("最低可见比例 0.5 表示至少一半正文在屏幕内；连续 2000 毫秒表示保持 2 秒。切换到后台、移出视野、打开遮挡弹窗会中断连续计时。已达标状态会保存。可见不等于认真阅读。")
    with st.form("exposure"):
        exp = config["environment"]["exposure"]
        fraction = st.number_input("最低可见比例", min_value=0.01, max_value=1.0, value=float(exp["minimum_visible_fraction"]), step=0.05)
        duration = st.number_input("连续可见时长（毫秒）", min_value=100, value=exp["continuous_visible_ms"], step=100)
        if st.form_submit_button("应用展示要求"):
            config["environment"]["theme"] = "weibo"
            exp.update(minimum_visible_fraction=fraction, continuous_visible_ms=duration)
            st.success("展示要求已应用。")

with preview:
    try:
        write_working_draft(WORKING, config)
    except (OSError, TypeError) as error:
        st.error(f"工作草稿未能保存：{error}")
        st.stop()
    st.caption("与参与者界面使用同一个组件。每次修改草稿后，预览从新会话开始；无需保存即可检查。")
    try:
        validate(config)
        preview_condition = st.selectbox("预览条件组合", [c["id"] for c in config["conditions"]])
        digest = hashlib.sha256((json.dumps(config, sort_keys=True, ensure_ascii=False) + preview_condition).encode()).hexdigest()[:16]
        if st.button("重新开始预览"):
            st.session_state.preview_round = st.session_state.get("preview_round", 0) + 1
        preview_id = digest + str(st.session_state.get("preview_round", 0))
        replies = st.session_state.setdefault("preview_replies", {})
        reply = replies.get(preview_id, {"config": config, "state": None, "ack": []})
        result = component()(data={**reply, "config": public_config(reply["config"]), "preview_id": preview_id}, key="preview-" + preview_id, on_packet_change=lambda: None)
        if result.packet:
            updated = exchange(ROOT / "data/admin-preview.sqlite3", config, result.packet, mode="preview", condition_id=preview_condition)
            if updated != replies.get(preview_id):
                replies[preview_id] = updated
                st.rerun()
        st.download_button("下载当前 JSON", json.dumps(config, ensure_ascii=False, indent=2), file_name="experiment.json", mime="application/json")
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error) as error:
        logging.getLogger(__name__).exception("Preview could not load")
        st.error(f"预览无法加载：{error}")
