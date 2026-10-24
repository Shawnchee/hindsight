"""Project inventory and remediation receipts. Reads text; never executes project code."""
import argparse
from bisect import bisect_left
import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
import re

spec = importlib.util.spec_from_file_location('hindsight_triage', Path(__file__).with_name('triage.py'))
triage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(triage)
SCHEMA = 'hindsight.remediation.v1'
SKIP = triage.BLOCKED | {'node_modules', 'lib', 'vendor', 'out', 'cache', 'artifacts', 'broadcast', '.venv'}


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def safe_file(path, limit=32_000_000):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in [path, *path.parents]) or not path.is_file() or path.stat().st_size > limit:
        raise ValueError('input must be a bounded regular file without symlink ancestors')
    return path


def load(path):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError('duplicate JSON key')
            obj[key] = value
        return obj
    return json.loads(safe_file(path).read_text(), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('non-finite JSON number')))


def mappings(values):
    result = []
    for value in values:
        prefix, sep, dest = value.partition('=')
        if not sep or not prefix or not dest or Path(dest).is_absolute():
            raise ValueError('remapping must be prefix=relative/path/')
        result.append((prefix, dest))
    return result


def inventory(root, remappings=(), max_files=1000, max_bytes=4_000_000, max_entries=20000):
    if root.is_symlink():
        raise ValueError('project root cannot be a symlink')
    root = root.resolve(strict=True)
    if not root.is_dir() or min(max_files, max_bytes, max_entries) < 1:
        raise ValueError('root must be a directory; limits must be positive')
    sources, skipped, total, entries = [], [], 0, 0
    def scan_error(error):
        raise ValueError('inventory directory could not be read') from None
    for current, dirs, names in os.walk(root, followlinks=False, onerror=scan_error):
        entries += len(dirs) + len(names)
        if entries > max_entries:
            raise ValueError('inventory entry limit exceeded; narrow the project root')
        keep = []
        for name in sorted(dirs):
            path = Path(current) / name
            if name.lower() in SKIP or name.startswith('.') or path.is_symlink():
                skipped.append(path.relative_to(root).as_posix())
            else:
                keep.append(name)
        dirs[:] = keep
        for name in sorted(names):
            path = Path(current) / name
            if path.suffix != '.sol' or name.startswith('.') or name.endswith(('.t.sol', '.s.sol')):
                continue
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                skipped.append(relative)
                continue
            path = triage.safe_source(root, relative)
            if not path.is_file():
                raise ValueError('source must be a regular file')
            if len(sources) >= max_files or path.stat().st_size > max_bytes - total:
                raise ValueError('inventory file or byte limit exceeded; narrow the project root')
            raw = path.read_bytes()
            total += len(raw)
            if total > max_bytes:
                raise ValueError('inventory byte limit exceeded')
            text = raw.decode('utf-8')
            # Mask comments AND string literals for lexical hints/declarations.
            masked = triage.LEX.sub(lambda m: re.sub(r'[^\n]', ' ', m[0]), text)
            newlines = [m.start() for m in re.finditer('\n', masked)]
            declarations = [{'kind': m[1], 'name': m[2], 'line': bisect_left(newlines, m.start()) + 1}
                            for m in re.finditer(r'\b(abstract\s+contract|contract|interface|library)\s+([A-Za-z_$][\w$]*)', masked)]
            edges = []
            for value in triage.imports(text):
                resolved, gap = triage.resolve_import(root, relative, value, remappings)
                edges.append({'import': value, 'resolved': resolved, 'gap': gap})
            hints = [{'kind': m[1], 'line': bisect_left(newlines, m.start()) + 1}
                     for m in re.finditer(r'\b(delegatecall|staticcall|call)\s*(?:\{|\()', masked)]
            if len(declarations) + len(hints) + len(edges) > 10000:
                raise ValueError('inventory metadata limit exceeded')
            sources.append({'file': relative, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
                            'declarations': declarations, 'imports': edges, 'lexical_call_hints': hints})
    return {'schema_version': 'hindsight.inventory.v1', 'files': sorted(sources, key=lambda s: s['file']),
            'candidate_targets': sorted(s['file'] for s in sources if any(d['kind'] == 'contract' for d in s['declarations'])),
            'source_bytes': total, 'skipped_paths': sorted(skipped),
            'coverage_gaps': ['Text inventory only: imports are not runtime interactions or deployment evidence.',
                              'Vendor, test, hidden and generated directories are excluded from discovery; selected targets still need dependency preparation.',
                              'Proxy implementations, facets, deployed configuration and cross-contract relationships require reviewer evidence.']}


