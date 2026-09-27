#!/usr/bin/env python3
"""Resolve the WPT-fix workspace.

The workspace root is user-provided. It is resolved in this order:

  1. explicit ``cli`` path (``--workspace``)
  2. the ``WPT_FIX_WORKSPACE`` environment variable
  3. the current working directory

The config file ``<root>/workspace.json`` is optional and only refines the
defaults; a workspace layout without it works. It may contain:

  <root>/servo             local Servo checkout (build + WPT target)
  <root>/gecko-dev         Firefox (mozilla/gecko-dev) sparse clone
  <root>/specs-dictionary  spec dictionary (dict/ + _src/webref, from w3c/webref)
  <root>/wpt-fix           data root: modules/, reports/, solutions/,
                           inventory.json, baselines/logs

``servo`` and ``gecko`` are required; ``specs`` may be built lazily when a
module's specs are first needed. The data root is configurable via ``data``.

Any individual path in ``workspace.json`` may be absolute or relative to
``workspace``.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXAMPLE = os.path.join(ROOT, "workspace.example.json")

DEFAULT_SUBDIRS = {
    "servo": "servo",
    "gecko": "gecko-dev",
    "specs": "specs-dictionary",
}
REQUIRED = ("servo", "gecko")
DATA_DIR = "wpt-fix"

CONSTRUCT_HINTS = {
    "servo": (
        "git clone https://github.com/servo/servo {path}\n"
        "    cd {path} && mach bootstrap -y && mach build --release"
    ),
    "gecko": (
        "git clone --filter=blob:none --no-checkout --depth 1 "
        "https://github.com/mozilla/gecko-dev {path}\n"
        "    cd {path} && git sparse-checkout init --cone\n"
        "    git sparse-checkout set dom/animation servo/components/style\n"
        "    git checkout"
    ),
    "specs": (
        "obtain the spec-dictionary checkout (from w3c/webref) at {path}\n"
        "    generate it with the wpt-fix skill's"
        " subskills/spec-lookup/generate.py (--dict {path})"
    ),
}


class WorkspaceError(RuntimeError):
    """Raised when no usable workspace root can be resolved."""


def config_path(root):
    """Return the config file path for a workspace root."""
    return os.path.join(root, "workspace.json")


def _abs(base, value):
    if not value:
        return None
    return os.path.abspath(value if os.path.isabs(value) else os.path.join(base, value))


def load(cli=None):
    """Return the merged raw config (CLI/env/cwd + file + defaults)."""
    ws = cli or os.environ.get("WPT_FIX_WORKSPACE") or os.getcwd()
    ws = os.path.abspath(ws)
    if not os.path.isdir(ws):
        raise WorkspaceError(
            f"workspace root '{ws}' does not exist; create it with "
            "scripts/workspace_init.py --workspace <root> (or fix "
            "WPT_FIX_WORKSPACE / --workspace)."
        )

    cfg = {}
    path = config_path(ws)
    if os.path.isfile(path):
        with open(path, encoding="utf-8-sig") as f:
            cfg = json.load(f)

    cfg["workspace"] = ws
    for key, default in DEFAULT_SUBDIRS.items():
        cfg.setdefault(key, default)
    cfg.setdefault("data", DATA_DIR)
    return cfg


def resolve(cli=None):
    """Return the workspace with every path made absolute."""
    cfg = load(cli)
    ws = cfg["workspace"]
    out = {"workspace": ws}
    for key in DEFAULT_SUBDIRS:
        out[key] = _abs(ws, cfg.get(key)) or os.path.join(ws, DEFAULT_SUBDIRS[key])
    out["data"] = _abs(ws, cfg.get("data")) or os.path.join(ws, DATA_DIR)
    out["cargo_home"] = os.path.abspath(
        cfg["cargo_home"]
    ) if cfg.get("cargo_home") else os.environ.get("CARGO_HOME")
    out["rustup_home"] = os.path.abspath(
        cfg["rustup_home"]
    ) if cfg.get("rustup_home") else os.environ.get("RUSTUP_HOME")
    return out


def missing(paths):
    """Return ``{key: construction_hint}`` for required paths that don't exist."""
    out = {}
    for key in REQUIRED:
        p = paths.get(key)
        if not p or not os.path.isdir(p):
            out[key] = CONSTRUCT_HINTS[key].format(path=p or "<path>")
    if not os.path.isdir(paths.get("specs") or ""):
        out["specs"] = CONSTRUCT_HINTS["specs"].format(path=paths.get("specs") or "<path>")
    return out


def opencode_snippet(paths):
    """Return the opencode.jsonc ``references`` block for this workspace."""
    def fwd(p):
        return (p or "").replace("\\", "/")

    refs = {
        "specs": {
            "path": fwd(paths.get("specs")),
            "description": (
                "Web platform spec dictionary (generated from w3c/webref). "
                "Markdown lookup for CSS properties, spec terms, and WebIDL."
            ),
        },
    }
    if paths.get("gecko"):
        refs["gecko"] = {
            "path": fwd(paths["gecko"]),
            "description": (
                "Firefox (mozilla/gecko-dev) source, sparse checkout. "
                "Reference implementation for porting features to Servo."
            ),
        }
    return json.dumps({"references": refs}, indent=2, ensure_ascii=False)
