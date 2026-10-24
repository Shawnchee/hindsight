"""Materialize previously fetched Sourcify data without network, builds or models.

Input is a directory of bounded HTTP response metadata (*.json) and body files.
Raw source is written only beneath a separate gitignored data directory. The
public inventory contains hashes/pointers, never source or article text.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_unit(name):
    if not isinstance(name, str) or "\\" in name or "\x00" in name:
        raise ValueError("invalid source-unit name")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts or name != path.as_posix():
        raise ValueError(f"unsafe source-unit name: {name!r}")
    return path


def immutable_write(path, raw):
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError("symlink in output path")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError(f"refusing to overwrite a different snapshot: {path}")
    else:
        with path.open("xb") as f:
            f.write(raw)


def materialize(cache, destination, repo):
    original_repo = repo.absolute()
    cache, destination, repo = cache.resolve(), destination.absolute(), repo.resolve()
    if not destination.resolve().is_relative_to(repo / "m0/data"):
        raise ValueError("raw source destination must be inside repository m0/data (gitignored)")
    for parent in (destination, *destination.parents):
        if parent in (original_repo, repo):
            break
        if parent.is_symlink():
            raise ValueError("symlink within output tree")
    destination = destination.resolve()
    records = []
    for path in sorted(cache.glob("*.json")):
        meta = json.loads(path.read_text())
        match = re.fullmatch(r"https://sourcify\.dev/server/v2/contract/1/(0x[0-9a-fA-F]{40})\?fields=[A-Za-z.,]+", meta.get("url", ""))
        if not match or meta.get("status") != 200:
            continue
        body_path = Path(meta["body_path"])
        if body_path.is_symlink() or not body_path.resolve().is_relative_to(cache):
            raise ValueError("response body escapes cache")
        body_path = body_path.resolve()
        raw = body_path.read_bytes()
        if digest(raw) != meta["sha256"] or len(raw) != meta["bytes"]:
            raise ValueError(f"response integrity mismatch: {path}")
        data = json.loads(raw)
        if data.get("runtimeMatch") not in ("match", "exact_match") or not data.get("sources"):
            raise ValueError("source response lacks a verified runtime match")
        comp = data.get("compilation") or {}
        if comp.get("language") != "Solidity":
            raise ValueError("non-Solidity source in intake")
        address = match[1].lower()
        folder = destination / address / meta["sha256"][:16]
        units = []
        local_units = set()
        for name, value in sorted(data["sources"].items()):
            # Compiler source-unit identifiers can legitimately be absolute
            # (e.g. /E/Defi/...); preserve that identifier in metadata while
            # mapping it into a bounded local namespace, never a host path.
            local_name = "_absolute_source_units/" + name[1:] if name.startswith("/") else name
            rel = safe_unit(local_name)
            if rel in local_units:
                raise ValueError("source-unit local path collision")
            local_units.add(rel)
            content = value.get("content")
            if not isinstance(content, str):
                raise ValueError("missing source content")
            source_raw = content.encode("utf-8")
            target = folder / "sources" / rel
            immutable_write(target, source_raw)
            spdx = sorted(set(re.findall(r"SPDX-License-Identifier:\s*([^\r\n]+)", content)))
            units.append({"source_unit": name, "local_path": target.relative_to(repo).as_posix(),
                          "sha256": digest(source_raw), "bytes": len(source_raw),
                          "line_count": len(content.splitlines()), "spdx_mentions": spdx})
        records.append({"chain_id": 1, "address": address, "contract_name": comp.get("name"),
                        "fully_qualified_name": comp.get("fullyQualifiedName"),
                        "compiler_version": comp.get("compilerVersion"),
                        "compiler_settings": comp.get("compilerSettings"),
                        "runtime_match": data["runtimeMatch"], "creation_match": data.get("creationMatch"),
                        "retrieved_at": meta["fetched_at"], "source_url": meta["url"],
                        "response_sha256": meta["sha256"],
                        "response_path": body_path.relative_to(repo).as_posix(),
                        "deployment": data.get("deployment"), "source_files": units,
                        "historical_runtime_compared": False,
                        "note": "Sourcify verification is for this retrieved deployment record; attack-time selection and runtime equality are separate checks. SPDX mentions may apply only to flattened components."})
    return {"schema_version": "hindsight.intake.sources.v1", "contracts": records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = materialize(args.cache, args.destination, args.repo)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n")
        print(f"Materialized {len(result['contracts'])} contract snapshots; source remains under m0/data.")
    except (ValueError, OSError, KeyError) as e:
        parser.exit(1, str(e) + "\n")


if __name__ == "__main__":
    main()
