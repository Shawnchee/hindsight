#!/usr/bin/env python3
"""Parse a read-only DeFiHackLabs clone into an incident catalog.

The clone is UNTRUSTED DATA. This script only reads text files from it; it never
imports, builds or executes anything inside it. Run with `python3 -I` from outside
the clone, passing the clone path as an argument.

Usage:
    python3 -I m0/scripts/catalog/parse_dhl.py \
        --dhl m0/data/catalog/dhl --out m0/catalog

Writes:
    <out>/all_incidents.csv        every README entry, all chains (intermediate)
    <out>/ethereum_incidents.csv   Ethereum mainnet only
    <out>/summary.md               per-year counts + chain resolution stats
"""
import argparse
import csv
import os
import re
import subprocess
import sys
from collections import Counter, OrderedDict

# --- README parsing ---------------------------------------------------------

ENTRY_RE = re.compile(r"^###\s+(\d{8})\s+(.*?)\s*$")
# One malformed heading uses hyphens: "### 20240924-MARA---price-manipulation"
ENTRY_DASH_RE = re.compile(r"^###\s+(\d{8})-([^-]+)-+(.*?)\s*$")
LOST_RE = re.compile(r"^#{0,6}\s*(?:Lost|Total Lost)\s*:?\s*(.*)$", re.I)
POC_LINK_RE = re.compile(r"\]\(([^)\s]*src/test/[^)\s]+\.sol)\)")
# Headings that close the incident index (everything else under an entry belongs to it,
# e.g. "### Lost", "### Rescued", "### Contract", "### Link reference").
SECTION_END_RE = re.compile(
    r"^###\s+(Transaction debugging tools|Useful tools|OnChain transaction debugging|"
    r"View Gas Reports|Ethereum Signature Database|Hacks Dashboard)\b", re.I)
FORGE_RE = re.compile(r"--contracts\s+\.?/?(src/test/\S+)")


def split_name_label(rest):
    # Name and label are separated by the first " - ".
    rest = re.sub(r"^-\s+", "", rest.strip())  # "### 20230317 - Name - Label"
    if " - " in rest:
        name, label = rest.split(" - ", 1)
        return name.strip(), label.strip()
    return rest.strip(), ""


def parse_readme(path, rel_readme):
    entries = []
    cur = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()
    for line in lines:
        m = ENTRY_RE.match(line)
        md = None if m else ENTRY_DASH_RE.match(line)
        if m or md:
            if cur:
                entries.append(cur)
            if m:
                name, label = split_name_label(m.group(2))
                date = m.group(1)
            else:
                date, name, label = md.group(1), md.group(2), md.group(3).replace("-", " ")
            cur = {"date": date, "name": name, "raw_label": label, "readme": rel_readme,
                   "readme_lost": "", "poc_links": [], "forge_paths": []}
            continue
        if cur is None:
            continue
        if SECTION_END_RE.match(line):
            # e.g. "### Transaction debugging tools" closes the index
            entries.append(cur)
            cur = None
            continue
        rm = re.match(r"^#{0,6}\s*Rescued\s*:?\s*(.*)$", line.strip(), re.I)
        if rm and not cur["readme_lost"]:
            cur["readme_lost"] = "Rescued: " + rm.group(1).strip()
        lm = LOST_RE.match(line.strip())
        if lm and not cur["readme_lost"] and line.strip().startswith(("#", "Lost", "Total")):
            cur["readme_lost"] = lm.group(1).strip()
        for fp in FORGE_RE.findall(line):
            if fp not in cur["forge_paths"]:
                cur["forge_paths"].append(fp)
        for pl in POC_LINK_RE.findall(line):
            p = pl[pl.index("src/test/"):]
            if p not in cur["poc_links"]:
                cur["poc_links"].append(p)
    if cur:
        entries.append(cur)
    return entries


# --- PoC parsing ------------------------------------------------------------

ALIAS_CHAIN = {
    "mainnet": "ethereum", "eth": "ethereum", "ethereum": "ethereum",
    "bsc": "bsc", "arbitrum": "arbitrum", "base": "base", "polygon": "polygon",
    "avalanche": "avalanche", "optimism": "optimism", "fantom": "fantom",
    "linea": "linea", "gnosis": "gnosis", "blast": "blast", "zksync": "zksync",
    "sei": "sei", "moonriver": "moonriver", "mantle": "mantle", "celo": "celo",
    "cronos": "cronos", "citrea": "citrea",
}
# Ordered: first match wins. Checked against the URL host.
HOST_CHAIN = [
    ("bsc", "bsc"), ("binance", "bsc"), ("polygon", "polygon"), ("arb", "arbitrum"),
    ("optimism", "optimism"), ("base", "base"), ("avax", "avalanche"),
    ("fantom", "fantom"), ("linea", "linea"), ("blast", "blast"),
    ("hyperliquid", "hyperliquid"), ("gnosis", "gnosis"),
    ("eth", "ethereum"),
]
FORK_RE = re.compile(r"\bcreateSelectFork\s*\(\s*([^,)]+)")
CREATEFORK_RE = re.compile(r"\bcreateFork\s*\(\s*([^,)]+)")
CONST_RE_T = r"\bstring\s+(?:(?:internal|private|public|constant|immutable)\s+)*{name}\s*=\s*\"([^\"]+)\""

