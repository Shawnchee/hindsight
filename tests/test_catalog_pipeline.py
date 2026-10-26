"""Synthetic upstream metadata and model outputs; no requests or PoC execution."""
from datetime import datetime, timezone
import contextlib
import importlib.util
import json
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


catalog = load('test_catalog_module', 'scripts/incidents/catalog.py')
summaries = load('test_summary_module', 'scripts/incidents/summarize.py')
TX = '0x' + 'a' * 64
VICTIM = '0x' + 'b' * 40
SHA = 'c' * 40
ENTRY = {'name': 'FixtureVault', 'date': '2026-10-25', 'paths': ['src/test/2026-10/Fixture_exp.sol'],
         'claim': 'Missing authorization on a privileged setter', 'loss': 'unknown'}
SOURCE = f'// Chain : Ethereum mainnet\n// Attack Tx : https://etherscan.io/tx/{TX}\n// Vulnerable : {VICTIM}\n'


class CatalogTests(unittest.TestCase):
    def candidate(self):
        return catalog.candidate(ENTRY, SOURCE, SHA)[0]

    def test_requires_explicit_scope_attack_transaction_and_victim(self):
        row = self.candidate()
        self.assertEqual(row['chain_id'], 1)
        self.assertFalse(row['human_verified'])
        for text in (SOURCE.replace('Ethereum mainnet', 'Base'), SOURCE.replace(TX, ''),
                     SOURCE.replace(VICTIM, ''), SOURCE.replace('https://etherscan.io', 'https://basescan.org'),
                     SOURCE + 'createSelectFork("bsc", 123);'):
            with self.subTest(text=text):
                self.assertIsNone(catalog.candidate(ENTRY, text, SHA)[0])
        alternate = SOURCE.replace('// Chain : Ethereum mainnet', '// Ethereum mainnet, 2026-10-25').replace('https://etherscan.io/tx/', '')
        self.assertIsNotNone(catalog.candidate(ENTRY, alternate, SHA)[0])

    def test_same_incident_different_source_matches_without_new_row(self):
        row = self.candidate()
        other = json.loads(json.dumps(row))
        other['upstream_paths'] = ['src/test/2026-10/SecondReport.sol']
        self.assertEqual(catalog.matching(other, [row]), ('existing', row['id']))
        other['transactions'] = ['0x' + 'd' * 64]
        self.assertEqual(catalog.matching(other, [row])[0], 'ambiguous')
        other['date'] = '2026-10-24'
        self.assertEqual(catalog.matching(other, [row])[0], 'new')

    def test_cross_protocol_roundup_or_conflicting_transaction_is_not_merged(self):
        row = self.candidate()
        other = json.loads(json.dumps(row))
        other.update(name='UnrelatedProtocol', upstream_paths=['src/test/2026-10/Other.sol'], contracts=['0x' + 'd' * 40])
        self.assertEqual(catalog.matching(other, [row])[0], 'ambiguous')

    def test_upstream_parsing_has_path_boundaries_and_rejects_future_dates(self):
        text = ('### 20261025 FixtureVault - claim\n### Lost: unknown\n'
                '[Contract](src/test/2026-10/Fixture_exp.sol)\n'
                '### 20990101 Future - claim\n[Contract](src/test/2026-10/Future.sol)\n'
                '### 20261024 Bad - claim\n[Contract](../../secret.sol)\n')
        rows = catalog.entries(text, datetime(2026, 10, 26, tzinfo=timezone.utc))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['name'], 'FixtureVault')

    def test_refresh_repeat_is_idempotent_and_preserves_baseline(self):
        state = {'schema_version': catalog.SCHEMA, 'updated_at': None, 'upstream_commit': None,
                 'additional': [], 'related_reports': {}, 'pending': [], 'last_refresh': None}
        readme = b'### 20261025 FixtureVault - Missing authorization\n### Lost: unknown\n[Contract](src/test/2026-10/Fixture_exp.sol)\n'
        def fetch(url, **kwargs):
            if 'api.github.com' in url:
                return json.dumps({'sha': SHA}).encode()
            return readme if url.endswith('/README.md') else SOURCE.encode()
        with patch.object(catalog, 'baseline', return_value=[]):
            first, _ = catalog.refresh(state, datetime(2026, 10, 26, tzinfo=timezone.utc), fetch)
            second, _ = catalog.refresh(first, datetime(2026, 10, 26, tzinfo=timezone.utc), fetch)
        self.assertEqual(len(first['additional']), 1)
        self.assertEqual(first['additional'], second['additional'])
        self.assertEqual(second['last_refresh']['added'], 0)

    def test_upstream_network_is_fixed_and_default_cli_is_offline(self):
        with patch.object(catalog.urllib.request, 'build_opener') as opener:
            with self.assertRaises(ValueError):
                catalog.fetch_public('https://example.org/README.md')
            opener.assert_not_called()


class SummaryTests(unittest.TestCase):
    def inputs(self):
        return [{'id': 'fixture', 'name': 'FixtureVault', 'claim': ENTRY['claim'],
                 'loss_reported': 'unknown', 'source_url': catalog.UPSTREAM + '/blob/' + SHA + '/README.md'}]

    def payload(self):
        return {'summaries': [{'id': 'fixture', 'summary': 'A setter reportedly lacked access control.',
                              'root_cause': 'Missing authorization', 'support_quote': 'Missing authorization'}]}

    def test_model_cannot_invent_identity_source_support_or_approval(self):
        good = summaries.validate_result(self.payload(), self.inputs())
        self.assertFalse(good[0]['human_verified'])
        for change in ({'id': 'invented'}, {'support_quote': 'not in source'}, {'human_verified': True}):
            value = self.payload()
            value['summaries'][0].update(change)
            with self.assertRaises(ValueError):
                summaries.validate_result(value, self.inputs())

    def test_one_batch_then_zero_requests_for_unchanged_claims(self):
        calls = []
        def generator(inputs, key):
            calls.append(inputs)
            return self.payload(), {'promptTokenCount': 20, 'candidatesTokenCount': 30}
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ', {'GEMINI_API_KEY': 'fixture-token'}), contextlib.redirect_stdout(io.StringIO()):
            output = Path(tmp).resolve() / 'summaries.json'
            summaries.compile_summaries(self.inputs(), output, generator)
            summaries.compile_summaries(self.inputs(), output, generator)
            self.assertNotIn('fixture-token', output.read_text())
        self.assertEqual(len(calls), 1)

    def test_failed_model_keeps_existing_records_and_logs_no_provider_text(self):
        def fail(inputs, key):
            raise ValueError('fixture-token private response')
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ', {'GEMINI_API_KEY': 'fixture-token'}), contextlib.redirect_stdout(io.StringIO()):
            output = Path(tmp).resolve() / 'summaries.json'
            result = summaries.compile_summaries(self.inputs(), output, fail)
            self.assertEqual(result['status'], 'failed')
            self.assertNotIn('fixture-token', output.read_text())
