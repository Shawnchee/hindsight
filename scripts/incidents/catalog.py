"""Bounded DeFiHackLabs metadata refresh and conservative incident matching.

Never executes or publishes fetched code. The historical CSV and research
exports remain immutable; additions live in an explicitly provisional overlay.
"""
import argparse
from collections import Counter
import csv
from datetime import date, datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / 'datasets/catalog/current.json'
PUBLIC = ROOT / 'website/data/catalog.json'
SPEC = importlib.util.spec_from_file_location('discovery_collect', Path(__file__).with_name('collect.py'))
collect = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collect)
BASELINE = ROOT / 'm0/catalog/ethereum_incidents.csv'
UPSTREAM = 'https://github.com/SunWeb3Sec/DeFiHackLabs'
RAW = 'https://raw.githubusercontent.com/SunWeb3Sec/DeFiHackLabs/'
SCHEMA = 'hindsight.catalog.v1'
RECORD_FIELDS = {'id', 'name', 'date', 'chain_id', 'status', 'human_verified', 'training_eligible',
                 'evaluation_eligible', 'transactions', 'contracts', 'sources', 'upstream_paths',
                 'loss_reported', 'reported_cause', 'stage'}


def digest(value):
    return hashlib.sha256(value).hexdigest()


def normal(value):
    return re.sub(r'[^a-z0-9]', '', value.lower())


def read_json(path, limit=4 * 1024 * 1024):
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file() or path.stat().st_size > limit:
        raise ValueError('invalid_metadata_file')
    return json.loads(path.read_text(), object_pairs_hook=collect.unique_json_fields)


