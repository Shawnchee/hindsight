"""Layer verified research supplements over the original metadata export, offline.

This produces research records only. It never promotes cases, infers human
approval, executes downloaded source, or changes an existing snapshot.
"""
import argparse
from datetime import date
import importlib.util
import json
from pathlib import Path
import re


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


base = module("export_research")


def checked(repo, relative, expected=None):
    path = repo / relative
    if path.is_symlink() or not path.resolve().is_relative_to(repo.resolve()):
        raise ValueError("evidence path escapes repository")
    raw = path.read_bytes()
    if expected is not None and base.sha(raw) != expected:
        raise ValueError("supplement evidence hash mismatch")
    return raw


def verify_supplement_manifest(repo, relative, manifest):
    required = {"sources.json", "incidents.followup.jsonl", "historical_checks.json"}
    required.update(name for name in ("label_events.jsonl", "ASTRA_REVIEW.json")
                    if (repo / relative / name).exists())
    if not required.issubset(manifest["artifacts"]):
        raise ValueError("supplement manifest omits consumed metadata")
    result = {}
    for name, expected in manifest["artifacts"].items():
        if Path(name).name != name:
            raise ValueError("supplement manifest must use flat artifact names")
        result[str(relative / name)] = base.sha(checked(repo, str(relative / name), expected))
    return result


def merge_incident(incident, supplement, available):
    """Add evidence without dropping an existing branch or asserting approval."""
    for key in ("human_verified", "training_eligible", "evaluation_eligible", "benchmark_promoted"):
        if supplement.get(key) is not False:
            raise ValueError("supplement must retain research-only gates")
    if (supplement.get("label_status"), supplement.get("adjudication")) != ("proposed", "unresolved"):
        raise ValueError("supplement cannot adjudicate research labels")
    if any(supplement.get(k) is not None for k in ("first_seen_at", "family_id")) or supplement.get("split") != "unassigned":
        raise ValueError("supplement cannot assign chronology or family partitions")
    if supplement.get("exact_transaction_state_verified") is not False:
        raise ValueError("exact transaction execution remains unverified")
    merged = json.loads(json.dumps(incident))
    locations = merged["proposed_locations"]
    for loc in supplement["proposed_locations"]:
        identity = (loc["address"], loc["source_unit"], loc["function"], loc["role"])
        if any((x["address"], x["source_unit"], x["function"], x["role"]) == identity for x in locations):
            raise ValueError("overlapping location requires explicit reconciliation")
        locations.append(loc)
    additions = supplement.get("recovered_contracts", [])
    # The first recovery packet predates recovered_contracts; these fields are
    # explicit deployment bindings, not addresses inferred from article text.
    for key in ("proxy", "implementation", "external_pricing_proxy", "external_pricing_implementation"):
        if key in supplement:
            additions = [*additions, {"address": supplement[key], "role": key}]
    for c in additions:
        address = c["address"]
        if address not in available:
            raise ValueError("recovered component lacks verified source inventory")
        if not any(x["address"] == address for x in merged["contracts"]):
            source = available[address]
            merged["contracts"].append({"address": address, "role": c["role"],
                "contract_name": source["contract_name"], "source_verification": source["runtime_match"]})
    merged.setdefault("recovery_supplements", []).append({
        k: supplement[k] for k in ("scope", "summary", "resolution", "remaining_gaps") if k in supplement})
    merged["source_coverage"] = {"proposed_defect_files_present": any(x["role"] == "defect" for x in locations),
                                 "complete_incident_source_confirmed": False}
    # Keep older gap statements as dated provenance rather than silently
    # claiming every previous economic/execution limitation has been resolved.
    merged.setdefault("historical_coverage_gaps", merged.pop("coverage_gaps", []))
    merged["coverage_gaps"] = list(dict.fromkeys(
        [g for s in merged["recovery_supplements"] for g in s.get("remaining_gaps", [])]))
    if supplement.get("summary"):
        original = merged.setdefault("original_intake_summary", merged["summary"])
        current_original = original.replace(
            "Retain one proposed xBNT path-validation composition only.",
            "The xBNT branch has one proposed path-validation composition.").replace(
            "xSNXa is report-only missing source, not a second source-backed finding.",
            "xBNT and recovered xSNXa are distinct proposals within this incident.")
        if not any(x["role"] == "defect" for x in incident["proposed_locations"]):
            current_original = "Previously a source-gap record."
        merged["summary"] = current_original + " Recovery follow-up: " + " ".join(s["summary"] for s in merged["recovery_supplements"])
    return merged


