"""Measure Ethereum incidents that DeFiHackLabs (DHL) misses, using DeFiLlama hacks as the comparison source.

Reads only (never executes) a shallow DHL clone and a cached DeFiLlama /hacks JSON.
Run with:  python3 -I m0/scripts/gaps/measure_gaps.py --data m0/data/gaps --out m0/gaps

DeFiLlama data is under a personal, non-commercial licence (PRD 7.1): outputs carry only
counts plus incident names and dates, never other DeFiLlama fields.
"""

import argparse
import datetime as dt
import difflib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

WINDOW_START = "2024-11"
WINDOW_END = "2026-10"
GAP_MONTHS = ["2025-09", "2025-10", "2025-11", "2025-12", "2026-01", "2026-02"]
DATE_TOL_DAYS = 7
FUZZY_RATIO = 0.85
NEAR_RATIO = 0.6
OFFCHAIN_CLASSES = {"Key Compromise", "Frontend & Infrastructure", "Social Engineering", "Rugpull"}
ETH_CHAIN_NAMES = {"ethereum"}
ETH_FORK_IDS = {"mainnet", "eth", "ethereum"}

STOP_SUFFIXES = [
    "finance", "protocol", "network", "exchange", "labs", "dao", "token", "swap", "fi",
    "io", "xyz", "app", "v1", "v2", "v3", "v4", "exploit", "hack", "attack", "vault",
]

HEADER_RE = re.compile(r"^### (\d{8}) (.+?)\s*$")
FORK_RE = re.compile(r'createSelectFork\(\s*"([A-Za-z0-9_]+)"')
CONTRACT_RE = re.compile(r"(src/test/[^)\s]+?\.sol)")


def norm(name):
    s = name.lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    changed = True
    while changed:
        changed = False
        for suf in STOP_SUFFIXES:
            if s.endswith(suf) and len(s) - len(suf) >= 3:
                s = s[: -len(suf)]
                changed = True
    return s


GENERIC_TOKENS = {
    "the", "finance", "protocol", "network", "bridge", "token", "dao", "lending", "vault", "vaults",
    "swap", "bot", "mev", "ai", "dex", "labs", "capital", "money", "cash", "old", "contract",
    "v1", "v2", "v3", "v4", "eth", "ethereum", "perp", "liquid", "lm", "fi", "usd",
}

# Hand-checked aliases for names the string rules can't link (DeFiLlama name -> DHL name, both normalized).
ALIASES = {
    ("yearnether", "yeth"),
    ("sorra", "sorstaking"),
}


def tokens(name):
    out = []
    for t in re.split(r"[\s/_\-]+", name.lower().replace("(", " ").replace(")", " ")):
        t = re.sub(r"[^a-z0-9]", "", t)
        if len(t) >= 3 and t not in GENERIC_TOKENS:
            out.append(t)
    return out


def deleet(s):
    return s.replace("0", "o")


def name_score(a, b, raw_a="", raw_b=""):
    """1.0 exact; 0.95 substring/token-prefix/long shared prefix/alias; else difflib ratio."""
    if not a or not b:
        return 0.0
    if a == b or deleet(a) == deleet(b):
        return 1.0
    if (a, b) in ALIASES or (b, a) in ALIASES:
        return 0.95
    short, long_ = sorted((a, b), key=len)
    if len(short) >= 4 and short in long_:
        return 0.95
    # Shared leading run of >= 6 chars (e.g. unistreets / unistreetlaunchpad).
    n = 0
    while n < len(short) and short[n] == long_[n]:
        n += 1
    if n >= 6:
        return 0.9
    # A distinctive word of one name starts or ends the other's compact form (e.g. "The Idols" / IdolsNFT).
    for ta, other in ((tokens(raw_a), b), (tokens(raw_b), a)):
        for t in ta:
            t = norm(t) or t
            if len(t) >= 3 and (other.startswith(t) or other.endswith(t)):
                return 0.9
    return difflib.SequenceMatcher(None, a, b).ratio()


def month(d):
    return d.strftime("%Y-%m")


