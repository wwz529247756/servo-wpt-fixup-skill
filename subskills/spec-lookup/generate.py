#!/usr/bin/env python3
"""Generate the spec dictionary (Markdown) from w3c/webref data.

Dictionary root (default: the `specs` entry of the wpt-fix workspace,
overridable with ``--dict``):

  _src/webref/ed/    webref ED data (index.json, css/, dfns/, idl/)
  dict/              generated output (css/, webapi/, html/, catalog.md, README.md)
  specs.json         manifest of covered spec shortnames (tool-maintained)

Usage:
  python generate.py --add <shortname>...   # render specs, append to manifest
  python generate.py                        # regenerate every manifest spec
  python generate.py --dict <path> ...      # explicit dictionary root
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "scripts")
if os.path.isdir(SKILL_SCRIPTS) and SKILL_SCRIPTS not in sys.path:
    sys.path.insert(0, SKILL_SCRIPTS)

MANIFEST_NAME = "specs.json"


def default_dict_root():
    try:
        import workspace
        return workspace.resolve()["specs"]
    except Exception:
        return None


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def strip_generated_header(idl):
    lines = [line for line in idl.splitlines() if not line.startswith("//")]
    while lines and lines[0].strip() == "":
        lines.pop(0)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def render_property(prop):
    lines = []
    lines.append(f"#### `{prop['name']}`")
    lines.append("")
    lines.append(f"- **Syntax:** `{prop.get('value', '')}`")
    if prop.get("initial"):
        lines.append(f"- **Initial:** `{prop['initial']}`")
    if prop.get("appliesTo"):
        lines.append(f"- **Applies to:** {prop['appliesTo']}")
    if prop.get("inherited"):
        lines.append(f"- **Inherited:** {prop['inherited']}")
    if prop.get("percentages"):
        lines.append(f"- **Percentages:** {prop['percentages']}")
    if prop.get("computedValue"):
        lines.append(f"- **Computed value:** {prop['computedValue']}")
    if prop.get("animationType"):
        lines.append(f"- **Animation type:** {prop['animationType']}")
    values = prop.get("values") or []
    if values:
        lines.append("- **Values:**")
        for v in values:
            prose = (v.get("prose") or "").replace("\n", " ").strip()
            lines.append(f"  - `{v.get('name')}` — {prose}")
    lines.append(f"- **Ref:** {prop.get('href', '')}")
    lines.append("")
    return "\n".join(lines)


def render_dfns(dfns):
    # group by type, order by term
    by_type = {}
    for d in dfns:
        term = (d.get("linkingText") or [d.get("id")])[0]
        t = d.get("type") or "dfn"
        by_type.setdefault(t, []).append((term, d))

    lines = []
    for t in sorted(by_type):
        lines.append(f"### {t}")
        lines.append("")
        for term, d in sorted(by_type[t], key=lambda x: x[0].lower()):
            head = d.get("heading") or {}
            for_list = ", ".join(d.get("for") or [])
            parts = [f"- **`{term}`**"]
            if for_list:
                parts.append(f"(for {for_list})")
            parts.append(f"— {d.get('href', '')}")
            lines.append(" ".join(parts))
            if head.get("title"):
                num = f" §{head.get('number')}" if head.get("number") else ""
                lines.append(f"  - _Defined in: {head.get('title')}{num}_")
        lines.append("")
    return "\n".join(lines)


def render_css_spec_md(name, cfg, ed):
    props = load_json(os.path.join(ed, cfg["props"]))
    spec = props["spec"]
    out = []
    out.append(f"# {spec['title']}")
    out.append("")
    out.append(f"- **Spec:** {spec['url']}")
    out.append(f"- **Category:** CSS")
    out.append("")
    out.append("## Properties")
    out.append("")
    for p in props.get("properties", []):
        out.append(render_property(p))

    if cfg.get("dfns"):
        dfn = load_json(os.path.join(ed, cfg["dfns"]))
        out.append("## Definitions")
        out.append("")
        out.append(render_dfns(dfn.get("dfns", [])))
    return "\n".join(out)


def render_webapi_md(name, cfg, ed):
    dfn = load_json(os.path.join(ed, cfg["dfns"]))
    spec = dfn["spec"]
    out = []
    out.append(f"# {spec['title']}")
    out.append("")
    out.append(f"- **Spec:** {spec['url']}")
    out.append(f"- **Category:** Web API (DOM/JS)")
    out.append("")
    out.append("## Definitions")
    out.append("")
    out.append(render_dfns(dfn.get("dfns", [])))
    if cfg.get("idl"):
        idl = strip_generated_header(load_text(os.path.join(ed, cfg["idl"])))
        out.append("## WebIDL")
        out.append("")
        out.append("```webidl")
        out.append(idl.strip())
        out.append("```")
        out.append("")
    return "\n".join(out)


def render_catalog(manifest, ed):
    index_path = os.path.join(ed, "index.json")
    by_shortname, by_series = {}, {}
    if os.path.isfile(index_path):
        results = load_json(index_path).get("results", [])
        for r in results:
            if r.get("shortname"):
                by_shortname[r["shortname"]] = r
            s = r.get("series") or {}
            if s.get("shortname"):
                by_series[s["shortname"]] = r

    out = ["# Spec dictionary catalog", "",
           "Specs covered by the dictionary, with metadata from the",
           "[webref](https://github.com/w3c/webref) crawl.",
           ""]
    for sn in manifest:
        r = by_shortname.get(sn) or by_series.get(sn)
        if not r:
            out.append(f"- **{sn}** — (metadata not found)")
            continue
        title = r.get("title") or (r.get("series") or {}).get("title") or sn
        url = r.get("url", "")
        nightly = r.get("nightly") or {}
        status = nightly.get("status", "")
        repo = nightly.get("repository", "")
        out.append(f"## {title}")
        out.append("")
        out.append(f"- **Shortname:** `{sn}`")
        out.append(f"- **URL:** {url}")
        if status:
            out.append(f"- **Status:** {status}")
        if repo:
            out.append(f"- **Repository:** {repo}")
        out.append("")
    return "\n".join(out)


def render_readme(manifest):
    return f"""# Spec dictionary

