import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from counterspeech.experiment import exchange, load_config, validate
from counterspeech.study import question_order, resolve, validate_answers

ROOT = Path(__file__).resolve().parents[1]


class StudyTest(unittest.TestCase):
    def setUp(self):
        self.config = load_config(ROOT / "configs/examples/study.example.json")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "study.sqlite3"
        self.token = "c" * 64

    def send(self, *events, mode="live", condition_id=None, config=None):
        return exchange(self.db, config or self.config, {"token": self.token, "events": list(events)}, mode=mode, condition_id=condition_id)

    def event(self, kind, **payload):
        return {"event_id": kind, "type": kind, **payload}

    def test_random_assignment_and_order_are_pinned(self):
        post = self.config["flow"]["post"]["blocks"][0]
        post["question_order"] = "random"
        post["questions"].append({"id": "extra_post", "type": "text", "label": "补充", "required": False})
        with patch("counterspeech.experiment.secrets.choice", return_value=next(c for c in self.config["conditions"] if c["id"] == "local_province")) as choose, patch("counterspeech.study.secrets.SystemRandom.shuffle", side_effect=lambda rows: rows.reverse()):
            first = self.send(condition_id="other_province")
        self.assertEqual(choose.call_count, 1)
        self.assertEqual(first["state"]["condition_id"], "local_province")
        self.assertEqual(first["state"]["question_order"]["post"], ["extra_post", "impression"])
        changed = copy.deepcopy(self.config)
        changed["conditions"].reverse()
        with patch("counterspeech.experiment.secrets.choice", side_effect=AssertionError("must not reassign")), patch("counterspeech.study.secrets.SystemRandom.shuffle", side_effect=AssertionError("must not reshuffle")):
            restored = self.send(mode="demo", condition_id="other_province", config=changed)
        self.assertEqual(restored, first)

    def test_whole_flow_and_duplicate_final_submission(self):
        self.send(mode="demo", condition_id="local_province")
        with self.assertRaises(ValueError):
            self.send(self.event("post_submit", answers={"impression": "too soon"}))
        pre = self.event("pre_submit", answers={"residence": "310101"})
        before = self.send(pre)
        self.assertEqual(before["state"]["phase"], "interaction")
        self.assertEqual(before["state"]["resolved_variables"]["展示地名"], "上海")
        self.assertEqual(before["state"]["pre_answers"]["residence"]["province"], "上海市")
        self.assertIn("来上海工作和旅游", before["config"]["stimuli"]["posts"][0]["text"])
        self.assertIn("{展示地名}", before["state"]["template_texts"]["p01"])
        self.assertEqual(self.send(pre), before)
        with self.assertRaises(ValueError):
            self.send({**pre, "event_id": "change"})
        with self.assertRaises(ValueError):
            self.send(self.event("complete"))
        self.send(self.event("exposure_met", target="c07", duration_ms=2200))
        self.assertEqual(self.send(self.event("complete"))["state"]["phase"], "post")
        final = self.event("post_submit", answers={"impression": "我的回答"})
        result = self.send(final)
        self.assertEqual(result["state"]["phase"], "submitted")
        self.assertEqual(self.send(final)["state"]["completion_code"], result["state"]["completion_code"])
        self.assertEqual(self.send()["state"]["post_answers"]["impression"], "我的回答")

    def test_completion_data_contains_only_this_submitted_session(self):
        self.config["environment"].update(show_completion_data=True, completion_mode="post_read")
        self.config["environment"]["enabled_actions"].append("dislike")
        pre = self.event("pre_submit", answers={"residence": "310101"})
        other_comment = self.event("comment", target="p01", text="另一个会话的留言")
        exchange(self.db, self.config, {"token": "d" * 64, "events": [pre, other_comment]},
                 mode="demo", condition_id="local_province")
        before = self.send(pre, mode="demo", condition_id="local_province")
        self.assertNotIn("completion_data", before)

        self.send(self.event("like", target="p01", liked=True),
                  {**self.event("like", target="c07", liked=True), "event_id": "like-reply"},
                  {**self.event("like", target="c07", liked=False), "event_id": "unlike-reply"},
                  self.event("dislike", target="c07", disliked=True),
                  self.event("comment", target="c07", text="本次会话的回复"))
        for post_id in before["config"]["conditions"][0]["post_order"]:
            self.send({**self.event("post_read", target=post_id, checked=True), "event_id": f"read-{post_id}"})
        self.assertNotIn("completion_data", self.send(self.event("complete")))
        final = self.event("post_submit", answers={"impression": "我的回答"})
        result = self.send(final)
        data = result["completion_data"]
        self.assertEqual(data["pre_answers"], result["state"]["pre_answers"])
        self.assertEqual(data["post_answers"], {"impression": "我的回答"})
        self.assertEqual(data["completion_code"], result["state"]["completion_code"])
        post = next(row for row in data["posts"] if row["post_id"] == "p01")
        self.assertTrue(post["read"])
        self.assertTrue(post["liked"])
        comment = next(row for row in post["comments"] if row["comment_id"] == "c07")
        self.assertFalse(comment["liked"])
        self.assertTrue(comment["disliked"])
        self.assertEqual(comment["submitted_replies"], [{"id": "comment", "text": "本次会话的回复"}])
        self.assertEqual([row["liked"] for row in data["interactions"] if row.get("target") == "c07" and row["type"] == "like"], [True, False])
        self.assertNotIn(other_comment["text"], json.dumps(data, ensure_ascii=False))
        self.assertEqual(self.send()["completion_data"], data)

    def test_fixed_demo_and_fallback_location(self):
        result = self.send(mode="demo", condition_id="other_province")
        self.assertEqual(result["state"]["mode"], "demo")
        result = self.send(self.event("pre_submit", answers={"residence": "310101"}))
        self.assertEqual(result["state"]["resolved_variables"]["展示地名"], "广东")
        with self.assertRaises(ValueError):
            exchange(Path(self.temp.name) / "invalid.sqlite3", self.config, {"token": "a" * 64}, mode="demo", condition_id="absent")

    def test_question_types_and_validation(self):
        config = copy.deepcopy(self.config)
        block = config["flow"]["post"]["blocks"][0]
        block["questions"] = [
            {"id": "single", "type": "single_choice", "label": "单选", "required": True, "options": ["是", "否"]},
            {"id": "multi", "type": "multiple_choice", "label": "多选", "required": True, "options": ["a", "b"]},
            {"id": "number", "type": "number", "label": "数字", "required": True, "min": 1, "max": 7},
            {"id": "text", "type": "text", "label": "文本", "required": False},
        ]
        validate(config)
        good = {"single": "是", "multi": ["a"], "number": 3}
        self.assertEqual(validate_answers(config, "post", good), good)
        for changes in ({"single": "不存在"}, {"multi": []}, {"multi": ["a", "a"]}, {"number": True}, {"number": 8}, {"extra": 1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_answers(config, "post", {**good, **changes})
        with self.assertRaises(ValueError):
            validate_answers(config, "pre", {"residence": "not-code"})

    def test_blocks_and_questions_shuffle_once(self):
        config = copy.deepcopy(self.config)
        pre = config["flow"]["pre"]
        pre["block_order"] = "random"
        pre["blocks"][0]["question_order"] = "random"
        pre["blocks"][0]["questions"].append({"id": "age", "type": "number", "label": "年龄", "required": False})
        pre["blocks"].append({"id": "another", "question_order": "fixed", "questions": [{"id": "extra", "label": "补充", "type": "text", "required": False}]})
        with patch("counterspeech.study.secrets.SystemRandom.shuffle", side_effect=lambda rows: rows.reverse()) as shuffle:
            order = question_order(config)
        self.assertEqual(shuffle.call_count, 2)
        self.assertEqual(order["pre"], ["extra", "age", "residence"])
        fixed = question_order(self.config)
        self.assertEqual(fixed["pre"], ["residence"])

    def test_unregistered_variable_and_missing_mapping_rejected(self):
        bad = copy.deepcopy(self.config)
        bad["stimuli"]["posts"][0]["text"] = "{未注册}"
        with self.assertRaises(ValueError):
            validate(bad)
        bad = copy.deepcopy(self.config)
        bad["conditions"][0]["variable_rules"] = {}
        with self.assertRaises(ValueError):
            validate(bad)

    def test_profile_location_sources_resolve_and_keep_original(self):
        config = copy.deepcopy(self.config)
        config["conditions"] = [next(c for c in config["conditions"] if c["id"] == "other_province")]
        authors = config["stimuli"]["authors"]
        authors[0]["location"] = "province"  # Existing configurations need no migration.
        authors[1].update(location_mode="variable", location="展示地名")
        authors[2].update(location_mode="literal", location="province")
        authors[3].update(location_mode="template", location="{province} · {展示地名}")
        validate(config)
        rendered, _, templates = resolve(config, validate_answers(config, "pre", {"residence": "310101"}))
        self.assertEqual([a["location"] for a in rendered["stimuli"]["authors"][:4]], ["上海", "广东", "province", "上海 · 广东"])
        self.assertEqual(authors[0]["location"], "province")
        self.assertEqual(templates["author:u01:location"], {"mode": "answer", "value": "province"})
        authors[3]["location"] = "{province"
        with self.assertRaises(ValueError):
            validate(config)
        authors[3]["location"] = "{province}"
        authors[1]["location"] = "未注册"
        with self.assertRaises(ValueError):
            validate(config)

    def test_dynamic_profile_requires_required_pre_question(self):
        config = copy.deepcopy(self.config)
        config["variables"] = []
        for condition in config["conditions"]:
            condition["variable_rules"] = {}
        config["stimuli"]["posts"][0]["text"] = "固定帖子"
        config["stimuli"]["authors"][0].update(location_mode="answer", location="province")
        config["flow"]["pre"]["blocks"][0]["questions"][0]["required"] = False
        with self.assertRaises(ValueError):
            validate(config)


if __name__ == "__main__":
    unittest.main()
