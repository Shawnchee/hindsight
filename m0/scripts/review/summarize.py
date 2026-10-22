"""Summarize M0 reviews into the numbers the PRD needs (§5 targets, §6 M1 size).

Usage (from repo root):
  python3 -I m0/scripts/review/summarize.py [--hours-per-week 3]
Reads m0/review/reviews.jsonl (latest record per incident) and m0/catalog/m0_sample.csv.
Writes m0/review/summary.md.
"""
import collections
import csv
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SAMPLE = os.path.join(REPO, "m0", "catalog", "m0_sample.csv")
REVIEWS = os.path.join(REPO, "m0", "review", "reviews.jsonl")
OUT = os.path.join(REPO, "m0", "review", "summary.md")


def pct(a, b):
    return f"{a}/{b} ({100 * a / b:.0f}%)" if b else f"{a}/0 (n/a)"


def quantile(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))] if xs else 0


def function_overlap(rec):
    """Loose coverage: any Slither finding (any status) touches a causal function."""
    fns = {(l.get("function") or "").split("(")[0] for l in rec.get("locations", []) if l.get("function")}
    fns.discard("")
    return any(set(f.get("functions") or []) & fns for f in rec.get("findings", []))


def main():
    args = sys.argv[1:]
    hours = float(args[args.index("--hours-per-week") + 1]) if "--hours-per-week" in args else 3.0
    global REVIEWS, OUT
    if "--reviews" in args:
        REVIEWS = os.path.abspath(args[args.index("--reviews") + 1])
    if "--out" in args:
        OUT = os.path.abspath(args[args.index("--out") + 1])
    sample = list(csv.DictReader(open(SAMPLE)))
    latest = {}
    if os.path.exists(REVIEWS):
        for line in open(REVIEWS):
            if line.strip():
                r = json.loads(line)
                latest[r["incident_id"]] = r
    recs = list(latest.values())
    mins = [r["review_seconds"] / 60 for r in recs]
    in_scope = [r for r in recs if r.get("in_scope")]
    ran = [r for r in in_scope if r.get("slither_ran_on_victim")]
    strict = [r for r in ran if any(f["explains_exploit"] for f in r.get("findings", []))]
    loose = [r for r in ran if function_overlap(r)]
    no_source = [r for r in in_scope if not r.get("slither_ran_on_victim")]
    changed = [r for r in in_scope if r["proposed"]["root_cause"] not in r["labels"]["root_cause"]]
    statuses = collections.Counter(f["status"] for r in in_scope for f in r.get("findings", []))
    roots = collections.Counter(rc for r in in_scope for rc in r["labels"]["root_cause"])
    multi_loc = [r for r in in_scope if len(r.get("locations", [])) > 1]

    L = [f"# M0 review summary (generated {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())})", ""]
    L.append(f"Reviewed {len(recs)} of {len(sample)} sampled incidents. "
             "The sample over-weights rare root-cause classes, so weight class-level rates before quoting them.")
    L += ["", "## Review effort", ""]
    if mins:
        real_med = statistics.median(mins)
        med = max(real_med, 0.1)  # guard against zero-length dry runs
        L += [f"- Minutes per review: median **{real_med:.1f}**, p90 {quantile(mins, 0.9):.1f}, max {max(mins):.1f}",
              f"- At {hours:g} h/week: about **{hours * 60 / med:.0f} incidents/week** at the median pace",
              f"- Fully reviewing all 357 Ethereum incidents: about **{357 * med / 60:.0f} hours** (median pace)"]
    else:
        L.append("- No reviews yet.")
    L += ["", "## Scope and source", "",
          f"- Code-level (in scope): {pct(len(in_scope), len(recs))}",
          f"- Slither ran on the chosen victim: {pct(len(ran), len(in_scope))}",
          f"- In scope but no usable source / Slither run: {len(no_source)}",
          f"- Proposed root cause changed by reviewer: {pct(len(changed), len(in_scope))}",
          f"- Incidents with more than one causal location: {pct(len(multi_loc), len(in_scope))}"]
    L += ["", "## Slither coverage (the key M0 number)", "",
          f"- **Strict** (a finding explains the exploit): {pct(len(strict), len(ran))}",
          f"- Loose (any finding touches a causal function): {pct(len(loose), len(ran))}",
          "- Denominator: in-scope incidents where Slither ran on the victim. The strict number sets the ceiling",
          "  for pure triage. PRD kill/pivot check: strict below ~30% means beyond-Slither must carry the product.",
          "", "Finding adjudications (in-scope incidents): " +
          ", ".join(f"{k} {v}" for k, v in statuses.most_common()) if statuses else "No findings adjudicated."]
    props = {}
    prop_path = os.path.join(os.path.dirname(REVIEWS), "proposals.jsonl")
    if os.path.exists(prop_path):
        for line in open(prop_path):
            if line.strip():
                p = json.loads(line)
                props[p["incident_id"]] = p
    with_p = [r for r in recs if r["incident_id"] in props]
    if with_p:
        def agree(r, field):
            return set(props[r["incident_id"]].get(field) or []) == set(r.get("labels", {}).get(field) or [])
        scoped = [r for r in with_p if r.get("in_scope") and props[r["incident_id"]].get("in_scope") is not False]
        victim_ok = [r for r in with_p if set(props[r["incident_id"]].get("victim_addresses") or [])
                     & set(r.get("victims") or [])]
        explain_ok = [r for r in scoped if
                      {(e["candidate"], e["detector_index"]) for e in props[r["incident_id"]].get("explains_findings", [])}
                      == {(f["candidate"], f["detector_index"]) for f in r.get("findings", []) if f["explains_exploit"]}]
        L += ["", "## LLM proposal vs reviewer (label-quality check)", "",
              f"- Reviews that had a proposal: {len(with_p)}",
              f"- In-scope call agreed: {pct(sum(1 for r in with_p if (props[r['incident_id']].get('in_scope') is not False) == bool(r.get('in_scope'))), len(with_p))}",
              f"- Victim contract overlap: {pct(len(victim_ok), len(with_p))}",
              f"- Root cause exact agreement: {pct(sum(agree(r, 'root_cause') for r in scoped), len(scoped))}",
              f"- Mechanism exact agreement: {pct(sum(agree(r, 'mechanism') for r in scoped), len(scoped))}",
              f"- 'Which finding explains it' exact agreement: {pct(len(explain_ok), len(scoped))}",
              "- Caveat: the reviewer saw the proposal, so agreement is inflated by anchoring. Use it as a lower bound",
              "  on how often the proposal is wrong (every disagreement is a proposal error the reviewer caught)."]
    L += ["", "## Root causes (reviewed)", ""]
    L += [f"- {k}: {v}" for k, v in roots.most_common()] or ["- none yet"]
    L += ["", "## Per incident", "", "| Incident | Min | In scope | Slither ran | Explains | Root cause |",
          "|---|---:|---|---|---|---|"]
    for r in sorted(recs, key=lambda x: x["incident_id"]):
        L.append(f"| {r['incident_id']} | {r['review_seconds'] / 60:.1f} | {'y' if r.get('in_scope') else 'n'} | "
                 f"{'y' if r.get('slither_ran_on_victim') else 'n'} | "
                 f"{'y' if any(f['explains_exploit'] for f in r.get('findings', [])) else 'n'} | "
                 f"{', '.join(r.get('labels', {}).get('root_cause', [])) or '-'} |")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L[:20]))


if __name__ == "__main__":
    main()
