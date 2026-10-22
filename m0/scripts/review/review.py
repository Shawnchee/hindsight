"""M0 review CLI: walk the 40-incident sample, label each incident, adjudicate Slither findings,
and time every review. Resumable: incidents already in the output file are skipped.

Run `prepare.py` first. Then, from repo root:
  python3 -I m0/scripts/review/review.py                 # review the next unreviewed incidents
  python3 -I m0/scripts/review/review.py --redo <id>     # review one incident again (latest record wins)
  python3 -I m0/scripts/review/review.py --list          # show progress

At any prompt: q = quit without saving the current incident, s = skip it.
Labels and findings follow PRD §7.3 and §8.2 (taxonomy v0.1).
"""
import csv
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SAMPLE = os.path.join(REPO, "m0", "catalog", "m0_sample.csv")
PREPARED = os.path.join(REPO, "m0", "data", "review", "prepared")
DHL = os.path.join(REPO, "m0", "data", "funnel", "dhl")
OUT = os.path.join(REPO, "m0", "review", "reviews.jsonl")
# LLM-proposed labels (PRD ENR-7). Shown as defaults; the reviewer accepts or overrides each one.
PROPOSALS = os.path.join(REPO, "m0", "review", "proposals.jsonl")
TAXONOMY_VERSION = "v0.1"

ROOT_CAUSES = ["access_control", "price_oracle_trust", "rounding_precision", "arithmetic_overflow_or_cast",
               "input_validation", "reentrancy", "business_logic", "signature_validation",
               "uninitialized_or_unprotected_init", "storage_collision", "arbitrary_external_call",
               "governance_design", "weak_randomness", "denial_of_service", "other"]
MECHANISMS = ["flash_loan", "price_manipulation", "reentrant_call", "crafted_calldata", "governance_vote",
              "donation", "other"]
IMPACTS = ["funds_drained", "tokens_minted", "funds_frozen", "governance_takeover", "other"]
ROLES = {"d": "defect", "e": "entry_point", "a": "affected"}
IMPACT_ORDER = {"High": 0, "Medium": 1, "Low": 2, "Informational": 3, "Optimization": 4}
DEP_MARKERS = ("openzeppelin", "node_modules", "lib/", "@", "solmate", "forge-std")


class Skip(Exception):
    pass


class Quit(Exception):
    pass


def ask(prompt, default=None):
    suffix = f" [{default}]" if default not in (None, "") else ""
    try:
        v = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        raise Quit
    if v == "q":
        raise Quit
    if v == "s":
        raise Skip
    return v if v else (default or "")


def nums(text, n):
    out = []
    for part in text.replace(" ", "").split(","):
        if part.isdigit() and 1 <= int(part) <= n:
            out.append(int(part))
    return out


def pick(title, options, default):
    print(f"\n{title}")
    for i, o in enumerate(options, 1):
        print(f"  {i:>2}. {o}")
    d = ",".join(str(options.index(x) + 1) for x in default if x in options)
    while True:
        chosen = nums(ask("Numbers, comma-separated", d), len(options))
        if chosen:
            return [options[i - 1] for i in chosen]
        print("  Pick at least one.")


def is_dependency(f):
    loc = (f.get("first_markdown") or "").lower()
    return any(m in loc for m in DEP_MARKERS)


def load_jsonl(path):
    if not os.path.exists(path):
        return {}
    latest = {}
    for line in open(path):
        if line.strip():
            r = json.loads(line)
            latest[r["incident_id"]] = r
    return latest


def load_reviews():
    return load_jsonl(OUT)


def reviewer():
    try:
        return subprocess.run(["git", "-C", REPO, "config", "user.name"], capture_output=True,
                              text=True).stdout.strip() or "unknown"
    except OSError:
        return "unknown"


