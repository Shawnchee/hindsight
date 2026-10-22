"""Score baseline B2 (frontier model, code only) and B0 (Slither's own top-5) against the blind
LLM review labels.

Ground truth per incident = function names of causal locations with role defect or entry_point,
taken from the Fable review (m0/review/reviews.llm.jsonl). The union with the Opus proposal
locations is reported as a second, more lenient key. Matching is by function name, case-insensitive.
Both keys are LLM labels, not human-verified (PRD REV-3).

Usage (from repo root):
  python3 -I m0/scripts/b2/score.py m0/b2/b2.part*.jsonl
Writes m0/b2/summary.md.
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(HERE, "..", "review"))
sys.path.insert(0, HERE)
from review import IMPACT_ORDER, PREPARED, is_dependency  # noqa: E402

CASE_MAP = os.path.join(REPO, "m0", "data", "b2", "case_map.json")
REVIEWS = os.path.join(REPO, "m0", "review", "reviews.llm.jsonl")
PROPOSALS = os.path.join(REPO, "m0", "review", "proposals.jsonl")
SAMPLE = os.path.join(REPO, "m0", "catalog", "m0_sample.csv")
OUT = os.path.join(REPO, "m0", "b2", "summary.md")
CONF_ORDER = {"High": 0, "Medium": 1, "Low": 2}
LATE = "2026-07-01"  # incidents on/after this are the most likely to be after the model's training cutoff


from scope import hit, loc_key  # noqa: E402  (file + function matching, fixed 2026-10-23)

fn = loc_key  # kept for older imports


def truth_from(locs):
    """Strict truth: defect locations only (entry points no longer count, per the 2026-10-23 audit)."""
    return {loc_key(l["raw"]) for l in locs or [] if l.get("role", "defect") == "defect"} - {None}


def slither_top5(victims, prep):
    cands = {c["address"]: c for c in prep["candidates"]}
    found = []
    for a in victims:
        for i, f in enumerate((cands.get(a) or {}).get("detectors") or []):
            if not is_dependency(f) and f.get("functions"):
                found.append((IMPACT_ORDER.get(f.get("impact"), 9), CONF_ORDER.get(f.get("confidence"), 9), i, f))
    found.sort(key=lambda x: x[:3])
    out = []
    for *_, f in found:
        file_ = os.path.basename((f.get("first_markdown") or "").split("#")[0]).lower()
        for name in f["functions"]:
            k = (file_, name.lower())
            if k not in out:
                out.append(k)
    return out[:5]


def show(keys):
    return ", ".join(f"{a}:{b}" for a, b in keys) or "-"


def rate(rows, key):
    n = len(rows)
    h = sum(1 for r in rows if r[key])
    return f"{h}/{n} ({100 * h / n:.0f}%)" if n else "0/0"


def main():
    case_map = json.load(open(CASE_MAP))
    reviews = {json.loads(l)["incident_id"]: json.loads(l) for l in open(REVIEWS)}
    props = {json.loads(l)["incident_id"]: json.loads(l) for l in open(PROPOSALS)}
    dates = {r["incident_id"]: r["date"] for r in csv.DictReader(open(SAMPLE))}
    b2 = {}
    for path in sys.argv[1:]:
        for line in open(path):
            if line.strip():
                r = json.loads(line)
                b2[r["case_id"]] = r
    rows = []
    for case, iid in sorted(case_map.items(), key=lambda x: x[1]):
        rev = reviews[iid]
        t_fable = truth_from(rev["locations"])
        t_union = t_fable | truth_from(props.get(iid, {}).get("locations"))
        pred = [fn(x.get("location")) for x in (b2.get(case) or {}).get("top5", [])]
        pred = [p for p in pred if p]
        prep = json.load(open(os.path.join(PREPARED, iid + ".json")))
        s5 = slither_top5(rev["victims"], prep)
        rows.append({"iid": iid, "date": dates.get(iid, ""), "late": dates.get(iid, "") >= LATE,
                     "answered": case in b2, "truth": sorted(t_fable), "pred": pred, "slither": s5,
                     "b2_h1": hit(pred, t_fable, 1), "b2_h5": hit(pred, t_fable, 5),
                     "b2_h5_union": hit(pred, t_union, 5), "b0_h5": hit(s5, t_fable, 5),
                     "b0_h5_union": hit(s5, t_union, 5), "no_truth": not t_fable})
    scored = [r for r in rows if not r["no_truth"]]
    late = [r for r in scored if r["late"]]
    early = [r for r in scored if not r["late"]]
    L = ["# B2 baseline: frontier model, code only (M0)", "",
         f"Model: {next(iter(b2.values()))['model'] if b2 else '?'}. Ground truth (strict, file + function, defect role only) from the blind "
         "Fable 5.1 review (and, leniently, the union with Opus proposals). **Both are LLM labels, not human-verified.**",
         "", f"Cases: {len(rows)} (answered {sum(r['answered'] for r in rows)}; "
         f"{len(rows) - len(scored)} without a function-level causal location, excluded).", "",
         "| Metric | All | Before 2026-07 | 2026-07 and later (likely post-cutoff) |", "|---|---|---|---|"]
    for label, key in [("**B2 Hit@1**", "b2_h1"), ("**B2 Hit@5**", "b2_h5"), ("B2 Hit@5 (lenient key)", "b2_h5_union"),
                       ("**B0 Slither top-5 Hit@5**", "b0_h5"), ("B0 Hit@5 (lenient key)", "b0_h5_union")]:
        L.append(f"| {label} | {rate(scored, key)} | {rate(early, key)} | {rate(late, key)} |")
    L += ["", "Caveats:",
          "- Older incidents are famous and probably in the model's pretraining data. The late column is the honest one, "
          f"and it has only {len(late)} cases.",
          "- Function-name matching is strict: a correct contract-level answer, or the right defect in a helper, counts as a miss.",
          "- B0 here is Slither's findings ranked by impact then confidence, mapped to functions. It's not a tuned config.",
          "", "| Incident | Date | Truth (Fable) | B2 top-5 | Slither top-5 | B2@5 | B0@5 |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['iid']} | {r['date']} | {show(r['truth'])} | {show(r['pred'])} | "
                 f"{show(r['slither'])} | {'y' if r['b2_h5'] else 'n'} | {'y' if r['b0_h5'] else 'n'} |")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L[:16]))


if __name__ == "__main__":
    main()
