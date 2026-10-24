# Hindsight landing page

A dependency-free static landing page, paired with VitePress documentation in `docs/`. It introduces the current existing-agent workflow and links to the repository docs. It has no account system, upload form, API requests, analytics, remote fonts, or build step.

## Preview

For the complete site, follow [docs/README.md](../docs/README.md) and serve the
assembled `site-dist/`. This gives the Docs link its `/docs/` routes.

For a landing-only preview without Node, from the repository root:

```sh
python3 -I -m http.server 8765 --bind 127.0.0.1 --directory website
```

Open <http://127.0.0.1:8765>. Serve only `website/`, not the repository root: review artifacts and credentials must never be exposed by a preview server. Stop the server with Ctrl+C. Opening `website/index.html` directly also works; if clipboard access is unavailable, the copy controls select text for manual copying.

Nothing is published by these instructions. Publishing requires explicit owner authorization. Repository URLs point at `https://github.com/Shawnchee/hindsight`; the local changes must be published before those pages appear remotely. Hindsight's own code and original documentation use the MIT License; upstream licenses remain unchanged.

## Files and accessibility

- `index.html`: semantic sections, real documentation links and visible agent prompt.
- `styles.css`: restrained responsive layout, local Inter typography, press feedback, focus states and reduced-motion/transparency support.
- `app.js`: copy controls, dataset filters and reduced-motion-aware entrances; no network access or storage.
- `assets/favicon.svg`: a simple path-based favicon.
- `assets/fonts/InterVariable.woff2`: locally served Inter variable font; all page text uses Inter, including commands and the prompt. Its SIL OFL license is in `assets/fonts/OFL.txt`.

Product copy reflects the README's current scope and limitations. Update snapshot figures when a new research version is introduced; never imply automatic incident approval or measured detection improvement. Test the page at desktop and mobile widths, keyboard navigation, and both clipboard success and selection fallback.

## Verified locally

Browser checks on 2026-10-24 passed at 375, 768 and 1440 px: no horizontal page
overflow, local Inter loaded across all text, visible controls have at least 40 px touch
areas, and internal anchors resolved. Clipboard copying, selection fallback,
keyboard skip navigation and reduced-motion scrolling were checked; no JavaScript
page errors were observed. This verifies the local page, not publication of its
GitHub documentation links or the security performance of the underlying skill.

## Dataset transparency

The marked dataset block and `data/research-preview.json` separate two layers:

- The pinned DeFiHackLabs Ethereum catalog: 357 entries, including58 dated2025
  and59 dated2026, as of21 October2026. Three recent examples per displayed year
  are name/date/link projections, without raw labels, PoCs or source code. Entry
  inclusion does not establish source coverage or human adjudication.
- Frozen research snapshot v0.2.0: ten enriched older incidents. Three selected
  examples include a remaining defect-source gap; these are not a representative
  sample. Labels remain proposed/unresolved and ineligible.

The preview pins catalog and snapshot payload hashes; snapshot inputs are checked
against their manifest. The included upstream license and explicit provenance
remain available. No source code, article text or local cache paths are published.
To deliberately refresh versions/selections, update `scripts/site/research_preview.py`
and then run:

```sh
python3 -I scripts/site/research_preview.py --write
```

Both the public-site build and portable checks reject a stale preview. Do not
manually edit the generated HTML block or alter frozen snapshots for presentation.

## Recent catalog and motion

The dataset view defaults to three recent 2026 catalog entries, with separate 2025
and enriched-snapshot controls. Counts and examples come from the pinned Ethereum
CSV; catalog records are not upgraded into enriched or verified incidents by the
preview. Without JavaScript, every labeled group remains visible.

Native Web Animations provide one-time scroll entrances, brief filter transitions
and disclosure fades. Content is never hidden by animation CSS. Reduced-motion
preferences skip animations and cancel active entrances when changed. There are
no loops, parallax, timers, animation packages or input lockouts.
