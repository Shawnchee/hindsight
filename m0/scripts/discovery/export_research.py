"""Create/verify a deterministic metadata-only research snapshot, entirely offline."""
import argparse
from datetime import date
import hashlib
import importlib.util
import json
from pathlib import Path
import re


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(obj):
    return (json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode()


def jsonl(rows):
    return ("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)).encode()


def rows(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def validate_records(incidents, contracts, disclosures, groups):
    ids = {r["incident_id"] for r in incidents}
    if not incidents or len(ids) != len(incidents):
        raise ValueError("missing or duplicate incident IDs")
    addresses = [c["address"] for c in contracts]
    if len(set(addresses)) != len(addresses):
        raise ValueError("duplicate contract deployment")
    for r in incidents:
        if any(r[k] is not False for k in ("human_verified", "training_eligible", "evaluation_eligible", "benchmark_promoted")):
            raise ValueError("research snapshot cannot assert approval or eligibility")
        if (r["label_status"], r["adjudication"], r["split"], r["family_id"], r["first_seen_at"]) != ("proposed", "unresolved", "unassigned", None, None):
            raise ValueError("research snapshot cannot fabricate adjudication, time splits or families")
        for loc in r["proposed_locations"]:
            candidates = [f for c in contracts if c["address"] == loc["address"] for f in c["source_files"]
                          if f["source_unit"] == loc["source_unit"] and f["sha256"] == loc["source_sha256"]]
            if len(candidates) != 1:
                raise ValueError("location lacks matching source metadata")
    if len(disclosures) != len(ids) or {r["incident_id"] for r in disclosures} != ids:
        raise ValueError("disclosure records do not cover the snapshot")
    for d in disclosures:
        date.fromisoformat(d["observed_publication_date"])
        if d["first_seen_at"] is not None or d["earliest_disclosure_confirmed"] is not False:
            raise ValueError("publication evidence is not an established earliest disclosure")
    members = [i for g in groups["groups"] for i in g["incident_ids"]]
    if len(members) != len(ids) or set(members) != ids:
        raise ValueError("provisional leakage groups must cover each incident exactly once")
    if any(g["exploit_family_confirmed"] is not False for g in groups["groups"]):
        raise ValueError("provisional cohorts are not proven exploit families")


def portable(value):
    """Drop machine-local acquisition references; preserve public source-unit IDs."""
    if isinstance(value, dict):
        return {k: portable(v) for k, v in value.items()
                if k not in {"local_path", "evidence_path", "response_path", "snapshot_path", "worker_packet_path"}}
    if isinstance(value, list):
        return [portable(v) for v in value]
    return value


def build(repo, version):
    spec = importlib.util.spec_from_file_location("intake_validator", Path(__file__).with_name("validate_intake.py"))
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    original, contracts, provenance, review_summaries, events = [], {}, {}, [], []
    for part in ("intake", "expansion"):
        folder = repo / "m0/discovery" / part
        checker.validate(repo, folder)
        original.extend(rows(folder / "incidents.proposed.jsonl"))
        for name in ("manifest.json", "incidents.proposed.jsonl", "sources.json", "historical_checks.json", "ASTRA_REVIEW.json"):
            path = folder / name
            provenance[path.relative_to(repo).as_posix()] = sha(path.read_bytes())
        for c in json.loads((folder / "sources.json").read_text())["contracts"]:
            response = json.loads((repo / c["response_path"]).read_text())
            key = c["address"]
            if key in contracts:
                raise ValueError("duplicate contract deployment needs explicit snapshot reconciliation")
            contracts[key] = {"address": key, "chain_id": c["chain_id"], "contract_name": c["contract_name"],
                "fully_qualified_name": c["fully_qualified_name"], "compiler_version": c["compiler_version"],
                "compiler_settings": c["compiler_settings"], "runtime_match": c["runtime_match"],
                "creation_match": c["creation_match"], "deployment": c["deployment"], "source_url": c["source_url"],
                "record_retrieved_at": c["retrieved_at"], "source_response_sha256": c["response_sha256"],
                "provider_verified_at": response.get("verifiedAt"),
                "source_available_at_incident_confirmed": False,
                "runtime_sha256": sha(bytes.fromhex(response["runtimeBytecode"]["onchainBytecode"][2:])),
                "historical_runtime_comparisons": portable(c.get("historical_runtime_comparisons", [])),
                "source_files": [{k: f[k] for k in ("source_unit", "sha256", "bytes", "line_count", "spdx_mentions")} for f in c["source_files"]]}
        review = json.loads((folder / "ASTRA_REVIEW.json").read_text())
        for r in review["incidents"]:
            review_summaries.append({"incident_id": r["incident_id"], "reviewer_model": review["reviewer_model"],
                "reasoning_effort": review["reasoning_effort"], "decision": r["decision"],
                "rationale": r.get("recommendation", r.get("rationale")), "human_verified": False,
                "limitations": review.get("limitations", []), "review_report_sha256": sha((folder / "ASTRA_REVIEW.json").read_bytes())})
        if "source_gap_only" in review:
            review_summaries.append({**review["source_gap_only"], "reviewer_model": review["reviewer_model"],
                                    "reasoning_effort": review["reasoning_effort"], "human_verified": False})
        if (folder / "label_events.jsonl").exists():
            events.extend(portable(rows(folder / "label_events.jsonl")))
    disclosures = rows(repo / "m0/discovery/curation/disclosures.jsonl")
    groups = json.loads((repo / "m0/discovery/curation/families.proposed.json").read_text())
    for name in ("disclosures.jsonl", "families.proposed.json"):
        path = repo / "m0/discovery/curation" / name
        provenance[path.relative_to(repo).as_posix()] = sha(path.read_bytes())
    contract_rows = sorted(contracts.values(), key=lambda c: c["address"])
    incidents = []
    for r in sorted(original, key=lambda r: r["incident_id"]):
        incident = {k: r[k] for k in ("incident_id", "candidate_id", "name", "chain_id", "incident_date", "summary",
            "label_status", "adjudication", "human_verified", "training_eligible", "evaluation_eligible", "benchmark_promoted",
            "first_seen_at", "family_id", "split", "source_coverage", "proposed_locations")}
        incident["transactions"] = [{k: t[k] for k in ("hash", "block_number", "block_hash", "transaction_index", "timestamp_utc")}
                                    for t in r["transactions"]]
        incident["contracts"] = [{k: c[k] for k in ("address", "role", "contract_name", "source_verification")} for c in r["sources"]]
        incident["primary_sources"] = r["primary_sources"]
        incident["coverage_gaps"] = r.get("gaps", []) + r.get("review_gaps", [])
        incident["exact_transaction_state_verified"] = False
        incident["provisional_leakage_group_id"] = next(g["leakage_group_id"] for g in groups["groups"] if r["incident_id"] in g["incident_ids"])
        if "parent_review_followup" in r:
            incident["post_review_evidence_followup"] = portable(r["parent_review_followup"])
        incidents.append(incident)
    validate_records(incidents, contract_rows, disclosures, groups)
    helper = Path(__file__).with_name("fetch_snapshot_source.py").read_bytes()
    payload = {"incidents.jsonl": jsonl(incidents), "contracts.jsonl": jsonl(contract_rows),
               "disclosures.jsonl": jsonl(disclosures), "families.proposed.json": encoded(groups),
               "review_summaries.jsonl": jsonl(review_summaries), "label_events.jsonl": jsonl(events),
               "discovery_leads.jsonl": (repo / "m0/discovery/expansion/social_leads.jsonl").read_bytes(),
               "fetch_source.py": helper, "input_hashes.json": encoded(provenance)}
    payload["README.md"] = f"""# Hindsight research snapshot {version}

Local metadata-only research export, recorded 2026-10-23. It contains {len(incidents)}
enriched incident records, {sum(r['source_coverage']['proposed_defect_files_present'] for r in incidents)}
with proposed defect source and two source gaps, plus {len(contract_rows)} contract
snapshots / {sum(len(c['source_files']) for c in contract_rows)} source-unit hashes.
Contract source and article/post bodies are not redistributed.

All labels remain AI-proposed/unresolved, with zero human approvals or training,
evaluation and benchmark eligibility. This is not a benchmark or a training-ready
dataset. `review_summaries.jsonl` records requested Astra low-effort reviews;
`label_events.jsonl` records the expansion's revisions. Earlier intake review
provenance is represented by its review report hash, not a fabricated edit log.

`disclosures.jsonl` contains ten directly inspected primary-page publication dates.
They are date-granularity observations, not proven earliest disclosures or UTC
timestamps; `first_seen_at` stays null. Source availability at incident time also
remains unproved. `families.proposed.json` has nine provisional split-blocking
groups: each incident stays together, and both xToken incidents share a conservative
protocol cohort. It does not claim one exploit family or complete clone clearance.
Shared libraries/wrappers and cited-span hashes are reported separately.

Historical code comparisons establish code at the recorded prior blocks. They
do not establish exact transaction prestate, complete economic context or a replay.
The source-backed May xToken proposal covers xBNT only; its xSNXa branch is missing.
bZx's primary module and August xToken's exact victim/source remain gaps.

## Reproduce one contract's source

Run from this directory. Dry-run first (offline):

```sh
python3 -I fetch_source.py --address 0x833e440332caa07597a5116fbb6163f0e15f743d
```

For one explicitly selected contract, add `--execute --out /absolute/new-local-directory`.
The helper makes one bounded Sourcify request, checks all source hashes and runtime
hash against this snapshot, and never builds/executes code or accesses credentials.
Use a gitignored output directory. It never loops over the snapshot: respect
Sourcify's single-contract fair-use policy. Provider changes can make reproduction
fail; do not silently substitute updated sources. No RPC URL or key is shipped.

## Integrity, provenance and rights

`manifest.json` hashes every payload file. `input_hashes.json` pins source metadata
and review inputs in the repository. To verify locally from the Hindsight project:
`python3 -I m0/scripts/discovery/export_research.py --verify /absolute/snapshot-directory`.
Regenerate using that script's `--out` and the same version; changed inputs require
a new snapshot directory. Existing differing snapshots are never overwritten.

This export was not published, committed or pushed. Hindsight's own distribution
license is still unselected. Upstream contract rights remain separate; SPDX mentions
can apply only to flattened dependencies and are not blanket release permissions.
DeFiHackLabs catalog provenance: Apache-2.0, upstream commit 23c7bd8; retain its
LICENSE/NOTICE obligations when distributing derived catalog material. New intake
summaries are our own, with original protocol/researcher URLs retained in each row.
Browser leads are discovery-only, with two new candidates and two catalog references.
""".encode()
    # Explicitly reject machine-specific paths or raw source payloads before writing.
    for name, raw in payload.items():
        if str(repo).encode() in raw or b'"content":' in raw or b'"local_path":' in raw:
            raise ValueError(f"nonportable/source content in export: {name}")
    backed = sum(r["source_coverage"]["proposed_defect_files_present"] for r in incidents)
    return payload, {"version": version, "recorded_at": "2026-10-23", "research_only": True,
        "incident_count": len(incidents), "source_backed_proposal_count": backed, "source_gap_record_count": len(incidents) - backed,
        "contract_snapshots": len(contract_rows), "source_unit_hashes": sum(len(c["source_files"]) for c in contract_rows),
        "publication_dates_recorded": len(disclosures), "provisional_leakage_groups": len(groups["groups"]),
        "human_verified_labels": 0, "point_in_time_ready": False, "training_eligible": False,
        "evaluation_eligible": False, "benchmark_promotions": 0, "contract_source_files_redistributed": 0}


def write_snapshot(out, payload, metadata):
    artifacts = {name: sha(raw) for name, raw in sorted(payload.items())}
    complete = {**payload, "manifest.json": encoded({**metadata, "artifacts": artifacts})}
    if any(Path(name).name != name for name in complete):
        raise ValueError("snapshot payload must contain flat file names")
    if out.exists():
        if out.is_symlink() or {p.name for p in out.iterdir()} != set(complete):
            raise ValueError("existing snapshot differs; choose a new version/directory")
        if any((out / name).read_bytes() != raw for name, raw in complete.items()):
            raise ValueError("refusing to overwrite a different snapshot")
        return
    out.mkdir(parents=True, exist_ok=False)
    for name, raw in complete.items():
        with (out / name).open("xb") as f:
            f.write(raw)


def verify_snapshot(out):
    manifest = json.loads((out / "manifest.json").read_text())
    for name, expected in manifest["artifacts"].items():
        path = out / name
        if Path(name).name != name or path.is_symlink() or sha(path.read_bytes()) != expected:
            raise ValueError("snapshot artifact mismatch")
    incidents, contracts = rows(out / "incidents.jsonl"), rows(out / "contracts.jsonl")
    disclosures, groups = rows(out / "disclosures.jsonl"), json.loads((out / "families.proposed.json").read_text())
    validate_records(incidents, contracts, disclosures, groups)
    actual = (len(incidents), len(contracts), sum(len(c["source_files"]) for c in contracts), len(disclosures), len(groups["groups"]))
    expected = tuple(manifest[k] for k in ("incident_count", "contract_snapshots", "source_unit_hashes", "publication_dates_recorded", "provisional_leakage_groups"))
    if actual != expected or manifest["research_only"] is not True or manifest["point_in_time_ready"] is not False:
        raise ValueError("snapshot counts or research status invalid")
    if (manifest["human_verified_labels"] != 0 or manifest["benchmark_promotions"] != 0
            or manifest["contract_source_files_redistributed"] != 0
            or manifest["training_eligible"] is not False or manifest["evaluation_eligible"] is not False):
        raise ValueError("research-only manifest gates changed")
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    p.add_argument("--version", default="v0.1.0")
    p.add_argument("--out", type=Path)
    p.add_argument("--verify", type=Path)
    args = p.parse_args()
    try:
        if args.verify:
            result = verify_snapshot(args.verify)
        else:
            if not args.out or not re.fullmatch(r"v\d+\.\d+\.\d+", args.version):
                raise ValueError("provide --out and a semantic vMAJOR.MINOR.PATCH version")
            payload, metadata = build(args.repo.resolve(), args.version)
            write_snapshot(args.out, payload, metadata)
            result = verify_snapshot(args.out)
        print(f"Verified research snapshot {result['version']}: {result['incident_count']} incidents, {result['contract_snapshots']} contract snapshots; no benchmark promotion.")
    except (OSError, ValueError, KeyError, TypeError) as error:
        p.exit(1, f"Research export failed: {error}\n")


if __name__ == "__main__":
    main()
