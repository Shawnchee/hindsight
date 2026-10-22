import json
M="sonnet-5.5 (B2 + precedents)"
def t(l,c,w): return {"location":l,"category":c,"why":w}
cases=[
("case_007ac219",False,"high",[
 t("UpgradeabilityProxy.sol:upgradeTo","access_control","Admin-only upgrade guarded by ifAdmin; correct but the highest-impact entry."),
 t("UpgradeabilityProxy.sol:changeAdmin","access_control","Admin handover guarded by ifAdmin; no zero-address check but not attacker-reachable."),
 t("UpgradeabilityProxy.sol:constructor","uninitialized_or_unprotected_init","Sets admin to deployer after init delegatecall; standard ordering, no exploit."),
 t("ERC1967Upgrade.sol:_upgradeToAndCall","arbitrary_external_call","Delegatecalls initializer data in constructor; only deployer controls it."),
 t("ERC1967Proxy.sol:constructor","uninitialized_or_unprotected_init","Initial implementation init; risk only if the logic contract is left uninitialized.")],4),
("case_024554b8",False,"medium",[
 t("Morpho.sol:liquidate","price_oracle_trust","Relies on per-market oracle; rounding and bad-debt logic match canonical Morpho Blue."),
 t("Morpho.sol:borrow","business_logic","Health check after state update, rounding up shares; matches canonical."),
 t("Morpho.sol:setAuthorizationWithSig","signature_validation","EIP-712 with nonce and deadline; correct."),
 t("Morpho.sol:flashLoan","arbitrary_external_call","Callback to msg.sender with balance pull-back; safe design."),
 t("Morpho.sol:withdrawCollateral","business_logic","Collateral removal gated by authorization and health check; fine.")],1),
("case_032a6091",False,"high",[
 t("AdminUpgradeabilityProxy.sol:upgradeToAndCall","arbitrary_external_call","Admin-only delegatecall to new implementation; standard ZeppelinOS."),
 t("AdminUpgradeabilityProxy.sol:changeAdmin","access_control","Guarded by ifAdmin."),
 t("AdminUpgradeabilityProxy.sol:upgradeTo","access_control","Guarded by ifAdmin."),
 t("UpgradeabilityProxy.sol:constructor","uninitialized_or_unprotected_init","Init delegatecall runs before admin set; only deployer-controlled."),
 t("AdminUpgradeabilityProxy.sol:_willFallback","access_control","Blocks admin from fallback; correct.")],2),
("case_05505e97",True,"low",[
 t("BPool.sol:gulp","other","Lets anyone resync recorded balance to actual token balance; with deflationary/rebasing tokens this desyncs accounting (Balancer STA incident pattern)."),
 t("BPool.sol:swapExactAmountIn","business_logic","Records tokenAmountIn before pull; fee-on-transfer tokens leave the pool with less than recorded, draining it."),
 t("BPool.sol:joinswapExternAmountIn","business_logic","Same recorded-vs-received mismatch plus single-asset join math asymmetry."),
 t("BPool.sol:exitswapPoolAmountIn","rounding_precision","Single-sided exit math can be arbitraged against swap-fee/rounding asymmetry."),
 t("BPool.sol:_pullUnderlying","business_logic","Trusts transferFrom amount; no balance-delta check for non-standard tokens.")],2),
("case_06cb2164",False,"medium",[
 t("TroveManager.sol:redeemCollateral","business_logic","Complex redemption/hint logic, matches Liquity V1 and appears unmodified."),
 t("TroveManager.sol:batchLiquidateTroves","business_logic","Liquidation accounting; no deviation from Liquity found."),
 t("TroveManager.sol:_redeemCollateralFromTrove","rounding_precision","Partial redemption NICR hint and rounding; canonical."),
 t("TroveManager.sol:_redistributeDebtAndColl","rounding_precision","Redistribution error-correction math; canonical."),
 t("TroveManager.sol:liquidateTroves","business_logic","Sequence liquidation in normal/recovery mode; canonical.")],1),
("case_08725d9b",False,"low",[
 t("USM.sol:checkForFreshOraclePrice","price_oracle_trust","Sole price source is an external Oracle (not in scope) with no staleness or deviation check."),
 t("USM.sol:_defundFum","business_logic","ETH sent after burn/state store but depends on complex pricing; debt-ratio check present."),
 t("USM.sol:ethFromDefund","rounding_precision","Heavy fixed-point exp/pow math; rounding drift possible but bounded."),
 t("USM.sol:fumFromFund","rounding_precision","Geometric-average pricing with unchecked blocks."),
 t("USM.sol:_burnUsm","business_logic","ETH payout via call after state update; reentrancy-safe ordering.")],None),
("case_151dcee8",True,"low",[
 t("Escrow.sol:_finishLiquidateSettle","business_logic","For ERC777 currencies, the liquidator's payment goes through operatorSend, which triggers tokensReceived and credits the liquidator a withdrawable cash balance on top of the payment, creating unbacked credit."),
 t("Escrow.sol:tokensReceived","business_logic","Credits cashBalances on every ERC777 receipt, including internal settlement transfers."),
 t("Escrow.sol:_tokenDeposit","business_logic","ERC777 operatorSend path interacts with the hook credit and is reused by liquidation and settlement."),
 t("ERC1155Trade.sol:safeTransferFrom","access_control","Deposits on behalf of payer/receiver via bridge or approvals; authorization combination is intricate."),
 t("Escrow.sol:_withdraw","reentrancy","ERC777 send hook runs before the batch free-collateral check when checkFC is false.")],None),
("case_1996c0bd",False,"high",[
 t("UniswapV2Factory.sol:swap","business_logic","K invariant check with fee adjustment is correct and matches canonical Uniswap V2."),
 t("UniswapV2Factory.sol:mint","rounding_precision","Canonical liquidity math with MINIMUM_LIQUIDITY lock."),
 t("UniswapV2Factory.sol:burn","reentrancy","Lock-guarded; canonical."),
 t("UniswapV2Factory.sol:createPair","access_control","Permissionless by design; create2 salted per sorted token pair."),
 t("UniswapV2Factory.sol:skim","other","Anyone may skim surplus balance by design.")],4),
("case_1f94083c",False,"medium",[
 t("LibDiamond.sol:diamondCut","access_control","Owner check lives in the DiamondCutFacet (not provided); library itself has none."),
 t("LibDiamond.sol:initializeDiamondCut","arbitrary_external_call","Delegatecalls arbitrary _init; safe only if diamondCut is owner-gated."),
 t("Diamond.sol:fallback","arbitrary_external_call","Delegatecalls to facet by selector; standard EIP-2535."),
 t("LibDiamond.sol:replaceFunctions","business_logic","Standard replace logic; no immutable-function guard issue found."),
 t("LibDiamond.sol:removeFunction","business_logic","Standard swap-and-pop removal.")],None),
]
with open("spike.part1.jsonl","w") as f:
    for cid,b,c,top,p in cases:
        f.write(json.dumps({"case_id":cid,"model":M,"exploitable_bug_found":b,"confidence":c,"top5":top,"precedent_used":p})+"\n")
