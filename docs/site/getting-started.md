# Get started

## Give your agent the link

Paste this into an AI coding agent that can access URLs and your local project.
The agent handles obtaining the Hindsight files; cloning manually is optional.
Python 3.11+ is required for source preparation and report validation.

```text
Review the Solidity contracts in my current codebase using https://github.com/Shawnchee/hindsight.
Identify and preserve this project's root before obtaining any Hindsight files. Keep the toolkit in a separate tools folder; this codebase remains the review target.
Read Hindsight's AGENTS.md, skills/hindsight-triage/SKILL.md and its report reference. If unavailable, say so and ask for an accessible copy.
Confirm the chain and contracts. Use the Ethereum-mainnet/Solidity, code-only workflow. Prepare source and dependencies, then write and validate an evidence-backed report when local execution is available; otherwise disclose that helper validation was not run.
Explain supported findings, impact, file/line evidence and proposed fixes. State missing sources and uncertainty; no findings does not mean safe.
Review only: do not edit or deploy my project, read secrets, run untrusted scripts on the host, install dependencies or download models.
```

Run your agent from the project you want reviewed. An agent that only reads web pages can offer an
instruction-guided source review, but cannot run the helpers or claim report
validation. A repository returning 404 may be private or unavailable: provide
an accessible local copy or authorized access, rather than assuming setup worked.

## Optional manual setup

```sh
git clone https://github.com/Shawnchee/hindsight.git
cd hindsight
python3 -I tests/test_skill.py
```

No extra Python packages or model downloads are needed. Read the skill directly,
or install the entire `skills/hindsight-triage/` folder using your host's process.
A review request leaves your project unchanged. Use the [fix workflow](./remediation.md)
when you want source edits.

## Keep review artifacts private

Store bundles and reports outside the public repository. They can contain source
and sensitive findings. Hosted agents may send the files they read to their provider;
use a local agent if code must remain on your machine.

## Check the tools

```sh
python3 -I scripts/check.py
```

This runs offline synthetic checks and metadata verification. It does not measure
security-detection quality or run a model.
