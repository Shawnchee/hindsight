#!/usr/bin/env python3
"""Pick a stratified M0 hand-review sample from ethereum_incidents.csv (PRD §15, REV-5).

Strata: year (2021-2026), mapped root cause (label_map.csv), complexity proxy, loss bucket.
Selection is a deterministic greedy fill (fixed seed for tie-breaks) so the same inputs
always give the same sample.

The complexity column is a PROXY computed from the PoC body (header comments stripped):
`multi_step` if the PoC references >= 8 distinct hard-coded addresses or has >= 130
non-comment lines, else `single_function`. It counts PoC size, not the victim's code, so
reviewers should overwrite it with the real answer (one obvious function vs several).

Usage:
    python3 -I m0/scripts/catalog/build_m0_sample.py --dhl m0/data/catalog/dhl \
        --incidents m0/catalog/ethereum_incidents.csv --labels m0/catalog/label_map.csv \
        --out m0/catalog/m0_sample.csv --n 40
"""
import argparse
import csv
import os
import random
import re
import sys
from collections import Counter

YEAR_QUOTA = {"2021": 5, "2022": 7, "2023": 7, "2024": 7, "2025": 7, "2026": 7}
# Root-cause targets: a floor of 2 per class so rare classes are present, the remainder
# roughly proportional to the Ethereum population (business_logic 80, access_control 58,
# price_oracle_trust 43, input_validation 34, reentrancy 26, arbitrary_external_call 23,
# rounding_precision 17, signature_validation 6, governance_design 6, uninit 5, storage 3).
# `other` is capped at 3: it is useful for testing the taxonomy, not for measuring coverage.
# Classes are hard-capped at their target unless a year has nothing else left.
RC_TARGET = {"business_logic": 6, "access_control": 5, "price_oracle_trust": 5,
             "input_validation": 4, "reentrancy": 3, "arbitrary_external_call": 3,
             "rounding_precision": 3, "other": 3, "signature_validation": 2,
             "governance_design": 2, "uninitialized_or_unprotected_init": 2,
             "storage_collision": 2}
SEED = 20261022
ADDR_RE = re.compile(r"0x[0-9a-fA-F]{40}(?![0-9a-fA-F])")
# Root causes that are not contract-code bugs are not useful for a code-triage spike.
OFFCHAIN_NOTE = "not a contract-code bug"


def poc_features(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        src = fh.read()
    body, in_block = [], False
    for line in src.splitlines():
        s = line.strip()
        if s.startswith("/*"):
            in_block = True
        if in_block:
            if "*/" in s:
                in_block = False
            continue
        if not s or s.startswith("//"):
            continue
        body.append(s)
    text = "\n".join(body)
    n_addr = len({a.lower() for a in ADDR_RE.findall(text)})
    flash = bool(re.search(r"flash", text, re.I))
    multi = n_addr >= 8 or len(body) >= 130
    return len(body), n_addr, flash, "multi_step" if multi else "single_function"


MULT = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "b": 1e9, "billion": 1e9}
USD_RE = re.compile(
    r"\$\s*([\d.,]+)\s*(k|m|b|million|billion|thousand)?\b(?!\s*(?:W?ETH|BNB|BTC))"
    r"|([\d.,]+)\s*(k|m|b|million|billion|thousand)?\s*(?:US\$|USD|USDC|USDT|DAI)\b", re.I)


def usd_estimate(text):
    """Best-effort USD from a free-text loss string. None if not stated in USD-like units."""
    if not text:
        return None
    m = USD_RE.search(text)
    if not m:
        return None
    num, suf = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
    try:
        num = num.rstrip(".,")
        if re.fullmatch(r"\d+,\d{1,2}", num) and suf:  # "6,5M" = 6.5M
            num = num.replace(",", ".")
        v = float(num.replace(",", ""))
    except ValueError:
        return None
    return v * MULT.get((suf or "").lower(), 1)


