import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


@unittest.skipUnless(importlib.util.find_spec("streamlit"), "requires the app's Streamlit environment")
class AdminTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.working = Path(self.folder.name) / "admin.work.json"
        environment = patch.dict(os.environ, {"ADMIN_WORKING_CONFIG": str(self.working), "EXPERIMENT_CONFIG": str(Path(__file__).resolve().parents[1] / "configs/examples/study.example.json")})
        environment.start()
        self.addCleanup(environment.stop)
    @patch("counterspeech.social_ui.component")
    def test_profile_location_can_use_pre_province(self, component):
        from streamlit.testing.v1 import AppTest

        component.return_value = lambda **kwargs: SimpleNamespace(packet=None)
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "admin.py")).run(timeout=15)
        next(field for field in app.selectbox if field.label == "IP 属地显示方式").set_value("answer").run(timeout=15)
        next(field for field in app.selectbox if field.label == "属地来源字段").set_value("province")
        next(button for button in app.button if button.label == "应用资料编辑").click().run(timeout=15)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0, [error.value for error in app.error])
        author = app.session_state["config"]["stimuli"]["authors"][0]
        self.assertEqual((author["location_mode"], author["location"]), ("answer", "province"))

    @patch("counterspeech.social_ui.component")
    def test_profile_edit_survives_rerun(self, component):
        from streamlit.testing.v1 import AppTest

        # AppTest's mock runtime has no v2 registry; this test covers forms, not JS.
        component.return_value = lambda **kwargs: SimpleNamespace(packet=None)
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "admin.py")).run(timeout=15)
        self.assertEqual(len(app.exception), 0)
        nickname = next(field for field in app.text_input if field.label == "昵称")
        nickname.set_value("管理页测试昵称")
        next(button for button in app.button if button.label == "应用资料编辑").click().run(timeout=15)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state["config"]["stimuli"]["authors"][0]["display_name"], "管理页测试昵称")
        app.run(timeout=15)
        self.assertEqual(app.session_state["config"]["stimuli"]["authors"][0]["display_name"], "管理页测试昵称")

    @patch("counterspeech.social_ui.component")
    def test_create_question_without_internal_reference_fields(self, component):
        from streamlit.testing.v1 import AppTest

        component.return_value = lambda **kwargs: SimpleNamespace(packet=None)
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "admin.py")).run(timeout=15)
        next(field for field in app.selectbox if field.label == "问卷阶段").set_value("post").run(timeout=15)
        next(field for field in app.selectbox if field.label == "题型").set_value("single_choice").run(timeout=15)
        next(field for field in app.text_input if field.label == "题目 ID").set_value("pos1")
        next(field for field in app.text_area if field.label == "题目内容").set_value("你能接受外国人来中国吗？")
        next(field for field in app.text_area if field.label.startswith("选项（")).set_value("1,2,3,4,5,6,7")
        next(button for button in app.button if button.label == "新增题目").click().run(timeout=15)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0, [error.value for error in app.error])
        qs = app.session_state["config"]["flow"]["post"]["blocks"][0]["questions"]
        self.assertEqual(qs[-1]["id"], "pos1")
        self.assertEqual(qs[-1]["options"], list("1234567"))

    @patch("counterspeech.social_ui.component")
    def test_create_user_post_and_condition_in_forms(self, component):
        from streamlit.testing.v1 import AppTest

        component.return_value = lambda **kwargs: SimpleNamespace(packet=None)
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "admin.py")).run(timeout=15)
        next(field for field in app.text_input if field.label == "新用户 ID").set_value("created_user")
        next(field for field in app.text_input if field.label == "新用户昵称").set_value("测试新用户")
        next(button for button in app.button if button.label == "新增用户").click().run(timeout=15)
        self.assertEqual(len(app.exception), 0)
        next(field for field in app.text_input if field.label == "新帖子 ID").set_value("created_post")
        next(field for field in app.selectbox if field.label == "新帖发布者").set_value("created_user")
        next(field for field in app.text_area if field.label == "新帖子正文").set_value("测试新帖 {展示地名}")
        next(button for button in app.button if button.label == "新增帖子").click().run(timeout=15)
        next(field for field in app.text_input if field.label == "新条件 ID").set_value("created_condition")
        next(field for field in app.text_input if field.label == "新条件说明").set_value("测试组合")
        next(button for button in app.button if button.label == "新增条件组合").click().run(timeout=15)
        next(field for field in app.selectbox if field.label == "编辑条件组合").set_value("created_condition").run(timeout=15)
        next(field for field in app.multiselect if field.label.startswith("本组合显示的帖子")).set_value(["p01", "created_post"])
        next(button for button in app.button if button.label == "应用条件规则").click().run(timeout=15)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 0, [error.value for error in app.error])
        config = app.session_state["config"]
        condition = next(c for c in config["conditions"] if c["id"] == "created_condition")
        self.assertEqual(condition["post_order"], ["p01", "created_post"])
        self.assertEqual(len(condition["comment_layout"]), 20)
        reloaded = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "admin.py")).run(timeout=15)
        self.assertEqual(len(reloaded.exception), 0)
        self.assertTrue(any(p["id"] == "created_post" for p in reloaded.session_state["config"]["stimuli"]["posts"]))
        self.assertTrue(any(a["id"] == "created_user" for a in reloaded.session_state["config"]["stimuli"]["authors"]))


if __name__ == "__main__":
    unittest.main()
