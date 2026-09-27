#!/usr/bin/env python3
"""D5+D6: run targeted WPT, parse the summary, and diff against a baseline.

Usage:
  python scripts/verify.py <wpt-path...>              # run these paths
  python scripts/verify.py --baseline baseline.json <wpt-path...>  # diff regressions
"""

import argparse
import json
import os
import re
import subprocess
import sys

import workspace

SUMMARY_RE = re.compile(
    r"Ran (?P<total>\d+) tests .*\n"
    r".*?(?P<expected>\d+) ran as expected\."
    r".*?(?P<skipped>\d+) skipped\."
    r"(?:.*?(?P<err>\d+) tests had errors unexpectedly)?"
    r"(?:.*?(?P<fail>\d+) tests failed unexpectedly)?"
    r"(?:.*?(?P<timeout>\d+) tests timed out unexpectedly)?"
    r"(?:.*?(?P<subtest>\d+) tests had unexpected subtest results)?"
    , re.DOTALL)


def parse_summary(text):
    m = SUMMARY_RE.search(text)
    if not m:
        # fallback: find the "Ran N tests" line and "ran as expected"
        ran = re.search(r"Ran (\d+) tests", text)
        expected = re.search(r"(\d+) ran as expected", text)
        if not ran:
            return None
        return {"total": int(ran.group(1)), "expected": int(expected.group(1)) if expected else None, "raw": True}
    g = m.groupdict()
    return {
        "total": int(g["total"]),
        "expected": int(g["expected"]),
        "skipped": int(g["skipped"]),
        "errors": int(g["err"] or 0),
        "failed": int(g["fail"] or 0),
        "timeouts": int(g["timeout"] or 0),
        "subtests": int(g["subtest"] or 0),
    }


def run_wpt(paths, ws, release=True, log_raw=None):
    """Run mach test-wpt with live output streaming.

    Args are passed as separate list items via ``powershell -File`` (no manual
    quoting/length risk), and each output line is printed as it arrives while
    being accumulated for summary parsing.
    """
    mach = os.path.join(ws["servo"], "mach.ps1")
    args = ["test-wpt"]
    if release:
        args.append("--release")
    args.extend(paths)
    if log_raw:
        args.extend(["--log-raw", log_raw])
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if ws.get("rustup_home"):
        env["RUSTUP_HOME"] = ws["rustup_home"]
    if ws.get("cargo_home"):
        env["CARGO_HOME"] = ws["cargo_home"]
    proc = subprocess.Popen(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", mach, *args],
        cwd=ws["servo"], env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )
    chunks = []
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        chunks.append(line)
    proc.wait()
    return "".join(chunks), proc.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default=None,
                    help="workspace root (else WPT_FIX_WORKSPACE env, else the current directory)")
    ap.add_argument("--module", default=None, help="module name under modules/ (scopes reports there)")
    ap.add_argument("--baseline", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--refresh-status", action="store_true",
                    help="refresh the support snapshot in inventory.json after the run")
    ap.add_argument("paths", nargs="+")
    args = ap.parse_args()

    ws = workspace.resolve(args.workspace)
    data = ws["data"]

    if args.module:
        reports_dir = os.path.join(data, "modules", args.module, "reports")
        os.makedirs(reports_dir, exist_ok=True)
        out = args.out or os.path.join(reports_dir, "last-verify.json")
        regressions_path = os.path.join(reports_dir, "regressions.md")
    else:
        reports_dir = os.path.join(data, "reports")
        out = args.out or os.path.join(reports_dir, "last-verify.json")
        regressions_path = os.path.join(reports_dir, "regressions.md")

    status_log = os.path.join(reports_dir, "last-status.jsonl") if args.refresh_status else None
    text, rc = run_wpt(args.paths, ws, log_raw=status_log)
    summary = parse_summary(text)

    result = {"paths": args.paths, "exit_code": rc, "summary": summary}
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"exit={rc} summary={summary}")

    if args.refresh_status:
        try:
            import support
            inv_path = (os.path.join(data, "modules", args.module, "inventory.json")
                        if args.module else os.path.join(data, "inventory.json"))
            inv = {}
            if os.path.isfile(inv_path):
                with open(inv_path, encoding="utf-8-sig") as f:
                    inv = json.load(f)
            inv["support"] = support.snapshot(ws, data, module=args.module, log_raw=status_log)
            with open(inv_path, "w", encoding="utf-8") as f:
                json.dump(inv, f, indent=2, ensure_ascii=False)
            print(f"refreshed support snapshot -> {inv_path}")
        except Exception as e:
            print(f"warning: support refresh failed: {e}", file=sys.stderr)

    if args.baseline and os.path.isfile(args.baseline):
        with open(args.baseline, encoding="utf-8") as f:
            base = json.load(f)
        base_summary = base.get("summary") or base
        if summary and base_summary:
            new_unexpected = sum(summary[k] for k in ("errors", "failed", "timeouts", "subtests"))
            base_unexpected = sum(base_summary.get(k, 0) for k in ("errors", "failed", "timeouts", "subtests"))
            delta = new_unexpected - base_unexpected
            print(f"unexpected: baseline={base_unexpected} now={new_unexpected} delta={delta}")
            if delta > 0:
                reg = f"- [{args.paths}] +{delta} new unexpected (baseline {base_unexpected} -> {new_unexpected})\n"
                with open(regressions_path, "a", encoding="utf-8") as f:
                    f.write(reg)
                print(f"REGRESSION DETECTED (see {regressions_path})")


if __name__ == "__main__":
    main()
