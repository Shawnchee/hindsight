# B2 baseline: frontier model, code only (M0)

Model: sonnet-5.5 (B2, code only). Ground truth: causal functions from the blind Fable 5.1 review (and, leniently, the union with Opus proposals). **Both are LLM labels, not human-verified.**

Cases: 27 (answered 27; 0 without a function-level causal location, excluded).

| Metric | All | Before 2026-07 | 2026-07 and later (likely post-cutoff) |
|---|---|---|---|
| **B2 Hit@1** | 14/27 (52%) | 13/24 (54%) | 1/3 (33%) |
| **B2 Hit@5** | 19/27 (70%) | 18/24 (75%) | 1/3 (33%) |
| B2 Hit@5 (lenient key) | 21/27 (78%) | 19/24 (79%) | 2/3 (67%) |
| **B0 Slither top-5 Hit@5** | 10/27 (37%) | 8/24 (33%) | 2/3 (67%) |
| B0 Hit@5 (lenient key) | 11/27 (41%) | 8/24 (33%) | 3/3 (100%) |

Caveats:
- Older incidents are famous and probably in the model's pretraining data. The late column is the honest one, and it has only 3 cases.
- Function-name matching is strict: a correct contract-level answer, or the right defect in a helper, counts as a miss.
- B0 here is Slither's findings ranked by impact then confidence, mapped to functions. It's not a tuned config.

