"""Question order, response validation, and registered text variables."""
import copy
import json
import re
import secrets
from functools import lru_cache

from . import ROOT

PLACEHOLDER = re.compile(r"\{([^{}]+)\}")
QUESTION_TYPES = {"text", "single_choice", "multiple_choice", "number", "location"}


def place_display_name(name):
    special = {"内蒙古自治区": "内蒙古", "广西壮族自治区": "广西", "西藏自治区": "西藏", "宁夏回族自治区": "宁夏", "新疆维吾尔自治区": "新疆", "香港特别行政区": "香港", "澳门特别行政区": "澳门"}
    return special.get(name, re.sub(r"[省市]$", "", name))


def profile_location_mode(author):
    if "location_mode" in author:
        return author["location_mode"]
    value = author.get("location", "")
    return "answer" if value in {"province", "city", "district"} else "template" if "{" in value else "literal"


def answer_text(values, field):
    value = values.get(field)
    if value is None:
        return None
    if isinstance(value, list):
        return "、".join(value)
    if isinstance(value, str) and field in {"province", "city"}:
        return place_display_name(value)
    return str(value)


@lru_cache(maxsize=1)
def regions():
    return json.loads((ROOT / "assets/regions.json").read_text(encoding="utf-8"))


def questions(config, stage):
    return [q for block in config["flow"][stage]["blocks"] for q in block["questions"]]


def validate_study(config):
    variables = config.get("variables", [])
    names = [v["name"] for v in variables]
    if len(names) != len(set(names)) or any(not re.fullmatch(r"[\w\u4e00-\u9fff]+", name) for name in names):
        raise ValueError("变量名重复或含不支持的符号")
    if "flow" not in config:
        if names or any(profile_location_mode(a) != "literal" for a in config["stimuli"]["authors"]):
            raise ValueError("注册变量或动态属地需要配置前测与后测")
        return
    ids, block_ids = set(), set()
    for stage in ("pre", "post"):
        section = config["flow"][stage]
        if section["block_order"] not in {"fixed", "random"}:
            raise ValueError("题块顺序须为 fixed 或 random")
        for block in section["blocks"]:
            if not block["id"] or block["id"] in block_ids or block["question_order"] not in {"fixed", "random"}:
                raise ValueError("题块 ID 重复、为空或顺序无效")
            block_ids.add(block["id"])
            for q in block["questions"]:
                if not q["id"] or q["id"] in ids or not isinstance(q["label"], str) or not q["label"].strip():
                    raise ValueError("题目 ID 重复／为空，或题干为空")
                if q["id"] in {"province", "city", "district", "province_code", "city_code", "district_code"}:
                    raise ValueError("题目 ID 不能使用地理信息的保留字段名")
                ids.add(q["id"])
                if q["type"] not in QUESTION_TYPES or type(q["required"]) is not bool:
                    raise ValueError("无效题型或必答设置")
                if q["type"] in {"single_choice", "multiple_choice"}:
                    opts = q.get("options", [])
                    if not opts or any(not isinstance(o, str) or not o.strip() for o in opts) or len(set(opts)) != len(opts):
                        raise ValueError("选择题选项不能为空或重复")
                if q["type"] == "number" and q.get("min", 0) > q.get("max", 100):
                    raise ValueError("数字题上下限无效")
                if q["type"] == "text" and (type(q.get("max_length", 1000)) is not int or q.get("max_length", 1000) <= 0):
                    raise ValueError("文本题字数限制无效")
                if q["type"] == "location" and stage != "pre":
                    raise ValueError("省市区题应放在前测")
    pre = questions(config, "pre")
    if sum(q["type"] == "location" for q in pre) > 1:
        raise ValueError("当前每份前测最多设置一个省市区题")
    fields = {q["id"] for q in pre if q["type"] != "location"} | {"province", "city", "district"}
    has_location = any(q["type"] == "location" for q in pre)

    def check_answer_source(field):
        if field not in fields or field in {"province", "city", "district"} and not has_location:
            raise ValueError("变量或属地引用的前测字段不存在")
        dependency = next((q for q in pre if q["id"] == field or field in {"province", "city", "district"} and q["type"] == "location"), None)
        if dependency and not dependency["required"]:
            raise ValueError("变量或属地依赖的前测题须设为必答")

    for author in config["stimuli"]["authors"]:
        mode, value = profile_location_mode(author), author.get("location", "")
        if mode == "answer":
            check_answer_source(value)
        elif mode == "variable":
            if value not in names:
                raise ValueError("用户属地引用了未注册变量")
        elif mode == "template":
            remainder = PLACEHOLDER.sub("", value)
            if "{" in remainder or "}" in remainder:
                raise ValueError("IP 属地模板的占位符格式不完整，请使用 {province} 这样的格式")
            for field in PLACEHOLDER.findall(value):
                if field not in names:
                    check_answer_source(field)
        elif mode != "literal":
            raise ValueError("未知 IP 属地显示方式")
    for condition in config["conditions"]:
        rules = condition.get("variable_rules", {})
        if set(rules) != set(names):
            raise ValueError("每个条件须给所有注册变量配置规则")
        for rule in rules.values():
            kind, value = rule["kind"], rule["value"]
            if not isinstance(value, str) or not value.strip():
                raise ValueError("变量规则值不能为空")
            if kind == "answer":
                check_answer_source(value)
            elif kind in {"other_province", "other_district"}:
                if not has_location:
                    raise ValueError("地理对照规则需要省市区题")
                if not next(q for q in pre if q["type"] == "location")["required"]:
                    raise ValueError("地理对照规则需要必答的省市区题")
                codes = {p["code"] for p in regions()} if kind == "other_province" else {d["code"] for p in regions() for c in p["children"] for d in c["children"]}
                if not set(value.split(",")) <= codes:
                    raise ValueError("对照地点代码无效（多个代码以英文逗号连接）")
            elif kind != "literal":
                raise ValueError("未知变量规则")
    for row in config["stimuli"]["posts"] + config["stimuli"]["comments"]:
        texts = [row["text"], *row.get("text_by_strategy", {}).values()]
        if any(not set(PLACEHOLDER.findall(text)) <= set(names) for text in texts):
            raise ValueError("正文使用了未注册变量")


