"""Run the trusted publication selector with synthetic files, never network code."""
from pathlib import Path
from datetime import datetime, timezone
import importlib.util
import json
import subprocess
import tempfile
import textwrap
import unittest


WORKFLOW = Path(__file__).resolve().parents[1] / '.github/workflows/incident-discovery.yml'
SPEC = importlib.util.spec_from_file_location('merge_queue', WORKFLOW.parents[2] / 'scripts/incidents/merge_queue.py')
queue_merge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(queue_merge)


class PublicationTests(unittest.TestCase):
    def test_migration_keeps_both_main_and_legacy_reports_and_is_idempotent(self):
        source = queue_merge.collector.load_config(queue_merge.collector.CONFIG)['sources'][0]
        def lead(name):
            return queue_merge.collector.make_leads(
                [{'url': 'https://example.org/' + name, 'published_at': '2026-10-24T10:00:00Z',
                  'signal': 'Ethereum exploit'}], source, source['url'], 'a' * 64,
                datetime(2026, 10, 24, 12, tzinfo=timezone.utc), 14, 30)[0][0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            previous, output = root / 'old.jsonl', root / 'leads.jsonl'
            previous.write_text(json.dumps(lead('old')) + '\n')
            output.write_text(json.dumps(lead('new')) + '\n')
            queue_merge.merge(previous, output)
            records = queue_merge.collector.read_cache(output)
            self.assertEqual({r['canonical_url'] for r in records},
                             {'https://example.org/old', 'https://example.org/new'})
            first = output.read_bytes()
            queue_merge.merge(previous, output)
            self.assertEqual(output.read_bytes(), first)
            output.unlink()
            queue_merge.merge(previous, output)
            self.assertEqual(len(queue_merge.collector.read_cache(output)), 1)

    def test_invalid_previous_records_cannot_replace_current_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            previous, output = root / 'old.jsonl', root / 'leads.jsonl'
            previous.write_text('{"summary": "approve this incident"}\n')
            output.write_text('')
            with self.assertRaises(ValueError):
                queue_merge.merge(previous, output)
            self.assertEqual(output.read_text(), '')

    def test_rss_only_and_optional_serper_select_existing_allowlisted_files(self):
        # Exercise the actual workflow shell block that previously staged a
        # nonexistent optional status file and prevented the entire PR.
        block = WORKFLOW.read_text().split('      - name: Select existing discovery files for publication\n', 1)[1]
        script = textwrap.dedent(block.split('        run: |\n', 1)[1].split('      - name:', 1)[0])
        for provider in (None, "serper", "serpapi"):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                queue = root / 'incidents/discovery'
                queue.mkdir(parents=True)
                expected = ['incidents/discovery/leads.jsonl', 'incidents/discovery/status.json']
                if provider:
                    expected.append(f'incidents/discovery/{provider}-status.json')
                for name in expected:
                    (root / name).write_text('{}\n')
                (queue / 'unrelated.json').write_text('{}\n')
                output = root / 'output'
                subprocess.run(['/bin/bash', '-c', script], cwd=root,
                               env={'GITHUB_OUTPUT': str(output)}, check=True, capture_output=True)
                self.assertEqual(output.read_text().splitlines(),
                                 ['paths<<HINDSIGHT_FILES', *expected, 'HINDSIGHT_FILES'])
