# B2 v2: post-cutoff exploits + clean contracts (blind, mixed pool)

Model: sonnet-5.5 (B2 + precedents). Ground truth for exploits is the blind Fable 5.1 review of the post-cutoff set (LLM labels, not human-verified). The model doesn't know which cases are clean.

| Metric | Value |
|---|---|
| Exploit cases scored | 22 (of 23; rest lack a function-level causal location) |
| **Exploit Hit@1** | 11/22 (50%) |
| **Exploit Hit@5** | 17/22 (77%) |
| Exploit cases where the model claims a bug (medium/high) | 3/23 (13%) |
| **Clean false-positive rate** (claims an exploitable bug, medium/high) | 0/12 (0%) |

Caveats:
- "Post-cutoff" means the incident is from 2026-07 or later. The model's exact training cutoff isn't documented, and some victims are old code that could be in pretraining.
- The clean contracts are famous and audited. The model has probably seen them called safe, so this flatters the false-positive rate. Obscure, never-exploited contracts would be the harder test.

## Exploit cases

| Incident | Truth | Top-5 | @1 | @5 |
|---|---|---|---|---|
| 20260701_edelxstock | getassetprice | getassetprice, setassetsources, setfallbackoracle, upgradetoandcall, initialize | y | y |
| 20260706_SummerFi | _sumtotalassets, deposit, redeem, totalassets | deposit, withdraw, redeem, rebalance, _forcedisembarkfromsortedarks | y | y |
| 20260805_StrongBlock | - | upgradetoandcall, changeadmin, upgradeto, constructor, _willfallback | n | n |
| 20260806_UnistreetLaunchpad | launch | launch, _seedbuys, harvest, pushdistribute, _approverouter | y | y |
| 20260809_USM | _defundfum, defund, ethfromdefund, fund | checkforfreshoracleprice, _defundfum, ethfromdefund, fumfromfund, _burnusm | n | y |
| 20260823_ArrakisGUNI | burn, getunderlyingbalances, mint | upgradetoandcall, _setimplementation, transferproxyadmin, _fallback, supportsinterface | n | n |
| 20260831_BalancerV1BPool | calcsingleingivenpoolout, exitswappoolamountin, joinswappoolamountout, swapexactamountin | gulp, swapexactamountin, joinswapexternamountin, exitswappoolamountin, _pullunderlying | n | y |
| 20260831_FloatProtocol | _amountsforliquidity, currenttick, deposit, gettotalamounts | deposit, gettotalamounts, withdraw, rebalance, _liquidityforshares | y | y |
| 20260901_ReflexerGEB | processsafe, quitsystem | protectsafe, transfersafeownership, quitsystem, transfer, _getgenerateddeltadebt | n | y |
| 20260903_NotionalFinance | _converttoeth, mintfcashpair, safetransferfrom | _finishliquidatesettle, tokensreceived, _tokendeposit, safetransferfrom, _withdraw | n | y |
| 20260905_Reddio | depositerc20, getremainingbalance, gettotalassetbalance, registererc20 | diamondcut, initializediamondcut, fallback, replacefunctions, removefunction | n | n |
| 20260905_SecuredFi | executeorder, getmarketunitprice, updateblockunitpricehistory | upgradeto, changeadmin, constructor, _upgradetoandcall, constructor | n | n |
| 20260909_EtherFiAtomicQueue | solve, updateatomicrequest | solve, updateatomicrequest, _calculateassetamount, viewsolvemetadata, isatomicrequestvalid | y | y |
| 20260909_OMNI404 | transfer, transferfrom | _transfer, transferfrom, _burnerc721, _credit, mint | n | y |
| 20260912_YamFinance | execute, proposalthreshold, propose, quorumvotes, state | masterfallback, enter, update_twap, addincentivizer, executetransaction | n | n |
| 20260915_RsETHSafeModule | multicall | createproxywithcallback, createproxy, createproxywithnonce, fallback, calculatecreateproxywithnonceaddress | n | n |
| 20260916_Flamincome | balanceofy, deposit, deposited, withdraw | deposit, withdraw, balanceofy, setimpl, withdraw | y | y |
| 20260916_Startale | constructor, createaccount, initializeaccount, requireinitializable | createaccount, deployproxy, constructor, withdrawstake, requireinitializable | y | y |
| 20260930_MUS | deposit, withdraw | withdraw, deposit, packsettings, transfer, transferfee | y | y |
| 20261001_FlashLoopAdapter | _start, _swap, open | _start, _swap, _validate, _sweep, _run | y | y |
| 20261008_X7Finance | claimrewards | claimrewards, unclaimedrewards, airdroptokens, unlocktransfer, _beforetokentransfer | y | y |
| 20261015_KolanHook | _buyback, _closewindow, _sqrtprice, accept | _closewindow, _reshape, _openwindow, _fill, cancel | y | y |
| 20261017_BiFi | _checkfirstaction, borrow, deposit, getinterestamount, repay, withdraw | handlerviewproxy, siviewproxy, reservedeposit, repayto, withdraw | n | y |

