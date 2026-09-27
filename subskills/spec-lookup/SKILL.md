---
name: spec-lookup
description: >-
  Look up web platform spec definitions from the local spec dictionary. Use
  when checking whether a CSS property, CSS term, HTML construct, or WebIDL
  interface matches the specification — e.g. verifying syntax, initial values,
  or API members against the specs. The dictionary is not exhaustive; when a
  spec or term is missing, extend it with `generate.py --add` and re-lookup.
---

# Spec lookup

The local spec dictionary (the `specs` entry of `<workspace>/workspace.json`,
default `<workspace>/specs-dictionary`; the dictionary itself lives under
`dict/`) holds Markdown extracts of web platform specs, generated from
[w3c/webref](https://github.com/w3c/webref). It is registered as the `specs`
reference. (`<workspace>` is the workspace root — resolved from
`WPT_FIX_WORKSPACE` or `--workspace`; `<skill>` is the wpt-fix skill's base
directory; see the wpt-fix `SKILL.md`.) Use it to
verify a fact against the spec instead of guessing.

## What's inside

- `catalog.md` — index of specs (title, URL, status, repository).
- `css/*.md` — per-spec CSS properties (syntax, initial value, applies-to, inherited, per-value prose) plus term definitions.
- `webapi/*.md` — Web API term definitions + WebIDL (e.g. `IntersectionObserver`, `Notification`, `WebSocket`).
- `html/*.md` — HTML-spec surface (e.g. `document.title`, `history`).
- `../specs.json` — manifest of covered spec shortnames (tool-maintained; lives at the dictionary root).

## How to look something up

1. Determine the category: CSS property/term → `css/`; JS/DOM interface → `webapi/`; HTML-level thing → `html/`.
2. Grep the dictionary for the name:
   - `grep -rn "grid-template-areas" <workspace>/specs-dictionary/dict/css`
   - `grep -rn "IntersectionObserver" <workspace>/specs-dictionary/dict/webapi`
3. Read the matching file; each entry includes its definition/prose and a **Ref** link to the authoritative spec.
4. For full normative text, follow the spec link (`drafts.csswg.org`, `html.spec.whatwg.org`).
5. **Not found?** The dictionary is not exhaustive — extend it (see *Extending the dictionary*) and re-lookup.

## Extending the dictionary

The dictionary is **not exhaustive**. If a spec/term isn't present, extend it
(rather than guessing):

- `python <skill>/subskills/spec-lookup/generate.py --add <shortname>`
  auto-discovers the spec's webref files (css/dfns/idl), renders the relevant
  `css/` or `webapi/` file, appends the shortname to the manifest
  (`specs.json`), and refreshes `catalog.md`. Example shortnames:
  `css-position-1`, `css-grid-1`, `webstorage`, `fullscreen-api`,
  `intersection-observer`.
- A plain run (no args) regenerates every manifest spec; `--dict <path>`
  overrides the dictionary root (default: the `specs` workspace entry).

## Notes

- The dictionary is a glossary/index, not the full spec prose. It gives syntax, defaults, and short definitions plus a link to the real text — go to the link for exact wording.
- To regenerate: `python <skill>/subskills/spec-lookup/generate.py` (rebuilds every spec in `specs.json`; reads `_src/webref`).
