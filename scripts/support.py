#!/usr/bin/env python3
"""Reusable support-status snapshot for a WPT module (D1 measurement).

A snapshot answers "how supported is this module right now?" without fixing
anything. It is produced by D1 (`discover.py`, stored in `inventory.json`) and
consumed by later stages: dispatch reads dir states, `verify.py
--refresh-status` refreshes it after a fix, and `report.py` renders it.

Per WPT dir, ``state`` is:

  supported        enabled and all executed tests pass
  partial          enabled but some executed tests fail
  unsupported      skipped in include.ini / absent / manifest-skipped (no data)
  unsupported-ran  skipped, but the run covered it anyway (explicit paths
                   bypass subdir skips) — real counts are kept, not zeroed
  unknown          enabled but no run data supplied

Data sources:
  - offline: include.ini skip tree (reused from ``discover``)
  - online : a WPT ``--log-raw`` JSONL (per-test pass/fail/skip)
"""

import json
import os
from datetime import datetime

import discover


def module_scope(data_root, module):
    """Return the ``scope`` list from <data_root>/modules/<module>/module.json (or None)."""
    if not module:
        return None
    mjson = os.path.join(data_root, "modules", module, "module.json")
    with open(mjson, encoding="utf-8-sig") as f:
        return json.load(f).get("scope", [])


def _parse_log_results(log_path):
    """Return {test_path: status} from a WPT --log-raw JSONL (test_end)."""
    out = {}
    if not log_path or not os.path.isfile(log_path):
        return out
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("action") == "test_end" and rec.get("test"):
                out[rec["test"]] = rec.get("status")
    return out


def _under(path, unit):
    path = path.lstrip("/")
    return path == unit or path.startswith(unit + "/")


def _is_skipped(unit, skipped):
    return any(unit == s["path"] or unit.startswith(s["path"] + "/") for s in skipped)


def _counts_for(unit, results):
    c = {"pass": 0, "fail": 0, "skip": 0}
    for test, status in results.items():
        if not _under(test, unit):
            continue
        if status in ("PASS", "OK"):
            c["pass"] += 1
        elif status == "SKIP":
            c["skip"] += 1
        else:
            c["fail"] += 1
    return c


def snapshot(ws, data_root, module=None, scope=None, log_raw=None):
    """Compute a support snapshot for a module/scope. Pure; no writes."""
    servo = ws["servo"]
    include_ini = os.path.join(servo, "tests", "wpt", "include.ini")
    tests_dir = os.path.join(servo, "tests", "wpt", "tests")

    if scope is None:
        scope = module_scope(data_root, module)

    root_skip, tree = discover.parse_include_ini(include_ini)
    skipped = []
    discover.walk_skips(tree, root_skip, "", skipped)
    for d in discover.list_top_level_dirs(tests_dir):
        if d not in set(tree.keys()) and root_skip is True:
            skipped.append({"path": d, "reason": "absent-from-include-ini"})

    if scope is not None:
        units = list(scope)
        skipped = [s for s in skipped if discover.in_scope(s["path"], scope)]
    else:
        units = discover.list_top_level_dirs(tests_dir)

    results = _parse_log_results(log_raw)

    rows = []
    for unit in sorted(set(units)):
        url, _ = discover.find_spec_url(tests_dir, unit)
        c = _counts_for(unit, results)
        if _is_skipped(unit, skipped):
            if (c["pass"] + c["fail"] + c["skip"]) > 0:
                # include.ini-skipped but the run covered it anyway (explicit
                # paths bypass subdir skips): keep the real counts visible.
                state = "unsupported-ran"
            else:
                state = "unsupported"
                c = {"pass": 0, "fail": 0, "skip": 0}
        elif (c["pass"] + c["fail"] + c["skip"]) == 0:
            state = "unknown"
        elif c["fail"] > 0:
            state = "partial"
        else:
            state = "supported"
        rows.append({
            "path": unit,
            "spec": discover.shortname_from_url(url),
            "category": discover.infer_category(unit, url),
            "state": state,
            "pass": c["pass"],
            "fail": c["fail"],
            "skip": c["skip"],
        })

    agg = {"dirs": len(rows), "supported": 0, "partial": 0, "unsupported": 0,
           "unsupported_ran": 0, "unknown": 0, "pass": 0, "fail": 0, "skip": 0}
    for r in rows:
        agg[r["state"].replace("-", "_")] += 1
        agg["pass"] += r["pass"]
        agg["fail"] += r["fail"]
        agg["skip"] += r["skip"]
    executed = agg["pass"] + agg["fail"]
    agg["support_pct"] = round(100.0 * agg["pass"] / executed, 1) if executed else None

    return {
        "module": module,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "source": {"log": log_raw, "offline": log_raw is None},
        "totals": agg,
        "dirs": rows,
    }


def render_md(snap):
    """Render a snapshot as the human-readable support report."""
    t = snap["totals"]
    src = snap.get("source") or {}
    out = []
    out.append(f"# Support status: {snap.get('module') or 'all'}")
    out.append("")
    out.append(f"- Generated: {snap.get('generated')}")
    out.append(f"- Source: `{src['log']}`" if src.get("log") else "- Source: include.ini only (offline)")
    out.append("")
    out.append("## Totals")
    out.append(f"- Dirs: {t['dirs']} (supported {t['supported']}, partial {t['partial']}, "
               f"unsupported {t['unsupported']}, unsupported-ran {t['unsupported_ran']}, "
               f"unknown {t['unknown']})")
    out.append(f"- Tests: {t['pass'] + t['fail'] + t['skip']} "
               f"(pass {t['pass']}, fail {t['fail']}, skip {t['skip']})")
    if t.get("support_pct") is not None:
        out.append(f"- Support: {t['support_pct']}% of executed")
    out.append("")
    out.append("## Dirs")
    out.append("")
    out.append("| Dir | Spec | Category | State | Pass | Fail | Skip |")
    out.append("|---|---|---|---|---|---|---|")
    for r in snap["dirs"]:
        out.append(f"| `{r['path']}` | {r['spec'] or ''} | {r['category'] or ''} | "
                   f"{r['state']} | {r['pass']} | {r['fail']} | {r['skip']} |")
    out.append("")
    return "\n".join(out)