A Markdown dictionary of web platform specs for agent lookup, generated from
[w3c/webref](https://github.com/w3c/webref) (see `_src/webref`). Spec coverage
is tracked in `{MANIFEST_NAME}` ({len(manifest)} specs).

- `css/<spec>.md` — CSS properties (syntax, initial value, applies-to,
  inherited, per-value prose) + term definitions per spec.
- `webapi/<spec>.md` — Web API term definitions + WebIDL.
- `catalog.md` — covered specs with metadata from the webref crawl.

## How to look things up

1. Grep `css/`, `webapi/`, or `html/` for the property/term; each entry links
   to the authoritative spec — follow the link for full normative text.
2. Not found? Extend: run the wpt-fix skill's
   `subskills/spec-lookup/generate.py --add <shortname>`.
"""


# ---------------------------------------------------------------------------
# Discovery + manifest
# ---------------------------------------------------------------------------

def discover_spec_files(ed, shortname):
    """Auto-discover webref files for a spec shortname.

    webref naming is inconsistent:
      - dfns/<shortname>.json            (e.g. css-view-transitions-1.json)
      - css/<shortname-no-level>.json    for L1, css/<shortname>.json for L2
      - idl/<shortname-no-level>.idl
    Returns dict with optional keys: props, dfns, idl (paths relative to ED).
    """
    base = shortname
    base_no_level = re.sub(r"-\d+$", "", shortname)

    def find(subdir, ext, candidates):
        for cand in candidates:
            p = os.path.join(ed, subdir, cand + ext)
            if os.path.isfile(p):
                return os.path.join(subdir, cand + ext)
        return None

    files = {
        "dfns": find("dfns", ".json", [base, base_no_level]),
        "props": find("css", ".json", [base, base_no_level]),
        "idl": find("idl", ".idl", [base, base_no_level]),
    }
    return {k: v for k, v in files.items() if v}


def category_for(files):
    return "css" if "props" in files else "webapi"


def load_manifest(root):
    path = os.path.join(root, MANIFEST_NAME)
    if os.path.isfile(path):
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f).get("specs", [])
    return []


def save_manifest(root, manifest):
    with open(os.path.join(root, MANIFEST_NAME), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"specs": sorted(manifest)}, f, indent=2, ensure_ascii=False)


def render_spec(ed, out, shortname):
    files = discover_spec_files(ed, shortname)
    if not files:
        print(f"  [warn] no webref files for {shortname}")
        return False
    cat = category_for(files)
    if cat == "css":
        cfg = {k: v for k, v in {"props": files.get("props"), "dfns": files.get("dfns"),
                                 "idl": files.get("idl")}.items() if v}
        text = render_css_spec_md(shortname, cfg, ed)
    else:
        cfg = {k: v for k, v in {"dfns": files.get("dfns"), "idl": files.get("idl")}.items() if v}
        text = render_webapi_md(shortname, cfg, ed)
    with open(os.path.join(out, cat, f"{shortname}.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text + "\n")
    print(f"  {cat}/{shortname}.md")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--add", nargs="*", default=[], metavar="SHORTNAME",
                    help="spec shortnames to render + append to the manifest")
    ap.add_argument("--dict", default=None, help="dictionary root (default: the `specs` workspace entry)")
    args = ap.parse_args()

    root = args.dict or default_dict_root()
    if not root:
        ap.error("no dictionary root: pass --dict <path> (or configure the wpt-fix workspace)")
    ed = os.path.join(root, "_src", "webref", "ed")
    out = os.path.join(root, "dict")
    if not os.path.isdir(ed):
        ap.error(f"webref ED data not found under {ed}")

    for sub in ("css", "webapi", "html"):
        os.makedirs(os.path.join(out, sub), exist_ok=True)

    manifest = load_manifest(root)
    changed = False

    for sn in args.add:
        if sn in manifest:
            print(f"  {sn}: already in {MANIFEST_NAME}; regenerating")
        if render_spec(ed, out, sn):
            if sn not in manifest:
                manifest.append(sn)
                changed = True

    # full regeneration of everything in the manifest
    for sn in list(manifest):
        render_spec(ed, out, sn)

    if args.add and changed:
        save_manifest(root, manifest)
        print(f"updated {MANIFEST_NAME} ({len(manifest)} specs)")

    with open(os.path.join(out, "catalog.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(render_catalog(sorted(manifest), ed) + "\n")
    with open(os.path.join(out, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(render_readme(sorted(manifest)))

    print(f"Generated spec dictionary under {out} ({len(manifest)} specs)")


if __name__ == "__main__":
    main()
