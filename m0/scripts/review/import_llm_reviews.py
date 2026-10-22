"""Convert blind LLM reviews (m0/review/llm_review.part*.jsonl) into review records with the
same shape review.py writes. Then summarize.py can report on them.

Usage (from repo root):
  python3 -I m0/scripts/review/import_llm_reviews.py m0/review/llm_review.part*.jsonl
Writes m0/review/reviews.llm.jsonl. Human reviews stay in reviews.jsonl. The two are never mixed.
Every non-dependency Slither finding on the chosen victims gets a status:
explains or valid -> confirmed_valid, invalid -> confirmed_invalid, anything else -> unresolved.
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from merge_proposals import clean  # noqa: E402
from review import PREPARED, REPO, TAXONOMY_VERSION, is_dependency  # noqa: E402

OUT = os.path.join(REPO, "m0", "review", "reviews.llm.jsonl")
# DHL label mapped to the taxonomy. It's the "proposed" baseline that the summary compares against.
SAMPLE = {r["incident_id"]: {"root_cause": r["root_cause"], "mechanism": r["mechanism"]}
          for r in csv.DictReader(open(os.path.join(REPO, "m0", "catalog", "m0_sample.csv")))}


def keyset(entries):
    return {((e.get("candidate") or "").lower(), e.get("detector_index")) for e in entries or []}


def convert(r):
    r, warn = clean(dict(r))  # drops invalid enums, addresses and finding refs
    prep = json.load(open(os.path.join(PREPARED, r["incident_id"] + ".json")))
    cands = {c["address"]: c for c in prep["candidates"]}
    victims = r["victim_addresses"]
    explains, valid, invalid = (keyset(r.get(k)) for k in ("explains_findings", "valid_findings", "invalid_findings"))
    findings, ran = [], False
    for a in victims:
        c = cands.get(a)
        if not c or not c.get("slither_ok"):
            continue
        ran = True
        for i, f in enumerate(c.get("detectors") or []):
            if is_dependency(f):
                continue
            k = (a, i)
            status = ("confirmed_valid" if k in explains or k in valid
                      else "confirmed_invalid" if k in invalid else "unresolved")
            findings.append({"candidate": a, "detector_index": i, "check": f.get("check"), "impact": f.get("impact"),
                             "confidence": f.get("confidence"), "first_markdown": f.get("first_markdown"),
                             "functions": f.get("functions") or [], "status": status, "explains_exploit": k in explains})
    dropped = [k for k in explains if k[0] not in victims]
    if dropped:
        warn.append(f"explains_findings on non-victim candidates ignored: {dropped}")
    locs = []
    for l in r.get("locations") or []:
        file_, _, rest = l["raw"].partition(":")
        locs.append({"raw": l["raw"], "file": file_ if rest else None, "function": rest or None,
                     "role": l.get("role", "defect")})
    rec = {"incident_id": r["incident_id"], "reviewer": r.get("reviewer", "llm"), "taxonomy_version": TAXONOMY_VERSION,
           "victims": victims, "victims_manual": [a for a in victims if a not in cands],
           "proposed": SAMPLE.get(r["incident_id"], {}), "had_llm_proposal": False, "blind_llm_review": True,
           "in_scope": bool(r.get("in_scope")), "off_chain_reason": r.get("off_chain_reason"),
           "source_status": {a: ("bytecode_matched" if cands.get(a, {}).get("sourcify") == "full_match"
                                 else "explorer_verified" if cands.get(a, {}).get("sourcify") == "partial_match"
                                 else "none") for a in victims},
           "labels": {k: r.get(k) or [] for k in ("root_cause", "mechanism", "impact")},
           "violated_invariant": r.get("violated_invariant"), "locations": locs,
           "findings": findings, "slither_ran_on_victim": ran, "notes": r.get("notes"),
           "confidence": r.get("confidence"), "started_at": r.get("reviewed_at"), "ended_at": r.get("reviewed_at"),
           "wall_seconds": 0, "interrupted_seconds": 0, "review_seconds": 0}
    return rec, warn


def main():
    global OUT, PREPARED, SAMPLE
    args = sys.argv[1:]
    # optional overrides, e.g. for the post-cutoff set
    for flag in ("--out", "--prepared", "--sample"):
        if flag in args:
            i = args.index(flag)
            val = os.path.abspath(args[i + 1])
            del args[i:i + 2]
            if flag == "--out":
                OUT = val
            elif flag == "--prepared":
                PREPARED = val
            else:
                SAMPLE = {r["incident_id"]: {"root_cause": r.get("root_cause", ""), "mechanism": r.get("mechanism", "")}
                          for r in csv.DictReader(open(val))}
    import merge_proposals
    merge_proposals.PREPARED = PREPARED  # clean() validates detector indices against this folder
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    recs = {}
    for path in args:
        for line in open(path):
            if line.strip():
                rec, warn = convert(json.loads(line))
                for w in warn:
                    print(f"{rec['incident_id']}: {w}")
                recs[rec["incident_id"]] = rec
    with open(OUT, "w") as f:
        for iid in sorted(recs):
            f.write(json.dumps(recs[iid]) + "\n")
    print(f"wrote {len(recs)} records to {os.path.relpath(OUT, REPO)}")


if __name__ == "__main__":
    main()
