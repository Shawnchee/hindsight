# Review a project

The source helper reads Solidity as text. It does not execute project code,
install dependencies or call a model.

## Identify the scope

```sh
python3 -I skills/hindsight-triage/scripts/workflow.py inventory \
  --root /absolute/project --out /absolute/new-inventory
```

Inspect `project.json`, then select the deployed targets and interacting contracts.
Import edges and lexical call hints are not a runtime call graph. Proxies need
implementation/facet evidence; missing deployment state stays a coverage gap.

## Prepare source

```sh
python3 -I skills/hindsight-triage/scripts/triage.py prepare \
  --root /absolute/project --target src/Vault.sol \
  --out /absolute/new-review
```

Repeat `--target` for interacting files. Use explicit import mappings when needed:

```sh
--remapping '@openzeppelin/=node_modules/@openzeppelin/'
```

Give the agent `bundle.json` and the skill instructions. Existing Slither JSON
can be supplied with `--slither /absolute/slither.json`; no analyzer is required.
The agent should trace reachability, state changes and trust boundaries, and
keep supported findings distinct from unresolved or disproven candidates.

## Validate the report

```sh
python3 -I skills/hindsight-triage/scripts/triage.py validate \
  --bundle /absolute/new-review/bundle.json \
  --report /absolute/new-review/report.json
```

Validation checks structure, source hashes, line references and coverage disclosures.
It cannot verify the agent's reasoning. See the [report format](./report-format.md).

Existing output directories are not overwritten. Missing imports, unreviewed
files and unavailable analysis remain explicit. An empty finding list is not
proof of safety.