def record_valid(row):
    if not isinstance(row, dict) or set(row) != RECORD_FIELDS:
        raise ValueError('invalid_catalog_record')
    if (not isinstance(row['id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,150}', row['id'])
            or not isinstance(row['name'], str) or not 1 <= len(row['name']) <= 160
            or any(ord(c) < 32 for c in row['name']) or row['chain_id'] != 1
            or row['status'] != 'reported_unverified' or row['human_verified'] is not False
            or row['training_eligible'] is not False or row['evaluation_eligible'] is not False
            or row['stage'] not in {'baseline_catalog', 'upstream_metadata'}):
        raise ValueError('invalid_catalog_record')
    date.fromisoformat(row['date'])
    if not isinstance(row['loss_reported'], str) or len(row['loss_reported']) > 1200:
        raise ValueError('invalid_catalog_loss')
    if row['reported_cause'] is not None and (not isinstance(row['reported_cause'], str) or len(row['reported_cause']) > 240):
        raise ValueError('invalid_reported_cause')
    for key, size in [('transactions', 64), ('contracts', 40)]:
        if (not isinstance(row[key], list) or len(row[key]) > 100
                or any(not isinstance(v, str) or not re.fullmatch(r'0x[a-f0-9]{' + str(size) + '}', v) for v in row[key])):
            raise ValueError('invalid_catalog_identifiers')
    if not isinstance(row['sources'], list) or not 1 <= len(row['sources']) <= 30:
        raise ValueError('invalid_catalog_sources')
    for url in row['sources']:
        collect.canonical_url(url)
    if not isinstance(row['upstream_paths'], list) or not 1 <= len(row['upstream_paths']) <= 20:
        raise ValueError('invalid_upstream_paths')
    for path in row['upstream_paths']:
        if not re.fullmatch(r'src/test/\d{4}-\d{2}/[A-Za-z0-9_.-]+\.sol', path):
            raise ValueError('invalid_upstream_path')


def baseline():
    records = []
    for row in csv.DictReader(BASELINE.read_text().splitlines()):
        record = {'id': row['incident_id'], 'name': row['name'], 'date': row['date'], 'chain_id': 1,
                  'status': 'reported_unverified', 'human_verified': False,
                  'training_eligible': False, 'evaluation_eligible': False,
                  'transactions': sorted(set(re.findall(r'0x[a-fA-F0-9]{64}', row['attack_tx_hashes'].lower()))),
                  'contracts': sorted(set(re.findall(r'0x[a-fA-F0-9]{40}', row['victim_addresses'].lower()))),
                  'sources': [UPSTREAM + '/blob/23c7bd83ccb4524972a9493617fcc8764ab6269b/' + row['readme_source']],
                  'upstream_paths': [p for p in [row['poc_path'], *row['extra_poc_paths'].split(';')] if p],
                  'loss_reported': row['loss_readme'][:1200], 'reported_cause': row['raw_label'][:240], 'stage': 'baseline_catalog'}
        record_valid(record)
        records.append(record)
    return records


def load_state(path=STATE):
    if not path.exists():
        return {'schema_version': SCHEMA, 'updated_at': None, 'upstream_commit': None,
                'additional': [], 'related_reports': {}, 'pending': [], 'last_refresh': None}
    state = read_json(path)
    if set(state) != {'schema_version', 'updated_at', 'upstream_commit', 'additional', 'related_reports', 'pending', 'last_refresh'} or state['schema_version'] != SCHEMA:
        raise ValueError('invalid_catalog_state')
    if not isinstance(state['additional'], list) or len(state['additional']) > 2000:
        raise ValueError('invalid_catalog_state')
    if state['updated_at'] is not None:
        collect.cache_timestamp(state['updated_at'])
    if state['upstream_commit'] is not None and not re.fullmatch(r'[a-f0-9]{40}', str(state['upstream_commit'])):
        raise ValueError('invalid_upstream_commit')
    if not isinstance(state['pending'], list) or len(state['pending']) > 30:
        raise ValueError('invalid_pending_records')
    for row in state['pending']:
        if (not isinstance(row, dict) or set(row) != {'name', 'date', 'reason'}
                or not isinstance(row['name'], str) or not 1 <= len(row['name']) <= 160
                or row['reason'] not in {'daily_fetch_cap', 'chain_missing_or_conflicting',
                    'missing_attack_transaction_or_victim', 'source_metadata_unavailable', 'ambiguous_incident_identity'}):
            raise ValueError('invalid_pending_record')
        date.fromisoformat(row['date'])
    for row in state['additional']:
        record_valid(row)
        if row['stage'] != 'upstream_metadata':
            raise ValueError('invalid_overlay_stage')
    if len({r['id'] for r in state['additional']}) != len(state['additional']):
        raise ValueError('duplicate_catalog_id')
    # Do not trust a fetched/edited operational file to carry unchecked URLs.
    if not isinstance(state['related_reports'], dict) or len(state['related_reports']) > 5000:
        raise ValueError('invalid_related_reports')
    for ident, urls in state['related_reports'].items():
        if not isinstance(urls, list) or len(urls) > 30:
            raise ValueError('invalid_related_reports')
        for url in urls:
            collect.canonical_url(url)
    return state


def matching(candidate, records):
    """Prefer upstream identity; conflicting/multiple identities never add a row."""
    paths = set(candidate['upstream_paths'])
    direct = [r for r in records if paths.intersection(r['upstream_paths'])]
    if len(direct) == 1:
        return 'existing', direct[0]['id']
    if len(direct) > 1:
        return 'ambiguous', None
    tx = set(candidate['transactions'])
    linked = [r for r in records if tx.intersection(r['transactions'])]
    named = [r for r in records if normal(r['name']) == normal(candidate['name']) and r['date'] == candidate['date']]
    if len(linked) == 1 and linked[0]['date'] == candidate['date']:
        # A report containing another incident's tx is not a license to merge it.
        if named and any(r['id'] != linked[0]['id'] for r in named):
            return 'ambiguous', None
        if normal(linked[0]['name']) == normal(candidate['name']) or set(linked[0]['contracts']).intersection(candidate['contracts']):
            return 'existing', linked[0]['id']
    if linked or named:
        return 'ambiguous', None
    return 'new', None


def entries(markdown, now):
    result = []
    pattern = r'^###\s+(\d{8})\s+(.+?)(?=^###\s+\d{8}\s|\Z)'
    for match in re.finditer(pattern, markdown, re.M | re.S):
        day = date.fromisoformat(match[1][:4] + '-' + match[1][4:6] + '-' + match[1][6:])
        if day > now.date():
            continue
        block = match[2]
        heading = block.splitlines()[0]
        name = heading.split(' - ', 1)[0].strip()
        paths = sorted(set(re.findall(r'\((src/test/\d{4}-\d{2}/[A-Za-z0-9_.-]+\.sol)\)', block)))
        if not paths or not 1 <= len(name) <= 160:
            continue
        loss = re.search(r'^###\s+Lost:\s*(.+)', block, re.M | re.I)
        result.append({'name': name, 'date': day.isoformat(), 'paths': paths[:20],
                       'claim': heading.split(' - ', 1)[1][:1800] if ' - ' in heading else '',
                       'loss': loss[1][:1200] if loss else ''})
    return sorted(result, key=lambda x: (x['date'], x['name']), reverse=True)[:30]


def candidate(entry, source, commit):
    # Solidity is read only as text. Only explicit chain/tx/address metadata is
    # extracted; code and comment analysis bodies are never persisted or run.
    header = '\n'.join(line for line in source.splitlines()[:100] if line.lstrip().startswith('//'))
    chains = re.findall(r'(?im)^//\s*Chain\s*:\s*(.+)', header)
    explicit_mainnet = any(re.search(r'\bEthereum(?: mainnet)?\b', c, re.I) for c in chains)
    other = any(re.search(r'\b(?:BNB|BSC|Base|Arbitrum|Polygon|Optimism|Avalanche|testnet)\b', c, re.I) for c in chains)
    forks = re.findall(r'createSelectFork\(\s*"([A-Za-z0-9_-]+)"', source)
    if forks and any(f.lower() not in {'mainnet', 'ethereum', 'eth'} for f in forks):
        other = True
    if not (explicit_mainnet or forks) or other:
        return None, 'chain_missing_or_conflicting'
    tx_lines = [line for line in header.splitlines() if re.match(r'//\s*(?:Attack|Profit|Exploit)(?:\s+Tx|\s+Transaction)\s*:', line, re.I)]
    transactions = sorted(set(re.findall(r'https://etherscan\.io/tx/(0x[a-fA-F0-9]{64})', '\n'.join(tx_lines))))
    victims = [line for line in header.splitlines() if re.match(r'//\s*(?:Vulnerable|Victim)(?:\s+(?:Contract|proxy))?\s*:', line, re.I)]
    contracts = sorted(set(x.lower() for x in re.findall(r'0x[a-fA-F0-9]{40}', '\n'.join(victims))))
    if not transactions or not contracts:
        return None, 'missing_attack_transaction_or_victim'
    row = {'id': 'dhl_' + digest(('1:' + transactions[0].lower()).encode())[:24],
           'name': entry['name'], 'date': entry['date'], 'chain_id': 1,
           'status': 'reported_unverified', 'human_verified': False, 'training_eligible': False,
           'evaluation_eligible': False, 'transactions': [x.lower() for x in transactions],
           'contracts': contracts, 'upstream_paths': entry['paths'], 'loss_reported': entry['loss'],
           'sources': [UPSTREAM + '/blob/' + commit + '/README.md',
                       UPSTREAM + '/blob/' + commit + '/' + entry['paths'][0],
                       *['https://etherscan.io/tx/' + x.lower() for x in transactions]],
           'reported_cause': None, 'stage': 'upstream_metadata'}
    record_valid(row)
    return row, None


def fetch_public(url, max_bytes=4 * 1024 * 1024):
    if not (url == 'https://api.github.com/repos/SunWeb3Sec/DeFiHackLabs/commits/main'
            or re.fullmatch(re.escape(RAW) + r'[a-f0-9]{40}/(?:README\.md|src/test/\d{4}-\d{2}/[A-Za-z0-9_.-]+\.sol)', url)):
        raise ValueError('upstream_endpoint_refused')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), collect.NoRedirect())
    request = urllib.request.Request(url, headers={'User-Agent': 'Hindsight-Metadata/1.0', 'Accept': 'application/json'})
    with opener.open(request, timeout=20) as response:
        body = response.read(max_bytes + 1)
        if response.status != 200 or len(body) > max_bytes:
            raise ValueError('upstream_response_limit')
    return body


