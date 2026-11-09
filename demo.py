import streamlit as st

from counterspeech.experiment import load_config
from counterspeech.participant_ui import configured_path, preview_config, run


def review_condition(conditions, feedback_levels, labels, fixed):
    pairs = {(row["counter_strategy"], row["counter_feedback"]): row["id"] for row in conditions
             if "counter_strategy" in row and "counter_feedback" in row}
    if len(pairs) != len(conditions):
        options = list(labels)
        label = "反驳方式" if any("counter_strategy" in row for row in conditions) else "选择场景"
        return st.radio(label, options, index=options.index(fixed) if fixed in labels else 0,
                        format_func=labels.__getitem__, horizontal=True, key="review-condition")

    current = next((row for row in conditions if row["id"] == fixed), conditions[0])
    strategy_labels = {row["counter_strategy"]: row.get("label", row["counter_strategy"]) for row in conditions}
    strategies = list(strategy_labels)
    strategy_column, feedback_column = st.columns(2)
    strategy = strategy_column.radio("反驳方式", strategies, index=strategies.index(current["counter_strategy"]),
                                     format_func=strategy_labels.__getitem__, horizontal=True, key="review-strategy")
    feedback_options = [level for level in feedback_levels if (strategy, level) in pairs]
    current_feedback = current["counter_feedback"]
    feedback = feedback_column.radio("赞踩反馈", feedback_options,
                                     index=feedback_options.index(current_feedback) if current_feedback in feedback_options else 0,
                                     format_func=lambda level: feedback_levels[level]["label"], horizontal=True, key="review-feedback")
    return pairs[strategy, feedback]


st.set_page_config(page_title="固定条件演示", layout="wide", initial_sidebar_state="collapsed")
try:
    config = load_config(configured_path())
except (OSError, ValueError, KeyError, TypeError) as error:
    st.error(f"配置无法加载：{error}")
    st.stop()

conditions = config["conditions"]
feedback_levels = config.get("counter_feedback_levels", {})
labels = {}
for condition in conditions:
    label = condition.get("label", condition["id"])
    if "counter_feedback" in condition:
        label += " · " + feedback_levels[condition["counter_feedback"]]["label"]
    labels[condition["id"]] = label
fixed = st.query_params.get("condition")
if config.get("review_only"):
    selected = next(iter(labels)) if len(labels) == 1 else review_condition(conditions, feedback_levels, labels, fixed)
    if len(labels) > 1 and fixed != selected:
        st.query_params["condition"] = selected
    run(preview_config(config), mode="demo", condition_id=selected)
    st.stop()

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
