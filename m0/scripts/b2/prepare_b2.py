"""Build blind inputs for baseline B2 (frontier model, code only).

For each in-scope incident where the blind LLM review found victim source, copy only the
victim contracts' recovered source into m0/data/b2/inputs/<case_id>/<n>/. The folders are
renamed to opaque case IDs. No PoC, no labels, no Slither output, no incident name or date
goes in. Third-party library folders (OpenZeppelin etc.) are kept, because a real scan sees
them too.

Usage (from repo root):
  python3 -I m0/scripts/b2/prepare_b2.py
Writes m0/data/b2/inputs/ (gitignored) and m0/data/b2/case_map.json (case_id -> incident).
The case map is the answer key's index, so B2 agents must never read it.
"""
import hashlib
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
REVIEWS = os.path.join(REPO, "m0", "review", "reviews.llm.jsonl")
PREPARED = os.path.join(REPO, "m0", "data", "review", "prepared")
OUT = os.path.join(REPO, "m0", "data", "b2")


def main():
    if os.path.exists(os.path.join(OUT, "inputs")):
        shutil.rmtree(os.path.join(OUT, "inputs"))
    case_map = {}
    for line in open(REVIEWS):
        r = json.loads(line)
        if not r["in_scope"] or not r["slither_ran_on_victim"]:
            continue
        prep = json.load(open(os.path.join(PREPARED, r["incident_id"] + ".json")))
        cands = {c["address"]: c for c in prep["candidates"]}
        dirs = [os.path.join(REPO, cands[a]["source_dir"]) for a in r["victims"]
                if a in cands and cands[a].get("source_dir")]
        if not dirs:
            continue
        case = "case_" + hashlib.sha256(r["incident_id"].encode()).hexdigest()[:8]
        for n, d in enumerate(dirs, 1):
            shutil.copytree(d, os.path.join(OUT, "inputs", case, f"contract_{n}"))
        case_map[case] = r["incident_id"]
    with open(os.path.join(OUT, "case_map.json"), "w") as f:
        json.dump(case_map, f, indent=1)
    print(f"{len(case_map)} cases written to {os.path.relpath(OUT, REPO)}/inputs")
    print(" ".join(sorted(case_map)))


if __name__ == "__main__":
    main()