def refresh(state, now=None, fetcher=fetch_public):
    now = now or datetime.now(timezone.utc)
    result = json.loads(json.dumps(state))
    before = len(result['additional'])
    commit = json.loads(fetcher('https://api.github.com/repos/SunWeb3Sec/DeFiHackLabs/commits/main'))['sha']
    if not re.fullmatch(r'[a-f0-9]{40}', commit):
        raise ValueError('invalid_upstream_commit')
    markdown = fetcher(RAW + commit + '/README.md').decode('utf-8')
    records = baseline() + result['additional']
    pending, summary_inputs, checked = [], [], 0
    for item in entries(markdown, now):
        existing = [r for r in records if set(item['paths']).intersection(r['upstream_paths'])]
        if len(existing) == 1:
            summary_inputs.append({'id': existing[0]['id'], 'name': existing[0]['name'],
                                   'claim': item['claim'], 'loss_reported': item['loss'],
                                   'source_url': UPSTREAM + '/blob/' + commit + '/README.md'})
            continue
        if checked >= 8:
            pending.append({'name': item['name'], 'date': item['date'], 'reason': 'daily_fetch_cap'})
            continue
        checked += 1
        try:
            source = fetcher(RAW + commit + '/' + item['paths'][0], max_bytes=128 * 1024).decode('utf-8')
            row, reason = candidate(item, source, commit)
        except Exception:
            row, reason = None, 'source_metadata_unavailable'
        if row is None:
            pending.append({'name': item['name'], 'date': item['date'], 'reason': reason})
            continue
        decision, ident = matching(row, records)
        if decision == 'new':
            records.append(row)
            result['additional'].append(row)
            ident = row['id']
        elif decision == 'ambiguous':
            pending.append({'name': item['name'], 'date': item['date'], 'reason': 'ambiguous_incident_identity'})
            continue
        summary_inputs.append({'id': ident, 'name': row['name'], 'claim': item['claim'],
                               'loss_reported': item['loss'], 'source_url': row['sources'][0]})
    # Reports with a unique shared tx are possible evidence links, not another
    # counted incident. Roundups/multiple matches remain outside the catalog.
    queue = ROOT / 'incidents/discovery/leads.jsonl'
    if queue.exists():
        for lead in collect.read_cache(queue):
            ids = {r['id'] for r in records if set(lead['transaction_hash_candidates']).intersection(r['transactions'])}
            if len(ids) == 1:
                ident = next(iter(ids))
                result['related_reports'][ident] = sorted(set(result['related_reports'].get(ident, []) + [lead['canonical_url']]))[:30]
    result.update(updated_at=collect.stamp(now), upstream_commit=commit, pending=pending,
                  last_refresh={'source': 'DeFiHackLabs', 'metadata_files_checked': checked,
                                'added': len(result['additional']) - before, 'pending': len(pending)})
    return result, summary_inputs


