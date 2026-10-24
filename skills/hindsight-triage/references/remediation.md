# Project review, fixes and comparison

Use source inventory for a project-wide request. Use remediation only when the
user requests fixes or a revision comparison. The agent performs the reasoning
and source edits; deterministic helpers collect scope and check evidence links.
No helper calls a model, applies a patch, launches a shell command or runs tests.

## Establish scope

```sh
python3 -I <skill-dir>/scripts/workflow.py inventory \
  --root /absolute/project --out /absolute/new-inventory
```

`project.json` lists production Solidity, declarations, candidate contract files,
resolved import edges/gaps and lexical low-level-call hints. Explicit remappings
use `--remapping '@lib/=lib/library/src/'`. Vendor/test/hidden/generated folders
and symlinks are excluded from the scan, and their directory exclusions are
listed. Files in vendor folders can still enter a prepared target's import closure.
Limits: 1,000 source files, 4 MB source, 20,000 scanned directory entries and
10,000 emitted metadata items per source; exceeding a limit or unreadable directory
fails visibly. Narrow the root or deliberately change file/byte limits as needed.
An empty inventory is not evidence that a project is safe.

Select concrete deployment targets and interacting source from this inventory and
configuration read as text. Inspect authorization, inheritance, value/state flows,
callbacks, libraries and trust boundaries across those files. Import edges alone
cannot establish runtime interaction. Proxy/facet implementation, deployment state
and external protocol dependencies require separate evidence. Do not call the
inventory or an import closure a complete deployment architecture.

Use `triage.py prepare` with repeated `--target` arguments for the chosen group,
review it and validate the report as described in SKILL.md. Keep unrelated groups
in separate reviews. Every report states files not reviewed and missing state.

## Preserve a baseline and make focused fixes

Keep `before/bundle.json` and `before/report.json` immutable. Validate the report
before proposing a fix. For supported findings, explain the invariant to preserve,
the focused change, compatibility/storage-layout risks and the regression behavior
to check. For unresolved findings, first obtain evidence; do not invent patches.
A user request to fix authorizes relevant source and test edits, not deployments,
external transactions, dependency installations or unrelated refactors.

Create the tracking record:

```sh
python3 -I <skill-dir>/scripts/workflow.py plan \
  --before-bundle /absolute/before/bundle.json \
  --before-report /absolute/before/report.json \
  --out /absolute/new-fix-plan
```

This writes `remediation.json` with canonical SHA-256 fingerprints of the complete
baseline artifacts, and one unresolved disposition per original finding. It does
not change the project. Make proposed source/test changes through the host agent's
normal file editing tools. New tests should assert the intended invariant and
relevant valid behavior; never create executable attacks against live contracts.

Run trusted, relevant regression checks only in an available disposable container
without credentials and with restricted networking. Bind the mounted source and
test files to recorded hashes. Record the command, environment, checked behavior,
result and evidence artifact. Do not run untrusted project tests/builds on the host.
If a suitable environment is absent, leave tests unexecuted and explain the gap.
Do not install a container runtime, dependencies or model to make a report green.

## Reassess the changed snapshot

Prepare `after/bundle.json` using the same targets/remappings, then review the
changed paths and dependencies and write/validate `after/report.json`. Do not reuse
old Slither results as if they describe changed source. Capture new issues even
if unrelated to the original findings. Keep remaining source/state/test gaps.

Fill `after` in the tracking record with the canonical hashes printed by:

```sh
python3 -I <skill-dir>/scripts/workflow.py fingerprint --file /absolute/after/bundle.json
python3 -I <skill-dir>/scripts/workflow.py fingerprint --file /absolute/after/report.json
```

`after` has `bundle_sha256` and `report_sha256`, just like `before`. These are
canonical JSON fingerprints, not raw-file hashes. Source `sha256` values and test
artifact digests instead hash exact file bytes.

Keep every original finding exactly once in `findings`. Each entry has:

- `before_id`: original report ID, scoped to that report's fingerprint.
- `assessment`: `proposed`, `unresolved`, `addressed_by_review` or `rejected`.
- `after_ids`: IDs of matching candidates in the after report, or `[]`.
- `rationale`: explain the current evidence and remaining assumptions.
- `after_evidence`: reviewed after-source references `{file,line_start,line_end}`.
- `test_ids`: supporting entries from `tests`, or `[]`.

`addressed_by_review` requires evidence in added/modified reviewed source; a
previously disproven finding is not a fix. Both `addressed_by_review` and `rejected`
require after-source evidence and cannot map to a still-active/unresolved after
finding. They remain reviewer assessments. Omission from a report, target removal,
a renamed file or passing tests never automatically establishes remediation.
Changes to targets, deleted source or reduced reviewed-file scope require a
nonempty `scope_change_explanation`; the comparison always displays those changes.
Treat lost coverage as an unresolved risk, not evidence of a successful fix.

## Test evidence contract

`tests` is a list; use `[]` if no test evidence exists. A supplied execution entry:

```json
{
  "id": "T1",
  "status": "passed",
  "environment": "disposable_container",
  "command": "the actual command used, with no credentials",
  "checks": "The invariant and valid behavior checked; identify source/test revision hashes and container provenance.",
  "before_bundle_sha256": "canonical fingerprint of before bundle",
  "after_bundle_sha256": "canonical fingerprint of after bundle",
  "artifact": {"path": "evidence/regression.log", "sha256": "SHA-256 of exact sanitized log bytes"}
}
```

Executed outcomes are `passed` or `failed`. Save only sanitized supporting logs
under `evidence/` beside the remediation record. Paths must stay in that directory,
use `.log`, `.txt` or `.json`, and contain no hidden, credential or symlink path.
The helper hashes artifacts but never copies or renders their contents. It checks
snapshot references, not whether the claimed command actually ran, the test
exercised the defect, or all mounted files matched the snapshot.

For an unexecuted check use `status: "not_run"`, `environment: "not_run"`,
`artifact: null`, `command: ""` (or the proposed command) and explain the reason
and intended behavior in `checks`. Keep both snapshot fingerprints. Missing tests
and supplied test outcomes remain visible; neither creates a security certificate.

## Write the comparison

```sh
python3 -I <skill-dir>/scripts/workflow.py compare \
  --before-bundle /absolute/before/bundle.json \
  --before-report /absolute/before/report.json \
  --after-bundle /absolute/after/bundle.json \
  --after-report /absolute/after/report.json \
  --record /absolute/fix-plan/remediation.json \
  --out /absolute/new-comparison
```

The output is `comparison.json` plus readable `comparison.md`: source changes,
original finding dispositions, current findings, test evidence and coverage gaps.
Existing output directories are never overwritten. Validation checks source
hashes/sizes/line counts, complete artifact fingerprints, ID mappings, evidence
locations and supplied test-log hashes. It does not validate reasoning or certify
security. A valid comparison may contain failed tests and unresolved findings.
Deliver the proposed source diff, regression test changes and comparison together;
state what was changed, what actually ran and what remains uncertain.

All artifacts can contain private code or sensitive findings. Keep them outside
the public repository. Host-agent privacy follows the user's agent provider.
