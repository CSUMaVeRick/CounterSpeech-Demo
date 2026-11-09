"""Visual editors for the study's JSON sections."""
import copy

import streamlit as st

from .experiment import validate
from .management import add_condition, parse_options, put_question, set_condition_posts


def variables_editor(config):
    st.caption("变量名用于正文中的 {变量名}，用途说明只给研究者看。变量只替换纯文本，不执行表达式；每个条件单独配置取值规则。")
    with st.form("variables"):
        rows = st.data_editor(config.get("variables") or [{"name": "", "label": ""}], num_rows="dynamic", column_config={"name": "变量名", "label": "用途说明"}, width="stretch", key="variables-table")
        if st.form_submit_button("应用变量注册"):
            config["variables"] = [r for r in rows if r.get("name", "").strip()]
            st.rerun()


def conditions_editor(config):
    ids = [c["id"] for c in config["conditions"]]
    selected = st.selectbox("编辑条件组合", ids)
    condition = next(c for c in config["conditions"] if c["id"] == selected)
    st.caption("每个条件组合包含展示帖子、评论树和变量规则。正式入口对组合等概率随机分配。answer 引用前测题目 ID 或 province/city/district；literal 为固定文本；other_province 填候选省级代码（如 31,44），按顺序选第一个不同地点。")
    with st.form("condition-rules-" + selected):
        label = st.text_input("条件说明", condition.get("label", selected))
        posts = st.multiselect("本组合显示的帖子（按所选顺序）", [p["id"] for p in config["stimuli"]["posts"]], default=condition["post_order"])
        rows = [{"name": v["name"], **condition.get("variable_rules", {}).get(v["name"], {"kind": "literal", "value": ""})} for v in config.get("variables", [])]
        rules = st.data_editor(rows, disabled=["name"], column_config={"name": "变量名", "kind": st.column_config.SelectboxColumn("取值方式", options=["answer", "literal", "other_province", "other_district"]), "value": st.column_config.TextColumn("来源字段／固定文本／候选代码")}, width="stretch", key="rules-" + selected) if rows else []
        if st.form_submit_button("应用条件规则"):
            candidate = copy.deepcopy(config)
            try:
                set_condition_posts(candidate, selected, posts)
                updated = next(c for c in candidate["conditions"] if c["id"] == selected)
                updated["label"] = label
                updated["variable_rules"] = {r["name"]: {"kind": r["kind"], "value": r["value"].strip()} for r in rules}
                config.clear()
                config.update(candidate)
                st.rerun()
            except (ValueError, TypeError) as error:
                st.error(str(error))
    with st.expander("新增条件组合"):
        st.caption("以当前组合为起点创建独立组合，可再修改帖子、评论树和变量规则。")
        with st.form("add-condition", clear_on_submit=True):
            new_id = st.text_input("新条件 ID")
            new_label = st.text_input("新条件说明")
            if st.form_submit_button("新增条件组合"):
                try:
                    add_condition(config, new_id, new_label, selected)
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))


