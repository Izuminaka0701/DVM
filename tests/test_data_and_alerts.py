"""Kiểm tra mẫu huấn luyện và timestamp cảnh báo mà không chạy lại traffic."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from app import alert
from app import inference
from experiments import run_full_experiment
from training.generate_dataset import generate_windows
from training.train_offline import purged_chronological_holdout


ROOT = Path(__file__).resolve().parent.parent


class DatasetIntegrityTest(unittest.TestCase):
    def test_sparse_log_does_not_generate_empty_windows(self):
        requests = [
            {"ts": t, "ip": "203.0.1.1", "method": "GET", "path": "/"}
            for t in (0.0, 1.0, 100.0, 101.0, 105.0)
        ]
        windows = list(generate_windows(requests))
        self.assertTrue(windows)
        self.assertTrue(all(w["request_rate"] > 0 for w in windows))
        self.assertLess(len(windows), 20)
        self.assertTrue(all("window_end_ts" in window for window in windows))

    def test_empty_burst_fails_before_writing_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "burst.jsonl"
            csv_path = Path(directory) / "training.csv"
            log.touch()
            result = subprocess.run(
                [sys.executable, str(ROOT / "training/generate_dataset.py"),
                 str(log), "normal", "--output", str(csv_path)],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(csv_path.exists())

    def test_burst_phase_rejects_unrelated_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / "raw_requests.jsonl"
            raw.write_text(json.dumps({"ts": 1, "ip": "10.0.0.1", "method": "GET", "path": "/"}) + "\n")
            class RunningServer:
                def poll(self):
                    return None

            with patch.object(run_full_experiment, "LOG_DIR", Path(directory)), patch.object(run_full_experiment, "run", return_value=True):
                ok = run_full_experiment.run_collection(
                    ["locust"], 1, "burst", RunningServer(), "198.51.")
            self.assertFalse(ok)


class AlertTimestampTest(unittest.TestCase):
    def test_t6_matches_recorded_alert_only_when_triggered(self):
        with tempfile.TemporaryDirectory() as directory:
            alerts = Path(directory) / "alerts.jsonl"
            blocked = Path(directory) / "blocked_ips.txt"
            with patch.object(alert, "ALERTS_LOG", alerts), patch.object(alert, "BLOCKED_IPS_FILE", blocked):
                manager = alert.AlertManager(debounce_windows=2)
                window = [{"ip": "198.51.1.1"}]
                self.assertEqual(manager.check(0.9, window), (False, "198.51.1.1", None))
                triggered, _, t6 = manager.check(0.9, window)
                self.assertTrue(triggered)
                self.assertEqual(t6, json.loads(alerts.read_text().splitlines()[0])["ts"])


class ServerStartupSafetyTest(unittest.TestCase):
    def test_incompatible_saved_model_does_not_crash_server_import(self):
        with tempfile.TemporaryDirectory() as directory:
            model_dir = Path(directory)
            (model_dir / "model.pkl").touch()
            (model_dir / "scaler.pkl").touch()
            with patch.object(inference, "MODEL_DIR", model_dir), \
                    patch.object(inference.joblib, "load", side_effect=ValueError("incompatible model")):
                engine = inference.InferenceEngine()
            self.assertFalse(engine.ready)
            self.assertIn("incompatible model", engine.load_error)
            self.assertEqual(engine.predict_proba({"request_rate": 10}), 0.0)
            self.assertEqual(engine.predict_proba({"request_rate": 51}), 1.0)

    def test_wait_for_server_stops_immediately_when_uvicorn_exits(self):
        class FailedProcess:
            def poll(self):
                return 1

        ready, reason = run_full_experiment.wait_for_server(
            FailedProcess(), 8000, "127.0.0.1", 60
        )
        self.assertFalse(ready)
        self.assertIn("mã 1", reason)


class ModelEvaluationSplitTest(unittest.TestCase):
    def test_holdout_is_chronological_and_has_five_window_purge(self):
        rows = []
        for source, label in (("normal_session", 0), ("attack_session", 1)):
            for timestamp in range(40):
                rows.append({
                    "source": source,
                    "label": label,
                    "window_end_ts": float(timestamp),
                })
        frame = pd.DataFrame(rows)
        train, test, purged, summary = purged_chronological_holdout(frame)
        self.assertEqual(len(purged), 10)
        self.assertEqual(set(frame.loc[train, "label"]), {0, 1})
        self.assertEqual(set(frame.loc[test, "label"]), {0, 1})
        for item in summary:
            self.assertGreater(
                item["test_first_ts"] - item["train_last_ts"], 5.0
            )


if __name__ == "__main__":
    unittest.main()
