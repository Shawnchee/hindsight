# Hindsight research snapshot v0.2.0

Recorded 2026-10-24. This offline metadata-only snapshot combines the original
intakes with explicit recovery supplements. It has 10 incidents,
9
with proposed defect source, and 55 component snapshots.
Component counts are not counts of vulnerable contracts. Older v0.1.0 is unchanged.

All findings are AI-proposed/unresolved; human verification and training/evaluation
eligibility remain false. No benchmark promotion or model test is implied.
Recovery summaries and current gaps are separate from historical intake gaps;
May xToken includes distinct xBNT and xSNXa proposals within one incident.
bZx remains a source gap. Complete incident coverage and exact transaction
execution remain unproved even where source has been recovered.

Publication dates are observations, not established earliest disclosures.
first_seen_at and family_id remain null and splits unassigned. Provisional cohorts
are not confirmed exploit families. Source availability at incident time and
distribution rights still need review. Do not use this as a sealed benchmark or
training set. Research supplements do not modify the separate post-cutoff pool.

Source is distributed as addresses and hashes only. `fetch_source.py` is the same
bounded single-contract fetch helper as v0.1.0. Run it offline first:
`python3 -I fetch_source.py --address 0x833e440332caa07597a5116fbb6163f0e15f743d`.
Only an explicit `--execute --out /absolute/new-gitignored-directory` fetches source;
it checks hashes and never builds or executes source. Provider changes can cause
reproduction to fail; do not substitute changed source silently.

manifest.json pins payloads; input_hashes.json pins repository metadata inputs.
Verify using `python3 -I m0/scripts/discovery/export_research.py --verify PATH`.
Changed input requires a new version/directory. No article/post bodies, contract
source or credentials are shipped. Own distribution license remains unselected;
flattened SPDX mentions do not grant blanket source permissions. DeFiHackLabs
catalog attribution: Apache-2.0, commit23c7bd8; retain LICENSE/NOTICE obligations.
This export is local; it has not been published, committed or pushed.