def public_catalog(state=None):
    state = load_state() if state is None else state
    records = baseline() + state['additional']
    if len({r['id'] for r in records}) != len(records):
        raise ValueError('catalog_id_collision')
    summaries = {}
    summary_path = ROOT / 'incidents/discovery/ai-summaries.json'
    if summary_path.exists():
        payload = read_json(summary_path)
        ids = {r['id'] for r in records}
        for row in payload['records']:
            if (row.get('id') not in ids or row.get('status') != 'ai_proposed' or row.get('human_verified') is not False
                    or row.get('training_eligible') is not False or row.get('evaluation_eligible') is not False):
                raise ValueError('invalid_published_summary')
            for field, cap in [('summary', 600), ('support_quote', 240)]:
                if not isinstance(row.get(field), str) or not 1 <= len(row[field]) <= cap:
                    raise ValueError('invalid_published_summary')
            collect.canonical_url(row['source_url'])
            summaries[row['id']] = row
    return {'schema_version': SCHEMA, 'updated_at': state['updated_at'],
            'baseline_as_of': '2026-10-21', 'upstream_commit': state['upstream_commit'],
            'attribution': {'name': 'DeFiHackLabs', 'url': UPSTREAM, 'license': 'Apache-2.0'},
            'entry_count': len(records), 'year_counts': dict(Counter(r['date'][:4] for r in records)),
            'records': sorted(records, key=lambda r: (r['date'], r['id']), reverse=True), 'ai_summaries': summaries,
            'limitations': 'Reported metadata, not verified vulnerabilities. AI summaries are proposals. Possible news matches do not increase counts.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--write-public', action='store_true')
    parser.add_argument('--check', action='store_true', help='Validate generated public metadata offline without writing')
    parser.add_argument('--gemini', action='store_true', help='At most one summary batch; requires GEMINI_API_KEY')
    args = parser.parse_args()
    try:
        state = load_state()
        if args.check:
            if args.execute or args.write_public or args.gemini:
                raise ValueError('check_cannot_mutate')
            if read_json(PUBLIC) != public_catalog(state):
                raise ValueError('public_catalog_stale')
        if args.execute:
            state, inputs = refresh(state)
            collect.atomic_write(STATE, json.dumps(state, indent=2, sort_keys=True) + '\n')
            if args.gemini:
                spec = importlib.util.spec_from_file_location('catalog_summaries', Path(__file__).with_name('summarize.py'))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.compile_summaries(inputs)
        if args.write_public:
            collect.atomic_write(PUBLIC, json.dumps(public_catalog(state), indent=2, sort_keys=True) + '\n')
        print(json.dumps({'mode': 'executed' if args.execute else 'offline', 'entry_count': len(baseline()) + len(state['additional']),
                          'last_refresh': state['last_refresh']}))
    except Exception:
        parser.exit(1, 'Catalog refresh failed; inspect source health. No credentials or response bodies are logged.\n')


if __name__ == '__main__':
    main()