def question_order(config):
    result = {}
    for stage in ("pre", "post"):
        section = config["flow"][stage]
        blocks = copy.deepcopy(section["blocks"])
        if section["block_order"] == "random":
            secrets.SystemRandom().shuffle(blocks)
        result[stage] = []
        for block in blocks:
            qs = block["questions"]
            if block["question_order"] == "random":
                secrets.SystemRandom().shuffle(qs)
            result[stage].extend(q["id"] for q in qs)
    return result


def validate_answers(config, stage, answers):
    if not isinstance(answers, dict) or set(answers) - {q["id"] for q in questions(config, stage)}:
        raise ValueError("回答格式或题目 ID 无效")
    clean = {}
    for q in questions(config, stage):
        value = answers.get(q["id"])
        if value is None or value == "" or value == []:
            if q["required"]:
                raise ValueError(f"请完成：{q['label']}")
            continue
        kind = q["type"]
        if kind == "text":
            if not isinstance(value, str) or not value.strip() or len(value) > q.get("max_length", 1000):
                raise ValueError("文本回答为空或超过字数限制")
            value = value.strip()
        elif kind == "single_choice":
            if value not in q["options"]:
                raise ValueError("选项无效")
        elif kind == "multiple_choice":
            if not isinstance(value, list) or any(not isinstance(v, str) for v in value) or len(value) != len(set(value)) or not set(value) <= set(q["options"]):
                raise ValueError("多选回答无效")
        elif kind == "number":
            if type(value) not in {int, float} or not q.get("min", 0) <= value <= q.get("max", 100):
                raise ValueError("数字回答超出范围")
        elif kind == "location":
            matches = [(p, c, d) for p in regions() for c in p["children"] for d in c["children"] if d["code"] == value]
            if len(matches) != 1:
                raise ValueError("请选择有效的省市区")
            p, c, d = matches[0]
            value = {"province": p["name"], "province_code": p["code"], "city": c["name"], "city_code": c["code"], "district": d["name"], "district_code": d["code"]}
        clean[q["id"]] = value
    return clean


def resolve(config, answers):
    values = dict(answers)
    for q in questions(config, "pre"):
        if q["type"] == "location" and q["id"] in answers:
            values.update(answers[q["id"]])
    result = {}
    for name, rule in config["conditions"][0].get("variable_rules", {}).items():
        kind, value = rule["kind"], rule["value"]
        if kind == "literal":
            resolved = value
        elif kind == "answer":
            resolved = answer_text(values, value)
        else:
            resolved = None
            for code in value.split(","):
                if kind == "other_province":
                    found = next((p["name"] for p in regions() if p["code"] == code and code != values.get("province_code")), None)
                else:
                    found = next((d["name"] for p in regions() for c in p["children"] for d in c["children"] if d["code"] == code and code != values.get("district_code") and d["name"] != values.get("district")), None)
                if found:
                    resolved = found
                    break
        if resolved is None or resolved == "":
            raise ValueError(f"变量 {name} 无法解析，请检查必答字段和对照地点的备用规则")
        if kind == "other_province" and resolved:
            resolved = place_display_name(resolved)
        result[name] = str(resolved)
    rendered = copy.deepcopy(config)
    templates = {}
    context = {key: answer_text(values, key) for key in values}
    context.update(result)
    for author in rendered["stimuli"]["authors"]:
        mode, value = profile_location_mode(author), author.get("location", "")
        if mode == "literal":
            continue
        if mode == "answer":
            location = answer_text(values, value)
        elif mode == "variable":
            location = result.get(value)
        else:
            refs = PLACEHOLDER.findall(value)
            if any(context.get(ref) in {None, ""} for ref in refs):
                raise ValueError("IP 属地模板依赖的回答缺失")
            location = PLACEHOLDER.sub(lambda m: context[m.group(1)], value)
        if location is None or location == "":
            raise ValueError("IP 属地无法解析，请检查前测和变量设置")
        templates["author:" + author["id"] + ":location"] = {"mode": mode, "value": value}
        author.update(location=location, location_mode="literal")
    for row in rendered["stimuli"]["posts"] + rendered["stimuli"]["comments"]:
        templates[row["id"]] = row["text"]
        row["text"] = PLACEHOLDER.sub(lambda m: result[m.group(1)], row["text"])
    return rendered, result, templates
