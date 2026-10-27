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

The workflow targets **09:17 Malaysia time (01:17 UTC)**, with catch-up triggers
at **12:17 and 18:17 Malaysia time (04:17 and 10:17 UTC)**. A read-only freshness
job checks this workflow's last 100 runs. A completed successful scheduled or
manual run on the default branch, started since today's 01:17 UTC, suppresses
later scheduled collection. Failed, skipped, running, other-branch and previous-day
runs do not suppress it. Manual dispatch always collects. Unavailable or invalid
run history defaults to collection, so a status API outage cannot silently skip
the refresh. Each run's summary explains the decision.

Collection fetches free
RSS feeds plus optional SerpAPI news/indexed X links, validates the metadata, and
commits only the allowlisted discovery files directly to the default branch.
**No review PR is required.** Existing leads are preserved and matching URLs are
deduplicated. New records stay proposed, unresolved and ineligible for benchmarks.

1. Enable Actions and publish the workflow on the default branch.
2. Run **Actions → Incident discovery → Run workflow** to test it immediately.
3. Inspect the run summary and `incidents/discovery/` for results and source health.
4. For SerpAPI, add `SERPAPI_API_KEY` as a repository Actions secret and set
   `ENABLE_SERPAPI_DISCOVERY=true` as a repository variable.

The freshness job needs only `contents: read` and `actions: read`. Collection
needs `contents: write`; neither job requests pull-request permission.
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

## Catalog and Gemini compilation

DeFiHackLabs is checked at a commit-specific revision: one GitHub revision
request, one README request, and at most eight Solidity metadata files (128 KiB
each). Only the 30 most recent dated README entries are considered per run.
Fetched files are untrusted text, never executed or redistributed.

The immutable 357-row CSV remains the historical baseline. Additions go into
`datasets/catalog/current.json`, a Git-tracked operational overlay. The combined
public feed is `website/data/catalog.json`. Counts mean **reported incidents**,
not human-verified hacks. Frozen research versions never change.

A new counted entry requires explicit Ethereum mainnet scope, an Etherscan
attack/profit transaction, a named victim contract and an upstream reference.
Conflicting chain metadata, missing evidence, reused protocol/date with uncertain
identity, roundups and multiple matches stay pending. Exact upstream paths match
baseline records; compatible shared transactions/victims can match another source
to an existing incident. News alone never increments catalog counts. Related
news transaction matches are possible evidence links, not independent verification.
These rules reduce false positives; they cannot guarantee none. Baseline
classifications also remain provisional.

`GEMINI_API_KEY` enables at most **one Gemini 3.5 Flash-Lite request per run**, over
up to ten changed licensed upstream claims. No new input means zero requests.
The default model is `gemini-3.5-flash-lite`; optional repository variable
`GEMINI_MODEL` can pin `gemini-3.1-flash-lite`. There are no retries or model fallbacks; output is capped at 4096 tokens.
Only public metadata is sent, never project source, article bodies or direct X
content. Output IDs must match inputs; support quotes must occur in the supplied
claim. AI cannot add members, change chains, merge incidents, set losses or approve
labels. Failures and token usage are recorded in
`incidents/discovery/ai-summaries.json`; previous summaries remain available.
Check `last_attempt`, not just workflow success. Valid schema and a supporting
quote do not establish factual correctness.

```sh
# Offline, no provider request or writes.
python3 -I scripts/incidents/catalog.py --check
# Explicit upstream refresh and optional single Gemini batch.
python3 -I scripts/incidents/catalog.py --execute --gemini --write-public
python3 -I scripts/site/research_preview.py --write
```

## Website and agent updates

Daily ingestion regenerates total/year counts, examples and the coverage chart
from the combined catalog, builds VitePress and validates the public site before
committing fixed generated paths. The five loss examples remain selected source
claims; no misleading aggregate loss total is calculated.

Cloudflare deployment stays off until repository variable `CLOUDFLARE_ACCOUNT_ID`
and secret `CLOUDFLARE_API_TOKEN` (Pages Edit on the project account) exist. Then
the workflow uploads **only `site-dist/`** to `hindsight-solidity` using pinned
Wrangler. GitHub data updates work without hosting credentials. No token is
published. See [Cloudflare's CI guide](https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/).

The [read-only MCP server](site/mcp.md) can read the live public GitHub catalog,
independently of Cloudflare. Local copies require `git pull`. Connecting MCP does
not force an agent to use it or demonstrate detection accuracy.

GitHub schedules can be delayed, dropped or disabled after public-repository
inactivity. Catch-ups reduce missed days but use the same scheduler and cannot
guarantee delivery. If no run appears, there is no collector log to inspect: check
that Actions and the default-branch workflow are enabled, then dispatch a manual
run. A passing manual run verifies execution, not future schedule delivery.
See [GitHub scheduling limits](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Optional SerpAPI search

SerpAPI is the active search provider. It searches Google News and indexed public
X/Twitter links; no direct X requests or browser scraping occurs. Each scheduled
run makes at most two searches (one page per source), retaining at most ten leads
per source. News result groups are flattened with a 100-item scan cap.
Successful daily collection makes later catch-ups free of search/model requests.
If all three scheduled attempts are needed, the bound is six searches and three
Gemini requests per day; unchanged claims still require no Gemini request.

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
not incident accuracy. Gemini compilation uses the separate `GEMINI_API_KEY` repository secret.

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