def review(bundle, report):
    errors = triage.validate_report(report, bundle)
    if errors:
        raise ValueError('invalid review: ' + '; '.join(errors))


def plan(bundle, report):
    review(bundle, report)
    return {'schema_version': SCHEMA, 'before': {'bundle_sha256': digest(bundle), 'report_sha256': digest(report)},
            'after': None, 'scope_change_explanation': '',
            'findings': [{'before_id': f['id'], 'assessment': 'unresolved', 'after_ids': [],
                          'rationale': 'Not reassessed yet.', 'after_evidence': [], 'test_ids': []} for f in report['findings']],
            'tests': []}


def exact(obj, keys, label):
    if not isinstance(obj, dict) or set(obj) != set(keys):
        raise ValueError('invalid ' + label + ' fields')


def strings(value, label):
    if not isinstance(value, list) or any(not triage.nonempty(v) for v in value) or len(value) != len(set(value)):
        raise ValueError('invalid ' + label)
    return value


def evidence(items, bundle, report):
    if not isinstance(items, list):
        raise ValueError('after_evidence must be a list')
    for item in items:
        exact(item, ['file', 'line_start', 'line_end'], 'after evidence')
        if not isinstance(item['file'], str) or item['file'] not in report['reviewed_files']:
            raise ValueError('after evidence must reference reviewed source')
        start, end = item['line_start'], item['line_end']
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= bundle['files'][item['file']]['line_count']:
            raise ValueError('invalid after evidence line range')


