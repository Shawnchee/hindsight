"""Run the trusted publication selector with synthetic files, never network code."""
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


WORKFLOW = Path(__file__).resolve().parents[1] / '.github/workflows/incident-discovery.yml'


class PublicationTests(unittest.TestCase):
    def test_rss_only_and_optional_serper_select_existing_allowlisted_files(self):
        # Exercise the actual workflow shell block that previously staged a
        # nonexistent optional status file and prevented the entire PR.
        block = WORKFLOW.read_text().split('      - name: Select existing discovery files for publication\n', 1)[1]
        script = textwrap.dedent(block.split('        run: |\n', 1)[1].split('      - name:', 1)[0])
        for serper in (False, True):
            with self.subTest(serper=serper), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                queue = root / 'incidents/discovery'
                queue.mkdir(parents=True)
                expected = ['incidents/discovery/leads.jsonl', 'incidents/discovery/status.json']
                if serper:
                    expected.append('incidents/discovery/serper-status.json')
                for name in expected:
                    (root / name).write_text('{}\n')
                (queue / 'unrelated.json').write_text('{}\n')
                output = root / 'output'
                subprocess.run(['/bin/bash', '-c', script], cwd=root,
                               env={'GITHUB_OUTPUT': str(output)}, check=True, capture_output=True)
                self.assertEqual(output.read_text().splitlines(),
                                 ['paths<<HINDSIGHT_FILES', *expected, 'HINDSIGHT_FILES'])
