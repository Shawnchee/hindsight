#!/usr/bin/env python3
"""Bounded, opt-in incident discovery. No inference, article storage or promotion.

Default invocation prints an offline plan and writes nothing. Executing requires
explicit source IDs. Only public metadata is persisted; response bodies and
search snippets are transient. A lead is a source document, never a verified incident.
"""
import argparse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/incidents/feeds.json"
SERPER_SOURCES = {
    "serper-news": {"kind": "serper_news", "endpoint": "https://google.serper.dev/news", "query": "(Ethereum OR Solidity) (hack OR exploit OR drained)"},
    "serper-x-links": {"kind": "serper_search", "endpoint": "https://google.serper.dev/search", "query": "(site:x.com OR site:twitter.com) (Ethereum OR Solidity) (hack OR exploit OR drained)"},
}
SERPAPI_SOURCES = {
    "serpapi-news": {"kind": "serpapi_news", "endpoint": "https://serpapi.com/search.json", "engine": "google_news", "query": "(Ethereum OR Solidity) (hack OR exploit OR drained)"},
    "serpapi-x-links": {"kind": "serpapi_search", "endpoint": "https://serpapi.com/search.json", "engine": "google", "query": "(site:x.com OR site:twitter.com) (Ethereum OR Solidity) (hack OR exploit OR drained)"},
}
SEARCH_SOURCES = {**SERPER_SOURCES, **SERPAPI_SOURCES}
FEED_ENDPOINTS = {
    "google-news-ethereum": ("news.google.com", "/rss/search"),
    "openzeppelin": ("www.openzeppelin.com", "/news/rss.xml"),
}
UTC = timezone.utc
TX = re.compile(r"(?<![a-zA-Z0-9])0x[a-fA-F0-9]{64}(?![a-zA-Z0-9])")
SCOPE = re.compile(r"\b(?:ethereum|solidity)\b|(?:www\.)?etherscan\.io", re.I)
SIGNAL = re.compile(r"\b(?:hack(?:ed|s|ing)?|exploit(?:ed|s|ation)?|drain(?:ed|s)?|post.?mortem)\b", re.I)
TRACKING = {"fbclid", "gclid", "mc_cid", "mc_eid"}
SUMMARY = "Ethereum-related security incident discovery signal; verify mainnet, Solidity, incident identity and source claims before intake."
CACHE_MAX_BYTES = 16 * 1024 * 1024
CACHE_MAX_ROWS = 10000
CACHE_MAX_ROW_BYTES = 256 * 1024
MAX_PROVENANCE = 128
LEAD_FIELDS = {"id", "canonical_url", "published_at", "observed_at", "first_seen_at", "summary", "status", "adjudication", "scope_status", "target_scope", "eligible_for_training", "eligible_for_evaluation", "transaction_hash_candidates", "provenance", "related_lead_ids"}
PROVENANCE_FIELDS = {"source_id", "source_url", "published_at", "observed_at", "response_sha256"}
SECRET_KEY = re.compile(r"(?:access|api|client|private|secret|refresh|session|security)?(?:key|token|secret)|auth(?:orization)?|bearer|password|passwd|credential|signature|sig|jwt|(?:xamz|xgoog)(?:signature|credential|securitytoken)", re.I)
PROVIDER_DOMAINS = {"alchemy.com", "alchemyapi.io", "infura.io", "quicknode.pro", "quiknode.pro", "chainstack.com", "ankr.com", "blastapi.io", "tenderly.co", "drpc.org"}


class CollectionError(Exception):
    """A fixed public error code, without response text or credentials."""


