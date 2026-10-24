# Hindsight

**Review Solidity with your AI agent. Keep incident evidence traceable.**

Hindsight gives an existing agent a source-review workflow, evidence checks and
a growing research dataset of Ethereum incidents. Start with the skill; no model
download, API key, database or extra Python package is needed for source preparation.

This is an early research tool. It helps an agent investigate possible bugs; it
does not certify a contract as safe or claim better detection than the base model.

## What is Hindsight?

The product is an **agent skill and review toolkit**. The incident catalog and
versioned research datasets are supporting research assets. The current skill
uses code-only review; it does not automatically search past hacks or claim a
measured detection improvement from the dataset.

## Quick start — give your agent the link

Paste this into an AI coding agent that can read URLs and local project files.
You do not need to clone the repository yourself; the agent can obtain the
required instructions and helpers in a separate tools folder.

```text
Use https://github.com/Shawnchee/hindsight to review my Solidity project at /absolute/path/to/my-project.
Read AGENTS.md, skills/hindsight-triage/SKILL.md and its report reference. Obtain the needed Hindsight files in a separate local tools folder if your environment supports it; handle that setup for me. If the link is inaccessible, say so and ask for an accessible local copy.
Confirm the target chain and contracts. Hindsight currently supports Ethereum mainnet + Solidity. Prepare source and dependencies, perform a code-only review, then write and validate a report if local execution is available. Otherwise label the result as an instruction-guided review without helper validation.
Explain supported findings with cause, impact, file/line evidence and proposed fixes. State missing sources, unavailable analysis and remaining uncertainty. Do not infer safety from no findings.
Review first; do not edit or deploy my project. Never read secrets or run untrusted project scripts on the host. Do not install dependencies or download models.
```

Replace the project path. Python 3.11+ is needed to run the helpers. An agent
that can only browse/read text can follow the review instructions, but cannot
claim a helper-validated report. Link-only setup also requires public access to
the repository; a private or unavailable repository needs an accessible local
copy or authorized repository access.

<details>
<summary>Manual setup</summary>

```sh
git clone https://github.com/Shawnchee/hindsight.git
cd hindsight
python3 -I tests/test_skill.py
```

Give the local Hindsight folder and your project path to your agent. A separate
skill manager is optional; preserve the whole skill directory and references.

</details>

**Source privacy follows your agent.** A hosted agent may send the files it reads
to its provider. The helper itself has no inference client or telemetry. Use a
local agent when source must stay on your machine.

## Prepare source yourself

These commands only read source as text. They do not build or execute the contract.

```sh
python3 -I skills/hindsight-triage/scripts/triage.py prepare \
  --root /absolute/path/to/my-project \
  --target src/Vault.sol \
  --out /absolute/path/to/a-new-review-folder
```

Give the resulting `bundle.json` to your agent along with the skill instructions.
It contains the target, reachable imports, source hashes and coverage gaps. If an
import is missing, add an explicit remapping or report the gap. Existing Slither
JSON is optional; Slither and a Solidity compiler are not required for this path.

After the agent writes `report.json`:

```sh
python3 -I skills/hindsight-triage/scripts/triage.py validate \
  --bundle /absolute/path/to/a-new-review-folder/bundle.json \
  --report /absolute/path/to/a-new-review-folder/report.json
```

Validation checks structure and evidence references, not whether a bug is real.
See the [full skill guide](docs/hindsight-skill.md) for remappings, optional Slither
input and report details. Keep bundles/reports containing private source outside Git.

## Review and fix a project with your agent

Point your agent at this repository and paste:

```text
Read AGENTS.md, skills/hindsight-triage/SKILL.md and its remediation reference.
Review my Solidity project at /absolute/path/to/my-project. Inventory its contracts
and dependencies, select the interacting targets, and save a baseline review.
For supported findings, propose focused fixes and regression tests. Make relevant
source/test edits, then review the changed snapshot and produce a before/after
report. Preserve unresolved findings and coverage gaps. Run project checks only
in an available disposable container without credentials and with restricted
networking; otherwise mark them not run. Do not install tools or deploy anything.
```

The agent performs the review and edits. Hindsight supplies a bounded source
inventory and checks that before/after reports refer to the actual snapshots.
The comparison shows changed files, finding assessments, new issues, remaining
coverage gaps and supplied test outcomes. No custom model or discovery API key
is required. A valid report does not prove a fix is correct.

