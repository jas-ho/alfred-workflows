"""Tests for the pjws Alfred script filter."""
import json
import os
import subprocess
import sys
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FILTER = ROOT / "workflows/pjws/pj_filter.py"


def _load_filter_module():
    spec = importlib.util.spec_from_file_location("pj_filter", FILTER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pj_filter = _load_filter_module()


def _write_readme(path: Path, frontmatter: str, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}\n---\n{body}", encoding="utf-8")


def _make_projects_root(tmp_path: Path) -> Path:
    root = tmp_path / "Projects"
    (root / "research").mkdir(parents=True)
    (root / "work").mkdir(parents=True)
    (root / "ops").mkdir(parents=True)
    return root


def test_parse_frontmatter_accepts_pjws_block(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    _write_readme(
        readme,
        "title: Enhancing Genomics\nstatus: active\npjws:\n  tmux: eg",
    )
    fm = pj_filter.parse_frontmatter(readme)
    assert fm == {"title": "Enhancing Genomics"}


def test_parse_frontmatter_rejects_missing_pjws_block(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    _write_readme(readme, "title: Plain Project\nstatus: active")
    assert pj_filter.parse_frontmatter(readme) is None


def test_parse_frontmatter_rejects_non_frontmatter_file(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("# Just a heading\n\npjws: appears in body", "utf-8")
    assert pj_filter.parse_frontmatter(readme) is None


def test_parse_frontmatter_strips_quoted_title(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    _write_readme(readme, 'title: "Quoted Title"\npjws:\n  tmux: q')
    fm = pj_filter.parse_frontmatter(readme)
    assert fm == {"title": "Quoted Title"}


def test_parse_frontmatter_falls_back_to_empty_title(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    _write_readme(readme, "pjws:\n  tmux: x")
    assert pj_filter.parse_frontmatter(readme) == {"title": ""}


def test_discover_projects_skips_projects_without_readme(
    tmp_path: Path,
) -> None:
    root = _make_projects_root(tmp_path)
    (root / "research/no-readme").mkdir()
    _write_readme(
        root / "research/with-readme/README.md",
        "title: With\npjws:\n  tmux: w",
    )
    projects = pj_filter.discover_projects(root)
    names = [p["name"] for p in projects]
    assert names == ["with-readme"]


def test_discover_projects_sorted_within_category(tmp_path: Path) -> None:
    root = _make_projects_root(tmp_path)
    for name in ("charlie", "alpha", "bravo"):
        _write_readme(
            root / f"research/{name}/README.md",
            f"title: {name.title()}\npjws:\n  tmux: {name}",
        )
    projects = pj_filter.discover_projects(root)
    assert [p["name"] for p in projects] == ["alpha", "bravo", "charlie"]


def test_discover_projects_ignores_missing_category_dirs(
    tmp_path: Path,
) -> None:
    # Only `research/` exists; other categories should be skipped silently.
    root = tmp_path / "Projects"
    (root / "research").mkdir(parents=True)
    _write_readme(
        root / "research/only/README.md",
        "title: Only\npjws:\n  tmux: only",
    )
    projects = pj_filter.discover_projects(root)
    assert [p["name"] for p in projects] == ["only"]


def test_discover_projects_walks_arbitrary_top_level_dirs(
    tmp_path: Path,
) -> None:
    # The orchestrator resolves projects via `~/Projects/*/<name>` —
    # ANY top-level subdirectory, not a fixed allowlist. The filter must
    # match that discovery contract so loaded projects aren't hidden
    # from Alfred when they live under a category we didn't anticipate
    # (e.g. `archive/`, `2026-Q2/`, or a future new bucket).
    root = tmp_path / "Projects"
    for cat in ("archive", "2026-Q2", "misc"):
        _write_readme(
            root / cat / f"{cat}-p/README.md",
            f"title: {cat}\npjws:\n  tmux: {cat}",
        )
    projects = pj_filter.discover_projects(root)
    cats = sorted(p["category"] for p in projects)
    assert cats == ["2026-Q2", "archive", "misc"]


def test_discover_projects_skips_hidden_top_level_dirs(
    tmp_path: Path,
) -> None:
    root = tmp_path / "Projects"
    _write_readme(
        root / "research/real/README.md",
        "title: Real\npjws:\n  tmux: r",
    )
    # A hidden dir (e.g. `.obsidian` vault metadata) must not be walked.
    _write_readme(
        root / ".obsidian/plugins/fake/README.md",
        "title: Ghost\npjws:\n  tmux: g",
    )
    projects = pj_filter.discover_projects(root)
    assert [p["name"] for p in projects] == ["real"]


def test_discover_projects_returns_empty_when_root_missing(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "no-such-dir"
    assert pj_filter.discover_projects(missing) == []


def test_build_items_sorts_loaded_before_unloaded() -> None:
    projects = [
        {"name": "zulu", "category": "research", "title": "Zulu"},
        {"name": "alpha", "category": "research", "title": "Alpha"},
    ]
    state = {
        "loaded": {
            "3": {"project": "zulu", "adapters": {"tmux": "ready"}},
        },
        "active_obsidian_project": None,
    }
    items = pj_filter.build_items(projects, state)
    assert items[0]["arg"] == "zulu"
    assert items[1]["arg"] == "alpha"
    assert "slot 3" in items[0]["subtitle"]
    assert items[0]["title"].startswith("●")
    assert items[1]["title"].startswith(" ")


def test_build_items_loaded_projects_sorted_by_slot() -> None:
    projects = [
        {"name": "a", "category": "research", "title": "A"},
        {"name": "b", "category": "research", "title": "B"},
    ]
    state = {
        "loaded": {
            "3": {"project": "b", "adapters": {}},
            "1": {"project": "a", "adapters": {}},
        },
        "active_obsidian_project": None,
    }
    items = pj_filter.build_items(projects, state)
    assert [i["arg"] for i in items] == ["a", "b"]


def test_build_items_sorts_slots_numerically_not_lexicographically() -> None:
    # Hypothetical future state where the orchestrator issues >9 slots:
    # lexicographic sort would put "10" before "2". Numeric sort keeps
    # 2 before 10 — matches how a human reads "slot N".
    projects = [
        {"name": f"p{i}", "category": "research", "title": f"P{i}"}
        for i in (1, 2, 10)
    ]
    state = {
        "loaded": {
            "10": {"project": "p10", "adapters": {}},
            "2": {"project": "p2", "adapters": {}},
            "1": {"project": "p1", "adapters": {}},
        },
        "active_obsidian_project": None,
    }
    items = pj_filter.build_items(projects, state)
    assert [i["arg"] for i in items] == ["p1", "p2", "p10"]


def test_build_items_shows_adapter_states_in_subtitle() -> None:
    projects = [{"name": "p", "category": "research", "title": "P"}]
    state = {
        "loaded": {
            "1": {
                "project": "p",
                "adapters": {"tmux": "ready", "edge-ws": "deferred"},
            },
        },
        "active_obsidian_project": None,
    }
    items = pj_filter.build_items(projects, state)
    assert "tmux=ready" in items[0]["subtitle"]
    assert "edge-ws=deferred" in items[0]["subtitle"]


def test_build_items_flags_obsidian_singleton_owner() -> None:
    projects = [
        {"name": "a", "category": "research", "title": "A"},
        {"name": "b", "category": "research", "title": "B"},
    ]
    state = {
        "loaded": {
            "1": {"project": "a", "adapters": {"tmux": "ready"}},
            "2": {"project": "b", "adapters": {"tmux": "ready"}},
        },
        "active_obsidian_project": "b",
    }
    items = pj_filter.build_items(projects, state)
    a_item = next(i for i in items if i["arg"] == "a")
    b_item = next(i for i in items if i["arg"] == "b")
    assert "obsidian" not in a_item["subtitle"]
    assert "obsidian" in b_item["subtitle"]


def test_build_items_cmd_modifier_disabled_when_not_loaded() -> None:
    projects = [{"name": "p", "category": "research", "title": "P"}]
    state = {"loaded": {}, "active_obsidian_project": None}
    items = pj_filter.build_items(projects, state)
    assert items[0]["mods"]["cmd"]["valid"] is False
    assert items[0]["variables"]["verb"] == "switch"


def test_build_items_cmd_modifier_unloads_when_loaded() -> None:
    projects = [{"name": "p", "category": "research", "title": "P"}]
    state = {
        "loaded": {"1": {"project": "p", "adapters": {"tmux": "ready"}}},
        "active_obsidian_project": None,
    }
    items = pj_filter.build_items(projects, state)
    cmd = items[0]["mods"]["cmd"]
    assert cmd["valid"] is True
    assert cmd["variables"] == {"verb": "unload"}
    assert cmd["arg"] == "p"


def test_build_items_falls_back_to_name_when_title_empty() -> None:
    projects = [{"name": "my-proj", "category": "ops", "title": "my-proj"}]
    state = {"loaded": {}, "active_obsidian_project": None}
    items = pj_filter.build_items(projects, state)
    assert "my-proj" in items[0]["title"]


def test_build_items_match_string_includes_all_search_tokens() -> None:
    projects = [
        {"name": "enhancing-genomics", "category": "research",
         "title": "Enhancing Genomics"},
    ]
    state = {"loaded": {}, "active_obsidian_project": None}
    items = pj_filter.build_items(projects, state)
    match = items[0]["match"]
    assert "enhancing-genomics" in match
    assert "Enhancing Genomics" in match
    assert "research" in match


def test_match_tokens_splits_slug_so_bare_segments_match() -> None:
    # Alfred matchmode 2 treats the match field as whitespace-tokenised and
    # prefix-matches each query word against at least one match word. The
    # split form lets users type `gen` and still find `enhancing-genomics`.
    match = pj_filter.match_tokens(
        "enhancing-genomics", "Enhancing Genomics", "research",
    )
    tokens = match.split()
    assert "enhancing-genomics" in tokens     # slug intact
    assert "enhancing" in tokens              # split form
    assert "genomics" in tokens
    assert "Enhancing" in tokens
    assert "research" in tokens


def test_match_tokens_handles_underscore_prefixed_slugs() -> None:
    match = pj_filter.match_tokens(
        "2026-03_stockholm", "Stockholm trip", "life",
    )
    tokens = match.split()
    assert "2026-03_stockholm" in tokens
    assert "stockholm" in tokens              # underscore split
    assert "2026" in tokens                   # hyphen split
    assert "Stockholm" in tokens


def test_load_state_returns_empty_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PJWS_STATE_PATH", str(tmp_path / "nope.json"))
    state = pj_filter.load_state()
    assert state == {"loaded": {}, "active_obsidian_project": None}


def test_load_state_survives_corrupt_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    bad = tmp_path / "state.json"
    bad.write_text("{not-json", "utf-8")
    monkeypatch.setenv("PJWS_STATE_PATH", str(bad))
    state = pj_filter.load_state()
    assert state == {"loaded": {}, "active_obsidian_project": None}


def test_load_state_rejects_non_dict_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # If state.json is valid JSON but isn't an object (e.g. a stray `[]`),
    # downstream `state.get(...)` would crash the filter. Defend at the
    # boundary and fall back to the empty baseline.
    bad = tmp_path / "state.json"
    bad.write_text("[]", "utf-8")
    monkeypatch.setenv("PJWS_STATE_PATH", str(bad))
    state = pj_filter.load_state()
    assert state == {"loaded": {}, "active_obsidian_project": None}


@pytest.mark.parametrize("bad_shape", [
    {"loaded": []},                                   # loaded is a list
    {"loaded": {"1": "oops"}},                        # slot entry is a scalar
    {"loaded": {"1": {"project": "p", "adapters": []}}},  # adapters is a list
])
def test_load_state_coerces_nested_non_dict_shapes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad_shape,
) -> None:
    # Hardens load_state against every nested shape the downstream code
    # would indexical-access. Building `items` from these shapes must
    # not raise — silently drop the malformed nodes.
    bad = tmp_path / "state.json"
    bad.write_text(json.dumps(bad_shape), "utf-8")
    monkeypatch.setenv("PJWS_STATE_PATH", str(bad))
    state = pj_filter.load_state()
    # Must still build items without crashing.
    projects = [{"name": "p", "category": "research", "title": "P"}]
    pj_filter.build_items(projects, state)


def test_discover_projects_skips_invalid_slug_dirs(tmp_path: Path) -> None:
    # The orchestrator rejects any name that isn't `^[A-Za-z0-9_\-]+$`.
    # Surfacing such dirs in Alfred would let the user select something
    # that `pjws switch` will immediately bounce — mirror the rule at
    # discovery time.
    root = tmp_path / "Projects"
    _write_readme(
        root / "research/valid-name/README.md",
        "title: OK\npjws:\n  tmux: ok",
    )
    _write_readme(
        root / "research/bad name/README.md",
        "title: Bad\npjws:\n  tmux: bad",
    )
    _write_readme(
        root / "research/dotted.name/README.md",
        "title: Dotted\npjws:\n  tmux: d",
    )
    projects = pj_filter.discover_projects(root)
    assert [p["name"] for p in projects] == ["valid-name"]


def test_end_to_end_script_emits_valid_alfred_json(tmp_path: Path) -> None:
    root = _make_projects_root(tmp_path)
    _write_readme(
        root / "research/alpha/README.md",
        "title: Alpha\npjws:\n  tmux: alpha",
    )
    _write_readme(
        root / "work/beta/README.md",
        "title: Beta\npjws:\n  tmux: beta",
    )
    # Project without pjws block — must be excluded.
    _write_readme(
        root / "research/skipme/README.md",
        "title: Skip\nstatus: active",
    )
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps({
            "loaded": {
                "2": {"project": "beta", "adapters": {"tmux": "ready"}},
            },
            "active_obsidian_project": "beta",
        }),
        "utf-8",
    )
    env = dict(os.environ)
    env["PJWS_PROJECTS_ROOT"] = str(root)
    env["PJWS_STATE_PATH"] = str(state_path)
    r = subprocess.run(
        [sys.executable, str(FILTER)],
        capture_output=True, text=True, env=env,
    )
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    args = [i["arg"] for i in payload["items"]]
    assert args == ["beta", "alpha"]
    assert "obsidian" in payload["items"][0]["subtitle"]


def test_end_to_end_empty_projects_tree_emits_placeholder(
    tmp_path: Path,
) -> None:
    root = tmp_path / "Projects"
    root.mkdir()
    env = dict(os.environ)
    env["PJWS_PROJECTS_ROOT"] = str(root)
    env["PJWS_STATE_PATH"] = str(tmp_path / "missing.json")
    r = subprocess.run(
        [sys.executable, str(FILTER)],
        capture_output=True, text=True, env=env,
    )
    assert r.returncode == 0
    payload = json.loads(r.stdout)
    assert len(payload["items"]) == 1
    assert payload["items"][0].get("valid") is False
