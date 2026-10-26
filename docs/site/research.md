# Research data

Research snapshot **v0.2.0** contains ten enriched Ethereum incidents and
55 component metadata snapshots. Nine incidents have proposed defect source.
Components include proxies and dependencies; they are not 55 vulnerable victims.

<a href="../#dataset">See three real examples on the landing page</a>, including an unresolved
source gap. The downloadable preview contains metadata and source fingerprints,
not contract code.

[Inspect the snapshot](https://github.com/Shawnchee/hindsight/tree/main/datasets/research/v0.2.0)

## Historical baseline and daily catalog

The separate pinned DeFiHackLabs catalog contains **357 Ethereum entries**,
including **58 dated 2025** and **59 dated 2026**, as recorded at upstream commit
`23c7bd83ccb4524972a9493617fcc8764ab6269b` on 21 October 2026. These are catalog
entries, not 357 independently verified hacks or members of the ten-incident
enriched snapshot. The landing page has separate 2026, 2025 and enriched views.
Catalog dates are reported incident dates; completeness, source coverage and
human adjudication are not established by catalog inclusion.

[Inspect the historical baseline](https://github.com/Shawnchee/hindsight/blob/main/m0/catalog/ethereum_incidents.csv)

The [current public catalog](https://github.com/Shawnchee/hindsight/blob/main/website/data/catalog.json)
combines that baseline with qualifying daily DeFiHackLabs metadata additions.
All entries remain unverified. Counts and charts regenerate from the combined
catalog; ambiguous matches and news leads are not counted.
[Connect your agent via MCP](./mcp.md) for search and freshness information.

## What is published

Addresses, evidence links, hashes and fetch instructions. Contract source, PoCs
and article/post bodies are not redistributed. Snapshots are immutable; new
research needs a new version.

Labels remain AI proposals. Human adjudication, earliest disclosure, family
separation and training/evaluation eligibility remain separate gates.

## Verify an export

```sh
python3 -I m0/scripts/discovery/export_research.py \
  --verify datasets/research/v0.2.0
```

## Practical trials

The workflow has been tried on a no-change OpenZeppelin beacon review and a known
historical ERC165Checker fix proposal. The latter preserved a baseline and
comparison, but compilation and runtime/resource regressions were not run because
no container runtime was available. Neither trial was a blind detection benchmark.

[Runtime validation limits](https://github.com/Shawnchee/hindsight/blob/main/docs/runtime-checks.md)
