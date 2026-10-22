# B2 v2: post-cutoff exploits + clean contracts (blind, mixed pool)

Model: sonnet-5.5 (B2 + oracle precedents). Ground truth for exploits is the blind Fable 5.1 review of the post-cutoff set (LLM labels, not human-verified). The model doesn't know which cases are clean.

| Metric | Value |
|---|---|
| Exploit cases scored | 22 (of 23; rest lack a function-level causal location) |
| **Exploit Hit@1** | 10/22 (45%) |
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
| 20260706_SummerFi | _sumtotalassets, deposit, redeem, totalassets | deposit, redeem, _forcedisembarkfromsortedarks, _getarksdata, rebalance | y | y |
| 20260805_StrongBlock | - | upgradetoandcall, changeadmin, upgradeto, constructor, _delegate | n | n |
| 20260806_UnistreetLaunchpad | launch | pushdistribute, harvest, _syncholder, _seedbuys, launch | n | y |
| 20260809_USM | _defundfum, defund, ethfromdefund, fund | checkforfreshoracleprice, _fundfum, _defundfum, ethfromburn, _storestate | n | y |
| 20260823_ArrakisGUNI | burn, getunderlyingbalances, mint | upgradetoandcall, transferproxyadmin, _setimplementation, constructor, _fallback | n | n |
| 20260831_BalancerV1BPool | calcsingleingivenpoolout, exitswappoolamountin, joinswappoolamountout, swapexactamountin | joinswapexternamountin, exitswappoolamountin, gulp, swapexactamountin, rebind | n | y |
| 20260831_FloatProtocol | _amountsforliquidity, currenttick, deposit, gettotalamounts | deposit, withdraw, rebalance, gettotalamounts, _liquidityforshares | y | y |
| 20260901_ReflexerGEB | processsafe, quitsystem | transfersafeownership, quitsystem, repaydebt, coinjoin_join, transfer | n | y |
| 20260903_NotionalFinance | _converttoeth, mintfcashpair, safetransferfrom | _tokendeposit, tokensreceived, safetransferfrom, _withdraw, _addliquidity | n | y |
| 20260905_Reddio | depositerc20, getremainingbalance, gettotalassetbalance, registererc20 | fallback, diamondcut, initializediamondcut, replacefunctions, removefunction | n | n |
| 20260905_SecuredFi | executeorder, getmarketunitprice, updateblockunitpricehistory | upgradeto, changeadmin, _upgradetoandcall, constructor, _delegate | n | n |
| 20260909_EtherFiAtomicQueue | solve, updateatomicrequest | solve, updateatomicrequest, _calculateassetamount, viewsolvemetadata, isatomicrequestvalid | y | y |
| 20260909_OMNI404 | transfer, transferfrom | _transfer, transferfrom, _credit, _setwhitelist, approve | n | y |
| 20260912_YamFinance | execute, proposalthreshold, propose, quorumvotes, state | enter, update_twap, masterfallback, executetransaction, getpriorvotes | n | n |
| 20260915_RsETHSafeModule | multicall | createproxywithnonce, createproxywithcallback, deployproxywithnonce, fallback, createproxy | n | n |
| 20260916_Flamincome | balanceofy, deposit, deposited, withdraw | deposit, balanceofy, withdraw, withdraw, setimpl | y | y |
| 20260916_Startale | constructor, createaccount, initializeaccount, requireinitializable | createaccount, deployproxy, requireinitializable, constructor, withdrawstake | y | y |
| 20260930_MUS | deposit, withdraw | withdraw, deposit, transfer, restart, transferfee | y | y |
| 20261001_FlashLoopAdapter | _start, _swap, open | _swap, _start, _validate, _sweep, _run | y | y |
| 20261008_X7Finance | claimrewards | claimrewards, unclaimedrewards, airdroptokens, unlocktransfer, _beforetokentransfer | y | y |
| 20261015_KolanHook | _buyback, _closewindow, _sqrtprice, accept | _closewindow, _openwindow, _reshape, afterswap, buy | y | y |
| 20261017_BiFi | _checkfirstaction, borrow, deposit, getinterestamount, repay, withdraw | handlerviewproxy, siviewproxy, _transferfrom, depositto, withdraw | n | y |

