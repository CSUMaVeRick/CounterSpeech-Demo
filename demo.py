import streamlit as st

from experiment import load_config
from participant_ui import configured_path, run

st.set_page_config(page_title="固定条件演示", layout="wide", initial_sidebar_state="collapsed")
try:
    config = load_config(configured_path())
except (OSError, ValueError, KeyError, TypeError) as error:
    st.error(f"配置无法加载：{error}")
    st.stop()

labels = {c["id"]: c.get("label", c["id"]) for c in config["conditions"]}
fixed = st.query_params.get("condition")
if not fixed:
    st.title("固定条件演示")
    st.caption("这里选择一个已配置的完整条件组合。演示数据不会进入正式被试数据库。")
    selected = st.selectbox("条件组合", list(labels), format_func=labels.__getitem__)
    if st.button("开始演示", type="primary"):
        st.query_params["condition"] = selected
        st.rerun()
    st.stop()

if fixed not in labels:
    st.error("该演示条件不存在，请返回入口选择已注册的条件。")
    st.stop()
st.caption("演示条件：" + labels[fixed])
if st.button("返回条件选择"):
    st.query_params.clear()
    st.rerun()
run(config, mode="demo", condition_id=fixed)