def questionnaire_editor(config):
    stage = st.selectbox("问卷阶段", ["pre", "post"], format_func={"pre": "前测", "post": "后测"}.__getitem__)
    section = config.setdefault("flow", {}).setdefault(stage, {"block_order": "fixed", "blocks": []})
    with st.expander("题目和题块字段说明"):
        st.markdown("""
| 字段 | 含义 |
| --- | --- |
| 题目 ID | 回答数据中的唯一标识，如 post_q01；与题干不同，不随措辞修改而变更。 |
| 题目内容 | 被试实际看到的题干。 |
| 题型 | 文本、单选、多选、数字，或前测专用的省市区联动。 |
| 必答 | 勾选后须作答才能继续。变量所依赖的前测题应设为必答。 |
| 选项 | 每行一个；也接受单行的 1,2,3 或中文逗号列表。 |
| 数字范围／字数上限 | 只对相应题型生效，其他题型不需要填写。 |
| 所属题块 | 逻辑分组；可分别设置块之间、块内部的固定或随机顺序。 |
| 插入位置／顺序 | 从 1 开始。随机显示时，这仍是配置中的基准顺序。 |

新增题目用下面的表单，不需要在表格空行里手填内部引用字段。
""")
    with st.expander("题块与显示顺序"):
        with st.form("block-order-" + stage):
            order = st.selectbox("题块之间的顺序", ["fixed", "random"], index=["fixed", "random"].index(section["block_order"]), format_func={"fixed": "固定", "random": "随机"}.__getitem__)
            block_rows = [{"id": b["id"], "order": i + 1, "question_order": b["question_order"]} for i, b in enumerate(section["blocks"])]
            changed = st.data_editor(block_rows, disabled=["id"], column_config={"id": "题块 ID", "order": st.column_config.NumberColumn("题块顺序", min_value=1, step=1, required=True), "question_order": st.column_config.SelectboxColumn("块内题序", options=["fixed", "random"], required=True)}, width="stretch", key="blocks-" + stage) if block_rows else []
            if st.form_submit_button("应用题块顺序"):
                try:
                    if len({r["order"] for r in changed}) != len(changed) or any(type(r["order"]) is not int or r["order"] < 1 for r in changed):
                        raise ValueError("题块顺序须为不重复的正整数")
                    by_id = {b["id"]: b for b in section["blocks"]}
                    section["blocks"] = [{**by_id[r["id"]], "question_order": r["question_order"]} for r in sorted(changed, key=lambda r: r["order"])]
                    section["block_order"] = order
                    st.rerun()
                except (TypeError, ValueError) as error:
                    st.error(str(error))
        with st.form("new-block-" + stage, clear_on_submit=True):
            block_id = st.text_input("新题块 ID")
            if st.form_submit_button("新增题块"):
                all_ids = {b["id"] for s in config["flow"].values() for b in s["blocks"]}
                if not block_id.strip() or block_id.strip() in all_ids:
                    st.error("题块 ID 不能为空或重复")
                else:
                    section["blocks"].append({"id": block_id.strip(), "question_order": "fixed", "questions": []})
                    st.rerun()
    if not section["blocks"]:
        st.info("请先在“题块与显示顺序”中新增题块。")
        return
    bank = {q["id"]: q for b in section["blocks"] for q in b["questions"]}
    labels = {"": "新增题目", **{key: key + " · " + q["label"] for key, q in bank.items()}}
    selected = st.selectbox("选择题目", list(labels), format_func=labels.__getitem__, key="question-select-" + stage)
    original = bank.get(selected)
    generation = st.session_state.get("question-generation-" + stage, 0)
    scope = f"{stage}-{selected or 'new'}-{generation}"
    types = {"text": "文本题", "single_choice": "单选题", "multiple_choice": "多选题", "number": "数字题", "location": "省市区联动（前测）"}
    allowed_types = list(types) if stage == "pre" else [kind for kind in types if kind != "location"]
    qtype = st.selectbox("题型", allowed_types, index=allowed_types.index(original["type"]) if original else 0, format_func=types.__getitem__, key="question-type-" + scope)
    current_block = next((b["id"] for b in section["blocks"] if any(q["id"] == selected for q in b["questions"])), section["blocks"][0]["id"])
    with st.form("question-" + scope):
        all_question_ids = {q["id"] for s in config["flow"].values() for b in s["blocks"] for q in b["questions"]}
        suffix = 1
        while f"{stage}_q{suffix:02d}" in all_question_ids:
            suffix += 1
        qid = st.text_input("题目 ID", value=selected or f"{stage}_q{suffix:02d}", disabled=bool(selected))
        title = st.text_area("题目内容", value=original["label"] if original else "")
        block_id = st.selectbox("所属题块", [b["id"] for b in section["blocks"]], index=[b["id"] for b in section["blocks"]].index(current_block))
        members = next(b["questions"] for b in section["blocks"] if b["id"] == current_block)
        position = st.number_input("插入位置", min_value=1, value=next((i + 1 for i, q in enumerate(members) if q["id"] == selected), len(members) + 1), step=1)
        required = st.checkbox("必答", value=original["required"] if original else True)
        question = {"id": qid.strip(), "label": title, "type": qtype, "required": required}
        if qtype in {"single_choice", "multiple_choice"}:
            options = st.text_area("选项（每行一个，或用逗号分隔）", value="\n".join(original.get("options", [])) if original else "", height=140)
            question["options"] = parse_options(options)
        elif qtype == "text":
            question["max_length"] = st.number_input("字数上限", min_value=1, value=original.get("max_length", 1000) if original else 1000, step=1)
        elif qtype == "number":
            question["min"] = st.number_input("最小值", value=float(original.get("min", 0)) if original else 0.0)
            question["max"] = st.number_input("最大值", value=float(original.get("max", 100)) if original else 100.0)
        if st.form_submit_button("保存题目" if selected else "新增题目"):
            candidate = copy.deepcopy(config)
            try:
                put_question(candidate, stage, block_id, question, position, selected or None)
                validate(candidate)
                config.clear()
                config.update(candidate)
                st.session_state["question-generation-" + stage] = generation + 1
                st.rerun()
            except (TypeError, ValueError, KeyError) as error:
                st.error(str(error))
    st.caption("已配置题目（固定显示时按此顺序；随机显示时在会话创建时洗牌并锁定）：")
    for block in section["blocks"]:
        st.write("题块：" + block["id"])
        for i, q in enumerate(block["questions"]):
            st.write(f"{i + 1}. {q['id']} · {q['label']}（{types[q['type']]}）")
