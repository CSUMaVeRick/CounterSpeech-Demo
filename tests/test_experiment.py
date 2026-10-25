import copy
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from experiment import asset_url, exchange, load_config, public_config, save_draft, validate, write_working_draft

ROOT = Path(__file__).resolve().parents[1]


class ExperimentTest(unittest.TestCase):
    def setUp(self):
        self.config = load_config(ROOT / "docs/experiment.example.json")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "test.sqlite3"
        self.token = "a" * 64

    def send(self, *events, token=None, config=None):
        return exchange(self.db, config or self.config, {"token": token or self.token, "events": list(events)})

    def test_idempotency_isolation_and_pinned_config(self):
        like = {"event_id": "like-1", "type": "like", "target": "c07", "liked": True}
        self.send(like)
        self.send(like)
        changed = copy.deepcopy(self.config)
        changed["environment"]["theme"] = "douyin"
        restored = self.send(config=changed)
        self.assertEqual(restored["config"]["environment"]["theme"], "weibo")
        self.assertTrue(restored["state"]["likes"]["c07"])
        self.assertEqual(self.send(token="b" * 64)["state"]["likes"], {})
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM events").fetchone()[0], 1)

    def test_completion_and_comment_validation(self):
        with self.assertRaises(ValueError):
            self.send({"event_id": "finish", "type": "complete"})
        with self.assertRaises(ValueError):
            self.send({"event_id": "empty", "type": "comment", "target": "c01", "text": "  "})
        with self.assertRaises(ValueError):
            self.send({"event_id": "short", "type": "exposure_met", "target": "c07", "duration_ms": 10})
        reply = {"event_id": "reply", "type": "comment", "target": "c01", "text": "<script>alert(1)</script>"}
        self.send(reply)
        self.assertEqual(len(self.send(reply)["state"]["comments"]), 1)
        self.send({"event_id": "exposed", "type": "exposure_met", "target": "c07", "duration_ms": 2100})
        self.assertTrue(self.send({"event_id": "finish", "type": "complete"})["state"]["completed"])

    def test_batch_failure_rolls_back(self):
        self.send()
        with self.assertRaises(ValueError):
            self.send({"event_id": "valid", "type": "like", "target": "c01", "liked": True},
                      {"event_id": "invalid", "type": "like", "target": "missing", "liked": True})
        self.assertEqual(self.send()["state"]["likes"], {})

    def test_config_tree_validation(self):
        for mutation in ("cycle", "missing", "duplicate_order", "count", "negative", "target"):
            config = copy.deepcopy(self.config)
            layout = config["conditions"][0]["comment_layout"]
            if mutation == "cycle":
                layout[0]["parent_id"] = "c04"
            elif mutation == "missing":
                layout[1]["parent_id"] = "absent"
            elif mutation == "duplicate_order":
                layout[2]["sibling_order"] = 1
            elif mutation == "count":
                config["stimuli"]["comments"].pop()
            elif mutation == "negative":
                config["stimuli"]["comments"][0]["initial_likes"] = -1
            else:
                config["conditions"][0]["required_exposure_comment_ids"] = ["absent"]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate(config)

    def test_roles_are_not_sent_to_browser(self):
        self.assertNotIn("research_role", json.dumps(public_config(self.config)))
        self.assertIn("research_role", self.config["stimuli"]["comments"][0])

    def test_profiles_and_images(self):
        public = public_config(self.config)
        self.assertTrue(public["stimuli"]["authors"][0]["avatar"].startswith("data:image/jpeg;base64,"))
        self.assertTrue(public["stimuli"]["posts"][0]["media"][0]["src"].startswith("data:image/jpeg;base64,"))
        self.assertTrue(public["stimuli"]["authors"][0]["verified"])
        self.assertEqual(self.config["stimuli"]["authors"][0]["avatar"], "assets/avatars/city-192.jpg")
        for path in ("experiment.py", "assets/../experiment.py", "https://example.com/a.jpg"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                asset_url(path)
        broken = copy.deepcopy(self.config)
        broken["stimuli"]["authors"][0]["followers"] = -1
        with self.assertRaises(ValueError):
            validate(broken)

    def test_draft_save_preserves_previous_on_error(self):
        path = Path(self.temp.name) / "draft.json"
        save_draft(path, self.config)
        previous = path.read_bytes()
        broken = copy.deepcopy(self.config)
        broken["stimuli"]["posts"][0]["media"][0]["src"] = "assets/missing.jpg"
        with self.assertRaises(OSError):
            save_draft(path, broken)
        self.assertEqual(path.read_bytes(), previous)
        changed = copy.deepcopy(self.config)
        changed["stimuli"]["authors"][0]["display_name"] = "新昵称"
        with self.assertRaises(ValueError):
            save_draft(path, changed)
        changed["config_version"] = "new-version"
        save_draft(path, changed)
        self.assertEqual(load_config(path)["stimuli"]["authors"][0]["display_name"], "新昵称")

    def test_incomplete_working_draft_does_not_replace_published_config(self):
        published = Path(self.temp.name) / "published.json"
        working = Path(self.temp.name) / "working.json"
        save_draft(published, self.config)
        before = published.read_bytes()
        incomplete = copy.deepcopy(self.config)
        incomplete["variables"] = [{"name": "未配置变量", "label": "正在编辑"}]
        write_working_draft(working, incomplete)
        self.assertEqual(json.loads(working.read_text(encoding="utf-8")), incomplete)
        with self.assertRaises(ValueError):
            save_draft(published, incomplete)
        self.assertEqual(published.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
