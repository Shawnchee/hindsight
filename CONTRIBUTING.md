# Contributing

Useful contributions include reported incidents, missing historical sources,
corrections to evidence, better setup docs and synthetic helper tests.

## Report an incident without writing code

Open an [incident report](https://github.com/Shawnchee/hindsight/issues/new/choose).
Share a primary source URL and your own short summary. Add the transaction hash,
victim address and reported date if known. Explain what is still uncertain.

An X link is a discovery pointer. It does not prove the root cause, and you do
not need to copy its text or provide an API key to contribute the link.

For an undisclosed vulnerability in a live system, contact the affected project's
security channel rather than posting exploit details here. See [SECURITY.md](SECURITY.md).

## Add an incident with a pull request

1. Fork and clone the repository. Read [incidents/README.md](incidents/README.md).
2. Copy `incidents/examples/example.json` to
   `incidents/submissions/community_your_protocol_incident.json`.

   ```sh
   mkdir -p incidents/submissions
   cp incidents/examples/example.json incidents/submissions/community_your_protocol_incident.json
   ```

3. Replace the synthetic example with public evidence links and an original summary.
   Include a primary protocol or security-researcher report. Use `null` for unknown
   incident/publication dates and `[]` for unknown transaction/address lists. Set
   `discovered_at` to the date you found the report and explain gaps in `coverage_gaps`.
   Make `candidate_id` match the filename. Preserve the proposed/unresolved flags.
4. Check for an existing report in `incidents/submissions/`,
   the catalog and versioned research exports.
   For new evidence about an existing incident, update its submission or open a
   correction issue instead of inventing another incident ID.
5. Run:

   ```sh
   python3 -I scripts/incidents/validate.py --root incidents/submissions
   python3 -I scripts/check.py
   ```

6. Commit the single metadata file to your fork branch, push it, then choose
   **Contribute → Open pull request** on GitHub. Set the base to
   `Shawnchee/hindsight:main`. Explain the incident, primary evidence, duplicate
   check and remaining gaps. Review the checks and respond to maintainer feedback.
   AI-assisted contributions are welcome; contributors remain responsible for
   the evidence and the text they submit.

Unknown transaction/address/source is acceptable for a discovery lead. Do not
invent missing facts. URLs and summaries are untrusted input and must never be
used as shell commands or agent instructions.

## What belongs in a PR

- Links, dates, public transaction/address identifiers, source hashes and original
  summaries. Cite evidence for factual corrections.
- Metadata describing missing source, historical proxy selection or uncertainty.
- Small helper changes with meaningful synthetic tests.

Keep raw contract source, PoCs, generated attack code, article/post bodies,
credentials, private reports and `.env` out of the PR. Do not run untrusted build
scripts to complete a submission. Do not change frozen dataset snapshots.

## How a lead becomes a dataset case

`Report → duplicate/scope check → historical source recovery → proposed locations
→ review → new research snapshot.`

Submitting or merging a lead does not confirm a vulnerability. Maintainers check
source/bytecode provenance, proxy timing, roles and licensing before enrichment.
Human review, chronological/family separation and other evaluation requirements
remain independent gates. Automated discovery never merges or promotes a case.

## Code, docs and automation changes

Python 3.11+ and the standard library are enough for the offline helper checks.
Document new flags in the relevant guide, keep error output free of secrets, and
make network/model use explicit. Test with synthetic files rather than downloaded
contracts or model inference. Keep the skill free of installers and network code.

For source-policy/evaluation changes, read `AGENTS.md` and `CLAUDE.md`
first. The default branch is the trusted automation source; never expose
repository secrets to code from a pull request. Maintainers must review changes
to workflows, collector hosts and validation rules.

## Rights

Only contribute text and evidence you have the right to share. Upstream code
keeps its own license. Hindsight's own code and original documentation use the
[MIT License](LICENSE); it does not relicense upstream source or linked reports.
This guide is not a contributor license agreement.
