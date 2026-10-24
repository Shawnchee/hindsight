# Add an incident

Found a public post-mortem or useful security alert? Open an
[incident issue](https://github.com/Shawnchee/hindsight/issues/new/choose)
or prepare a metadata PR. You do not need a working exploit.

## Include evidence

Provide the primary URL, an original short summary, the reported date, and victim
or transaction identifiers when known. Explain missing evidence instead of guessing.
Check existing submissions and the discovery queue for duplicates.

## Ask an agent to prepare a PR

```text
Read CONTRIBUTING.md and incidents/README.md.
Prepare a proposed incident record for this public report: <URL>.
Check duplicates, store links and our own summary, leave unknowns unresolved,
and run the offline validator. Do not generate an exploit or promote the record.
```

The canonical schema, sample and commands are in
[CONTRIBUTING.md](https://github.com/Shawnchee/hindsight/blob/main/CONTRIBUTING.md).

```sh
python3 -I scripts/incidents/validate.py --root incidents/submissions
```

## Keep proposals separate from approval

New records stay proposed/unresolved, unassigned and ineligible. Merging a lead
is not human adjudication or benchmark admission. Maintainers review scope,
provenance, source rights and chronology before a new research snapshot.

Do not submit raw source, copied article bodies, secrets, executable attacks or
changes to frozen exports. For undisclosed live issues, use the affected project's
security channel. Hindsight's own code and documentation are MIT licensed;
third-party material retains its existing terms.
