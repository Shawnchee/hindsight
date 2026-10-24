"""Synthetic project and remediation integrity checks; no builds or model calls."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/hindsight-triage/scripts/workflow.py'
spec = importlib.util.spec_from_file_location('workflow', SCRIPT)
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / 'src').mkdir()
        (self.root / 'src/Vault.sol').write_text('pragma solidity ^0.8.0;\nimport "./Math.sol";\ncontract Vault { function update() external {} }\n')
        (self.root / 'src/Math.sol').write_text('library Math {}\n')
        self.before = w.triage.prepare(self.root, ['src/Vault.sol'], [])
        self.br = self.report()
        self.br['findings'] = [self.finding()]
        (self.root / 'src/Vault.sol').write_text('pragma solidity ^0.8.0;\nimport "./Math.sol";\ncontract Vault { function update() external { require(msg.sender == address(1)); } }\n')
        self.after = w.triage.prepare(self.root, ['src/Vault.sol'], [])
        self.ar = self.report()
        self.record = w.plan(self.before, self.br)
        self.record['after'] = {'bundle_sha256': w.digest(self.after), 'report_sha256': w.digest(self.ar)}

    def report(self):
        return {'schema_version': w.triage.SCHEMA, 'mode': 'source-only', 'model': 'synthetic-not-run',
                'summary': 'Synthetic fixture; no security verdict', 'reviewed_files': ['src/Vault.sol', 'src/Math.sol'],
                'coverage_gaps': ['Slither not used'], 'findings': []}

    def finding(self):
        return {'id': 'H001', 'title': 'Synthetic candidate', 'status': 'unresolved', 'severity': 'low',
                'confidence': 'low', 'category': 'other', 'location': 'Vault.sol:update',
                'evidence': [{'file': 'src/Vault.sol', 'line_start': 3, 'line_end': 3}],
                'preconditions': ['Synthetic only'], 'impact': 'Synthetic', 'reasoning': 'Synthetic',
                'verification': 'Not executed', 'recommendation': 'Reassess'}

    def compare(self):
        return w.compare(self.before, self.br, self.after, self.ar, self.record, self.root)

    def addressed(self):
        item = self.record['findings'][0]
        item.update(assessment='addressed_by_review', rationale='Synthetic source change examined.',
                    after_evidence=[{'file': 'src/Vault.sol', 'line_start': 3, 'line_end': 3}])

    def test_inventory_imports_candidates_and_no_spoofed_hints(self):
        (self.root / 'src/Proxy.sol').write_text('''// contract Fake { delegatecall(x); }
interface IFoo {}
abstract contract Base {}
contract Proxy { string s = "contract Bad { call(x); }";
function f() external { assembly { let r := delegatecall(0,0,0,0,0,0) } } }
''')
        result = w.inventory(self.root)
        self.assertEqual(result['candidate_targets'], ['src/Proxy.sol', 'src/Vault.sol'])
        proxy = next(f for f in result['files'] if f['file'] == 'src/Proxy.sol')
        self.assertEqual([d['name'] for d in proxy['declarations']], ['IFoo', 'Base', 'Proxy'])
        self.assertEqual([h['kind'] for h in proxy['lexical_call_hints']], ['delegatecall'])
        vault = next(f for f in result['files'] if f['file'] == 'src/Vault.sol')
        self.assertEqual(vault['imports'][0]['resolved'], 'src/Math.sol')

    def test_inventory_exclusions_and_unresolved_imports(self):
        for directory in ('test', 'node_modules', '.secret'):
            (self.root / directory).mkdir()
            (self.root / directory / 'Hidden.sol').write_text('contract Hidden {}')
        (self.root / 'src/Link.sol').symlink_to(self.root / 'src/Vault.sol')
        (self.root / 'src/Other.sol').write_text('import "Missing.sol"; contract Other {}')
        result = w.inventory(self.root)
        self.assertNotIn('src/Link.sol', [f['file'] for f in result['files']])
        self.assertTrue(all('Hidden.sol' not in f['file'] for f in result['files']))
        other = next(f for f in result['files'] if f['file'] == 'src/Other.sol')
        self.assertIn('unresolved', other['imports'][0]['gap'])

    def test_inventory_fails_on_caps_and_invalid_encoding(self):
        for args in ({'max_files': 1}, {'max_bytes': 2}, {'max_entries': 1}):
            with self.assertRaises(ValueError):
                w.inventory(self.root, **args)
        (self.root / 'src/Bad.sol').write_bytes(b'contract C {}\xff')
        with self.assertRaises(UnicodeError):
            w.inventory(self.root)
        with self.assertRaises(UnicodeError):
            w.triage.prepare(self.root, ['src/Bad.sol'], [])

    def test_snapshot_content_bytes_hash_and_targets_are_checked(self):
        for key, value in [('sha256', '0' * 64), ('bytes', 0), ('line_count', 900), ('content', 'changed')]:
            bad = copy.deepcopy(self.before)
            bad['files']['src/Vault.sol'][key] = value
            self.assertTrue(w.triage.validate_report(self.br, bad))
        self.before['targets'] = ['missing.sol']
        self.assertTrue(w.triage.validate_report(self.br, self.before))

    def test_plan_binds_whole_review_and_defaults_unresolved(self):
        self.assertEqual(self.record['findings'][0]['assessment'], 'unresolved')
        self.br['summary'] = 'Changed review'
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            self.compare()

    def test_disappeared_finding_stays_unresolved(self):
        result = self.compare()
        self.assertEqual(result['findings'][0]['assessment'], 'unresolved')
        self.assertEqual(result['file_changes']['modified'], ['src/Vault.sol'])
        self.assertIn('not independently verified', result['verification'])
        self.assertIn('No test evidence', w.markdown(result))

    def test_missing_duplicate_and_unknown_dispositions_fail(self):
        for items in ([], self.record['findings'] * 2, [dict(self.record['findings'][0], before_id='H999')]):
            old = self.record['findings']
            self.record['findings'] = items
            with self.assertRaises(ValueError):
                self.compare()
            self.record['findings'] = old

    def test_addressed_requires_changed_reviewed_source_and_valid_lines(self):
        self.addressed()
        self.assertEqual(self.compare()['findings'][0]['assessment'], 'addressed_by_review')
        self.record['findings'][0]['after_evidence'][0]['line_end'] = 99
        with self.assertRaisesRegex(ValueError, 'line range'):
            self.compare()
        self.record['findings'][0]['after_evidence'] = [{'file': 'src/Math.sol', 'line_start': 1, 'line_end': 1}]
        with self.assertRaisesRegex(ValueError, 'changed source'):
            self.compare()

    def test_active_mapped_finding_cannot_be_claimed_fixed(self):
        self.addressed()
        self.ar['findings'] = [self.finding()]
        self.record['after']['report_sha256'] = w.digest(self.ar)
        self.record['findings'][0]['after_ids'] = ['H001']
        with self.assertRaisesRegex(ValueError, 'active or unresolved'):
            self.compare()

    def test_new_after_findings_are_always_visible(self):
        self.ar['findings'] = [dict(self.finding(), id='NEW')]
        self.record['after']['report_sha256'] = w.digest(self.ar)
        self.assertEqual(self.compare()['unmapped_after_findings'], ['NEW'])

    def test_scope_reduction_requires_explanation(self):
        self.after = w.triage.prepare(self.root, ['src/Math.sol'], [])
        self.ar['reviewed_files'] = ['src/Math.sol']
        self.record['after'] = {'bundle_sha256': w.digest(self.after), 'report_sha256': w.digest(self.ar)}
        with self.assertRaisesRegex(ValueError, 'scope changes'):
            self.compare()
        self.record['scope_change_explanation'] = 'Removed target; still unresolved.'
        result = self.compare()
        self.assertEqual(result['scope_changes']['removed_targets'], ['src/Vault.sol'])
        self.assertIn('src/Vault.sol', result['file_changes']['deleted'])

    def test_test_artifacts_bound_to_snapshots_and_not_proof_of_fix(self):
        (self.root / 'evidence').mkdir()
        log = self.root / 'evidence/test.log'
        log.write_text('synthetic log; no tests executed')
        test = {'id': 'T1', 'status': 'passed', 'environment': 'disposable_container',
                'command': 'display-only synthetic command', 'checks': 'Synthetic fixture',
                'before_bundle_sha256': w.digest(self.before), 'after_bundle_sha256': w.digest(self.after),
                'artifact': {'path': 'evidence/test.log', 'sha256': hashlib.sha256(log.read_bytes()).hexdigest()}}
        self.record['tests'] = [test]
        self.record['findings'][0]['test_ids'] = ['T1']
        self.assertEqual(self.compare()['findings'][0]['assessment'], 'unresolved')
        log.write_text('changed log')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.compare()
        test['after_bundle_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'snapshot fingerprint'):
            self.compare()

    def test_test_artifact_escape_symlink_and_host_execution_rejected(self):
        test = {'id': 'T1', 'status': 'passed', 'environment': 'disposable_container', 'command': 'not executed',
                'checks': 'Synthetic', 'before_bundle_sha256': w.digest(self.before), 'after_bundle_sha256': w.digest(self.after),
                'artifact': {'path': '../test.log', 'sha256': '0' * 64}}
        self.record['tests'] = [test]
        with self.assertRaisesRegex(ValueError, 'relative'):
            self.compare()
        (self.root / 'evidence').mkdir()
        test['artifact']['path'] = 'evidence/link.log'
        (self.root / 'evidence/link.log').symlink_to(self.root / 'src/Vault.sol')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.compare()
        test['environment'] = 'host'
        with self.assertRaisesRegex(ValueError, 'disposable container'):
            self.compare()

    def test_not_run_and_failed_tests_remain_explicit(self):
        self.record['tests'] = [{'id': 'T1', 'status': 'not_run', 'environment': 'not_run', 'command': '',
                                 'checks': 'No suitable container available', 'before_bundle_sha256': w.digest(self.before),
                                 'after_bundle_sha256': w.digest(self.after), 'artifact': None}]
        self.assertIn('not\\_run', w.markdown(self.compare()))

    def test_cli_end_to_end_and_no_overwrite(self):
        paths = {}
        for name, obj in [('before-bundle', self.before), ('before-report', self.br), ('after-bundle', self.after),
                          ('after-report', self.ar), ('record', self.record)]:
            paths[name] = self.root / (name + '.json')
            paths[name].write_text(json.dumps(obj))
        out = self.root / 'comparison'
        cmd = [sys.executable, '-I', str(SCRIPT), 'compare', '--out', str(out)]
        for name, path in paths.items():
            cmd += ['--' + name, str(path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        original = (out / 'comparison.json').read_bytes()
        self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
        self.assertEqual(original, (out / 'comparison.json').read_bytes())
        self.assertTrue((out / 'comparison.md').exists())
        inv = subprocess.run([sys.executable, '-I', str(SCRIPT), 'inventory', '--root', str(self.root),
                              '--out', str(self.root / 'inventory')], capture_output=True, text=True)
        self.assertEqual(inv.returncode, 0, inv.stderr)

    def test_unreadable_inventory_directory_fails_visibly(self):
        def broken_walk(*args, **kwargs):
            kwargs['onerror'](PermissionError('synthetic private path'))
            return iter(())
        with mock.patch.object(w.os, 'walk', side_effect=broken_walk):
            with self.assertRaisesRegex(ValueError, 'could not be read'):
                w.inventory(self.root)

    def test_dense_inventory_metadata_is_bounded(self):
        (self.root / 'src/Dense.sol').write_text('contract C {}\n' * 10001)
        with self.assertRaisesRegex(ValueError, 'metadata limit'):
            w.inventory(self.root)

    def test_markdown_keeps_untrusted_images_and_links_inert(self):
        self.ar['coverage_gaps'].append('![external](https://example.org/tracker) [link](https://example.org)')
        self.record['after']['report_sha256'] = w.digest(self.ar)
        output = w.markdown(self.compare())
        self.assertNotIn('![external]', output)
        self.assertNotIn('[link](', output)
        self.assertIn(r'\[external\]', output)

    def test_secret_artifact_rejected_before_read(self):
        self.record['tests'] = [{'id': 'T1', 'status': 'passed', 'environment': 'disposable_container',
                                'command': 'synthetic', 'checks': 'Synthetic',
                                'before_bundle_sha256': w.digest(self.before), 'after_bundle_sha256': w.digest(self.after),
                                'artifact': {'path': 'evidence/.env', 'sha256': '0' * 64}}]
        with mock.patch.object(w, 'safe_file', side_effect=AssertionError('must not read')):
            with self.assertRaisesRegex(ValueError, 'non-secret'):
                self.compare()

    def test_comparison_exposes_high_severity_new_findings(self):
        self.ar['findings'] = [dict(self.finding(), id='NEW', title='New material concern', severity='high')]
        self.record['after']['report_sha256'] = w.digest(self.ar)
        output = w.markdown(self.compare())
        self.assertIn('New material concern', output)
        self.assertIn('high / unresolved', output)
        self.assertIn('Synthetic candidate', output)

    def test_duplicate_json_keys_rejected(self):
        path = self.root / 'bad.json'
        path.write_text('{"a": 1, "a": 2}')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            w.load(path)


if __name__ == '__main__':
    unittest.main()
