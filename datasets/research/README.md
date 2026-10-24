# Hindsight research snapshots

The toolkit includes immutable, metadata-only research exports:

- [v0.1.0](v0.1.0/README.md): 10 incidents and 31 component snapshots.
- [v0.2.0](v0.2.0/README.md): the same 10 incidents with recovery supplements,
  55 components and 9 proposed defect-source locations present.

Components include proxies and dependencies, not separate vulnerable victims.
All labels remain AI-proposed/unresolved; human verification and training,
benchmark and evaluation eligibility remain false. No source files or copied
article/post bodies are redistributed. Source-fetch helpers are opt-in.

Verify the supplied snapshots offline:

```sh
python3 -I m0/scripts/discovery/export_research.py --verify datasets/research/v0.1.0
python3 -I m0/scripts/discovery/export_research.py --verify datasets/research/v0.2.0
```

Verification checks payload hashes and research-only gates. Original generation
inputs and internal adjudication/planning archives are not distributed with the
toolkit. Their recorded paths and hashes remain historical provenance, not a
promise that this checkout can rebuild those snapshots from scratch. Do not
regenerate or silently edit a frozen version. New evidence requires a separately
reviewed version and its explicit input manifest.

Use [community intake](../../incidents/README.md) for new reported incidents.
