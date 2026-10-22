"""Stage 4: assemble m0/funnel/funnel.csv and m0/funnel/summary.md from the
selection file and per-incident results.

Usage (from repo root):
  python3 -I m0/scripts/funnel/report.py m0/data/funnel/incidents.json m0/data/funnel/results m0/funnel \
      [--dhl-sha <sha>]
"""
import collections
import csv
import json
import os
import statistics
import sys

IMPACTS = ["High", "Medium", "Low", "Informational", "Optimization"]
CONFS = ["High", "Medium", "Low"]
DEP_HINTS = ("@openzeppelin", "openzeppelin-contracts", "node_modules", "/lib/", "lib/forge-std", "@uniswap",
             "@chainlink", "solmate", "solady", "@balancer-labs", "@aave")


def is_dep(loc):
    low = loc.lower()
    return any(h in low for h in DEP_HINTS)


def proxy_class(res):
    ev = res.get("proxy_evidence", [])
    if any(e.startswith("sourcify:") for e in ev) or "source:proxy_name+delegatecall" in ev:
        return "yes"
    if "source:eip1967_slot" in ev:
        return "impl_with_eip1967_slot"  # e.g. UUPS logic contract: the code itself is scanned
    return "no"


def stage(row):
    if not row["in_scope"]:
        return "out_of_scope"
    if not row["victim_found"]:
        return "no_victim_in_header"
    if row["source_recovered"] != "yes":
        return "sourcify_not_found" if row["sourcify_best"] == "not_found" else "no_source"
    if row["compile_ok"] != "yes":
        return "compile_fail"
    if row["slither_ok"] != "yes":
        return "slither_fail"
    return "slither_ok"


def pct(a, b):
    return f"{100 * a / b:.0f}%" if b else "-"


