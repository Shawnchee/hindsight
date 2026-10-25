# Discovery setup

RSS and optional Serper search collect unverified source-document leads. The daily job
saves them automatically as proposed metadata; no eligibility promotion occurs.

## Use RSS locally

```sh
python3 -I scripts/incidents/collect.py
python3 -I scripts/incidents/collect.py --execute \
  --source google-news-ethereum --source openzeppelin
python3 -I scripts/incidents/health.py --root incidents/discovery
```

The first command is an offline plan. The second explicitly makes bounded feed
requests. Status records failures and limits; it cannot guarantee complete coverage.

## Optional Serper

Provide `SERPER_API_KEY` through your environment or secret manager, never as a
CLI argument. The collector does not read `.env`.

```sh
python3 -I scripts/incidents/collect.py --execute \
  --source serper-news --source serper-x-links --max-items 10 --days 7 \
  --status-out incidents/discovery/serper-status.json
python3 -I scripts/incidents/health.py --root incidents/discovery --include-serper
```

Serper searches news and indexed public X links. No direct X requests or browser
scraping occurs. Copied post/article bodies are not retained. Unknown publication
dates stay null; observation time is not earliest disclosure.

## GitHub schedule

The workflow runs daily at **09:17 Malaysia time (01:17 UTC)** and commits
validated discovery metadata directly to the default branch. **No PR review is
needed.** Existing leads are preserved and URLs are deduplicated.

Free RSS collection needs no API key. Optional Serper uses repository secret
`SERPER_API_KEY` and variable `ENABLE_SERPER_DISCOVERY=true`. The workflow needs
contents-write permission, but no pull-request permission. Branch protection
still applies. Schedules can be delayed or disabled by GitHub; health allows
36 hours between successful attempts.

Automatic collection adds unverified reports, not confirmed vulnerabilities.
Frozen research exports remain unchanged. AI compilation needs a separately
configured model; the collector currently performs no AI calls.

See the complete [operations guide](https://github.com/Shawnchee/hindsight/blob/main/docs/incident-discovery.md)
for request limits, queue preservation, health, token behavior and failure handling.