def months_between(start, end):
    y, m = map(int, start.split("-"))
    out = []
    while f"{y:04d}-{m:02d}" <= end:
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def parse_dhl(dhl_root):
    readmes = [dhl_root / "README.md"] + sorted((dhl_root / "past").glob("*/README.md"))
    entries = []
    for path in readmes:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines):
            m = HEADER_RE.match(line)
            if not m:
                continue
            try:
                date = dt.datetime.strptime(m.group(1), "%Y%m%d").date()
            except ValueError:
                continue
            rest = m.group(2)
            name = rest.split(" - ", 1)[0].strip()
            # Look ahead within this entry for the Lost line and contract link.
            block = []
            for nxt in lines[i + 1 : i + 15]:
                if HEADER_RE.match(nxt):
                    break
                block.append(nxt)
            block_txt = "\n".join(block)
            chain = None
            cm = CONTRACT_RE.search(block_txt)
            sol = None
            if cm:
                sol = dhl_root / cm.group(1)
                if sol.is_file():
                    fm = FORK_RE.search(sol.read_text(encoding="utf-8", errors="replace"))
                    if fm:
                        chain = fm.group(1).lower()
            if chain is None:
                lost = " ".join(l for l in block if l.startswith("### Lost")) + " " + rest
                if re.search(r"\bon (Ethereum|ETH mainnet|mainnet)\b", lost, re.I):
                    chain = "mainnet"
                elif re.search(r"\bon (BNB Chain|BSC|Base|Arbitrum|Polygon|Optimism|Avalanche)\b", lost, re.I):
                    chain = "other"
            entries.append({
                "date": date,
                "name": name,
                "norm": norm(name),
                "is_eth": chain in ETH_FORK_IDS,
                "chain_known": chain is not None,
                "readme": str(path.relative_to(dhl_root)),
            })
    # De-duplicate identical (date, name) entries that appear in both main and past READMEs.
    seen, uniq = set(), []
    for e in entries:
        key = (e["date"], e["norm"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(e)
    return uniq


def parse_llama(path):
    raw = json.loads(path.read_text())
    out = []
    for x in raw:
        d = dt.datetime.fromtimestamp(x["date"], dt.timezone.utc).date()
        chains = [c.lower() for c in (x.get("chain") or [])]
        out.append({
            "date": d,
            "name": x.get("name") or "",
            "norm": norm(x.get("name") or ""),
            "is_eth": any(c in ETH_CHAIN_NAMES for c in chains),
            "eth_only": bool(chains) and all(c in ETH_CHAIN_NAMES for c in chains),
            "cls": x.get("classification") or "None",
            "offchain": x.get("classification") in OFFCHAIN_CLASSES,
        })
    return out


def best_match(target, pool, tol=DATE_TOL_DAYS):
    best, best_s = None, 0.0
    for e in pool:
        if abs((e["date"] - target["date"]).days) > tol:
            continue
        s = name_score(target["norm"], e["norm"], target["name"], e["name"])
        if s > best_s:
            best, best_s = e, s
    return best, best_s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--seed", type=int, default=20261022)
    args = ap.parse_args()

    dhl = parse_dhl(args.data / "dhl")
    llama = parse_llama(args.data / "llama_hacks.json")
    months = months_between(WINDOW_START, WINDOW_END)
    in_win = lambda d: WINDOW_START <= month(d) <= WINDOW_END

    llama_eth = [x for x in llama if x["is_eth"] and in_win(x["date"])]
    llama_eth_code = [x for x in llama_eth if not x["offchain"]]
    llama_eth_off = [x for x in llama_eth if x["offchain"]]
    dhl_win = [e for e in dhl if in_win(e["date"])]
    dhl_eth = [e for e in dhl_win if e["is_eth"]]

    # DeFiLlama Ethereum code-level -> any DHL entry (any chain), so a DHL chain mislabel can't fake a miss.
    per_month = {m: Counter() for m in months}
    llama_only, near_misses, date_only_misses, matched = [], [], [], []
    lo_cls, gap_cls, lo_multichain = Counter(), Counter(), 0
    for x in llama_eth_code:
        e, s = best_match(x, dhl)
        mo = month(x["date"])
        if e is not None and s >= FUZZY_RATIO:
            per_month[mo]["both"] += 1
            matched.append({"date": x["date"].isoformat(), "name": x["name"],
                            "dhl": f"{e['date']} {e['name']}", "score": round(s, 2)})
            continue
        per_month[mo]["llama_only"] += 1
        lo_cls[x["cls"]] += 1
        lo_multichain += 0 if x["eth_only"] else 1
        if mo in GAP_MONTHS:
            gap_cls[x["cls"]] += 1
        rec = {"date": x["date"].isoformat(), "name": x["name"],
               "nearest_dhl": f"{e['date']} {e['name']}" if e else "", "nearest_score": round(s, 2)}
        llama_only.append(rec)
        if s >= NEAR_RATIO:
            near_misses.append(rec)
        e30, s30 = best_match(x, dhl, tol=60)
        if e30 is not None and s30 >= FUZZY_RATIO:
            date_only_misses.append({**rec, "dhl_outside_window": f"{e30['date']} {e30['name']}"})

    # DHL Ethereum entries -> any DeFiLlama incident (any chain/class): DHL-only means absent from DeFiLlama.
    dhl_only = []
    for e in dhl_eth:
        x, s = best_match(e, llama)
        if x is None or s < FUZZY_RATIO:
            per_month[month(e["date"])]["dhl_only"] += 1
            dhl_only.append({"date": e["date"].isoformat(), "name": e["name"]})

    totals = Counter()
    gap = Counter()
    for m in months:
        totals.update(per_month[m])
        if m in GAP_MONTHS:
            gap.update(per_month[m])
    gap_off = sum(1 for x in llama_eth_off if month(x["date"]) in GAP_MONTHS)
    dhl_all_per_month = Counter(month(e["date"]) for e in dhl_win)
    dhl_eth_per_month = Counter(month(e["date"]) for e in dhl_eth)

    rng = random.Random(args.seed)
    sample = sorted(rng.sample(llama_only, min(15, len(llama_only))), key=lambda r: r["date"])
    gap_llama_only = [r for r in llama_only if r["date"][:7] in GAP_MONTHS]

    result = {
        "generated_from": {
            "window": [WINDOW_START, WINDOW_END],
            "gap_months": GAP_MONTHS,
            "date_tolerance_days": DATE_TOL_DAYS,
            "fuzzy_ratio": FUZZY_RATIO,
        },
        "counts": {
            "dhl_entries_total_parsed": len(dhl),
            "dhl_entries_window": len(dhl_win),
            "dhl_eth_entries_window": len(dhl_eth),
            "dhl_window_chain_unknown": sum(1 for e in dhl_win if not e["chain_known"]),
            "llama_eth_window": len(llama_eth),
            "llama_eth_offchain_window": len(llama_eth_off),
            "llama_eth_offchain_gap": gap_off,
            "llama_eth_code_window": len(llama_eth_code),
            "totals_window": dict(totals),
            "totals_gap": dict(gap),
            "llama_only_by_classification_window": dict(lo_cls.most_common()),
            "llama_only_by_classification_gap": dict(gap_cls.most_common()),
            "llama_only_multichain_window": lo_multichain,
            "llama_only_near_misses_score_0.6_to_0.85": len(near_misses),
            "llama_only_with_dhl_name_match_within_60d": len(date_only_misses),
        },
        "per_month": {m: {"llama_only": per_month[m]["llama_only"], "dhl_only": per_month[m]["dhl_only"],
                          "both": per_month[m]["both"], "dhl_all_chains": dhl_all_per_month[m],
                          "dhl_eth": dhl_eth_per_month[m]} for m in months},
        "sample_llama_only": sample,
        "gap_llama_only": gap_llama_only,
        "llama_only": llama_only,
        "matched": matched,
        "near_misses": near_misses,
        "date_only_misses": date_only_misses,
        "dhl_only": dhl_only,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "gaps.json").write_text(json.dumps(result, indent=2, default=str) + "\n")
    json.dump(result["counts"], sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
