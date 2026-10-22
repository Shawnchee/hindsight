"""Build the B2 v2 blind pool: post-cutoff exploited victims and clean audited contracts, mixed under
opaque case IDs, so the model can't tell which cases are exploited.

  exploit cases: in-scope post-cutoff incidents whose blind Fable review names victim(s) with source
                 (from --reviews, using sources prepared under --prepared)
  clean cases:   well-known audited mainnet contracts with no known exploit, fetched from Sourcify. Each one
                 is kept only if Sourcify's contract name matches the expected name.

Usage (from repo root):
  python3 -I m0/scripts/b2/prepare_b2v2.py --reviews m0/review/postcutoff/reviews.llm.jsonl \
      --prepared m0/data/postcutoff/prepared
Writes m0/data/b2v2/inputs/ and m0/data/b2v2/case_map.json (the answer key; B2 agents must not read it).
"""
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(HERE, "..", "funnel"))
from build_and_scan import safe_rel  # noqa: E402
from fetch_sourcify import fetch  # noqa: E402

OUT = os.path.join(REPO, "m0", "data", "b2v2")
CACHE = os.path.join(REPO, "m0", "data", "funnel", "sourcify")

# (address, expected Sourcify contract name). Widely used, audited, and no known exploit of the contract itself
# as of 2026-10-22. Famous contracts are likely in model pretraining, which flatters the false-positive rate.
CLEAN = [
    ("0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2", "WETH9"),
    ("0x7a250d5630b4cf539739df2c5dacb4c659f2488d", "UniswapV2Router02"),
    ("0x5c69bee701ef814a2b6a3edd4b1652cb9cc5aa6f", "UniswapV2Factory"),
    ("0x1f98431c8ad98523631ae4a59f267346ea31f984", "UniswapV3Factory"),
    ("0xe592427a0aece92de3edee1f18e0157c05861564", "SwapRouter"),
    ("0xc36442b4a4522e871399cd717abdd847ab11fe88", "NonfungiblePositionManager"),
    ("0x000000000022d473030f116ddee9f6b43ac78ba3", "Permit2"),
    ("0xbbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb", "Morpho"),
    ("0xd9db270c1b5e3bd161e8c8503c55ceabee709552", "GnosisSafe"),
    ("0x00000000000000adc04c56bf30ac9d3c0aaf14dc", "Seaport"),
    ("0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad", "UniversalRouter"),
    ("0xa39739ef8b0231dbfa0dcda07d7e29faabcf4bb2", "TroveManager"),
]


def case_id(key):
    return "case_" + hashlib.sha256(("v2:" + key).encode()).hexdigest()[:8]


def write_sources(d, dest):
    for k, v in (d.get("sources") or {}).items():
        p = os.path.join(dest, safe_rel(k))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write((v or {}).get("content", ""))


def main():
    args = sys.argv[1:]
    reviews = os.path.abspath(args[args.index("--reviews") + 1]) if "--reviews" in args else None
    prepared = os.path.abspath(args[args.index("--prepared") + 1]) if "--prepared" in args else None
    if os.path.exists(os.path.join(OUT, "inputs")):
        shutil.rmtree(os.path.join(OUT, "inputs"))
    case_map, dropped = {}, []
    for addr, name in CLEAN:
        d, _ = fetch(addr, CACHE, 1.5)
        got = (d.get("compilation") or {}).get("name")
        if d.get("_status") != 200 or got != name or not d.get("sources"):
            dropped.append(f"{addr} expected {name}, got {got} (status {d.get('_status')})")
            continue
        c = case_id(addr)
        write_sources(d, os.path.join(OUT, "inputs", c, "contract_1"))
        case_map[c] = {"kind": "clean", "id": f"{name}@{addr}"}
    if reviews and prepared:
        for line in open(reviews):
            r = json.loads(line)
            if not r["in_scope"] or not r["slither_ran_on_victim"]:
                continue
            prep = json.load(open(os.path.join(prepared, r["incident_id"] + ".json")))
            cands = {c["address"]: c for c in prep["candidates"]}
            dirs = [os.path.join(REPO, cands[a]["source_dir"]) for a in r["victims"]
                    if a in cands and cands[a].get("source_dir")]
            if not dirs:
                continue
            c = case_id(r["incident_id"])
            for n, d in enumerate(dirs, 1):
                shutil.copytree(d, os.path.join(OUT, "inputs", c, f"contract_{n}"))
            case_map[c] = {"kind": "exploit", "id": r["incident_id"]}
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "case_map.json"), "w") as f:
        json.dump(case_map, f, indent=1)
    kinds = [v["kind"] for v in case_map.values()]
    print(f"{kinds.count('exploit')} exploit + {kinds.count('clean')} clean cases")
    for d in dropped:
        print("dropped clean:", d)
    print(" ".join(sorted(case_map)))


if __name__ == "__main__":
    main()
