"""Fetch one explicitly selected public contract from a metadata-only snapshot.

Default is offline. Never builds or executes downloaded source, reads credentials,
or loops over the dataset. See the snapshot README for licensing/coverage limits.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import urllib.error
import urllib.request


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def local_unit(name):
    if not isinstance(name, str) or "\\" in name or "\x00" in name:
        raise ValueError("invalid compiler source unit")
    local = "_absolute_source_units/" + name[1:] if name.startswith("/") else name
    path = PurePosixPath(local)
    if path.is_absolute() or ".." in path.parts or not path.parts or path.as_posix() != local:
        raise ValueError("unsafe compiler source unit")
    return path


def verified_sources(contract, response):
    if response.get("runtimeMatch") != contract["runtime_match"]:
        raise ValueError("provider verification classification changed")
    code = response.get("runtimeBytecode", {}).get("onchainBytecode", "")
    if not re.fullmatch(r"0x(?:[0-9a-fA-F]{2})+", code):
        raise ValueError("missing deployed runtime")
    if digest(bytes.fromhex(code[2:])) != contract["runtime_sha256"]:
        raise ValueError("provider runtime differs from the snapshot")
    expected = {f["source_unit"]: f for f in contract["source_files"]}
    actual = response.get("sources", {})
    if set(actual) != set(expected):
        raise ValueError("provider source-unit set differs from the snapshot")
    output = {}
    for unit, f in expected.items():
        raw = actual[unit]["content"].encode("utf-8")
        if digest(raw) != f["sha256"] or len(raw) != f["bytes"]:
            raise ValueError("source bytes differ from the snapshot")
        path = local_unit(unit)
        if path in output:
            raise ValueError("compiler source units collide locally")
        output[path] = raw
    return output


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise ValueError("provider redirects are not followed")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--contracts", type=Path, default=Path(__file__).with_name("contracts.jsonl"))
    p.add_argument("--address", required=True)
    p.add_argument("--out", type=Path)
    p.add_argument("--execute", action="store_true")
    args = p.parse_args()
    try:
        address = args.address.lower()
        if not re.fullmatch(r"0x[0-9a-f]{40}", address):
            raise ValueError("invalid contract address")
        rows = [json.loads(l) for l in args.contracts.read_text().splitlines()]
        contracts = [c for c in rows if c["address"] == address and c["chain_id"] == 1]
        if len(contracts) != 1:
            raise ValueError("select exactly one contract present in this snapshot")
        contract = contracts[0]
        # Construct the fixed public endpoint; never trust a dataset-provided URL.
        url = "https://sourcify.dev/server/v2/contract/1/" + address + "?fields=sources,runtimeBytecode.onchainBytecode"
        if not args.execute:
            print(json.dumps({"address": address, "url": url, "source_files": len(contract["source_files"]),
                              "network_requested": False, "note": "Use --execute and a new --out directory to fetch one contract."}, indent=2))
            return
        if not args.out or args.out.exists() or args.out.is_symlink():
            raise ValueError("--out must be a new local directory")
        for parent in (args.out.absolute(), *args.out.absolute().parents):
            if parent.is_symlink():
                raise ValueError("symlink in output path")
        request = urllib.request.Request(url, headers={"Accept": "application/json",
            "User-Agent": "HindsightResearchSnapshot/0.1 (single-contract explicit reproduction)"})
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=40) as response:
            raw = response.read(4_000_001)
        if len(raw) > 4_000_000:
            raise ValueError("response exceeds four-megabyte bound")
        sources = verified_sources(contract, json.loads(raw))
        args.out.mkdir(parents=True, exist_ok=False)
        (args.out / "provider-response.json").write_bytes(raw)
        for unit, content in sources.items():
            target = args.out / "sources" / unit
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as f:
                f.write(content)
        print(f"Verified and saved {len(sources)} source files for {address}. No code executed.")
    except (OSError, ValueError, KeyError, TypeError) as error:
        p.exit(1, f"Source fetch stopped ({type(error).__name__}); no automatic retry. Check provider availability and snapshot compatibility.\n")


if __name__ == "__main__":
    main()