## Clean cases

| Contract | Claims bug | Confidence | Top-1 reason |
|---|---|---|---|
| GnosisSafe@0xd9db270c1b5e3bd161e8c8503c55ceabee709552 | n | high | Core execution path; appears identical to audited Safe 1.3.0. |
| Morpho@0xbbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb | n | high | Complex rounding and bad-debt socialization, but matches audited Morpho Blue rounding directions. |
| NonfungiblePositionManager@0xc36442b4a4522e871399cd717abdd847ab11fe88 | n | high | Standard Uniswap V3 collect with owner/approval check; matches canonical code. |
| Permit2@0x000000000022d473030f116ddee9f6b43ac78ba3 | n | high | Matches canonical Permit2 nonce and signature handling. |
| Seaport@0x00000000000000adc04c56bf30ac9d3c0aaf14dc | n | medium | Complex fulfillment aggregation, the most intricate accounting path in Seaport 1.5 but no defect seen. |
| SwapRouter@0xe592427a0aece92de3edee1f18e0157c05861564 | n | high | Pool verified via the CREATE2 factory computation, canonical. |
| TroveManager@0xa39739ef8b0231dbfa0dcda07d7e29faabcf4bb2 | n | medium | Unmodified Liquity v1 redemption logic; hint and fee checks appear intact. |
| UniswapV2Factory@0x5c69bee701ef814a2b6a3edd4b1652cb9cc5aa6f | n | high | K invariant check intact and identical to stock Uniswap V2. |
| UniswapV2Router02@0x7a250d5630b4cf539739df2c5dacb4c659f2488d | n | high | Standard Uniswap V2 router logic using balance deltas. |
| UniswapV3Factory@0x1f98431c8ad98523631ae4a59f267346ea31f984 | n | low | onlyFactoryOwner was removed so anyone can sweep accrued protocol fees to an arbitrary recipient. |
| UniversalRouter@0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad | n | medium | Permissionless call with caller data to the fixed LooksRare distributor, so the target is constrained. |
| WETH9@0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2 | n | high | Effects before transfer and the 2300 gas stipend, so safe. |

## Three-way comparison (same model, same blind pool; only PRECEDENTS.md differs)

| Metric | B2 v2 | + retrieved | + oracle |
|---|---|---|---|
| Exploit flagged, med/high | 2/23 | 3/23 | 3/23 |
| Exploit flagged, any conf | 5/23 | 6/23 | 5/23 |
| Correct detection (flagged + top-1 is the bug) | 4/23 | 4/23 | 3/23 |
| Clean FP, med/high | 0/12 | 0/12 | 0/12 |
| Clean FP, any conf | 0/12 | 1/12 | 1/12 |
| Hit@1 | 9/22 | 11/22 | 10/22 |
| Hit@5 | 17/22 | 17/22 | 17/22 |

- oracle flagged exploits: ['UnistreetLaunchpad', 'USM', 'FloatProtocol', 'Flamincome', 'X7Finance']
- v2 flagged exploits: ['UnistreetLaunchpad', 'BalancerV1BPool', 'FloatProtocol', 'Flamincome', 'X7Finance']
- oracle clean flags: ['UniswapV3Factory@0x1']

**Verdict: no lift, even with hand-picked past hacks.** The same handful of incidents is flagged in all three runs. Detection depends on the code, not on the past hacks. See PRD D17.

**Regenerate:**

1. `python3 -I m0/scripts/spike/oracle.py dump`
2. Run the selector agents, which write `m0/data/oracle/picks.part*.jsonl`.
3. `python3 -I m0/scripts/spike/oracle.py render`
4. Run the evaluator agents, using the spike prompt with `m0/data/oracle/inputs`.
5. Score with `score_v2.py --out m0/b2/oracle/summary.md`.
