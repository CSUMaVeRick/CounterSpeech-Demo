import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from counterspeech.experiment import exchange, load_config
from counterspeech.records import list_records, record_detail

ROOT = Path(__file__).resolve().parents[1]


class RecordsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "demo.sqlite3"
        config = load_config(ROOT / "configs/examples/study.example.json")
        exchange(self.path, config, {"token": "a" * 64}, mode="demo", condition_id="local_province")
        self.completed = exchange(self.path, config, {"token": "b" * 64, "events": [
            {"event_id": "pre", "type": "pre_submit", "answers": {"residence": "310101"}},
            {"event_id": "exposure", "type": "exposure_met", "target": "c07", "duration_ms": 2100},
            {"event_id": "complete", "type": "complete"},
            {"event_id": "post", "type": "post_submit", "answers": {"impression": "测试回答"}},
        ]}, mode="demo", condition_id="local_province")

    def test_readonly_counts_filters_and_details(self):
        before = self.path.read_bytes()
        result = list_records(self.path)
        self.assertEqual((result["total"], result["submitted"], result["filtered"]), (2, 1, 2))
        code = self.completed["state"]["completion_code"]
        found = list_records(self.path, search=code, phase="submitted", condition="local_province")
        self.assertEqual(found["filtered"], 1)
        detail = record_detail(self.path, found["rows"][0]["id"])
        self.assertEqual(detail["state"]["post_answers"]["impression"], "测试回答")
        self.assertEqual([e["type"] for e in detail["events"]], ["pre_submit", "exposure_met", "complete", "post_submit"])
        self.assertEqual(list_records(self.path, search="%' OR 1=1 --")["filtered"], 0)
        self.assertEqual(list_records(self.path, page=2)["rows"], [])
        self.assertEqual(before, self.path.read_bytes())
        with self.assertRaises(ValueError):
            record_detail(self.path, "missing")

    def test_no_database_created_by_browser(self):
        missing = Path(self.temp.name) / "missing.sqlite3"
        with self.assertRaises(sqlite3.Error):
            list_records(missing)
        self.assertFalse(missing.exists())

    def test_legacy_completion_is_not_final_submission(self):
        db = sqlite3.connect(self.path)
        try:
            with db:
                db.execute("INSERT INTO sessions VALUES (?,?,?)", ("legacy", json.dumps({"conditions": [{"id": "old"}]}), json.dumps({"completed": True})))
        finally:
            db.close()
        result = list_records(self.path)
        self.assertEqual((result["total"], result["submitted"]), (3, 1))
        self.assertEqual(list_records(self.path, phase="legacy_complete")["filtered"], 1)


if __name__ == "__main__":
    unittest.main()