def stamp(value):
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_date(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        result = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        try:
            result = parsedate_to_datetime(value)
        except (ValueError, TypeError, OverflowError):
            return None
    if result.tzinfo is None:
        return None  # Never invent a timezone for source publication dates.
    return result.astimezone(UTC)


def canonical_url(value):
    """Normalize document identities, preserving meaningful query parameters."""
    if not isinstance(value, str) or not 1 <= len(value) <= 4096 or any(ord(c) < 33 for c in value) or "\\" in value:
        raise ValueError("invalid_public_url")
    p = urllib.parse.urlsplit(value.strip())
    if p.scheme.lower() not in {"http", "https"} or not p.hostname or p.username or p.password:
        raise ValueError("invalid_public_url")
    host = p.hostname.lower()
    port = p.port
    # Offline checks deliberately avoid DNS. Public evidence must use a normal
    # domain, never numeric addresses, local namespaces or RPC-provider URLs.
    labels = host.split(".")
    if (len(labels) < 2 or len(host) > 253 or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels)
            or re.fullmatch(r"(?:0x[a-f0-9]+|[0-9]+)(?:\.(?:0x[a-f0-9]+|[0-9]+))*", host)
            or labels[-1] in {"local", "localhost", "localdomain", "internal", "lan", "home", "corp", "private", "test", "invalid", "example", "onion"}
            or host == "home.arpa" or host.endswith(".home.arpa")
            or any(host == domain or host.endswith("." + domain) for domain in PROVIDER_DOMAINS)
            or any(label == "rpc" or label.startswith("rpc-") or label.endswith("-rpc") for label in labels)
            or port not in {None, 80, 443}):
        raise ValueError("invalid_public_url")
    decoded = value
    for _ in range(3):
        decoded = urllib.parse.unquote(decoded)
    if any(ord(c) < 32 for c in decoded):
        raise ValueError("invalid_public_url")
    # Inspect before normalizing or dropping X/tracking parameters. Nested
    # redirect URLs and encoded credential keys must not become public metadata.
    for match in re.finditer(r"[?&#]([^?&#=]+)=", decoded):
        key = re.sub(r"[^a-zA-Z]", "", match[1])
        if (SECRET_KEY.fullmatch(key)
                or key.lower().endswith(("token", "apikey", "secret", "password", "credential", "signature", "accesskeyid"))):
            raise ValueError("credential_url_refused")
    if re.search(r"(?:Bearer\s|\beyJ[A-Za-z0-9_-]{12,}\.|\bsk-[A-Za-z0-9_-]{16,}|\bxox[baprs]-)", decoded, re.I):
        raise ValueError("credential_url_refused")
    if host in {"twitter.com", "www.twitter.com", "www.x.com"}:
        host = "x.com"
    status = re.fullmatch(r"/(?:[^/]+/status|i/web/status|i/status)/(\d+)/?", p.path)
    if host == "x.com" and status:
        return "https://x.com/i/status/" + status[1]
    scheme = p.scheme.lower()
    netloc = host if port is None or (scheme, port) in {("https", 443), ("http", 80)} else f"{host}:{port}"
    query = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in TRACKING]
    return urllib.parse.urlunsplit((scheme, netloc, p.path or "/", urllib.parse.urlencode(sorted(query)), ""))


def source_url(source, days, now, max_items):
    if source["id"] in SEARCH_SOURCES:
        return SEARCH_SOURCES[source["id"]]["endpoint"]
    value = source["url"]
    p = urllib.parse.urlsplit(value)
    if source["id"] == "google-news-ethereum":
        params = dict(urllib.parse.parse_qsl(p.query))
        params["q"] = f"Ethereum hack exploit when:{days}d"
        value = urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, urllib.parse.urlencode(params), ""))
    return value


def source_payload(source, days, now, max_items):
    specification = SEARCH_SOURCES[source["id"]]
    start = (now - timedelta(days=days)).date().isoformat()
    end = (now + timedelta(days=1)).date().isoformat()
    return {"q": f"{specification['query']} after:{start} before:{end}", "num": max_items}


