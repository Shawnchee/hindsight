"""Report source-attempt freshness without fetching content or reading secrets."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path


UTC = timezone.utc


def assess(root, include_serper=False, max_age_hours=36, now=None):
    now = now or datetime.now(UTC)
    expected = [("status.json", ("google-news-ethereum", "openzeppelin"))]
    if include_serper:
        expected.append(("serper-status.json", ("serper-news", "serper-x-links")))
    rows, healthy = [], True
    for filename, ids in expected:
        path = root / filename
        try:
            if root.is_symlink() or path.is_symlink() or path.stat().st_size > 131072:
                raise ValueError("invalid_status")
            status = json.loads(path.read_text())
            states = {s["source_id"]: s for s in status["sources"]}
        except (OSError, ValueError, TypeError, KeyError):
            states = {}
        for sid in ids:
            state = states.get(sid, {})
            try:
                observed = datetime.fromisoformat(state["observed_at"].replace("Z", "+00:00"))
                if observed.tzinfo is None:
                    raise ValueError("missing_timezone")
                age = now - observed
                recent = -timedelta(minutes=5) <= age <= timedelta(hours=max_age_hours)
                result = "ok" if state.get("status") == "ok" and recent else "failed or stale"
                timestamp = observed.astimezone(UTC).isoformat().replace("+00:00", "Z")
            except (ValueError, TypeError, KeyError, AttributeError):
                result, timestamp = "not checked", "unknown"
            count = state.get("lead_count")
            count = str(count) if type(count) is int and count >= 0 else "unknown"
            bounded = any(state.get(k) is True for k in ("capped", "scan_capped", "page_capped"))
            rows.append((sid, result, timestamp, count, "yes" if bounded else "no"))
            healthy = healthy and result == "ok"
    lines = ["## Incident discovery health", "", "| Source | Latest attempt | UTC | Leads in response | Capped |",
             "|---|---|---|---|---|"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    lines += ["", "These timestamps describe bounded collection attempts, not incident verification or complete coverage.",
              "Publication dates and first observations do not establish earliest disclosure. Serper is optional; no direct X requests are made."]
    return "\n".join(lines) + "\n", healthy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("incidents/discovery"))
    parser.add_argument("--include-serper", action="store_true")
    parser.add_argument("--max-age-hours", type=int, default=36)
    parser.add_argument("--github-summary", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.max_age_hours <= 168:
        parser.error("max age must be 1..168 hours")
    text, healthy = assess(args.root, args.include_serper, args.max_age_hours)
    print(text)
    if args.github_summary and os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as stream:
            stream.write(text)
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
