"""Deterministic source preparation/report validation. No builds, network or models."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat

SCHEMA = "hindsight.triage.v1"
CATEGORIES = set("access_control price_oracle_trust rounding_precision arithmetic_overflow_or_cast input_validation reentrancy business_logic signature_validation uninitialized_or_unprotected_init storage_collision arbitrary_external_call governance_design weak_randomness denial_of_service other".split())
LEX = re.compile(r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|//[^\n]*|/\*[\s\S]*?\*/''')
TOKEN = re.compile(r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[A-Za-z_$][\w$]*|[^\s]''')
BLOCKED = {"test", "tests", "script", "scripts", ".git", ".aws", ".codex", ".agents"}


def no_comments(text):
    return LEX.sub(lambda m: re.sub(r"[^\n]", " ", m[0]) if m[0].startswith(("//", "/*")) else m[0], text)


def imports(text):
    # String contents and comments cannot introduce imports. Named multiline
    # imports have braces, so splitting Solidity at braces would lose dependencies.
    tokens = iter(TOKEN.findall(no_comments(text)))
    found = []
    for token in tokens:
        if token != "import":
            continue
        quoted = []
        for item in tokens:
            if item == ";":
                break
            if item.startswith(("'", '"')):
                quoted.append(item[1:-1])
        if len(quoted) == 1:
            found.append(quoted[0])
    return found


def safe_source(root, name):
    raw = Path(name)
    if raw.is_absolute() or "\\" in str(name):
        raise ValueError(f"source path must be relative: {name}")
    path = root / raw
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"source escapes project root: {name}")
    relative = resolved.relative_to(root)
    cursor = root
    for part in raw.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"source symlink rejected: {name}")
    if any(p.lower() in BLOCKED for p in relative.parts) or resolved.suffix != ".sol" or resolved.name.endswith((".t.sol", ".s.sol")):
        raise ValueError(f"not production Solidity source: {name}")
    return resolved


def resolve_import(root, importer, value, remappings):
    if value.startswith("."):
        names = [(Path(importer).parent / value).as_posix()]
    else:
        matches = [(prefix, dest) for prefix, dest in remappings if value.startswith(prefix)]
        if matches:
            longest = max(len(prefix) for prefix, _ in matches)
            names = [dest + value[len(prefix):] for prefix, dest in matches if len(prefix) == longest]
        else:
            names = [value, "node_modules/" + value, "lib/" + value]
    paths, rejected = set(), []
    for name in names:
        try:
            path = safe_source(root, name)
            if path.is_file():
                paths.add(path.relative_to(root).as_posix())
        except ValueError as e:
            rejected.append(str(e))
    if len(paths) == 1:
        return next(iter(paths)), None
    reason = "ambiguous: " + ", ".join(sorted(paths)) if paths else "unresolved"
    if rejected:
        reason += "; " + "; ".join(rejected)
    return None, reason


def read_slither(path):
    if path is None:
        return {"status": "not_supplied", "hints": []}
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("unsafe or oversized Slither JSON")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > 10_000_000:
        raise ValueError("unsafe or oversized Slither JSON")
    obj = json.loads(path.read_text())
    if not isinstance(obj, dict) or type(obj.get("success")) is not bool:
        raise ValueError("Slither JSON needs a boolean success field")
    if not obj["success"]:
        return {"status": "failed", "error": str(obj.get("error", "unknown")), "hints": []}
    results = obj.get("results") or {}
    if not isinstance(results, dict):
        raise ValueError("invalid Slither results object")
    detectors = obj.get("detectors", results.get("detectors", []))
    if not isinstance(detectors, list) or any(not isinstance(d, dict) for d in detectors):
        raise ValueError("invalid Slither detector list")
    return {"status": "supplied", "provenance": "user-supplied; execution not independently verified",
            "hints": [{k: d.get(k) for k in ("check", "impact", "confidence", "description", "elements", "functions")}
                      for d in detectors]}


def prepare(root, targets, remappings, slither=None, max_bytes=4_000_000):
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("root must be a directory")
    target_names = sorted({safe_source(root, t).relative_to(root).as_posix() for t in targets})
    files, gaps, pending, total = {}, [], list(reversed(target_names)), 0
    while pending:
        name = pending.pop()
        if name in files:
            continue
        path = safe_source(root, name)
        if not path.is_file():
            raise ValueError(f"not a regular source file: {name}")
        size = path.stat().st_size
        if size > max_bytes - total:
            raise ValueError(f"source byte limit exceeded at {name}; narrow targets or explicitly raise --max-bytes")
        raw = path.read_bytes()
        total += len(raw)
        if total > max_bytes:
            raise ValueError("source grew beyond byte limit")
        text = raw.decode("utf-8")
        files[name] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                       "line_count": len(text.splitlines()), "content": text}
        for value in imports(text):
            resolved, error = resolve_import(root, name, value, remappings)
            if resolved:
                pending.append(resolved)
            else:
                gaps.append(f"{name}: import {value!r}: {error}")
    return {"schema_version": "hindsight.bundle.v1", "targets": target_names,
            "files": dict(sorted(files.items())), "source_bytes": total,
            "coverage_gaps": sorted(set(gaps)), "slither": read_slither(slither)}


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate_bundle(bundle):
    """Authenticate the snapshot representation, not the truth of its contents."""
    if not isinstance(bundle, dict) or bundle.get("schema_version") != "hindsight.bundle.v1":
        raise ValueError("invalid source bundle")
    files = bundle.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("bundle needs source files")
    total = 0
    for name, source in files.items():
        if (not isinstance(name, str) or "\\" in name or Path(name).is_absolute()
                or any(p in {"..", "."} for p in name.split("/"))
                or Path(name).as_posix() != name or Path(name).suffix != ".sol"):
            raise ValueError("invalid bundle source path")
        if not isinstance(source, dict) or not isinstance(source.get("content"), str):
            raise ValueError("invalid source snapshot")
        raw = source["content"].encode("utf-8")
        if (source.get("sha256") != hashlib.sha256(raw).hexdigest()
                or type(source.get("bytes")) is not int or source["bytes"] != len(raw)
                or type(source.get("line_count")) is not int
                or source["line_count"] != len(source["content"].splitlines())):
            raise ValueError("source snapshot hash, bytes or line count mismatch")
        total += len(raw)
    targets = bundle.get("targets")
    if (not isinstance(targets, list) or not targets or any(not isinstance(t, str) or t not in files for t in targets)
            or len(set(targets)) != len(targets)):
        raise ValueError("invalid bundle targets")
    if type(bundle.get("source_bytes")) is not int or bundle["source_bytes"] != total:
        raise ValueError("bundle source byte count mismatch")
    if not isinstance(bundle.get("coverage_gaps"), list) or any(not nonempty(g) for g in bundle["coverage_gaps"]):
        raise ValueError("invalid bundle gaps")
    if not isinstance(bundle.get("slither"), dict) or bundle["slither"].get("status") not in {"supplied", "failed", "not_supplied"}:
        raise ValueError("invalid bundle analyzer status")


def validate_report(report, bundle):
    errors = []
    if not isinstance(report, dict) or not isinstance(bundle, dict):
        return ["report and bundle must be JSON objects"]
    try:
        validate_bundle(bundle)
    except (ValueError, TypeError, UnicodeError) as error:
        return [str(error)]
    if report.get("schema_version") != SCHEMA:
        errors.append("invalid report schema_version")
    for key in ("model", "summary"):
        if not nonempty(report.get(key)):
            errors.append(f"{key} must be nonempty text")
    supplied = bundle.get("slither", {}).get("status") == "supplied"
    mode = report.get("mode")
    if mode not in ("source-only", "source+slither") or (mode == "source+slither" and not supplied):
        errors.append("invalid mode or no successful Slither data")
    reviewed = report.get("reviewed_files")
    if not isinstance(reviewed, list) or not reviewed or not all(isinstance(f, str) for f in reviewed):
        return errors + ["reviewed_files must be a nonempty list of source paths"]
    if len(set(reviewed)) != len(reviewed) or set(reviewed) - bundle["files"].keys():
        errors.append("reviewed_files has duplicate or unknown files")
    gaps = report.get("coverage_gaps")
    if not isinstance(gaps, list) or any(not nonempty(g) for g in gaps):
        errors.append("coverage_gaps must be a list of nonempty strings")
        gaps = []
    for gap in bundle.get("coverage_gaps", []):
        if gap not in gaps:
            errors.append(f"missing bundle gap: {gap}")
    if mode == "source-only" and not any("slither" in g.lower() for g in gaps):
        errors.append("record that Slither was not used in coverage_gaps")
    for path in bundle["files"].keys() - set(reviewed):
        if not any(path in g for g in gaps):
            errors.append(f"unreviewed file needs a coverage gap: {path}")
    findings = report.get("findings")
    if not isinstance(findings, list):
        return errors + ["findings must be a list"]
    ids = set()
    for i, finding in enumerate(findings):
        tag = f"finding {i + 1}"
        if not isinstance(finding, dict):
            errors.append(f"{tag} must be an object")
            continue
        for key in ("id", "title", "location", "impact", "reasoning", "verification", "recommendation"):
            if not nonempty(finding.get(key)):
                errors.append(f"{tag}: missing {key}")
        ident = finding.get("id")
        if isinstance(ident, str):
            if ident in ids:
                errors.append(f"duplicate finding id: {ident}")
            ids.add(ident)
        for key, choices in (("status", {"confirmed_valid", "confirmed_invalid", "unresolved"}),
                             ("severity", {"critical", "high", "medium", "low", "informational"}),
                             ("confidence", {"high", "medium", "low"}), ("category", CATEGORIES)):
            if not isinstance(finding.get(key), str) or finding[key] not in choices:
                errors.append(f"{tag}: invalid {key}")
        conditions = finding.get("preconditions")
        if not isinstance(conditions, list) or not conditions or any(not nonempty(v) for v in conditions):
            errors.append(f"{tag}: preconditions need nonempty text entries")
        location = finding.get("location", "")
        if not isinstance(location, str) or not re.fullmatch(r"[^/:\\]+\.sol:[^\s:]+", location):
            errors.append(f"{tag}: location must be File.sol:function")
        evidence = finding.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{tag}: evidence is required")
            continue
        evidence_files = []
        for item in evidence:
            if not isinstance(item, dict) or not isinstance(item.get("file"), str) or item["file"] not in reviewed:
                errors.append(f"{tag}: evidence file was not reviewed")
                continue
            path = item["file"]
            evidence_files.append(Path(path).name)
            start, end = item.get("line_start"), item.get("line_end")
            if type(start) is not int or type(end) is not int or not 1 <= start <= end <= bundle["files"].get(path, {}).get("line_count", 0):
                errors.append(f"{tag}: invalid evidence line range")
        if isinstance(location, str) and location.partition(":")[0] not in evidence_files:
            errors.append(f"{tag}: location basename has no supporting evidence")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--root", type=Path, required=True)
    prep.add_argument("--target", action="append", required=True)
    prep.add_argument("--remapping", action="append", default=[])
    prep.add_argument("--slither", type=Path)
    prep.add_argument("--out", type=Path, required=True, help="new directory; never overwrites")
    prep.add_argument("--max-bytes", type=int, default=4_000_000)
    val = sub.add_parser("validate")
    val.add_argument("--bundle", type=Path, required=True)
    val.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            mappings = []
            for mapping in args.remapping:
                prefix, sep, dest = mapping.partition("=")
                if not sep or not prefix or not dest or Path(dest).is_absolute():
                    raise ValueError("remapping must be prefix=relative/path/")
                mappings.append((prefix, dest))
            if args.max_bytes < 1:
                raise ValueError("max-bytes must be positive")
            bundle = prepare(args.root, args.target, mappings, args.slither, args.max_bytes)
            args.out.mkdir(parents=True, exist_ok=False)
            path = args.out / "bundle.json"
            path.write_text(json.dumps(bundle, indent=2) + "\n")
            print(f"Prepared {len(bundle['files'])} files; {len(bundle['coverage_gaps'])} import gaps: {path}")
        else:
            errors = validate_report(json.loads(args.report.read_text()), json.loads(args.bundle.read_text()))
            if errors:
                raise ValueError("\n".join(errors))
            print("Report structure and source locations valid; security conclusions not verified.")
    except (ValueError, OSError) as e:
        parser.exit(1, str(e) + "\n")


if __name__ == "__main__":
    main()
