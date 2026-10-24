# Hindsight skill prototype

The first usable delivery is `skills/hindsight-triage/`: a self-contained skill
for the user's existing agent. It packages source preparation, the review workflow
and report validation. It has no inference client, custom weights, network code,
telemetry, or dependency installer. Source and benchmark data are not bundled.

Invoke it in a chat where the skill is available:

> Use $hindsight-triage to review src/Vault.sol in /absolute/project. Use source
> only, and report findings with evidence and unresolved coverage gaps.

Specify interacting target files together. Existing Slither JSON can be supplied;
the skill never runs an untrusted build on the host. If a suitable disposable
container is unavailable, review continues with source only and states that gap.
Nothing is downloaded automatically.

For project-wide reviews and requested fixes, read the skill's
[remediation reference](../skills/hindsight-triage/references/remediation.md).
`workflow.py inventory` maps source candidates/imports; `plan` tracks every
baseline finding; `compare` writes a before/after JSON and Markdown report.
The agent makes scoped edits and supplies test evidence. These helpers never
apply patches or execute project commands. A supplied passing test is supporting
evidence, not an independently verified fix. Use an available disposable container
for project checks or mark them not run. Fingerprints bind both reviews and source
snapshots, and reduced scope/new issues stay visible.

The skill uses whichever model hosts the agent. Installing it does not turn a
hosted agent into an offline/private local model. Use a local host if source must
remain on the machine. No claim of better detection is established yet.

## Deterministic helpers

Source preparation, without any model or analyzer invocation:

```sh
python3 -I skills/hindsight-triage/scripts/triage.py prepare \
  --root /absolute/project --target src/Vault.sol \
  --out /absolute/new-review-folder
```

The new folder contains `bundle.json`: source snapshots with original line
numbers and hashes, targets, import gaps and optional supplied Slither hints.
Only the targets' import closure is included. Remappings are explicit via
`--remapping '@openzeppelin/=node_modules/@openzeppelin/'`; no project config
or build script is executed. Imports that cannot be resolved uniquely remain gaps.
The source byte limit fails explicitly rather than silently trimming code.

After a reviewer writes report.json following the skill's report reference:

```sh
python3 -I skills/hindsight-triage/scripts/triage.py validate \
  --bundle /absolute/review-folder/bundle.json \
  --report /absolute/review-folder/report.json
```

Validation verifies the report's structure, reviewed-source references, line
ranges and coverage disclosures. It does not judge whether a defect is real.
Reports and bundles may contain private source: store them locally and do not
commit or redistribute recovered contract source.

## Installation and checks

The maintained source is in this repository. For a one-off review, point your
agent directly at `skills/hindsight-triage/SKILL.md` and the target contract; no
personal installation is required. To install it permanently, follow your
agent host's skill-installation instructions and copy the entire skill directory,
including its scripts and references. Installing it does not download a model.
Repository changes do not automatically update separately installed copies;
record the repository revision and refresh those copies deliberately.

```sh
python3 -I tests/test_skill.py
python3 -I tests/test_remediation.py
```

The skill-helper tests use synthetic files only. They cover import forms and
closure, ambiguous/missing dependencies, remappings, cycles, path escapes,
symlinks, size limits, Slither success/failure, evidence references, coverage gaps,
and CLI behavior without overwrites. Run all portable offline checks from a fresh
clone with `python3 -I scripts/check.py`. These checks establish mechanics, not
security-detection performance.

As of 2026-10-23, no model-based skill test has run, no custom model was downloaded,
and local-model tests remain on hold. Before evaluating, use the skill's separate
evaluation reference and obtain owner authorization to resume model testing.
The benchmark remains useful for measuring the skill against the same bare model.
