# CLAUDE.md

Hindsight for smart contracts: a local-first CLI that triages Solidity code against a database of real past exploits. The source of truth is [PRD.md](PRD.md), with a plain-English walkthrough in [PRD-explained.md](PRD-explained.md). Read the PRD before you change scope, data sources or the evaluation.

## Git and PRs

- **Never add Claude attribution.** No `Co-Authored-By: Claude ...` trailer, no "Generated with Claude Code" line, no "Authored by ... Claude" in commit messages, PR titles, PR bodies or code comments.
- Commit or push only when asked.

## Current phase

- **M0 spike:** 30–50 Ethereum mainnet incidents taken through the funnel by hand (PRD §15).
- v1 scope is **Ethereum mainnet + Solidity only.** Don't add other chains or languages until the PRD says so.
- **No LLM fine-tuning before M5.** The small models are trained earlier: the precedent reranker and the findings ranker (PRD §7.9). Lightning AI credits go to labeling, embeddings, baselines and reranker training.
- **Rerankers and embedding models must be Apache-2.0 or MIT.** Jina rerankers are CC-BY-NC, so don't use them.

## Hard rules

- **No exploit generation.** Never write working attack transactions or scripts aimed at live contracts. No trading, MEV or farming code.
- **Data sources:** only the ones allowed in PRD §7.1.
  - No scraping of X or Solodit. X goes through the official API only.
  - News (Serper, Google News, RSS) is for discovery: store the URL, the date and our own summary, not the full text.
  - Keep DeFiHackLabs' Apache-2.0 attribution.
- **Untrusted code:** DeFiHackLabs PoCs, victim sources and their build scripts are untrusted.
  - Run them only in a disposable container, with no keys or credentials and network restricted.
  - Never run them from inside a cloned repo with the host interpreter.
- **Privacy:** in local mode, no user code, Slither output or embeddings of user code may leave the machine. No telemetry by default.

## Evaluation rules (don't weaken these)

- Split chronologically by `first_seen_at` into train, validation and a sealed test. An exploit family never spans partitions.
- Retrieval during eval uses `as_of` = the incident's `first_seen_at`. Exclude the target incident and its family.
- Strip PoC header comments, write-ups and the DHL README `raw_label` text from every eval input. All of them leak the answer.
- Judge each finding on its own: `confirmed_valid` / `confirmed_invalid` / `unresolved`. Report how many are unresolved.
- Report every baseline (B0–B4) on every run. Report per-incident confidence intervals.
- Report bad results plainly. A loss to a baseline is a finding, not something to hide.

## Working style

- Separate measured facts from assumptions, and say which one you're stating.
- Put measured numbers back into the PRD when M0 produces them.
