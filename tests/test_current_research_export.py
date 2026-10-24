"""Synthetic supplements must preserve branches, provenance and research gates."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("current_export", Path(__file__).resolve().parents[1] /
    "m0/scripts/discovery/export_current_research.py")
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)


class SupplementTests(unittest.TestCase):
    def setUp(self):
        self.incident = {"summary": "Original branch", "proposed_locations": [
            {"address": "old", "source_unit": "Old.sol", "function": "mint", "role": "defect"}],
            "contracts": [], "coverage_gaps": ["Previously missing branch"]}
        self.supplement = {"label_status": "proposed", "adjudication": "unresolved",
            "human_verified": False, "training_eligible": False, "evaluation_eligible": False,
            "benchmark_promoted": False, "first_seen_at": None, "family_id": None,
            "split": "unassigned", "exact_transaction_state_verified": False,
            "summary": "Recovered second branch", "remaining_gaps": ["Trace absent"],
            "proposed_locations": [{"address": "new", "source_unit": "New.sol",
                "function": "price", "role": "defect"}], "recovered_contracts": [
                    {"address": "new", "role": "pricing implementation"}]}
        self.contracts = {"new": {"contract_name": "Pricing", "runtime_match": "match"}}

    def test_recovery_preserves_old_branch_and_gap_provenance(self):
        result = export.merge_incident(self.incident, self.supplement, self.contracts)
        self.assertEqual(len(result["proposed_locations"]), 2)
        self.assertEqual(result["historical_coverage_gaps"], ["Previously missing branch"])
        self.assertEqual(result["coverage_gaps"], ["Trace absent"])
        self.assertIn("Original branch", result["summary"])
        self.assertIn("Recovered second branch", result["summary"])
        self.assertFalse(result["source_coverage"]["complete_incident_source_confirmed"])
        self.assertEqual(len(self.incident["proposed_locations"]), 1)

    def test_supplement_cannot_promote_or_invent_execution_and_dates(self):
        for key, value in (("human_verified", True), ("training_eligible", True),
                           ("evaluation_eligible", True), ("benchmark_promoted", True),
                           ("exact_transaction_state_verified", True),
                           ("first_seen_at", "2020-01-01"), ("family_id", "family"),
                           ("adjudication", "confirmed_valid")):
            s = copy.deepcopy(self.supplement)
            s[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                export.merge_incident(self.incident, s, self.contracts)

    def test_conflicting_location_and_uninventoried_component_fail_closed(self):
        self.supplement["proposed_locations"] = copy.deepcopy(self.incident["proposed_locations"])
        with self.assertRaises(ValueError):
            export.merge_incident(self.incident, self.supplement, self.contracts)
        self.supplement["proposed_locations"] = []
        with self.assertRaises(ValueError):
            export.merge_incident(self.incident, self.supplement, {})

    def test_checked_evidence_rejects_tampering_and_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            p = root / "evidence.json"
            p.write_bytes(b"original")
            digest = export.base.sha(p.read_bytes())
            self.assertEqual(export.checked(root, p.name, digest), b"original")
            p.write_bytes(b"changed")
            with self.assertRaises(ValueError):
                export.checked(root, p.name, digest)
            with self.assertRaises(ValueError):
                export.checked(root, "../outside")

    def test_manifest_cannot_omit_consumed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            folder = root / "supplement"
            folder.mkdir()
            artifacts = {}
            for name in ("sources.json", "incidents.followup.jsonl", "historical_checks.json"):
                (folder / name).write_bytes(b"{}")
                artifacts[name] = export.base.sha(b"{}")
            export.verify_supplement_manifest(root, Path("supplement"), {"artifacts": artifacts})
            del artifacts["sources.json"]
            with self.assertRaises(ValueError):
                export.verify_supplement_manifest(root, Path("supplement"), {"artifacts": artifacts})


if __name__ == "__main__":
    unittest.main()
