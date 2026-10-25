# Discovery queue

`leads.jsonl` contains unverified source-document observations, not confirmed
incidents or training examples. `status.json` records the last free-feed attempt;
optional `serper-status.json` records the last enabled Serper news/link searches.

Start with [discovery setup](../../docs/incident-discovery.md). Check the Actions
summary or run `python3 -I scripts/incidents/health.py` to distinguish a recent
attempt from an old file. No schedule is active merely because these files exist.

Follow links to primary evidence before adding an incident submission. Publication
dates, transaction candidates and related-lead links are not adjudicated facts.
The desired scope is Ethereum/Solidity, but each lead's scope remains unresolved.

The initial four rows came from a bounded public RSS smoke check on 2026-10-24
local time. They are discovery pointers only; no article/post text was retained.
A Serper smoke test on the same date added eleven unverified leads (six news
links and five indexed public X links), with null publication dates and no direct
X requests. `serper-status.json` records both successful requests.
Future workflow runs update metadata through a draft PR, never an automatic merge.

The cache is intentionally bounded. If its byte/row/provenance limit is reached,
collection fails visibly rather than dropping history silently. Archive reviewed
leads through an explicit maintainer PR before growing the queue further; keep
the original observation metadata and do not turn archival into label approval.
