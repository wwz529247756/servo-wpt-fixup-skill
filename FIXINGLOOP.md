# Servo WPT-fix — single-test loop (FIXINGLOOP)

Fix **exactly one** Web Platform Test. Input: the test's path relative to
`<servo>/tests/wpt/tests/` — e.g.
`web-animations/interfaces/Animation/play.html`. The orchestrator (`SKILL.md`)
sets up the workspace and identifies which tests are skipped/failing; this file
is the loop you run for **one** of them.

> **Binding rule:** one test at a time. Run L1 → L7 in order; do not batch
> unrelated changes, skip a step, or drift into broad untracked refactors. Any
> deviation must be called out and approved first.

## Inputs & preconditions

- **Workspace** root set (`--workspace` → `WPT_FIX_WORKSPACE` env → the current
  directory) and resolved (`<workspace>/workspace.json` optional).
- **One test path** (from the inventory produced by `scripts/discover.py`, or
  given directly). Its type is one of testharness | reftest | wdspec | crashtest.
- **Module context** (optional): the owning `<data>/modules/<name>/` for
  `solutions/` and `reports/`; without it, use the top-level `<data>/`.
- **Build** exists for the checkout (see `servo-build`).
- The test's spec is covered by the dictionary, or L2 extends it.

## The loop

### L1 — Read & scope
- Read `<servo>/tests/wpt/tests/<path>`; record the test type and what it
  asserts.
- Resolve the spec + category from the test dir's `META.yml`
  (`spec:` URL → shortname, canonicalized via the webref index); `category` is
  `css` | `html` | `webapi`.
- Create/update the solution doc (frontmatter + §1 Fixture + §2 stub), status
  `pending`.

### L2 — Spec reference (dictionary gate)
- Look up the normative behavior in the spec dictionary (load `spec-lookup`;
  follow the definition's link for exact wording).
- If the spec is missing from the dictionary, extend it first:
  `python subskills/spec-lookup/generate.py --add <shortname>`
  (the coverage gate — never diagnose against an absent spec).
- Fill §2 (spec title/URL, section, algorithm, term/property/interface).

### L3 — Firefox reference & diagnosis
- Compare against Firefox using `servo-port` (`<workspace>/gecko-dev`); record
  the file(s) + function/algorithm in §3.
- Emit the root-cause diagnosis — *missing API method / property not parsed /
  event ordering / rendering diff* — as a concrete change (repo + file +
  algorithm); fill §4. Status `diagnosed`.
- If the behavior maps across spec ↔ Firefox ↔ Servo, append an entry to
  `<workspace>/PORTING.md` (one per behavior, via the skill's
  `PORTING_TEMPLATE.md`) linking this fixture's solution doc, and add its
  `## Index` row.

### L4 — Minimal fix
- Port from Firefox following the spec's numbered steps; Servo code first
  (`components/script/**`, `components/script_bindings/webidls/*`), stylo only
  when a CSS property/model is missing (load `servo-build` for the rebuild).
- Keep the change minimal and scoped to this test; rebuild with
  `mach build --release`.
- Fill §5 (repo, files, ordered steps, algorithm sketch); status `in-progress`
  → `fixed`.

### L5 — Verify
- `python scripts/verify.py <path>` (or `mach test-wpt --release <path>`); load
  `servo-wpt` for test-selection/expectation details.
- Fill §6 (exact command, expected result, gate suites); status `verified` (or
  `blocked` with the reason).

### L6 — Regression check
- Run the test's neighbors / gate suites and diff against the baseline captured
  in the `SKILL.md` prerequisites.
- Any new unexpected result is a regression: fix it, or record it one-by-one in
  `<data>/reports/regressions.md` (root cause, before/after, action). Never
  silently absorb it into `meta/`.
- Optionally refresh the module's support snapshot so the moved dir state is
  recorded: `python scripts/verify.py --module <name> --refresh-status <path>`.

### L7 — Conclude this fixture
- Finalize §7 (Result & notes): outcome, regression notes, expectation
  changes, follow-ups; keep the solution doc's `status` current.
- Update `<servo>/tests/wpt/include.ini` (`skip: false`) and
  `<servo>/tests/wpt/meta/` expectations for **this test**.
- Roll-up across tests/module is the orchestrator's job (`python scripts/report.py`).

## Solution document (per fixture)

Location: `<data>/modules/<name>/solutions/<category>/<spec>/<fixture>.md` (or
the top-level `<data>/solutions/` when unscoped). Use `SOLUTION_TEMPLATE.md`:
§1 Fixture, §2 W3C spec reference, §3 Firefox reference, §4 Diagnosis,
§5 Implementation plan, §6 Verification, §7 Result.

Status lifecycle:
`pending → diagnosed → in-progress → fixed → verified` (or `blocked`).

| Step | Action on the solution doc |
|---|---|
| L1 | frontmatter + §1 + §2 stub, `pending` |
| L3 | §3 + §4, `diagnosed` |
| L4 | §5, `in-progress` → `fixed` |
| L5 | §6, `verified` (or `blocked`) |
| L7 | finalize §7; link from `solutions/index.md` |

## Sub-skills used

| Step | Sub-skill | Purpose |
|---|---|---|
| L2 | `spec-lookup` | Spec definitions + the bundled `generate.py --add` |
| L3 / L4 | `servo-port` | Firefox → Servo/stylo mapping (fills §3) |
| L4 | `servo-build` | Build/run Servo |
| L5 | `servo-wpt` | Run the test / update expectations |

## Definition of done

- The target test passes (`verified`), and no new unexpected result appears
  against the baseline.
- The solution doc records §1–§7 with `status: verified`.
- `include.ini` / `meta/` reflect the passing test.
- `<workspace>/PORTING.md` has an entry for the behavior (if a port was made).
