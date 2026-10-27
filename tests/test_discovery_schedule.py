"""Synthetic run histories for the daily catch-up gate; no API or model calls."""
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('discovery_schedule', ROOT / 'scripts/incidents/schedule.py')
schedule = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(schedule)


class ScheduleTests(unittest.TestCase):
    now = datetime(2026, 10, 27, 4, 17, tzinfo=timezone.utc)

    def run_record(self, **changes):
        return dict(id=1, head_branch='main', event='schedule', status='completed',
                    conclusion='success', created_at='2026-10-27T01:20:00Z',
                    updated_at='2026-10-27T01:23:00Z', **changes)

    def decide(self, *records):
        return schedule.needs_collection({'workflow_runs': list(records)}, 'main', '99', self.now)

    def test_successful_daily_refresh_skips_catchup(self):
        self.assertFalse(self.decide(self.run_record()))
        manual = self.run_record()
        manual['event'] = 'workflow_dispatch'
        self.assertFalse(self.decide(manual))

    def test_failed_skipped_running_or_other_branch_does_not_suppress_collection(self):
        for key, value in [('conclusion', 'failure'), ('conclusion', 'skipped'),
                           ('status', 'in_progress'), ('head_branch', 'feature'),
                           ('event', 'push'), ('id', 99)]:
            with self.subTest(key=key, value=value):
                run = self.run_record()
                run[key] = value
                self.assertTrue(self.decide(run))

    def test_only_success_started_after_daily_cutoff_counts(self):
        for started, completed in [('2026-10-26T01:20:00Z', '2026-10-26T01:23:00Z'),
                                   ('2026-10-27T01:16:59Z', '2026-10-27T01:23:00Z'),
                                   ('2026-10-27T04:20:00Z', '2026-10-27T04:23:00Z'),
                                   ('2026-10-27T01:20:00Z', '2026-10-27T04:23:00Z')]:
            run = self.run_record()
            run.update(created_at=started, updated_at=completed)
            self.assertTrue(self.decide(run))

    def test_malformed_or_empty_history_fails_open(self):
        for payload in [None, {}, {'workflow_runs': None}, {'workflow_runs': [None, {}]}]:
            self.assertTrue(schedule.needs_collection(payload, 'main', '99', self.now))
        self.assertTrue(self.decide())
        for value in [None, 'nonsense', '2026-10-27T01:20:00']:
            run = self.run_record()
            run['created_at'] = value
            self.assertTrue(self.decide(run))


if __name__ == '__main__':
    unittest.main()
