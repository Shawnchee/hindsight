#!/usr/bin/env python3
"""Map every distinct DeFiHackLabs raw label on an Ethereum incident to the PRD §8.2 taxonomy.

This is a hand-written lookup table (reviewed by reading each label), not a classifier.
Mappings are made from the label TEXT. Where a label is ambiguous it stays `other` with
`low` confidence and plausible classes go in `candidates` instead of a guess.

Confidence:
  high - the label names one taxonomy class directly and unambiguously
  med  - the label implies a class, but DeFiHackLabs uses the term loosely (e.g. the
         "Business Logic Flaw" catch-all), the label names two causes, or it describes a
         mechanism rather than a root cause
  low  - ambiguous; root_cause left as `other` unless noted

Usage:
    python3 -I m0/scripts/catalog/build_label_map.py \
        --incidents m0/catalog/ethereum_incidents.csv --out m0/catalog/label_map.csv
Fails (exit 1) if a label in the incidents file is missing from the table.
"""
import argparse
import csv
import sys
from collections import Counter

ROOT = {"access_control", "price_oracle_trust", "rounding_precision", "input_validation",
        "reentrancy", "business_logic", "signature_replay", "uninitialized_or_unprotected_init",
        "storage_collision", "arbitrary_external_call", "governance_design", "other"}
MECH = {"flash_loan", "price_manipulation", "reentrant_call", "crafted_calldata",
        "governance_vote", "donation", "other"}

AC, PO, RP, IV, RE, BL, SR, UI, SC, AEC, GD, OT = (
    "access_control", "price_oracle_trust", "rounding_precision", "input_validation",
    "reentrancy", "business_logic", "signature_replay", "uninitialized_or_unprotected_init",
    "storage_collision", "arbitrary_external_call", "governance_design", "other")

CATCHALL = "DeFiHackLabs catch-all term; expect reclassification on review"
ARITH = "taxonomy gap: no arithmetic overflow/underflow/truncation class in v0"
SIG = "taxonomy gap: v0 only has signature_replay; this is broader signature/permit verification"
OFFCHAIN = "not a contract-code bug; out of scope for code triage"
MECH_ONLY = "label names the mechanism; root cause usually trusting a manipulable price"