def show_incident(row, prep):
    print("\n" + "=" * 78)
    print(f"{row['incident_id']}  |  {row['date']}  |  {row['name']}  |  loss: {row['loss_readme'] or 'unknown'}")
    print(f"DHL label (evidence): {row['raw_label'][:300]}")
    print(f"Proposed: root_cause={row['root_cause']} mechanism={row['mechanism'] or '-'} "
          f"(confidence {row['label_confidence']})")
    print(f"PoC: {os.path.join(DHL, row['poc_path'])}")
    if row["attack_tx_hashes"]:
        print(f"Attack tx: {row['attack_tx_hashes'][:140]}")
    if not prep:
        print("!! Not prepared: run prepare.py first. Candidates will be empty.")


def fork_block(poc_path):
    """Block number of the PoC's first mainnet fork, or None."""
    try:
        code = open(os.path.join(DHL, poc_path), errors="replace").read()
    except OSError:
        return None
    m = re.search(r'createSelectFork\(\s*"[^"]*"\s*,\s*([0-9_]+)', code)
    return int(m.group(1).replace("_", "")) if m else None


def show_candidates(cands, exploit_block=None):
    print("\nVictim candidates (header first, then PoC code addresses):")
    if exploit_block:
        print(f"  PoC forks at block {exploit_block}")
    if not cands:
        print("  (none)")
    for i, c in enumerate(cands, 1):
        status = c["sourcify"]
        if c.get("contract_name"):
            status += f", {c['contract_name']}"
        if c.get("is_proxy"):
            status += ", PROXY"
        dep = str(c.get("deployment_block") or "")
        if exploit_block and dep.isdigit() and int(dep) > exploit_block:
            status += f", DEPLOYED AFTER EXPLOIT (block {dep}): not the exploited code"
        if c.get("compile_ok") is False:
            status += f", compile failed ({c.get('compile_error_class')})"
        elif c.get("slither_ok") is False:
            status += ", slither failed"
        elif c.get("slither_ok"):
            status += f", {len(c.get('detectors', []))} findings"
        hdr = " [header]" if c.get("from_header") else ""
        print(f"  {i}. {c['address']}{hdr}  {status}")
        print(f"     https://etherscan.io/address/{c['address']}#code")
        if c.get("source_dir"):
            print(f"     source: {os.path.join(REPO, c['source_dir'])}")


def review_findings(victims, proposal=None):
    """Adjudicate Slither findings of the chosen victim contracts. Returns (findings, slither_ran)."""
    proposed_keys = {(e.get("candidate"), e.get("detector_index"))
                     for e in (proposal or {}).get("explains_findings", [])}
    listed, slither_ran = [], False
    for c in victims:
        if not c.get("slither_ok"):
            continue
        slither_ran = True
        dets = [(i, f) for i, f in enumerate(c.get("detectors", [])) if not is_dependency(f)]
        dets.sort(key=lambda x: (IMPACT_ORDER.get(x[1].get("impact"), 9), x[0]))
        for i, f in dets:
            listed.append((c["address"], i, f))
    if not listed:
        print("\nNo Slither findings to adjudicate (Slither did not run on the chosen victim, or it found nothing).")
        return [], slither_ran
    show_low = False
    while True:
        print(f"\nSlither findings on the victim, dependencies hidden ({len(listed)}):")
        hidden = 0
        for n, (addr, i, f) in enumerate(listed, 1):
            if f.get("impact") in ("Informational", "Optimization") and not show_low:
                hidden += 1
                continue
            desc = (f.get("description") or "").strip().splitlines()[0][:110] if f.get("description") else ""
            fn = ",".join(f.get("functions") or []) or "-"
            print(f"  {n:>3}. [{f.get('impact')}/{f.get('confidence')}] {f.get('check')}  fn={fn}  "
                  f"{f.get('first_markdown')}")
            if desc:
                print(f"       {desc}")
        if hidden and not show_low:
            if ask(f"{hidden} Informational/Optimization findings hidden. Show them? y/n", "n") == "y":
                show_low = True
                continue
        break
    n = len(listed)
    default_explains = ",".join(str(k) for k, (addr, i, _) in enumerate(listed, 1) if (addr, i) in proposed_keys)
    if proposal:
        print(f"  (proposal says {default_explains or 'none'} explain the exploit; type '-' for none)")
    raw = ask("Findings that EXPLAIN the exploit (numbers, blank = none)", default_explains)
    explains = set() if raw == "-" else set(nums(raw, n))
    valid = set(nums(ask("Other findings you CONFIRM are valid issues (numbers, blank = none)", ""), n))
    invalid = set(nums(ask("Findings you CONFIRM are invalid / noise (numbers, blank = none)", ""), n))
    out = []
    for k, (addr, i, f) in enumerate(listed, 1):
        if k in explains or k in valid:
            status = "confirmed_valid"
        elif k in invalid:
            status = "confirmed_invalid"
        else:
            status = "unresolved"
        out.append({"candidate": addr, "detector_index": i, "check": f.get("check"), "impact": f.get("impact"),
                    "confidence": f.get("confidence"), "first_markdown": f.get("first_markdown"),
                    "functions": f.get("functions") or [], "status": status, "explains_exploit": k in explains})
    return out, slither_ran


