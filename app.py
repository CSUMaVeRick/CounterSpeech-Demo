import streamlit as st

from counterspeech.experiment import load_config
from counterspeech.participant_ui import configured_path, run

st.set_page_config(page_title="在线研究", layout="wide", initial_sidebar_state="collapsed")
try:
    config = load_config(configured_path())
except (OSError, ValueError, KeyError, TypeError) as error:
    st.error(f"实验配置无法加载：{error}")
    st.stop()

if config.get("review_only"):
    st.info("新一轮实验材料正在审阅，参与者入口暂未开放。")
    st.stop()

# Formal allocation is server-side; URL parameters cannot select a condition.
run(config, mode="live")
