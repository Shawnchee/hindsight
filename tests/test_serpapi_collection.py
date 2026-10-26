"""Synthetic SerpAPI responses and credentials; never make requests."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

SPEC = importlib.util.spec_from_file_location('serpapi_collect', Path(__file__).resolve().parents[1] / 'scripts/incidents/collect.py')
collect = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collect)
NOW = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)


class SerpApiTests(unittest.TestCase):
    def source(self, sid='serpapi-news'):
        return next(s for s in collect.load_config(collect.CONFIG)['sources'] if s['id'] == sid)

    def test_grouped_news_and_indexed_x_links_persist_no_key_or_copied_text(self):
        news = {'search_metadata': {'status': 'Success'}, 'news_results': [
            {'stories': [{'title': 'Ethereum hack', 'link': 'https://example.org/report',
                          'snippet': 'PRIVATE SNIPPET', 'date': '2 days ago'}]}]}
        links = {'search_metadata': {'status': 'Success'}, 'organic_results': [
            {'title': 'Ethereum exploit', 'link': 'https://x.com/research/status/123'},
            {'title': 'Ethereum exploit', 'link': 'https://example.org/unrelated'}]}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            args = SimpleNamespace(out=root / 'leads.jsonl', status_out=root / 'status.json',
                                   days=7, max_items=10, timeout=15, max_bytes=1048576)
            for sid, body in [('serpapi-news', news), ('serpapi-x-links', links)]:
                fetcher = Mock(return_value=json.dumps(body).encode())
                with patch.dict('os.environ', {'SERPAPI_API_KEY': 'fixture-key'}):
                    result = collect.collect([self.source(sid)], args, NOW, fetcher)
                self.assertEqual(result['failed_sources'], 0)
                self.assertEqual(fetcher.call_count, 1)
                self.assertEqual(fetcher.call_args.args[0], 'https://serpapi.com/search.json')
                self.assertNotIn('fixture-key', args.status_out.read_text())
                self.assertNotIn('PRIVATE SNIPPET', args.out.read_text())
            records = collect.read_cache(args.out)
            self.assertEqual(len(records), 2)
            self.assertTrue(all(r['published_at'] is None for r in records))

    def test_missing_key_never_requests_and_provider_errors_are_opaque(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            args = SimpleNamespace(out=root / 'leads.jsonl', status_out=root / 'status.json',
                                   days=7, max_items=10, timeout=15, max_bytes=1048576)
            fetcher = Mock()
            with patch.dict('os.environ', {}, clear=True):
                result = collect.collect([self.source()], args, NOW, fetcher)
            fetcher.assert_not_called()
            self.assertEqual(result['sources'][0]['error'], 'missing_serpapi_api_key')
        with self.assertRaisesRegex(collect.CollectionError, 'serpapi_api_errors'):
            collect.serpapi_items(b'{"error":"fixture-key"}', self.source())
        items, _ = collect.serpapi_items(json.dumps({'search_metadata': {'status': 'Success'},
            'error': "Google hasn't returned any results for this query."}).encode(), self.source())
        self.assertEqual(items, [])

    def test_key_is_sent_only_to_fixed_endpoint_without_redirects_or_proxy(self):
        response = Mock(status=200, headers={})
        response.read.return_value = b'{}'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        opener = Mock()
        opener.open.return_value = response
        for sid, engine in [('serpapi-news', 'google_news'), ('serpapi-x-links', 'google')]:
            payload = collect.source_payload(self.source(sid), 7, NOW, 10)
            with patch.object(collect.urllib.request, 'build_opener', return_value=opener) as build:
                collect.fetch('https://serpapi.com/search.json', api_key='fixture-key', payload=payload)
            request = opener.open.call_args.args[0]
            self.assertEqual(request.get_method(), 'GET')
            params = parse_qs(urlsplit(request.full_url).query)
            self.assertEqual(params['engine'], [engine])
            self.assertEqual(params['api_key'], ['fixture-key'])
            self.assertEqual(build.call_args.args[0].proxies, {})
            self.assertIsInstance(build.call_args.args[1], collect.NoRedirect)
        with self.assertRaises(collect.CollectionError):
            collect.fetch('https://serpapi.com/other', api_key='fixture-key', payload=payload)
