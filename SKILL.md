---
name: wpt-fix
description: >-
  Orchestrate Servo WPT fixes: set up a workspace, discover skipped and failing
  Web Platform Tests, then fix them one at a time through a single-test loop
  grounded in the W3C spec and Firefox. Use when fixing WPT failures or
  implementing missing web-platform features in the Servo browser engine.
---

# Servo WPT-fix

The main working stream for finding and fixing Web Platform Test (WPT) gaps in
[Servo](https://github.com/servo/servo). This file owns **workspace setup**,
**discovery** (which tests are skipped/failing), **module scoping**, dispatching
each test to the **single-test loop** in `FIXINGLOOP.md`, and the final
**roll-up**. Every fix is grounded in the **spec dictionary** (`spec-lookup`
sub-skill) and **Firefox** (`servo-port` sub-skill) as ground truth.

> **Path notation.** Paths without a prefix are relative to this skill's base
> directory (the folder containing this `SKILL.md`); run the Python scripts as
> `python scripts/<name>.py` from that directory. `<workspace>` is the
> workspace root you provide below; `<servo>` is `<workspace>/servo`; `<data>`
> is the per-workspace data root (`<workspace>/wpt-fix` by default). The
> workspace config lives at `<workspace>/workspace.json`, the porting database
> at `<workspace>/PORTING.md` — both are workspace-side, not in the skill.

> **Binding rule:** fix **one test at a time** by running the `FIXINGLOOP.md`
> loop (L1–L7) for that single path. Do not batch unrelated changes, skip a
> step, or drift into broad untracked refactors. Any deviation must be called
> out and approved first.

## D0 — Setup / init workspace

**Ask the user for a workspace root first — the root must be set.** The
workspace is a single folder holding the sources; set it up with
`workspace_init.py`, which persists it in `<workspace>/workspace.json` (see
"Initialize").

| Workspace path | Contents | Role |
|---|---|---|
| `<workspace>/servo` | local Servo checkout (build + WPT target) | `servo` (required) |
| `<workspace>/gecko-dev` | Firefox `mozilla/gecko-dev` sparse clone | `gecko` (required) |
| `<workspace>/specs-dictionary` | spec dictionary (`dict/` + `_src/webref`, from w3c/webref) | `specs` (built on demand) |
| `<workspace>/wpt-fix` | per-workspace data: `modules/`, `reports/`, `solutions/`, `inventory.json`, baselines/logs | `data` |
| `<workspace>/workspace.json` | resolved workspace config | written by `workspace_init.py` |
| `<workspace>/PORTING.md` | porting database (Firefox ↔ Servo ↔ spec) | grows during L3/L4 |

Servo's style engine (stylo) is auto-fetched by `mach build` under
`$CARGO_HOME/git/checkouts/stylo-*`.

### Initialize
```powershell
python scripts/workspace_init.py --workspace <root> [--clone]
```
Creates the root + data dir, records/creates the required checkouts, prints a
recipe for anything missing (`--clone` runs the clones), writes
`<workspace>/workspace.json`, scaffolds `<workspace>/PORTING.md`, and prints an
`opencode.jsonc` `references` snippet to paste (`specs` + `gecko`).
Runtime resolution order: `--workspace` → `WPT_FIX_WORKSPACE` env → **the
current working directory**. The root must be set (env or CLI) when running the
scripts from outside the workspace. Template: `workspace.example.json`.

### Constructing a missing prerequisite
- **Servo** (`<workspace>/servo`, required) — to clone, bootstrap, and build
  (including switching versions), load the **`servo-build`** sub-skill
  (`subskills/servo-build/SKILL.md`) and point it at `<workspace>/servo`.
- **Firefox** (`<workspace>/gecko-dev`, required) — shallow, sparse clone:
  ```bash
  git clone --filter=blob:none --no-checkout --depth 1 \
      https://github.com/mozilla/gecko-dev <workspace>/gecko-dev
  cd <workspace>/gecko-dev
  git sparse-checkout init --cone
  git sparse-checkout set dom/animation servo/components/style
  git checkout
  ```
  Extend later with `git sparse-checkout add <path>`.
- **Spec dictionary** (`<workspace>/specs-dictionary`, built on demand) —
  obtain the spec-dictionary checkout (`dict/` + `_src/webref`, from w3c/webref):
  ```bash
  python subskills/spec-lookup/generate.py     # writes dict/
  ```
  Add a missing spec with
  `python subskills/spec-lookup/generate.py --add <shortname>`; see the
  `spec-lookup` sub-skill.

### Baseline, environment, porting
- **Capture the baseline once** (used by the single-test regression check L6):
  ```powershell
  mach test-wpt --release --log-raw baseline.jsonl
  ```
  Store the parsed summary + unexpected paths as
  `<data>/modules/<name>/baseline.json`.
- **Environment** for the scripts/WPT:
  - Non-UTF-8 consoles: set `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8`.
  - `RUSTUP_HOME` / `CARGO_HOME` come from `<workspace>/workspace.json` (or the
    ambient environment) when the toolchains are relocated.
- **`<workspace>/PORTING.md`** grows during the single-test loop (L3/L4) — do
  not pre-fill it.

## D1 — Identify skipped & failing tests

**Running WPT is owned by the `servo-wpt` sub-skill** (full or partial runs);
this stream consumes its results and turns them into a gap inventory.

1. Run the tests with `servo-wpt` and write a structured log, e.g.
   `mach test-wpt --release [--log-raw <file>] [<paths...>]`.
2. Turn the results into gaps with `scripts/discover.py`:

```powershell
python scripts/discover.py --module <name>          # skipped + mapped gaps
python scripts/discover.py --log-raw <file>         # add failing tests
python scripts/discover.py --list-failed <file>     # list failing tests only
```
Add `--workspace <root>` (or set `WPT_FIX_WORKSPACE`) when the current
directory is not the workspace root.

- **Skipped:** parses `<servo>/tests/wpt/include.ini` (indentation-based
  nesting, 2 spaces/level; root default is `skip: true`) — every `skip: true`
  entry, every top-level dir *absent* from the file, plus manifest skips in
  `<servo>/tests/wpt/config.ini`.
- **Failed:** parses the `--log-raw` JSONL for `test_status`/`test_end` with
  `status != expected`.
- **Output:** `<data>/modules/<name>/inventory.json` — one entry per gap:
  `{ path, kind: skipped|failed|subtest, reason, spec_url, spec_shortname, category }`.
  The top-level `<data>/inventory.json` is the unscoped equivalent.
- **Known limits**: the raw-log parser covers `test_status`/`test_end` only
  (run the baseline/`servo-wpt` first so a log exists); `META.yml` spec mapping
  is noisy and `shortname_from_url` is naive (last URL segment — e.g. `motion`
  vs `motion-1`), so treat `spec_shortname` as a hint and canonicalize against
  the webref index when it matters; `verify.py` summary parsing is
  regex-approximate (testharness-oriented; reftest/wdspec/crashtest counts are
  rough).

## Report support status (standalone, D1-only)

To answer "how supported is module X right now?" **without fixing anything**:

```powershell
python scripts/status.py --module <name> [--workspace <root>]
                         [--log-raw <file> | --run] [--out <md>] [--print]
```

- Runs only the D1 measurement: skipped/unsupported areas from `include.ini`;
  pass/fail from `--log-raw` (or a fresh `--run` via the `servo-wpt` sub-skill).
- Prints a summary and writes `<data>/modules/<name>/reports/support.md`.
- Changes nothing else — no code, build, solution docs, expectations, or
  `inventory.json` gap mutations.

This is the same snapshot D1 records in `inventory.json` and roll-up renders, so
a standalone run and the pipeline always agree. Later stages reuse it: dispatch
reads dir states; `scripts/verify.py --refresh-status` refreshes it after a fix;
roll-up re-renders `reports/support.md`.

## Module scoping

A module groups a set of WPT dirs + specs (e.g. `animation`). Create
`<data>/modules/<name>/module.json` (`name`, `scope`, `specs`, `category`), then
a `<data>/modules/<name>/MODULE.md` instance describing the module's gap order
(scaffold from `templates/`). Run the scripts with `--module <name>` so
discovery/reporting is scoped to `<data>/modules/<name>/` (`inventory.json`,
`solutions/`, `reports/`).

## Dispatch — fix one test

Given a **single test path** from the inventory — e.g.
`web-animations/interfaces/Animation/play.html` — run the per-test loop in
**`FIXINGLOOP.md`** (L1 read → L2 spec → L3 Firefox/diagnose → L4 fix →
L5 verify → L6 regress → L7 conclude). Pick a test, load `FIXINGLOOP.md`, and
follow L1–L7 for that path only; the orchestrator resumes for the next gap.

## Roll-up

After a test (or a set) is fixed:
```powershell
python scripts/report.py --module <name>
```
writes `<data>/reports/progress.md`, `<data>/reports/conclusion.md`,
`<data>/reports/support.md`, and `<data>/solutions/index.md`. Update
`<servo>/tests/wpt/include.ini` (`skip: false`)
and `<servo>/tests/wpt/meta/` expectations for the passing set. Never silently
absorb a regression — record each in `<data>/reports/regressions.md` with root
cause, before/after, and action.

## Parts of this skill

| Path | Role |
|---|---|
| `SKILL.md` | This file — orchestrator (setup, discovery, dispatch, roll-up) |
| `FIXINGLOOP.md` | Single-test fix loop L1–L7 |
| `PORTING_TEMPLATE.md` | Template for `<workspace>/PORTING.md` entries |
| `SOLUTION_TEMPLATE.md` | Template for per-fixture solution docs |
| `scripts/workspace.py` | Workspace path resolver (shared by the scripts) |
| `scripts/workspace_init.py` | D0: define/init a workspace (checkouts + data dir + `<workspace>/PORTING.md`), print the references snippet |
| `workspace.example.json` | Template for `<workspace>/workspace.json` |
| `templates/module.json`, `templates/MODULE.md` | Skeletons for a new module |
| `scripts/discover.py` | D1: parse runs → gap inventory (+ support snapshot) |
| `scripts/support.py` | Shared support-snapshot logic (states, counts, Markdown) |
| `scripts/status.py` | D1-only: report module support status (no fixing) |
| `scripts/verify.py` | L5/L6: run a target and diff vs baseline |
| `scripts/report.py` | Roll-up: progress/conclusion/`solutions/index.md` |
| `<workspace>/workspace.json` | Resolved workspace config (workspace-side) |
| `<workspace>/PORTING.md` | Growable Firefox ↔ Servo ↔ spec porting database (appended during L3/L4; workspace-side) |
| `<data>/` | Per-workspace data (workspace-side, not in the skill): `modules/`, `reports/`, `solutions/`, `inventory.json` |
| `subskills/<name>/SKILL.md` | Sub-skills (see below) |

## Sub-skills — when to load

Sub-skills live at `subskills/<name>/SKILL.md` (bundled with this skill; not
auto-loaded by opencode). Load the one(s) for the current stage:

| Stage | Sub-skill | Purpose |
|---|---|---|
| D1 / L5 | `servo-wpt` | Run WPT fully/partially, shard, update expectations |
| L2 | `spec-lookup` | Look up CSS/HTML/WebAPI definitions in the spec dictionary; extend it with the bundled `generate.py --add` |
| L3 / L4 | `servo-port` | Map behavior from Firefox (`gecko-dev`) to Servo/stylo; fills solution §3 |
| L4 | `servo-build` | Build/run Servo; switch versions; mirrors/proxies |

## Extending to a new module

1. Create `<data>/modules/<name>/module.json` (copy `templates/module.json`).
2. Create `<data>/modules/<name>/MODULE.md` (copy `templates/MODULE.md`)
   describing the module's gap order.
3. Run the tooling with `--module <name>` so discovery/reporting is scoped to
   `<data>/modules/<name>/`.
4. The spec dictionary is a **hard gate**: no test is diagnosed against a spec
   that is not in the dictionary; extend it first
   (`subskills/spec-lookup/generate.py --add`).

## Automation boundary

- **Fully automatic:** discovery/mapping (`scripts/discover.py`), dictionary
  extension, verification + regression diffing (`scripts/verify.py`), roll-up
  (`scripts/report.py`).
- **Agent-automated with review:** the single-test loop (`FIXINGLOOP.md`) —
  diagnosis, fix, and the per-fixture solution doc; a human reviews each patch.
- **Human decisions:** architectural refactors, spec ambiguities, and whether
  to accept an expectation change.
