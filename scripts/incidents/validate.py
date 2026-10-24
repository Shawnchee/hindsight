#!/usr/bin/env python3
"""Offline, standard-library validation of untrusted community incident metadata.

This never resolves/fetches URLs, imports submission code, or reads credentials.
Schema checks establish shape and conservative intake gates, not factual truth.
"""
import argparse
import csv
from datetime import date
import ipaddress
import json
from pathlib import Path
import re
import sys
from urllib.parse import parse_qsl, unquote, urlsplit, urlunsplit

REPO_ROOT = Path(__file__).resolve().parents[2]
MAX_FILE_BYTES = 32_768
MAX_FILES = 1_000
ID_RE = re.compile(r"community_[a-z0-9][a-z0-9_-]{2,63}\Z")
TX_RE = re.compile(r"0x[0-9a-fA-F]{64}\Z")
ADDRESS_RE = re.compile(r"0x[0-9a-fA-F]{40}\Z")
# Conservative rejection of obvious credentials and source/payload pastes. Prose
# ownership and factual accuracy still require a maintainer's review.
SECRET_RE = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|"
    r"(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,})|"
    r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b|"
    r"\b(?:api[_ -]?key|access[_ -]?token|auth[_ -]?token|private[_ -]?key|password|secret)\s*[=:]\s*\S+",
    re.IGNORECASE,
)
PAYLOAD_RE = re.compile(
    r"```|#!\s*/|\bpragma\s+solidity\b|\b(?:contract|library|interface)\s+\w+\s*(?:is\s+[^\n{]+)?\{|"
    r"\bfunction\s+\w+\s*\([^)]*\)\s*(?:external|public|internal|private)|"
    r"^\s*[\[{]|<\s*(?:[a-z][a-z0-9:-]*)(?:\s|>)|<\s*!doctype\b|\bimport\s+[\"']|\b(?:eval|exec)\s*\(",
    re.IGNORECASE,
)
SENSITIVE_QUERY_RE = re.compile(r"(?:^|[_-])(?:key|token|secret|password|credential|signature|auth)(?:$|[_-])|apikey|accesskey", re.I)
CONSTANTS = {
    "schema_version": "hindsight.community-incident.v1",
    "chain_id": 1,
    "language": "Solidity",
    "source_policy": "link_and_own_summary_only",
    "identifier_verification": "source_reported_unverified",
    "intake_status": "discovery_only",
    "first_seen_at": None,
    "family_id": None,
    "label_status": "proposed",
    "adjudication": "unresolved",
    "human_verified": False,
    "training_eligible": False,
    "evaluation_eligible": False,
    "benchmark_promoted": False,
    "split": "unassigned",
}
FIELDS = set(CONSTANTS) | {
    "candidate_id", "name", "incident_date", "discovered_at", "summary",
    "primary_sources", "tx_hashes", "victim_addresses", "coverage_gaps",
}


class InvalidRecord(ValueError):
    """Safe diagnostic: messages contain schema paths, never submitted values."""


def fail(field, explanation):
    raise InvalidRecord(f"{field}: {explanation}")


def text_value(value, field, maximum):
    if not isinstance(value, str) or not 1 <= len(value) <= maximum or not value.strip():
        fail(field, f"must be nonempty own prose of at most {maximum} characters")
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        fail(field, "must be a single line without control characters")
    if SECRET_RE.search(value):
        fail(field, "possible credential; remove it before submitting")
    if PAYLOAD_RE.search(value):
        fail(field, "code, source, markup, or document payload is not permitted; use an original prose summary")
    return value


def iso_date(value, field, nullable=False):
    if value is None and nullable:
        return
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        fail(field, "must be an ISO YYYY-MM-DD date" + (" or null" if nullable else ""))
    try:
        date.fromisoformat(value)
    except ValueError:
        fail(field, "must be a real calendar date")


