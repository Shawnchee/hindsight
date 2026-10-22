"""Stage 2 of the M0 funnel: look up each victim candidate on Sourcify (chain 1).

Endpoint (Sourcify APIv2, no key): GET https://sourcify.dev/server/v2/contract/1/<address>?fields=...
  match = exact_match -> full_match, match -> partial_match, HTTP 404 -> not_found.
Responses are cached under <cache_dir>/<address>.json (404s cached as {"_status": 404}).

Usage:
  python3 -I fetch_sourcify.py <incidents_json> <cache_dir> [--max-candidates 4] [--delay 1.5]
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = "https://sourcify.dev/server/v2/contract/1/"
FIELDS = "sources,compilation,proxyResolution,deployment"
UA = "hindsight-m0-funnel/0.1 (research; contact via github)"


def fetch(addr, cache_dir, delay):
    path = os.path.join(cache_dir, addr + ".json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f), False
    url = f"{BASE}{addr}?fields={FIELDS}"
    for attempt in range(6):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.load(r)
                data["_status"] = r.status
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                data = {"_status": 404}
                break
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(delay * (2 ** (attempt + 1)))
                continue
            data = {"_status": e.code, "_error": str(e)}
            break
        except Exception as e:  # network error
            time.sleep(delay * (2 ** (attempt + 1)))
            data = {"_status": None, "_error": repr(e)}
    data["_fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if data.get("_status") in (200, 404):
        with open(path, "w") as f:
            json.dump(data, f)
    time.sleep(delay)
    return data, True


def main():
    args = sys.argv[1:]
    inc_path, cache_dir = args[0], args[1]
    maxc = int(args[args.index("--max-candidates") + 1]) if "--max-candidates" in args else 4
    delay = float(args[args.index("--delay") + 1]) if "--delay" in args else 1.5
    os.makedirs(cache_dir, exist_ok=True)
    rows = json.load(open(inc_path))
    n = 0
    for r in rows:
        if not r["in_scope"]:
            continue
        for addr in r["victims"][:maxc]:
            d, net = fetch(addr, cache_dir, delay)
            n += net
            print(r["incident"], addr, d.get("_status"), d.get("match"), flush=True)
    print(f"done; {n} network requests")


if __name__ == "__main__":
    main()