## Clean cases

| Contract | Claims bug | Confidence | Top-1 reason |
|---|---|---|---|
| GnosisSafe@0xd9db270c1b5e3bd161e8c8503c55ceabee709552 | n | high | Core execution path; matches audited Safe 1.3.0 with no deviation found. |
| Morpho@0xbbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb | n | medium | Relies on per-market oracle; rounding and bad-debt logic match canonical Morpho Blue. |
| NonfungiblePositionManager@0xc36442b4a4522e871399cd717abdd847ab11fe88 | n | high | Standard Uniswap V3 periphery; fee collection path. |
| Permit2@0x000000000022d473030f116ddee9f6b43ac78ba3 | n | high | Matches canonical Permit2: nonce consumed, signature verified, spender bound to msg.sender. |
| Seaport@0x00000000000000adc04c56bf30ac9d3c0aaf14dc | n | high | Most complex assembly-heavy aggregation path, but this is canonical Seaport 1.5 and audited. |
| SwapRouter@0xe592427a0aece92de3edee1f18e0157c05861564 | n | low | The pair and tokens are never validated, so a fake pair can claim inflated amounts and refunds are paid out of any token |
| TroveManager@0xa39739ef8b0231dbfa0dcda07d7e29faabcf4bb2 | n | medium | Complex redemption/hint logic, matches Liquity V1 and appears unmodified. |
| UniswapV2Factory@0x5c69bee701ef814a2b6a3edd4b1652cb9cc5aa6f | n | high | K invariant check with fee adjustment is correct and matches canonical Uniswap V2. |
| UniswapV2Router02@0x7a250d5630b4cf539739df2c5dacb4c659f2488d | n | high | Reads pair balance minus reserve for input amount; standard behaviour, manipulable only via the token. |
| UniswapV3Factory@0x1f98431c8ad98523631ae4a59f267346ea31f984 | n | low | This pool variant drops the onlyFactoryOwner modifier, so anyone could drain protocol fees if this variant is the deploy |
| UniversalRouter@0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad | n | medium | Forwards user-controlled calldata to a fixed set of marketplaces; the router holds no persistent funds. |
| WETH9@0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2 | n | high | Balance is decremented before transfer, so it is safe. |

## Comparison with B2 v2 (same model, same blind pool, no precedents)

| Metric | B2 v2 | + precedents |
|---|---|---|
| Exploit detection (medium/high) | 2/23 | 3/23 |
| Exploit detection (any confidence) | 5/23 | 6/23 |
| Clean FP (medium/high) | 0/12 | 0/12 |
| Clean FP (any confidence) | 0/12 | 1/12 (SwapRouter, low) |
| Hit@1 / Hit@5 | 9/22, 17/22 | 11/22, 17/22 |

**Verdict: flat.** Retrieval quality was poor:
- 5 generic incidents filled 43 of 175 slots.
- The median top-1 TF-IDF similarity was 0.17.

So this result tests the crude retriever, not the precedent idea itself. See PRD D16.

**Regenerate:**
1. Build the inputs: `python3 -I m0/scripts/spike/build_spike.py`.
2. Run the B2 v2 prompt plus PRECEDENTS.md on the 4 batches.
3. Score: `python3 -I m0/scripts/b2/score_v2.py --out m0/b2/spike/summary.md m0/b2/spike/spike.part*.jsonl`.