| Incident | Date | Truth (Fable) | B2 top-5 | Slither top-5 | B2@5 | B0@5 |
|---|---|---|---|---|---|---|
| 20210811_PolyNetwork | 2021-08-11 | _executecrosschaintx, verifyheaderandexecutetx | putcurepochconpubkeybytes, unlock, transferownership, setmanagerproxy, bindproxyhash | _serializetxargs, _transferfromcontract, _deserializetxargs, putcurepochstartheight, setmanagerproxy | n | n |
| 20211221_VisorFinance | 2021-12-21 | deposit | deposit, withdraw, iscontract, mint, transferownership | deposit, constructor, name, decimals, symbol | y | y |
| 20220326_Auctus | 2022-03-26 | _sellacotokens, write | write, _sellacotokens, receive, _transferfromerc20, _approveerc20 | constructor, _transfererc20, _sellacotokens, _approveerc20, _balanceoferc20 | y | y |
| 20220327_RevestFinance | 2022-03-27 | mint, mintaddresslock | mint, domint, mintaddresslock, depositadditionaltofnft, mintbatchrec | domint, burn, mintvaluelock, extendfnftmaturity, minttimelock | y | n |
| 20220416_BeanstalkFarms | 2022-04-16 | emergencycommit, propose | diamondcut, initializediamondcut, diamondcut, msgsender, enforceiscontractowner | getchainid, fallback, msgsender, diamondstorage, enforcehascontractcode | n | n |
| 20220430_RariCapitalFeiProtocol | 2022-04-30 | borrowfresh, borrowinternal, dotransferout | exitmarket, borrowfresh, dotransferout, redeemfresh, borrowallowed | hasadminrights, fallback, _becomeimplementation, _setborrowcapguardian, _setmarketborrowcaps | y | n |
| 20220723_Audius | 2022-07-23 | audiusadminupgradeabilityproxy, governance.initialize | initialize, guardianexecutetransaction, _executetransaction, submitproposal, evaluateproposaloutcome | _executetransaction, delegatestake, setaddress, setserviceversion, addservicetype | n | n |
| 20221009_XaveFinance | 2022-10-09 | addproposalwithnonce, constructor, executeproposalwithindex | executeproposalwithindex, addproposalwithnonce, markproposalwithexpiredanswerasinvalid, markproposalasinvalid, getquestionid | setquestioncooldown, setminimumbond, setquestiontimeout, settemplate, setanswerexpiration | y | n |
| 20221017_UeriiToken | 2022-10-17 | mint | mint, constructor, decimals, transferfrom, _mint | _burn, _msgdata, constructor, mint | y | y |
| 20230224_EFVault | 2023-02-24 | converttoassets, redeem | _authorizeupgrade, upgradetoandcall, upgradeto, _beforeupgrade, upgradetoandcall | admin, constructor | n | n |
| 20230606_VINU | 2023-06-06 | addliquidityeth | addliquidityeth, _transfer, transferfrom, decode, approve | _transfer, addliquidityeth, _approve, owner, allowance | y | y |
| 20230722_ConicFinance02 | 2023-07-22 | _curvelptounderlying, _gettotalandperpoolunderlying, depositfor, withdraw | withdraw, depositfor, _gettotalandperpoolunderlying, _curvelptounderlying, _withdrawfromcurve | poolcheckpoint, claimearnings, depositfor, _withdrawfromcurvepool, functiondelegatecall | y | y |
| 20231122_KyberSwap | 2023-11-22 | calcfinalprice, calcreachamount, computeswapstep, swap | swap, calcfinalprice, computeswapstep, calcreachamount, _updateliquidityandcrosstick | muldivfloor, getsqrtratioattick, _initpoolstorage, _tweakposition, _updatepooldata | y | n |
| 20231216_GoodDollar | 2023-12-16 | collectinterest | initialize, deployminimal, deployproxy, deploycode, _deploycode | _deployproxy, deployminimal, _deploycode, deploycode, getdeploymentaddress | n | n |
| 20240202_ADC | 2024-02-02 | calcstepincome, joingame | calcstepincome, withdraw, settlementstatic, checkticket, crosslevel | buyadc, withdraw, startnewrount, caldeductionadc, calcs_t | y | n |
| 20240223_BlueberryProtocol | 2024-02-23 | borrowallowed | exchangeratestoredinternal, gethypotheticalaccountliquidityinternal, redeemallowedinternal, borrowallowed, liquidatecalculateseizetokens | - | y | n |
| 20240309_UnizenIO | 2024-03-09 | _fallback | _authorizeupgrade, upgradetoandcall, upgradeto, _beforeupgrade, upgradetoandcall | admin, constructor | n | n |
| 20240724_Spectrafinance | 2024-07-24 | _fallback | upgradeandcall, constructor, _fallback, _dispatchupgradetoandcall, _proxyadmin | _delegate, _fallback, _implementation | y | y |
| 20250104_SorStaking | 2025-01-04 | withdraw | withdraw, _calculaterewards, getpendingrewards, _decreaseposition, emergencywithdraw | _updateposition, withdraw, _decreaseposition, _increaseposition, _calculaterewards | y | y |
| 20250208_PeapodsFinance | 2025-02-08 | depositfrompairedlptoken | depositfrompairedlptoken, _processfeesifapplicable, _depositrewards, _distributereward, setshares | beginningofmonth, _calloptionalreturn, _distributereward, _removeshares, functioncallwithvalue | y | n |
| 20250729_AnyswapWETHPermit | 2025-07-29 | anyswapoutunderlyingwithpermit | anyswapoutexacttokensfortokensunderlyingwithpermit, anyswapoutunderlyingwithpermit, anyswapoutexacttokensfornativeunderlyingwithpermit, anyswapoutunderlyingwithtransferpermit, anyswapoutexacttokensfortokensunderlyingwithtransferpermit | anyswapoutunderlyingwithpermit, anyswapoutexacttokensfortokensunderlyingwithpermit, anyswapoutexacttokensfornativeunderlyingwithpermit, anyswapinunderlying, anyswapoutexacttokensfornativeunderlyingwithtransferpermit | y | y |
| 20251103_BalancerV2 | 2025-11-03 | _swapgivenout, _upscale, onswap | _swapgivenout, _upscale, _calcingivenout, _swapwithbpt, _gettokenbalancegiveninvariantandallotherbalances | constructor, _getsupplyandfeesdata, _ondisablerecoverymode, _updatetokenratecache, _beforeprotocolfeecacheupdate | y | n |
| 20260423_GiddyVaultV3 | 2026-04-23 | _validateauthorization, compound | _validateauthorization, executeswap, swaprewardtokens, _executedeposit, withdraw | executeswap, deposit, _compound, _recordyield, withdraw | y | n |
| 20260617_AztecV1 | 2026-06-17 | escapehatch, verifyproofandupdatestate | processdepositsandwithdrawals, validatemerkleroots, verifyproofandupdatestate, depositpendingfundspermit, internaldeposit | internaldeposit, withdraw, transferfee, decreasependingdepositbalance, processdepositsandwithdrawals | y | n |
| 20260806_UnistreetLaunchpad | 2026-08-06 | launch | launch, harvest, _seedbuys, pushdistribute, _syncholder | launch, harvest, _seedbuys, pushdistribute, _approverouter | y | y |
| 20260909_OMNI404 | 2026-09-09 | transfer | _transfer, transferfrom, _minterc721, _burnerc721, _minterc20 | approve, transferfrom, panic, setbaseuri | n | n |
| 20261017_BiFi | 2026-10-17 | _checkfirstaction, deposit | handlerviewproxy, siviewproxy, partialliquidationuser, reservedeposit, withdraw | _getusermaxborrowamount, _getusermaxwithdrawamount, borrow, deposit, depositflashloanfee | n | y |

## Notes added after scoring

- **Contamination seen directly:** a B2 answer called one case "Audius-style re-initialization", so the model recognised the hack from memory.
- **The labels share a model family with B2.** The labels come from Opus and Fable, and B2 is Sonnet: all three are Claude models. Agreement may be inflated by shared priors.
- **6 of the 8 B2 misses are input-data gaps.** Only the proxy was supplied (EFVault, Unizen), the Diamond facet was missing (Beanstalk), or the defect was in an unrecovered contract (GoodDollar, Audius, BiFi). Fixing proxy and implementation resolution should lift every baseline.
- **Regenerate:**
  1. `python3 -I m0/scripts/b2/prepare_b2.py` writes the blind inputs to `m0/data/b2/` (gitignored).
  2. Run the B2 agents with the prompt in `m0/b2/PROMPT.md`.
  3. Score with `python3 -I m0/scripts/b2/score.py m0/b2/b2.part*.jsonl`.