def main():
    args = sys.argv[1:]
    inc_path, res_dir, out_dir = args[0], args[1], args[2]
    sha = args[args.index("--dhl-sha") + 1] if "--dhl-sha" in args else "unknown"
    incidents = [r for r in json.load(open(inc_path)) if r["in_scope"]]
    total_pocs = len(json.load(open(inc_path)))
    rows = []
    for r in incidents:
        p = os.path.join(res_dir, r["incident"] + ".json")
        res = json.load(open(p)) if os.path.exists(p) else {}
        cands = res.get("candidates", [])
        labels = [c["sourcify"] for c in cands]
        best = ("full_match" if "full_match" in labels else "partial_match" if "partial_match" in labels
                else "not_found" if "not_found" in labels else ("" if not labels else labels[0]))
        dets = res.get("detectors", []) if res.get("slither_ok") else []
        imp = collections.Counter(d["impact"] for d in dets)
        conf = collections.Counter(d["confidence"] for d in dets)
        tf = res.get("target_file") or ""
        in_target = [d for d in dets if tf and d["first_markdown"].startswith(tf)]
        non_dep = [d for d in dets if not is_dep(d["first_markdown"])]
        top = collections.Counter(d["check"] for d in dets).most_common(3)
        row = {
            "incident": r["incident"], "month": r["month"], "poc_path": r["poc_path"],
            "fork_arg": r["fork_arg"], "in_scope": True,
            "victim_found": bool(r["victims"]), "victim_source": r.get("victim_source") or "",
            "n_victim_candidates": len(r["victims"]),
            "victim_explorer_chains": ";".join(r["victim_explorer_chains"]),
            "primary_address": r["victims"][0] if r["victims"] else "",
            "sourcify_primary": labels[0] if labels else "",
            "sourcify_best": best,
            "source_address": res.get("address", ""),
            "source_recovered": "yes" if res.get("address") else "no",
            "source_from_candidate_index": (r["victims"].index(res["address"]) if res.get("address") else ""),
            "contract_name": res.get("contract_name", ""), "language": res.get("language", ""),
            "compiler_version": res.get("compiler_version", ""), "n_source_files": res.get("n_source_files", ""),
            "deployment_block": res.get("deployment_block", ""),
            "is_proxy": proxy_class(res) if res.get("address") else "",
            "proxy_evidence": ";".join(res.get("proxy_evidence", [])),
            "compile_ok": ("yes" if res.get("compile_ok") else "no") if res.get("address") else "",
            "compile_error_class": res.get("compile_error_class") or "",
            "slither_ok": ("yes" if res.get("slither_ok") else "no") if res.get("compile_ok") else "",
            "slither_error": (res.get("slither_error") or "").split("\n")[0][:200],
            "slither_findings_total": len(dets) if res.get("slither_ok") else "",
            **{f"impact_{k.lower()}": imp.get(k, 0) if res.get("slither_ok") else "" for k in IMPACTS},
            **{f"conf_{k.lower()}": conf.get(k, 0) if res.get("slither_ok") else "" for k in CONFS},
            "findings_in_target_file": len(in_target) if res.get("slither_ok") else "",
            "findings_non_dependency": len(non_dep) if res.get("slither_ok") else "",
            "top_detectors": ";".join(f"{c}:{n}" for c, n in top),
        }
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(inc_path))), "funnel", "dhl", r["poc_path"]),
                  encoding="utf-8", errors="replace") as f:
            hdr = f.read().split("contract ", 1)[0].lower()
        row["unverified_hint"] = any(t in hdr for t in ("unverified", "not verified", "not open source", "isn't open source"))
        row["funnel_stage_reached"] = stage(row)
        rows.append(row)

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "funnel.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    n = len(rows)
    v = [x for x in rows if x["victim_found"]]
    s = [x for x in v if x["source_recovered"] == "yes"]
    c = [x for x in s if x["compile_ok"] == "yes"]
    sl = [x for x in c if x["slither_ok"] == "yes"]
    lab = collections.Counter(x["sourcify_best"] for x in v)
    prim = collections.Counter(x["sourcify_primary"] for x in v)
    comp_fail = collections.Counter(x["compile_error_class"] for x in s if x["compile_ok"] != "yes")
    sl_fail = collections.Counter(x["slither_error"].split(":")[0] for x in c if x["slither_ok"] != "yes")
    proxies = [x for x in s if x["is_proxy"] == "yes"]
    totals = [x["slither_findings_total"] for x in sl]
    nondep = [x["findings_non_dependency"] for x in sl]
    intarget = [x["findings_in_target_file"] for x in sl]
    impact_tot = {k: sum(x[f"impact_{k.lower()}"] for x in sl) for k in IMPACTS}
    impact_med = {k: statistics.median([x[f"impact_{k.lower()}"] for x in sl]) if sl else 0 for k in IMPACTS}
    det_tot = collections.Counter()
    det_contracts = collections.Counter()
    for x in sl:
        res = json.load(open(os.path.join(res_dir, x["incident"] + ".json")))
        cc = collections.Counter(d["check"] for d in res["detectors"])
        det_tot.update(cc)
        det_contracts.update(cc.keys())
    by_year = collections.defaultdict(lambda: [0, 0, 0, 0, 0])
    for x in rows:
        y = x["month"][:4]
        b = by_year[y]
        b[0] += 1
        b[1] += x["victim_found"]
        b[2] += x["source_recovered"] == "yes"
        b[3] += x["compile_ok"] == "yes"
        b[4] += x["slither_ok"] == "yes"
    nf = [x for x in v if x["sourcify_best"] == "not_found"]

    def med(a):
        return statistics.median(a) if a else "-"

    L = []
    L.append("# M0 data funnel: Ethereum mainnet DeFiHackLabs incidents, 2024-11 to 2026-10\n")
    L.append(f"Measured 2026-10-22. DeFiHackLabs commit `{sha}` (shallow clone). Source lookup: **Sourcify APIv2 only** "
             "(no Etherscan key). Compiler: exact solc version via solc-select, Sourcify's compiler settings, "
             "solc standard-JSON. Slither 0.11.6, all built-in detectors, run on the whole compilation unit.\n")
    L.append("## Funnel\n")
    L.append("| Stage | Count | % of in-scope | % of previous stage |")
    L.append("|---|---:|---:|---:|")
    L.append(f"| DeFiHackLabs PoCs in window (all chains) | {total_pocs} | | |")
    L.append(f"| In scope (first `createSelectFork` = Ethereum mainnet) | {n} | 100% | {pct(n, total_pocs)} |")
    L.append(f"| Victim address found in PoC header | {len(v)} | {pct(len(v), n)} | {pct(len(v), n)} |")
    L.append(f"| Verified source recovered (Sourcify full or partial, any header candidate) | {len(s)} | {pct(len(s), n)} | {pct(len(s), len(v))} |")
    L.append(f"| Compiles (exact solc, Sourcify settings) | {len(c)} | {pct(len(c), n)} | {pct(len(c), len(s))} |")
    L.append(f"| Slither runs | {len(sl)} | {pct(len(sl), n)} | {pct(len(sl), len(c))} |")
    usable = [x for x in sl if x["is_proxy"] != "yes"]
    L.append(f"| ...and scanned contract is not a proxy shell | {len(usable)} | {pct(len(usable), n)} | {pct(len(usable), len(sl))} |")
    L.append("")
    L.append("### Sourcify result (incidents with a victim address)\n")
    L.append("| Result | Best over header candidates | Primary (first) candidate only |")
    L.append("|---|---:|---:|")
    for k in ("full_match", "partial_match", "not_found"):
        L.append(f"| {k} | {lab.get(k, 0)} | {prim.get(k, 0)} |")
    other = {k: c_ for k, c_ in lab.items() if k not in ("full_match", "partial_match", "not_found")}
    if other:
        L.append(f"| other | {sum(other.values())} ({other}) | |")
    L.append("")
    L.append(f"Sources were taken from a non-primary header candidate in "
             f"{sum(1 for x in s if x['source_from_candidate_index'] not in ('', 0))} incidents.\n")
    L.append("### By year\n")
    L.append("| Year | In scope | Victim found | Source | Compiles | Slither |")
    L.append("|---|---:|---:|---:|---:|---:|")
    for y in sorted(by_year):
        b = by_year[y]
        L.append(f"| {y} | {b[0]} | {b[1]} | {b[2]} | {b[3]} | {b[4]} |")
    L.append("")
    L.append("## Where incidents drop out\n")
    drop = collections.Counter(x["funnel_stage_reached"] for x in rows)
    L.append("| Final stage reached | Count |")
    L.append("|---|---:|")
    for k, c_ in drop.most_common():
        L.append(f"| {k} | {c_} |")
    L.append("")
    nv = [x for x in rows if not x["victim_found"]]
    L.append(f"- **No victim address in header ({len(nv)}):** the `// Vulnerable Contract :` line is empty and no "
             "header comment tags an address as victim/vulnerable. Most of these headers still list addresses "
             "(untagged, or in free-form prose); the full catalog's parser or a manual pass can recover many of them. "
             "This pass used only `Vulnerable Contract`, `Victim` and inline `victim`/`vulnerab` tags.")
    L.append(f"- **Sourcify not_found ({len(nf)}):** no candidate address verified on Sourcify. These are the incidents an "
             "Etherscan key would most likely rescue (many DeFi contracts are verified only on Etherscan); some are "
             "genuinely unverified. " + f"{sum(1 for x in nf if 'unverified' in x['incident'].lower() or x['unverified_hint'])} of them "
             "are named `unverified_*` by DeFiHackLabs or say 'unverified'/'not verified'/'not open source' in the PoC header, "
             "so an Etherscan key would not help those.")
    if comp_fail:
        L.append(f"- **Compile failures ({sum(comp_fail.values())}):** " + ", ".join(f"{k}: {c_}" for k, c_ in comp_fail.most_common()))
    if sl_fail:
        L.append(f"- **Slither failures ({sum(sl_fail.values())}):** " + ", ".join(f"{k}: {c_}" for k, c_ in sl_fail.most_common()))
    L.append("")
    L.append("## Proxies\n")
    impl1967 = [x for x in s if x["is_proxy"] == "impl_with_eip1967_slot"]
    L.append(f"**{len(proxies)} of {len(s)}** recovered sources are proxies (Sourcify `proxyResolution` says proxy, or "
             "the contract is named *Proxy* and uses delegatecall). For these, Slither scanned the proxy shell, not the "
             f"logic that was exploited, so their finding counts are not meaningful. A further {len(impl1967)} reference "
             "the EIP-1967 slot but are themselves logic contracts (e.g. UUPS implementations) and were scanned as "
             "such. Historical implementations at the exploit block were **not** resolved in this "
             "pass (needs archive RPC, ENR-3); Sourcify's `implementations` field reflects the current implementation.\n")
    L.append("## Slither findings (incidents where Slither ran)\n")
    L.append(f"- Median findings per contract, whole compilation unit: **{med(totals)}** "
             f"(min {min(totals) if totals else '-'}, max {max(totals) if totals else '-'}, total {sum(totals)})")
    L.append(f"- Median excluding findings whose first location is in an obvious dependency path "
             f"(OpenZeppelin, node_modules, lib/...): **{med(nondep)}**")
    L.append(f"- Median whose first location is in the compilation target's own file: **{med(intarget)}**")
    u_tot = [x["slither_findings_total"] for x in usable]
    u_tgt = [x["findings_in_target_file"] for x in usable]
    L.append(f"- Non-proxy contracts only ({len(usable)}): median **{med(u_tot)}** whole unit, **{med(u_tgt)}** in target file")
    L.append("")
    L.append("| Impact | Total | Median per contract |")
    L.append("|---|---:|---:|")
    for k in IMPACTS:
        L.append(f"| {k} | {impact_tot[k]} | {impact_med[k]} |")
    L.append("")
    L.append("Top detectors (total findings / contracts where it fired):\n")
    L.append("| Detector | Findings | Contracts |")
    L.append("|---|---:|---:|")
    for k, c_ in det_tot.most_common(15):
        L.append(f"| {k} | {c_} | {det_contracts[k]} |")
    L.append("")
    L.append("## Caveats (stated, not measured)\n")
    L.append("- \"Compiles\" means solc produced no errors from Sourcify's own sources and settings. It is not a "
             "bytecode re-match and not a buildable project in the ENR-2 sense.")
    L.append("- The funnel scans one contract per incident (first header candidate with source). Multi-contract root "
             "causes and proxied logic are not covered.")
    L.append("- Slither finding counts say nothing about whether the causal weakness was flagged; that is a separate "
             "M0 measurement.")
    L.append("- Mainnet selection uses the PoC's first fork call only; cross-chain incidents whose first fork is "
             "another chain are excluded.")
    with open(os.path.join(out_dir, "summary.md"), "w") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L[:30]))


if __name__ == "__main__":
    main()
