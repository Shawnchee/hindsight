# M0 incident catalog (DeFiHackLabs, Ethereum mainnet)

The catalog for the M0 spike (PRD §15). It is built from a read-only clone of
[DeFiHackLabs](https://github.com/SunWeb3Sec/DeFiHackLabs) (Apache-2.0, © SunWeb3Sec and
contributors; keep this attribution with any derived data).

Built from DeFiHackLabs commit `23c7bd83ccb4524972a9493617fcc8764ab6269b` (2026-10-21).

## Files

| File | What it is |
|---|---|
| `ethereum_incidents.csv` | One row per Ethereum mainnet README entry (357). Extracted fields only, no taxonomy. |
| `all_incidents.csv` | The same extraction for every chain (899). Intermediate; kept for the chain-mix numbers. |
| `summary.md` | Generated: per-year counts, chain mix, why chains were unresolved, unreferenced PoCs. |
| `label_map.csv` | Every distinct raw label on an Ethereum incident (210) mapped to the PRD §8.2 taxonomy. Hand-written table. |
| `m0_sample.csv` | The 40-incident stratified sample for the M0 hand review, with `why_picked`. |

Key columns in `ethereum_incidents.csv`:
- `fork_chain` is the first `createSelectFork(...)` argument (or `createFork` if there is none), resolved from an alias (`"mainnet"`), an RPC URL host, or a `string constant` in the same file. Anything else is `unresolved`.
- `chain` is `fork_chain`, except when that is unresolved and the header's explorer links point at exactly one chain (`chain_source = header_explorer_fallback`, 3 rows).
- `victim_addresses`, `attack_contract_addresses`, `attacker_eoa_addresses` and `attack_tx_hashes` come from the `Key : value` lines in the PoC header comments. They're blank when the header doesn't state them.
- `loss_readme` is the README's `Lost:` line, and `loss_header` is the PoC's `Total Lost` / `Profit` line. Both are verbatim text, not normalised.
- `header_has_analysis` is `yes` when the header has 3 or more lines of prose beyond the key/value lines, meaning it carries a root-cause write-up.

## Regenerate

Run from the repo root. The clone is untrusted data: the scripts only read text from it, they live outside it, and every Python call uses `-I` (isolated mode, so nothing in the clone or the current directory can be imported).

```sh
# 1. Fetch (shallow, no submodules, hooks disabled)
mkdir -p m0/data/catalog
git -c core.hooksPath=/dev/null clone --depth 1 --no-recurse-submodules \
    https://github.com/SunWeb3Sec/DeFiHackLabs m0/data/catalog/dhl

# 2. Parse README index + PoC headers -> all_incidents.csv, ethereum_incidents.csv, summary.md
python3 -I m0/scripts/catalog/parse_dhl.py --dhl m0/data/catalog/dhl --out m0/catalog

# 3. Label map (exits 1 and lists the labels if a new one has no table entry)
python3 -I m0/scripts/catalog/build_label_map.py \
    --incidents m0/catalog/ethereum_incidents.csv --out m0/catalog/label_map.csv

# 4. Stratified sample (deterministic; fixed seed)
python3 -I m0/scripts/catalog/build_m0_sample.py --dhl m0/data/catalog/dhl \
    --incidents m0/catalog/ethereum_incidents.csv --labels m0/catalog/label_map.csv \
    --out m0/catalog/m0_sample.csv --n 40
```

A newer clone will change the counts and may add labels. Step 3 then fails until someone adds the new labels to the table in `build_label_map.py`, which is intended. Re-pin the commit hash above when you regenerate.

## Counts (measured on the commit above)

- **899** README entries across all chains. **357** are Ethereum mainnet: 354 by fork call, 3 by header fallback.
- Fork chain unresolved: **8 of 899** entries.
  - 6 pass the RPC through a function parameter or `vm.envString`/`vm.envOr`.
  - 1 is an identifier with no constant.
  - 1 README entry (`20251004_Abracadabra`) links to a PoC that doesn't exist.
  - 5 of the 8 were recovered from header explorer links, which leaves 3 unresolved.
  - Among the 357 Ethereum incidents, 3 depend on that fallback: `20170719_ParityMultisig`, `20230715_USDTStakingContract28` and `20240307_GHT`.
- Ethereum per year:

  | Year | 2017 | 2018 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
  |---|---|---|---|---|---|---|---|---|---|
  | Count | 2 | 3 | 9 | 18 | 49 | 77 | 82 | 58 | 59 |

- Last 12 months (from 2025-10-22): 159 entries, of which Ethereum 62, BSC 52, Base 14, Polygon 13, Arbitrum 6, other 11 and unresolved 1. PRD §3 said Ethereum 58, BSC 44 and **unresolved 22**. Most of the difference is that this parser resolves RPC URLs and string constants. Update §3.
- 3 `*_exp.sol` files aren't referenced by any README entry: `SheepFarm2`, `WiseLending03` and `ThetanutsFi`. They aren't in the catalog.
- Header fields filled, out of the 357 Ethereum incidents:

  | Field | Filled |
  |---|---:|
  | Attack tx | 280 |
  | Attacker EOA | 270 |
  | Attack contract | 229 |
  | Victim address | 212 |
  | README loss | 343 |

  The victim-address gap is real: older headers often list only the attacker. Recover the victim from the tx during M0.
