# Porting entry template

Copy one block into the `## Entries` section of `<workspace>/PORTING.md` (the
workspace porting database) and add the matching
row to its `## Index` when a behavior is ported from Firefox into Servo.

Key entries by **behavior/feature** (stable), not by file or fixture; list every
WPT fixture the behavior covers and link their solution docs.

## Entry

```markdown
### <feature/behavior>
- **Spec:** <shortname> §<section> — <heading> (<url>)
- **Gecko:** `<gecko-dev path>` — `<function/type>`
- **Servo:** `<servo|stylo path>` — `<function/type>`
- **Fixtures:** [`<solution doc>`](<relative link>), …
- **Status:** partial | complete
- **Notes:** <algorithm summary / divergence>
```

## Index row

```markdown
| <feature> | <shortname> | `<gecko path>` | `<servo path>` | <status> | <fixtures> |
```

## Field guide

- **feature/behavior** — stable name, e.g. `Animation.play() auto-rewind`.
- **Spec** — shortname + section + heading + URL (from the spec dictionary).
- **Gecko** — Firefox file/function that implements it.
- **Servo** — repo (`servo` | `stylo`) + path + function/type.
- **Fixtures** — links to the per-fixture solution docs under `solutions/`.
- **Status** — `partial` (some covered fixtures still failing) | `complete`
  (all covered fixtures pass).
- **Notes** — algorithm summary / divergences. Resolve by **module/type name,
  not path** (see `<workspace>/PORTING.md` → Known divergences).
