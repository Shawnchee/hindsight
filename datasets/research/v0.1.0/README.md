# Hindsight research snapshot v0.1.0

Local metadata-only research export, recorded 2026-10-23. It contains 10
enriched incident records, 8
with proposed defect source and two source gaps, plus 31 contract
snapshots / 56 source-unit hashes.
Contract source and article/post bodies are not redistributed.

All labels remain AI-proposed/unresolved, with zero human approvals or training,
evaluation and benchmark eligibility. This is not a benchmark or a training-ready
dataset. `review_summaries.jsonl` records requested Astra low-effort reviews;
`label_events.jsonl` records the expansion's revisions. Earlier intake review
provenance is represented by its review report hash, not a fabricated edit log.

`disclosures.jsonl` contains ten directly inspected primary-page publication dates.
They are date-granularity observations, not proven earliest disclosures or UTC
timestamps; `first_seen_at` stays null. Source availability at incident time also
remains unproved. `families.proposed.json` has nine provisional split-blocking
groups: each incident stays together, and both xToken incidents share a conservative
protocol cohort. It does not claim one exploit family or complete clone clearance.
Shared libraries/wrappers and cited-span hashes are reported separately.

Historical code comparisons establish code at the recorded prior blocks. They
do not establish exact transaction prestate, complete economic context or a replay.
The source-backed May xToken proposal covers xBNT only; its xSNXa branch is missing.
bZx's primary module and August xToken's exact victim/source remain gaps.

## Reproduce one contract's source

Run from this directory. Dry-run first (offline):

```sh
python3 -I fetch_source.py --address 0x833e440332caa07597a5116fbb6163f0e15f743d
```

For one explicitly selected contract, add `--execute --out /absolute/new-local-directory`.
The helper makes one bounded Sourcify request, checks all source hashes and runtime
hash against this snapshot, and never builds/executes code or accesses credentials.
Use a gitignored output directory. It never loops over the snapshot: respect
Sourcify's single-contract fair-use policy. Provider changes can make reproduction
fail; do not silently substitute updated sources. No RPC URL or key is shipped.

## Integrity, provenance and rights

`manifest.json` hashes every payload file. `input_hashes.json` pins source metadata
and review inputs in the repository. To verify locally from the Hindsight project:
`python3 -I m0/scripts/discovery/export_research.py --verify /absolute/snapshot-directory`.
Regenerate using that script's `--out` and the same version; changed inputs require
a new snapshot directory. Existing differing snapshots are never overwritten.

This export was not published, committed or pushed. Hindsight's own distribution
license is still unselected. Upstream contract rights remain separate; SPDX mentions
can apply only to flattened dependencies and are not blanket release permissions.
DeFiHackLabs catalog provenance: Apache-2.0, upstream commit 23c7bd8; retain its
LICENSE/NOTICE obligations when distributing derived catalog material. New intake
summaries are our own, with original protocol/researcher URLs retained in each row.
Browser leads are discovery-only, with two new candidates and two catalog references.