- Label map: 210 distinct raw labels.

  | Confidence | Labels | Incidents |
  |---|---:|---:|
  | high | 82 | 159 |
  | med | 93 | 157 |
  | low | 35 | 41 |

  Incidents by mapped root cause:

  | Root cause | Incidents |
  |---|---:|
  | business_logic | 80 |
  | access_control | 58 |
  | other | 56 |
  | price_oracle_trust | 43 |
  | input_validation | 34 |
  | reentrancy | 26 |
  | arbitrary_external_call | 23 |
  | rounding_precision | 17 |
  | signature_replay | 6 |
  | governance_design | 6 |
  | uninitialized_or_unprotected_init | 5 |
  | storage_collision | 3 |

## The M0 sample

40 incidents from 336 candidates. The candidates are Ethereum incidents from 2021–2026 with a PoC on disk, excluding 7 with an off-chain cause (key compromise, rug, phishing) or that are disclosure-only.

- **Year:** 2021: 5 (only 18 exist), then 7 each for 2022–2026.
- **Root cause** (targets: a floor of 2 per class, the rest roughly in proportion to the population, `other` capped at 3):

  | Root cause | Sampled |
  |---|---:|
  | business_logic | 6 |
  | access_control | 5 |
  | price_oracle_trust | 5 |
  | input_validation | 4 |
  | reentrancy | 3 |
  | arbitrary_external_call | 3 |
  | rounding_precision | 3 |
  | other | 3 |
  | signature_replay | 2 |
  | governance_design | 2 |
  | uninitialized_or_unprotected_init | 2 |
  | storage_collision | 2 |

  Rare classes are over-sampled relative to the population. Weight by class before quoting any rate as a population estimate.
- **Complexity proxy:** 20 `multi_step`, 20 `single_function`.
- **Loss:** 8 under $100K, 8 at $100K–1M, 8 at $1M–10M, 7 at ≥ $10M, and 9 unknown or not in USD.
- **Label confidence:** 18 high, 18 med, 4 low.
- At most one incident per protocol-name stem (first five letters of the name).

## Caveats

- **Answer leakage: never feed these into eval inputs.** CLAUDE.md requires eval inputs to have PoC header comments and write-ups stripped. Three things in this catalog carry the answer:
  1. **PoC header comments.** 73 of 357 Ethereum PoCs (48 of the 59 from 2026) have a prose root-cause write-up in the header.
  2. **The README label itself.** Recent labels are often a full write-up (15 Ethereum labels run past 8 words; some name the buggy function and the fix), so `raw_label` is answer text too.
  3. **README `Lost:` lines and PoC filenames.** These sometimes name the mechanism.

  `ethereum_incidents.csv`, `label_map.csv` and `m0_sample.csv` are reviewer and ground-truth material, not model inputs.
- **The complexity proxy measures the PoC, not the bug.** It's `multi_step` when the PoC has ≥ 8 distinct hard-coded addresses or ≥ 130 non-comment lines. Long interface boilerplate inflates it. Reviewers should overwrite it with the real answer: one obvious function, or several functions or contracts.
- **The label map is label-text only.** It isn't checked against the incidents. Two examples where it's probably wrong:
  - `AMP Collateral Borrow Price Manipulation` (flagged low).
  - `Bridge` on Ronin, which was a key compromise. It's mapped `other`/low, but the incident is off-chain and should be excluded.

  `Business Logic Flaw` / `Logic Flaw` (80 incidents, mapped med) is a catch-all and will split on review. "Price Manipulation" names a mechanism, so its root-cause mapping is med.
- **Taxonomy gaps found while mapping** (inputs to the v0 → v1 revision in §8.2):
  - There is no class for arithmetic overflow, underflow or unsafe cast: 7 labels, mapped `other`/med.
  - `signature_replay` is too narrow for broken signature or permit verification: 5 labels, mapped to it at med.
  - There is no class for weak randomness or DoS.
  - Missing-slippage labels are mapped to `business_logic`, which is debatable.
- **Not every entry is an exploit.** `20260414_SaturnProtocol` is a disclosure with no loss, and some are whitehat reproductions. The off-chain ones are excluded from the sample but left in the incidents file.
- **Loss strings are free text** in mixed units (ETH, tokens, USD, "~$10 ETH"). `loss_usd_est` in the sample is a best-effort parse of USD-denominated strings only.
- **Exploit date ≠ code date.** Many 2025–26 entries hit dormant 2020–21 contracts (PRD §3), so the chronological split must use `first_seen_at`, not deployment date.
- **Chain coverage is what DeFiHackLabs covers.** It has months-long gaps (PRD §3) and under-represents off-chain causes.
