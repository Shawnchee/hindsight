# DeFiHackLabs coverage gaps on Ethereum (measured 2026-10-22)

**Question.** How many Ethereum incidents does DeFiHackLabs (DHL) miss, especially from 2025-09 to 2026-02, when it added only 1–6 entries a month? The answer decides whether news discovery (PRD §7.1, §15) is worth building.

**Stand-in source.** DeFiLlama `/hacks`, because there is no Serper key yet. Its licence is personal and non-commercial (PRD §7.1), so it is used here for internal measurement only. This file gives counts plus incident names and dates, and no other DeFiLlama fields.

Inputs: DeFiLlama snapshot fetched 2026-10-22 (1,314 incidents, latest dated 2026-10-21) and DHL at commit `23c7bd8` (2026-10-21, 896 dated entries parsed).

## Headline (measured)

Window: 2024-11 to 2026-10. The last month is partial (to 2026-10-21).

| | 24-month window | Gap months (2025-09 to 2026-02) |
|---|---|---|
| DeFiLlama Ethereum incidents | 179 | 30 |
| Off-chain (key compromise, frontend, social engineering, rug), excluded | 45 | 10 |
| **DeFiLlama Ethereum code-level** | **134** | **20** |
| Found in DHL too (±7 days) | 65 (49%) | 6 (30%) |
| **DeFiLlama-only (DHL miss)** | **69** | **14** |
| DHL miss after hand-correcting 2 date-offset cases | **~67** | **~13** |
| DHL-only (DHL Ethereum entry not in DeFiLlama at all) | 54 | 1 |

- In the gap months DHL caught 6 of the 20 DeFiLlama code-level Ethereum incidents, about 30%. In the other 18 months it caught 59 of 114, about 52%. So the gap months are worse, but **DHL misses about half of DeFiLlama's Ethereum code-level list even in normal months.**
- The reverse also holds. DHL has 54 Ethereum entries that DeFiLlama lacks, mostly small or unnamed contracts (`Unverified_*`, small tokens). Neither source is a superset of the other.
- DeFiLlama-only by DeFiLlama's own classification, over the window: Access Control 21, Bridge & Cross-Chain 13, Protocol Logic 12, Token & Share Accounting 7, Oracle Manipulation 6, Input Validation 4, Governance 3, Reentrancy 2, Market Manipulation 1. In 22 of the 69, the chain list has other chains besides Ethereum.
- Some DeFiLlama-only incidents are only arguably code-level, for example UXLINK (multisig takeover), Coinsbuy (custodial) and Aave V3 (oracle misconfiguration). Bridges (13) are code-level but often multi-chain and hard to fork-replay. **Inference (not measured):** perhaps 45–55 of the 69 would be in scope for Hindsight's funnel.

## Per month (Ethereum code-level)

`DHL eth` counts DHL entries whose PoC forks `mainnet`. `DHL all` counts every DHL entry on any chain, so you can see the update gaps.

| Month | DeFiLlama-only | DHL-only | Both | DHL eth | DHL all |
|---|---|---|---|---|---|
| 2024-11 | 0 | 0 | 4 | 5 | 14 |
| 2024-12 | 5 | 0 | 0 | 0 | 8 |
| 2025-01 | 1 | 2 | 3 | 5 | 17 |
| 2025-02 | 0 | 2 | 0 | 4 | 14 |
| 2025-03 | 1 | 4 | 4 | 6 | 18 |
| 2025-04 | 3 | 4 | 2 | 6 | 14 |
| 2025-05 | 0 | 0 | 2 | 2 | 16 |
| 2025-06 | 0 | 4 | 4 | 10 | 24 |
| 2025-07 | 2 | 10 | 1 | 11 | 22 |
| 2025-08 | 1 | 8 | 1 | 9 | 26 |
| 2025-09 (gap) | 2 | 0 | 0 | 0 | 2 |
| 2025-10 (gap) | 0 | 1 | 1 | 1 | 4 |
| 2025-11 (gap) | 2 | 0 | 3 | 2 | 3 |
| 2025-12 (gap) | 6 | 0 | 0 | 1 | 1 |
| 2026-01 (gap) | 2 | 0 | 2 | 2 | 6 |
| 2026-02 (gap) | 2 | 0 | 0 | 0 | 3 |
| 2026-03 | 6 | 1 | 1 | 3 | 13 |
| 2026-04 | 6 | 3 | 3 | 7 | 15 |
| 2026-05 | 8 | 1 | 7 | 9 | 24 |
| 2026-06 | 6 | 1 | 7 | 8 | 25 |
| 2026-07 | 8 | 0 | 1 | 2 | 5 |
| 2026-08 | 2 | 1 | 9 | 8 | 15 |
| 2026-09 | 5 | 9 | 6 | 15 | 35 |
| 2026-10 (partial) | 1 | 3 | 4 | 7 | 12 |
| **Total** | **69** | **54** | **65** | | |

A DeFiLlama row is placed by DeFiLlama's date, and a DHL-only row by DHL's date. In "Both", a DHL entry can be up to 7 days from the DeFiLlama date, so the "DHL eth" column doesn't reconcile exactly with "Both + DHL-only".

DeFiLlama-only incidents in the gap months (all 14): Bunni V2 (2025-09-02), UXLINK (2025-09-22), Dexmax AI (2025-11-20), Agentic FoF (2025-11-24), Goldfinch (2025-12-02), US Permissionless Dollar (2025-12-04), Ribbon (2025-12-12), Yearn Finance (2025-12-16), FutureSwap (2025-12-16; **not a real miss**, since DHL lists it on 2026-01-10), Rari Capital (2025-12-18), YO Protocol (2026-01-13), Aperture LM (2026-01-25), Ploutos Money (2026-02-26), Wise Lending V2 (2026-02-28).

