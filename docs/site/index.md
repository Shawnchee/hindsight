# Hindsight documentation

Hindsight gives your existing AI coding agent a workflow for reviewing Solidity,
proposing fixes, and keeping the source evidence behind each change.

[Get started →](./getting-started.md)

## What you can do

- [Review a project](./review.md): prepare contracts and imports, then write a report.
- [Fix and compare](./remediation.md): preserve a baseline and track proposed changes.
- [Add an incident](./contributing.md): contribute public evidence through an issue or PR.

Ethereum mainnet and Solidity are the current scope. The helper tools need
Python 3.11+; reviews do not require a custom model, discovery key or database.

## What the tooling checks

Source snapshots, report structure, evidence references and comparison artifacts.
The agent supplies the reasoning. These checks do not establish that a bug is real,
a fix is correct or a contract is safe.

Read [privacy and limits](./privacy.md) before sharing private source with an agent.
