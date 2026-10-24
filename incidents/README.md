# Contribute a historical incident lead

Add one small JSON file to `incidents/submissions/` in a pull request. Community
intake accepts **Ethereum mainnet + Solidity** discovery leads with public primary
evidence and your own short summaries. A lead is a research pointer, not a
confirmed vulnerability, a human label, or a training/evaluation example.

The current research is separate: [research exports](../datasets/research/README.md),
[current v0.2.0 metadata](../datasets/research/v0.2.0/README.md), and existing
community submissions. Search these before adding
a lead. Versioned exports are frozen; contributions do not edit or regenerate them.

## Add a lead

1. Copy [the synthetic example](examples/example.json) to
   `incidents/submissions/community_your-project-incident.json`. Create the
   submissions directory if this is the first contribution. Set `candidate_id`
   to the matching filename without `.json`; use a stable descriptive slug.
2. Replace the synthetic name, summaries, and evidence URL with a researched
   incident. Add a primary protocol/security-researcher report in `primary_sources`.
   Each source has `url`, `published_date`, and an original `summary`. Use `null`
   for an unknown publication date or incident date. `discovered_at` is when you
   found the lead; it does not establish its earliest public disclosure.
3. Include full, source-reported `tx_hashes` and `victim_addresses` when available.
   An address is a candidate victim, not an attacker, recipient, or replacement
   contract. Do not guess an identifier. Empty arrays are valid for a source-gap
   report with a primary URL, your own summary, and explicit `coverage_gaps`.
4. Describe unresolved source, date, chain, identifier, and root-cause questions
   in `coverage_gaps`. Keep every review and eligibility field at its template
   value. Validate locally, then open a PR with the evidence and remaining gaps:

   ```sh
   python3 -I scripts/incidents/validate.py --root incidents/submissions
   python3 -I tests/test_community_incidents.py
   ```

The validator uses only Python's standard library. No installation, credentials,
models, network requests, or source-code execution are needed. An empty or absent
submissions directory passes. The `examples/` directory is excluded from intake;
`community_example` is rejected if copied unchanged into submissions. Examples
and test fixtures are synthetic and never enter research or train/eval datasets.

## Metadata contract

[The JSON schema](schema.json) documents all required keys and rejects additional
keys. The CLI also enforces file size, filename binding, valid calendar dates,
public URL shape, conservative secret/payload guards, and cross-record duplicate
checks. A schema-only editor check is insufficient.

| Field | Contribution rule |
| --- | --- |
| `schema_version` | `hindsight.community-incident.v1` |
| `candidate_id` | `community_` plus a 3–64 character lowercase slug; match the filename |
| `name`, `summary` | Your own single-line prose, at most 160 / 2,000 characters |
| `chain_id`, `language` | `1`, `Solidity`; deployment and language claims remain unverified |
| `incident_date`, `discovered_at` | ISO `YYYY-MM-DD`; incident date may be `null` |
| `primary_sources` | 1–10 public HTTP(S) links, nullable `published_date`, and own summaries of at most 600 characters |
| `tx_hashes`, `victim_addresses` | At most 50 each; full `0x` + 64 / 40 hex digits; empty if unknown |
| `coverage_gaps` | 1–20 original notes of at most 600 characters each |
| `identifier_verification` | `source_reported_unverified` |
| `source_policy`, `intake_status` | `link_and_own_summary_only`, `discovery_only` |
| `first_seen_at`, `family_id` | `null`; contribution dates and similar mechanisms do not establish either |
| `label_status`, `adjudication`, `split` | `proposed`, `unresolved`, `unassigned` |
| `human_verified`, `training_eligible`, `evaluation_eligible`, `benchmark_promoted` | All `false` |

Each file is at most 32,768 bytes, with one object per `.json` file. Arrays cannot
contain repeated identifiers or primary URLs. Nested files and symlinks are
rejected. Do not include contract source, ABI, bytecode, PoCs, exploit scripts,
article/post bodies, copied write-ups, cached responses, credentials, local file
contents, or paths masquerading as evidence URLs. Link public evidence and write
your own summary. These text guards catch obvious pastes and secret patterns;
they do not prove authorship or detect every possible secret.

Evidence links cannot contain credentials or credential-like query parameters.
Private/reserved IP literals, local hostnames, common local-address wildcard
services, provider RPC endpoints, and nonstandard ports are rejected. Validation
never resolves DNS or fetches a link, so maintainers must still inspect evidence
and redirects using an appropriate safe research process.

## Duplicates and review

The CLI checks candidate IDs, case-insensitive transaction hashes, and canonical
primary URLs against other submissions and fixed existing discovery/export
metadata and the catalog's transaction identifiers. URL comparisons ignore
scheme, `www`, fragment, trailing slash, common tracking parameters, and query
order. This is a conservative pointer check: two separate incidents cited by the
same report require maintainer review instead of bypassing the duplicate gate.
Address reuse alone does not identify an incident, so addresses do not trigger
cross-record duplicate failures. Name aliases, missing identifiers, novel report
URLs, and corpus metadata outside the checked files still need manual review.

When a duplicate is found, update the existing community lead or describe the
correction/source gap in a PR or issue pointing to the existing research record.
Do not create another incident ID to evade a match or edit frozen exports.

A passing check means the metadata is shaped correctly. Maintainers still need
to verify incident scope and identifiers, recover exact historical source,
review source rights, establish documentary `first_seen_at` and exploit-family
boundaries, and obtain human adjudication before any separate promotion.
Community PRs cannot supply that approval by changing flags. The data-source
rules remain [agent source policy](../AGENTS.md), including link/own-summary
handling and no X scraping. No repository or upstream license is established by
submitting a record; source rights remain a review question.