# raw_label -> (root_cause, mechanism ('' if not implied; ';' joins several), confidence,
#               candidates, note)
M = {
    # --- access control
    "Access Control": (AC, "", "high", "", ""),
    "Access control": (AC, "", "high", "", ""),
    "Accesscontrol": (AC, "", "high", "", ""),
    "Bad Access Controal": (AC, "", "high", "", ""),
    "Incorrect Access Control": (AC, "", "high", "", ""),
    "Incorrect access control": (AC, "", "high", "", ""),
    "incorrect-access-control": (AC, "", "high", "", ""),
    "Insufficient access control": (AC, "", "high", "", ""),
    "Lack of access control": (AC, "", "high", "", ""),
    "lack of access control": (AC, "", "high", "", ""),
    "lack-of-access-control": (AC, "", "high", "", ""),
    "Missing caller check": (AC, "", "high", "", ""),
    "SquidRouterModule Missing Caller Check": (AC, "", "high", "", ""),
    "Unauthorized TransferFrom": (AC, "", "high", "", ""),
    "Wrong visibility in function": (AC, "", "high", "", ""),
    "missing access control on createOrderForBuyer drains buyer accounts": (AC, "", "high", "", ""),
    "missing solver access control drains victim allowances": (AC, "", "high", "", ""),
    "Arbitrary Mint": (AC, "", "med", "input_validation", "unrestricted mint; could be a validation bug"),
    "Broken transferFrom Allowance Check": (AC, "", "med", "business_logic", ""),
    "Missing ERC4626 allowance check": (AC, "", "med", "input_validation", ""),
    "Tax wallet allowance bypass": (AC, "", "med", "business_logic", ""),
    "Shared GebProxyActions library registered as SAFE owner": (AC, "", "med", "", ""),
    "Owner-privileged JAKE burn reserve drain": (AC, "", "med", "other", "may be an owner rug rather than a bug"),
    "Fake Uniswap Callback": (AC, "crafted_calldata", "med", "input_validation", "callback caller not verified"),
    "Unchecked Flash Loan Callback": (AC, "crafted_calldata", "med", "input_validation", "callback caller not verified"),
    "Verify flashLoan Callback": (AC, "crafted_calldata", "med", "input_validation", "callback caller not verified"),
    "Bridge, getting around modifier through cross-chain message": (AC, "crafted_calldata", "med", "input_validation", ""),
    "permissionless newOrganization lets an attacker hijack an existing Reputation contract and drain the Avatar": (AC, "", "med", "business_logic", "prose label"),
    "nested self-referential multicall authorization bypass drains Gnosis Safe via DELEGATECALL": (AC, "crafted_calldata", "med", "arbitrary_external_call", "prose label"),
    "a Safe module authenticates its caller by asking that caller whether the module is enabled (self-attestation) and then makes an unconstrained call to a caller-supplied router, letting a fake Safe drive the adapter into draining real Safes that enabled it": (AC, "crafted_calldata", "med", "arbitrary_external_call", "prose label; two causes"),
    # --- arbitrary external call
    "Arbitrary Call": (AEC, "crafted_calldata", "high", "", ""),
    "Arbitrary call": (AEC, "crafted_calldata", "high", "", ""),
    "Arbitrary Call Error": (AEC, "crafted_calldata", "high", "", ""),
    "Arbitrary External Call": (AEC, "crafted_calldata", "high", "", ""),
    "Arbitrary External Call Vulnerability": (AEC, "crafted_calldata", "high", "", ""),
    "Arbitrary external call vulnerability": (AEC, "crafted_calldata", "high", "", ""),
    "arbitrary call injection via unvalidated launch forwarding": (AEC, "crafted_calldata", "high", "", ""),
    "unverified external call": (AEC, "crafted_calldata", "med", "input_validation", ""),
    # --- input validation
    "Incorrect input validation": (IV, "", "high", "", ""),
    "Incorrect Input Validation": (IV, "", "high", "", ""),
    "Insufficient validation": (IV, "", "high", "", ""),
    "Insufficient Validation": (IV, "", "high", "", ""),
    "Insufficient Token Validation": (IV, "", "high", "", ""),
    "No input validation": (IV, "", "high", "", ""),
    "Unchecked User Input": (IV, "", "high", "", ""),
    "lack of validation": (IV, "", "high", "", ""),
    "lack of validation data": (IV, "crafted_calldata", "high", "", ""),
    "lack of validation dst address": (IV, "", "high", "", ""),
    "lack of validation userData": (IV, "crafted_calldata", "high", "", ""),
    "Lack of calldata validation": (IV, "crafted_calldata", "high", "", ""),
    "Arbitrary Address Spoofing Attack": (IV, "crafted_calldata", "med", "access_control", ""),
    "Arbitrary Yul Calldata": (IV, "crafted_calldata", "med", "arbitrary_external_call", "malformed calldata parsed in assembly"),
    "Bridge address(0).safeTransferFrom() does not revert": (IV, "", "med", "", ""),
    "Business Logic Flaw : Incorrect acceptable merkle-root checks": (IV, "", "med", "business_logic", ""),
    "Business Logic Flaw : Missing Check For Number of NFT to Mint": (IV, "", "med", "business_logic", ""),
    "Fake Market": (IV, "", "med", "", "unvalidated market address"),
    "Fake terminal loan source validation bypass": (IV, "", "med", "", ""),
    "Infinite Mint via unvalidated ERC4626 mint": (IV, "", "med", "business_logic", ""),
    "escapeHatch Proof-Forgery (permissionless RollupProcessor exit)": (IV, "crafted_calldata", "med", "business_logic", "proof not validated"),
    "numRealTxs Proof/Settlement Mismatch (permissionless RollupProcessorV3)": (IV, "crafted_calldata", "med", "business_logic", ""),
    "Lack of Input Validation & Reentrancy": (IV, "reentrant_call", "med", "reentrancy", "two causes"),
    # --- reentrancy
    "Reentrancy": (RE, "reentrant_call", "high", "", ""),
    "reentrancy": (RE, "reentrant_call", "high", "", ""),
    "ERC777 Reentrancy": (RE, "reentrant_call", "high", "", ""),
    "Cross Contract Reentrancy": (RE, "reentrant_call", "high", "", ""),
    "Read-Only-Reentrancy": (RE, "reentrant_call", "high", "", ""),
    "Read-Only-Reentrancy && MisConfiguration": (RE, "reentrant_call", "high", "", ""),
    "Vyper Compiler Bug && Reentrancy": (RE, "reentrant_call", "high", "", "compiler bug broke the reentrancy lock; source-level guard looks correct"),
    "Flashloan Attack + Reentrancy": (RE, "flash_loan;reentrant_call", "med", "", ""),
    "Insufficient validation + Reentrancy": (RE, "reentrant_call", "med", "input_validation", "two causes"),
    "Reentrancy && Business Logic Flaw": (RE, "reentrant_call", "med", "business_logic", "two causes"),
    "Reentrancy and Reward Manipulation": (RE, "reentrant_call", "med", "business_logic", "two causes"),
    # --- price / oracle trust
    "Price Oracle Manipulation": (PO, "price_manipulation", "high", "", ""),
    "Flashloan & Price Oracle Manipulation": (PO, "flash_loan;price_manipulation", "high", "", ""),
    "Oracle bad price": (PO, "", "high", "", ""),
    "Overpriced Asset in Oracle": (PO, "", "high", "", ""),
    "Price Out Of Date": (PO, "", "high", "", "stale price"),
    "Vulnerable Price Dependency": (PO, "price_manipulation", "high", "", ""),
    "Uniswap V3 spot-price manipulation of vault mint/burn": (PO, "price_manipulation", "high", "", ""),
    "Uniswap V3 spot price manipulation of Hypervisor LP shares": (PO, "price_manipulation", "high", "", "prose label"),
    "short-window Uniswap V3 TWAP oracle enables ~9x overvalued strategy deposit": (PO, "price_manipulation", "high", "", "prose label"),
    "same-block self-trade manipulates getMarketUnitPrice to fabricate collateral": (PO, "price_manipulation", "high", "", "prose label"),
    "Price Manipulation": (PO, "price_manipulation", "med", "business_logic", MECH_ONLY),
    "Price manipulation": (PO, "price_manipulation", "med", "business_logic", MECH_ONLY),
    "price manipulation": (PO, "price_manipulation", "med", "business_logic", MECH_ONLY),
    "FlashLoan price manipulation": (PO, "flash_loan;price_manipulation", "med", "business_logic", MECH_ONLY),
    "Pair Balance Manipulation": (PO, "price_manipulation", "med", "business_logic", MECH_ONLY),
    "Price-caching Design Defect": (PO, "", "med", "business_logic", ""),
    "Flashloan + scaledBalanceOf Manipulation": (PO, "flash_loan;price_manipulation", "med", "business_logic", "collateral valued from a manipulable balance"),
    "FleetCommander NAV Inflation via Depegged xUSD": (PO, "other", "med", "business_logic", "NAV trusted a depegged asset price"),
    "Uniswap V4 spot-price borrow plus tx.origin-keyed same-block guard bypass": (PO, "price_manipulation", "med", "access_control", "prose label; two causes"),
    "KolanHook settles its escrowed ETH buy-windows at the same Uniswap v4 pool's instantaneous spot price with no TWAP or bound and accept() is ungated once a window has expired, so the attacker flash-borrows 6.7 WETH from Balancer, swaps it to move the KLN spot, then calls accept() on two expired windows it does not own so _closeWindow() mispositions their escrowed ETH as single-sided liquidity around the manipulated price and runs an unbounded buyback, and reverses the swap back through that freshly placed ETH liquidity before repaying the loan for a 1.279453 ETH net gain": (PO, "flash_loan;price_manipulation", "med", "access_control", "prose label; two causes"),
    "AMP Collateral Borrow Price Manipulation": (PO, "price_manipulation", "low", "reentrancy", "label text only; AMP is an ERC777-style token, verify cause on review"),
    # --- rounding / precision
    "Precision Loss": (RP, "", "high", "", ""),
    "precision loss": (RP, "", "high", "", ""),
    "loss of precision": (RP, "", "high", "", ""),
    "Precission Loss": (RP, "", "high", "", ""),
    "Precission Loss Vulnerability": (RP, "", "high", "", ""),
    "Div Precision Loss": (RP, "", "high", "", ""),
    "Vault Share Rounding Manipulation": (RP, "", "high", "", ""),
    "defund() price split-invariance rounding exploit": (RP, "", "high", "", ""),
    "joinswapPoolAmountOut rounding drain across 5 pools": (RP, "", "high", "", ""),
    "CompoundV2 Inflation Attack": (RP, "donation", "high", "", "empty-market exchange-rate inflation"),
    "Donate Inflation ExchangeRate & Rounding Error": (RP, "donation", "high", "", ""),
    "Donate Inflation ExchangeRate && Rounding Error": (RP, "donation", "high", "", ""),
    "Inflation Attack": (RP, "donation", "high", "", ""),
    "Rounding Error && Business Logic Flaw": (RP, "", "med", "business_logic", "two causes"),
    # --- signatures (v0 class is narrow)
    "Signature Replay": (SR, "", "high", "", ""),
    "Broken Signature Verification": (SR, "", "med", "input_validation", SIG),
    "Incomplete Signature Coverage": (SR, "", "med", "input_validation", SIG),
    "Invalid signature verification": (SR, "", "med", "input_validation", SIG),
    "Signature Verification Bypass": (SR, "", "med", "input_validation", SIG),
    "Permit Validation Bypass": (SR, "", "med", "input_validation", SIG),
    # --- init / storage
    "Uninitialized Proxy": (UI, "", "high", "", ""),
    "delegatecall to unprotected initWallet": (UI, "", "high", "", ""),
    "unprotected registry reinitialization, manager takeover": (UI, "", "high", "", ""),
    "transient storage init flag outlives the constructor and lets anyone reinitialize an ERC7579 account and drain it": (UI, "", "high", "", "prose label"),
    "'Accidentally Killed It'": (UI, "", "med", "access_control", "label is not descriptive; mapped from the well-known 2017 Parity library incident"),
    "Storage Collision": (SC, "", "high", "", ""),
    "Storage SLOT1 collision": (SC, "", "high", "", ""),
    "Storage Collision & Malicious Proposal": (SC, "governance_vote", "high", "governance_design", ""),
    # --- governance
    "Malicious Proposal Mint & Transfer Ownership": (GD, "governance_vote", "high", "", ""),
    "Governance capture via thinly-wrapped Aragon voting power": (GD, "governance_vote", "high", "", ""),
    "governance takeover of an abandoned Governor": (GD, "governance_vote", "high", "", ""),
    "dormant-DAO quorum governance takeover drains legacy UMA farming contracts": (GD, "governance_vote", "high", "", "prose label"),
    "DAO + Flashloan": (GD, "flash_loan;governance_vote", "med", "", ""),
    "Governance-controlled token mint and Balancer pool drain": (GD, "governance_vote", "med", "access_control", ""),
    # --- business logic
    "Business Logic Flaw": (BL, "", "med", "", CATCHALL),
    "business logic flaw": (BL, "", "med", "", CATCHALL),
    "Business Logic": (BL, "", "med", "", CATCHALL),
    "Logic Flaw": (BL, "", "med", "", CATCHALL),
    "logic flaw": (BL, "", "med", "", CATCHALL),
    "Fault logic": (BL, "", "med", "", CATCHALL),
    "Incorrect Logic Check": (BL, "", "med", "input_validation", ""),
    "Bridge, logic flaw": (BL, "", "med", "", CATCHALL),
    "Repeated Reward Claim - Logic Flaw": (BL, "", "med", "", ""),
    "Rebasing logic issue": (BL, "", "med", "", ""),
    "Reflection token": (BL, "price_manipulation", "med", "", "reflection/fee-on-transfer accounting vs AMM pair reserves"),
    "Pair Manipulation With Transfer Function": (BL, "price_manipulation", "med", "", "token transfer hook moves pair balances"),
    "Incorrect Reward calculation": (BL, "", "med", "rounding_precision", ""),
    "Incorrect reward calculation": (BL, "", "med", "rounding_precision", ""),
    "Incorrect dividends calculation": (BL, "", "med", "rounding_precision", ""),
    "Incorrect calculation via cached data": (BL, "", "med", "", ""),
    "Reward Accounting Flaw": (BL, "", "med", "", ""),
    "Claim Accounting": (BL, "", "med", "", ""),
    "Native surplus accounting flaw": (BL, "", "med", "", ""),
    "Index vault component-share accounting flaw": (BL, "", "med", "rounding_precision", ""),
    "Duplicate xLOOT Redemption": (BL, "", "med", "", ""),
    "Bypassed Insolvency Check": (BL, "", "med", "input_validation", ""),
    "Bad HealthFactor Check": (BL, "", "med", "input_validation", ""),
    "Constructor Dividend Checkpoint Bypass": (BL, "", "med", "", ""),
    "Miscalculation on \\_spendAllowance": (BL, "", "med", "access_control", ""),
    "ERC-404 dual ID/amount transfer interpretation drains pool WETH": (BL, "", "med", "input_validation", ""),
    "_englove Sybil Incentive Abuse": (BL, "", "med", "", ""),
    "cross-share-class balance double-count via permissionless registerErc20": (BL, "", "med", "access_control", ""),
    "liquidation accounting manipulation via self-controlled auction": (BL, "", "med", "", ""),
    "msgValue in loop": (BL, "", "med", "", "msg.value reused across loop iterations"),
    "error k value Attack": (BL, "", "med", "rounding_precision", "AMM K-invariant check wrong"),
    "Lack Slippage Protection": (BL, "price_manipulation", "med", "input_validation", "missing slippage bound"),
    "Lack of slippage protection": (BL, "price_manipulation", "med", "input_validation", "missing slippage bound"),
    "Slippage proection absent": (BL, "price_manipulation", "med", "input_validation", "missing slippage bound"),
    "permissionless Convex stakeFor inflates Strategy NAV and lets VaultYUSDT overpay on withdrawAll": (BL, "donation", "med", "price_oracle_trust;access_control", "prose label"),
    "deposit refunds a first-deposit bonus and also credits it as withdrawable allocation, so a single deposit-withdraw from a fresh address returns more ETH than deposited": (BL, "", "med", "", "prose label"),
    "X7Pioneer's claimRewards() adds the unaccounted ETH balance delta into totalRewards on every call but only refreshes lastETHBalance when claimable is non-zero, so calling it with an empty tokenIds array re-counts the same donated delta each time and inflates the per-token reward until a single owned NFT drains the whole pool, the ~26.96 ETH donation supplied by a flash loan and repaid from the drain": (BL, "flash_loan;donation", "med", "", "prose label"),
    "the idle BiFi USDT market freezes its per-block exchange rate and stores the entire 264,059-block inactive gap on the first action, then the interest model charges that full ~36 day gap of deposit interest on every later action in the same block at a utilization rate the attacker sets through permissionless deposit and borrow, so the attacker flash-borrows 40.5M USDT from Morpho, deposits it to seed the frozen gap, borrows to spike utilization, runs a repay and withdraw loop twice to cash out the inflated deposit interest, then repays the loan and swaps the 165,574 USDT surplus to 68.0572 WETH": (BL, "flash_loan", "med", "", "prose label"),
    # --- other: taxonomy gaps (arithmetic, randomness, DoS)
    "Integer Overflow": (OT, "", "med", "", ARITH),
    "Integer Underflow": (OT, "", "med", "", ARITH),
    "Overflow": (OT, "", "med", "", ARITH),
    "OverFlow": (OT, "", "med", "", ARITH),
    "Underflow": (OT, "", "med", "", ARITH),
    "unsafecast": (OT, "", "med", "", ARITH),
    "ERC1155 fCash mint overflow drains escrow": (OT, "", "med", "business_logic", ARITH),
    "Predicting Random Numbers": (OT, "", "med", "", "taxonomy gap: weak on-chain randomness"),
    "Denial of Service": (OT, "", "med", "business_logic", "impact-style label; v0 has no DoS class"),
    # --- other: not a contract-code bug
    "Private key compromised": (OT, "", "high", "", OFFCHAIN),
    "Rug pull": (OT, "", "high", "", OFFCHAIN + " (malicious owner)"),
    "Rug Pull": (OT, "", "high", "", OFFCHAIN + " (malicious owner)"),
    "Phishing attack": (OT, "", "high", "", OFFCHAIN),
    "Vulnerability Disclosure": (OT, "", "low", "", "disclosure, not an exploit; README says no loss occurred"),
    # --- other: ambiguous, left unguessed
    "Flashloan Attack": (OT, "flash_loan", "low", "", "mechanism only"),
    "Flashloan": (OT, "flash_loan", "low", "", "mechanism only"),
    "FlashLoan": (OT, "flash_loan", "low", "", "mechanism only"),
    "Sandwich attack": (OT, "price_manipulation", "low", "business_logic", "mechanism only"),
    "sandwich ack": (OT, "price_manipulation", "low", "business_logic", "mechanism only"),
    "Pool manipulation": (OT, "price_manipulation", "low", "price_oracle_trust;business_logic", "mechanism only"),
    "Share price manipulation": (OT, "price_manipulation", "low", "price_oracle_trust;rounding_precision", "vault-inflation or share-price-as-oracle; can't tell from label"),
    "Share Price Manipulation": (OT, "price_manipulation", "low", "price_oracle_trust;rounding_precision", "vault-inflation or share-price-as-oracle; can't tell from label"),
    "Swap Metapool Attack": (OT, "price_manipulation", "low", "business_logic;price_oracle_trust", ""),
    "Swap ETH/BTC 1/1 in mint function": (OT, "", "low", "business_logic;price_oracle_trust", "hard-coded 1:1 price"),
    "Manipulation of funds through fluctuations in the amount of exchangeable assets": (OT, "price_manipulation", "low", "price_oracle_trust;business_logic", "prose label"),
    "Incorrect calculation": (OT, "", "low", "business_logic;rounding_precision", ""),
    "Unsafe Math": (OT, "", "low", "rounding_precision", ARITH),
    "Misconfiguration": (OT, "", "low", "access_control;governance_design", ""),
    "Bridge": (OT, "", "low", "", "category, not a cause"),
    "Bridges": (OT, "", "low", "", "category, not a cause"),
    "DAO": (OT, "", "low", "governance_design", "category, not a cause"),
    "Urgent Redemption": (OT, "", "low", "business_logic", "protocol-specific term"),
    "Fixed Order Swap": (OT, "", "low", "business_logic", ""),
    "Fixed Reward Redemption": (OT, "", "low", "business_logic", ""),
    "Arbitrage": (OT, "", "low", "business_logic;price_oracle_trust", ""),
    "Infinite Number of Loans": (OT, "", "low", "business_logic", ""),
    "Liquidity Migration Exploit": (OT, "", "low", "input_validation;business_logic", ""),
    "Incorrect transfer": (OT, "", "low", "business_logic", ""),
    "Any token is destroyed": (OT, "", "low", "access_control;input_validation", ""),
    "bad function implementation": (OT, "", "low", "business_logic", ""),
    "Parameter manipulation": (OT, "", "low", "input_validation", ""),
    "Custom Approval Logic": (OT, "", "low", "access_control;business_logic", ""),
    "AllowanceTarget approval drain": (OT, "", "low", "arbitrary_external_call;access_control", ""),
    "Stale Approval": (OT, "", "low", "arbitrary_external_call;access_control", ""),
    "Protocol Token incompatible": (OT, "", "low", "business_logic", ""),
    "Token Incompatible": (OT, "", "low", "business_logic", ""),
    "proof_id Accounting Bypass (whitehat reproduction)": (OT, "", "low", "business_logic;input_validation", ""),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--incidents", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    for k, (rc, mech, conf, cand, _) in M.items():
        assert rc in ROOT, (k, rc)
        assert conf in ("high", "med", "low"), k
        assert all(x in MECH for x in mech.split(";") if x), (k, mech)
        assert all(x in ROOT for x in cand.split(";") if x), (k, cand)
    rows = list(csv.DictReader(open(a.incidents, encoding="utf-8")))
    counts = Counter(r["raw_label"] for r in rows)
    missing = [l for l in counts if l not in M]
    if missing:
        print("Unmapped labels:", *missing, sep="\n  ", file=sys.stderr)
        return 1
    out = []
    for lab, n in sorted(counts.items(), key=lambda x: (-x[1], x[0].lower())):
        rc, mech, conf, cand, note = M[lab]
        out.append({"raw_label": lab, "n_ethereum_incidents": n, "root_cause": rc,
                    "mechanism": mech, "confidence": conf, "candidates": cand, "note": note})
    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    by_conf = Counter(o["confidence"] for o in out)
    inc_conf = Counter()
    for o in out:
        inc_conf[o["confidence"]] += o["n_ethereum_incidents"]
    rc_inc = Counter()
    for o in out:
        rc_inc[o["root_cause"]] += o["n_ethereum_incidents"]
    print(f"distinct labels: {len(out)}; by confidence (labels): {dict(by_conf)}; "
          f"by confidence (incidents): {dict(inc_conf)}")
    print("incidents by root_cause:", dict(rc_inc.most_common()))
    unused = [k for k in M if k not in counts]
    if unused:
        print(f"note: {len(unused)} table entries not used by this incidents file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
