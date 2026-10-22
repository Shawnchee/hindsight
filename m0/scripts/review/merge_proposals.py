"""Merge and validate LLM label proposals into m0/review/proposals.jsonl.

Usage (from repo root):
  python3 -I m0/scripts/review/merge_proposals.py m0/review/proposals.part*.jsonl
Checks every enum against the review CLI's taxonomy, the address format, and that each
explains_findings entry points at a real Slither finding in the prepared data. Invalid
values are dropped with a warning; the reviewer still sees the rest of the proposal.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from review import IMPACTS, MECHANISMS, PREPARED, PROPOSALS, ROOT_CAUSES  # noqa: E402

ADDR = re.compile(r"^0x[0-9a-f]{40}$")
ROLES = {"defect", "entry_point", "affected"}


def clean(p):
    warn = []
    for field, allowed in (("root_cause", ROOT_CAUSES), ("mechanism", MECHANISMS), ("impact", IMPACTS)):
        vals = p.get(field) or []
        bad = [v for v in vals if v not in allowed]
        if bad:
            warn.append(f"{field}: dropped {bad}")
        p[field] = [v for v in vals if v in allowed]
    addrs = [a.lower() for a in p.get("victim_addresses") or []]
    if any(not ADDR.match(a) for a in addrs):
        warn.append("victim_addresses: dropped malformed")
    p["victim_addresses"] = [a for a in addrs if ADDR.match(a)]
    p["locations"] = [l for l in p.get("locations") or [] if l.get("raw") and l.get("role", "defect") in ROLES]
    prep_path = os.path.join(PREPARED, p["incident_id"] + ".json")
    dets = {}
    if os.path.exists(prep_path):
        for c in json.load(open(prep_path))["candidates"]:
            dets[c["address"]] = len(c.get("detectors") or [])
    ok = []
    for e in p.get("explains_findings") or []:
        cand = (e.get("candidate") or "").lower()
        if cand in dets and isinstance(e.get("detector_index"), int) and 0 <= e["detector_index"] < dets[cand]:
            ok.append({"candidate": cand, "detector_index": e["detector_index"]})
        else:
            warn.append(f"explains_findings: dropped {e}")
    p["explains_findings"] = ok
    return p, warn


def main():
    merged = {}
    for path in sys.argv[1:]:
        for n, line in enumerate(open(path), 1):
            if not line.strip():
                continue
            try:
                p = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"{path}:{n}: invalid JSON ({e}); skipped")
                continue
            p, warn = clean(p)
            for w in warn:
                print(f"{p['incident_id']}: {w}")
            merged[p["incident_id"]] = p
    with open(PROPOSALS, "w") as f:
        for iid in sorted(merged):
            f.write(json.dumps(merged[iid]) + "\n")
    print(f"wrote {len(merged)} proposals to {os.path.relpath(PROPOSALS)}")


if __name__ == "__main__":
    main()