July 2026 is a second, smaller DHL slump (5 entries on all chains, 8 DeFiLlama-only on Ethereum), outside the stated gap window.

## Spot-check sample (15 DeFiLlama-only, seeded random)

The last column shows the closest DHL entry within 7 days. All of these candidates are unrelated names, which means no near-match was missed. I also searched the names in **bold** case-insensitively across every DHL entry at any date, and none appear: Tenderize, ZKSwap, Solv, Kelp, THORChain, SUPERFORTUNE, JaredFromSubway, Hinkal, Drips, Coinsbuy and Payy. "Transit" and "Meter" match only DHL entries from 2022–23, which are earlier incidents. "Aave" matches DHL's 2026-04-19 AaveRebalancerCreditDelegation, which is a different incident.

| DeFiLlama date | DeFiLlama name | Nearest DHL entry within 7 days |
|---|---|---|
| 2025-04-07 | **Tenderize V2** | 2025-04-11 Unverified 0x6077 |
| 2025-07-09 | **ZKSwap** | 2025-07-16 VDS |
| 2025-12-04 | US Permissionless Dollar | 2025-12-01 yETH |
| 2026-03-06 | **SolvBTC** | 2026-03-10 AlkemiEarn |
| 2026-03-12 | **Aave V3** | 2026-03-15 Venus THE |
| 2026-04-18 | **Kelp** | 2026-04-21 KipseliPropAMM |
| 2026-04-20 | **Transit Finance** | 2026-04-14 Saturn Protocol |
| 2026-05-15 | **THORChain DEX** | 2026-05-10 Renegade |
| 2026-05-27 | **SUPERFORTUNE AI** | 2026-05-25 SquidRouterModule |
| 2026-06-20 | **JaredFromSubway MEV Bot** | 2026-06-22 Aztec Escape Hatch |
| 2026-07-02 | **Hinkal** | 2026-06-29 Vault4626 |
| 2026-07-14 | **Drips Network** | 2026-07-16 CrowdRingCircle |
| 2026-08-09 | **Coinsbuy** | 2026-08-09 USM |
| 2026-09-23 | **Meter** | 2026-09-21 InternetToken |
| 2026-09-24 | **Payy Network** | 2026-09-30 SKYDAO |

A human should still confirm on a block explorer or in a post-mortem that each one is a real Ethereum incident. The search above only shows that DHL lacks them.

## Method

1. **DeFiLlama.** Keep incidents whose `chain` list includes Ethereum. Separate the classifications Key Compromise, Frontend & Infrastructure, Social Engineering and Rugpull as off-chain. All others count as code-level.
2. **DHL.** Parse `### YYYYMMDD Name - Label` headers from `README.md` and `past/*/README.md`, then de-duplicate on (date, normalized name). The chain is read as text from the linked PoC's `createSelectFork("<chain>")`. If there is no PoC, the "on Ethereum/BNB Chain/…" phrase in the Lost line is used instead. Of the 336 window entries, 15 have no chain found. Nothing from the clone is executed.
3. **Name normalization.** Lowercase, strip non-alphanumerics, and strip suffixes such as finance/protocol/network/v2/vault. Two names match within ±7 days on any of these:
   - exact match, or exact after 0→o
   - substring of 4 or more characters
   - a shared prefix of 6 or more characters
   - a distinctive word of one name that starts or ends the other (generic words such as "the", "bridge" and "lending" are ignored)
   - difflib ratio ≥ 0.85
   - two hand-checked aliases (Yearn Ether↔yETH, Sorra↔SorStaking)
4. **Matching direction.** DeFiLlama Ethereum code-level incidents are matched against DHL entries on **every** chain, so a DHL chain mislabel can't create a fake miss. DHL Ethereum entries are matched against **every** DeFiLlama incident, of any chain or class, so DHL-only means "absent from DeFiLlama".

## Limitations and confidence

- **Name matching is noisy.** I hand-reviewed all 30 non-exact matches, and all looked correct. I also reviewed the nearest DHL candidate for all 69 DeFiLlama-only incidents: none score in the 0.6–0.85 "maybe" band. Known residual errors are 2 date offsets beyond 7 days (FutureSwap +25 days, SquidRouterModule +21 days), which the headline corrects by hand. Expect a few more mismatches of this kind (±3) that I didn't catch. The DHL-only side (54) was not hand-reviewed as closely.
- **DeFiLlama is not exhaustive.** It lacks 54 of DHL's Ethereum entries, so "DHL misses" here is a **lower bound** on what a broader news search would surface. Real Serper or Google News coverage of a gap month remains unmeasured (PRD §15 item).
- **Classification boundaries are DeFiLlama's.** Some "Access Control" incidents are operational (multisig takeovers, custodial wallets). Multi-chain incidents tagged Ethereum may have been exploited mainly on another chain.
- **Dates differ by source.** DeFiLlama uses the incident date and DHL the PoC header date, usually within a few days. DHL's past-year READMEs were assumed to be current.
- **One snapshot, one commit.** DHL backfills old incidents (for example, many 2026-09 entries hit dormant contracts), so later DHL commits may close some of these gaps.

## Implication for the decision

**Measured:** even against one aggregator, DHL alone would have missed about 67 code-level Ethereum incidents in 24 months, roughly half of DeFiLlama's list. In the gap months it missed about 13 of 19 real ones.

**Inference:** independent discovery is worth building. Its value isn't limited to the gap months, since DHL coverage is incomplete everywhere. However, DeFiLlama already provides much of this signal (internal, non-commercial use only). So the marginal value of Serper over DeFiLlama is the open question. Answering it needs the 20-query Serper test on 2025-12, the worst month here.