def load_config(path):
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("invalid_source_config")
    sources = config.get("sources", [])
    if config.get("version") != 1 or not isinstance(sources, list) or not 1 <= len(sources) <= 10:
        raise ValueError("invalid_source_config")
    seen = set()
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("invalid_source_config")
        sid, kind = source.get("id"), source.get("kind")
        if sid in seen:
            raise ValueError("duplicate_source_id")
        seen.add(sid)
        if sid in SERPER_SOURCES and kind == SERPER_SOURCES[sid]["kind"]:
            if source.get("url") != SERPER_SOURCES[sid]["endpoint"] or source.get("query") != SERPER_SOURCES[sid]["query"]:
                raise ValueError("serper_contract_is_fixed")
            continue
        if sid in SERPAPI_SOURCES and kind == SERPAPI_SOURCES[sid]["kind"]:
            if source.get("url") != SERPAPI_SOURCES[sid]["endpoint"] or source.get("query") != SERPAPI_SOURCES[sid]["query"]:
                raise ValueError("serpapi_contract_is_fixed")
            continue
        if kind != "rss" or sid not in FEED_ENDPOINTS:
            raise ValueError("source_not_allowlisted")
        p = urllib.parse.urlsplit(source.get("url", ""))
        if (p.scheme != "https" or p.username or p.password or p.port is not None
                or p.fragment or (p.hostname, p.path) != FEED_ENDPOINTS[sid]):
            raise ValueError("feed_endpoint_not_allowlisted")
    if any(sid not in seen for sid in config.get("default_sources", [])):
        raise ValueError("unknown_default_source")
    return config


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CollectionError("redirect_refused")


def fetch(url, *, api_key=None, payload=None, timeout=15, max_bytes=1048576):
    serpapi = url == "https://serpapi.com/search.json" and api_key is not None
    if api_key is not None or payload is not None:
        if not api_key or not isinstance(payload, dict) or url not in {value["endpoint"] for value in SEARCH_SOURCES.values()}:
            raise CollectionError("credential_endpoint_refused")
        candidates = SERPAPI_SOURCES if serpapi else SERPER_SOURCES
        sid = next((sid for sid, spec in candidates.items() if spec["endpoint"] == url
                    and isinstance(payload.get("q"), str) and payload["q"].startswith(spec["query"] + " after:")), None)
        try:
            validate_serper_request(sid, payload)
        except ValueError:
            raise CollectionError("serper_request_refused") from None
    else:
        p = urllib.parse.urlsplit(url)
        if p.scheme != "https" or p.username or p.password or p.port is not None or p.fragment or (p.hostname, p.path) not in FEED_ENDPOINTS.values():
            raise CollectionError("network_endpoint_refused")
    headers = {"User-Agent": "Hindsight-Discovery/1.0", "Accept": "application/json" if api_key else "application/rss+xml, application/atom+xml, application/xml"}
    if api_key and not serpapi:
        headers["X-API-KEY"] = api_key
        headers["Content-Type"] = "application/json"
    # No ambient proxy can receive the credential; no redirect may forward it.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    data = json.dumps(payload, sort_keys=True).encode("utf-8") if payload is not None and not serpapi else None
    if serpapi:
        params = {"engine": SERPAPI_SOURCES[sid]["engine"], "q": payload["q"], "hl": "en", "gl": "us", "api_key": api_key}
        if params["engine"] == "google":
            params["num"] = payload["num"]
        # SerpAPI requires the key in its query. This URL is never persisted or
        # printed; metadata retains only the credential-free endpoint/payload.
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, data=data, headers=headers, method="POST" if api_key and not serpapi else "GET")
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200:
                raise CollectionError("unexpected_http_status")
            if response.headers.get("Content-Encoding", "identity") not in {"", "identity"}:
                raise CollectionError("compressed_response_refused")
            body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise CollectionError("response_too_large")
        return body
    except urllib.error.HTTPError as error:
        raise CollectionError(f"http_{error.code}") from None
    except (urllib.error.URLError, OSError, ValueError):
        raise CollectionError("network_error") from None


def local_name(tag):
    return tag.rsplit("}", 1)[-1]


