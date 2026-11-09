"""Password-protected, read-only researcher page; run separately from recruitment."""
import hashlib
import hmac
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone

import streamlit as st

from counterspeech import ROOT
from counterspeech.records import list_records, record_detail

PHASES = {"": "全部", "pre": "前测填写中", "interaction": "交互中", "post": "后测填写中", "submitted": "已提交", "legacy_complete": "旧版交互完成", "legacy_interaction": "旧版交互中"}
DATABASES = {"正式回收": "responses.sqlite3", "固定条件演示": "demo.sqlite3", "管理预览": "admin-preview.sqlite3"}
EVENTS = {"session_start": "进入会话", "pre_submit": "确认前测", "post_open": "打开帖子／评论", "post_leave": "离开帖子／评论", "like": "点赞状态变化", "dislike": "点踩状态变化", "post_read": "帖子阅读确认", "comment": "提交评论／回复", "exposure_met": "达到展示门槛", "exposure_interval": "可见区间", "complete": "完成交互", "post_submit": "提交后测"}


def local_time(value):
    if not value:
        return "暂无事件"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return str(value)


def event_status(event):
    if event["type"] == "like":
        return str(event.get("liked", ""))
    if event["type"] == "dislike":
        return str(event.get("disliked", ""))
    if event["type"] == "post_read":
        return "已勾选" if event["checked"] else "已取消"
    return f"{event['duration_ms']:.0f} ms" if "duration_ms" in event else ""


def answer_rows(config, state, stage):
    bank = {q["id"]: q for b in config.get("flow", {}).get(stage, {}).get("blocks", []) for q in b["questions"]}
    answers = state.get(stage + "_answers", {})
    order = state.get("question_order", {}).get(stage, list(bank))
    return [{"题目 ID": key, "题干": bank.get(key, {}).get("label", key), "回答": json.dumps(answers[key], ensure_ascii=False) if key in answers else "未回答"} for key in order]


st.set_page_config(page_title="数据回收", layout="wide")
st.title("数据回收")
password = os.environ.get("RESEARCHER_PASSWORD", "")
if not password:
    st.error("尚未设置研究者访问密码。请先设置服务进程的 RESEARCHER_PASSWORD 环境变量，再启动此页面。")
    st.stop()
fingerprint = hashlib.sha256(password.encode()).hexdigest()
if st.session_state.get("researcher_authenticated") != fingerprint:
    with st.form("researcher-login"):
        entered = st.text_input("研究者访问密码", type="password")
        if st.form_submit_button("登录"):
            if hmac.compare_digest(entered.encode(), password.encode()):
                st.session_state.researcher_authenticated = fingerprint
                st.rerun()
            else:
                st.error("密码不正确")
    st.stop()

left, right = st.columns([5, 1])
left.caption("每条记录是一个会话；点开摘要查看详情。页面只读，不修改数据库。时间显示为北京时间。")
if right.button("退出登录"):
    del st.session_state.researcher_authenticated
    st.rerun()
source = st.selectbox("数据来源", list(DATABASES))
path = ROOT / "data" / DATABASES[source]
if st.button("刷新数据"):
    st.rerun()
if not path.exists():
    st.info("该来源暂未产生数据库。首次会话创建后即可查看。")
    st.stop()

f1, f2, f3 = st.columns(3)
phase = f1.selectbox("完成状态", list(PHASES), format_func=PHASES.__getitem__)
condition = f2.text_input("条件 ID（留空看全部）").strip()
search = f3.text_input("搜索完成码或记录 ID").strip()
size = st.selectbox("每页条数", [20, 50])
filter_key = (source, phase, condition, search, size)
if st.session_state.get("record_filters") != filter_key:
    st.session_state.record_filters = filter_key
    st.session_state.record_page = 1
page = st.number_input("页码", min_value=1, step=1, key="record_page")
try:
    data = list_records(path, phase=phase, condition=condition, search=search, page=page, page_size=size)
except (sqlite3.Error, ValueError, OSError) as error:
    st.error(f"数据库读取失败：{error}")
    st.stop()
m1, m2, m3, m4 = st.columns(4)
m1.metric("会话总数", data["total"])
m2.metric("已提交", data["submitted"])
m3.metric("未提交", data["total"] - data["submitted"])
m4.metric("筛选结果", data["filtered"])
st.caption(f"第 {page} 页，共 {max(1, (data['filtered'] + size - 1) // size)} 页。“未提交”可能仍在填写，不直接判断为退出；旧版交互完成也不等同于已提交后测。")
if not data["rows"]:
    st.info("本页没有记录。可调整筛选或返回第一页。")

for row in data["rows"]:
    summary = f"{row['id'][:12]} · {PHASES.get(row['phase'], row['phase'])} · {row['condition_id']} · 完成码 {row['completion_code'] or '—'} · {row['event_count']} 条事件"
    with st.expander(summary, expanded=False):
        st.caption(f"首次事件：{local_time(row['first_received'])} ｜ 最近事件：{local_time(row['last_received'])} ｜ 配置版本：{row['config_version']}")
        try:
            detail = record_detail(path, row["id"])
        except (sqlite3.Error, ValueError, OSError) as error:
            st.error(f"详情无法读取：{error}")
            continue
        config, state, events = detail["config"], detail["state"], detail["events"]
        answers, timeline, materials, raw = st.tabs(["前后测回答", "行为时间线", "实际展示材料", "原始记录"])
        with answers:
            st.subheader("前测")
            st.dataframe(answer_rows(config, state, "pre"), width="stretch", hide_index=True)
            st.subheader("后测")
            st.dataframe(answer_rows(config, state, "post"), width="stretch", hide_index=True)
            st.write("实际题序", state.get("question_order", {}))
        with timeline:
            st.dataframe([{"服务端时间": local_time(e["received_at"]), "行为": EVENTS.get(e["type"], e["type"]), "对象": e.get("target") or "", "状态／时长": event_status(e), "提交文本": e.get("text", "")} for e in events], width="stretch", hide_index=True)
            st.write("最终点赞状态", state.get("likes", {}))
            st.write("已提交评论", state.get("comments", []))
            st.write("已达展示要求的目标", state.get("exposed", []))
        with materials:
            if state.get("phase") == "pre":
                st.info("此会话尚未进入交互。下方是保存的材料模板，变量尚未解析，不代表已展示给被试。")
            st.write("变量最终取值", state.get("resolved_variables", {}))
            st.json(config["stimuli"])
            st.write("原始模板", state.get("template_texts", {}))
        with raw:
            st.json({"state": state, "config": config, "events": events})
