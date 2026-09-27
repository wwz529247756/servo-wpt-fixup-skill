#!/usr/bin/env python3
"""D1-only support status for a module (standalone, no fixing).

Answers "how supported is module X right now?" without changing code, builds,
solution docs, expectations, or inventory gaps. The snapshot logic is shared
with `discover.py` (D1) and `report.py` (roll-up), so a standalone run and the
pipeline always agree.

Usage:
  python scripts/status.py --module <name> [--workspace <root>]
                           [--log-raw <file> | --run] [--out <md>] [--print]

  --log-raw <file>  parse an existing WPT --log-raw JSONL for pass/fail
  --run             run the module scope via servo-wpt to collect pass/fail
  --print           also print the rendered Markdown report
"""

import argparse
import os

import support
import workspace


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default=None,
                    help="workspace root (else WPT_FIX_WORKSPACE env, else the current directory)")
    ap.add_argument("--module", default=None, help="module name under modules/")
    ap.add_argument("--scope", nargs="*", default=None, help="explicit WPT dirs (overrides module scope)")
    ap.add_argument("--log-raw", default=None, help="existing WPT --log-raw JSONL for pass/fail")
    ap.add_argument("--run", action="store_true", help="run the scope via servo-wpt to collect pass/fail")
    ap.add_argument("--out", default=None, help="output Markdown path")
    ap.add_argument("--print", dest="print_md", action="store_true", help="also print the report")
    args = ap.parse_args()

    ws = workspace.resolve(args.workspace)
    data = ws["data"]
    log_raw = args.log_raw

    if args.run:
        import verify
        scope = args.scope or support.module_scope(data, args.module) or []
        run_log = os.path.join(data, "reports", "status-run.jsonl")
        os.makedirs(os.path.dirname(run_log), exist_ok=True)
        print(f"running {len(scope)} scope dir(s) via servo-wpt ...")
        _, rc = verify.run_wpt(scope, ws, log_raw=run_log)
        print(f"servo-wpt exit={rc}; log={run_log}")
        log_raw = run_log

    snap = support.snapshot(ws, data, module=args.module, scope=args.scope, log_raw=log_raw)
    md = support.render_md(snap)

    if args.out:
        out = args.out
    elif args.module:
        out = os.path.join(data, "modules", args.module, "reports", "support.md")
    else:
        out = os.path.join(data, "reports", "support.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)

    t = snap["totals"]
    pct = f" support={t['support_pct']}%" if t.get("support_pct") is not None else ""
    print(f"support: dirs={t['dirs']} supported={t['supported']} partial={t['partial']} "
          f"unsupported={t['unsupported']} unsupported-ran={t['unsupported_ran']}{pct}")
    print(f"tests={t['pass'] + t['fail'] + t['skip']} pass={t['pass']} fail={t['fail']} skip={t['skip']}")
    print(f"wrote {out}")

    if args.print_md:
        print()
        print(md)


if __name__ == "__main__":
    main()
