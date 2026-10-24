"""Runtime planning checks; no container or Solidity code is executed."""
import importlib.util
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('runtime_plan', Path(__file__).resolve().parents[1] / 'scripts/runtime/plan.py')
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


class RuntimePlanTests(unittest.TestCase):
    def test_absent_runtime_stays_not_run(self):
        with patch.object(runtime.shutil, 'which', return_value=None):
            result = runtime.plan()
        self.assertEqual(result['status'], 'not_run')
        self.assertIsNone(result['command'])
        self.assertEqual(len(result['fixture_sha256']), 2)

    def test_execution_plan_is_offline_readonly_and_fixed_fixture(self):
        with patch.object(runtime.shutil, 'which', return_value='/usr/bin/docker'):
            result = runtime.plan('example.org/foundry@sha256:' + 'a' * 64)
        command = result['command']
        for flag in ('--pull=never', '--network=none', '--read-only', '--cap-drop=ALL', '--user=65534:65534'):
            self.assertIn(flag, command)
        self.assertIn('--offline', command[-1])
        self.assertEqual(result['status'], 'not_run')

    def test_mutable_or_injected_image_rejected(self):
        for value in ('foundry:latest', '--privileged', 'a@sha256:123', 'repo; echo unsafe'):
            with self.assertRaises(ValueError):
                runtime.plan(value)

    def test_only_two_fingerprinted_files_are_mounted(self):
        with patch.object(runtime.shutil, 'which', return_value='/usr/bin/docker'):
            command = runtime.plan('example.org/foundry@sha256:' + 'a' * 64)['command']
        mounts = [command[i + 1] for i, value in enumerate(command) if value == '--mount']
        self.assertEqual(len(mounts), 2)
        self.assertTrue(mounts[0].endswith('foundry.toml,dst=/input/foundry.toml,readonly'))
        self.assertTrue(mounts[1].endswith('Smoke.t.sol,dst=/input/Smoke.t.sol,readonly'))
        self.assertNotIn('cp -R', command[-1])

    def test_fixture_parent_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            fixture = root / 'tests/runtime'
            fixture.mkdir(parents=True)
            (fixture / 'foundry.toml').write_text('')
            external = root / 'external'
            external.mkdir()
            (external / 'Smoke.t.sol').write_text('')
            (fixture / 'test').symlink_to(external, target_is_directory=True)
            with patch.object(runtime, 'ROOT', root), self.assertRaises(ValueError):
                runtime.plan()


if __name__ == '__main__':
    unittest.main()
