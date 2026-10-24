"""Synthetic discovery fixtures; never makes credential requests or runs PoCs."""
import contextlib
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.parse


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("incident_collect", ROOT / "scripts/incidents/collect.py")
collect = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collect)
NOW = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
TX = "0x" + "a" * 64
RSS = f'''<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Ethereum exploit report</title><link>https://example.org/report?utm_source=feed</link>
<pubDate>Fri, 23 Oct 2026 10:00:00 GMT</pubDate><description>Do not retain this article text. Tx {TX}</description></item>
<item><title>Solana hack</title><link>https://example.org/other-chain</link><pubDate>Fri, 23 Oct 2026 10:00:00 GMT</pubDate></item>
<item><title>Ethereum exploit without date</title><link>https://example.org/undated</link></item>
<item><title>Ethereum exploit old</title><link>https://example.org/old</link><pubDate>Wed, 01 Jan 2025 10:00:00 GMT</pubDate></item>
</channel></rss>'''.encode()
ATOM = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<title>Ethereum hacked</title><link rel="self" href="https://example.org/feed"/>
<link rel="alternate" href="https://example.org/atom"/>
<published>2026-10-23T10:00:00+08:00</published><summary>Never retain this post body.</summary>
</entry></feed>'''


class CollectionTests(unittest.TestCase):
    def test_cache_rejects_symlink_parent_and_fifo_before_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            real = root / 'real'
            real.mkdir()
            (real / 'leads.jsonl').write_text('')
            (root / 'alias').symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'unsafe_cache_path'):
                collect.read_cache(root / 'alias/leads.jsonl')
            if hasattr(os, 'mkfifo'):
                fifo = root / 'pipe'
                os.mkfifo(fifo)
                with self.assertRaisesRegex(ValueError, 'unsafe_cache_path'):
                    collect.read_cache(fifo)

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name).resolve()
        self.args = SimpleNamespace(out=self.path / "leads.jsonl", status_out=self.path / "status.json", days=14,
                                    max_items=30, timeout=15, max_bytes=1048576)
        self.sources = collect.load_config(collect.CONFIG)["sources"]

    def source(self, sid="google-news-ethereum"):
        return next(source for source in self.sources if source["id"] == sid)

    def leads(self, body=RSS, source=None):
        source = source or self.source()
        items, _ = collect.feed_items(body)
        return collect.make_leads(items, source, source["url"], "a" * 64, NOW, 14, 30)[0]

    def test_rss_filter_dates_and_discovery_only_fields(self):
        items, _ = collect.feed_items(RSS)
        leads, counts = collect.make_leads(items, self.source(), self.source()["url"], "a" * 64, NOW, 14, 30)
        self.assertEqual(len(leads), 1)
        self.assertEqual(counts["undated"], 1)
        self.assertEqual(counts["excluded"], 2)
        lead = leads[0]
        self.assertEqual(lead["canonical_url"], "https://example.org/report")
        self.assertIsNone(lead["first_seen_at"])
        self.assertEqual(lead["status"], "proposed")
        self.assertEqual(lead["adjudication"], "unresolved")
        self.assertFalse(lead["eligible_for_training"])
        self.assertFalse(lead["eligible_for_evaluation"])
        self.assertEqual(lead["transaction_hash_candidates"], [TX])
        self.assertNotIn("Do not retain", json.dumps(leads))
        self.assertNotIn("Ethereum exploit report", json.dumps(leads))

    def test_atom_alternate_link_and_timezone(self):
        lead = self.leads(ATOM)[0]
        self.assertEqual(lead["canonical_url"], "https://example.org/atom")
        self.assertEqual(lead["published_at"], "2026-10-23T02:00:00Z")
        self.assertNotIn("Never retain", json.dumps(lead))

    def test_invalid_feeds_and_xml_entities_rejected(self):
        for body in (b"not xml", b"<html/>", b'<!DOCTYPE rss [<!ENTITY x "secret">]><rss/>' , b"\xff"):
            with self.subTest(body=body), self.assertRaises(collect.CollectionError):
                collect.feed_items(body)

    def test_canonical_urls_keep_incident_parameters_and_x_identity(self):
        self.assertEqual(collect.canonical_url("https://EXAMPLE.org:443/report?id=2&utm_medium=rss#details"), "https://example.org/report?id=2")
        self.assertNotEqual(collect.canonical_url("https://example.org/report?id=1"), collect.canonical_url("https://example.org/report?id=2"))
        self.assertEqual(collect.canonical_url("https://twitter.com/account/status/123?utm_source=test"), "https://x.com/i/status/123")
        self.assertEqual(collect.canonical_url("https://x.com/i/web/status/123"), "https://x.com/i/status/123")
        for url in ("file:///etc/passwd", "https://u:secret@example.org", "https://127.0.0.1/", "https://localhost/", "https://[::1]/"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                collect.canonical_url(url)

    def test_idempotent_url_dedup_preserves_source_versions(self):
        original = self.leads()
        duplicate = self.leads(source=self.source("openzeppelin"))
        one = collect.merge_leads([], original)
        self.assertEqual(collect.merge_leads(one, original), one)
        two_sources = collect.merge_leads(one, duplicate)
        self.assertEqual(len(two_sources), 1)
        self.assertEqual(len(two_sources[0]["provenance"]), 2)
        self.assertEqual(two_sources[0]["id"], one[0]["id"])

    def test_same_txid_does_not_conflate_roundups_or_incidents(self):
        first = self.leads()
        second = self.leads(RSS.replace(b"/report?", b"/roundup?"))
        rows = collect.merge_leads(first, second)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["related_lead_ids"], [rows[1]["id"]])
        self.assertEqual(rows[1]["related_lead_ids"], [rows[0]["id"]])

    def test_date_and_item_bounds(self):
        items, _ = collect.feed_items(RSS)
        items += collect.feed_items(ATOM)[0]
        items.append(dict(items[0], published_at="2026-10-25T00:00:00Z"))
        leads, counts = collect.make_leads(items, self.source(), self.source()["url"], "a" * 64, NOW, 14, 1)
        self.assertEqual(len(leads), 1)
        self.assertTrue(counts["capped"])
        self.assertIsNone(collect.parse_date("2026-10-23T10:00:00"))

    def test_partial_failure_preserves_success_and_error_never_leaks_token(self):
        def fetcher(url, **kwargs):
            if "openzeppelin" in url:
                raise RuntimeError("sensitive-secret-token plus full copied response")
            return RSS
        status = collect.collect(self.sources[:2], self.args, NOW, fetcher)
        self.assertEqual(status["failed_sources"], 1)
        self.assertEqual(status["lead_count"], 1)
        self.assertEqual(status["sources"][1]["error"], "source_processing_error")
        before = self.args.out.read_bytes()
        collect.collect(self.sources[:2], self.args, NOW + timedelta(days=1), fetcher)
        self.assertEqual(before, self.args.out.read_bytes())
        self.assertNotIn("sensitive-secret", self.args.status_out.read_text())

    def test_corrupt_cache_rejected_before_any_request(self):
        self.args.out.write_text(json.dumps({"id": "wrong", "canonical_url": "https://example.org/"}))
        fetcher = Mock()
        with self.assertRaises(ValueError):
            collect.collect(self.sources[:1], self.args, NOW, fetcher)
        fetcher.assert_not_called()
        self.assertFalse(self.args.status_out.exists())

    def test_cache_cannot_silently_promote_discovery_or_assert_first_seen(self):
        for field, value in (("eligible_for_training", True), ("eligible_for_evaluation", True),
                             ("first_seen_at", "2026-10-23T10:00:00Z"), ("status", "confirmed")):
            rows = self.leads()
            rows[0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "discovery_only"):
                collect.merge_leads(rows, [])

    def test_unknown_copied_body_and_human_flags_rejected_at_every_level(self):
        for location in ("lead", "provenance", "scope"):
            for field in ("body", "raw_text", "source", "secret", "human_verified", "confirmed_valid"):
                rows = self.leads()
                destination = rows[0] if location == "lead" else rows[0]["provenance"][0] if location == "provenance" else rows[0]["target_scope"]
                destination[field] = "copied text or manufactured verification"
                with self.subTest(location=location, field=field), self.assertRaises(ValueError):
                    collect.merge_leads(rows, [])

    def test_cache_types_lengths_and_summary_are_strict(self):
        cases = (("summary", "copied article body"), ("observed_at", ["2026-10-24T12:00:00Z"]),
                 ("transaction_hash_candidates", [TX, TX]), ("transaction_hash_candidates", [TX.upper()]),
                 ("transaction_hash_candidates", [TX] * 101), ("related_lead_ids", ["not-an-id"]),
                 ("provenance", []), ("provenance", "raw article text"),
                 ("target_scope", {"chain_id": True, "language": "Solidity"}))
        for field, value in cases:
            rows = self.leads()
            rows[0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                collect.merge_leads(rows, [])
        rows = self.leads()
        rows[0]["provenance"][0]["response_sha256"] = "not-a-hash"
        with self.assertRaises(ValueError):
            collect.merge_leads(rows, [])

    def test_public_urls_reject_credentials_rpc_and_local_namespaces(self):
        urls = ("https://example.org/report?api_key=fixture-secret", "https://example.org/report?access_token=fixture-secret",
                "https://example.org/report?API-KEY=fixture-secret", "https://example.org/report?%61pi%5Fkey=fixture-secret",
                "https://example.org/report?url=https%3A%2F%2Fexample.org%2F%3Ftoken%3Dfixture-secret",
                "https://x.com/user/status/123?token=fixture-secret", "https://example.org/?X-Amz-Signature=fixture-secret",
                "https://eth-mainnet.g.alchemy.com/v2/fixture-secret", "https://mainnet.infura.io/v3/fixture-secret",
                "https://eth.rpc.example.org/", "https://node.quicknode.pro/fixture-secret/", "https://node.internal/",
                "https://host.local/", "https://host.test/", "https://localhost.localdomain/", "https://singlelabel/",
                "https://192.168.1.1/", "https://0x7f.0.0.1/", "https://home.arpa/", "https://example.org./")
        for url in urls:
            with self.subTest(url=url), self.assertRaises(ValueError):
                collect.canonical_url(url)

    def test_cached_provenance_cannot_smuggle_url_or_post_text(self):
        for url in ("https://www.openzeppelin.com/news/rss.xml?api_key=fixture-secret",
                    "https://www.openzeppelin.com/news/rss.xml?full_article=copied-text",
                    "https://evil.example.org/feed", "https://news.google.com/rss/search?q=copied-post-text"):
            rows = self.leads()
            rows[0]["provenance"][0]["source_url"] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                collect.merge_leads(rows, [])

    def test_bounded_cache_rejects_size_row_count_and_long_lines_before_network(self):
        data = "".join(json.dumps(row) + "\n" for row in collect.merge_leads([], self.leads()))
        self.args.out.write_text(data)
        fetcher = Mock()
        limits = (("CACHE_MAX_BYTES", len(data.encode()) - 1), ("CACHE_MAX_ROW_BYTES", len(data.encode()) - 1), ("CACHE_MAX_ROWS", 0))
        for constant, limit in limits:
            before = self.args.out.read_bytes()
            with self.subTest(constant=constant), patch.object(collect, constant, limit), self.assertRaises(ValueError):
                collect.collect(self.sources[:1], self.args, NOW, fetcher)
            self.assertEqual(before, self.args.out.read_bytes())
        fetcher.assert_not_called()
        self.assertFalse(self.args.status_out.exists())

    def test_offline_cache_validation_bypasses_config_and_never_fetches_or_writes(self):
        rows = collect.merge_leads([], self.leads())
        self.args.out.write_text("".join(json.dumps(row) + "\n" for row in rows))
        before = self.args.out.read_bytes()
        with patch.object(collect, "fetch") as fetcher, patch.object(collect, "atomic_write") as writer, patch.object(collect, "load_config") as config_loader, contextlib.redirect_stdout(io.StringIO()) as stdout:
            result = collect.main(["--validate-cache", str(self.args.out)])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(stdout.getvalue())["mode"], "offline-cache-validation")
        fetcher.assert_not_called()
        writer.assert_not_called()
        config_loader.assert_not_called()
        self.assertEqual(before, self.args.out.read_bytes())
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            collect.main(["--validate-cache", str(self.args.out), "--execute"])

    def test_invalid_cache_ci_exit_is_nonzero_and_opaque(self):
        rows = self.leads()
        rows[0]["raw_body"] = "fixture-secret copied article"
        self.args.out.write_text(json.dumps(rows[0]) + "\n")
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(collect.main(["--validate-cache", str(self.args.out)]), 2)
        self.assertNotIn("fixture-secret", stderr.getvalue())
        self.assertNotIn("copied article", stderr.getvalue())

    def test_duplicate_json_keys_and_fabricated_related_leads_fail_validation(self):
        row = collect.merge_leads([], self.leads())[0]
        self.args.out.write_text(json.dumps(row)[:-1] + ',"status":"proposed"}\n')
        with self.assertRaisesRegex(ValueError, "duplicate_cached_json_field"):
            collect.read_cache(self.args.out)
        row["related_lead_ids"] = ["lead_" + "a" * 24]
        self.args.out.write_text(json.dumps(row) + "\n")
        with self.assertRaisesRegex(ValueError, "invalid_cached_related_leads"):
            collect.read_cache(self.args.out)

    def test_serper_selected_source_environment_key_required(self):
        fetcher = Mock()
        with patch.dict("os.environ", {}, clear=True):
            status = collect.collect([self.source("serper-news")], self.args, NOW, fetcher)
        self.assertEqual(status["sources"][0]["error"], "missing_serper_api_key")
        fetcher.assert_not_called()

    def test_rss_collection_does_not_read_any_environment_credentials(self):
        with patch.object(collect.os.environ, "get", side_effect=AssertionError("no environment reads for RSS")):
            status = collect.collect([self.source()], self.args, NOW, Mock(return_value=RSS))
        self.assertEqual(status["failed_sources"], 0)

    def test_serper_request_metadata_rejects_unknown_fields_queries_and_dates(self):
        source = self.source("serper-news")
        payload = collect.source_payload(source, 7, NOW, 10)
        items = [{"url": "https://example.org/news", "published_at": None, "signal": "Ethereum exploit"}]
        rows, _ = collect.make_leads(items, source, source["url"], "a" * 64, NOW, 7, 10, payload)
        for request in ({**payload, "raw_body": "private post"}, {**payload, "num": True},
                        {**payload, "num": 101}, {**payload, "q": "copied snippet"},
                        {**payload, "q": payload["q"].replace("2026-10-25", "2026-10-26")}):
            tampered = json.loads(json.dumps(rows))
            tampered[0]["provenance"][0]["request"] = request
            with self.subTest(request=request), self.assertRaises(ValueError):
                collect.merge_leads(tampered, [])

    def test_serper_news_one_post_request_and_no_snippets_stored(self):
        payload = {"news": [{"link": "https://example.org/report", "date": "2026-10-23T10:00:00Z", "title": "Ethereum exploit", "snippet": "PRIVATE FIXTURE TEXT " + TX}]}
        fetcher = Mock(return_value=json.dumps(payload).encode())
        with patch.dict("os.environ", {"SERPER_API_KEY": "fixture-token"}):
            status = collect.collect([self.source("serper-news")], self.args, NOW, fetcher)
        self.assertEqual(status["failed_sources"], 0)
        fetcher.assert_called_once()
        url = fetcher.call_args.args[0]
        self.assertEqual(url, "https://google.serper.dev/news")
        self.assertEqual(fetcher.call_args.kwargs["api_key"], "fixture-token")
        request = fetcher.call_args.kwargs["payload"]
        self.assertEqual(request["num"], 30)
        self.assertEqual(request["q"], "(Ethereum OR Solidity) (hack OR exploit OR drained) after:2026-10-10 before:2026-10-25")
        self.assertTrue(status["sources"][0]["single_page"])
        self.assertNotIn("fixture-token", self.args.status_out.read_text())
        self.assertNotIn("PRIVATE FIXTURE TEXT", self.args.out.read_text())
        rows = collect.read_cache(self.args.out)
        self.assertEqual(rows[0]["provenance"][0]["request"], request)

    def test_serper_api_error_body_never_stored(self):
        with self.assertRaisesRegex(collect.CollectionError, "serper_api_errors"):
            collect.serper_items(b'{"error":"private-token"}', self.source("serper-news"))

    def test_serper_x_links_keep_unknown_publication_dates_without_x_fetches(self):
        payload = {"organic": [
            {"link": "https://x.com/security/status/123456", "date": "2 days ago", "title": "Ethereum exploit", "snippet": "PRIVATE SNIPPET"},
            {"link": "https://twitter.com/security/status/123457", "date": "Oct 23, 2026", "title": "Solidity hacked"},
            {"link": "https://example.org/not-x", "date": "2026-10-23T10:00:00Z", "title": "Ethereum hack"}]}
        fetcher = Mock(return_value=json.dumps(payload).encode())
        with patch.dict("os.environ", {"SERPER_API_KEY": "fixture-token"}):
            status = collect.collect([self.source("serper-x-links")], self.args, NOW, fetcher)
        fetcher.assert_called_once()
        self.assertEqual(fetcher.call_args.args[0], "https://google.serper.dev/search")
        self.assertIn("site:x.com OR site:twitter.com", fetcher.call_args.kwargs["payload"]["q"])
        self.assertEqual(status["sources"][0]["undated"], 2)
        rows = collect.read_cache(self.args.out)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["published_at"] is None and row["first_seen_at"] is None for row in rows))
        self.assertTrue(all(row["provenance"][0]["published_at"] is None for row in rows))
        self.assertNotIn("PRIVATE SNIPPET", self.args.out.read_text())

    def test_serper_unknown_dates_merge_with_dated_rss_without_inventing_time(self):
        source = self.source("serper-news")
        items = [{"url": "https://example.org/report", "published_at": "2 hours ago", "signal": "Ethereum exploit"}]
        unknown, counts = collect.make_leads(items, source, source["url"], "a" * 64, NOW, 14, 30, collect.source_payload(source, 14, NOW, 30))
        self.assertIsNone(unknown[0]["published_at"])
        self.assertEqual(counts["undated"], 1)
        merged = collect.merge_leads(unknown, self.leads())
        self.assertEqual(merged[0]["published_at"], "2026-10-23T10:00:00Z")
        self.assertEqual(len(merged[0]["provenance"]), 2)
        rss = self.leads()
        rss[0]["published_at"] = None
        rss[0]["provenance"][0]["published_at"] = None
        with self.assertRaises(ValueError):
            collect.merge_leads(rss, [])

    def test_serper_errors_are_opaque_and_preserve_successful_rss(self):
        def fetcher(url, **kwargs):
            if "serper" in url:
                raise RuntimeError("fixture-token PRIVATE SNIPPET")
            return RSS
        with patch.dict("os.environ", {"SERPER_API_KEY": "fixture-token"}):
            status = collect.collect([self.source(), self.source("serper-news")], self.args, NOW, fetcher)
        self.assertEqual(status["failed_sources"], 1)
        self.assertEqual(status["lead_count"], 1)
        self.assertNotIn("fixture-token", self.args.status_out.read_text())
        self.assertNotIn("PRIVATE SNIPPET", self.args.status_out.read_text())

    def test_fetch_blocks_redirect_proxy_and_bounds_response(self):
        response = Mock()
        response.status = 200
        response.headers = {}
        response.read.return_value = b"x" * 1025
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        opener = Mock()
        opener.open.return_value = response
        with patch.object(collect.urllib.request, "build_opener", return_value=opener) as build:
            with self.assertRaisesRegex(collect.CollectionError, "response_too_large"):
                collect.fetch("https://google.serper.dev/news", api_key="fixture-token", payload=collect.source_payload(self.source("serper-news"), 14, NOW, 10), max_bytes=1024)
        self.assertEqual(build.call_args.args[0].proxies, {})
        self.assertIsInstance(build.call_args.args[1], collect.NoRedirect)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_header("X-api-key"), "fixture-token")
        self.assertIsNone(request.get_header("Authorization"))
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(json.loads(request.data)["num"], 10)
        self.assertNotIn("fixture-token", request.full_url)
        response.read.assert_called_once_with(1025)
        with self.assertRaisesRegex(collect.CollectionError, "redirect_refused"):
            collect.NoRedirect().redirect_request(request, None, 302, "redirect", {}, "https://evil.example/")
        for url in ("https://evil.example/2/tweets/search/recent", "http://api.x.com/2/tweets/search/recent", "https://api.x.com:443/2/tweets/search/recent"):
            with self.subTest(url=url), self.assertRaisesRegex(collect.CollectionError, "credential_endpoint_refused"):
                collect.fetch(url, api_key="fixture-token", payload={"q": "test", "num": 10})

    def test_x_requests_are_impossible_even_without_credentials(self):
        for url in ("https://api.x.com/2/tweets/search/recent", "https://api.twitter.com/2/tweets/search/recent", "https://x.com/security/status/123"):
            with self.subTest(url=url), patch.object(collect.urllib.request, "build_opener") as build:
                with self.assertRaisesRegex(collect.CollectionError, "network_endpoint_refused"):
                    collect.fetch(url)
                build.assert_not_called()

    def test_allowlist_rejects_modified_host_and_serper_url(self):
        config = json.loads(collect.CONFIG.read_text())
        config["sources"][0]["url"] = "https://localhost/rss/search"
        path = self.path / "config.json"
        path.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, "feed_endpoint_not_allowlisted"):
            collect.load_config(path)
        config = json.loads(collect.CONFIG.read_text())
        config["sources"][2]["url"] = "https://evil.example/"
        path.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, "serper_contract_is_fixed"):
            collect.load_config(path)

    def test_default_is_offline_no_writes_and_execute_requires_sources(self):
        with patch.object(collect, "fetch") as fetcher, contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(collect.main(["--out", str(self.args.out), "--status-out", str(self.args.status_out)]), 0)
        fetcher.assert_not_called()
        self.assertEqual(json.loads(stdout.getvalue())["network"], False)
        self.assertFalse(self.args.out.exists())
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            collect.main(["--execute"])

    def test_main_partial_failure_exit_and_identical_outputs_rejected(self):
        with patch.object(collect, "fetch", side_effect=collect.CollectionError("http_429")), contextlib.redirect_stdout(io.StringIO()):
            code = collect.main(["--execute", "--source", "openzeppelin", "--out", str(self.args.out), "--status-out", str(self.args.status_out)])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(self.args.status_out.read_text())["sources"][0]["error"], "http_429")
        self.args.status_out = self.args.out
        with self.assertRaisesRegex(ValueError, "output_paths_must_differ"):
            collect.collect(self.sources[:1], self.args, NOW, Mock())


if __name__ == "__main__":
    unittest.main()
