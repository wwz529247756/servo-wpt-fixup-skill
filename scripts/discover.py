#!/usr/bin/env python3
"""D1+D2: discover skipped & failed WPT tests and map them to their specs.

Sources:
  - tests/wpt/include.ini   (Servo skip rules; root default is skip: true)
  - tests/wpt/tests/**/META.yml  (each WPT dir declares `spec: <url>`)
  - optional: --log-raw JSONL   (failed/unexpected results)
  - optional: --index webref/ed/index.json (canonical shortname lookup)

Output: inventory.json
"""

import argparse
import json
import os
import re
import sys

import workspace


def parse_include_ini(path):
    """Return (root_skip, tree) where tree maps section -> dict of children
    and '__skip__'. Nesting is indentation-based (2 spaces per level)."""
    root_skip = None
    tree = {}
    stack = [tree]  # stack of dict nodes by depth

    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            indent = len(line) - len(line.lstrip(" \t"))
            depth = indent // 2
            stripped = line.strip()
            if stripped.startswith("["):
                name = stripped.strip("[]").strip()
                node = {}
                while len(stack) > depth + 1:
                    stack.pop()
                stack[-1][name] = node
                stack.append(node)
                continue
            m = re.match(r"skip:\s*(true|false)", stripped)
            if m:
                skip = m.group(1) == "true"
                if len(stack) == 1:
                    root_skip = skip
                else:
                    stack[-1]["__skip__"] = skip
    return root_skip, tree


def walk_skips(tree, parent_skip, prefix, out):
    for name, node in tree.items():
        if name == "__skip__":
            continue
        skip = node.get("__skip__", parent_skip)
        path = f"{prefix}/{name}" if prefix else name
        if skip:
            out.append({"path": path, "reason": "skip-true" if "__skip__" in node else "inherited-skip"})
        walk_skips(node, skip, path, out)


def list_top_level_dirs(tests_dir):
    return sorted(
        d for d in os.listdir(tests_dir)
        if os.path.isdir(os.path.join(tests_dir, d)) and not d.startswith(".")
    )


def find_spec_url(tests_dir, rel_dir):
    """Walk up from the dir to find the nearest META.yml with a `spec:` field."""
    cur = os.path.join(tests_dir, rel_dir)
    while cur.startswith(tests_dir) and cur != tests_dir:
        meta = os.path.join(cur, "META.yml")
        if os.path.isfile(meta):
            url = None
            with open(meta, encoding="utf-8") as f:
                for line in f:
                    m = re.match(r"\s*spec:\s*(\S+)", line)
                    if m:
                        url = m.group(1)
                        break
            if url:
                return url, rel_dir
        cur = os.path.dirname(cur)
        rel_dir = os.path.dirname(rel_dir)
    return None, None


def shortname_from_url(url):
    if not url:
        return None
    path = url.rstrip("/").split("/")[-1]
    return path


def infer_category(rel_dir, url):
    if rel_dir.startswith("css/"):
        return "css"
    if rel_dir.startswith("html/"):
        return "html"
    if url and "csswg" in url:
        return "css"
    if url and "whatwg" in url:
        return "html"
    return "webapi"


def parse_raw_log(path):
    """Parse a --log-raw JSONL file into failed test paths."""
    out = {}
    if not path or not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            action = rec.get("action")
            if action == "test_status":
                if rec.get("status") not in ("PASS", "OK", "SKIP", None) and rec.get("expected") != rec.get("status"):
                    out.setdefault(rec.get("test"), "subtest")
            elif action == "test_end":
                if rec.get("status") not in ("PASS", "OK", "SKIP", None):
                    out.setdefault(rec.get("test"), "failed")
    return out


def in_scope(path, scope):
    for s in scope:
        if path == s or path.startswith(s + "/") or s.startswith(path + "/"):
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default=None,
                    help="workspace root (else WPT_FIX_WORKSPACE env, else the current directory)")
    ap.add_argument("--include-ini", default=None)
    ap.add_argument("--tests-dir", default=None)
    ap.add_argument("--log-raw", default=None)
    ap.add_argument("--list-failed", default=None,
                    help="parse a --log-raw JSONL and print the failing tests, sorted (test-level D1)")
    ap.add_argument("--module", default=None, help="module name under modules/ (loads module.json, scopes + relocates output)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.list_failed:
        failed = parse_raw_log(args.list_failed)
        for path in sorted(failed):
            print(path)
        print(f"# {len(failed)} failing tests", file=sys.stderr)
        return

    ws = workspace.resolve(args.workspace)
    servo = ws["servo"]
    data = ws["data"]
    include_ini = args.include_ini or os.path.join(servo, "tests", "wpt", "include.ini")
    tests_dir = args.tests_dir or os.path.join(servo, "tests", "wpt", "tests")

    scope = None
    out = args.out or os.path.join(data, "inventory.json")
    if args.module:
        mdir = os.path.join(data, "modules", args.module)
        mjson = os.path.join(mdir, "module.json")
        with open(mjson, encoding="utf-8-sig") as f:
            module = json.load(f)
        scope = module.get("scope", [])
        os.makedirs(mdir, exist_ok=True)
        out = os.path.join(mdir, "inventory.json")

    root_skip, tree = parse_include_ini(include_ini)

    skipped = []
    walk_skips(tree, root_skip, "", skipped)

    # top-level dirs absent from include.ini inherit root skip (default true)
    top_level = list_top_level_dirs(tests_dir)
    mentioned = set(tree.keys())
    for d in top_level:
        if d not in mentioned and root_skip is True:
            skipped.append({"path": d, "reason": "absent-from-include-ini"})

    gaps = []
    seen = set()
    for s in skipped:
        if s["path"] in seen:
            continue
        seen.add(s["path"])
        url, rel = find_spec_url(tests_dir, s["path"])
        gaps.append({
            "path": s["path"],
            "kind": "skipped",
            "reason": s["reason"],
            "spec_url": url,
            "spec_shortname": shortname_from_url(url),
            "category": infer_category(s["path"], url),
        })

    failed = parse_raw_log(args.log_raw)
    for path, kind in failed.items():
        gaps.append({
            "path": path,
            "kind": kind,
            "reason": "unexpected",
            "spec_url": None,
            "spec_shortname": None,
            "category": None,
        })

    if scope is not None:
        gaps = [g for g in gaps if in_scope(g["path"], scope)]

    result = {
        "module": args.module,
        "root_skip": root_skip,
        "count": len(gaps),
        "gaps": gaps,
    }
    try:
        import support
        result["support"] = support.snapshot(ws, data, module=args.module, scope=scope,
                                             log_raw=args.log_raw)
    except Exception as e:
        print(f"warning: support snapshot failed: {e}", file=sys.stderr)

    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"wrote {len(gaps)} gaps -> {out}")
    for g in gaps:
        print(f"  [{g['kind']:7}] {g['path']}  spec={g['spec_shortname']}  ({g['reason']})")


if __name__ == "__main__":
    main()
