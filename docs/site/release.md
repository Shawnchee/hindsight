# Release readiness

The landing page and documentation can be built locally. They are not published
by a build or preview command. Publication, commits and pushes require an explicit
owner request.

## Checked

- Offline helper tests and frozen research-export verification.
- Responsive landing page, local Inter font, keyboard navigation and copy controls.
- Source-only practical reviews with baseline and comparison artifacts.
- Bounded RSS/Serper discovery and proposal-only contribution validation.
- MIT license for Hindsight's own code and documentation; upstream notices retained.

## Still open

- Compile and execute meaningful isolated regressions for the historical fix proposal.
- Obtain independent review before treating a proposed patch as production-ready.
- Publish approved files, choose hosting, and verify the real production URLs and headers.
- Enable and inspect GitHub Actions before claiming incident monitoring is active.

Research labels, chronological/family partitions and benchmark eligibility remain
unresolved. A docs build or passing helper suite does not close those gates.

## Build the public site

From the repository root, with Node 22+:

```sh
npm ci --prefix docs --ignore-scripts
node scripts/site/build.mjs
python3 -I scripts/site/check.py --root site-dist
python3 -I -m http.server 8766 --bind 127.0.0.1 --directory site-dist
```

Open `http://127.0.0.1:8766/` for the landing page and `/docs/` for documentation.
Only `site-dist/` is a hosting artifact. It excludes research caches, credentials,
review artifacts, historical internal reviews and dependency directories.

The dependency install requires registry access. The Python source helpers remain
standard-library-only; ordinary skill users do not need this website toolchain.