def show_proposal(p):
    print(f"\nLLM proposal ({p.get('model', '?')}, confidence {p.get('confidence', '?')}) — check, don't trust:")
    print(f"  victim: {', '.join(p.get('victim_addresses') or []) or 'none identified'}"
          f"   in scope: {p.get('in_scope')}")
    print(f"  root cause: {p.get('root_cause')}  mechanism: {p.get('mechanism')}  impact: {p.get('impact')}")
    if p.get("locations"):
        print(f"  locations: {'; '.join(l['raw'] + ' (' + l.get('role', 'defect') + ')' for l in p['locations'])}")
    if p.get("rationale"):
        print(f"  why: {p['rationale'][:400]}")


def review_one(row, prep, proposal=None):
    show_incident(row, prep)
    ask("\nOpen the PoC and the write-up. Press Enter to START the timer")
    started = time.time()
    cands = (prep or {}).get("candidates", [])
    show_candidates(cands, fork_block(row["poc_path"]))
    p = proposal or {}
    if proposal:
        show_proposal(proposal)
    pv = [c for c in (p.get("victim_addresses") or [])]
    default_sel = ",".join(str(i) for i, c in enumerate(cands, 1) if c["address"] in pv)
    if not default_sel:
        default_sel = "-" if (proposal and not pv) or not cands else ("m" if pv else "1")
    sel = ask("\nVictim contract(s) with the bug: numbers, 'm' = enter address, '-' = not in the list", default_sel)
    victims, manual = [], []
    if sel == "m":
        known = {c["address"] for c in cands}
        manual = [a.strip().lower() for a in ask("Address(es), comma-separated",
                                                 ",".join(a for a in pv if a not in known)).split(",") if a.strip()]
    elif sel != "-":
        victims = [cands[i - 1] for i in nums(sel, len(cands))]
    rec = {"incident_id": row["incident_id"], "reviewer": reviewer(), "taxonomy_version": TAXONOMY_VERSION,
           "victims": [c["address"] for c in victims] + manual, "victims_manual": manual,
           "proposed": {"root_cause": row["root_cause"], "mechanism": row["mechanism"]},
           "had_llm_proposal": bool(proposal), "llm_proposal_model": p.get("model")}
    in_scope = ask("Is this a code-level bug in the victim contract? y/n", "n" if p.get("in_scope") is False else "y") == "y"
    rec["in_scope"] = in_scope
    if not in_scope:
        rec["off_chain_reason"] = ask("Why not (key compromise, rug, frontend, not an exploit...)",
                                      p.get("off_chain_reason") or "")
    else:
        src = {}
        for c in victims:
            if c["sourcify"] == "full_match":
                src[c["address"]] = "bytecode_matched"
            elif c["sourcify"] == "partial_match":
                ok = ask(f"Source for {c['address'][:10]} is a Sourcify partial match. Does it match the deployed "
                         f"contract (check Etherscan)? y/n/?", "?")
                src[c["address"]] = {"y": "explorer_verified", "n": "none"}.get(ok, "unchecked")
            else:
                src[c["address"]] = "none"
        for a in manual:
            src[a] = "none"
        rec["source_status"] = src
        rec["labels"] = {
            "root_cause": pick("Root cause (the defect)", ROOT_CAUSES,
                               p.get("root_cause") or ([row["root_cause"]] if row["root_cause"] else [])),
            "mechanism": pick("Mechanism (how it was exploited)", MECHANISMS,
                              p.get("mechanism") or ([row["mechanism"]] if row["mechanism"] else [])),
            "impact": pick("Impact", IMPACTS, p.get("impact") or ["funds_drained"]),
        }
        rec["violated_invariant"] = ask("\nViolated invariant, one line (optional)", p.get("violated_invariant") or "")
        print("\nCausal code locations. Format: File.sol:function or File.sol#L120-140 or 'contract'.")
        locs = []
        if p.get("locations"):
            for l in p["locations"]:
                print(f"  proposed: {l['raw']} ({l.get('role', 'defect')})")
            if ask("Accept the proposed locations? y/n (n = enter your own)", "y") == "y":
                for l in p["locations"]:
                    file_, _, rest = l["raw"].partition(":")
                    locs.append({"raw": l["raw"], "file": file_ if rest else None, "function": rest or None,
                                 "role": l.get("role", "defect")})
        while True:
            loc = ask(f"Location {len(locs) + 1} (blank = done)")
            if not loc:
                break
            role = ask("  Role: d = defect, e = entry point, a = affected", "d")
            file_, _, rest = loc.partition(":")
            locs.append({"raw": loc, "file": file_ if rest else None, "function": rest or None,
                         "role": ROLES.get(role, "defect")})
        rec["locations"] = locs
        rec["findings"], rec["slither_ran_on_victim"] = review_findings(victims, proposal)
    rec["notes"] = ask("\nNotes (optional)")
    ended = time.time()
    interrupted = ask("Minutes you were interrupted during this review (0 if none)", "0")
    try:
        interrupted_s = max(0.0, float(interrupted) * 60)
    except ValueError:
        interrupted_s = 0.0
    wall = ended - started
    rec.update(started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
               ended_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ended)),
               wall_seconds=round(wall, 1), interrupted_seconds=round(interrupted_s, 1),
               review_seconds=round(max(0.0, wall - interrupted_s), 1))
    return rec


