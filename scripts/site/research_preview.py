"""Render selected catalog entries and enriched snapshot metadata without source code."""
import argparse
import csv
import io
import importlib.util
from collections import Counter
import hashlib
import html
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
VERSION = 'v0.2.0'
SELECTED = ['20201106_CheeseBank', '20210829_xTokenAugust', '20200215_bZxFirst']
START, END = '    <!-- dataset-preview:start -->', '    <!-- dataset-preview:end -->'
REPO = 'https://github.com/Shawnchee/hindsight'


def public_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value)
    return parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password


def render():
    root = ROOT / 'datasets/research' / VERSION
    manifest = json.loads((root / 'manifest.json').read_text())
    inputs = {}
    for name in ('incidents.jsonl', 'contracts.jsonl'):
        raw = (root / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest['artifacts'][name]:
            raise ValueError('frozen snapshot payload does not match its manifest')
        inputs[name] = [json.loads(line) for line in raw.decode().splitlines()]
    catalog_path = ROOT / 'm0/catalog/ethereum_incidents.csv'
    catalog_raw = catalog_path.read_bytes()
    catalog = list(csv.DictReader(io.StringIO(catalog_raw.decode())))
    spec = importlib.util.spec_from_file_location('public_catalog', ROOT / 'scripts/incidents/catalog.py')
    current = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(current)
    live = current.public_catalog()
    for row in live['records']:
        if row['stage'] == 'upstream_metadata':
            catalog.append({'incident_id': row['id'], 'name': row['name'], 'date': row['date'],
                            'year': row['date'][:4], 'chain': 'ethereum', 'loss_readme': row['loss_reported'],
                            'readme_source': 'README.md', '_upstream_url': row['sources'][0],
                            '_record_url': 'data/catalog.json'})
    catalog_as_of = live['updated_at'][:10] if live['updated_at'] else '2026-10-21'
    counts = Counter(r['year'] for r in catalog)
    # Explicit selections, not a total: source amounts may span chains/recoveries.
    loss_selections = [('BalancerV2', 120_000_000, '120M USD'), ('Corkprotocol', 12_000_000, '12M USD'),
                       ('ResupplyFi', 9_600_000, '9.6M USD'), ('yETH', 9_000_000, '9M USD'),
                       ('Makina', 5_100_000, '5.1M USD')]
    loss_examples = []
    for name, amount, reported in loss_selections:
        row = next(r for r in catalog if r['name'] == name)
        if row['loss_readme'] != reported:
            raise ValueError('Selected loss amount changed; review its units and scope before publishing')
        loss_examples.append({'name': name, 'reported_usd': amount, 'reported_text': reported,
                              'reported_date': row['date'], 'incident_id': row['incident_id'],
                              'record_url': f'{REPO}/blob/main/m0/catalog/ethereum_incidents.csv#L{catalog.index(row) + 2}',
                              'verification': 'source_reported_unverified', 'scope': 'may_include_other_chains_or_gross_losses'})
    loss_examples.sort(key=lambda item: (-item['reported_usd'], item['name']))
    annual = [{'year': str(year), 'entries': counts[str(year)]} for year in range(2017, max(2026, max(map(int, counts))) + 1)]
    count_bars = []
    for i, item in enumerate(annual):
        y = 12 + i * 27
        width = item['entries'] / max(counts.values()) * 285
        count_bars.append(f'<text x="0" y="{y + 14}">{item["year"]}</text><rect class="count-bar" x="58" y="{y}" width="{width:.2f}" height="18" rx="3"/><text x="{68 + width:.2f}" y="{y + 14}">{item["entries"]}</text>')
    loss_bars = []
    for i, item in enumerate(loss_examples):
        y = 16 + i * 52
        width = item['reported_usd'] / max(x['reported_usd'] for x in loss_examples) * 285
        loss_bars.append(f'<text x="0" y="{y}">{html.escape(item["name"])} · {item["reported_date"][:4]}</text><rect class="loss-bar" x="0" y="{y + 9}" width="{width:.2f}" height="14" rx="3"/><text x="{width + 9:.2f}" y="{y + 21}">${item["reported_usd"] / 1_000_000:g}M</text>')
    chart_table = ''.join(f'<tr><th scope="row"><a href="{x["record_url"]}">{html.escape(x["name"])}</a></th><td>{x["reported_date"]}</td><td>${x["reported_usd"]:,.0f}</td></tr>' for x in loss_examples)
    charts = f'''<div class="research-charts">
        <figure class="research-chart"><figcaption><h3>Incidents in the catalog</h3><p>Reported entries by year · {len(catalog)} total</p></figcaption>
          <svg viewBox="0 0 400 290" role="img" aria-labelledby="counts-title counts-desc"><title id="counts-title">Catalog entries by reported incident year</title><desc id="counts-desc">{'; '.join(x['year'] + ': ' + str(x['entries']) for x in annual)}. This is catalog coverage, not the frequency of all hacks.</desc>{''.join(count_bars)}</svg>
          <p class="chart-note">Coverage varies by year. Latest metadata refresh: {catalog_as_of}. Counts measure reported catalog coverage, not industry-wide hack frequency.</p>
        </figure>
        <figure class="research-chart"><figcaption><h3>Reported loss examples</h3><p>Highest to lowest · five selected cases · reported USD</p></figcaption>
          <svg viewBox="0 0 400 290" role="img" aria-labelledby="losses-title losses-desc"><title id="losses-title">Selected source-reported loss amounts</title><desc id="losses-desc">{'; '.join(x['name'] + ': ' + x['reported_text'] for x in loss_examples)}. Unverified figures; not a total or a ranking of all incidents.</desc>{''.join(loss_bars)}</svg>
          <p class="chart-note">Not total losses. Balancer’s $120M includes multiple chains. These are five selected examples; recoveries are not independently reconciled.</p>
        </figure>
      </div>
      <details class="dataset-details"><summary>Chart sources &amp; amounts</summary><p>Counts come from the pinned Ethereum catalog. Losses are selected explicit USD claims from its upstream metadata; no token prices or exchange rates were inferred. Balancer’s amount includes multiple chains. Catalog membership and chain classifications remain provisional.</p><table class="dataset-table"><caption class="sr-only">Selected loss claims and source records</caption><thead><tr><th scope="col">Source record</th><th scope="col">Incident date</th><th scope="col">Reported USD</th></tr></thead><tbody>{chart_table}</tbody></table></details>'''
    catalog_examples, catalog_views = [], []
    for year in ('2026', '2025'):
        recent = sorted((r for r in catalog if r['year'] == year), key=lambda r: (r['date'], r['incident_id']), reverse=True)[:3]
        recent_rows = []
        for r in recent:
            line = catalog.index(r) + 2
            upstream = r.get('_upstream_url') or 'https://github.com/SunWeb3Sec/DeFiHackLabs/blob/23c7bd83ccb4524972a9493617fcc8764ab6269b/' + r['readme_source']
            record = r.get('_record_url') or f'{REPO}/blob/main/m0/catalog/ethereum_incidents.csv#L{line}'
            catalog_examples.append({'incident_id': r['incident_id'], 'name': r['name'], 'reported_date': r['date'],
                                     'catalog_year': year, 'chain_classification': r['chain'], 'data_stage': 'catalog_entry',
                                     'enriched_snapshot_member': r['incident_id'] in {item['incident_id'] for item in inputs['incidents.jsonl']},
                                     'source_coverage': 'not_assessed_by_this_preview', 'human_adjudication': 'not_established',
                                     'catalog_record_url': record, 'upstream_index_url': upstream})
            recent_rows.append(f'''<tr><th scope="row">{html.escape(r['name'])}<time datetime="{html.escape(r['date'])}">{html.escape(r['date'])}</time></th><td>Catalog entry<br><span class="catalog-status">Coverage not assessed here</span></td><td><a href="{record}">Record ↗</a><a href="{html.escape(upstream, quote=True)}">Upstream ↗</a></td></tr>''')
        catalog_views.append(f'''<div class="dataset-view" data-dataset-view="{year}">
        <h3>{year} catalog examples</h3>
        <p class="dataset-note">Showing 3 of {counts[year]} reported entries from {year}. This is a preview; use the full catalog for every record.</p>
        <table class="dataset-table"><caption class="sr-only">Three recent {year} catalog entries; not enriched or verified by this preview.</caption><thead><tr><th scope="col">Reported incident</th><th scope="col">Data status</th><th scope="col">Evidence</th></tr></thead><tbody>{''.join(recent_rows)}</tbody></table>
        </div>''')
    records = {r['incident_id']: r for r in inputs['incidents.jsonl']}
    contracts = {r['address'].lower(): r for r in inputs['contracts.jsonl']}
    examples, rows = [], []
    for ident in SELECTED:
        r = records[ident]
        fields = ('incident_id', 'name', 'incident_date', 'chain_id', 'source_coverage', 'label_status',
                  'adjudication', 'human_verified', 'training_eligible', 'evaluation_eligible',
                  'first_seen_at', 'family_id', 'split', 'exact_transaction_state_verified', 'coverage_gaps')
        example = {key: r[key] for key in fields}
        example['primary_report_url'] = next(s['url'] for s in r['primary_sources'] if public_url(s.get('url')))
        example['transactions'] = r['transactions']
        example['contracts'] = r['contracts']
        example['proposed_defect_evidence'] = []
        for location in r['proposed_locations']:
            if location.get('role') != 'defect':
                continue
            contract = contracts[location['address'].lower()]
            example['proposed_defect_evidence'].append({
                key: location[key] for key in ('address', 'source_unit', 'source_sha256', 'evidence_line_start', 'evidence_line_end')})
            example['proposed_defect_evidence'][-1]['source_url'] = contract['source_url']
        examples.append(example)
        esc = html.escape
        coverage = 'Proposed defect file present' if r['source_coverage']['proposed_defect_files_present'] else 'Defect source still missing'
        line = list(records).index(ident) + 1
        rows.append(f'''          <tr>
            <th scope="row">{esc(r['name'])}<time datetime="{esc(r['incident_date'])}">{esc(r['incident_date'])}</time></th>
            <td>{coverage}</td>
            <td><a href="{esc(example['primary_report_url'], quote=True)}">Report <span aria-hidden="true">↗</span></a><a href="{REPO}/blob/main/datasets/research/{VERSION}/incidents.jsonl#L{line}">Record <span aria-hidden="true">↗</span></a></td>
          </tr>''')
    payload = {'schema_version': 'hindsight.public-preview.v1', 'snapshot': VERSION,
               'recorded_at': manifest['recorded_at'],
               'upstream_catalog_attribution': {'name': 'DeFiHackLabs', 'commit': '23c7bd8', 'license': 'Apache-2.0', 'license_file': 'DeFiHackLabs-LICENSE.txt', 'url': 'https://github.com/SunWeb3Sec/DeFiHackLabs'},
               'selection': 'Three selected enriched examples, not a representative sample or complete records; catalog examples are a separate projection.',
               'catalog': {'entry_count': len(catalog), 'year_counts': dict(counts), 'as_of': catalog_as_of, 'upstream_commit': live['upstream_commit'], 'baseline_commit': '23c7bd83ccb4524972a9493617fcc8764ab6269b', 'source_csv_sha256': hashlib.sha256(catalog_raw).hexdigest(), 'selection': 'Three most recent dated entries for each displayed year; no root-cause labels, PoCs or private source included.', 'examples': catalog_examples},
               'snapshot_payload_sha256': {name: manifest['artifacts'][name] for name in inputs},
               'charts': {'annual_entries': annual, 'selected_loss_examples': loss_examples, 'loss_total': None,
                          'methodology': 'Counts reflect pinned catalog coverage. Selected source USD claims are not reconciled, may span chains, and are not a total or exhaustive ranking.'},
               'examples': examples}
    sample = examples[0]
    excerpt = {key: sample[key] for key in ('incident_id', 'label_status', 'human_verified', 'first_seen_at', 'family_id', 'training_eligible', 'evaluation_eligible')}
    section = f'''    <section class="dataset" id="dataset" aria-labelledby="research-title">
      <div class="dataset-heading">
        <div><h2 id="research-title">Hundreds of incidents. Evidence you can inspect.</h2><p>Ethereum incident metadata, source references and research records.</p></div>
        <a class="dataset-link" href="docs/research.html">Dataset guide <span aria-hidden="true">↗</span></a>
      </div>
      <dl class="dataset-stats" aria-label="Dataset coverage">
        <div><dt>Reported incidents</dt><dd>{len(catalog)}</dd></div>
        <div><dt>From 2025–2026</dt><dd>{counts['2025'] + counts['2026']}</dd></div>
        <div><dt>Deeper research cases</dt><dd>{manifest['incident_count']}</dd></div>
      </dl>
      <p class="dataset-intro">Browse all {len(catalog)} catalog entries, including {counts['2025']} from 2025 and {counts['2026']} from 2026. The separate research snapshot covers {manifest['incident_count']} cases and {manifest['contract_snapshots']} components; its labels remain unverified ({manifest['human_verified_labels']} human-verified). Counts overlap.</p>
      <a class="dataset-link" href="data/catalog.json">Browse all {len(catalog)} incidents <span aria-hidden="true">↗</span></a>
      <p class="dataset-sources">Sources: <a href="https://github.com/SunWeb3Sec/DeFiHackLabs/tree/23c7bd8">DeFiHackLabs leads</a>, protocol/researcher reports, <a href="https://sourcify.dev/">Sourcify</a>/<a href="https://etherscan.io/">Etherscan</a>, and historical Ethereum reads.</p>
      <p class="dataset-asof">Metadata checked: {catalog_as_of}. Historical baseline: 21 October 2026. New records remain unverified; duplicate or ambiguous news reports do not increase these counts.</p>
      {charts}
      <div class="dataset-filters" role="group" aria-label="Choose dataset examples" hidden>
        <button type="button" data-dataset-filter="2026" aria-pressed="true">2026</button>
        <button type="button" data-dataset-filter="2025" aria-pressed="false">2025</button>
        <button type="button" data-dataset-filter="enriched" aria-pressed="false">Enriched snapshot</button>
      </div>
      {''.join(catalog_views)}
      <div class="dataset-view" data-dataset-view="enriched">
      <h3>Enriched snapshot {VERSION}</h3>
      <p class="dataset-note">Three older research examples. Components include proxies and dependencies, not separate vulnerable contracts.</p>
      <table class="dataset-table">
        <caption class="sr-only">Three selected examples from research snapshot {VERSION}. All labels are proposed and unresolved.</caption>
        <thead><tr><th scope="col">Incident</th><th scope="col">Source coverage</th><th scope="col">Evidence</th></tr></thead>
        <tbody>
{chr(10).join(rows)}
        </tbody>
      </table>
      <p class="dataset-note">All labels are AI-proposed and unresolved. A recovered file does not establish complete incident coverage. None of these enriched records is approved for training or evaluation.</p>
      </div>
      <details class="dataset-details">
        <summary>Where the data comes from</summary>
        <dl>
          <div><dt>Incident leads</dt><dd><a href="https://github.com/SunWeb3Sec/DeFiHackLabs/tree/23c7bd8">DeFiHackLabs</a> catalog (<a href="data/DeFiHackLabs-LICENSE.txt">Apache-2.0</a>), parsed from README entries and header identifiers, plus protocol post-mortems and original security research.</dd></div>
          <div><dt>Source &amp; chain evidence</dt><dd><a href="https://sourcify.dev/">Sourcify</a>, <a href="https://etherscan.io/">Etherscan</a>, and historical Ethereum RPC reads. Records retain addresses, transaction identifiers and source hashes.</dd></div>
          <div><dt>New reports</dt><dd>RSS and optional Serper find unverified leads. They stay in a separate review queue; they do not automatically enter this snapshot.</dd></div>
          <div><dt>What we publish</dt><dd>Metadata, evidence links and our own summaries. No contract source, PoCs or copied article/post bodies.</dd></div>
          <div><dt>What remains unknown</dt><dd>Earliest disclosure, exploit-family grouping, source availability at incident time and human adjudication. Publication dates and source matches do not resolve these gaps.</dd></div>
        </dl>
      </details>
      <details class="dataset-details">
        <summary>Inspect an actual record’s fields</summary>
        <p>This is a shortened Cheese Bank record, not a full training example.</p>
        <pre><code>{html.escape(json.dumps(excerpt, indent=2))}</code></pre>
        <a class="dataset-link" href="data/research-preview.json" download>Download catalog &amp; enriched examples <span aria-hidden="true">↓</span></a>
        <p>The preview separates six recent catalog entries from three enriched records, with evidence links, source fingerprints and coverage gaps. It is generated from the versioned snapshot; it includes no source code.</p>
      </details>
      <div class="dataset-actions"><a href="{REPO}/tree/main/datasets/research/{VERSION}">Browse the full snapshot <span aria-hidden="true">↗</span></a><a href="{REPO}/blob/main/CONTRIBUTING.md">Contribute evidence <span aria-hidden="true">↗</span></a></div>
    </section>'''
    return section, json.dumps(payload, indent=2, sort_keys=True) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='Refresh only the marked HTML block and public preview JSON')
    args = parser.parse_args()
    section, data = render()
    page = ROOT / 'website/index.html'
    text = page.read_text()
    if text.count(START) != 1 or text.count(END) != 1:
        parser.error('dataset markers must occur exactly once')
    a, b = text.index(START) + len(START), text.index(END)
    expected = text[:a] + '\n' + section + '\n' + text[b:]
    preview = ROOT / 'website/data/research-preview.json'
    license_text = (ROOT / 'third_party/DeFiHackLabs/LICENSE').read_text()
    license_out = ROOT / 'website/data/DeFiHackLabs-LICENSE.txt'
    project_license = (ROOT / 'LICENSE').read_text()
    project_license_out = ROOT / 'website/data/Hindsight-LICENSE.txt'
    if args.write:
        preview.parent.mkdir(parents=True, exist_ok=True)
        preview.write_text(data)
        license_out.write_text(license_text)
        project_license_out.write_text(project_license)
        page.write_text(expected)
    elif (text != expected or not preview.is_file() or preview.read_text() != data
          or not license_out.is_file() or license_out.read_text() != license_text
          or not project_license_out.is_file() or project_license_out.read_text() != project_license):
        parser.exit(1, 'Dataset preview is stale. Run python3 -I scripts/site/research_preview.py --write\n')
    print('Dataset preview matches the frozen snapshot and catalog: recent entries plus enriched projections; no source code.')


if __name__ == '__main__':
    main()