ADDR_RE = re.compile(r"0x[0-9a-fA-F]{40}(?![0-9a-fA-F])")
TX_RE = re.compile(r"0x[0-9a-fA-F]{64}(?![0-9a-fA-F])")
CODE_START_RE = re.compile(r"^\s*(?:abstract\s+)?(?:contract|interface|library)\s+\w+")

EXPLORER_CHAIN = [
    ("etherscan.io", "ethereum"), ("/tx/eth/", "ethereum"), ("/tx/ethereum/", "ethereum"),
    ("/address/eth/", "ethereum"), ("bscscan.com", "bsc"), ("/tx/bsc/", "bsc"),
    ("polygonscan", "polygon"), ("arbiscan", "arbitrum"), ("basescan", "base"),
    ("optimistic.etherscan", "optimism"), ("snowtrace", "avalanche"), ("ftmscan", "fantom"),
    ("blastscan", "blast"), ("lineascan", "linea"), ("gnosisscan", "gnosis"),
]


def host_chain(url):
    host = re.sub(r"^\w+://", "", url).split("/")[0].lower()
    for key, chain in HOST_CHAIN:
        if key in host:
            return chain
    return None


def resolve_fork_arg(arg, src):
    """Return (chain, source). chain is 'unresolved' when it can't be read statically."""
    arg = arg.strip()
    if arg.startswith('"'):
        val = arg.strip('"')
        if val.lower() in ALIAS_CHAIN:
            return ALIAS_CHAIN[val.lower()], "fork_alias"
        if "://" in val:
            c = host_chain(val)
            return (c, "fork_url") if c else ("unresolved", "fork_url_unknown_host")
        return "unresolved", "fork_unknown_alias"
    ident = re.match(r"[A-Za-z_]\w*$", arg)
    if ident:
        m = re.search(CONST_RE_T.format(name=re.escape(arg)), src)
        if m:
            val = m.group(1)
            if val.lower() in ALIAS_CHAIN:
                return ALIAS_CHAIN[val.lower()], "fork_const_alias"
            if "://" in val:
                c = host_chain(val)
                if c:
                    return c, "fork_const_url"
        return "unresolved", "fork_identifier"
    return "unresolved", "fork_expression"


def header_lines(src):
    out = []
    in_block = False
    for line in src.splitlines():
        if CODE_START_RE.match(line):
            break
        s = line.strip()
        if s.startswith("/*"):
            in_block = True
        if in_block or s.startswith("//") or s.startswith("*"):
            out.append(s)
        if "*/" in s:
            in_block = False
    return out


def kv_split(line):
    s = line.lstrip("/* ").strip()
    if ":" not in s:
        return "", s
    k, v = s.split(":", 1)
    if k.lower().startswith(("http", "https")):
        return "", s
    return k.strip().lower(), v.strip()


def classify_key(k):
    k = k.replace("@keyinfo", "").strip(" -")
    if not k:
        return None
    if re.search(r"\b(tx|txs|transaction|hash)\b", k) and "contract" not in k:
        return "tx"
    if "attack contract" in k or "exploit contract" in k or "attacker contract" in k:
        return "attack_contract"
    if re.search(r"attacker|exploiter|hacker", k):
        return "attacker_eoa"
    if re.search(r"vulnerab|victim|target|exploited|affected|proxy|implementation|pool|vault|logic", k):
        return "victim"
    if re.search(r"total lost|^lost|profit|loss", k):
        return "loss"
    return None


