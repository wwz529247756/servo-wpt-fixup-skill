# <Name> module — WPT-fix module instance

Module instance of the WPT-fix skill. The orchestrator is the skill's
`SKILL.md` (workspace setup + discovery); the per-test loop is the skill's
`FIXINGLOOP.md` (L1–L7). Fill the module variables below and run the loop for
one test at a time.

This file lives at `<data>/modules/<name>/MODULE.md`, where `<data>` is the
workspace data root (default `<workspace>/wpt-fix`).

## Module variables

- **name:** `<name>`
- **scope (WPT dirs):** `<dir>`, `<dir>`, …
- **specs:** `<shortname>`, `<shortname>`, …
- **category:** css | html | webapi | mixed

## Gap processing order

Process the gaps one at a time, smallest/leaf first (IDL/interfaces →
attributes → timing/behavior). For each gap: un-skip it, enumerate its failing
tests, then run the `FIXINGLOOP.md` loop (L1–L7) until the gap is green. Do not
batch unrelated changes or jump ahead.

1. `<dir>` — `<notes: repo tree, Firefox ref, order>`.
2. …

## Outputs

- `<data>/modules/<name>/inventory.json` — scoped gaps.
- `<data>/modules/<name>/solutions/` — per-fixture solution docs.
- `<data>/modules/<name>/reports/` — `progress.md`, `regressions.md`,
  `conclusion.md`, `support.md`.