def feed_items(body):
    """Extract transient candidates from RSS or Atom without storing copied text."""
    try:
        text = body.decode("utf-8-sig")
        if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise CollectionError("xml_entities_refused")
        root = ET.fromstring(text)
    except (UnicodeError, ET.ParseError):
        raise CollectionError("invalid_feed") from None
    if local_name(root.tag) not in {"rss", "feed", "RDF"}:
        raise CollectionError("invalid_feed")
    items = []
    for node in root.iter():
        if local_name(node.tag) not in {"item", "entry"}:
            continue
        fields = {}
        links = []
        for child in node:
            name = local_name(child.tag)
            fields.setdefault(name, "".join(child.itertext()))
            if name == "link" and child.get("rel", "alternate") == "alternate":
                links.append(child.get("href") or (child.text or "").strip())
        items.append({"url": links[0] if links else "",
                      "published_at": fields.get("pubDate") or fields.get("published") or fields.get("date") or fields.get("updated"),
                      "signal": " ".join(fields.get(k, "") for k in ("title", "description", "summary", "content", "encoded"))})
        if len(items) >= 1000:
            break
    return items, {"scan_capped": len(items) >= 1000}


def serper_items(body, source):
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict) or payload.get("error") or payload.get("errors") or payload.get("statusCode", 200) != 200:
            raise CollectionError("serper_api_errors")
        field = "news" if source["kind"] == "serper_news" else "organic"
        results = payload.get(field)
        if not isinstance(results, list):
            raise CollectionError("invalid_serper_response")
        items = []
        for result in results[:100]:
            if not isinstance(result, dict) or not isinstance(result.get("link"), str):
                raise CollectionError("invalid_serper_response")
            url = result["link"]
            if source["id"] == "serper-x-links" and urllib.parse.urlsplit(url).hostname not in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}:
                continue
            # Relative dates and date-only strings do not establish a precise
            # publication timestamp. Preserve unknown rather than guessing.
            items.append({"url": url, "published_at": result.get("date"),
                          "signal": str(result.get("title", "")) + " " + str(result.get("snippet", ""))})
        return items, {"scan_capped": len(results) > 100, "single_page": True,
                       "date_window_is_search_filter_only": True}
    except (ValueError, TypeError, AttributeError, KeyError):
        raise CollectionError("invalid_serper_response") from None


def serpapi_items(body, source):
    """Flatten bounded news groups; never retain titles/snippets or API URLs."""
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict) or payload.get("search_metadata", {}).get("status") != "Success":
            raise CollectionError("serpapi_api_errors")
        if payload.get("error") and not str(payload["error"]).startswith("Google hasn't returned any results"):
            raise CollectionError("serpapi_api_errors")
        results = payload.get("news_results" if source["kind"] == "serpapi_news" else "organic_results", [])
        if not isinstance(results, list):
            raise CollectionError("invalid_serpapi_response")
        items, scanned = [], 0
        for group in results[:100]:
            if not isinstance(group, dict):
                raise CollectionError("invalid_serpapi_response")
            stories = group.get("stories", [group])
            if not isinstance(stories, list):
                raise CollectionError("invalid_serpapi_response")
            for result in stories[:100]:
                scanned += 1
                if scanned > 100:
                    break
                if not isinstance(result, dict) or not isinstance(result.get("link"), str):
                    raise CollectionError("invalid_serpapi_response")
                url = result["link"]
                if source["id"] == "serpapi-x-links" and urllib.parse.urlsplit(url).hostname not in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}:
                    continue
                items.append({"url": url, "published_at": result.get("date"),
                              "signal": str(result.get("title", "")) + " " + str(result.get("snippet", ""))})
            if scanned > 100:
                break
        return items, {"scan_capped": len(results) > 100 or scanned > 100, "single_page": True,
                       "date_window_is_search_filter_only": True}
    except (ValueError, TypeError, AttributeError, KeyError):
        raise CollectionError("invalid_serpapi_response") from None


