# M0 data funnel: Ethereum mainnet DeFiHackLabs incidents, 2024-11 to 2026-10

Measured 2026-10-22. DeFiHackLabs commit `23c7bd83ccb4524972a9493617fcc8764ab6269b` (shallow clone). Source lookup: **Sourcify APIv2 only** (no Etherscan key). Compiler: exact solc version via solc-select, Sourcify's compiler settings, solc standard-JSON. Slither 0.11.6, all built-in detectors, run on the whole compilation unit.

## Funnel

| Stage | Count | % of in-scope | % of previous stage |
|---|---:|---:|---:|
| DeFiHackLabs PoCs in window (all chains) | 338 | | |
| In scope (first `createSelectFork` = Ethereum mainnet) | 127 | 100% | 38% |
| Victim address found in PoC header | 102 | 80% | 80% |
| Verified source recovered (Sourcify full or partial, any header candidate) | 77 | 61% | 75% |
| Compiles (exact solc, Sourcify settings) | 75 | 59% | 97% |
| Slither runs | 74 | 58% | 99% |
| ...and scanned contract is not a proxy shell | 53 | 42% | 72% |

### Sourcify result (incidents with a victim address)

| Result | Best over header candidates | Primary (first) candidate only |
|---|---:|---:|
| full_match | 44 | 43 |
| partial_match | 33 | 33 |
| not_found | 25 | 26 |

Sources were taken from a non-primary header candidate in 1 incidents.

### By year

| Year | In scope | Victim found | Source | Compiles | Slither |
|---|---:|---:|---:|---:|---:|
| 2024 | 5 | 3 | 3 | 3 | 3 |
| 2025 | 58 | 50 | 37 | 35 | 34 |
| 2026 | 64 | 49 | 37 | 37 | 37 |

## Where incidents drop out

| Final stage reached | Count |
|---|---:|
| slither_ok | 74 |
| no_victim_in_header | 25 |
| sourcify_not_found | 25 |
| compile_fail | 2 |
| slither_fail | 1 |

- **No victim address in header (25):** the `// Vulnerable Contract :` line is empty and no header comment tags an address as victim/vulnerable. Most of these headers still list addresses (untagged, or in free-form prose); the full catalog's parser or a manual pass can recover many of them. This pass used only `Vulnerable Contract`, `Victim` and inline `victim`/`vulnerab` tags.
- **Sourcify not_found (25):** no candidate address verified on Sourcify. These are the incidents an Etherscan key would most likely rescue (many DeFi contracts are verified only on Etherscan); some are genuinely unverified. 5 of them are named `unverified_*` by DeFiHackLabs or say 'unverified'/'not verified'/'not open source' in the PoC header, so an Etherscan key would not help those.
- **Compile failures (2):** solc_no_standard_json(<0.4.11): 1, language_Vyper: 1
- **Slither failures (1):** SlithIRError: 1

## Proxies

**21 of 77** recovered sources are proxies (Sourcify `proxyResolution` says proxy, or the contract is named *Proxy* and uses delegatecall). For these, Slither scanned the proxy shell, not the logic that was exploited, so their finding counts are not meaningful. A further 9 reference the EIP-1967 slot but are themselves logic contracts (e.g. UUPS implementations) and were scanned as such. Historical implementations at the exploit block were **not** resolved in this pass (needs archive RPC, ENR-3); Sourcify's `implementations` field reflects the current implementation.

## Slither findings (incidents where Slither ran)

- Median findings per contract, whole compilation unit: **47.0** (min 4, max 465, total 6192)
- Median excluding findings whose first location is in an obvious dependency path (OpenZeppelin, node_modules, lib/...): **36.0**
- Median whose first location is in the compilation target's own file: **21.0**
- Non-proxy contracts only (53): median **67** whole unit, **30** in target file

| Impact | Total | Median per contract |
|---|---:|---:|
| High | 388 | 2.0 |
| Medium | 811 | 3.0 |
| Low | 880 | 7.0 |
| Informational | 3989 | 23.5 |
| Optimization | 124 | 0.0 |

Top detectors (total findings / contracts where it fired):

| Detector | Findings | Contracts |
|---|---:|---:|
| naming-convention | 1437 | 52 |
| assembly | 817 | 61 |
| too-many-digits | 522 | 26 |
| divide-before-multiply | 381 | 26 |
| dead-code | 369 | 44 |
| low-level-calls | 274 | 53 |
| calls-loop | 243 | 30 |
| timestamp | 195 | 35 |
| unused-return | 190 | 40 |
| solc-version | 186 | 73 |
| reentrancy-events | 158 | 35 |
| unindexed-event-address | 116 | 43 |
| unused-state | 102 | 7 |
| reentrancy-benign | 92 | 32 |
| unchecked-transfer | 81 | 17 |

## Caveats (stated, not measured)

- "Compiles" means solc produced no errors from Sourcify's own sources and settings. It is not a bytecode re-match and not a buildable project in the ENR-2 sense.
- The funnel scans one contract per incident (first header candidate with source). Multi-contract root causes and proxied logic are not covered.
- Slither finding counts say nothing about whether the causal weakness was flagged; that is a separate M0 measurement.
- Mainnet selection uses the PoC's first fork call only; cross-chain incidents whose first fork is another chain are excluded.
