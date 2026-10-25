import os
import sqlite3
from pathlib import Path

import streamlit as st

from experiment import exchange, load_config, public_config
from social_ui import component

ROOT = Path(__file__).parent


def configured_path():
    draft = ROOT / "data/study.draft.json"
    release = ROOT / "configs/study.json"
    return os.environ.get("EXPERIMENT_CONFIG", draft if draft.exists() else release if release.exists() else ROOT / "docs/study.example.json")


def run(config, *, mode, condition_id=None):
    st.markdown("""<style>
    [data-testid="stHeader"] {display:none}
    .block-container {padding:0!important;max-width:none!important}
    </style>""", unsafe_allow_html=True)
    entry_key = f"{mode}-{config['experiment_id']}" + (f"-{condition_id}-{config['config_version']}" if mode == "demo" else "")
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
