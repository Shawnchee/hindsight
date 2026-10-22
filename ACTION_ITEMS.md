# Action items for Shawn

These are the things only you can do. Everything else in M0 is automated or waiting on one of these. Most important first.

## Blocking M0

1. **Review the 40 sampled incidents.** Ready now: all 40 are prepared and have LLM proposals. This is the core M0 measurement: minutes per review, and how often Slither catches the real bug.
   - **What the proposals suggest, not yet verified:** Slither explains the exploit in only 3 of 40. If your review confirms that, the product direction changes (PRD §3). Please judge the "explains" question carefully, and don't just press Enter.
   - **Doubtful incidents to look at closely:**
     - SushiSwapMiso: whitehat rescue, proposed out of scope
     - ActivePoolScrvUsd: may be a designed feature, not a bug
     - AmpKashi, ConicFinance02: low confidence
     - Audius: one candidate is post-exploit code; the CLI flags it
   - Run from the repo root:
     ```sh
     python3 -I m0/scripts/review/review.py
     ```
   - It's resumable. LLM proposals show as defaults: check them, don't trust them.
   - The guide is in `m0/review/README.md`.
   - The baselines B2 and B3 need these reviews as ground truth.
2. **Add API keys to `.env`.** It's gitignored. Enter the keys yourself; I don't handle them.
   - `ETHERSCAN_API_KEY`: recovers more source, especially victims that aren't on Sourcify, and lets us resolve proxies.
   - `SERPER_API_KEY`: for the news-discovery test on 2025-12.
   - An archive RPC URL for Ethereum mainnet: to find which implementation a proxy pointed to at the exploit block. Pick a provider whose free tier allows historical state calls.

## Decisions (non-blocking)

3. **Register the names:** the `hindsight-sec` GitHub org, the PyPI and npm package names, and a domain. Before any commercial release, also do a trademark search.
4. **Pick Hindsight's own licence.** The PRD leans towards Apache-2.0.
5. **Tell me your MacBook RAM.** It sets the largest model local mode can run.
6. **Tell me your Lightning AI credit amount and expiry date.** It sets how much labeling and baseline work to do up front.
7. **Set a budget for Serper and the X API.**

## Repo

8. Nothing is pushed. Changes made after commit `e674014` are not committed yet. Say when to commit and when to push.
