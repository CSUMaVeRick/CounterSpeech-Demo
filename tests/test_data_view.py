import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiment import exchange, load_config

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(importlib.util.find_spec("streamlit"), "requires Streamlit")
class DataViewTest(unittest.TestCase):
    def test_password_gate_and_collapsed_records(self):
        from streamlit.testing.v1 import AppTest

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            script = root / "data_view.py"
            script.write_text((ROOT / "data_view.py").read_text(encoding="utf-8"), encoding="utf-8")
            config = load_config(ROOT / "docs/study.example.json")
            db_path = root / "data/responses.sqlite3"
            exchange(db_path, config, {"token": "a" * 64}, mode="live")
            before = db_path.read_bytes()
            with patch.dict(os.environ, {"RESEARCHER_PASSWORD": ""}), patch("records.list_records") as query:
                app = AppTest.from_file(str(script)).run(timeout=15)
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(len(app.error), 1)
                query.assert_not_called()
            with patch.dict(os.environ, {"RESEARCHER_PASSWORD": "test-only-researcher-password"}):
                app = AppTest.from_file(str(script)).run(timeout=15)
                self.assertEqual(len(app.metric), 0)
                app.text_input[0].set_value("wrong")
                next(b for b in app.button if b.label == "登录").click().run(timeout=15)
                self.assertEqual(len(app.metric), 0)
                app.text_input[0].set_value("test-only-researcher-password")
                next(b for b in app.button if b.label == "登录").click().run(timeout=15)
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(len(app.error), 0, [e.value for e in app.error])
                self.assertEqual(app.metric[0].value, "1")
                drawers = app.get("expander")
                self.assertEqual(len(drawers), 1)
                self.assertFalse(drawers[0].proto.expanded)
                next(b for b in app.button if b.label == "退出登录").click().run(timeout=15)
                self.assertEqual(len(app.metric), 0)
            self.assertEqual(before, db_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
