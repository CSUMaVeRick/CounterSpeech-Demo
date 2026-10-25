import streamlit as st

from experiment import load_config
from participant_ui import configured_path, run

st.set_page_config(page_title="在线研究", layout="wide", initial_sidebar_state="collapsed")
try:
    config = load_config(configured_path())
except (OSError, ValueError, KeyError, TypeError) as error:
    st.error(f"实验配置无法加载：{error}")
    st.stop()

# Formal allocation is server-side; URL parameters cannot select a condition.
run(config, mode="live")