def parse_poc(abs_path):
    with open(abs_path, encoding="utf-8", errors="replace") as fh:
        src = fh.read()
    r = {"fork_arg_raw": "", "fork_chain": "unresolved", "fork_source": "no_fork_call",
         "header_chain_hint": "", "victim_addresses": [], "attack_contract_addresses": [],
         "attacker_eoa_addresses": [], "attack_tx_hashes": [], "header_loss": "",
         "header_has_analysis": False, "loc": src.count("\n") + 1}
    m = FORK_RE.search(src)
    if not m:
        m = CREATEFORK_RE.search(src)
        via = "createFork"
    else:
        via = "createSelectFork"
    if m:
        r["fork_arg_raw"] = m.group(1).strip()
        r["fork_chain"], r["fork_source"] = resolve_fork_arg(m.group(1), src)
        if via == "createFork":
            r["fork_source"] += "(createFork)"

    hdr = header_lines(src)
    hdr_text = "\n".join(hdr)
    hints = Counter()
    for key, chain in EXPLORER_CHAIN:
        n = hdr_text.lower().count(key)
        if n:
            hints[chain] += n
    if hints.get("optimism"):
        hints["ethereum"] -= hints["optimism"]  # optimistic.etherscan contains etherscan
    hints = +hints
    r["header_chain_hint"] = ";".join(sorted(hints)) if hints else ""

    analysis_markers = 0
    for line in hdr:
        k, v = kv_split(line)
        role = classify_key(k) if k else None
        if role is None:
            continue
        if role == "loss":
            if not r["header_loss"]:
                r["header_loss"] = v[:200]
            continue
        if role == "tx":
            for h in TX_RE.findall(v):
                h = h.lower()
                if h not in r["attack_tx_hashes"]:
                    r["attack_tx_hashes"].append(h)
            continue
        dest = {"victim": "victim_addresses", "attack_contract": "attack_contract_addresses",
                "attacker_eoa": "attacker_eoa_addresses"}[role]
        for a in ADDR_RE.findall(v):
            a = a.lower()
            if a not in r[dest]:
                r[dest].append(a)
    # Did the header carry prose beyond the standard key/value lines?
    prose = [l for l in hdr if len(l) > 60 and "http" not in l and ":" not in l[:30]]
    r["header_has_analysis"] = len(prose) >= 3
    return r


def git_head(dhl):
    try:
        out = subprocess.run(["git", "-C", dhl, "log", "-1", "--format=%H %cI"],
                             capture_output=True, text=True, check=True,
                             env={"PATH": os.environ.get("PATH", ""), "GIT_CONFIG_NOSYSTEM": "1",
                                  "HOME": "/nonexistent"})
        return out.stdout.strip()
    except Exception:
        return "unknown"


