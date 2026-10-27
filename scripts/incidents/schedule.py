"""Decide whether a scheduled catch-up needs collection, using run metadata only."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path


UTC = timezone.utc


def needs_collection(payload, branch, run_id, now=None):
    """Count completed successes started since today's 01:17 UTC daily window.

    Failed, skipped, in-progress, other-branch and previous-day runs cannot
    suppress a catch-up. Unknown/malformed history defaults to collecting.
    """
    now = now or datetime.now(UTC)
    cutoff = now.astimezone(UTC).replace(hour=1, minute=17, second=0, microsecond=0)
    if not isinstance(payload, dict) or not isinstance(payload.get('workflow_runs'), list):
        return True
    for run in payload['workflow_runs']:
        if not isinstance(run, dict):
            continue
        if (str(run.get('id')) == str(run_id) or run.get('head_branch') != branch
                or run.get('event') not in ('schedule', 'workflow_dispatch')
                or run.get('status') != 'completed' or run.get('conclusion') != 'success'):
            continue
        try:
            started = datetime.fromisoformat(run['created_at'].replace('Z', '+00:00'))
            completed = datetime.fromisoformat(run['updated_at'].replace('Z', '+00:00'))
            if started.tzinfo is None or completed.tzinfo is None:
                continue
            if cutoff <= started <= completed <= now:
                return False
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', required=True, type=Path)
    parser.add_argument('--branch', required=True)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    try:
        if args.runs.stat().st_size > 4 * 1024 * 1024:
            raise ValueError('oversized history')
        payload = json.loads(args.runs.read_text())
    except (OSError, ValueError):
        payload = None
    collect = needs_collection(payload, args.branch, args.run_id)
    print('collect=' + str(collect).lower())
    summary = ('No successful refresh since 09:17 Malaysia today; attempting collection.' if collect else
               'A refresh already succeeded since 09:17 Malaysia today; catch-up skipped. '
               'No search or model requests were made by this run.')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as stream:
            stream.write(summary + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
