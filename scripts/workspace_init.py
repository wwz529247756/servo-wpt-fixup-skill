#!/usr/bin/env python3
"""D0 helper: define/initialize a WPT-fix workspace.

A workspace is a single root the user chooses, containing:

  <root>/servo             local Servo checkout          (required)
  <root>/gecko-dev         Firefox sparse clone          (required)
  <root>/specs-dictionary  generated spec dictionary     (built lazily)
  <root>/wpt-fix           data root: modules/, reports/, solutions/,
                           inventory.json, baselines/logs

Usage:
  python scripts/workspace_init.py --workspace <root> [--data wpt-fix]
                                   [--servo <path>] [--gecko <path>] [--clone]
                                   [--cargo-home <dir>] [--rustup-home <dir>]
                                   [--dry-run] [--force]

Writes ``<root>/workspace.json`` and scaffolds ``<root>/PORTING.md`` (the
workspace porting database; entries follow the skill's ``PORTING_TEMPLATE.md``).
Missing checkouts are cloned with ``--clone``, otherwise a construction recipe
is printed.
"""

import argparse
import json
import os
import subprocess
import sys

import workspace

SERVO_URL = "https://github.com/servo/servo"
GECKO_URL = "https://github.com/mozilla/gecko-dev"
GECKO_TREES = ["dom/animation", "servo/components/style"]

PORTING_SCAFFOLD = """# Porting database (Firefox ↔ Servo ↔ W3C spec)

Append-only map of behaviors ported from Firefox into Servo, grounded in the
W3C spec. The single-test loop (`FIXINGLOOP.md`, L3/L4) appends **one entry per
behavior**; never rewrite past entries. New entries use the skill's
`PORTING_TEMPLATE.md`.

## Conventions

- **Key = behavior/feature** (stable); list every WPT fixture it covers.
- Resolve targets by **module/type name, not path**.
- Cite the spec shortname + §, the Gecko path/function, and the Servo
  repo/path/function.
- Link the per-fixture solution doc(s); status `partial` | `complete`.

## Index

| Feature | Spec | Gecko | Servo | Status | Fixtures |
|---|---|---|---|---|---|

## Entries

<!-- appended by L3/L4 using PORTING_TEMPLATE.md -->
"""


def _rel_or_abs(root, p):
    try:
        rel = os.path.relpath(p, root)
        if not rel.startswith(".."):
            return rel.replace("\\", "/")
    except ValueError:
        pass
    return p.replace("\\", "/")


def _run(cmd):
    print("  $ " + " ".join(cmd))
    return subprocess.run(cmd, check=False).returncode


def _clone_servo(path):
    return _run(["git", "clone", SERVO_URL, path]) == 0


def _clone_gecko(path):
    if _run(["git", "clone", "--filter=blob:none", "--no-checkout", "--depth", "1",
             GECKO_URL, path]) != 0:
        return False
    if _run(["git", "-C", path, "sparse-checkout", "init", "--cone"]) != 0:
        return False
    if _run(["git", "-C", path, "sparse-checkout", "set", *GECKO_TREES]) != 0:
        return False
    return _run(["git", "-C", path, "checkout"]) == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True, help="workspace root")
    ap.add_argument("--data", default=workspace.DATA_DIR,
                    help=f"data dir, relative to root or absolute (default: {workspace.DATA_DIR})")
    ap.add_argument("--servo", default=None, help="existing Servo checkout (default: <root>/servo)")
    ap.add_argument("--gecko", default=None, help="existing Firefox clone (default: <root>/gecko-dev)")
    ap.add_argument("--clone", action="store_true", help="clone missing servo/gecko checkouts")
    ap.add_argument("--cargo-home", default=os.environ.get("CARGO_HOME"))
    ap.add_argument("--rustup-home", default=os.environ.get("RUSTUP_HOME"))
    ap.add_argument("--dry-run", action="store_true", help="validate only; do not write config")
    ap.add_argument("-f", "--force", action="store_true", help="overwrite an existing workspace.json")
    args = ap.parse_args()

    root = os.path.abspath(args.workspace)
    data = workspace._abs(root, args.data)
    servo = workspace._abs(root, args.servo or "servo")
    gecko = workspace._abs(root, args.gecko or "gecko-dev")
    specs = os.path.join(root, "specs-dictionary")

    os.makedirs(root, exist_ok=True)
    os.makedirs(data, exist_ok=True)

    if args.clone:
        if not os.path.isdir(servo):
            print(f"cloning Servo -> {servo}")
            if not _clone_servo(servo):
                print("  servo clone failed; see the recipe below.", file=sys.stderr)
        if not os.path.isdir(gecko):
            print(f"cloning Firefox (sparse) -> {gecko}")
            if not _clone_gecko(gecko):
                print("  gecko clone failed; see the recipe below.", file=sys.stderr)

    paths = {
        "workspace": root,
        "servo": servo,
        "gecko": gecko,
        "specs": specs,
        "data": data,
        "cargo_home": os.path.abspath(args.cargo_home) if args.cargo_home else None,
        "rustup_home": os.path.abspath(args.rustup_home) if args.rustup_home else None,
    }

    print(f"workspace: {root}")
    ok = True
    for key in workspace.REQUIRED:
        p = paths[key]
        state = "ok" if os.path.isdir(p) else "MISSING"
        print(f"  {key:6} {state:7} {p}   (required)")
        if state == "MISSING":
            ok = False
    print(f"  specs  {'ok' if os.path.isdir(specs) else 'lazy':7} {specs}   (built on demand)")
    print(f"  data   ok      {data}")

    miss = workspace.missing(paths)
    if miss:
        print("\nConstruct the missing prerequisites:\n")
        for key in ("servo", "gecko", "specs"):
            if key in miss:
                print(f"- {key}:")
                print(f"    {miss[key]}\n")

    if not args.dry_run:
        config = workspace.config_path(root)
        cfg = {
            "workspace": root,
            "servo": _rel_or_abs(root, servo),
            "gecko": _rel_or_abs(root, gecko),
            "specs": _rel_or_abs(root, specs),
            "data": _rel_or_abs(root, data),
        }
        if paths["rustup_home"]:
            cfg["rustup_home"] = paths["rustup_home"]
        if paths["cargo_home"]:
            cfg["cargo_home"] = paths["cargo_home"]
        if os.path.isfile(config) and not args.force:
            print(f"note: {config} exists; not overwriting (use --force).")
        else:
            with open(config, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            print(f"wrote {config}")

        porting = os.path.join(root, "PORTING.md")
        if os.path.isfile(porting):
            print(f"note: {porting} exists; keeping it.")
        else:
            with open(porting, "w", encoding="utf-8") as f:
                f.write(PORTING_SCAFFOLD)
            print(f"scaffolded {porting}")

    print("\nPaste into opencode.jsonc:\n")
    print(workspace.opencode_snippet(paths))

    if not ok:
        print("\nWorkspace is incomplete: finish the recipes above (or re-run with --clone).")
    else:
        print("\nWorkspace ready.")


if __name__ == "__main__":
    main()
