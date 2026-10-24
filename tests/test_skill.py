"""Synthetic helper checks. No model, real benchmark data, network or builds."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "skills/hindsight-triage/scripts/triage.py"
spec = importlib.util.spec_from_file_location("hindsight_triage", SCRIPT)
triage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(triage)


class SkillTests(unittest.TestCase):
    def test_slither_rejects_symlink_parent_and_fifo_before_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            real = root / 'real'
            real.mkdir()
            (real / 'report.json').write_text('{"success": true}')
            (root / 'alias').symlink_to(real, target_is_directory=True)
            with self.assertRaises(ValueError):
                triage.read_slither(root / 'alias/report.json')
            if hasattr(os, 'mkfifo'):
                fifo = root / 'pipe'
                os.mkfifo(fifo)
                with self.assertRaises(ValueError):
                    triage.read_slither(fifo)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "src").mkdir()
        (self.root / "src/Vault.sol").write_text('pragma solidity ^0.8.0;\nimport {Math} from "./Math.sol";\ncontract Vault {}\n')
        (self.root / "src/Math.sol").write_text('library Math {}\n')
        (self.root / "src/Unrelated.sol").write_text('contract Unrelated {}\n')

    def bundle(self):
        return triage.prepare(self.root, ["src/Vault.sol"], [])

    def report(self):
        return {"schema_version": triage.SCHEMA, "mode": "source-only", "model": "not-run",
                "summary": "Synthetic schema check only", "reviewed_files": ["src/Vault.sol", "src/Math.sol"],
                "coverage_gaps": ["Slither not supplied"], "findings": []}

    def finding(self):
        return {"id": "H001", "title": "Synthetic candidate", "status": "unresolved", "severity": "low",
                "confidence": "low", "category": "other", "location": "Vault.sol:example",
                "evidence": [{"file": "src/Vault.sol", "line_start": 1, "line_end": 2}],
                "preconditions": ["Synthetic fixture"], "impact": "Synthetic consequence",
                "reasoning": "Schema fixture only", "verification": "No security conclusion",
                "recommendation": "Inspect actual source"}

    def test_import_closure_excludes_unrelated_files(self):
        bundle = self.bundle()
        self.assertEqual(set(bundle["files"]), {"src/Vault.sol", "src/Math.sol"})
        self.assertEqual(bundle["coverage_gaps"], [])
        self.assertEqual(bundle["slither"]["status"], "not_supplied")

    def test_import_forms_ignore_comments_and_string_instructions(self):
        source = '''// import "Fake.sol";
        /* import "AlsoFake.sol"; */
        import /* comment */ {A,
            B as C} from "./Real.sol";
        import "./Plain.sol";
        import * as Lib from './Alias.sol';
        import './Old.sol' as Old;
        contract C { string constant x = 'import "Secret.sol";'; }
        '''
        self.assertEqual(triage.imports(source), ["./Real.sol", "./Plain.sol", "./Alias.sol", "./Old.sol"])

    def test_unresolved_and_ambiguous_imports_are_gaps(self):
        (self.root / "src/Vault.sol").write_text('import "Missing.sol"; import "Shared.sol";')
        (self.root / "Shared.sol").write_text("library Shared {}")
        (self.root / "node_modules").mkdir()
        (self.root / "node_modules/Shared.sol").write_text("library OtherShared {}")
        bundle = self.bundle()
        self.assertEqual(len(bundle["coverage_gaps"]), 2)
        self.assertTrue(any("ambiguous" in g for g in bundle["coverage_gaps"]))
        self.assertEqual(set(bundle["files"]), {"src/Vault.sol"})

    def test_remappings_follow_longest_prefix_and_cycles_terminate(self):
        (self.root / "src/Vault.sol").write_text('import "@lib/Math.sol";')
        (self.root / "src/Math.sol").write_text('import "./Vault.sol";')
        bundle = triage.prepare(self.root, ["src/Vault.sol"], [("@", "missing/"), ("@lib/", "src/")])
        self.assertEqual(len(bundle["files"]), 2)
        self.assertFalse(bundle["coverage_gaps"])

    def test_escape_symlink_and_test_targets_rejected(self):
        (self.root / "src/Alias.sol").symlink_to(self.root / "src/Math.sol")
        for target in ("../Escape.sol", "src/Alias.sol", "test/Attack.t.sol", "/tmp/Escape.sol"):
            with self.assertRaises(ValueError):
                triage.prepare(self.root, [target], [])

    def test_import_escape_is_reported_without_reading_it(self):
        (self.root / "src/Vault.sol").write_text('import "../../outside.sol";')
        bundle = self.bundle()
        self.assertEqual(set(bundle["files"]), {"src/Vault.sol"})
        self.assertIn("escapes project root", bundle["coverage_gaps"][0])

    def test_byte_cap_fails_instead_of_silently_trimming(self):
        with self.assertRaisesRegex(ValueError, "byte limit"):
            triage.prepare(self.root, ["src/Vault.sol"], [], max_bytes=5)

    def test_supplied_and_failed_slither_are_distinct(self):
        path = self.root / "slither.json"
        path.write_text(json.dumps({"success": True, "results": {"detectors": [{"check": "synthetic", "impact": "Low"}]}}))
        supplied = triage.prepare(self.root, ["src/Vault.sol"], [], path)
        self.assertEqual(supplied["slither"]["status"], "supplied")
        self.assertEqual(supplied["slither"]["hints"][0]["check"], "synthetic")
        path.write_text(json.dumps({"success": False, "error": "compiler missing"}))
        self.assertEqual(triage.read_slither(path)["status"], "failed")

    def test_empty_findings_valid_and_source_evidence_checked(self):
        bundle, report = self.bundle(), self.report()
        self.assertEqual(triage.validate_report(report, bundle), [])
        report["findings"] = [self.finding()]
        self.assertEqual(triage.validate_report(report, bundle), [])
        for key, value in (("line_start", 0), ("line_end", 999), ("line_start", True), ("file", "Wrong.sol")):
            bad = copy.deepcopy(report)
            bad["findings"][0]["evidence"][0][key] = value
            self.assertTrue(triage.validate_report(bad, bundle))
        bad = copy.deepcopy(report)
        bad["findings"][0]["location"] = "Wrong.sol:example"
        self.assertTrue(triage.validate_report(bad, bundle))

    def test_missing_gaps_duplicate_ids_and_unsupported_mode_fail(self):
        bundle, report = self.bundle(), self.report()
        bundle["coverage_gaps"] = ["Missing implementation"]
        self.assertTrue(triage.validate_report(report, bundle))
        report["coverage_gaps"].append("Missing implementation")
        self.assertFalse(triage.validate_report(report, bundle))
        report["mode"] = "source+slither"
        self.assertTrue(triage.validate_report(report, bundle))
        report["mode"] = "source-only"
        report["reviewed_files"].remove("src/Math.sol")
        self.assertTrue(triage.validate_report(report, bundle))
        report["coverage_gaps"].append("Not reviewed: src/Math.sol")
        report["findings"] = [self.finding(), self.finding()]
        self.assertTrue(any("duplicate" in e for e in triage.validate_report(report, bundle)))

    def test_cli_prepares_validates_and_never_overwrites(self):
        out = self.root / "review"
        command = [sys.executable, "-I", str(SCRIPT), "prepare", "--root", str(self.root),
                   "--target", "src/Vault.sol", "--out", str(out)]
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
        before = (out / "bundle.json").read_bytes()
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.assertEqual(before, (out / "bundle.json").read_bytes())
        report = out / "report.json"
        report.write_text(json.dumps(self.report()))
        command = [sys.executable, "-I", str(SCRIPT), "validate", "--bundle", str(out / "bundle.json"), "--report", str(report)]
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)


if __name__ == "__main__":
    unittest.main()