def main():
    global OUT
    args = sys.argv[1:]
    if "--out" in args:  # alternate output file, e.g. for a dry run
        OUT = os.path.abspath(args[args.index("--out") + 1])
    rows = list(csv.DictReader(open(SAMPLE)))
    done = load_reviews()
    if "--list" in args:
        for r in rows:
            d = done.get(r["incident_id"])
            mark = f"done ({d['review_seconds'] / 60:.1f} min)" if d else "todo"
            print(f"{r['incident_id']:<40} {mark}")
        print(f"\n{len(done)}/{len(rows)} reviewed")
        return
    redo = args[args.index("--redo") + 1] if "--redo" in args else None
    todo = [r for r in rows if (r["incident_id"] == redo if redo else r["incident_id"] not in done)]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    print(f"{len(done)}/{len(rows)} reviewed. {len(todo)} to go. q = quit, s = skip.")
    proposals = load_jsonl(PROPOSALS)
    for row in todo:
        p = os.path.join(PREPARED, row["incident_id"] + ".json")
        prep = json.load(open(p)) if os.path.exists(p) else None
        try:
            rec = review_one(row, prep, proposals.get(row["incident_id"]))
        except Skip:
            print("Skipped.")
            continue
        except Quit:
            print("\nQuit. Nothing saved for this incident.")
            return
        with open(OUT, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"Saved. Review took {rec['review_seconds'] / 60:.1f} min.")


if __name__ == "__main__":
    main()
