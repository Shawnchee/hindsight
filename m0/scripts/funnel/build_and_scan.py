"""Stage 3 of the M0 funnel: for each in-scope incident with a Sourcify source,
write the sources to m0/data/funnel/src/<incident>/, compile with the exact solc
(standard JSON, Sourcify's compiler settings), then run Slither.

Only solc and Slither touch the downloaded sources. No build frameworks are run.

Usage (from repo root):
  VIRTUAL_ENV=$PWD/.venv .venv/bin/python -I m0/scripts/funnel/build_and_scan.py \
      m0/data/funnel/incidents.json m0/data/funnel/sourcify m0/data/funnel
"""
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
VENV = os.path.join(REPO, ".venv")
SOLC_SELECT = os.path.join(VENV, "bin", "solc-select")
PY = os.path.join(VENV, "bin", "python")
ARTIFACTS = os.path.join(VENV, ".solc-select", "artifacts")
EIP1967_IMPL_SLOT = "360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
EIP1967_LABEL = "eip1967.proxy.implementation"


def load(cache_dir, addr):
    p = os.path.join(cache_dir, addr + ".json")
    return json.load(open(p)) if os.path.exists(p) else None


def match_label(d):
    if d is None:
        return "not_fetched"
    if d.get("_status") == 404:
        return "not_found"
    if d.get("_status") != 200:
        return f"error_{d.get('_status')}"
    return {"exact_match": "full_match", "match": "partial_match"}.get(d.get("match"), "unknown")


def safe_rel(key):
    k = key.replace("\\", "/").lstrip("/")
    parts = [p for p in k.split("/") if p not in ("", ".", "..")]
    return os.path.join(*parts) if parts else "unnamed.sol"


def to_std_settings(cs):
    s = {k: v for k, v in cs.items() if k not in ("compilationTarget", "search_paths")}
    libs = s.get("libraries") or {}
    if libs and any(isinstance(v, str) for v in libs.values()):  # metadata format "file:Lib": addr
        nested = {}
        for k, v in libs.items():
            f, _, name = k.rpartition(":")
            nested.setdefault(f, {})[name] = v
        libs = nested
    s["libraries"] = libs
    s["outputSelection"] = {"*": {"*": ["abi", "evm.bytecode.object"], "": ["ast"]}}
    return s


def ensure_solc(version):
    path = os.path.join(ARTIFACTS, f"solc-{version}", f"solc-{version}")
    if os.path.exists(path):
        return path, None
    env = dict(os.environ, VIRTUAL_ENV=VENV)
    p = subprocess.run([SOLC_SELECT, "install", version], capture_output=True, text=True, env=env, timeout=600)
    if os.path.exists(path):
        return path, None
    return None, (p.stdout + p.stderr)[-500:]


def proxy_info(d):
    pr = d.get("proxyResolution") or {}
    ev = []
    if pr.get("isProxy"):
        ev.append(f"sourcify:{pr.get('proxyType')}")
    src = "\n".join((v or {}).get("content", "") for v in (d.get("sources") or {}).values()).lower()
    if EIP1967_IMPL_SLOT in src or EIP1967_LABEL in src:
        ev.append("source:eip1967_slot")
    name = (d.get("compilation") or {}).get("name") or ""
    if "proxy" in name.lower() and "delegatecall" in src:
        ev.append("source:proxy_name+delegatecall")
    impls = [i.get("address") for i in pr.get("implementations") or []]
    return bool(ev), ev, impls


def compile_solc(solc, std, workdir):
    t = time.time()
    p = subprocess.run([solc, "--standard-json"], input=json.dumps(std), capture_output=True, text=True,
                       cwd=workdir, timeout=900)
    dt = time.time() - t
    try:
        out = json.loads(p.stdout)
    except Exception:
        if "unrecognised option '--standard-json'" in (p.stderr + p.stdout):
            return False, "solc_no_standard_json(<0.4.11)", (p.stderr or p.stdout)[-500:], dt
        return False, "solc_crash", (p.stderr or p.stdout)[-500:], dt
    errs = [e for e in out.get("errors", []) if e.get("severity") == "error"]
    if errs:
        return False, errs[0].get("type", "Error"), errs[0].get("formattedMessage", errs[0].get("message", ""))[:800], dt
    return True, None, None, dt


