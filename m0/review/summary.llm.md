# M0 review summary (generated 2026-10-22 12:57 UTC)

Reviewed 40 of 40 sampled incidents. The sample over-weights rare root-cause classes, so weight class-level rates before quoting them.

**40 of these reviews are blind LLM reviews (fable-5.1 (blind LLM review)), not human.** They aren't verified ground truth (PRD REV-3), and they can't measure human review effort.

## Review effort

- Not applicable: no human reviews in this file.

## Scope and source

- Code-level (in scope): 39/40 (98%)
- Slither ran on the chosen victim: 27/39 (69%)
- In scope but no usable source / Slither run: 12
- DeFiHackLabs label (mapped) differs from reviewer's root cause: 6/39 (15%)
- Incidents with more than one causal location: 35/39 (90%)

## Slither coverage (the key M0 number)

- **Strict** (a finding explains the exploit): 3/27 (11%)
- Loose (any finding touches a causal function): 21/27 (78%)
- Denominator: in-scope incidents where Slither ran on the victim. The strict number sets the ceiling
  for pure triage. PRD kill/pivot check: strict below ~30% means beyond-Slither must carry the product.

Finding adjudications (in-scope incidents): unresolved 2707, confirmed_invalid 243, confirmed_valid 36

## LLM proposal vs reviewer (label-quality check)

- Reviews that had a proposal: 40
- In-scope call agreed: 38/40 (95%)
- Victim contract overlap: 39/40 (98%)
- Root cause exact agreement: 25/38 (66%)
- Mechanism exact agreement: 25/38 (66%)
- 'Which finding explains it' exact agreement: 38/38 (100%)
- Blind review: the reviewer never saw the proposals, so this is inter-model agreement (two LLMs judging independently). It isn't accuracy against a human.

## Root causes (reviewed)

- input_validation: 11
- access_control: 8
- business_logic: 8
- uninitialized_or_unprotected_init: 5
- arbitrary_external_call: 5
- price_oracle_trust: 5
- reentrancy: 3
- rounding_precision: 3
- governance_design: 2
- storage_collision: 2
- other: 2
- signature_validation: 2

## Per incident

| Incident | Min | In scope | Slither ran | Explains | Root cause |
|---|---:|---|---|---|---|
| 20210308_DODO | 0.0 | y | n | n | uninitialized_or_unprotected_init |
| 20210607_88mphNFT | 0.0 | y | n | n | uninitialized_or_unprotected_init |
| 20210811_PolyNetwork | 0.0 | y | y | n | access_control, arbitrary_external_call |
| 20210916_SushiSwapMiso | 0.0 | y | n | n | business_logic |
| 20211221_VisorFinance | 0.0 | y | y | n | input_validation |
| 20220326_Auctus | 0.0 | y | y | n | arbitrary_external_call |
| 20220327_RevestFinance | 0.0 | y | y | y | reentrancy |
| 20220416_BeanstalkFarms | 0.0 | y | y | n | governance_design |
| 20220430_RariCapitalFeiProtocol | 0.0 | y | y | y | reentrancy |
| 20220723_Audius | 0.0 | y | y | n | storage_collision, uninitialized_or_unprotected_init |
| 20221009_XaveFinance | 0.0 | y | y | n | governance_design |
| 20221017_UeriiToken | 0.0 | y | y | n | access_control |
| 20230224_EFVault | 0.0 | y | y | n | storage_collision |
| 20230413_yearnFinance | 0.0 | y | n | n | other, business_logic |
| 20230606_VINU | 0.0 | y | y | n | access_control, input_validation |
| 20230722_ConicFinance02 | 0.0 | y | y | n | price_oracle_trust |
| 20230902_DAppSocial | 0.0 | y | n | n | business_logic, input_validation |
| 20231122_KyberSwap | 0.0 | y | y | n | rounding_precision |
| 20231216_GoodDollar | 0.0 | y | y | n | input_validation, reentrancy |
| 20240122_DAOSoulMate | 0.0 | y | n | n | access_control |
| 20240202_ADC | 0.0 | y | y | n | access_control |
| 20240223_BlueberryProtocol | 0.0 | y | y | n | business_logic, price_oracle_trust |
| 20240309_UnizenIO | 0.0 | y | y | n | arbitrary_external_call, input_validation |
| 20240430_PikeFinance | 0.0 | y | n | n | uninitialized_or_unprotected_init |
| 20240705_DeFiPlaza | 0.0 | y | n | n | rounding_precision, business_logic |
| 20240724_Spectrafinance | 0.0 | y | y | n | input_validation, arbitrary_external_call |
| 20250104_SorStaking | 0.0 | y | y | n | business_logic |
| 20250208_PeapodsFinance | 0.0 | y | y | n | input_validation, price_oracle_trust |
| 20250407_AmpKashi | 0.0 | y | n | n | price_oracle_trust |
| 20250705_ActivePoolScrvUsd | 0.0 | n | y | n | other |
| 20250729_AnyswapWETHPermit | 0.0 | y | y | y | signature_validation, input_validation |
| 20251103_BalancerV2 | 0.0 | y | y | n | rounding_precision |
| 20251110_DRLVaultV3 | 0.0 | y | n | n | price_oracle_trust, access_control |
| 20260423_GiddyVaultV3 | 0.0 | y | y | n | signature_validation |
| 20260505_Ekubo | 0.0 | y | n | n | input_validation, access_control |
| 20260617_AztecV1 | 0.0 | y | y | n | other, input_validation |
| 20260806_UnistreetLaunchpad | 0.0 | y | y | n | arbitrary_external_call, input_validation |
| 20260826_EnjinCryptoItems | 0.0 | y | n | n | uninitialized_or_unprotected_init, access_control |
| 20260909_OMNI404 | 0.0 | y | y | n | business_logic |
| 20261017_BiFi | 0.0 | y | y | n | business_logic |
