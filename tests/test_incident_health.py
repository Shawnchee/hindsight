"""Synthetic timestamps/status only; no feed or API connection."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("health", Path(__file__).resolve().parents[1] / "scripts/incidents/health.py")
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)


class HealthTests(unittest.TestCase):
    def test_recent_success_and_optional_serper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            states = [{"source_id": sid, "observed_at": "2026-10-24T11:00:00Z", "status": "ok", "lead_count": 2}
                      for sid in ("google-news-ethereum", "openzeppelin")]
            (root / "status.json").write_text(json.dumps({"sources": states}))
            now = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
            _, healthy = health.assess(root, now=now)
            self.assertTrue(healthy)
            _, healthy = health.assess(root, include_serper=True, now=now)
            self.assertFalse(healthy)
            serper = [{"source_id": sid, "observed_at": "2026-10-24T11:00:00Z", "status": "ok", "lead_count": 0}
                      for sid in ("serper-news", "serper-x-links")]
            (root / "serper-status.json").write_text(json.dumps({"sources": serper}))
            _, healthy = health.assess(root, include_serper=True, now=now)
            self.assertTrue(healthy)
            serper.pop()
            (root / "serper-status.json").write_text(json.dumps({"sources": serper}))
            _, healthy = health.assess(root, include_serper=True, now=now)
            self.assertFalse(healthy)

    def test_stale_failed_missing_or_malformed_status_is_not_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
            for payload in ({}, {"sources": []}, {"sources": [
                {"source_id": "google-news-ethereum", "observed_at": "2020-01-01T00:00:00Z", "status": "ok"},
                {"source_id": "openzeppelin", "observed_at": "2026-10-24T11:00:00Z", "status": "failed"}]}):
                (root / "status.json").write_text(json.dumps(payload))
                _, healthy = health.assess(root, now=now)
                self.assertFalse(healthy)
