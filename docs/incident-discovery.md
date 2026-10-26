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
RSS feeds plus optional SerpAPI news/indexed X links, validates the metadata, and
commits only the allowlisted discovery files directly to the default branch.
**No review PR is required.** Existing leads are preserved and matching URLs are
deduplicated. New records stay proposed, unresolved and ineligible for benchmarks.

1. Enable Actions and publish the workflow on the default branch.
2. Run **Actions → Incident discovery → Run workflow** to test it immediately.
3. Inspect the run summary and `incidents/discovery/` for results and source health.
4. For SerpAPI, add `SERPAPI_API_KEY` as a repository Actions secret and set
   `ENABLE_SERPAPI_DISCOVERY=true` as a repository variable.

The workflow needs `contents: write`; it does not request pull-request permission.
Branch protection can block automatic commits. It never bypasses protection or
force-pushes. A concurrent maintainer push makes publication fail visibly; the
next run recollects the rolling time window.

For migration, a previous `codex/incident-discovery` branch is read as untrusted
metadata and merged with the current queue. No code from that branch is executed.
Invalid or oversized metadata blocks publication. Only fixed discovery paths are staged:
`leads.jsonl`, `status.json` and optional `serpapi-status.json` under
`incidents/discovery/`, plus an existing legacy `serper-status.json` if present.
Source failures remain visible, even when successful
sources produce records that can be saved.

This adds **discovery reports**, not verified incidents or changes to frozen
research exports. AI compilation requires a separately configured hosted model;
the RSS/SerpAPI collector itself does not call an AI service. Automated model
summaries must remain labeled proposals and retain their evidence links.

GitHub schedules can be delayed or disabled after public-repository inactivity.
See [GitHub scheduling limits](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Optional SerpAPI search

SerpAPI is the active search provider. It searches Google News and indexed public
X/Twitter links; no direct X requests or browser scraping occurs. Each scheduled
run makes at most two searches (one page per source), retaining at most ten leads
per source. News result groups are flattened with a 100-item scan cap.

Add repository Actions secret **`SERPAPI_API_KEY`** and repository variable
**`ENABLE_SERPAPI_DISCOVERY=true`**. Do not use the old Serper variable/key names.
The existing Serper adapter remains only for legacy configuration and provenance;
the scheduled workflow no longer invokes it.

```sh
python3 -I scripts/incidents/collect.py --execute \
  --source serpapi-news --source serpapi-x-links --max-items 10 --days 7 \
  --status-out incidents/discovery/serpapi-status.json
python3 -I scripts/incidents/health.py --root incidents/discovery --include-serpapi
```

Provide the key through your environment or secret manager. The collector does
not read `.env` or accept keys in command-line arguments. SerpAPI requires a
query-string credential on its fixed HTTPS endpoint; the authenticated URL is
never printed or stored. Proxies and redirects are disabled. Published metadata
keeps only the credential-free endpoint, query, response hash and evidence links.
API errors use fixed codes, never provider response text.

Titles and snippets are screened transiently and discarded. Relative or unknown
publication dates remain null; query date filters do not prove publication time.
No article bodies, post corpora or AI-generated verification are published.
Indexed results can be delayed, incomplete, unrelated or wrong.

On 26 October 2026, a bounded live smoke test returned a successful Google News
response. A separate tiny Gemini 3.1 Flash-Lite request returned the expected
response after one temporary unavailable response. These confirm connectivity,
not incident accuracy. Gemini compilation is not integrated into the workflow.
The optional future Gemini integration needs a separate `GEMINI_API_KEY` secret.

See [SerpAPI Google News documentation](https://serpapi.com/google-news-api).

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
than 36 hours, allowing for a delayed daily run. Add `--include-serpapi` only when SerpAPI monitoring is enabled. No tool can
guarantee an always-current or exhaustive list of hacks.
