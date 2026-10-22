"""Stage 0-1 of the M0 funnel: pick Ethereum-mainnet DeFiHackLabs PoCs in a month
window and pull victim addresses from their header comments.

Reads the DeFiHackLabs clone as plain text only (never executes anything in it).

Usage:
  python3 -I select_incidents.py <dhl_root> <out_json> [--from 2024-11] [--to 2026-10]
"""
import json
import os
import re
import sys

ADDR_RE = re.compile(r"0x[0-9a-fA-F]{40}(?![0-9a-fA-F])")
FORK_RE = re.compile(r"createSelectFork\s*\(\s*([^,)]*)")
MAINNET_ALIASES = {"mainnet", "ethereum", "eth", "eth_mainnet", "ethereum_mainnet", "mainnet_archive"}
# hosts/paths that identify an Ethereum mainnet RPC URL
MAINNET_URL_HINTS = ("eth-mainnet", "eth.drpc", "ethereum-rpc", "ethereum.publicnode", "mainnet.infura",
                     "eth.llamarpc", "rpc.ankr.com/eth", "eth.merkle", "cloudflare-eth", "rpc.flashbots")
NON_MAINNET_URL_HINTS = ("sepolia", "goerli", "holesky", "arb", "optimism", "polygon", "bsc", "base",
                         "avax", "fantom", "linea", "blast", "mantle", "zksync", "sei", "hyperliquid")
EXPLORER_CHAIN = {
    "etherscan.io": "ethereum", "bscscan.com": "bsc", "basescan.org": "base", "arbiscan.io": "arbitrum",
    "polygonscan.com": "polygon", "optimistic.etherscan.io": "optimism", "ftmscan.com": "fantom",
    "snowtrace.io": "avalanche", "lineascan.build": "linea", "blastscan.io": "blast",
}


def classify_url(u):
    low = u.lower()
    if any(h in low for h in MAINNET_URL_HINTS):
        return "mainnet"
    for h in NON_MAINNET_URL_HINTS:
        if h in low:
            return "other:" + h
    return "unknown_url"


def resolve_fork(text):
    """Return (raw_first_arg, resolved_value, chain_class)."""
    m = FORK_RE.search(text)
    if not m:
        return None, None, "no_fork"
    raw = m.group(1).strip()
    val = raw
    if raw.startswith('"') or raw.startswith("'"):
        val = raw.strip("\"'")
    elif re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", raw):
        c = re.search(r"\b" + re.escape(raw) + r"\s*=\s*\"([^\"]*)\"", text)
        if c:
            val = c.group(1)
        else:
            return raw, None, "unresolved_identifier"
    elif raw.startswith("vm.env"):
        return raw, None, "env_var:" + raw
    else:
        return raw, None, "unresolved_expr"
    if val.lower() in MAINNET_ALIASES:
        return raw, val, "mainnet"
    if "://" in val:
        return raw, val, classify_url(val)
    return raw, val, "other:" + val


def header_victims(text):
    """Victim candidates from '// Vulnerable Contract ...' / '// Victim ...' comment lines.
    Order: 'Vulnerable Contract :' lines, then 'Victim' lines, then 'Vulnerable Contract Code' lines."""
    primary, victim, code = [], [], []
    explorer_chains = set()
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("//"):
            continue
        body = s.lstrip("/").strip()
        low = body.lower()
        if low.startswith("vulnerable contract code"):
            bucket = code
        elif low.startswith("vulnerable contract"):
            bucket = primary
        elif low.startswith("victim"):
            bucket = victim
        else:
            continue
        for host, chain in EXPLORER_CHAIN.items():
            if re.search(r"(?<![a-z.])" + re.escape(host), low):
                explorer_chains.add(chain)
        bucket.extend(a.lower() for a in ADDR_RE.findall(body))
    out = []
    for a in primary + victim + code:
        if a not in out:
            out.append(a)
    tier = "keyinfo" if out else None
    if not out:
        # Free-form headers (common from 2026): any header comment line that tags an
        # address as victim/vulnerable, e.g. "Avatar / treasury (victim) : 0x...".
        for line in text.splitlines():
            if re.match(r"\s*(abstract\s+)?(contract|interface|library)\s", line):
                break
            s = line.strip()
            if s.startswith("//") and re.search(r"victim|vulnerab", s, re.I):
                for a in ADDR_RE.findall(s):
                    if a.lower() not in out:
                        out.append(a.lower())
        tier = "freeform_tag" if out else None
    return out, sorted(explorer_chains), tier


def header_addresses(text):
    out = set()
    for line in text.splitlines():
        if re.match(r"\s*(abstract\s+)?(contract|interface|library)\s", line):
            break
        if line.strip().startswith("//"):
            out.update(a.lower() for a in ADDR_RE.findall(line))
    return out


def main():
    args = sys.argv[1:]
    root, out = args[0], args[1]
    lo = args[args.index("--from") + 1] if "--from" in args else "2024-11"
    hi = args[args.index("--to") + 1] if "--to" in args else "2026-10"
    test_dir = os.path.join(root, "src", "test")
    months = sorted(d for d in os.listdir(test_dir) if re.fullmatch(r"\d{4}-\d{2}", d) and lo <= d <= hi)
    rows = []
    for mon in months:
        for fn in sorted(os.listdir(os.path.join(test_dir, mon))):
            if not fn.endswith(".sol"):
                continue
            path = os.path.join(test_dir, mon, fn)
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
            raw, val, chain = resolve_fork(text)
            victims, ex_chains, tier = header_victims(text)
            n_hdr_addr = len(header_addresses(text))
            rows.append({
                "incident": f"{mon}_{fn[:-4]}",
                "month": mon,
                "poc_path": os.path.relpath(path, root),
                "fork_arg": raw,
                "fork_resolved": val,
                "fork_chain": chain,
                "in_scope": chain == "mainnet",
                "victims": victims,
                "victim_source": tier,
                "header_addresses_total": n_hdr_addr,
                "victim_explorer_chains": ex_chains,
            })
    with open(out, "w") as f:
        json.dump(rows, f, indent=1)
    n = sum(r["in_scope"] for r in rows)
    print(f"{len(rows)} PoCs in {lo}..{hi}; {n} mainnet; "
          f"{sum(1 for r in rows if r['in_scope'] and r['victims'])} with header victim address")


if __name__ == "__main__":
    main()
