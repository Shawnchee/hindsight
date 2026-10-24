"""Public-output boundaries and metadata checks; no website dependencies needed."""
import importlib.util
import json
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('public_site', ROOT / 'scripts/site/check.py')
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)


class PublicSiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        for name in ('index.html', 'docs/index.html', 'docs/getting-started.html', 'docs/remediation.html', 'docs/report-format.html', 'assets/fonts/OFL.txt'):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('<h1 id="start">Fixture</h1>')

    def test_valid_links_and_extensionless_docs(self):
        (self.root / 'index.html').write_text('<a href="docs/">Docs</a>')
        (self.root / 'docs/index.html').write_text('<a href="getting-started#start">Start</a><a href="../">Website</a>')
        self.assertEqual(site.check(self.root)[0], [])

    def test_missing_anchor_and_asset_fail(self):
        (self.root / 'index.html').write_text('<a href="docs/getting-started.html#absent">Bad</a><img src="missing.svg">')
        errors, _ = site.check(self.root)
        self.assertTrue(any('missing anchor' in e for e in errors))
        self.assertTrue(any('missing link/asset' in e for e in errors))

    def test_private_files_symlinks_and_unexpected_types_fail(self):
        (self.root / '.env').write_text('synthetic fixture only')
        (self.root / '.env.local').write_text('synthetic fixture only')
        (self.root / 'credentials.json').write_text('{}')
        (self.root / 'leak.html').symlink_to(self.root / 'index.html')
        (self.root / 'source.sol').write_text('synthetic nonexecuted text')
        errors, _ = site.check(self.root)
        self.assertTrue(any('.env' in e for e in errors))
        self.assertTrue(any('.env.local' in e for e in errors))
        self.assertTrue(any('credentials.json' in e for e in errors))
        self.assertTrue(any('leak.html' in e for e in errors))
        self.assertTrue(any('source.sol' in e for e in errors))

    def test_external_subresources_rejected_external_links_allowed(self):
        page = self.root / 'index.html'
        page.write_text('<a href="https://example.org">Reference</a>')
        self.assertEqual(site.check(self.root)[0], [])
        page.write_text('<script src="https://example.org/tracker.js"></script>')
        self.assertTrue(any('external subresource' in e for e in site.check(self.root)[0]))

    def test_css_assets_checked_and_traversal_rejected(self):
        (self.root / 'site.css').write_text('body{background:url(../../private.png)}')
        self.assertTrue(any('escapes site' in e for e in site.check(self.root)[0]))

    def test_preview_keeps_catalog_and_enriched_records_distinct(self):
        spec = importlib.util.spec_from_file_location('research_preview', ROOT / 'scripts/site/research_preview.py')
        preview = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(preview)
        markup, raw = preview.render()
        data = json.loads(raw)
        selectors = re.findall(r'data-dataset-filter="([^"]+)"', markup)
        self.assertEqual(selectors, ['2026', '2025', 'enriched'])
        self.assertEqual(data['catalog']['entry_count'], sum(data['catalog']['year_counts'].values()))
        self.assertEqual(len(data['catalog']['examples']), 6)
        self.assertEqual(sum(x['entries'] for x in data['charts']['annual_entries']), data['catalog']['entry_count'])
        self.assertIsNone(data['charts']['loss_total'])
        self.assertEqual(len(data['charts']['selected_loss_examples']), 5)
        amounts = [x['reported_usd'] for x in data['charts']['selected_loss_examples']]
        self.assertEqual(amounts, sorted(amounts, reverse=True))
        self.assertTrue(all(x['verification'] == 'source_reported_unverified' for x in data['charts']['selected_loss_examples']))
        self.assertIn('Not total losses.', markup)
        for entry in data['catalog']['examples']:
            self.assertEqual(entry['data_stage'], 'catalog_entry')
            self.assertEqual(entry['source_coverage'], 'not_assessed_by_this_preview')
            self.assertTrue(entry['reported_date'].startswith(entry['catalog_year']))
            self.assertNotIn('raw_label', entry)
            self.assertNotIn('poc_path', entry)
        self.assertTrue(all(not r['human_verified'] and not r['training_eligible'] and not r['evaluation_eligible'] for r in data['examples']))

    @unittest.skipUnless(shutil.which('node'), 'Node is optional for source-helper users')
    def test_builder_refuses_unrecognized_output_before_dependencies(self):
        script = self.root / 'scripts/site/build.mjs'
        script.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / 'scripts/site/build.mjs', script)
        output = self.root / 'site-dist'
        output.mkdir()
        sentinel = output / 'keep.txt'
        sentinel.write_text('must remain unchanged')
        result = subprocess.run(['node', str(script)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sentinel.read_text(), 'must remain unchanged')


if __name__ == '__main__':
    unittest.main()