def build(repo, version, folders, recorded_at):
    date.fromisoformat(recorded_at)
    payload, metadata = base.build(repo, version)
    incidents = {r["incident_id"]: r for r in map(json.loads, payload["incidents.jsonl"].decode().splitlines())}
    contracts = {c["address"]: c for c in map(json.loads, payload["contracts.jsonl"].decode().splitlines())}
    provenance = json.loads(payload["input_hashes.json"])
    events = list(map(json.loads, payload["label_events.jsonl"].decode().splitlines()))
    for relative in folders:
        folder = repo / relative
        manifest = json.loads(checked(repo, str(relative / "manifest.json")))
        provenance.update(verify_supplement_manifest(repo, relative, manifest))
        provenance[str(relative / "manifest.json")] = base.sha((folder / "manifest.json").read_bytes())
        for c in json.loads((folder / "sources.json").read_text())["contracts"]:
            response = json.loads(checked(repo, c["response_path"], c["response_sha256"]))
            runtime = bytes.fromhex(response["runtimeBytecode"]["onchainBytecode"][2:])
            comparison = c["historical_comparison"]
            e = comparison["rpc_evidence"]
            historical = json.loads(checked(repo, e["path"], e["sha256"]))
            if (historical.get("chain_id") != 1 or comparison["runtime_equal"] is not True
                    or runtime != bytes.fromhex(historical["result"][2:])
                    or comparison["runtime_sha256"] != base.sha(runtime)
                    or historical["query"]["method"] != "eth_getCode"
                    or historical["query"]["params"] != [c["address"], hex(comparison["block"])]
                    or int(c["deployment"]["blockNumber"]) > comparison["block"]):
                raise ValueError("historical source selection is not corroborated")
            if c["address"] in contracts:
                raise ValueError("duplicate deployment needs explicit reconciliation")
            for f in c["source_files"]:
                checked(repo, f["local_path"], f["sha256"])
                if f["source_unit"] not in response["sources"] or base.sha(response["sources"][f["source_unit"]]["content"].encode()) != f["sha256"]:
                    raise ValueError("source unit differs from provider snapshot")
            contracts[c["address"]] = {k: c[k] for k in (
                "address", "chain_id", "contract_name", "fully_qualified_name", "compiler_version",
                "compiler_settings", "runtime_match", "creation_match", "deployment", "source_url")}
            contracts[c["address"]].update({"record_retrieved_at": c["retrieved_at"],
                "source_response_sha256": c["response_sha256"], "provider_verified_at": response.get("verifiedAt"),
                "source_available_at_incident_confirmed": False, "runtime_sha256": base.sha(runtime),
                "historical_runtime_comparisons": [{k: comparison[k] for k in ("block", "runtime_equal", "runtime_sha256")}],
                "source_files": [{k: f[k] for k in ("source_unit", "sha256", "bytes", "line_count", "spdx_mentions")} for f in c["source_files"]]})
        for s in base.rows(folder / "incidents.followup.jsonl"):
            if s["incident_id"] not in incidents:
                raise ValueError("supplement refers to unknown incident")
            incidents[s["incident_id"]] = merge_incident(incidents[s["incident_id"]], s, contracts)
        if (folder / "label_events.jsonl").exists():
            events.extend(base.portable(base.rows(folder / "label_events.jsonl")))
    incident_rows = sorted(incidents.values(), key=lambda r: r["incident_id"])
    contract_rows = sorted(contracts.values(), key=lambda c: c["address"])
    base.validate_records(incident_rows, contract_rows,
        list(map(json.loads, payload["disclosures.jsonl"].decode().splitlines())), json.loads(payload["families.proposed.json"]))
    latest_review = repo / "m0/discovery/review/ASTRA_REVIEW.json"
    if latest_review.exists():
        report_raw = checked(repo, str(latest_review.relative_to(repo)))
        report = json.loads(report_raw)
        if report.get("human_verified") is not False or report.get("adjudication") != "unresolved":
            raise ValueError("AI evidence review cannot supply human adjudication")
        reviewed = {r["incident_id"] for r in report["incidents"]}
        summaries = [r for r in map(json.loads, payload["review_summaries.jsonl"].decode().splitlines())
                     if r["incident_id"] not in reviewed]
        summaries.extend({"incident_id": r["incident_id"], "reviewer_model": "gpt-6-astra",
            "reasoning_effort": "low", "decision": r["ai_decision"], "rationale": r["rationale"],
            "human_verified": False, "limitations": r["material_remaining_gaps"],
            "review_report_sha256": base.sha(report_raw)} for r in report["incidents"])
        payload["review_summaries.jsonl"] = base.jsonl(summaries)
        provenance[str(latest_review.relative_to(repo))] = base.sha(report_raw)
        correction_path = latest_review.with_name("label_events.jsonl")
        if correction_path.exists():
            correction_raw = checked(repo, str(correction_path.relative_to(repo)))
            provenance[str(correction_path.relative_to(repo))] = base.sha(correction_raw)
            events.extend(map(json.loads, correction_raw.decode().splitlines()))
    for relative in folders:
        review_path = repo / relative / "ASTRA_REVIEW.json"
        if review_path.exists():
            report_raw = review_path.read_bytes()
            report = json.loads(report_raw)
            # Repository/scratch input paths stay local; the original report
            # hash still pins the independently reviewed evidence packet.
            report = {k: v for k, v in report.items() if k not in {"pins", "input_hashes", "input_artifact_hashes"}}
            report["original_review_report_sha256"] = base.sha(report_raw)
            payload[relative.name + "_review.json"] = base.encoded(base.portable(report))
    groups = json.loads(payload["families.proposed.json"])
    groups["supplemental_analysis_limit"] = (
        "Original provisional cohorts retained. Supplemental dependencies and new spans "
        "have not received complete cross-catalog semantic clone/family clearance.")
    payload["families.proposed.json"] = base.encoded(groups)
    payload.update({"incidents.jsonl": base.jsonl(incident_rows), "contracts.jsonl": base.jsonl(contract_rows),
                    "label_events.jsonl": base.jsonl(events), "input_hashes.json": base.encoded(provenance)})
    payload["README.md"] = f"""# Hindsight research snapshot {version}

Recorded {recorded_at}. This offline metadata-only snapshot combines the original
intakes with explicit recovery supplements. It has {len(incident_rows)} incidents,
{sum(r['source_coverage']['proposed_defect_files_present'] for r in incident_rows)}
with proposed defect source, and {len(contract_rows)} component snapshots.
Component counts are not counts of vulnerable contracts. Older v0.1.0 is unchanged.

All findings are AI-proposed/unresolved; human verification and training/evaluation
eligibility remain false. No benchmark promotion or model test is implied.
Recovery summaries and current gaps are separate from historical intake gaps;
May xToken includes distinct xBNT and xSNXa proposals within one incident.
bZx remains a source gap. Complete incident coverage and exact transaction
execution remain unproved even where source has been recovered.

Publication dates are observations, not established earliest disclosures.
first_seen_at and family_id remain null and splits unassigned. Provisional cohorts
are not confirmed exploit families. Source availability at incident time and
distribution rights still need review. Do not use this as a sealed benchmark or
training set. Research supplements do not modify the separate post-cutoff pool.

Source is distributed as addresses and hashes only. `fetch_source.py` is the same
bounded single-contract fetch helper as v0.1.0. Run it offline first:
`python3 -I fetch_source.py --address 0x833e440332caa07597a5116fbb6163f0e15f743d`.
Only an explicit `--execute --out /absolute/new-gitignored-directory` fetches source;
it checks hashes and never builds or executes source. Provider changes can cause
reproduction to fail; do not substitute changed source silently.

manifest.json pins payloads; input_hashes.json pins repository metadata inputs.
Verify using `python3 -I m0/scripts/discovery/export_research.py --verify PATH`.
Changed input requires a new version/directory. No article/post bodies, contract
source or credentials are shipped. Own distribution license remains unselected;
flattened SPDX mentions do not grant blanket source permissions. DeFiHackLabs
catalog attribution: Apache-2.0, commit23c7bd8; retain LICENSE/NOTICE obligations.
This export is local; it has not been published, committed or pushed.
""".encode()
    for name, raw in payload.items():
        if str(repo).encode() in raw or b'"local_path":' in raw or b'"content":' in raw:
            raise ValueError("nonportable or raw source content in export: " + name)
    backed = sum(r["source_coverage"]["proposed_defect_files_present"] for r in incident_rows)
    metadata.update({"recorded_at": recorded_at, "source_backed_proposal_count": backed,
        "source_gap_record_count": len(incident_rows) - backed, "contract_snapshots": len(contract_rows),
        "source_unit_hashes": sum(len(c["source_files"]) for c in contract_rows), "supplements": list(map(str, folders))})
    return payload, metadata


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    p.add_argument("--version", required=True)
    p.add_argument("--recorded-at", required=True)
    p.add_argument("--supplement", action="append", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    try:
        if not re.fullmatch(r"v\d+\.\d+\.\d+", args.version):
            raise ValueError("semantic version required")
        payload, metadata = build(args.repo.resolve(), args.version, args.supplement, args.recorded_at)
        base.write_snapshot(args.out, payload, metadata)
        result = base.verify_snapshot(args.out)
        print(f"Verified research snapshot {result['version']}: {result['incident_count']} incidents, {result['contract_snapshots']} component snapshots; research only.")
    except (OSError, ValueError, KeyError, TypeError) as e:
        p.exit(1, f"Current research export failed: {e}\n")


if __name__ == "__main__":
    main()
