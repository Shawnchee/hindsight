# M0 data funnel (Ethereum mainnet, DeFiHackLabs 2024-11 to 2026-10)

Measures how far each in-scope DeFiHackLabs incident gets through:
in scope -> victim address found -> verified source recovered (Sourcify) -> compiles (solc) -> Slither runs -> finding counts.

- `funnel.csv`: one row per in-scope incident (column meanings below).
- `summary.md`: stage counts and percentages, failure reasons, Slither finding statistics.

Scripts live in `m0/scripts/funnel/`. Downloads and intermediate files go to `m0/data/funnel/` (gitignored).

## Safety notes

- DeFiHackLabs and the victim sources are untrusted. The clone is only read as text; none of its scripts,
  tests or build files are run. Our scripts live outside the clone and run with `python3 -I`.
- The only tools that touch downloaded Solidity are `solc` (standard-JSON compile) and Slither (static analysis).
  No npm / hardhat / forge.
- No Etherscan key is used. Sourcify's public APIv2 needs no key; requests are spaced 1.5 s apart with
  exponential backoff on 429/5xx, and responses are cached so reruns make no network calls.

## Regenerate

From the repo root (`/Users/shawnchee/Desktop/projects/hindsight`):

```sh
# 0. venv (Python 3.12; slither-analyzer 0.11.6, solc-select 1.2.0, crytic-compile 0.4.2 at time of measurement)
python3.12 -m venv .venv
.venv/bin/pip install slither-analyzer solc-select

# 1. DeFiHackLabs shallow clone (measured at commit 23c7bd83ccb4524972a9493617fcc8764ab6269b)
mkdir -p m0/data/funnel
git clone --depth 1 https://github.com/SunWeb3Sec/DeFiHackLabs m0/data/funnel/dhl

# 2. Select mainnet incidents and parse victim addresses from PoC headers
python3 -I m0/scripts/funnel/select_incidents.py m0/data/funnel/dhl m0/data/funnel/incidents.json --from 2024-11 --to 2026-10

# 3. Sourcify lookups (cached in m0/data/funnel/sourcify/; delete that folder to refetch)
python3 -I m0/scripts/funnel/fetch_sourcify.py m0/data/funnel/incidents.json m0/data/funnel/sourcify --delay 1.5

# 4. Write sources to m0/data/funnel/src/<incident>/, install exact solc, compile, run Slither
#    (VIRTUAL_ENV makes solc-select keep its binaries in .venv/.solc-select; old solc builds are x86_64 and need Rosetta on Apple Silicon)
VIRTUAL_ENV=$PWD/.venv .venv/bin/python -I m0/scripts/funnel/build_and_scan.py \
    m0/data/funnel/incidents.json m0/data/funnel/sourcify m0/data/funnel
#    add `--only <incident-substring>` to rerun one incident

# 5. Build funnel.csv and summary.md
python3 -I m0/scripts/funnel/report.py m0/data/funnel/incidents.json m0/data/funnel/results m0/funnel \
    --dhl-sha "$(git -C m0/data/funnel/dhl rev-parse HEAD)"
```

## Method details

- **In scope:** the first `createSelectFork(...)` argument in the PoC resolves to Ethereum mainnet: the alias
  `"mainnet"`/`"ethereum"`/`"eth"`, or an RPC URL (literal or a string constant such as `MAINNET_ARCHIVE`) whose host
  is a known mainnet endpoint (`eth-mainnet`, `eth.drpc`, ...).
- **Victim address:** addresses on `// Vulnerable Contract :`, `// Victim ...` and `// Vulnerable Contract Code :`
  header lines, in that order. If none, any header comment line (before the first `contract`/`interface`/`library`)
  containing `victim` or `vulnerab` and an address (`victim_source = freeform_tag`). `is_proxy` is `yes` (Sourcify says proxy, or `*Proxy*` + delegatecall), `impl_with_eip1967_slot` (logic contract that references the slot) or `no`. Deliberately minimal; the full
  catalog parser is separate work.
- **Sourcify:** `GET https://sourcify.dev/server/v2/contract/1/<address>?fields=sources,compilation,proxyResolution,deployment`.
  `match = exact_match` -> `full_match`, `match` -> `partial_match`, HTTP 404 -> `not_found`. Up to 4 header candidates
  are looked up; the first one with sources is scanned.
- **Proxy flag:** Sourcify `proxyResolution.isProxy`, or the EIP-1967 implementation slot in source, or a contract
  named `*Proxy*` with `delegatecall`. Historical implementations are not resolved.
- **Compile:** solc `--standard-json` with Sourcify's sources and `compilerSettings` (outputSelection replaced).
  `compile_error_class` is the `type` of the first error (`ParserError`, `DeclarationError`, ...), or
  `solc_install_failed` / `language_Vyper` / `solc_crash`.
- **Slither:** `m0/scripts/funnel/slither_one.py` builds the same standard JSON through crytic-compile and runs all
  built-in detectors over the whole compilation unit (dependencies included). `findings_non_dependency` drops findings
  whose first location path looks like a library (OpenZeppelin, node_modules, lib/...);
  `findings_in_target_file` keeps only findings in the compilation target's own file.

## funnel.csv columns

`incident, month, poc_path, fork_arg, in_scope, victim_found, victim_source, n_victim_candidates,
victim_explorer_chains, primary_address, sourcify_primary, sourcify_best, source_address, source_recovered,
source_from_candidate_index, contract_name, language, compiler_version, n_source_files, deployment_block, is_proxy,
proxy_evidence, compile_ok, compile_error_class, slither_ok, slither_error, slither_findings_total,
impact_{high,medium,low,informational,optimization}, conf_{high,medium,low}, findings_in_target_file,
findings_non_dependency, top_detectors, unverified_hint, funnel_stage_reached`

DeFiHackLabs is Apache-2.0 (SunWeb3Sec/DeFiHackLabs); this folder stores only derived metadata (paths, addresses,
counts), not PoC text.
