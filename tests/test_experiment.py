import copy
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from counterspeech.experiment import asset_url, exchange, load_config, public_config, save_draft, validate, write_working_draft

ROOT = Path(__file__).resolve().parents[1]


class ExperimentTest(unittest.TestCase):
    def setUp(self):
        self.config = load_config(ROOT / "configs/examples/experiment.example.json")
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

    def test_post_read_completion_requires_all_post_confirmations(self):
        self.config["environment"]["completion_mode"] = "post_read"
        first = self.config["stimuli"]["posts"][0]
        second = {**first, "id": "second_post"}
        self.config["stimuli"]["posts"].append(second)
        self.config["conditions"][0]["post_order"].append(second["id"])

        def mark(event_id, target, checked=True):
            return {"event_id": event_id, "type": "post_read", "target": target, "checked": checked}

        finish = {"event_id": "finish", "type": "complete"}
        with self.assertRaisesRegex(ValueError, "无效的帖子阅读确认"):
            self.send(mark("bad-target", "c07"))
        self.send({"event_id": "exposed", "type": "exposure_met", "target": "c07", "duration_ms": 2100})
        self.send(mark("first-read", first["id"]))
        with self.assertRaisesRegex(ValueError, "勾选所有帖子"):
            self.send(finish)

        self.send(mark("second-read", second["id"]))
        self.send(mark("second-unread", second["id"], False))
        self.assertEqual(self.send()["state"]["read_posts"], {first["id"]: True, second["id"]: False})
        with self.assertRaisesRegex(ValueError, "勾选所有帖子"):
            self.send(finish)
        self.assertTrue(self.send(mark("second-reread", second["id"]), finish)["state"]["completed"])

    def test_assigned_feedback_applies_only_to_counter_speech(self):
        self.config["environment"]["mask_background_reaction_counts"] = True
        self.config["counter_feedback_levels"] = {
            "mixed": {"label": "很多赞和踩", "initial_likes": 14, "initial_dislikes": 12},
        }
        self.config["conditions"][0]["counter_feedback"] = "mixed"
        assigned = self.send()
        self.assertEqual(assigned["state"]["likes"], {})
        stimuli = assigned["config"]["stimuli"]
        self.assertEqual(stimuli["posts"], self.config["stimuli"]["posts"])
        for before, after in zip(self.config["stimuli"]["comments"], stimuli["comments"]):
            if before.get("research_role") == "counter_speech":
                self.assertEqual((after["initial_likes"], after["initial_dislikes"]), (14, 12))
            else:
                self.assertEqual(after, before)
        public = public_config(assigned["config"])
        self.assertNotIn("counter_feedback_levels", public)
        self.assertNotIn("counter_feedback", public["conditions"][0])
        self.assertTrue(all(post["mask_reaction_counts"] for post in public["stimuli"]["posts"]))
        for before, after in zip(stimuli["comments"], public["stimuli"]["comments"]):
            self.assertEqual(after.get("mask_reaction_counts", False), before.get("research_role") != "counter_speech")

        self.config["conditions"][0]["counter_feedback"] = "unknown"
        with self.assertRaisesRegex(ValueError, "档位不存在"):
            validate(self.config)

    def test_reactions_are_exclusive_per_target_and_replay_safe(self):
        self.config["environment"]["enabled_actions"].append("dislike")
        like_post = {"event_id": "like-post", "type": "like", "target": "p01", "liked": True}
        dislike_post = {"event_id": "dislike-post", "type": "dislike", "target": "p01", "disliked": True}
        dislike_comment = {"event_id": "dislike-comment", "type": "dislike", "target": "c07", "disliked": True}
        state = self.send(like_post, dislike_post, dislike_comment)["state"]
        self.assertFalse(state["likes"]["p01"])
        self.assertEqual(state["dislikes"], {"p01": True, "c07": True})

        like_again = {**like_post, "event_id": "like-post-again"}
        state = self.send(like_again, dislike_post)["state"]
        self.assertTrue(state["likes"]["p01"])
        self.assertEqual(state["dislikes"], {"p01": False, "c07": True})
        cancel = {**dislike_comment, "event_id": "undo-dislike", "disliked": False}
        self.assertFalse(self.send(cancel)["state"]["dislikes"]["c07"])

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
