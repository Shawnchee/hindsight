"""Synthetic-only research export/privacy/reproduction checks; no downloaded code runs."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "m0/scripts/discovery"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


export = load("export_research")
fetch = load("fetch_snapshot_source")


class ResearchExportTests(unittest.TestCase):
    def setUp(self):
        self.incidents = [{"incident_id": "demo", "human_verified": False, "training_eligible": False,
            "evaluation_eligible": False, "benchmark_promoted": False, "label_status": "proposed",
            "adjudication": "unresolved", "split": "unassigned", "family_id": None,
            "first_seen_at": None, "proposed_locations": []}]
        self.disclosures = [{"incident_id": "demo", "observed_publication_date": "2020-01-02",
                             "earliest_disclosure_confirmed": False, "first_seen_at": None}]
        self.groups = {"groups": [{"incident_ids": ["demo"], "exploit_family_confirmed": False}]}

    def test_approval_and_earliest_disclosure_cannot_be_inferred(self):
        export.validate_records(self.incidents, [], self.disclosures, self.groups)
        for key in ("human_verified", "training_eligible", "evaluation_eligible", "benchmark_promoted"):
            changed = copy.deepcopy(self.incidents)
            changed[0][key] = True
            with self.assertRaises(ValueError):
                export.validate_records(changed, [], self.disclosures, self.groups)
        self.disclosures[0]["earliest_disclosure_confirmed"] = True
        with self.assertRaises(ValueError):
            export.validate_records(self.incidents, [], self.disclosures, self.groups)

    def test_every_incident_must_belong_to_exactly_one_provisional_cohort(self):
        for members in ([], ["demo", "demo"], ["unknown"]):
            self.groups["groups"][0]["incident_ids"] = members
            with self.assertRaises(ValueError):
                export.validate_records(self.incidents, [], self.disclosures, self.groups)

    def test_source_locations_require_matching_hashes(self):
        self.incidents[0]["proposed_locations"] = [{"address": "a", "source_unit": "Demo.sol", "source_sha256": "right"}]
        contract = {"address": "a", "source_files": [{"source_unit": "Demo.sol", "sha256": "wrong"}]}
        with self.assertRaises(ValueError):
            export.validate_records(self.incidents, [contract], self.disclosures, self.groups)

    def test_snapshot_is_idempotent_and_differing_contents_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "snapshot"
            payload, meta = {"record.json": b'{"proposed":true}\n'}, {"version": "v0.1.0"}
            export.write_snapshot(out, payload, meta)
            original = (out / "manifest.json").read_bytes()
            export.write_snapshot(out, payload, meta)
            self.assertEqual((out / "manifest.json").read_bytes(), original)
            with self.assertRaises(ValueError):
                export.write_snapshot(out, {"record.json": b"different"}, meta)
            self.assertEqual((out / "record.json").read_bytes(), payload["record.json"])

    def test_source_reproduction_checks_actual_bytes_and_safe_paths(self):
        text = "contract Demo {}\n"
        unit = "/E/Demo.sol"
        contract = {"runtime_match": "match", "runtime_sha256": fetch.digest(bytes.fromhex("6000")),
                    "source_files": [{"source_unit": unit, "sha256": fetch.digest(text.encode()), "bytes": len(text.encode())}]}
        response = {"runtimeMatch": "match", "runtimeBytecode": {"onchainBytecode": "0x6000"},
                    "sources": {unit: {"content": text}}}
        self.assertIn(Path("_absolute_source_units/E/Demo.sol"), fetch.verified_sources(contract, response))
        response["sources"][unit]["content"] += "//changed"
        with self.assertRaises(ValueError):
            fetch.verified_sources(contract, response)
        for unit in ("../outside.sol", "/../outside.sol", "a\\b.sol"):
            with self.assertRaises(ValueError):
                fetch.local_unit(unit)

    def test_source_fetch_dry_run_has_no_network_or_filesystem_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "contracts.jsonl"
            addr = "0x" + "1" * 40
            path.write_text(json.dumps({"address": addr, "chain_id": 1, "source_files": []}) + "\n")
            out = Path(tmp) / "output"
            with patch.object(sys, "argv", ["fetch.py", "--contracts", str(path), "--address", addr, "--out", str(out)]), \
                 patch.object(fetch.urllib.request, "build_opener") as network, contextlib.redirect_stdout(io.StringIO()):
                fetch.main()
            network.assert_not_called()
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