def compare(before, before_report, after, after_report, record, record_root):
    review(before, before_report)
    review(after, after_report)
    exact(record, ['schema_version', 'before', 'after', 'scope_change_explanation', 'findings', 'tests'], 'remediation')
    if record['schema_version'] != SCHEMA:
        raise ValueError('invalid remediation schema')
    for label, bundle, report in [('before', before, before_report), ('after', after, after_report)]:
        if record[label] != {'bundle_sha256': digest(bundle), 'report_sha256': digest(report)}:
            raise ValueError(label + ' artifact fingerprint mismatch')
    old, new = before['files'], after['files']
    changes = {'added': sorted(new.keys() - old.keys()), 'deleted': sorted(old.keys() - new.keys()),
               'modified': sorted(p for p in old.keys() & new.keys() if old[p]['sha256'] != new[p]['sha256']),
               'unchanged': sorted(p for p in old.keys() & new.keys() if old[p]['sha256'] == new[p]['sha256'])}
    scope = {'removed_targets': sorted(set(before['targets']) - set(after['targets'])),
             'added_targets': sorted(set(after['targets']) - set(before['targets'])),
             'no_longer_reviewed': sorted(set(before_report['reviewed_files']) - set(after_report['reviewed_files']))}
    explanation = record['scope_change_explanation']
    if not isinstance(explanation, str) or ((changes['deleted'] or any(scope.values())) and not explanation.strip()):
        raise ValueError('scope changes require an explicit explanation')
    tests = record['tests']
    if not isinstance(tests, list):
        raise ValueError('tests must be a list')
    test_ids = set()
    for test in tests:
        exact(test, ['id', 'status', 'environment', 'command', 'checks', 'before_bundle_sha256', 'after_bundle_sha256', 'artifact'], 'test')
        for key in ('id', 'checks'):
            if not triage.nonempty(test[key]):
                raise ValueError('test needs id and checked behavior')
        if test['id'] in test_ids:
            raise ValueError('duplicate test id')
        test_ids.add(test['id'])
        if test['before_bundle_sha256'] != digest(before) or test['after_bundle_sha256'] != digest(after):
            raise ValueError('test snapshot fingerprint mismatch')
        if test['status'] == 'not_run':
            if test['environment'] != 'not_run' or test['artifact'] is not None or not isinstance(test['command'], str):
                raise ValueError('invalid not_run test')
        elif test['status'] in ('passed', 'failed'):
            if test['environment'] != 'disposable_container' or not triage.nonempty(test['command']):
                raise ValueError('test execution must use a disposable container')
            artifact = test['artifact']
            exact(artifact, ['path', 'sha256'], 'test artifact')
            if not isinstance(artifact['path'], str) or Path(artifact['path']).is_absolute() or '..' in Path(artifact['path']).parts or '\\' in artifact['path']:
                raise ValueError('test artifact must be relative to the remediation record')
            relative = Path(artifact['path'])
            if (not relative.parts or relative.parts[0] != 'evidence' or relative.suffix not in {'.log', '.txt', '.json'}
                    or any(p.startswith('.') or p.lower() in triage.BLOCKED or re.search(r'credential|secret|token|password|private.?key', p, re.I) for p in relative.parts)):
                raise ValueError('test artifact must be a non-secret text file under evidence/')
            path = safe_file(record_root / artifact['path'], 10_000_000)
            if not path.is_relative_to(record_root.absolute()) or hashlib.sha256(path.read_bytes()).hexdigest() != artifact['sha256']:
                raise ValueError('test artifact hash mismatch')
        else:
            raise ValueError('invalid test status')
    prior = {f['id']: f for f in before_report['findings']}
    later = {f['id']: f for f in after_report['findings']}
    if not isinstance(record['findings'], list):
        raise ValueError('finding dispositions must be a list')
    seen, mapped = set(), set()
    for item in record['findings']:
        exact(item, ['before_id', 'assessment', 'after_ids', 'rationale', 'after_evidence', 'test_ids'], 'disposition')
        ident = item['before_id']
        if not isinstance(ident, str) or ident not in prior or ident in seen:
            raise ValueError('unknown or duplicate before finding')
        seen.add(ident)
        after_ids = strings(item['after_ids'], 'after_ids')
        if set(after_ids) - later.keys():
            raise ValueError('unknown after finding')
        mapped.update(after_ids)
        if set(strings(item['test_ids'], 'test_ids')) - test_ids:
            raise ValueError('unknown test reference')
        assessment = item['assessment']
        if assessment not in ('proposed', 'addressed_by_review', 'unresolved', 'rejected') or not triage.nonempty(item['rationale']):
            raise ValueError('invalid reviewer assessment')
        evidence(item['after_evidence'], after, after_report)
        if assessment in ('addressed_by_review', 'rejected'):
            if not item['after_evidence']:
                raise ValueError('reviewer conclusion requires after source evidence')
            if any(later[i]['status'] != 'confirmed_invalid' for i in after_ids):
                raise ValueError('an active or unresolved mapped finding cannot be marked addressed/rejected')
        if assessment == 'addressed_by_review':
            evidence_files = {e['file'] for e in item['after_evidence']}
            if not evidence_files.intersection(changes['added'] + changes['modified']):
                raise ValueError('addressed assessment needs evidence in changed source')
            if prior[ident]['status'] == 'confirmed_invalid':
                raise ValueError('a disproven original finding is not a fix')
    if seen != prior.keys():
        raise ValueError('every original finding needs exactly one disposition')
    return {'schema_version': 'hindsight.comparison.v1', 'before': record['before'], 'after': record['after'],
            'before_findings': before_report['findings'], 'after_findings': after_report['findings'],
            'file_changes': changes, 'scope_changes': scope, 'scope_change_explanation': explanation,
            'before_coverage_gaps': before_report['coverage_gaps'], 'after_coverage_gaps': after_report['coverage_gaps'],
            'unmapped_after_findings': sorted(later.keys() - mapped), 'findings': record['findings'], 'tests': tests,
            'verification': 'Fingerprints, references and supplied artifact hashes checked. Reviewer assessments and supplied test outcomes are not independently verified; no security conclusion is certified.',
            'remediation_sha256': digest(record)}


