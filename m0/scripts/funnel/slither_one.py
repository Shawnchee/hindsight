"""Run Slither (all built-in detectors) on one solc standard-JSON input.

Usage (from the hindsight venv):
  .venv/bin/python -I slither_one.py <std_json_input> <solc_binary> <out_json> [<solc_working_dir>]
Writes {"success": bool, "error": str|None, "detectors": [...]} to out_json.
"""
import inspect
import json
import sys
import traceback


def main():
    src, solc, out = sys.argv[1:4]
    workdir = sys.argv[4] if len(sys.argv) > 4 else None
    res = {"success": False, "error": None, "detectors": []}
    try:
        from crytic_compile import CryticCompile
        from crytic_compile.platform.solc_standard_json import SolcStandardJson
        from slither import Slither
        from slither.detectors import all_detectors
        from slither.detectors.abstract_detector import AbstractDetector

        with open(src) as f:
            std = json.load(f)
        # let crytic-compile request the outputs it needs
        std.get("settings", {}).pop("outputSelection", None)
        cc = CryticCompile(SolcStandardJson(std), solc=solc, solc_working_dir=workdir)
        sl = Slither(cc)
        for _, obj in inspect.getmembers(all_detectors):
            if inspect.isclass(obj) and issubclass(obj, AbstractDetector) and obj is not AbstractDetector:
                sl.register_detector(obj)
        found = []
        for batch in sl.run_detectors():
            for r in batch:
                found.append({
                    "check": r.get("check"),
                    "impact": r.get("impact"),
                    "confidence": r.get("confidence"),
                    "first_markdown": (r.get("first_markdown_element") or "")[:300],
                    # used by the M0 review CLI to show and adjudicate findings
                    "description": (r.get("description") or "")[:800],
                    "functions": sorted({
                        e.get("name") if e.get("type") == "function"
                        else ((e.get("type_specific_fields") or {}).get("parent") or {}).get("name")
                        for e in r.get("elements") or []
                        if e.get("type") == "function"
                        or ((e.get("type_specific_fields") or {}).get("parent") or {}).get("type") == "function"
                    } - {None}),
                })
        res["detectors"] = found
        res["success"] = True
    except Exception as e:  # noqa: BLE001 - we record any failure class
        res["error"] = f"{type(e).__name__}: {e}"[:2000]
        res["traceback"] = traceback.format_exc()[-3000:]
    with open(out, "w") as f:
        json.dump(res, f, indent=1)


if __name__ == "__main__":
    main()