def loss_bucket(r):
    v = usd_estimate(r["loss_readme"]) or usd_estimate(r["loss_header"])
    if v is None:
        return "unknown_or_non_usd", None
    if v < 100_000:
        return "<100K", v
    if v < 1_000_000:
        return "100K-1M", v
    if v < 10_000_000:
        return "1M-10M", v
    return ">=10M", v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dhl", required=True)
    ap.add_argument("--incidents", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=40)
    a = ap.parse_args()
    assert sum(YEAR_QUOTA.values()) == a.n, "year quotas must sum to --n"
    assert sum(RC_TARGET.values()) == a.n, "root-cause targets must sum to --n"

    lm = {r["raw_label"]: r for r in csv.DictReader(open(a.labels, encoding="utf-8"))}
    rows = list(csv.DictReader(open(a.incidents, encoding="utf-8")))
    cands = []
    excluded = Counter()
    for r in rows:
        if r["year"] not in YEAR_QUOTA:
            excluded["outside 2021-2026"] += 1
            continue
        if r["poc_path"].startswith("MISSING"):
            excluded["no PoC file"] += 1
            continue
        lab = lm[r["raw_label"]]
        if OFFCHAIN_NOTE in lab["note"] or "disclosure" in lab["note"]:
            excluded["off-chain cause or disclosure-only"] += 1
            continue
        loc, n_addr, flash, cx = poc_features(os.path.join(a.dhl, r["poc_path"]))
        lb, usd = loss_bucket(r)
        cands.append({**r, "root_cause": lab["root_cause"], "mechanism": lab["mechanism"],
                      "label_confidence": lab["confidence"], "complexity_proxy": cx,
                      "poc_code_lines": loc, "poc_distinct_addresses": n_addr,
                      "poc_mentions_flash": "yes" if flash else "no",
                      "loss_bucket": lb, "loss_usd_est": "" if usd is None else int(usd)})

    rng = random.Random(SEED)
    for c in cands:
        c["_tie"] = rng.random()
    all_roots = sorted({c["root_cause"] for c in cands})

    picked, rc_n, lb_n, cx_n_year, conf_n = [], Counter(), Counter(), Counter(), Counter()
    quota = dict(YEAR_QUOTA)
    stems = set()

    def stem(c):
        # crude protocol-family key: first 5 letters of the name ("AztecV1", "AztecConnect")
        return re.sub(r"[^a-z]", "", c["name"].lower())[:5]
    pool = list(cands)
    # Round-robin over years so no year grabs the rare categories first.
    while any(quota.values()):
        for y in sorted(quota):
            if not quota[y]:
                continue
            ys = [c for c in pool if c["year"] == y]
            if not ys:
                quota[y] = 0
                continue

            def score(c):
                t = RC_TARGET.get(c["root_cause"], 1)
                n = rc_n[c["root_cause"]]
                # fill the class furthest below its target; over-target is a last resort
                s = 4.0 * (t - n) / t if n < t else -10.0 - n
                s += 1.5 / (1 + cx_n_year[(y, c["complexity_proxy"])])  # mix complexity per year
                s += 1.0 / (1 + lb_n[c["loss_bucket"]])          # mix loss sizes
                s += 0.5 / (1 + conf_n[c["label_confidence"]])   # include some low-confidence labels
                if stem(c) in stems:                              # one per protocol family
                    s -= 5.0
                return s + 0.01 * c["_tie"]

            best = max(ys, key=score)
            why = [f"{y} slot ({YEAR_QUOTA[y]} for this year)"]
            if rc_n[best["root_cause"]] == 0:
                why.append(f"first {best['root_cause']} in sample")
            else:
                why.append(f"{best['root_cause']} #{rc_n[best['root_cause']] + 1} "
                           f"of target {RC_TARGET.get(best['root_cause'], 1)}")
            why.append(f"{best['complexity_proxy']} proxy "
                       f"({best['poc_code_lines']} code lines, {best['poc_distinct_addresses']} addrs)")
            why.append(f"loss {best['loss_bucket']}")
            if best["label_confidence"] == "low":
                why.append("low-confidence label: tests the taxonomy")
            best["why_picked"] = "; ".join(why)
            picked.append(best)
            pool.remove(best)
            stems.add(stem(best))
            rc_n[best["root_cause"]] += 1
            lb_n[best["loss_bucket"]] += 1
            cx_n_year[(y, best["complexity_proxy"])] += 1
            conf_n[best["label_confidence"]] += 1
            quota[y] -= 1

    picked.sort(key=lambda c: c["date"])
    cols = ["incident_id", "date", "year", "name", "raw_label", "root_cause", "mechanism",
            "label_confidence", "complexity_proxy", "poc_code_lines", "poc_distinct_addresses",
            "poc_mentions_flash", "loss_bucket", "loss_usd_est", "loss_readme", "poc_path",
            "victim_addresses", "attack_tx_hashes", "chain_source", "why_picked"]
    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(picked)

    print(f"candidates: {len(cands)}; excluded: {dict(excluded)}")
    print("by year:", dict(sorted(Counter(c['year'] for c in picked).items())))
    print("by root_cause:", dict(rc_n.most_common()))
    missing = [r for r in all_roots if not rc_n[r]]
    print("root causes with candidates but not sampled:", missing)
    print("by complexity:", dict(Counter(c['complexity_proxy'] for c in picked)))
    print("by loss bucket:", dict(lb_n))
    print("by label confidence:", dict(conf_n))
    print("candidate complexity mix:", dict(Counter(c['complexity_proxy'] for c in cands)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
