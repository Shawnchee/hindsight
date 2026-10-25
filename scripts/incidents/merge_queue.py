"""Preserve validated legacy bot-branch leads without executing branch code."""
import argparse
import importlib.util
import json
from pathlib import Path


spec = importlib.util.spec_from_file_location('collector', Path(__file__).with_name('collect.py'))
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


def merge(previous, output):
    old = collector.read_cache(previous)
    current = collector.read_cache(output) if output.exists() else []
    if any(path.is_symlink() for path in (output, *output.parents)):
        raise ValueError('unsafe_cache_path')
    records = collector.merge_leads(current, old)
    payload = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in records)
    if (len(records) > collector.CACHE_MAX_ROWS or len(payload.encode()) > collector.CACHE_MAX_BYTES
            or any(len(line.encode()) + 1 > collector.CACHE_MAX_ROW_BYTES for line in payload.splitlines())):
        raise ValueError('merged_cache_limit_exceeded')
    for row in records:
        collector.validate_lead(row)
    output.write_text(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=Path('incidents/discovery/leads.jsonl'))
    args = parser.parse_args()
    try:
        merge(args.previous, args.out)
    except (OSError, ValueError):
        parser.exit(1, 'Cannot preserve previous leads: invalid or oversized discovery metadata.\n')


if __name__ == '__main__':
    main()
