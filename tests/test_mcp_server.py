"""Exercise real stdio framing and fixed read-only metadata tools offline."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/mcp/server.py'
SPEC = importlib.util.spec_from_file_location('mcp_test_server', SCRIPT)
server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server)


class McpTests(unittest.TestCase):
    def test_stdio_initialize_search_status_and_unknown_methods(self):
        requests = [
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25'}},
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'search_incidents', 'arguments': {'query': 'BiFi', 'limit': 2}}},
            {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'get_dataset_status'}},
            {'jsonrpc': '2.0', 'id': 4, 'method': 'execute_shell'},
            {'jsonrpc': '2.0', 'id': 5, 'method': 'tools/call', 'params': {'name': 'search_incidents', 'arguments': {'query': 'fee', 'limit': 999}}},
        ]
        result = subprocess.run([sys.executable, '-I', str(SCRIPT)], input='\n'.join(map(json.dumps, requests)) + '\n',
                                text=True, capture_output=True, check=True, timeout=10)
        rows = list(map(json.loads, result.stdout.splitlines()))
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]['result']['protocolVersion'], '2025-11-25')
        self.assertTrue(json.loads(rows[1]['result']['content'][0]['text'])['matches'])
        self.assertGreaterEqual(json.loads(rows[2]['result']['content'][0]['text'])['entry_count'], 357)
        self.assertEqual(rows[3]['error']['code'], -32601)
        self.assertEqual(rows[4]['error']['code'], -32602)

    def test_feed_rejects_count_tampering_or_human_verified_records(self):
        data = server.catalog.public_catalog()
        data['entry_count'] += 1
        with self.assertRaises(ValueError):
            server.validate_feed(data)
        data = server.catalog.public_catalog()
        data['records'][0]['human_verified'] = True
        with self.assertRaises(ValueError):
            server.validate_feed(data)
