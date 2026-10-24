"""Synthetic offline checks for the public metadata intake boundary."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPOSITORY = Path(__file__).resolve().parents[1]
SCRIPT = REPOSITORY / "scripts/incidents/validate.py"
spec = importlib.util.spec_from_file_location("community_incidents", SCRIPT)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class CommunityIncidentsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name)
        self.root = self.repo / "incidents/submissions"
        self.root.mkdir(parents=True)
        self.record = json.loads((REPOSITORY / "incidents/examples/example.json").read_text())
        self.record.update(candidate_id="community_test_lead", name="Synthetic test lead",
                           summary="Original synthetic summary for offline validator tests.")
        self.record["primary_sources"][0]["url"] = "https://reports.example.org/incidents/one"

    def write(self, record=None, filename=None):
        record = self.record if record is None else record
        path = self.root / (filename or (record["candidate_id"] + ".json"))
        path.write_text(json.dumps(record), encoding="utf-8")
        return path

    def check(self):
        return validator.validate_directory(self.root, self.repo)[0]

    def assert_invalid(self, field):
        self.write()
        errors = self.check()
        self.assertEqual(len(errors), 1, errors)
        self.assertIn(field, errors[0])
        return errors[0]

    def test_empty_and_missing_corpus_pass_without_network(self):
        with patch("socket.getaddrinfo", side_effect=AssertionError("DNS prohibited")), \
             patch("urllib.request.urlopen", side_effect=AssertionError("HTTP prohibited")):
            self.assertEqual(self.check(), [])
            self.root.rmdir()
            self.assertEqual(self.check(), [])

    def test_url_only_source_gap_and_reported_identifiers_are_valid(self):
        with patch("socket.getaddrinfo", side_effect=AssertionError("DNS prohibited")):
            self.write()
            self.assertEqual(self.check(), [])
            self.record["tx_hashes"] = ["0x" + "a" * 64]
            self.record["victim_addresses"] = ["0x" + "b" * 40]
            self.write()
            self.assertEqual(self.check(), [])

    def test_all_promotion_and_scope_gates_are_immutable(self):
        mutations = {
            "chain_id": [137, True], "language": ["Vyper"],
            "human_verified": [True, 0], "training_eligible": [True],
            "evaluation_eligible": [True], "benchmark_promoted": [True],
            "first_seen_at": ["2020-01-01"], "family_id": ["inferred-family"],
            "adjudication": ["confirmed_valid"], "label_status": ["confirmed"],
            "split": ["train"], "intake_status": ["ready"],
            "identifier_verification": ["verified"], "source_policy": ["full_text"],
        }
        for field, values in mutations.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    changed = copy.deepcopy(self.record)
                    changed[field] = value
                    with self.assertRaisesRegex(validator.InvalidRecord, field):
                        validator.validate_record(changed)

    def test_unknown_fields_and_source_bodies_rejected_without_echo(self):
        marker = "do-not-print-submitted-value"
        for key in ("article_body", "post_body", "content", "sources", "PoC.sol", "api_key", marker):
            with self.subTest(key=key):
                self.record[key] = {"content": marker}
                error = self.assert_invalid("unknown fields")
                self.assertNotIn(marker, error)
                del self.record[key]
        self.record["primary_sources"][0]["body"] = marker
        self.assert_invalid("unknown fields")

    def test_missing_fields_dates_and_filename_binding_rejected(self):
        self.record.pop("coverage_gaps")
        self.assert_invalid("coverage_gaps")
        self.record["coverage_gaps"] = ["Pending review."]
        self.record["incident_date"] = "2020-02-30"
        self.assert_invalid("calendar date")
        self.record["incident_date"] = None
        self.record["discovered_at"] = None
        self.assert_invalid("discovered_at")
        self.record["discovered_at"] = "2026-10-24"
        self.write(filename="community_wrong_name.json")
        self.assertTrue(any("match the JSON filename" in error for error in self.check()))

    def test_public_url_shape_rejects_local_private_and_credentials(self):
        bad_urls = [
            "file:///etc/passwd", "javascript:alert(1)", "https:///missing",
            "http://localhost/post", "http://host.local/post", "http://host.internal/",
            "http://127.0.0.1/post", "https://10.0.0.1/post", "http://169.254.169.254/",
            "http://[::1]/post", "http://[::ffff:127.0.0.1]/post", "http://[ff02::1]/",
            "http://2130706433/", "http://0177.0.0.1/", "http://0x7f000001/",
            "http://192.168.1.1.nip.io/post", "https://localtest.me/post",
            "https://user:do-not-print@reports.example.org/post",
            "https://reports.example.org:99999/post", "https://reports.example.org:1234/post",
            "https://reports.example.org/post?api_key=do-not-print",
            "https://reports.example.org/post?X-Amz-Credential=do-not-print",
            "https://mainnet.infura.io/v3/do-not-print", "https://reports.example.org/%0apost",
            "https://reports.example.org\\@localhost/post", "https://bad_host.org/post",
        ]
        for url in bad_urls:
            with self.subTest(url=url), self.assertRaises(validator.InvalidRecord):
                validator.canonical_url(url)
        self.assertEqual(validator.canonical_url("https://reports.example.org/post?lang=en"),
                         "https://reports.example.org/post?lang=en")
        self.assertEqual(validator.canonical_url("https://[2606:4700:4700::1111]/"),
                         "https://[2606:4700:4700::1111]/")

    def test_source_payload_and_secrets_are_never_printed(self):
        values = [
            "pragma solidity ^0.8.0; contract Victim {}",
            "```solidity contract Victim {}```", "<article>copied article body</article>",
            '{"sources":{"Victim.sol":{"content":"raw source"}}}',
            "api_key=do-not-print-this-credential", "-----BEGIN PRIVATE KEY-----",
            "ghp_" + "x" * 30, "sk-" + "x" * 30,
            "eyJ" + "x" * 20 + "." + "y" * 20 + "." + "z" * 20,
        ]
        for value in values:
            with self.subTest(value=value):
                self.record["summary"] = value
                error = self.assert_invalid("summary")
                self.assertNotIn(value, error)

    def test_identifier_shape_duplicates_and_arrays_rejected(self):
        mutations = [
            ("tx_hashes", ["0x1234"]), ("victim_addresses", ["not-an-address"]),
            ("tx_hashes", ["0x" + "a" * 64, "0x" + "A" * 64]),
            ("victim_addresses", ["0x" + "a" * 40, "0x" + "A" * 40]),
            ("coverage_gaps", []), ("primary_sources", []), ("tx_hashes", "0x" + "a" * 64),
        ]
        for field, value in mutations:
            with self.subTest(field=field):
                changed = copy.deepcopy(self.record)
                changed[field] = value
                with self.assertRaises(validator.InvalidRecord):
                    validator.validate_record(changed)

    def test_canonical_url_and_transaction_dedupe_across_submissions(self):
        self.write()
        second = copy.deepcopy(self.record)
        second["candidate_id"] = "community_second_lead"
        second["primary_sources"][0]["url"] = "http://www.reports.example.org/incidents/one/?utm_source=test#section"
        self.write(second)
        self.assertTrue(any("duplicate canonical evidence URL" in error for error in self.check()))
        second["primary_sources"][0]["url"] = "https://reports.example.org/incidents/two"
        second["tx_hashes"] = ["0x" + "A" * 64]
        self.record["tx_hashes"] = ["0x" + "a" * 64]
        self.write()
        self.write(second)
        self.assertTrue(any("duplicate transaction" in error for error in self.check()))

    def test_duplicate_against_research_and_catalog(self):
        existing = self.repo / "m0/discovery/incidents.proposed.jsonl"
        existing.parent.mkdir(parents=True)
        existing.write_text(json.dumps({"candidate_id": "research_test", "source_urls": [
            "https://reports.example.org/incidents/one#old"], "tx_hashes": []}) + "\n")
        self.assert_invalid("duplicate canonical evidence URL")
        self.record["primary_sources"][0]["url"] = "https://reports.example.org/incidents/two"
        self.record["tx_hashes"] = ["0x" + "a" * 64]
        catalog = self.repo / "m0/catalog/all_incidents.csv"
        catalog.parent.mkdir(parents=True)
        catalog.write_text("incident_id,attack_tx_hashes\nexisting,0x" + "a" * 64 + "\n")
        self.assert_invalid("duplicate transaction")

    def test_size_limits_bounded_text_and_invalid_json(self):
        self.record["summary"] = "x" * 2001
        self.assert_invalid("2000 characters")
        path = self.write()
        path.write_bytes(b"x" * (validator.MAX_FILE_BYTES + 1))
        self.assertIn("exceeds", self.check()[0])
        for raw in ('{"summary":"one","summary":"two"}', '{"value":NaN}', '[1,2]', '{bad json'):
            path.write_text(raw)
            self.assertTrue(self.check())

    def test_symlinks_nested_and_unexpected_files_rejected(self):
        external = self.repo / "outside.json"
        external.write_text(json.dumps(self.record))
        (self.root / "community_test_lead.json").symlink_to(external)
        self.assertIn("symlinks", self.check()[0])
        (self.root / "community_test_lead.json").unlink()
        (self.root / "community_nested.json").mkdir()
        self.assertIn("non-regular", self.check()[0])
        (self.root / "unexpected.txt").write_text("do-not-print")
        self.assertTrue(any("only JSON metadata" in error for error in self.check()))
        alias = self.repo / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        self.assertIn("symlink", validator.validate_directory(alias, self.repo)[0][0])

    def test_example_is_excluded_and_schema_matches_validator(self):
        schema = json.loads((REPOSITORY / "incidents/schema.json").read_text())
        self.assertEqual(set(schema["required"]), validator.FIELDS)
        self.assertEqual(set(schema["properties"]), validator.FIELDS)
        for field, value in validator.CONSTANTS.items():
            self.assertEqual(schema["properties"][field]["const"], value)
        example = json.loads((REPOSITORY / "incidents/examples/example.json").read_text())
        validator.validate_record(example)
        self.write(example)
        self.assertIn("synthetic template is excluded", self.check()[0])

    def test_credentials_in_candidate_ids_and_filenames_are_not_echoed(self):
        credential = "ghp_" + "x" * 30
        self.record["candidate_id"] = "community_" + credential
        self.write()
        error = self.check()[0]
        self.assertIn("candidate_id", error)
        self.assertNotIn(credential, error)

    def test_cli_failure_is_actionable_and_does_not_echo_secret(self):
        self.record["summary"] = "api_key=do-not-print-this-credential"
        self.write()
        result = subprocess.run([sys.executable, "-I", str(SCRIPT), "--root", str(self.root)],
                                text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("community_test_lead.json: summary", result.stderr)
        self.assertNotIn("do-not-print-this-credential", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