def canonical_url(value, field="url"):
    """Return a comparison key without network or DNS access."""
    if not isinstance(value, str) or not 1 <= len(value) <= 2048:
        fail(field, "must be an HTTP(S) public evidence URL of at most 2048 characters")
    decoded = unquote(value)
    if any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in decoded) or "\\" in decoded:
        fail(field, "URL cannot contain whitespace, control characters, or backslashes")
    if SECRET_RE.search(value):
        fail(field, "possible credential in URL; use a public evidence link")
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").lower().rstrip(".")
        port = parts.port
    except ValueError:
        fail(field, "malformed URL authority or port")
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc or not host:
        fail(field, "must use http:// or https:// with a public host")
    if parts.username is not None or parts.password is not None:
        fail(field, "URL credentials are prohibited")
    if host in {"localtest.me", "lvh.me", "nip.io", "sslip.io"} or host.endswith((".localtest.me", ".lvh.me", ".nip.io", ".sslip.io")):
        fail(field, "local-address wildcard targets are prohibited")
    if port not in {None, 80, 443}:
        fail(field, "only standard public HTTP(S) ports are allowed")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        labels = host.split(".")
        if len(labels) < 2 or not re.fullmatch(r"(?:[a-z]{2,63}|xn--[a-z0-9-]{2,59})", labels[-1]):
            fail(field, "must use a public domain or globally routable IP literal")
        if any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels):
            fail(field, "malformed public domain")
        if labels[-1] in {"localhost", "local", "internal", "lan", "home", "test", "invalid", "example", "onion", "arpa"}:
            fail(field, "local, private, and reserved targets are prohibited")
        if host in {"metadata.google.internal", "metadata.google", "instance-data.ec2.internal"}:
            fail(field, "local metadata targets are prohibited")
    else:
        if not address.is_global or address.is_multicast or address.is_reserved:
            fail(field, "local, private, and reserved IP targets are prohibited")
    if any(SENSITIVE_QUERY_RE.search(key) for key, _ in parse_qsl(parts.query, keep_blank_values=True)):
        fail(field, "credential-like query parameters are prohibited")
    # Provider RPC URLs commonly carry secrets in their path. They are never
    # primary public incident evidence.
    if host in {"infura.io", "alchemy.com", "alchemyapi.io"} or host.endswith((".infura.io", ".alchemy.com", ".alchemyapi.io")):
        fail(field, "provider endpoints are prohibited; link public incident evidence")
    netloc = f"[{host}]" if ":" in host else host
    # Ignore fragments, scheme, www, trailing slash and tracking parameters for
    # duplicate checks; preserve substantive query parameters such as article IDs.
    netloc = netloc.removeprefix("www.")
    query = sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                   if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"})
    from urllib.parse import urlencode
    return urlunsplit(("https", netloc, unquote(parts.path).rstrip("/") or "/", urlencode(query), ""))


def exact_fields(record, expected, field):
    if not isinstance(record, dict):
        fail(field, "must be an object")
    if set(record) - expected:
        fail(field, "unknown fields are prohibited; see incidents/schema.json")
    if expected - set(record):
        # Expected names come from trusted schema, not submitted keys.
        fail(field, "missing required fields: " + ", ".join(sorted(expected - set(record))))


def list_value(value, field, maximum, minimum=0):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        fail(field, f"must be an array with {minimum}–{maximum} entries")


def validate_record(record):
    exact_fields(record, FIELDS, "record")
    for key, expected in CONSTANTS.items():
        if type(record[key]) is not type(expected) or record[key] != expected:
            fail(key, "must retain the template's unverified discovery value")
    if not isinstance(record["candidate_id"], str) or not ID_RE.fullmatch(record["candidate_id"]):
        fail("candidate_id", "must be community_ followed by 3–64 lowercase letters, digits, underscores or hyphens")
    if SECRET_RE.search(record["candidate_id"]):
        fail("candidate_id", "possible credential; choose a descriptive incident slug")
    text_value(record["name"], "name", 160)
    text_value(record["summary"], "summary", 2000)
    iso_date(record["incident_date"], "incident_date", nullable=True)
    iso_date(record["discovered_at"], "discovered_at")
    list_value(record["primary_sources"], "primary_sources", 10, 1)
    urls = set()
    for index, source in enumerate(record["primary_sources"]):
        field = f"primary_sources[{index}]"
        exact_fields(source, {"url", "published_date", "summary"}, field)
        url = canonical_url(source["url"], field + ".url")
        if url in urls:
            fail(field + ".url", "duplicate canonical evidence URL within record")
        urls.add(url)
        iso_date(source["published_date"], field + ".published_date", nullable=True)
        text_value(source["summary"], field + ".summary", 600)
    for key, regex, maximum in (("tx_hashes", TX_RE, 50), ("victim_addresses", ADDRESS_RE, 50)):
        list_value(record[key], key, maximum)
        seen = set()
        for index, value in enumerate(record[key]):
            if not isinstance(value, str) or not regex.fullmatch(value):
                fail(f"{key}[{index}]", "must be a full 0x-prefixed Ethereum " + ("transaction hash" if key == "tx_hashes" else "address"))
            if value.lower() in seen:
                fail(key, "duplicate identifier within record")
            seen.add(value.lower())
    list_value(record["coverage_gaps"], "coverage_gaps", 20, 1)
    for index, gap in enumerate(record["coverage_gaps"]):
        text_value(gap, f"coverage_gaps[{index}]", 600)
    return urls


def no_duplicate_json_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise InvalidRecord("JSON: duplicate object keys are prohibited")
        obj[key] = value
    return obj


def load_record(path):
    if path.is_symlink() or not path.is_file():
        raise InvalidRecord("file: symlinks and non-regular files are prohibited")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise InvalidRecord(f"file: exceeds {MAX_FILE_BYTES} bytes; submit metadata only")
    try:
        return json.loads(path.read_bytes().decode("utf-8"), object_pairs_hook=no_duplicate_json_keys,
                          parse_constant=lambda _: fail("JSON", "non-finite values are prohibited"))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise InvalidRecord("JSON: must be a valid UTF-8 JSON object") from None