def markdown(result):
    def text(value):
        escaped = re.sub(r'([\\`*_{}\[\]()#+.!|>~-])', r'\\\1', html.escape(str(value)))
        return escaped.replace('\n', ' ').replace('\r', ' ')
    lines = ['# Hindsight before/after review', '', result['verification'], '', '## Source changes', '']
    for kind, paths in result['file_changes'].items():
        lines.append(f'- {kind}: {len(paths)} file(s)')
    prior = {f['id']: f for f in result['before_findings']}
    lines += ['', '## Original findings', '', '| Finding | Severity / original status | Reviewer assessment and rationale |', '|---|---|---|']
    for item in result['findings']:
        original = prior[item['before_id']]
        lines.append(f"| {text(item['before_id'] + ': ' + original['title'])} | {text(original['severity'] + ' / ' + original['status'])} | {text(item['assessment'] + ': ' + item['rationale'])} |")
    lines += ['', '## After-review findings', '']
    for status in ('confirmed_valid', 'unresolved', 'confirmed_invalid'):
        lines.append(f"- {text(status)}: {sum(f['status'] == status for f in result['after_findings'])}")
    for finding in result['after_findings']:
        lines.append('- ' + text(f"{finding['id']}: {finding['severity']} / {finding['status']} — {finding['title']}"))
    lines += ['', '## Remaining coverage gaps', '']
    lines += ['- ' + text(gap) for gap in result['after_coverage_gaps']] or ['- None recorded; this is not proof of safety.']
    lines += ['', '## Scope changes', '', text(result['scope_change_explanation'] or 'No source/target/review scope reduction recorded.')]
    lines += ['', '## Test evidence', '', 'Supplied outcomes; commands are recorded, never executed by this helper.', '']
    lines += ['- ' + text(t['id']) + ': ' + text(t['status']) for t in result['tests']] or ['- No test evidence supplied.']
    lines += ['', 'After findings without an original mapping: ' + text(', '.join(result['unmapped_after_findings']) or 'none'),
              '', 'See comparison.json for exact file changes, evidence, fingerprints and finding rationales.']
    return '\n'.join(lines) + '\n'


def write_new(out, name, obj, md=None):
    # Reject symlink parents before creating output; never overwrite snapshots.
    if any(p.is_symlink() for p in [out, *out.absolute().parents]):
        raise ValueError('output symlinks rejected')
    out.mkdir(parents=True, exist_ok=False)
    (out / name).write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')
    if md is not None:
        (out / 'comparison.md').write_text(md)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    inv = sub.add_parser('inventory')
    inv.add_argument('--root', type=Path, required=True)
    inv.add_argument('--remapping', action='append', default=[])
    inv.add_argument('--max-files', type=int, default=1000)
    inv.add_argument('--max-bytes', type=int, default=4_000_000)
    fingerprint = sub.add_parser('fingerprint')
    fingerprint.add_argument('--file', type=Path, required=True, help='bundle, report or remediation JSON')
    for name in ('plan', 'compare'):
        cmd = sub.add_parser(name)
        cmd.add_argument('--before-bundle', type=Path, required=True)
        cmd.add_argument('--before-report', type=Path, required=True)
        if name == 'compare':
            cmd.add_argument('--after-bundle', type=Path, required=True)
            cmd.add_argument('--after-report', type=Path, required=True)
            cmd.add_argument('--record', type=Path, required=True)
    for cmd in (inv, *[sub.choices[n] for n in ('plan', 'compare')]):
        cmd.add_argument('--out', type=Path, required=True, help='new directory; never overwritten')
    args = parser.parse_args()
    try:
        if args.command == 'fingerprint':
            obj = load(args.file)
            if not isinstance(obj, dict) or obj.get('schema_version') not in {'hindsight.bundle.v1', triage.SCHEMA, SCHEMA}:
                raise ValueError('fingerprint requires a review artifact')
            print(digest(obj))
        elif args.command == 'inventory':
            result = inventory(args.root, mappings(args.remapping), args.max_files, args.max_bytes)
            write_new(args.out, 'project.json', result)
            print(f"Inventoried {len(result['files'])} source files; target candidates require review.")
        elif args.command == 'plan':
            result = plan(load(args.before_bundle), load(args.before_report))
            write_new(args.out, 'remediation.json', result)
            print('Created unresolved remediation record; no source changed.')
        else:
            result = compare(load(args.before_bundle), load(args.before_report), load(args.after_bundle),
                             load(args.after_report), load(args.record), args.record.absolute().parent)
            write_new(args.out, 'comparison.json', result, markdown(result))
            print('Comparison written; security conclusions and supplied test outcomes are reviewer assessments.')
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        # Avoid exposing file contents or arbitrary source/JSON text in errors.
        parser.exit(1, 'Workflow failed: ' + (str(error) if isinstance(error, ValueError) and not isinstance(error, (json.JSONDecodeError, UnicodeError)) else 'invalid or unreadable input') + '\n')


if __name__ == '__main__':
    main()
