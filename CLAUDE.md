# Hindsight agent rules

Read [AGENTS.md](AGENTS.md) for supported workflows, source policy and boundaries,
then [the skill](skills/hindsight-triage/SKILL.md) for source review.

- Ethereum mainnet + Solidity only. Other-chain references never silently become
  in-scope dataset entries. Research labels remain proposed and ineligible.
- No exploit generation, live attack transactions, MEV, trading or farming code.
- Never execute untrusted project code/builds on the host. Use an available
  disposable container without credentials and with restricted networking, or
  record execution as not_run. Never install tools or models automatically.
- No direct X or Solodit scraping. Discovery keeps links, dates and original
  summaries. Preserve upstream attribution and review source rights.
- Do not read credentials or send private source to additional providers. The
  host agent determines source privacy; the helpers have no model client.
- Model tests and weight downloads remain paused. No fine-tuning is authorized.
- Commit or push only when asked. Never add Claude attribution or coauthor
  trailers to commits, PRs or source comments.
- State measured results separately from assumptions. A valid report is not a
  security certificate. Do not weaken snapshot fingerprints or eligibility gates.
