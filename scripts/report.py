#!/usr/bin/env python3
"""D7: aggregate inventory + solutions + verify results into reports.

Produces:
  reports/progress.md
  reports/conclusion.md
  solutions/index.md
"""

import argparse
import json
import os
from datetime import datetime

import support
import workspace

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load_inventory(path):
    if not os.path.isfile(path):
        return {"gaps": []}
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def scan_solutions(solutions_dir):
    rows = []
    if not os.path.isdir(solutions_dir):
        return rows
    for root, _, files in os.walk(solutions_dir):
        for fn in files:
            if fn.endswith(".md") and fn != "index.md":
                rel = os.path.relpath(os.path.join(root, fn), solutions_dir)
                status = "pending"
                with open(os.path.join(root, fn), encoding="utf-8") as f:
                    head = "".join(f.readline() for _ in range(20))
                for line in head.splitlines():
                    if line.startswith("status:"):
                        status = line.split(":", 1)[1].strip()
                        break
                rows.append((rel, status))
    return sorted(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--module", default=None, help="module name under modules/ (scopes solutions/reports there)")
    ap.add_argument("--inventory", default=None)
    ap.add_argument("--workspace", default=None,
                    help="workspace root (else WPT_FIX_WORKSPACE env, else the current directory)")
    args = ap.parse_args()

    ws = workspace.resolve(args.workspace)
    data = ws["data"]

    if args.module:
        mdir = os.path.join(data, "modules", args.module)
        solutions_dir = os.path.join(mdir, "solutions")
        reports_dir = os.path.join(mdir, "reports")
        inventory = args.inventory or os.path.join(mdir, "inventory.json")
    else:
        solutions_dir = os.path.join(data, "solutions")
        reports_dir = os.path.join(data, "reports")
        inventory = args.inventory or os.path.join(data, "inventory.json")

    inv = load_inventory(inventory)
    gaps = inv.get("gaps", [])
    sols = scan_solutions(solutions_dir)

    sup = inv.get("support")
    if not sup and args.module:
        try:
            sup = support.snapshot(ws, data, module=args.module)
        except Exception:
            sup = None

    os.makedirs(reports_dir, exist_ok=True)
    now = datetime.now().isoformat(timespec="seconds")

    # progress.md
    total = len(gaps)
    solved = len([s for s in sols if s[1] == "verified"])
    by_cat = {}
    for g in gaps:
        by_cat.setdefault(g.get("category") or "unknown", 0)
        by_cat[g.get("category") or "unknown"] += 1
    with open(os.path.join(reports_dir, "progress.md"), "w", encoding="utf-8") as f:
        f.write(f"# Progress ({now})\n\n")
        f.write(f"- Discovered gaps: {total}\n")
        f.write(f"- Solution docs: {len(sols)}\n")
        f.write(f"- Verified (passing): {solved}\n")
        if sup:
            t = sup["totals"]
            extra = (f", {t['unsupported_ran']} unsupported-ran"
                     if t.get("unsupported_ran") else "")
            f.write(f"- Support: {t['supported']}/{t['dirs']} dirs supported "
                    f"({t['partial']} partial, {t['unsupported']} unsupported{extra})\n")
        f.write("\nBy category:\n\n")
        for c, n in sorted(by_cat.items()):
            f.write(f"- {c}: {n}\n")

    # conclusion.md
    with open(os.path.join(reports_dir, "conclusion.md"), "w", encoding="utf-8") as f:
        f.write(f"# Conclusion ({now})\n\n")
        f.write(f"Total WPT gaps discovered: {total}.\n")
        f.write(f"Solution docs written: {len(sols)} ({solved} verified).\n")
        if sup:
            t = sup["totals"]
            pct = f" ({t['support_pct']}% of executed)" if t.get("support_pct") is not None else ""
            f.write(f"Support: {t['supported']}/{t['dirs']} dirs supported, "
                    f"{t['partial']} partial, {t['unsupported']} unsupported{pct}.\n")
        f.write("\n(Regenerate after running the loop to reflect the latest state.)\n")

    # support.md
    if sup:
        with open(os.path.join(reports_dir, "support.md"), "w", encoding="utf-8") as f:
            f.write(support.render_md(sup))

    # solutions/index.md
    os.makedirs(solutions_dir, exist_ok=True)
    with open(os.path.join(solutions_dir, "index.md"), "w", encoding="utf-8") as f:
        f.write(f"# Solutions index ({now})\n\n")
        for rel, status in sols:
            f.write(f"- `{status:10}` [{rel}]({rel.replace(chr(92), '/')})\n")

    extra = ", support.md" if sup else ""
    print(f"progress.md, conclusion.md{extra}, solutions/index.md written ({total} gaps, {len(sols)} solutions)")


if __name__ == "__main__":
    main()
