"""Shared helpers for the B2 benchmark: input scoping and location matching.

Scoping: Sourcify returns every file in the original compilation, which can include unrelated contracts.
For example, the UniswapV3Factory compilation has 390 files, among them a modified pool with missing owner
checks. A case may contain only the deployed target's import closure, and it names the target in TARGET.md.

Matching: a location is (file basename, function name), both lowercase. A finding in Wrong.sol:withdraw
doesn't match a label at Victim.sol:withdraw.
"""
import os
import posixpath
import re
import shutil

IMPORT_RE = re.compile(r"""^\s*import\s+(?:[^'";]*?\bfrom\s+)?["']([^"']+)["']""", re.M)


def _resolve(imp, importer, files):
    """Map an import string to a key in `files` (Sourcify source paths)."""
    if imp.startswith("."):
        cand = posixpath.normpath(posixpath.join(posixpath.dirname(importer), imp))
        if cand in files:
            return cand
    if imp in files:
        return imp
    # remapped or absolute imports: fall back to the unique longest suffix match
    hits = [f for f in files if f.endswith("/" + imp) or f.endswith(imp)]
    if not hits:
        base = posixpath.basename(imp)
        hits = [f for f in files if posixpath.basename(f) == base]
    return min(hits, key=len) if hits else None


def import_closure(sources, target):
    """sources: {path: content}. Returns the set of paths reachable from `target` through imports."""
    files = set(sources)
    if target not in files:
        return files  # can't scope; keep everything and let the caller flag it
    seen, stack = set(), [target]
    while stack:
        f = stack.pop()
        if f in seen:
            continue
        seen.add(f)
        for imp in IMPORT_RE.findall(sources[f] or ""):
            r = _resolve(imp, f, files)
            if r and r not in seen:
                stack.append(r)
    return seen


def read_tree(root):
    out = {}
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith(".sol"):
                p = os.path.join(dp, f)
                out[os.path.relpath(p, root).replace(os.sep, "/")] = open(p, errors="replace").read()
    return out


def write_scoped(sources, target, contract_name, dest):
    """Write only the import closure of `target` under dest, plus TARGET.md. Returns (kept paths, scoped ok)."""
    keep = import_closure(sources, target)
    for path in keep:
        p = os.path.join(dest, *[x for x in path.split("/") if x not in ("", ".", "..")])
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(sources[path] or "")
    with open(os.path.join(dest, "TARGET.md"), "w") as f:
        f.write(f"# Deployed target\n\n- File: `{target}`\n- Contract: `{contract_name or '?'}`\n\n"
                "The other files here are its imports.\n")
    return sorted(keep), target in sources


def copy_scoped_dir(src_dir, target, contract_name, dest):
    return write_scoped(read_tree(src_dir), target, contract_name, dest)


def loc_key(loc):
    """'path/File.sol:func(args)' -> ('file.sol', 'func'), or None if no function is given."""
    file_, _, rest = (loc or "").partition(":")
    name = rest.split("(")[0].strip().lower()
    if not name:
        return None
    return (posixpath.basename(file_.strip()).lower(), name)


def truth_keys(locations, roles):
    return {k for k in (loc_key(l["raw"]) for l in locations or [] if l.get("role", "defect") in roles) if k}


def hit(pred_keys, truth, k):
    return bool(truth) and any(p in truth for p in pred_keys[:k])
