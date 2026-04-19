#!/usr/bin/env python3
"""Alfred Script Filter for pjws — list projects annotated with load state.

Discovers every `~/Projects/<category>/<name>/README.md` whose frontmatter
contains a `pjws:` block, joins it against the runtime state at
`~/.config/pjws/state.json`, and emits an Alfred JSON feed. Loaded
projects sort to the top, grouped by slot; unloaded projects follow
alphabetically.

Per-item modifiers:
    return      → `pjws switch <name>`  (switch itself falls back to load)
    cmd+return  → `pjws unload <name>`  (valid only when loaded)

PJWS_STATE_PATH / PJWS_PROJECTS_ROOT env vars override the default
locations (used by tests).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

HOME = Path.home()
DEFAULT_STATE_PATH = HOME / ".config/pjws/state.json"
DEFAULT_PROJECTS_ROOT = HOME / "Projects"

TITLE_RE = re.compile(r"^title:\s*(.+?)\s*$", re.MULTILINE)

# Mirror the orchestrator's project-name validation. A loose-named directory
# (spaces, dots, glob metachars) would appear in the filter UI but the
# downstream `pjws switch <name>` call would bounce with "invalid project
# name" — so silently drop these at discovery time.
NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def projects_root() -> Path:
    override = os.environ.get("PJWS_PROJECTS_ROOT")
    return Path(override) if override else DEFAULT_PROJECTS_ROOT


def state_path() -> Path:
    override = os.environ.get("PJWS_STATE_PATH")
    return Path(override) if override else DEFAULT_STATE_PATH


def parse_frontmatter(readme: Path) -> dict[str, str] | None:
    """Return `{title}` for a README whose frontmatter has a `pjws:` block.

    Returns None if the file has no frontmatter or no pjws block.
    Uses byte-bounded read + regex rather than a YAML parser — the only
    field we need is `title`, and pulling in PyYAML for a shebang-Python
    script is overkill.
    """
    try:
        with readme.open(encoding="utf-8", errors="replace") as fh:
            head = fh.read(8192)
    except OSError:
        return None
    if not head.startswith("---"):
        return None
    end = head.find("\n---", 3)
    if end == -1:
        return None
    fm = head[3:end]
    if "\npjws:" not in "\n" + fm:
        return None
    m = TITLE_RE.search(fm)
    title = m.group(1).strip().strip("\"'") if m else ""
    return {"title": title}


def load_state() -> dict[str, Any]:
    """Return the pjws runtime state, or a blank baseline on error.

    A malformed `state.json` (missing file, non-JSON, wrong shape at any
    level) must not crash the filter — Alfred would just show an opaque
    error. Normalise every nested container to the expected dict shape;
    anything that isn't a dict becomes `{}`. Orchestrator writes are
    always well-formed, so this only kicks in when state.json is hand-
    edited or rolled back to a pre-v1 schema.
    """
    try:
        raw = json.loads(state_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        raw = None
    if not isinstance(raw, dict):
        raw = {}
    loaded = raw.get("loaded")
    if not isinstance(loaded, dict):
        loaded = {}
    normalised_loaded: dict[str, Any] = {}
    for slot, entry in loaded.items():
        if not isinstance(entry, dict):
            continue
        adapters = entry.get("adapters")
        if not isinstance(adapters, dict):
            adapters = {}
        normalised_loaded[slot] = {
            "project": entry.get("project"),
            "adapters": adapters,
        }
    return {
        "loaded": normalised_loaded,
        "active_obsidian_project": raw.get("active_obsidian_project"),
    }


def slot_of(state: dict[str, Any], name: str) -> tuple[str | None, dict | None]:
    for slot, entry in state.get("loaded", {}).items():
        if entry.get("project") == name:
            return slot, entry
    return None, None


def discover_projects(root: Path) -> list[dict[str, str]]:
    """Walk every `~/Projects/<category>/<name>/README.md`.

    Iterates every immediate subdirectory of `root` rather than a fixed
    allowlist — the pjws orchestrator itself resolves projects via
    `~/Projects/*/<name>`, so any category the orchestrator accepts must
    be discoverable here too. Hidden dirs (leading `.`) are skipped
    (e.g. `.obsidian`).
    """
    if not root.is_dir():
        return []
    found: list[dict[str, str]] = []
    for cat_dir in sorted(root.iterdir()):
        if not cat_dir.is_dir() or cat_dir.name.startswith("."):
            continue
        for proj in sorted(cat_dir.iterdir()):
            if not proj.is_dir():
                continue
            if not NAME_RE.match(proj.name):
                continue
            readme = proj / "README.md"
            if not readme.is_file():
                continue
            fm = parse_frontmatter(readme)
            if fm is None:
                continue
            found.append({
                "name": proj.name,
                "category": cat_dir.name,
                "title": fm["title"] or proj.name,
            })
    return found


def match_tokens(name: str, title: str, category: str) -> str:
    """Build the Alfred `match` string.

    Alfred (matchmode 2) tokenises both query and match-field on
    whitespace and prefix-matches each query word against at least one
    match word. Hyphens and underscores act as word separators inside
    the match field, so we include the raw slug *plus* the split form
    so users can type either `enhancing-genomics` or bare `gen`.
    """
    slug_words = name.replace("-", " ").replace("_", " ")
    return " ".join(filter(None, [name, slug_words, title, category]))


def build_items(
    projects: list[dict[str, str]], state: dict[str, Any],
) -> list[dict[str, Any]]:
    active_obs = state.get("active_obsidian_project")

    # Loaded first (by numeric slot — lexicographic would misorder
    # slot 10 before slot 2 if the orchestrator ever gets more than 9
    # slots), then unloaded alphabetically. Non-numeric slot IDs (future
    # string-named slots) fall back to a large numeric sentinel +
    # lexicographic tiebreak so they still sort deterministically.
    def sort_key(p: dict[str, str]) -> tuple[int, int, str, str]:
        slot, _ = slot_of(state, p["name"])
        if slot is None:
            return (1, 0, "", p["name"])
        try:
            slot_num = int(slot)
            return (0, slot_num, "", p["name"])
        except ValueError:
            return (0, 10**9, slot, p["name"])

    items: list[dict[str, Any]] = []
    for p in sorted(projects, key=sort_key):
        slot, entry = slot_of(state, p["name"])
        loaded = slot is not None
        if loaded:
            adapters = entry.get("adapters", {}) if entry else {}
            adapters_fmt = (
                ", ".join(f"{k}={v}" for k, v in adapters.items()) or "—"
            )
            obs_badge = " · obsidian" if active_obs == p["name"] else ""
            subtitle = (
                f"slot {slot} · {p['category']} · {adapters_fmt}{obs_badge}"
            )
            title = f"● {p['title']}"
        else:
            subtitle = f"{p['category']} · not loaded"
            title = f"  {p['title']}"

        items.append({
            "title": title,
            "subtitle": subtitle,
            "arg": p["name"],
            "autocomplete": p["name"],
            "match": match_tokens(p["name"], p["title"], p["category"]),
            "variables": {"verb": "switch"},
            "mods": {
                "cmd": (
                    {
                        "valid": True,
                        "arg": p["name"],
                        "subtitle": f"Unload (tear down slot {slot})",
                        "variables": {"verb": "unload"},
                    }
                    if loaded else
                    {
                        "valid": False,
                        "subtitle": "Unload unavailable — project not loaded",
                    }
                ),
            },
        })
    return items


def main() -> int:
    state = load_state()
    projects = discover_projects(projects_root())
    items = build_items(projects, state)
    if not items:
        items.append({
            "title": "No pjws-enabled projects found",
            "subtitle": (
                "Add a `pjws:` block to a project's README.md frontmatter"
            ),
            "valid": False,
        })
    print(json.dumps({"items": items}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