def main():
    inc_path, cache_dir, data_root = (os.path.abspath(a) for a in sys.argv[1:4])
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    res_dir = os.path.join(data_root, "results")
    os.makedirs(res_dir, exist_ok=True)
    rows = json.load(open(inc_path))
    for r in rows:
        if not r["in_scope"] or (only and only not in r["incident"]):
            continue
        out = {"incident": r["incident"], "candidates": []}
        chosen = None
        for addr in r["victims"][:4]:
            d = load(cache_dir, addr)
            lab = match_label(d)
            out["candidates"].append({"address": addr, "sourcify": lab})
            if chosen is None and lab in ("full_match", "partial_match") and d.get("sources"):
                chosen = (addr, lab, d)
        if chosen:
            addr, lab, d = chosen
            comp = d.get("compilation") or {}
            ver = (comp.get("compilerVersion") or "").split("+")[0].lstrip("v")
            is_proxy, ev, impls = proxy_info(d)
            out.update({
                "address": addr, "sourcify": lab, "language": comp.get("language"),
                "compiler_version": comp.get("compilerVersion"), "contract_name": comp.get("name"),
                "target_file": (comp.get("fullyQualifiedName") or "").rpartition(":")[0],
                "n_source_files": len(d["sources"]), "is_proxy": is_proxy, "proxy_evidence": ev,
                "sourcify_current_impls": impls,
                "deployment_block": (d.get("deployment") or {}).get("blockNumber"),
            })
            folder = os.path.join(data_root, "src", r["incident"])
            sdir = os.path.join(folder, "sources")
            for k, v in d["sources"].items():
                p = os.path.join(sdir, safe_rel(k))
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w") as f:
                    f.write(v.get("content", ""))
            if comp.get("language") != "Solidity":
                out.update(compile_ok=False, compile_error_class=f"language_{comp.get('language')}")
            else:
                std = {"language": "Solidity",
                       "sources": {k: {"content": v.get("content", "")} for k, v in d["sources"].items()},
                       "settings": to_std_settings(comp.get("compilerSettings") or {})}
                std_path = os.path.join(folder, "std_input.json")
                with open(std_path, "w") as f:
                    json.dump(std, f)
                solc, err = ensure_solc(ver)
                if not solc:
                    out.update(compile_ok=False, compile_error_class="solc_install_failed", compile_error=err)
                else:
                    ok, cls, msg, dt = compile_solc(solc, std, folder)
                    out.update(compile_ok=ok, compile_error_class=cls, compile_error=msg, compile_seconds=round(dt, 1))
                    if ok:
                        sj = os.path.join(folder, "slither.json")
                        t = time.time()
                        try:
                            subprocess.run([PY, "-I", os.path.join(HERE, "slither_one.py"), std_path, solc, sj, sdir],
                                           cwd=sdir, capture_output=True, text=True, timeout=1800)
                            s = json.load(open(sj))
                        except subprocess.TimeoutExpired:
                            s = {"success": False, "error": "Timeout: >1800s", "detectors": []}
                        except Exception as e:  # noqa: BLE001
                            s = {"success": False, "error": f"runner: {e!r}", "detectors": []}
                        out.update(slither_ok=s["success"], slither_error=s.get("error"),
                                   slither_seconds=round(time.time() - t, 1), detectors=s["detectors"])
        with open(os.path.join(res_dir, r["incident"] + ".json"), "w") as f:
            json.dump(out, f, indent=1)
        print(r["incident"], out.get("sourcify", "-"), out.get("compile_ok"), out.get("compile_error_class"),
              out.get("slither_ok"), len(out.get("detectors", [])), flush=True)


if __name__ == "__main__":
    main()