COLS = ["incident_id", "date", "year", "name", "raw_label", "poc_path", "extra_poc_paths",
        "fork_arg_raw", "fork_chain", "fork_source", "header_chain_hint", "chain",
        "chain_source", "victim_addresses", "attack_contract_addresses",
        "attacker_eoa_addresses", "attack_tx_hashes", "loss_readme", "loss_header",
        "header_has_analysis", "poc_loc", "readme_source"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dhl", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    dhl = os.path.abspath(a.dhl)
    os.makedirs(a.out, exist_ok=True)

    readmes = [("README.md", os.path.join(dhl, "README.md"))]
    past = os.path.join(dhl, "past")
    for y in sorted(os.listdir(past)):
        p = os.path.join(past, y, "README.md")
        if os.path.isfile(p):
            readmes.append((f"past/{y}/README.md", p))

    entries = []
    for rel, p in readmes:
        entries.extend(parse_readme(p, rel))

    rows, ids = [], Counter()
    missing_poc = 0
    referenced = set()
    for e in entries:
        slug = re.sub(r"[^A-Za-z0-9]+", "", e["name"])[:40] or "unnamed"
        base = f"{e['date']}_{slug}"
        ids[base] += 1
        iid = base if ids[base] == 1 else f"{base}_{ids[base]}"
        pocs = e["poc_links"] + [p for p in e["forge_paths"] if p not in e["poc_links"]]
        existing = []
        for p in pocs:
            for cand in (p, p + "_exp.sol", p[:-4] + ".sol_exp.sol" if p.endswith(".sol") else None):
                if cand and os.path.isfile(os.path.join(dhl, cand)) and cand not in existing:
                    existing.append(cand)
                    break
        referenced.update(existing)
        poc = existing[0] if existing else (pocs[0] if pocs else "")
        info = parse_poc(os.path.join(dhl, poc)) if existing else None
        if not existing:
            missing_poc += 1
        row = {
            "incident_id": iid, "date": f"{e['date'][:4]}-{e['date'][4:6]}-{e['date'][6:]}",
            "year": e["date"][:4], "name": e["name"], "raw_label": e["raw_label"],
            "poc_path": poc if existing else (f"MISSING:{poc}" if poc else "MISSING"),
            "extra_poc_paths": ";".join(existing[1:]),
            "loss_readme": e["readme_lost"], "readme_source": e["readme"],
        }
        if info:
            row.update({
                "fork_arg_raw": info["fork_arg_raw"], "fork_chain": info["fork_chain"],
                "fork_source": info["fork_source"], "header_chain_hint": info["header_chain_hint"],
                "victim_addresses": ";".join(info["victim_addresses"]),
                "attack_contract_addresses": ";".join(info["attack_contract_addresses"]),
                "attacker_eoa_addresses": ";".join(info["attacker_eoa_addresses"]),
                "attack_tx_hashes": ";".join(info["attack_tx_hashes"]),
                "loss_header": info["header_loss"],
                "header_has_analysis": "yes" if info["header_has_analysis"] else "no",
                "poc_loc": info["loc"],
            })
        else:
            row.update({"fork_chain": "unresolved", "fork_source": "no_poc"})
        # Final chain: the fork call wins. Only if it is unresolved do we fall back to the
        # header's explorer links, and only when they point at exactly one chain.
        if row["fork_chain"] != "unresolved":
            row["chain"], row["chain_source"] = row["fork_chain"], "fork"
        elif row.get("header_chain_hint") and ";" not in row["header_chain_hint"]:
            row["chain"], row["chain_source"] = row["header_chain_hint"], "header_explorer_fallback"
        else:
            row["chain"], row["chain_source"] = "unresolved", "none"
        rows.append({c: row.get(c, "") for c in COLS})

    rows.sort(key=lambda r: (r["date"], r["incident_id"]))

    def write(path, rs):
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=COLS)
            w.writeheader()
            w.writerows(rs)

    write(os.path.join(a.out, "all_incidents.csv"), rows)
    eth = [r for r in rows if r["chain"] == "ethereum"]
    write(os.path.join(a.out, "ethereum_incidents.csv"), eth)

    # Orphan PoCs (exploit files no README entry points at)
    all_pocs = set()
    for root, _, files in os.walk(os.path.join(dhl, "src", "test")):
        for f in files:
            if f.endswith("_exp.sol") or re.search(r"_exp\.\w+\.\d+\.sol$", f):
                all_pocs.add(os.path.relpath(os.path.join(root, f), dhl))
    orphans = sorted(all_pocs - referenced)

    # Summary
    years = sorted({r["year"] for r in rows})
    by_year_all = Counter(r["year"] for r in rows)
    by_year_eth = Counter(r["year"] for r in eth)
    by_year_eth_fb = Counter(r["year"] for r in eth if r["chain_source"] != "fork")
    unres_fork_all = sum(r["fork_chain"] == "unresolved" for r in rows)
    unres_final = sum(r["chain"] == "unresolved" for r in rows)
    chain_counts = Counter(r["chain"] for r in rows)
    fork_src = Counter(r["fork_source"] for r in rows if r["fork_chain"] == "unresolved")

    L = []
    L.append("# DeFiHackLabs catalog summary (generated, do not edit)\n")
    L.append(f"- DeFiHackLabs commit: `{git_head(dhl)}`")
    L.append(f"- README entries parsed (all chains): **{len(rows)}**")
    L.append(f"- Entries whose README PoC link is missing on disk: {missing_poc}")
    L.append(f"- `*_exp.sol` PoC files not referenced by any README entry: {len(orphans)}")
    L.append(f"- Ethereum mainnet incidents: **{len(eth)}** "
             f"({sum(r['chain_source']=='fork' for r in eth)} from the fork call, "
             f"{sum(r['chain_source']!='fork' for r in eth)} from the header-explorer fallback)")
    L.append(f"- Fork chain `unresolved` (first createSelectFork not statically readable), all chains: "
             f"**{unres_fork_all}**; still unresolved after header fallback: **{unres_final}**")
    L.append("")
    L.append("## Per-year counts\n")
    L.append("| Year | All chains | Ethereum | of which Ethereum via header fallback |")
    L.append("|---|---:|---:|---:|")
    for y in years:
        L.append(f"| {y} | {by_year_all[y]} | {by_year_eth[y]} | {by_year_eth_fb[y]} |")
    L.append(f"| **Total** | **{len(rows)}** | **{len(eth)}** | **{sum(by_year_eth_fb.values())}** |")
    L.append("")
    L.append("## Chain mix (final `chain` column, all entries)\n")
    L.append("| Chain | Count |")
    L.append("|---|---:|")
    for c, n in chain_counts.most_common():
        L.append(f"| {c} | {n} |")
    L.append("")
    L.append("## Why the fork chain was unresolved\n")
    L.append("| fork_source | Count |")
    L.append("|---|---:|")
    for c, n in fork_src.most_common():
        L.append(f"| {c} | {n} |")
    L.append("")
    if orphans:
        L.append("## Unreferenced PoC files\n")
        for o in orphans:
            L.append(f"- `{o}`")
        L.append("")
    with open(os.path.join(a.out, "summary.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    print("\n".join(L[:12]))


if __name__ == "__main__":
    sys.exit(main())
