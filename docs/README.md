# Documentation site

VitePress adds navigation and local search under `/docs/`. The existing Markdown
files and `skills/hindsight-triage/` remain the agent-facing references. Ordinary
skill users need only Python; the docs toolchain is for maintainers.

## Build and preview

From the repository root, with Node 22+, npm and Python 3.11+:

```sh
npm ci --prefix docs --ignore-scripts
node scripts/site/build.mjs
python3 -I -m http.server 8766 --bind 127.0.0.1 --directory site-dist
```

Open <http://127.0.0.1:8766/> and <http://127.0.0.1:8766/docs/>.
Only `site-dist/` is a public hosting artifact. Do not serve the repository root.
No build or preview command uploads or deploys anything.

For Cloudflare Pages, upload **`site-dist/`**, not `website/` or the docs-only
output. It contains both the landing page and VitePress documentation. After
deployment, check the homepage, `/docs/` and `/docs/getting-started.html` on your
public domain. The landing page links directly to the documentation.

For docs-only editing:

```sh
npm run dev --prefix docs
```

The dev server binds to loopback. It is a maintainer tool, not a production server.
Node dependencies, caches and generated output are Git-ignored.

## Content and styling

- `site/`: curated public guides; private/internal reviews are not site sources.
- `.vitepress/config.mjs`: navigation, local search, routes and `/docs/` base.
- `.vitepress/theme/`: local Inter font and restrained styling matching the landing page.
- `site/remediation.md` and `site/report-format.md`: include the canonical skill
  references at build time so these contracts are not maintained twice.

The lockfile pins VitePress 1.6.4. A deliberate Vite **6.4.5** override replaces
its default Vite 5 dependency, which had unresolved audit advisories. The patched
combination is build/browser checked; `npm audit --prefix docs` reported zero
advisories on 2026-10-24. Recheck on dependency changes; that result is not a
permanent security guarantee. Install with `npm ci`, not an unpinned `npx` command.

## Release checks

`node scripts/site/build.mjs` builds the docs, copies an explicit landing-page asset
list, checks public output, and only then replaces its own marked `site-dist/`.
An unrelated existing directory or symlink is rejected. No repository-tree copy
is used. The checker rejects private paths, unexpected file types, external
subresources and broken local links/assets/anchors.

```sh
python3 -I scripts/site/check.py --root site-dist
python3 -I scripts/check.py
npm audit --prefix docs
```

The GitHub checks workflow builds/audits the public site without deployment
permissions. Hosted CI still needs verification after the approved changes are
published. Production hosting, response headers, license selection and runtime
validation of proposed Solidity patches remain separate release gates; see
[release readiness](site/release.md).