def existing_identifiers(repo_root):
    """Read only committed metadata pointers; never source bodies or credentials."""
    ids, transactions, urls = {}, {}, {}
    paths = [
        "m0/discovery/incidents.proposed.jsonl",
        "m0/discovery/intake/incidents.proposed.jsonl",
        "m0/discovery/expansion/incidents.proposed.jsonl",
        "datasets/research/v0.1.0/incidents.jsonl",
        "datasets/research/v0.2.0/incidents.jsonl",
    ]
    for relative in paths:
        path = repo_root / relative
        if not path.exists():
            continue
        if path.is_symlink() or not path.is_file():
            raise InvalidRecord("existing corpus: expected regular metadata files")
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            for key in ("candidate_id", "incident_id"):
                if record.get(key):
                    ids[record[key]] = relative
            for tx in record.get("tx_hashes", []) + [item.get("hash", "") for item in record.get("transactions", [])]:
                if isinstance(tx, str) and TX_RE.fullmatch(tx):
                    transactions[tx.lower()] = relative
            for url in record.get("source_urls", []) + [item.get("url", "") for item in record.get("primary_sources", [])]:
                try:
                    urls[canonical_url(url)] = relative
                except InvalidRecord:
                    pass  # Existing historical metadata can contain local evidence pointers.
    path = repo_root / "m0/catalog/all_incidents.csv"
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise InvalidRecord("existing corpus: expected a regular catalog file")
        with path.open(encoding="utf-8", newline="") as stream:
            for record in csv.DictReader(stream):
                ids[record["incident_id"]] = "m0/catalog/all_incidents.csv"
                for tx in record.get("attack_tx_hashes", "").split(";"):
                    if TX_RE.fullmatch(tx):
                        transactions[tx.lower()] = "m0/catalog/all_incidents.csv"
    return ids, transactions, urls


def validate_directory(root, repo_root=REPO_ROOT):
    errors = []
    if root.is_symlink():
        return ["submissions: symlink directories are prohibited"], 0
    if not root.exists():
        return [], 0  # The initial empty corpus has no tracked directory.
    if not root.is_dir():
        return ["submissions: root must be a directory"], 0
    entries = sorted(root.iterdir())
    if len(entries) > MAX_FILES:
        return [f"submissions: exceeds {MAX_FILES} files"], 0
    try:
        ids, transactions, urls = existing_identifiers(repo_root)
    except (InvalidRecord, OSError, ValueError, KeyError, TypeError):
        return ["existing corpus: metadata could not be checked; restore the repository metadata files"], 0
    for number, path in enumerate(entries, 1):
        # A malicious filename must not inject control characters or secrets into
        # CI logs. Invalid filenames receive an index instead of being echoed.
        safe_name = bool(re.fullmatch(r"community_[a-z0-9][a-z0-9_-]{2,63}\.json", path.name))
        label = path.name if safe_name and not SECRET_RE.search(path.name) else f"submission #{number}"
        try:
            if not safe_name:
                fail("file", "use community_<slug>.json; only JSON metadata files belong in submissions")
            record = load_record(path)
            if isinstance(record, dict) and record.get("candidate_id") == "community_example":
                fail("candidate_id", "the synthetic template is excluded; replace it with a researched incident lead")
            record_urls = validate_record(record)
            if path.stem != record["candidate_id"]:
                fail("candidate_id", "must match the JSON filename without its extension")
            if record["candidate_id"] in ids:
                fail("candidate_id", "already exists; update the existing lead instead")
            if any(tx.lower() in transactions for tx in record["tx_hashes"]):
                fail("tx_hashes", "duplicate transaction in existing corpus or another submission; update that lead")
            if any(url in urls for url in record_urls):
                fail("primary_sources", "duplicate canonical evidence URL in existing corpus or another submission; update that lead")
            ids[record["candidate_id"]] = label
            for tx in record["tx_hashes"]:
                transactions[tx.lower()] = label
            for url in record_urls:
                urls[url] = label
        except (InvalidRecord, OSError) as exc:
            # OSError can contain arbitrary submitted path content; do not echo it.
            detail = str(exc) if isinstance(exc, InvalidRecord) else "file: could not read regular metadata file"
            errors.append(f"{label}: {detail}")
    return errors, len(entries)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT / "incidents/submissions",
                        help="community submissions directory (default: incidents/submissions)")
    args = parser.parse_args(argv)
    errors, count = validate_directory(args.root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"Community incident validation failed ({len(errors)} file errors).", file=sys.stderr)
        return 1
    print(f"Community incident metadata valid: {count} submissions; discovery only, no promotion.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
