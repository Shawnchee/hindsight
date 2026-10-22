"""Score runs on the B2 v2 blind pool (post-cutoff exploits plus clean audited contracts).

Changes after the 2026-10-23 audit:
  - Locations match on (file basename, function). Wrong.sol:withdraw no longer matches Victim.sol:withdraw.
  - "strict" truth = defect locations only; "lenient" also accepts entry points.
  - Exploit cases are split into source-complete (every defect file is in the input) and incomplete,
    so source-recovery failures aren't counted as detection failures.
  - A clean-case flag is a false positive only if its top-1 location is inside the deployed target's
    import closure. Flags on unrelated bundled files are reported separately as out-of-scope.
  - Submissions are validated: unknown, duplicate or malformed cases are an error, and missing cases are
    reported as abstentions, never silently counted as "no bug".

Usage (from repo root):
  python3 -I m0/scripts/b2/score_v2.py --out OUT.md run1 'm0/b2/v2/b2v2.part*.jsonl' [run2 'glob' ...]
Each run is a label followed by a quoted glob.
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
from scope import hit, loc_key, truth_keys  # noqa: E402

CASE_MAP = os.path.join(REPO, "m0", "data", "b2v2", "case_map.json")
REVIEWS = os.path.join(REPO, "m0", "review", "postcutoff", "reviews.llm.jsonl")
STRICT, LENIENT = ("defect",), ("defect", "entry_point")


def load_run(pattern, case_ids):
    preds, errors = {}, []
    for path in sorted(glob.glob(pattern)):
        for n, line in enumerate(open(path), 1):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                errors.append(f"{path}:{n} invalid JSON")
                continue
            c = r.get("case_id")
            if c not in case_ids:
                errors.append(f"{path}:{n} unknown case_id {c!r}")
            elif c in preds:
                errors.append(f"{path}:{n} duplicate case_id {c}")
            elif not isinstance(r.get("exploitable_bug_found"), bool) or not isinstance(r.get("top5"), list) \
                    or r.get("confidence") not in ("high", "medium", "low"):
                errors.append(f"{path}:{n} malformed record for {c}")
            else:
                preds[c] = r
    return preds, errors


def score(preds, cm, rev):
    out = {"ex": [], "cl": []}
    for c, info in sorted(cm.items()):
        p = preds.get(c)
        keys = [k for k in (loc_key(x.get("location")) for x in (p or {}).get("top5", [])) if k]
        claims = bool(p) and p["exploitable_bug_found"] and p["confidence"] in ("high", "medium")
        any_claim = bool(p) and p["exploitable_bug_found"]
        if info["kind"] == "exploit":
            r = rev[info["id"]]
            ts, tl = truth_keys(r["locations"], STRICT), truth_keys(r["locations"], LENIENT)
            out["ex"].append({"id": info["id"], "answered": bool(p), "complete": info.get("source_complete", False),
                              "has_truth": bool(ts), "h1": hit(keys, ts, 1), "h5": hit(keys, ts, 5),
                              "h5_len": hit(keys, tl, 5), "claims": claims, "any": any_claim,
                              "correct": any_claim and hit(keys, ts, 1)})
        else:
            scope = {os.path.basename(f).lower() for f in info.get("files", [])}
            top_file = keys[0][0] if keys else None
            in_scope = top_file in scope if top_file else False
            out["cl"].append({"id": info["id"], "answered": bool(p), "claims": claims, "any": any_claim,
                              "fp": claims and in_scope, "fp_any": any_claim and in_scope,
                              "oos": any_claim and not in_scope})
    return out


def frac(rows, key, cond=lambda r: True):
    rows = [r for r in rows if cond(r)]
    return f"{sum(1 for r in rows if r[key])}/{len(rows)}"


def main():
    args = sys.argv[1:]
    out_path = None
    if "--out" in args:
        i = args.index("--out")
        out_path = os.path.abspath(args[i + 1])
        del args[i:i + 2]
    runs = list(zip(args[::2], args[1::2]))
    cm = json.load(open(CASE_MAP))
    rev = {json.loads(l)["incident_id"]: json.loads(l) for l in open(REVIEWS)}
    results, problems = [], []
    for label, pattern in runs:
        preds, errors = load_run(pattern, set(cm))
        problems += [f"[{label}] {e}" for e in errors]
        results.append((label, score(preds, cm, rev), len(cm) - len(preds)))
    if problems:
        print("\n".join(problems))
        sys.exit("invalid submission(s): fix the errors above before scoring")
    ex_t = lambda r: r["has_truth"]
    comp = lambda r: r["has_truth"] and r["complete"]
    rows = [
        ("Abstentions (missing cases)", lambda s, a: str(a)),
        ("Exploit flagged, med/high: all 23", lambda s, a: frac(s["ex"], "claims")),
        ("Exploit flagged, med/high: source-complete only", lambda s, a: frac(s["ex"], "claims", lambda r: r["complete"])),
        ("Exploit flagged, any confidence: all", lambda s, a: frac(s["ex"], "any")),
        ("Correct detection (flagged, top-1 = defect): all", lambda s, a: frac(s["ex"], "correct", ex_t)),
        ("Correct detection: source-complete only", lambda s, a: frac(s["ex"], "correct", comp)),
        ("Hit@1, defect (strict): all", lambda s, a: frac(s["ex"], "h1", ex_t)),
        ("Hit@5, defect (strict): all", lambda s, a: frac(s["ex"], "h5", ex_t)),
        ("Hit@5, defect (strict): source-complete only", lambda s, a: frac(s["ex"], "h5", comp)),
        ("Hit@5, defect or entry point (lenient): all", lambda s, a: frac(s["ex"], "h5_len", ex_t)),
        ("Clean FP, med/high, in target scope", lambda s, a: frac(s["cl"], "fp")),
        ("Clean FP, any confidence, in target scope", lambda s, a: frac(s["cl"], "fp_any")),
        ("Clean flags on out-of-scope bundled files", lambda s, a: frac(s["cl"], "oos")),
    ]
    L = ["# B2 v2 pool: scored with the corrected scorer (2026-10-23)", "",
         "Locations match on file basename plus function. \"Strict\" means defect locations only. Clean false "
         "positives count only flags inside the deployed target's import closure. Ground truth is LLM labels "
         "(blind Fable 5.1, with Opus 5.5 as a second labeler), not human-verified. **Earlier runs saw unscoped "
         "inputs**, which included unrelated bundled files. They're rescored here, not rerun.", "",
         "| Metric | " + " | ".join(l for l, _, _ in results) + " |", "|---|" + "---|" * len(results)]
    for name, f in rows:
        L.append(f"| {name} | " + " | ".join(f(s, a) for _, s, a in results) + " |")
    n_comp = sum(1 for r in results[0][1]["ex"] if r["complete"])
    L += ["", f"Source-complete exploit cases: {n_comp} of {len(results[0][1]['ex'])}. The others lack the defect "
          "file (proxy-only, a missing facet or an unrecovered library), so no tool could localize them from the input."]
    text = "\n".join(L) + "\n"
    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w") as f:
            f.write(text)
    print(text)


if __name__ == "__main__":
    main()
