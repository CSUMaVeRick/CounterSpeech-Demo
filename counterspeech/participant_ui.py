import hashlib
import json
import os
import sqlite3

import streamlit as st

from . import ROOT
from .experiment import exchange, public_config
from .social_ui import component


def configured_path():
    draft = ROOT / "data/study.draft.json"
    release = ROOT / "configs/study.json"
    return os.environ.get("EXPERIMENT_CONFIG", draft if draft.exists() else release if release.exists() else ROOT / "configs/examples/study.example.json")


def preview_config(config):
    has_questions = any(section["blocks"] for section in config.get("flow", {}).values())
    if config.get("review_only") and not has_questions and not config["environment"].get("show_completion_data"):
        return {key: value for key, value in config.items() if key != "flow"}
    return config


def run(config, *, mode, condition_id=None):
    st.markdown("""<style>
    [data-testid="stHeader"] {display:none}
    .block-container {padding:0!important;max-width:none!important}
    </style>""", unsafe_allow_html=True)
    entry_key = f"{mode}-{config['experiment_id']}" + (f"-{condition_id}-{config['config_version']}" if mode == "demo" else "")
    if mode == "demo" and config.get("review_only"):
        material = json.dumps(config, sort_keys=True, ensure_ascii=False).encode("utf-8")
        entry_key += "-" + hashlib.sha256(material).hexdigest()[:16]
    reply_key = "reply-" + entry_key
    reply = st.session_state.get(reply_key, {"config": config, "state": None, "ack": []})
    try:
        payload = {**reply, "config": public_config(reply["config"]), "entry_key": entry_key}
        result = component()(data=payload, key=entry_key, on_packet_change=lambda: None)
        if result.packet:
            try:
                updated = exchange(ROOT / f"data/{'responses' if mode == 'live' else 'demo'}.sqlite3", config, result.packet, mode=mode, condition_id=condition_id)
            except ValueError as error:
                updated = {**reply, "rejected": [error.event_id] if error.event_id else [], "error": str(error)}
            if updated != st.session_state.get(reply_key):
                st.session_state[reply_key] = updated
                st.rerun()
            if updated.get("error"):
                st.error(updated["error"])
    except (sqlite3.Error, ValueError, KeyError, TypeError, OSError) as error:
        st.error(f"无法载入或保存：{error}。请重试，不要清除浏览器数据。")
