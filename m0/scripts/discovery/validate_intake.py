"""Verify saved intake metadata and local source evidence, without any network."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def checked_read(repo, path, expected):
    repo = repo.resolve()
    file = repo / path
    if file.is_symlink() or not file.resolve().is_relative_to(repo):
        raise ValueError("evidence path escapes repository")
    raw = file.read_bytes()
    if sha(raw) != expected:
        raise ValueError(f"evidence hash mismatch: {path}")
    return raw


def check_runtime_comparison(repo, comparison, source_response):
    row = json.loads(checked_read(repo, comparison["evidence_path"], comparison["evidence_sha256"]))
    expected = source_response["runtimeBytecode"]["onchainBytecode"]
    actual = row.get("result")
    query = row.get("query") or {}
    if not (query.get("method") == "eth_getCode" and query.get("params") == [comparison["address"], comparison["block_tag"]]
            and isinstance(actual, str) and actual.lower() == expected.lower() and comparison["equal"] is True
            and sha(bytes.fromhex(actual[2:])) == comparison["historical_runtime_sha256"]
            and sha(bytes.fromhex(expected[2:])) == comparison["sourcify_runtime_sha256"]):
        raise ValueError("historical runtime comparison does not match its evidence")


def validate(repo, folder):
    repo, folder = repo.resolve(), folder.resolve()
    manifest = json.loads((folder / "manifest.json").read_text())
    for name, expected in manifest["artifacts"].items():
        if Path(name).name != name or sha((folder / name).read_bytes()) != expected:
            raise ValueError(f"manifest artifact mismatch: {name}")
    for name, key in (("all_incidents.csv", "baseline_all_catalog_sha256"),
                      ("ethereum_incidents.csv", "baseline_ethereum_catalog_sha256")):
        if sha((repo / "m0/catalog" / name).read_bytes()) != manifest[key]:
            raise ValueError("baseline catalog changed since intake")
    inventory = json.loads((folder / "sources.json").read_text())["contracts"]
    sources = {}
    comparison_ids = set()
    for contract in inventory:
        response = json.loads(checked_read(repo, contract["response_path"], contract["response_sha256"]))
        if contract["runtime_match"] != response["runtimeMatch"]:
            raise ValueError("source verification metadata mismatch")
        comparisons = contract.get("historical_runtime_comparisons", [])
        if contract["historical_runtime_compared"] != bool(comparisons):
            raise ValueError("historical comparison flag lacks evidence")
        for comparison in comparisons:
            if comparison["address"] != contract["address"] or comparison["source_response_sha256"] != contract["response_sha256"]:
                raise ValueError("historical comparison points to wrong source")
            check_runtime_comparison(repo, comparison, response)
            comparison_ids.add(comparison["query_id"])
        for f in contract["source_files"]:
            raw = checked_read(repo, f["local_path"], f["sha256"])
            if raw != response["sources"][f["source_unit"]]["content"].encode():
                raise ValueError("source bytes differ from verifier response")
            if len(raw) != f["bytes"] or len(raw.decode().splitlines()) != f["line_count"]:
                raise ValueError("source length metadata mismatch")
            sources[contract["address"], f["source_unit"]] = f, raw
    history = json.loads((folder / "historical_checks.json").read_text())
    if comparison_ids != {c["query_id"] for c in history["runtime_comparisons"]} or len(comparison_ids) != manifest["historical_runtime_comparisons_equal"]:
        raise ValueError("historical comparison count or inventory mismatch")
    for observation in history["state_observations"]:
        row = json.loads(checked_read(repo, observation["evidence_path"], observation["evidence_sha256"]))
        if row["query"] != observation["query"] or row.get("result") != observation["result"]:
            raise ValueError("historical state observation differs from cached response")
    for failure in history["failures"]:
        row = json.loads(checked_read(repo, failure["evidence_path"], failure["evidence_sha256"]))
        if "result" in row or row.get("error_code") != failure["error_code"]:
            raise ValueError("failed read was incorrectly represented")
    records = [json.loads(line) for line in (folder / "incidents.proposed.jsonl").read_text().splitlines()]
    if len(records) != manifest["incident_count"] or len({r["incident_id"] for r in records}) != len(records):
        raise ValueError("missing or duplicate incident record")
    total_transactions = 0
    for r in records:
        # Prior-block observations exist; exact transaction state and human
        # labels remain unverified. Prevent accidental promotion.
        if r["human_verified"] or r["training_eligible"] or r["evaluation_eligible"] or r["benchmark_promoted"] or r["historical_source_binding_confirmed"]:
            raise ValueError("this proposed intake cannot be promoted without a separately reviewed evidence update")
        if r["first_seen_at"] is not None or r["split"] != "unassigned" or r["family_id"] is not None:
            raise ValueError("unreviewed chronological/family assignment")
        for binding in r.get("preblock_binding_evidence", []):
            row = json.loads(checked_read(repo, binding["evidence_path"], binding["evidence_sha256"]))
            if row["query"]["id"] != binding["query_id"] or row.get("result") != binding["result"]:
                raise ValueError("incident binding differs from archived evidence")
        for failure in r.get("source_recovery_failures", []):
            checked_read(repo, failure["evidence_path"], failure["evidence_sha256"])
        for job in r.get("source_recovery_jobs", []):
            row = json.loads(checked_read(repo, job["evidence_path"], job["evidence_sha256"]))
            body = row["body"]
            if not (row["http_status"] == 200 and row["method"] == "GET"
                    and row["address"] == job["address"]
                    and body["verificationId"] == job["verification_id"]
                    and body["isJobCompleted"] is job["completed"] is True
                    and body.get("error", {}).get("customCode") == job["result"] == "no_similar_match_found"):
                raise ValueError("source recovery job differs from its terminal evidence")
        for tx in r["transactions"]:
            receipt = json.loads(checked_read(repo, tx["receipt_evidence"]["response_path"], tx["receipt_evidence"]["sha256"]))["result"]
            header = json.loads(checked_read(repo, tx["header_evidence"]["response_path"], tx["header_evidence"]["sha256"]))["result"]
            stamp = datetime.fromtimestamp(int(header["timestamp"], 16), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if not (receipt["transactionHash"] == tx["hash"] and receipt["status"] == "0x1"
                    and header["hash"] == receipt["blockHash"] == tx["block_hash"]
                    and int(header["number"], 16) == int(receipt["blockNumber"], 16) == tx["block_number"]
                    and int(receipt["transactionIndex"], 16) == tx["transaction_index"]
                    and header["transactions"][tx["transaction_index"]] == tx["hash"]
                    and stamp == tx["timestamp_utc"]):
                raise ValueError("transaction/header metadata disagreement")
            total_transactions += 1
        for loc in r["proposed_locations"]:
            f, raw = sources[loc["address"], loc["source_unit"]]
            lines = raw.decode().splitlines()
            start, end = loc["evidence_line_start"], loc["evidence_line_end"]
            if not (loc["source_sha256"] == f["sha256"] and type(start) is int and type(end) is int and 1 <= start <= end <= len(lines)):
                raise ValueError("invalid proposed source location")
            if not re.search(r"\b" + re.escape(loc["function"]) + r"\b", "\n".join(lines[start - 1:end])):
                raise ValueError("function missing from cited evidence lines")
            if loc["label_status"] != "proposed" or loc["adjudication"] != "unresolved":
                raise ValueError("unreviewed label changed status")
    if total_transactions != manifest["successful_transactions_verified"]:
        raise ValueError("transaction count mismatch")
    return len(records), total_transactions, len(sources)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    p.add_argument("--folder", type=Path, default=Path("m0/discovery/intake"))
    args = p.parse_args()
    try:
        records, txs, sources = validate(args.repo, args.folder)
    except (OSError, ValueError, KeyError, TypeError) as error:
        p.exit(1, f"Invalid intake: {error}\n")
    print(f"Verified {records} proposed incident records, {txs} receipt/header pairs, {sources} source files and saved archive comparisons. Exact-transaction and human-review gates remain open.")


if __name__ == "__main__":
    main()
