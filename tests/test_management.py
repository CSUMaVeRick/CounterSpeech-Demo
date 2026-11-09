import copy
import unittest
from pathlib import Path

from counterspeech.experiment import load_config, validate
from counterspeech.management import add_author, add_condition, add_post, parse_options, put_question, set_condition_posts
from counterspeech.study import place_display_name

ROOT = Path(__file__).resolve().parents[1]


class ManagementTest(unittest.TestCase):
    def setUp(self):
        self.config = load_config(ROOT / "configs/examples/study.example.json")

    def test_new_user_post_and_condition_are_independent(self):
        add_author(self.config, "new_user", "新用户", "assets/avatars/cat-192.jpg")
        add_post(self.config, "new_post", "p01", "new_user", "新帖 {展示地名}")
        validate(self.config)
        self.assertEqual(sum(c["post_id"] == "new_post" for c in self.config["stimuli"]["comments"]), 10)
        add_condition(self.config, "new_condition", "新组合", "local_province")
        set_condition_posts(self.config, "new_condition", ["p01", "new_post"])
        validate(self.config)
        new = next(c for c in self.config["conditions"] if c["id"] == "new_condition")
        self.assertEqual(len(new["comment_layout"]), 20)
        self.assertIn("new_post_c07", new["required_exposure_comment_ids"])
        new["variable_rules"]["展示地名"]["value"] = "city"
        self.assertEqual(self.config["conditions"][0]["variable_rules"]["展示地名"]["value"], "province")
        self.config["stimuli"]["comments"][-1]["text"] = "独立评论"
        self.assertNotEqual(self.config["stimuli"]["comments"][9]["text"], "独立评论")
        with self.assertRaises(ValueError):
            add_author(self.config, "new_user", "重复", "assets/avatars/cat-192.jpg")
        with self.assertRaises(ValueError):
            add_post(self.config, "new_post", "p01", "new_user", "重复")

    def test_new_question_has_block_position_and_separate_options(self):
        q = {"id": "pos1", "label": "你能接受外国人来中国吗？", "type": "single_choice", "required": True, "options": parse_options("1,2,3,4,5,6,7")}
        put_question(self.config, "post", "feedback", q, 2)
        validate(self.config)
        self.assertEqual(self.config["flow"]["post"]["blocks"][0]["questions"][1]["options"], list("1234567"))
        self.assertEqual(parse_options("同意，但有顾虑\n不同意"), ["同意，但有顾虑", "不同意"])
        with self.assertRaises(ValueError):
            put_question(self.config, "post", None, q, 1)
        with self.assertRaises(ValueError):
            put_question(self.config, "post", "feedback", q, 3)

    def test_comment_times_respect_post_and_parent(self):
        for value in (-1, 61, None):
            config = copy.deepcopy(self.config)
            config["stimuli"]["comments"][0]["relative_time_minutes"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate(config)
        config = copy.deepcopy(self.config)
        config["stimuli"]["comments"][1]["relative_time_minutes"] = 0
        with self.assertRaises(ValueError):
            validate(config)

    def test_natural_place_names(self):
        for name, expected in {"上海市": "上海", "广东省": "广东", "内蒙古自治区": "内蒙古", "新疆维吾尔自治区": "新疆", "广西壮族自治区": "广西", "北京市": "北京"}.items():
            self.assertEqual(place_display_name(name), expected)


if __name__ == "__main__":
    unittest.main()
