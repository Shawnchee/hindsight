"""Prepare the M0 review sample: for each incident in m0/catalog/m0_sample.csv, collect
victim-contract candidates, fetch their verified source from Sourcify, compile, and run Slither.

Candidates = victim addresses from the PoC header (catalog), then addresses that appear in the
PoC code, in order of first appearance. Well-known tokens, routers and the Foundry cheatcode
address are skipped. The reviewer picks the real victim in the review CLI.

Reuses the funnel helpers (Sourcify cache is shared with the funnel). Only solc and Slither touch
the downloaded sources; the PoC is read as text.

Usage (from repo root):
  VIRTUAL_ENV=$PWD/.venv .venv/bin/python -I m0/scripts/review/prepare.py \
      m0/catalog/m0_sample.csv m0/data/funnel/dhl m0/data/review [--max-candidates 6] [--only <id-substring>]
"""
import csv
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "funnel"))
from build_and_scan import (PY, compile_solc, ensure_solc, match_label, proxy_info,  # noqa: E402
                            safe_rel, to_std_settings)
from fetch_sourcify import fetch  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SOURCIFY_CACHE = os.path.join(REPO, "m0", "data", "funnel", "sourcify")
SLITHER_ONE = os.path.join(HERE, "..", "funnel", "slither_one.py")
ADDR_RE = re.compile(r"0x[0-9a-fA-F]{40}\b")

# Addresses that are almost never the victim: cheatcodes, major tokens, routers, flash-loan pools.
SKIP = {a.lower() for a in [
    "0x7109709ECfa91a80626fF3989D68f67F5b1DD12D",  # Foundry cheatcodes
    "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
    "0xdAC17F958D2ee523a2206206994597C13D831ec7",  # USDT
    "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # USDC
    "0x6B175474E89094C44Da98b954EedeAC495271d0F",  # DAI
    "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",  # WBTC
    "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",  # Uniswap V2 router
    "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",  # Uniswap V2 factory
    "0xE592427A0AEce92De3Edee1F18E0157C05861564",  # Uniswap V3 router
    "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",  # Uniswap V3 router 02
    "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",  # Sushi router
    "0xBA12222222228d8Ba445958a75a0704d566BF2C8",  # Balancer vault
    "0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9",  # Aave V2 pool
    "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",  # Aave V3 pool
    "0x0000000000000000000000000000000000000000",
]}


def strip_comments(code):
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    return re.sub(r"//[^\n]*", "", code)


def candidates(row, dhl, maxc):
    out = []
    for a in ADDR_RE.findall(row.get("victim_addresses") or ""):
        if a.lower() not in out:
            out.append(a.lower())
    try:
        code = open(os.path.join(dhl, row["poc_path"]), errors="replace").read()
    except OSError:
        code = ""
    for a in ADDR_RE.findall(strip_comments(code)):
        a = a.lower()
        if a not in out and a not in SKIP:
            out.append(a)
    return out[:maxc]


def scan(d, folder):
    """Write sources, compile, run Slither. Returns a result dict."""
    comp = d.get("compilation") or {}
    res = {"contract_name": comp.get("name"), "language": comp.get("language"),
           "compiler_version": comp.get("compilerVersion"),
           "target_file": (comp.get("fullyQualifiedName") or "").rpartition(":")[0],
           "n_source_files": len(d.get("sources") or {}),
           "deployment_block": (d.get("deployment") or {}).get("blockNumber")}
    is_proxy, ev, impls = proxy_info(d)
    res.update(is_proxy=is_proxy, proxy_evidence=ev, sourcify_current_impls=impls)
    sdir = os.path.join(folder, "sources")
    for k, v in (d.get("sources") or {}).items():
        p = os.path.join(sdir, safe_rel(k))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write((v or {}).get("content", ""))
    res["source_dir"] = os.path.relpath(sdir, REPO)
    if comp.get("language") != "Solidity":
        return dict(res, compile_ok=False, compile_error_class=f"language_{comp.get('language')}")
    std = {"language": "Solidity",
           "sources": {k: {"content": (v or {}).get("content", "")} for k, v in d["sources"].items()},
           "settings": to_std_settings(comp.get("compilerSettings") or {})}
    std_path = os.path.join(folder, "std_input.json")
    with open(std_path, "w") as f:
        json.dump(std, f)
    ver = (comp.get("compilerVersion") or "").split("+")[0].lstrip("v")
    solc, err = ensure_solc(ver)
    if not solc:
        return dict(res, compile_ok=False, compile_error_class="solc_install_failed", compile_error=err)
    ok, cls, msg, _ = compile_solc(solc, std, folder)
    res.update(compile_ok=ok, compile_error_class=cls, compile_error=msg)
    if not ok:
        return res
    sj = os.path.join(folder, "slither.json")
    try:
        subprocess.run([PY, "-I", SLITHER_ONE, std_path, solc, sj, sdir], cwd=sdir,
                       capture_output=True, text=True, timeout=1800)
        s = json.load(open(sj))
    except subprocess.TimeoutExpired:
        s = {"success": False, "error": "Timeout: >1800s", "detectors": []}
    except Exception as e:  # noqa: BLE001
        s = {"success": False, "error": f"runner: {e!r}", "detectors": []}
    return dict(res, slither_ok=s["success"], slither_error=s.get("error"), detectors=s["detectors"])


def main():
    sample, dhl, out_root = (os.path.abspath(a) for a in sys.argv[1:4])
    args = sys.argv[4:]
    maxc = int(args[args.index("--max-candidates") + 1]) if "--max-candidates" in args else 6
    only = args[args.index("--only") + 1] if "--only" in args else None
    prep_dir = os.path.join(out_root, "prepared")
    os.makedirs(prep_dir, exist_ok=True)
    os.makedirs(SOURCIFY_CACHE, exist_ok=True)
    for row in csv.DictReader(open(sample)):
        iid = row["incident_id"]
        if only and only not in iid:
            continue
        rec = {"incident_id": iid, "prepared_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "poc_path": row["poc_path"], "candidates": []}
        for addr in candidates(row, dhl, maxc):
            d, _ = fetch(addr, SOURCIFY_CACHE, 1.5)
            c = {"address": addr, "sourcify": match_label(d),
                 "from_header": addr in (row.get("victim_addresses") or "").lower()}
            if c["sourcify"] in ("full_match", "partial_match") and d.get("sources"):
                c.update(scan(d, os.path.join(out_root, "src", iid, addr)))
            rec["candidates"].append(c)
        with open(os.path.join(prep_dir, iid + ".json"), "w") as f:
            json.dump(rec, f, indent=1)
        print(iid, [(c["address"][:10], c["sourcify"], c.get("contract_name"), len(c.get("detectors", [])))
                    for c in rec["candidates"]], flush=True)


if __name__ == "__main__":
    main()
