# Keep incident discovery current

The collector checks public signals and queues source-document leads for review.
It does not identify confirmed bugs, label source or automatically update a
benchmark. A report might be about another chain, repeat an older incident or
contain incorrect early claims.

## Try it locally

Python 3.11+ and the standard library are enough. No model or database is needed.

```sh
# Offline plan: no requests, keys or writes.
python3 -I scripts/incidents/collect.py

# Explicit bounded public RSS reads. No API key required.
python3 -I scripts/incidents/collect.py --execute \
  --source google-news-ethereum --source openzeppelin

# Offline cache validation and latest-attempt health.
python3 -I scripts/incidents/collect.py --validate-cache incidents/discovery/leads.jsonl
python3 -I scripts/incidents/health.py --root incidents/discovery
```

The default outputs are `incidents/discovery/leads.jsonl` and `status.json`.
RSS/Atom bodies are parsed transiently, never stored as a text corpus. Each lead
keeps a URL, publication observation, collection observation, response hash and
an original generic discovery summary. Google News URLs can remain redirect
wrappers; follow the link manually to find primary evidence before enrichment.
The OpenZeppelin feed can yield no matching recent incidents; that is not a failure.

One request per selected source; defaults are14 days,30 matching leads,15-second
timeout and1MiB response cap. There is no retry loop or pagination. Capped,
undated, excluded and failed-source counts appear in status. Failures return a
nonzero exit while preserving successful leads and recording source failures.
An invalid existing cache fails before network or mutation.

The queue is capped at16MiB,10,000 rows,256KiB per row and128 provenance versions
per document. Reaching a limit fails visibly. Maintainers should archive reviewed
old leads through a separate PR while preserving their original observation
metadata; the collector never silently discards history to keep running.

Existing documents merge by canonical URL. Shared transaction candidates only
create related-lead links: a roundup can mention multiple incidents, so they do
not prove incident identity. `observed_at` is first observation by this collector,
not earliest public disclosure; `first_seen_at` stays null. `target_scope` is the
desired filter, while `scope_status` remains unresolved until independently checked.

## Automatic daily ingestion

The workflow runs daily at **09:17 Malaysia time (01:17 UTC)**. It collects free
RSS feeds plus optional Serper news/indexed X links, validates the metadata, and
commits only the allowlisted discovery files directly to the default branch.
**No review PR is required.** Existing leads are preserved and matching URLs are
deduplicated. New records stay proposed, unresolved and ineligible for benchmarks.

1. Enable Actions and publish the workflow on the default branch.
2. Run **Actions → Incident discovery → Run workflow** to test it immediately.
3. Inspect the run summary and `incidents/discovery/` for results and source health.
4. For Serper, add `SERPER_API_KEY` as a repository Actions secret and set
   `ENABLE_SERPER_DISCOVERY=true` as a repository variable.

The workflow needs `contents: write`; it does not request pull-request permission.
Branch protection can block automatic commits. It never bypasses protection or
force-pushes. A concurrent maintainer push makes publication fail visibly; the
next run recollects the rolling time window.

For migration, a previous `codex/incident-discovery` branch is read as untrusted
metadata and merged with the current queue. No code from that branch is executed.
Invalid or oversized metadata blocks publication. Three fixed paths are staged:
`leads.jsonl`, `status.json` and optional `serper-status.json` under
`incidents/discovery/`. Source failures remain visible, even when successful
sources produce records that can be saved.

This adds **discovery reports**, not verified incidents or changes to frozen
research exports. AI compilation requires a separately configured hosted model;
the RSS/Serper collector itself does not call an AI service. Automated model
summaries must remain labeled proposals and retain their evidence links.

GitHub schedules can be delayed or disabled after public-repository inactivity.
See [GitHub scheduling limits](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Optional Serper search

Serper searches news and indexed public X/Twitter links. The collector never
requests X directly and does not run a browser scraper. Search results are
pointers to investigate; prefer original protocol notices and technical reports.

For GitHub Actions:

- Add repository secret **`SERPER_API_KEY`** from your Serper account.
- Set repository variable **`ENABLE_SERPER_DISCOVERY`** to **`true`**.
- Review the queries in `config/incidents/feeds.json` and your API allowance.
  The scheduled run makes at most two Serper requests per day, requesting
  ten results each: one news search and one indexed public-link search.

Locally, provide the key through your environment/secret manager, then run:

```sh
python3 -I scripts/incidents/collect.py --execute \
  --source serper-news --source serper-x-links --max-items 10 --days 7 \
  --status-out incidents/discovery/serper-status.json
python3 -I scripts/incidents/health.py --root incidents/discovery --include-serper
```

Do not put the key in a CLI argument, feed config, issue, PR or committed `.env`.
The collector does not read `.env`. Credential-bearing requests use fixed
`google.serper.dev` endpoints with proxies and redirects disabled. Result text
is parsed transiently and discarded; stored summaries are original generic
observations. Missing keys or refused requests fail visibly.

Search date filters do not prove when a report was published. Relative or unknown
publication dates remain null; observation timestamps are recorded separately.
Indexing delays, result limits and missing/deleted/private posts leave coverage
gaps. See [Serper](https://serper.dev/) for access and account allowances.
Authenticated smoke test on 2026-10-24 succeeded for both endpoints: one request
each, ten results examined per source, yielding six news leads and five indexed
public X links. These remain unverified; all returned dates lacked a precise
publication timestamp and were stored as null. Credentials were used only in
process memory, never written to metadata or configuration.

## Add a feed or contribute a lead

Feed endpoints live in `config/incidents/feeds.json` and the collector's explicit
endpoint allowlist. A new feed needs a working public RSS/Atom URL, permitted
source policy, a small fixture test and a PR updating both places. Do not replace
X with an unofficial RSS bridge. Verify dates and source terms; never import a
publisher's article archive as training text.

To investigate a lead, follow its public URL, find original evidence, check for
duplicates and use [CONTRIBUTING.md](../CONTRIBUTING.md). A community submission
is an incident proposal; a feed row is a document observation. They are different
levels, so sharing a feed URL does not automatically prove a duplicate incident.
Historical source recovery, rights, timing, family separation and review still
precede any eligibility decision.

Source failures and stale attempts appear in the health command/Actions summary.
Default health is unhealthy when either free feed is missing, failed or older
than 36 hours, allowing for a delayed daily run. Add `--include-serper` only when Serper monitoring is enabled. No tool can
guarantee an always-current or exhaustive list of hacks.