def make_leads(items, source, url, body_hash, now, days, max_items, request_payload=None):
    leads = []
    counts = {"examined": len(items), "excluded": 0, "undated": 0, "capped": False}
    for item in items:
        published = parse_date(item["published_at"])
        if published is None:
            counts["undated"] += 1
            if source["id"] not in SEARCH_SOURCES:
                continue
        signal = item["signal"]
        if (published is not None and not now - timedelta(days=days) <= published <= now) or not SCOPE.search(signal) or not SIGNAL.search(signal):
            counts["excluded"] += 1
            continue
        try:
            canonical = canonical_url(item["url"])
        except ValueError:
            counts["excluded"] += 1
            continue
        if len(leads) == max_items:
            counts["capped"] = True
            break
        publication = stamp(published) if published is not None else None
        provenance = {"source_id": source["id"], "source_url": url,
                      "published_at": publication, "observed_at": stamp(now), "response_sha256": body_hash}
        if request_payload is not None:
            provenance["request"] = request_payload
        leads.append({
            "id": "lead_" + hashlib.sha256(canonical.encode()).hexdigest()[:24],
            "canonical_url": canonical,
            "published_at": publication, "observed_at": stamp(now), "first_seen_at": None,
            "summary": SUMMARY,
            "status": "proposed", "adjudication": "unresolved", "scope_status": "unresolved",
            "target_scope": {"chain_id": 1, "language": "Solidity"},
            "eligible_for_training": False, "eligible_for_evaluation": False,
            "transaction_hash_candidates": sorted({tx.lower() for tx in TX.findall(signal)})[:100],
            "provenance": [provenance],
        })
    return leads, counts


def cache_timestamp(value):
    if not isinstance(value, str) or len(value) != 20:
        raise ValueError("invalid_cached_timestamp")
    parsed = parse_date(value)
    if parsed is None or stamp(parsed) != value or parsed.year < 1970:
        raise ValueError("invalid_cached_timestamp")
    return parsed


def validate_serper_request(sid, request):
    if sid not in SEARCH_SOURCES or not isinstance(request, dict) or set(request) != {"q", "num"}:
        raise ValueError("invalid_serper_request")
    if type(request["num"]) is not int or not 1 <= request["num"] <= 100 or not isinstance(request["q"], str):
        raise ValueError("invalid_serper_request")
    pattern = re.escape(SEARCH_SOURCES[sid]["query"]) + r" after:(\d{4}-\d{2}-\d{2}) before:(\d{4}-\d{2}-\d{2})"
    match = re.fullmatch(pattern, request["q"])
    if not match:
        raise ValueError("invalid_serper_request")
    start = cache_timestamp(match[1] + "T00:00:00Z")
    end = cache_timestamp(match[2] + "T00:00:00Z")
    if not timedelta(days=2) <= end - start <= timedelta(days=91):
        raise ValueError("invalid_serper_request_window")


