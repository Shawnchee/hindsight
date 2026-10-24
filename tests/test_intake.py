"""Synthetic-only source materialization checks; never executes downloaded code."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
import io
import contextlib

SCRIPT = Path(__file__).resolve().parents[1] / "m0/scripts/discovery/materialize_sources.py"
spec = importlib.util.spec_from_file_location("materialize_sources", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
archive_spec = importlib.util.spec_from_file_location("read_archive", SCRIPT.with_name("read_archive.py"))
archive = importlib.util.module_from_spec(archive_spec)
archive_spec.loader.exec_module(archive)
validator_spec = importlib.util.spec_from_file_location("validate_intake", SCRIPT.with_name("validate_intake.py"))
validator = importlib.util.module_from_spec(validator_spec)
validator_spec.loader.exec_module(validator)


class IntakeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.cache = self.root / "m0/data/cache"
        self.cache.mkdir(parents=True)
        self.dest = self.root / "m0/data/contracts"
        self.response = {"runtimeMatch": "exact_match", "creationMatch": "exact_match",
                         "compilation": {"language": "Solidity", "name": "Victim"},
                         "sources": {"src/Victim.sol": {"content": "// SPDX-License-Identifier: MIT\r\ncontract Victim {}\r\n"}}}

    def write_cache(self):
        raw = json.dumps(self.response).encode()
        body = self.cache / "test.body"
        body.write_bytes(raw)
        meta = {"url": "https://sourcify.dev/server/v2/contract/1/0x" + "1" * 40 + "?fields=sources,compilation",
                "status": 200, "body_path": str(body), "sha256": module.digest(raw),
                "bytes": len(raw), "fetched_at": "2026-10-23T00:00:00Z"}
        (self.cache / "test.json").write_text(json.dumps(meta))
        return body

    def test_exact_bytes_and_repeat_are_preserved(self):
        self.write_cache()
        result = module.materialize(self.cache, self.dest, self.root)
        source = result["contracts"][0]["source_files"][0]
        raw = (self.root / source["local_path"]).read_bytes()
        self.assertEqual(raw, self.response["sources"]["src/Victim.sol"]["content"].encode())
        self.assertEqual(source["line_count"], 2)
        self.assertEqual(source["sha256"], module.digest(raw))
        self.assertEqual(module.materialize(self.cache, self.dest, self.root), result)
        self.assertNotIn("content", json.dumps(result))

    def test_unsafe_units_and_destination_rejected(self):
        for name in ("../outside.sol", "/outside.sol", "src/../outside.sol", "src\\outside.sol"):
            with self.assertRaises(ValueError):
                module.safe_unit(name)
        self.write_cache()
        with self.assertRaises(ValueError):
            module.materialize(self.cache, self.root / "publishable", self.root)

    def test_absolute_compiler_units_are_namespaced_without_rewriting_identifiers(self):
        content = "contract Victim {}\n"
        self.response["sources"] = {"/E/Defi/Victim.sol": {"content": content}}
        self.write_cache()
        result = module.materialize(self.cache, self.dest, self.root)
        source = result["contracts"][0]["source_files"][0]
        self.assertEqual(source["source_unit"], "/E/Defi/Victim.sol")
        self.assertIn("/_absolute_source_units/E/Defi/Victim.sol", source["local_path"])
        self.assertEqual((self.root / source["local_path"]).read_bytes(), content.encode())
        self.response["sources"]["_absolute_source_units/E/Defi/Victim.sol"] = {"content": content}
        self.write_cache()
        with self.assertRaises(ValueError):
            module.materialize(self.cache, self.dest, self.root)

    def test_cache_integrity_and_source_match_required(self):
        body = self.write_cache()
        body.write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            module.materialize(self.cache, self.dest, self.root)
        self.response["runtimeMatch"] = None
        self.write_cache()
        with self.assertRaises(ValueError):
            module.materialize(self.cache, self.dest, self.root)

    def test_existing_snapshot_and_symlink_not_overwritten(self):
        self.write_cache()
        result = module.materialize(self.cache, self.dest, self.root)
        path = self.root / result["contracts"][0]["source_files"][0]["local_path"]
        path.write_text("changed")
        with self.assertRaises(ValueError):
            module.materialize(self.cache, self.dest, self.root)
        path.unlink()
        outside = self.root / "outside"
        outside.write_text("untouched")
        path.symlink_to(outside)
        with self.assertRaises(ValueError):
            module.materialize(self.cache, self.dest, self.root)
        self.assertEqual(outside.read_text(), "untouched")

    def test_archive_rejects_write_methods_and_non_getter_calls(self):
        for query in (
            {"id": "unsafe", "method": "eth_sendRawTransaction", "params": ["0x00"]},
            {"id": "unsafe", "method": "eth_call", "params": [{"to": "0x" + "1" * 40, "data": "0xdeadbeef"}, "0x123"]},
            {"id": "../escape", "method": "eth_getCode", "params": ["0x" + "1" * 40, "0x123"]},
        ):
            with self.assertRaises(ValueError):
                archive.check_query(query)
        archive.check_query({"id": "safe", "method": "eth_getStorageAt", "params": ["0x" + "1" * 40, "0x1c", "0x123"]})

    def test_archive_dry_run_does_not_read_credentials_or_network(self):
        plan = self.root / "plan.json"
        plan.write_text(json.dumps({"queries": [{"id": "code", "method": "eth_getCode", "params": ["0x" + "1" * 40, "0x123"]}]}))
        with patch.object(sys, "argv", ["read_archive.py", "--plan", str(plan)]), patch.object(archive, "load_url") as credentials, patch.object(archive, "rpc") as network, contextlib.redirect_stdout(io.StringIO()):
            archive.main()
        credentials.assert_not_called()
        network.assert_not_called()

    def test_archive_error_text_with_secret_is_not_returned(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit):
                return json.dumps({"jsonrpc": "2.0", "id": 1, "error": {"code": -1, "message": "secret https://example.com/TOKEN"}}).encode()
        class Opener:
            def open(self, request, timeout): return Response()
        with patch.object(archive.urllib.request, "build_opener", return_value=Opener()):
            result = archive.rpc("https://example.com/TOKEN", "eth_chainId", [])
        self.assertNotIn("TOKEN", json.dumps(result))
        self.assertNotIn("example.com", json.dumps(result))
        self.assertEqual(result["error_code"], -1)

    def test_runtime_equality_is_checked_against_actual_evidence(self):
        path = self.cache / "archive.json"
        addr = "0x" + "1" * 40
        raw = json.dumps({"query": {"method": "eth_getCode", "params": [addr, "0x123"]}, "result": "0x6000"}).encode()
        path.write_bytes(raw)
        comparison = {"address": addr, "block_tag": "0x123", "equal": True,
                      "historical_runtime_sha256": module.digest(bytes.fromhex("6000")),
                      "sourcify_runtime_sha256": module.digest(bytes.fromhex("6000")),
                      "evidence_path": path.relative_to(self.root).as_posix(), "evidence_sha256": module.digest(raw)}
        validator.check_runtime_comparison(self.root, comparison, {"runtimeBytecode": {"onchainBytecode": "0x6000"}})
        with self.assertRaises(ValueError):
            validator.check_runtime_comparison(self.root, comparison, {"runtimeBytecode": {"onchainBytecode": "0x6001"}})
        comparison["block_tag"] = "0x124"
        with self.assertRaises(ValueError):
            validator.check_runtime_comparison(self.root, comparison, {"runtimeBytecode": {"onchainBytecode": "0x6000"}})


if __name__ == "__main__":
    unittest.main()
