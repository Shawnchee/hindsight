"""Score B2 v2 on the mixed blind pool: post-cutoff exploits plus clean audited contracts.

  exploit cases: Hit@1 and Hit@5 of causal functions (defect or entry_point) from the blind Fable review
                 of the post-cutoff set. Function-name match.
  clean cases:   false-positive rate = share where the model claims an exploitable bug with
                 medium or high confidence.

Usage (from repo root):
  python3 -I m0/scripts/b2/score_v2.py m0/b2/v2/b2v2.part*.jsonl
Writes m0/b2/v2/summary.md.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
from score import fn, hit, truth_from  # noqa: E402

CASE_MAP = os.path.join(REPO, "m0", "data", "b2v2", "case_map.json")
REVIEWS = os.path.join(REPO, "m0", "review", "postcutoff", "reviews.llm.jsonl")
OUT = os.path.join(REPO, "m0", "b2", "v2", "summary.md")


def main():
    global OUT
    if "--out" in sys.argv:  # e.g. the precedent spike writes its own summary
        i = sys.argv.index("--out")
        OUT = os.path.abspath(sys.argv[i + 1])
        del sys.argv[i:i + 2]
    case_map = json.load(open(CASE_MAP))
    reviews = {json.loads(l)["incident_id"]: json.loads(l) for l in open(REVIEWS)}
    preds = {}
    for p in sys.argv[1:]:
        for line in open(p):
            if line.strip():
                r = json.loads(line)
                preds[r["case_id"]] = r
    ex, cl = [], []
    for case, info in sorted(case_map.items(), key=lambda x: (x[1]["kind"], x[1]["id"])):
        p = preds.get(case) or {}
        top = [fn(x.get("location")) for x in p.get("top5", [])]
        top = [t for t in top if t]
        claims = bool(p.get("exploitable_bug_found")) and p.get("confidence") in ("high", "medium")
        if info["kind"] == "exploit":
            truth = truth_from(reviews[info["id"]]["locations"])
            ex.append({"id": info["id"], "truth": sorted(truth), "top": top, "h1": hit(top, truth, 1),
                       "h5": hit(top, truth, 5), "claims": claims, "answered": bool(p), "no_truth": not truth})
        else:
            cl.append({"id": info["id"], "top": top, "claims": claims, "conf": p.get("confidence"),
                       "answered": bool(p), "why": (p.get("top5") or [{}])[0].get("why", "")})
    scored = [r for r in ex if not r["no_truth"]]

    def frac(rows, k):
        n = len(rows)
        h = sum(1 for r in rows if r[k])
        return f"{h}/{n} ({100 * h / n:.0f}%)" if n else "0/0"

    L = ["# B2 v2: post-cutoff exploits + clean contracts (blind, mixed pool)", "",
         f"Model: {next(iter(preds.values())).get('model', '?') if preds else '?'}. Ground truth for exploits is the blind "
         "Fable 5.1 review of the post-cutoff set (LLM labels, not human-verified). The model doesn't know which "
         "cases are clean.", "",
         "| Metric | Value |", "|---|---|",
         f"| Exploit cases scored | {len(scored)} (of {len(ex)}; rest lack a function-level causal location) |",
         f"| **Exploit Hit@1** | {frac(scored, 'h1')} |",
         f"| **Exploit Hit@5** | {frac(scored, 'h5')} |",
         f"| Exploit cases where the model claims a bug (medium/high) | {frac(ex, 'claims')} |",
         f"| **Clean false-positive rate** (claims an exploitable bug, medium/high) | {frac(cl, 'claims')} |",
         "", "Caveats:",
         "- \"Post-cutoff\" means the incident is from 2026-07 or later. The model's exact training cutoff isn't documented, "
         "and some victims are old code that could be in pretraining.",
         "- The clean contracts are famous and audited. The model has probably seen them called safe, so this flatters "
         "the false-positive rate. Obscure, never-exploited contracts would be the harder test.",
         "", "## Exploit cases", "", "| Incident | Truth | Top-5 | @1 | @5 |", "|---|---|---|---|---|"]
    for r in ex:
        L.append(f"| {r['id']} | {', '.join(r['truth']) or '-'} | {', '.join(r['top']) or '-'} | "
                 f"{'y' if r['h1'] else 'n'} | {'y' if r['h5'] else 'n'} |")
    L += ["", "## Clean cases", "", "| Contract | Claims bug | Confidence | Top-1 reason |", "|---|---|---|---|"]
    for r in cl:
        L.append(f"| {r['id']} | {'y' if r['claims'] else 'n'} | {r['conf'] or '-'} | {r['why'][:120]} |")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L[:14]))


if __name__ == "__main__":
    main()