For command examples and the fix-record format, read the
[review and fix workflow](skills/hindsight-triage/references/remediation.md).
It covers Ethereum/Solidity; it is not a general PHP or web-app security scanner.
Runtime reproduction is a separate check. See the [isolated smoke-test plan](docs/runtime-checks.md).
Source review and schema validation do not establish runtime behavior or detection accuracy.

## Add a reported hack

Found a primary post-mortem, security alert or useful X post? Open an
[incident issue](https://github.com/Shawnchee/hindsight/issues/new/choose), or send
a PR with a small metadata record. **You do not need a working exploit.**

Include a link, an original short summary, the reported date, and transaction or
victim identifiers when available. Missing source is a useful coverage gap; do not
invent an address or causal function to complete a record.

Ask an agent:

```text
Read CONTRIBUTING.md and incidents/README.md. Prepare a proposed incident record
for this primary report: <URL>. Check for duplicates. Store links and our own
summary only, leave unknown facts unresolved, and run the offline validator.
Do not generate an exploit, scrape X, or promote the record into a benchmark.
```

The [contribution guide](CONTRIBUTING.md) covers the schema, checks and review path.

## Stay current

The [incident discovery workflow](.github/workflows/incident-discovery.yml) is
configured to check feeds every six hours and open or update a review PR. Serper
can search news and indexed public X links; RSS works without an API key. There
are no direct X API calls or automated X/browser scrapers.

Discovery creates **unverified leads**, not confirmed vulnerabilities. Maintainers
review new reports and recover historical source before creating a new research
snapshot. There is no automatic merge, label approval or training promotion.

Read [freshness setup](docs/incident-discovery.md) to enable the GitHub workflow,
check its last successful run, add feeds or configure Serper. Scheduling starts only
after the workflow is on the default branch and Actions is enabled. Feed/API
coverage is incomplete; no monitor can guarantee it catches every hack.

## Research dataset

[Snapshot v0.2.0](datasets/research/v0.2.0/README.md) contains ten enriched
incidents, nine with proposed defect source, and 55 component metadata snapshots.
Components include proxies and dependencies; they are not 55 vulnerable victims.
Labels are AI proposals, with no human verification or training/evaluation approval.

Exports contain addresses, evidence links, hashes and a source-fetch helper.
Contract source and article/post bodies are not redistributed. Original snapshots
are immutable; new reports arrive through the contribution/discovery queue.

```sh
python3 -I m0/scripts/discovery/export_research.py \
  --verify datasets/research/v0.2.0
```

## For agents and maintainers

The landing page lives in [website/](website/README.md), with searchable
[VitePress documentation](docs/README.md). To preview the complete public site:

```sh
npm ci --prefix docs --ignore-scripts
node scripts/site/build.mjs
python3 -I -m http.server 8766 --bind 127.0.0.1 --directory site-dist
```

Open <http://127.0.0.1:8766/> and `/docs/`. Node 22+ is needed only to build
the website. For a landing-only preview without Node:

```sh
python3 -I -m http.server 8765 --bind 127.0.0.1 --directory website
```

Open <http://127.0.0.1:8765>. The Docs link requires the complete build above.
This previews the page; it does not publish it or
upload source/review artifacts. Hosting remains a separate explicit action.

| Task | Start here |
|---|---|
| Review a Solidity contract | [AGENTS.md](AGENTS.md), then [the skill](skills/hindsight-triage/SKILL.md) |
| Submit an incident | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Set up RSS/Serper discovery | [Discovery setup](docs/incident-discovery.md) |
| Inspect research records | [Dataset index](datasets/research/README.md) |

Run the offline checks with `python3 -I scripts/check.py`. They use synthetic
fixtures and require no model or API credentials. Model benchmark runs and model
downloads are currently paused; ordinary use of the skill with your chosen agent
is a separate workflow.

## Scope and rights

Ethereum mainnet and Solidity only. Detection and triage only; no working attack
transactions, exploit replays, trading or MEV tools. See [security guidance](SECURITY.md).

Hindsight's own code and original documentation use the [MIT License](LICENSE).
Upstream contracts retain their own terms. DeFiHackLabs
catalog provenance is Apache-2.0; see [third-party notices](THIRD_PARTY_NOTICES.md).
