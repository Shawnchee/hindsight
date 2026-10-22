# Action items for Shawn

These are the things only you can do. Everything else in M0 is automated or waiting on one of these. Most important first.

## Blocking M0

1. **Spot-check about 10 incidents by hand.** This replaces the full review of 40. Fable 5.1 has already reviewed all 40 blind, so the provisional decision is D15 in PRD §13.
   - Run `python3 -I m0/scripts/review/review.py --redo <id>` for each one, and time yourself.
   - **The 3 where Slither "explains" the exploit:** 20220327_RevestFinance, 20220430_RariCapitalFeiProtocol, 20250729_AnyswapWETHPermit. Is the finding really the bug?
   - **Where Opus and Fable disagree:** 20230722_ConicFinance02, 20250208_PeapodsFinance, 20210916_SushiSwapMiso (in scope?), 20250705_ActivePoolScrvUsd (in scope?)
   - **Negatives where Slither came close:** 20211221_VisorFinance, 20231122_KyberSwap, 20251103_BalancerV2. Did both models miss a real hit?
   - If your calls match, D15 is final.

   Original item, kept for reference: review all 40 sampled incidents. This was the core M0 measurement: minutes per review, and how often Slither catches the real bug.
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
5. ~~MacBook RAM~~ Done: Air, 24 GB. Local mode targets 7–14B models at 4-bit.
6. ~~Lightning credit~~ Done: $15, reserved for reranker fine-tuning. Tell me the expiry date if there is one.
7. **Set a budget for Serper and the X API.**

## Repo

8. Nothing is pushed. Changes made after commit `e674014` are not committed yet. Say when to commit and when to push.
