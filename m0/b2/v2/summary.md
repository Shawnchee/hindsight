# B2 v2: post-cutoff exploits + clean contracts (blind, mixed pool)

Model: sonnet-5.5 (B2 v2, code only). Ground truth for exploits is the blind Fable 5.1 review of the post-cutoff set (LLM labels, not human-verified). The model doesn't know which cases are clean.

| Metric | Value |
|---|---|
| Exploit cases scored | 22 (of 23; rest lack a function-level causal location) |
| **Exploit Hit@1** | 9/22 (41%) |
| **Exploit Hit@5** | 17/22 (77%) |
| Exploit cases where the model claims a bug (medium/high) | 2/23 (9%) |
| **Clean false-positive rate** (claims an exploitable bug, medium/high) | 0/12 (0%) |

Caveats:
- "Post-cutoff" means the incident is from 2026-07 or later. The model's exact training cutoff isn't documented, and some victims are old code that could be in pretraining.
- The clean contracts are famous and audited. The model has probably seen them called safe, so this flatters the false-positive rate. Obscure, never-exploited contracts would be the harder test.

## Exploit cases

| Incident | Truth | Top-5 | @1 | @5 |
|---|---|---|---|---|
| 20260701_edelxstock | getassetprice | getassetprice, setassetsources, setfallbackoracle, _willfallback, initialize | y | y |
| 20260706_SummerFi | _sumtotalassets, deposit, redeem, totalassets | redeem, withdrawfromarks, _totalassets, _accruetip, sweep | y | y |
| 20260805_StrongBlock | - | upgradetoandcall, changeadmin, constructor, _willfallback, _delegate | n | n |
| 20260806_UnistreetLaunchpad | launch | launch, _seedbuys, harvest, pushdistribute, _approverouter | y | y |
| 20260809_USM | _defundfum, defund, ethfromdefund, fund | ethfromburn, fumfromfund, ethfromdefund, checkforfreshoracleprice, _burnusm | n | y |
| 20260823_ArrakisGUNI | burn, getunderlyingbalances, mint | upgradetoandcall, transferproxyadmin, _setimplementation, upgradeto, _fallback | n | n |
| 20260831_BalancerV1BPool | calcsingleingivenpoolout, exitswappoolamountin, joinswappoolamountout, swapexactamountin | gulp, swapexactamountin, _pullunderlying, swapexactamountout, rebind | n | y |
| 20260831_FloatProtocol | _amountsforliquidity, currenttick, deposit, gettotalamounts | deposit, withdraw, rebalance, uniswapv3swapcallback, gettotalamounts | y | y |
| 20260901_ReflexerGEB | processsafe, quitsystem | repaydebt, transfersafeownershiptoproxy, quitsystem, protectsafe, _getgenerateddeltadebt | n | y |
| 20260903_NotionalFinance | _converttoeth, mintfcashpair, safetransferfrom | _withdraw, tokensreceived, safetransferfrom, _addliquidity, transferaccountasset | n | y |
| 20260905_Reddio | depositerc20, getremainingbalance, gettotalassetbalance, registererc20 | diamondcut, initializediamondcut, fallback, replacefunctions, removefunction | n | n |
| 20260905_SecuredFi | executeorder, getmarketunitprice, updateblockunitpricehistory | changeadmin, upgradeto, constructor, _upgradetoandcall, implementation | n | n |
| 20260909_EtherFiAtomicQueue | solve, updateatomicrequest | solve, updateatomicrequest, _calculateassetamount, viewsolvemetadata, isatomicrequestvalid | y | y |
| 20260909_OMNI404 | transfer, transferfrom | _transfer, transferfrom, _credit, _setwhitelist, approve | n | y |
| 20260912_YamFinance | execute, proposalthreshold, propose, quorumvotes, state | enter, exit, update_twap, masterfallback, addincentivizer | n | n |
| 20260915_RsETHSafeModule | multicall | fallback, constructor, createproxywithnonce, createproxywithcallback, deployproxywithnonce | n | n |
| 20260916_Flamincome | balanceofy, deposit, deposited, withdraw | deposit, withdraw, balanceofy, withdraw, update | y | y |
| 20260916_Startale | constructor, createaccount, initializeaccount, requireinitializable | deployproxy, createaccount, withdrawstake, requireinitializable, predictproxyaddress | n | y |
| 20260930_MUS | deposit, withdraw | withdraw, deposit, packsettings, transferfee, restart | y | y |
| 20261001_FlashLoopAdapter | _start, _swap, open | _validate, _start, _swap, _run, executeoperation | n | y |
| 20261008_X7Finance | claimrewards | claimrewards, airdroptokens, unclaimedrewards, _beforetokentransfer, unlocktransfer | y | y |
| 20261015_KolanHook | _buyback, _closewindow, _sqrtprice, accept | _closewindow, cancel, _reshape, buy, _fill | y | y |
| 20261017_BiFi | _checkfirstaction, borrow, deposit, getinterestamount, repay, withdraw | handlerviewproxy, siviewproxy, _transferfrom, withdraw, partialliquidationuser | n | y |

## Clean cases

| Contract | Claims bug | Confidence | Top-1 reason |
|---|---|---|---|
| GnosisSafe@0xd9db270c1b5e3bd161e8c8503c55ceabee709552 | n | high | Core signature loop appears identical to audited Safe 1.3.0 with ordered-owner and contract-signature bounds checks. |
| Morpho@0xbbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb | n | medium | Complex share/asset rounding and bad-debt socialization; appears to match audited design. |
| NonfungiblePositionManager@0xc36442b4a4522e871399cd717abdd847ab11fe88 | n | medium | Fee accounting and recipient handling, matches upstream Uniswap. |
| Permit2@0x000000000022d473030f116ddee9f6b43ac78ba3 | n | high | Canonical Permit2 nonce bitmap and signature flow. |
| Seaport@0x00000000000000adc04c56bf30ac9d3c0aaf14dc | n | medium | Heavily assembly-optimized calldata handling is the most error-prone surface. |
| SwapRouter@0xe592427a0aece92de3edee1f18e0157c05861564 | n | medium | Pool-validated callback pays from payer; canonical Uniswap periphery. |
| TroveManager@0xa39739ef8b0231dbfa0dcda07d7e29faabcf4bb2 | n | low | entireSystemColl omits collSurplus subtraction unlike the sequence variant; minor accounting error. |
| UniswapV2Factory@0x5c69bee701ef814a2b6a3edd4b1652cb9cc5aa6f | n | high | Standard V2 K invariant check. |
| UniswapV2Router02@0x7a250d5630b4cf539739df2c5dacb4c659f2488d | n | high | Standard chained swap, unchanged from upstream. |
| UniswapV3Factory@0x1f98431c8ad98523631ae4a59f267346ea31f984 | n | low | Core swap loop; matches canonical Uniswap V3 so no deviation found. |
| UniversalRouter@0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad | n | medium | Forwards calls to fixed marketplace targets with user value; targets are immutable, not attacker chosen. |
| WETH9@0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2 | n | high | Balance decremented before transfer; canonical WETH9. |
