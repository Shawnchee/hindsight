"""Read a bounded incident-state plan after the owner configures archive access.

Default is dry-run: no credentials read and no network. --execute is for an
owner-authorized data recovery pass. Credentials never enter saved metadata.
"""
import argparse
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request

ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")
WORD = re.compile(r"0x[0-9a-fA-F]+\Z")
TX = re.compile(r"0x[0-9a-fA-F]{64}\Z")
GETTERS = {"0x995363d3", "0x96c7871b", "0x4858064c", "0xf77c4791", "0x96b9cc0e"}
# isValid(address), infos(address), targets(bytes4), oracleAddresses(address).
ARGUMENT_GETTERS = {"0x8b1b925f", "0xc6ddb642", "0x16a6bff6", "0x71eb125e"}


def check_query(q):
    if not isinstance(q, dict) or not re.fullmatch(r"[a-z0-9-]+", str(q.get("id", ""))):
        raise ValueError("invalid query id")
    method, params = q.get("method"), q.get("params")
    if not isinstance(params, list):
        raise ValueError("params must be a list")
    valid = False
    if method == "eth_getCode" and len(params) == 2:
        valid = all(isinstance(x, str) for x in params) and bool(ADDRESS.fullmatch(params[0]) and WORD.fullmatch(params[1]))
    elif method == "eth_getStorageAt" and len(params) == 3:
        valid = all(isinstance(x, str) for x in params) and bool(ADDRESS.fullmatch(params[0]) and WORD.fullmatch(params[1]) and WORD.fullmatch(params[2]))
    elif method == "eth_call" and len(params) == 2 and isinstance(params[0], dict):
        call = params[0]
        data = call.get("data", "")
        selector = data[:10] if isinstance(data, str) else ""
        getter = (selector in GETTERS and len(data) == 10) or (selector in ARGUMENT_GETTERS and len(data) == 74 and WORD.fullmatch(data))
        valid = set(call) == {"to", "data"} and isinstance(call.get("to"), str) and bool(ADDRESS.fullmatch(call["to"])) and bool(getter) and isinstance(params[1], str) and bool(WORD.fullmatch(params[1]))
    elif method == "debug_traceTransaction" and len(params) == 2:
        valid = isinstance(params[0], str) and bool(TX.fullmatch(params[0])) and params[1] == {"tracer": "callTracer", "timeout": "15s"}
    if not valid:
        raise ValueError(f"unsupported read query: {q['id']}")


def load_url(env_file):
    value = os.environ.get("ETHEREUM_ARCHIVE_RPC_URL")
    if not value and env_file.exists():
        for line in env_file.read_text().splitlines():
            key, sep, raw = line.strip().removeprefix("export ").partition("=")
            if sep and key.strip() == "ETHEREUM_ARCHIVE_RPC_URL":
                value = raw.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
    if not value:
        raise ValueError("Owner must configure ETHEREUM_ARCHIVE_RPC_URL; do not paste credentials into chat.")
    parts = urllib.parse.urlsplit(value)
    if parts.fragment or not parts.hostname or (parts.scheme != "https" and not (parts.scheme == "http" and parts.hostname in {"localhost", "127.0.0.1", "::1"})):
        raise ValueError("Archive URL must use HTTPS or loopback HTTP.")
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Archive redirects are not followed.")


def rpc(url, method, params):
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=40) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError("Archive response exceeded two megabytes; narrow the request.")
    obj = json.loads(raw)
    if not isinstance(obj, dict) or obj.get("jsonrpc") != "2.0" or obj.get("id") != 1:
        raise ValueError("Invalid JSON-RPC response.")
    if obj.get("error"):
        # Provider error messages may echo tokens or URLs; persist only the code.
        return {"error_code": obj["error"].get("code"), "error": "Provider rejected the read; credentials and error text omitted."}
    result = obj.get("result")
    if result is None:
        return {"error": "No historical result returned."}
    if method in {"eth_call", "eth_getCode", "eth_getStorageAt", "eth_chainId"} and (not isinstance(result, str) or not re.fullmatch(r"0x[0-9a-fA-F]*", result)):
        raise ValueError("Invalid hexadecimal RPC result.")
    if method == "debug_traceTransaction" and not isinstance(result, dict):
        raise ValueError("Invalid call trace result.")
    return {"result": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        plan = json.loads(args.plan.read_text())
        queries = plan.get("queries")
        if not isinstance(queries, list) or not 1 <= len(queries) <= 50:
            raise ValueError("Plan must contain 1-50 bounded read queries.")
        ids = set()
        for q in queries:
            check_query(q)
            if q["id"] in ids:
                raise ValueError("Duplicate read query id.")
            ids.add(q["id"])
        if not args.execute:
            print(f"Plan valid: {len(queries)} read queries plus chain ID verification. No credentials read or network requests made.")
            return
        if not args.out:
            raise ValueError("--out is required for execution; choose a new gitignored data directory.")
        repo = Path(__file__).resolve().parents[3]
        if not args.out.resolve().is_relative_to(repo / "m0/data"):
            raise ValueError("Archive results must stay inside repository m0/data.")
        url = load_url(args.env_file)
        chain = rpc(url, "eth_chainId", [])
        if chain.get("result") != "0x1":
            raise ValueError("Archive endpoint did not confirm Ethereum mainnet chain ID 1.")
        args.out.mkdir(parents=True, exist_ok=False)
        failed = 0
        for q in queries:
            start = time.monotonic()
            try:
                response = rpc(url, q["method"], q["params"])
            except (OSError, ValueError) as e:
                response = {"error": f"Read failed ({type(e).__name__}); provider URL and error text omitted."}
            row = {"query": q, "provider": "owner_configured_archive_url_redacted", "chain_id": 1,
                   "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "seconds": time.monotonic() - start, **response}
            failed += "result" not in response
            with (args.out / (q["id"] + ".json")).open("x") as f:
                f.write(json.dumps(row, indent=2) + "\n")
            print(q["id"], "ok" if "result" in response else "unresolved", flush=True)
            time.sleep(0.2)
        if failed:
            parser.exit(1, f"{failed} historical reads unresolved; successful evidence preserved. No automatic retry.\n")
    except (OSError, ValueError, KeyError) as e:
        # Never print exceptions from network calls or URL parsing with secrets.
        parser.exit(1, f"Archive pass stopped ({type(e).__name__}); provider details omitted. Check configuration and saved evidence.\n")


if __name__ == "__main__":
    main()
