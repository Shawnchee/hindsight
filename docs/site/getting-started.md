# Get started

## Give your agent the link

Paste this into an AI coding agent that can access URLs and your local project.
The agent handles obtaining the Hindsight files; cloning manually is optional.
Python 3.11+ is required for source preparation and report validation.

```text
Use https://github.com/Shawnchee/hindsight to review my Solidity project at /absolute/path/to/my-project.
Read AGENTS.md, skills/hindsight-triage/SKILL.md and its report reference. Obtain the needed Hindsight files in a separate local tools folder if your environment supports it; handle that setup for me. If the link is inaccessible, say so and ask for an accessible local copy.
Confirm the target chain and contracts. Hindsight currently supports Ethereum mainnet + Solidity. Prepare source and dependencies, perform a code-only review, then write and validate a report if local execution is available. Otherwise label the result as an instruction-guided review without helper validation.
Explain supported findings with cause, impact, file/line evidence and proposed fixes. State missing sources, unavailable analysis and remaining uncertainty. Do not infer safety from no findings.
Review first; do not edit or deploy my project. Never read secrets or run untrusted project scripts on the host. Do not install dependencies or download models.
```

Replace the project path. An agent that only reads web pages can offer an
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
