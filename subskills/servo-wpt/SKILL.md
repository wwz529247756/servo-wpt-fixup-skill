---
name: servo-wpt
description: Run Web Platform Tests (WPT) against the Servo browser engine, fully or partially. Use when running the whole WPT suite, a single test file or directory, selecting test types, sharding across machines, updating test expectations, or debugging WPT failures.
---

# Servo WPT

Web Platform Tests live under `tests/wpt/` in a Servo checkout and are run through `mach test-wpt`, which wraps `wptrunner` and drives a built `servoshell` via WebDriver. Run all commands from the repo root.

## Prerequisites

- A built binary: `./mach build --release` (or `--dev`). `test-wpt` auto-selects the matching binary, so you don't have to pass it explicitly.
- `mach bootstrap` must have been run at least once (Python deps via `uv`).

## Full run

```bash
./mach test-wpt --release
```

This runs the whole suite (all enabled directories, all default test types) against the release build. It can take hours on one machine — see "Sharding" to split it across machines/CI workers.

## Partial runs (test selection)

Paths are relative to `tests/wpt/tests/`. You can pass one or more files or directories:

```bash
./mach test-wpt --release dom/nodes/Node-cloneNode.html       # single test file
./mach test-wpt --release css/css-animations                  # whole directory
./mach test-wpt --release css/css-animations css/css-transitions web-animations   # several at once
```

Additional selection filters:

```bash
--include <url-prefix>        # include tests whose URL starts with a prefix
--include-file <path>         # include tests listed in a file
--include-manifest <ini>      # use a custom include/skip manifest (see below)
--exclude <url-prefix>        # exclude tests by URL prefix
--test-types <types...>       # restrict to e.g. testharness reftest
--no-default-test-types       # run only types given by --test-types
--tag <t> / --exclude-tag <t> # select by test metadata tags
```

Listing without running: `--list-tests`, `--list-tests-json`, `--list-disabled`.

### Test types

Defaults for Servo are `testharness reftest wdspec crashtest` (set in `python/wpt/run.py`). Restrict them with `--test-types` or `--no-default-test-types`.

## Sharding / parallelism

```bash
./mach test-wpt --release --total-chunks 4 --this-chunk 1
./mach test-wpt --release --chunk-type id_hash      # default; also: none, hash, dir_hash
```

Local parallelism:

```bash
--processes N      # number of browser processes (defaults to CPU count)
-f/--fully-parallel
```

## Mode / runtime options

```bash
--release | --dev | --profile <p>   # which build to run against
-M/--multiprocess                   # run Servo in multiprocess mode
--headless                          # default; add --no-headless for a visible window
--timeout-multiplier <f>            # scale timeouts (slow machines)
```

## Skip / include configuration

- `tests/wpt/include.ini` is Servo's default skip list (`--include-manifest`). Directories marked `skip: true` are excluded by default (e.g. `web-animations` is skipped except its `interfaces/` IDL tests).
- `tests/wpt/config.ini` defines the products and the manifests: `upstream`, `mozilla`, `webgl`, `webgpu`.
- To run a normally-skipped area anyway, make a copy of `include.ini`, flip the relevant `skip` to `false`, and pass it via `--include-manifest <copy>`.
- **Explicitly-passed paths bypass include.ini subdir skips**: `mach test-wpt --release css html` runs what you name, including `skip: true` subdirectories (e.g. `css-anchor-position`). The skip manifest governs default (full-suite) selection only; to skip subdirectories of an explicitly-passed root, prepare an `include.ini` copy with `skip: false` only on the roots you want and pass it via `--include-manifest <copy>`.

## Updating expectations

```bash
./mach test-wpt --release --update-expectations <paths...>   # or -u
./mach test-wpt --release --log-raw <file> ...               # write a structured log
./mach update-manifest                                       # regenerate MANIFEST.json
./mach update-wpt                                            # sync the WPT submodule/test suite
```

`--update-expectations` rewrites the baseline metadata under `tests/wpt/meta/` from the run results.

## Debugging

```bash
--debug-test          # debug a specific failing test
--pause-after-test    # keep the browser open after each test
--repeat N / --retry-unexpected N
--log-mach            # per-test logs on stdout
--log-raw <file>      # structured (JSON lines) log for later analysis
--rr-chaos            # run under rr chaos mode until a failure (Linux)
--filter-intermittents <file>   # drop known-flaky results via the intermittent tracker
```

The harness self-test: `./mach test-wpt-failure` (verifies failures are reported correctly).

## Notes

- On non-UTF-8 Windows consoles, run with `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` to avoid `UnicodeEncodeError` from the grouping formatter.
- Unexpected results are grouped by directory in the final summary; "Ran N tests ... X ran as expected" is the headline number, followed by per-directory unexpected listings.