def validate_provenance(record):
    if not isinstance(record, dict):
        raise ValueError("invalid_cached_provenance_fields")
    is_serper = record.get("source_id") in SEARCH_SOURCES if isinstance(record.get("source_id"), str) else False
    if set(record) != (PROVENANCE_FIELDS | {"request"} if is_serper else PROVENANCE_FIELDS):
        raise ValueError("invalid_cached_provenance_fields")
    sid = record["source_id"]
    url = record["source_url"]
    if not isinstance(sid, str) or sid not in {*FEED_ENDPOINTS, *SEARCH_SOURCES}:
        raise ValueError("invalid_cached_source")
    canonical_url(url)  # Reject credentials and nonpublic links, even in provenance.
    p = urllib.parse.urlsplit(url)
    if p.scheme != "https" or p.port is not None or p.fragment:
        raise ValueError("invalid_cached_source_url")
    pairs = urllib.parse.parse_qsl(p.query, keep_blank_values=True, max_num_fields=12)
    params = dict(pairs)
    if len(pairs) != len(params):
        raise ValueError("invalid_cached_source_url")
    if sid == "google-news-ethereum":
        valid = ((p.hostname, p.path) == FEED_ENDPOINTS[sid]
                 and set(params) == {"q", "hl", "gl", "ceid"}
                 and params["hl"] == "en-US" and params["gl"] == "US" and params["ceid"] == "US:en"
                 and re.fullmatch(r"Ethereum hack exploit when:(?:[1-9]|[1-8][0-9]|90)d", params["q"]))
    elif sid == "openzeppelin":
        valid = (p.hostname, p.path) == FEED_ENDPOINTS[sid] and not params
    else:
        valid = url == SEARCH_SOURCES[sid]["endpoint"]
        validate_serper_request(sid, record["request"])
    if not valid:
        raise ValueError("invalid_cached_source_url")
    published = cache_timestamp(record["published_at"]) if record["published_at"] is not None else None
    observed = cache_timestamp(record["observed_at"])
    if is_serper:
        expected_end = (observed + timedelta(days=1)).date().isoformat()
        if not record["request"]["q"].endswith(" before:" + expected_end):
            raise ValueError("invalid_serper_request_observation_window")
    if (published is None and not is_serper) or (published is not None and published > observed):
        raise ValueError("invalid_cached_timestamp_order")
    if not isinstance(record["response_sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", record["response_sha256"]):
        raise ValueError("invalid_cached_response_hash")


def validate_lead(lead):
    if not isinstance(lead, dict) or not LEAD_FIELDS - {"related_lead_ids"} <= set(lead) or not set(lead) <= LEAD_FIELDS:
        raise ValueError("invalid_cached_lead_fields")
    if (lead["status"] != "proposed" or lead["adjudication"] != "unresolved"
            or lead["scope_status"] != "unresolved" or lead["first_seen_at"] is not None
            or lead["eligible_for_training"] is not False or lead["eligible_for_evaluation"] is not False
            or type(lead["target_scope"]) is not dict or set(lead["target_scope"]) != {"chain_id", "language"}
            or type(lead["target_scope"]["chain_id"]) is not int or lead["target_scope"] != {"chain_id": 1, "language": "Solidity"}):
        raise ValueError("cached_lead_is_not_discovery_only")
    if lead["summary"] != SUMMARY:
        raise ValueError("invalid_cached_summary")
    key = canonical_url(lead["canonical_url"])
    if key != lead["canonical_url"]:
        raise ValueError("cached_url_is_not_canonical")
    expected_id = "lead_" + hashlib.sha256(key.encode()).hexdigest()[:24]
    if lead["id"] != expected_id:
        raise ValueError("cached_lead_identity_mismatch")
    observed = cache_timestamp(lead["observed_at"])
    if lead["published_at"] is not None and cache_timestamp(lead["published_at"]) > observed:
        raise ValueError("invalid_cached_timestamp_order")
    for field, pattern, limit in (("transaction_hash_candidates", r"0x[a-f0-9]{64}", 100), ("related_lead_ids", r"lead_[a-f0-9]{24}", 1000)):
        values = lead.get(field, [])
        if (not isinstance(values, list) or len(values) > limit
                or any(not isinstance(value, str) or not re.fullmatch(pattern, value) for value in values)
                or values != sorted(set(values))):
            raise ValueError("invalid_cached_list")
    records = lead["provenance"]
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_PROVENANCE:
        raise ValueError("invalid_cached_provenance_count")
    for record in records:
        validate_provenance(record)
    known_publications = sorted(record["published_at"] for record in records if record["published_at"] is not None)
    if (lead["published_at"] != (known_publications[0] if known_publications else None)
            or lead["observed_at"] != min(record["observed_at"] for record in records)):
        raise ValueError("invalid_cached_provenance_dates")
    return key


def read_cache(path):
    """Validate untrusted JSONL before any request or mutation, with hard caps."""
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("unsafe_cache_path")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("unsafe_cache_path")
    if info.st_size > CACHE_MAX_BYTES:
        raise ValueError("cache_too_large")
    rows = []
    consumed = 0
    with path.open("rb") as stream:
        while True:
            raw = stream.readline(CACHE_MAX_ROW_BYTES + 1)
            if not raw:
                break
            consumed += len(raw)
            if len(raw) > CACHE_MAX_ROW_BYTES or consumed > CACHE_MAX_BYTES:
                raise ValueError("cache_too_large")
            if not raw.strip():
                raise ValueError("empty_cached_row")
            if len(rows) >= CACHE_MAX_ROWS:
                raise ValueError("too_many_cached_rows")
            rows.append(json.loads(raw.decode("utf-8"), object_pairs_hook=unique_json_fields))
    merged = merge_leads(rows, [])
    if len(merged) != len(rows):
        raise ValueError("duplicate_cached_lead")
    expected_related = {row["id"]: row["related_lead_ids"] for row in merged}
    if any(row.get("related_lead_ids", []) != expected_related[row["id"]] for row in rows):
        raise ValueError("invalid_cached_related_leads")
    return rows


def unique_json_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_cached_json_field")
        result[key] = value
    return result


def merge_leads(existing, incoming):
    """Only identical source URLs merge. Shared tx hashes create review links.

    A roundup can mention several incidents; shared addresses, titles or hashes
    alone must never establish incident identity or combine adjudications.
    """
    merged = {}
    for lead in existing + incoming:
        key = validate_lead(lead)
        if key not in merged:
            merged[key] = json.loads(json.dumps(lead))
            continue
        current = merged[key]
        current["observed_at"] = min(current["observed_at"], lead["observed_at"])
        publications = [value for value in (current["published_at"], lead["published_at"]) if value is not None]
        current["published_at"] = min(publications) if publications else None
        current["transaction_hash_candidates"] = sorted(set(current["transaction_hash_candidates"] + lead["transaction_hash_candidates"]))
        # One immutable provenance version per response/source/publication. A
        # repeat fetch of identical bytes never grows the cache indefinitely.
        versions = {}
        for record in current["provenance"] + lead["provenance"]:
            identity = (record["source_id"], record["source_url"], record["published_at"] or "", record["response_sha256"], json.dumps(record.get("request"), sort_keys=True))
            if identity not in versions or record["observed_at"] < versions[identity]["observed_at"]:
                versions[identity] = record
        current["provenance"] = [versions[k] for k in sorted(versions)]
    values = sorted(merged.values(), key=lambda row: row["id"])
    by_tx = {}
    for row in values:
        for tx in row["transaction_hash_candidates"]:
            by_tx.setdefault(tx, set()).add(row["id"])
    for row in values:
        row["related_lead_ids"] = sorted(set().union(*(by_tx[tx] for tx in row["transaction_hash_candidates"])) - {row["id"]}) if row["transaction_hash_candidates"] else []
        validate_lead(row)
    return values


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        try:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def collect(sources, args, now=None, fetcher=None):
    now, fetcher = now or datetime.now(UTC), fetcher or fetch
    if args.out.resolve() == args.status_out.resolve():
        raise ValueError("output_paths_must_differ")
    existing = []
    if args.out.exists():
        existing = read_cache(args.out)
    incoming, statuses = [], []
    for source in sources:
        state = {"source_id": source["id"], "observed_at": stamp(now), "status": "failed"}
        try:
            api_key, payload = None, None
            if source["id"] in SEARCH_SOURCES:
                provider = "serpapi" if source["id"] in SERPAPI_SOURCES else "serper"
                api_key = os.environ.get(provider.upper() + "_API_KEY")
                if not api_key:
                    raise CollectionError("missing_" + provider + "_api_key")
                if not 1 <= len(api_key) <= 512 or any(c.isspace() for c in api_key):
                    raise CollectionError("invalid_" + provider + "_api_key")
                payload = source_payload(source, args.days, now, args.max_items)
            url = source_url(source, args.days, now, args.max_items)
            body = fetcher(url, api_key=api_key, payload=payload, timeout=args.timeout, max_bytes=args.max_bytes)
            body_hash = hashlib.sha256(body).hexdigest()
            if source["id"] in SERPAPI_SOURCES:
                items, limits = serpapi_items(body, source)
            else:
                items, limits = serper_items(body, source) if source["id"] in SERPER_SOURCES else feed_items(body)
            leads, counts = make_leads(items, source, url, body_hash, now, args.days, args.max_items, payload)
            incoming.extend(leads)
            state.update(status="ok", request_url=url, response_sha256=body_hash, lead_count=len(leads), **counts, **limits)
            if payload is not None:
                state["request"] = payload
        except Exception as error:
            # Never stringify arbitrary exceptions: HTTP bodies, request headers
            # or environment values can contain credentials or copied post text.
            state["error"] = str(error) if isinstance(error, CollectionError) else "source_processing_error"
        statuses.append(state)
    merged = merge_leads(existing, incoming)
    status = {"version": 1, "observed_at": stamp(now), "coverage": "bounded discovery only; no guarantee of complete or current incident coverage", "sources": statuses,
              "lead_count": len(merged), "failed_sources": sum(s["status"] != "ok" for s in statuses)}
    output = "".join(json.dumps(row, sort_keys=True) + "\n" for row in merged)
    if (len(merged) > CACHE_MAX_ROWS or len(output.encode("utf-8")) > CACHE_MAX_BYTES
            or any(len(line.encode("utf-8")) + 1 > CACHE_MAX_ROW_BYTES for line in output.splitlines())):
        raise ValueError("merged_cache_limit_exceeded")
    atomic_write(args.out, output)
    atomic_write(args.status_out, json.dumps(status, indent=2, sort_keys=True) + "\n")
    return status


def bounded_int(low, high):
    def parse(value):
        number = int(value)
        if not low <= number <= high:
            raise argparse.ArgumentTypeError(f"must be between {low} and {high}")
        return number
    return parse


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--execute", action="store_true", help="Make bounded public network reads and merge metadata")
    parser.add_argument("--validate-cache", type=Path, metavar="JSONL", help="Validate a bounded discovery cache offline; never fetch or write")
    parser.add_argument("--source", action="append", default=[], help="Explicit source ID; repeat to select multiple")
    parser.add_argument("--out", type=Path, default=ROOT / "incidents/discovery/leads.jsonl")
    parser.add_argument("--status-out", type=Path, default=ROOT / "incidents/discovery/status.json")
    parser.add_argument("--max-items", type=bounded_int(1, 100), default=30, help="Maximum proposed leads per source, one request/page")
    parser.add_argument("--days", type=bounded_int(1, 90), default=14)
    parser.add_argument("--timeout", type=bounded_int(1, 60), default=15)
    parser.add_argument("--max-bytes", type=bounded_int(1024, 4194304), default=1048576)
    args = parser.parse_args(argv)
    try:
        if args.validate_cache is not None:
            if args.execute:
                parser.error("--validate-cache cannot be combined with --execute")
            rows = read_cache(args.validate_cache)
            print(json.dumps({"mode": "offline-cache-validation", "lead_count": len(rows), "network": False, "writes": False}, sort_keys=True))
            return 0
        config = load_config(args.config)
        by_id = {s["id"]: s for s in config["sources"]}
        selected = list(dict.fromkeys(args.source or config["default_sources"]))
        if any(sid not in by_id for sid in selected):
            parser.error("unknown source ID")
        if not args.execute:
            print(json.dumps({"mode": "offline-dry-run", "sources": selected, "max_items_per_source": args.max_items, "days": args.days, "max_requests_per_source": 1, "writes": False, "network": False, "search_requires_selected_source_and_environment_key": True}, sort_keys=True))
            return 0
        if not args.source:
            parser.error("--execute requires explicit --source IDs")
        status = collect([by_id[sid] for sid in selected], args)
        print(json.dumps({"lead_count": status["lead_count"], "failed_sources": status["failed_sources"]}, sort_keys=True))
        return 1 if status["failed_sources"] else 0
    except (ValueError, OSError, KeyError, TypeError, RecursionError):
        print("Collection failed: invalid configuration, cache or output path.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
