# M0 review summary (generated 2026-10-22 13:24 UTC)

Reviewed 30 of 40 sampled incidents. The sample over-weights rare root-cause classes, so weight class-level rates before quoting them.

**30 of these reviews are blind LLM reviews (fable-5.1 (blind LLM review)), not human.** They aren't verified ground truth (PRD REV-3), and they can't measure human review effort.

## Review effort

- Not applicable: no human reviews in this file.

## Scope and source

- Code-level (in scope): 30/30 (100%)
- Slither ran on the chosen victim: 23/30 (77%)
- In scope but no usable source / Slither run: 7
- DeFiHackLabs label (mapped) differs from reviewer's root cause: 30/30 (100%)
- Incidents with more than one causal location: 26/30 (87%)

## Slither coverage (the key M0 number)

- **Strict** (a finding explains the exploit): 1/23 (4%)
- Loose (any finding touches a causal function): 18/23 (78%)
- Denominator: in-scope incidents where Slither ran on the victim. The strict number sets the ceiling
  for pure triage. PRD kill/pivot check: strict below ~30% means beyond-Slither must carry the product.

Finding adjudications (in-scope incidents): unresolved 2083, confirmed_valid 102, confirmed_invalid 70

## Root causes (reviewed)

- business_logic: 10
- access_control: 10
- price_oracle_trust: 9
- input_validation: 6
- governance_design: 3
- arbitrary_external_call: 2
- rounding_precision: 2
- uninitialized_or_unprotected_init: 2
- arithmetic_overflow_or_cast: 1

## Per incident

| Incident | Min | In scope | Slither ran | Explains | Root cause |
|---|---:|---|---|---|---|
| 20260701_edelxstock | 0.0 | y | y | n | price_oracle_trust |
| 20260706_SummerFi | 0.0 | y | y | n | business_logic, price_oracle_trust |
| 20260805_StrongBlock | 0.0 | y | y | n | governance_design |
| 20260806_UnistreetLaunchpad | 0.0 | y | y | n | arbitrary_external_call, input_validation |
| 20260809_USM | 0.0 | y | y | n | business_logic, rounding_precision |
| 20260823_ArrakisGUNI | 0.0 | y | y | n | price_oracle_trust |
| 20260823_TermFinance | 0.0 | y | n | n | governance_design |
| 20260826_EnjinCryptoItems | 0.0 | y | n | n | uninitialized_or_unprotected_init, access_control |
| 20260828_AjnaFinance | 0.0 | y | n | n | business_logic |
| 20260831_BalancerV1BPool | 0.0 | y | y | n | rounding_precision, input_validation |
| 20260831_FloatProtocol | 0.0 | y | y | n | price_oracle_trust |
| 20260901_ReflexerGEB | 0.0 | y | y | n | access_control |
| 20260903_NotionalFinance | 0.0 | y | y | n | arithmetic_overflow_or_cast, business_logic |
| 20260905_Reddio | 0.0 | y | y | n | business_logic, access_control |
| 20260905_SecuredFi | 0.0 | y | y | n | price_oracle_trust |
| 20260908_OrderFactory | 0.0 | y | n | n | access_control, input_validation |
| 20260909_EnsoFinance | 0.0 | y | n | n | price_oracle_trust |
| 20260909_EtherFiAtomicQueue | 0.0 | y | y | y | access_control, input_validation |
| 20260909_OMNI404 | 0.0 | y | y | n | business_logic, input_validation |
| 20260912_SpiralHookV2 | 0.0 | y | n | n | price_oracle_trust, access_control |
| 20260912_YamFinance | 0.0 | y | y | n | governance_design |
| 20260915_RsETHSafeModule | 0.0 | y | y | n | access_control |
| 20260916_Flamincome | 0.0 | y | y | n | price_oracle_trust, business_logic |
| 20260916_Startale | 0.0 | y | y | n | uninitialized_or_unprotected_init |
| 20260926_DAOstack | 0.0 | y | n | n | input_validation, access_control |
| 20260930_MUS | 0.0 | y | y | n | business_logic |
| 20261001_FlashLoopAdapter | 0.0 | y | y | n | access_control, arbitrary_external_call |
| 20261008_X7Finance | 0.0 | y | y | n | business_logic |
| 20261015_KolanHook | 0.0 | y | y | n | price_oracle_trust, access_control |
| 20261017_BiFi | 0.0 | y | y | n | business_logic |
