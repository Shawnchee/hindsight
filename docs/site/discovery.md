# Discovery setup

RSS and optional Serper search collect unverified source-document leads. Maintainers
review them before incident intake. No automatic merge or eligibility promotion occurs.

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

The workflow checks daily at **09:17 Malaysia time (01:17 UTC)** and opens or
updates one draft review PR. It preserves unmerged leads and deduplicates URLs.
It starts only after publication on the default branch and enabling Actions.
Optional Serper uses repository secret `SERPER_API_KEY` and variable
`ENABLE_SERPER_DISCOVERY=true`. Schedules can be delayed or disabled by GitHub.

Enable **Allow GitHub Actions to create and approve pull requests** in repository
Actions settings; this workflow only creates draft PRs and never approves or
merges them. Without Serper configuration, free RSS collection still runs.
Health allows 36 hours between successful attempts to accommodate daily scheduling.

See the complete [operations guide](https://github.com/Shawnchee/hindsight/blob/main/docs/incident-discovery.md)
for request limits, queue preservation, health, token behavior and failure handling.
