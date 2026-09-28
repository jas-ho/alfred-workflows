"""Palette conveniences: rename current, ⌘ switch, ⌥ all apps, project suggestions."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "workflows/new-workspace"))
import workspace_terminal as terminal  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ws = load("convenience_workspace", "workflows/new-workspace/workspace.py")
palette = load("convenience_palette", "workflows/doorplate/palette.py")

STATE = {
    "desktops": [
        {"id": "5", "number": 1, "name": "immo"},
        {"id": "7", "number": 2, "name": ""},
    ],
    "active": "7",
}
APPS = [
    {"name": "Microsoft Edge", "opener": "chromium", "extra": True},
    {"name": "Ghostty", "opener": "ghostty"},
]


def root(query, **kwargs):
    return palette.render("root", query, state=STATE, **kwargs)["items"]


def by_uid(rows, uid):
    return next(r for r in rows if r["uid"] == uid)


def test_rename_current_row_targets_active_desktop():
    rows = root("stockholm")
    rename = rows[-1]
    assert rename["uid"] == "ws-root-rename-current"
    assert json.loads(rename["arg"]) == {
        "action": "rename",
        "id": "7",
        "name": "stockholm",
    }
    assert rename["variables"]["ws_screen"] == "execute"
    assert "2 · Desktop 2 → ‘stockholm’" in rename["subtitle"]


@pytest.mark.parametrize(
    "query,state",
    [
        ("IMMO", STATE),  # exact desktop name hides create and rename alike
        ("", STATE),
        ("stockholm", {**STATE, "active": "fullscreen"}),  # cannot be named
    ],
)
def test_rename_current_row_hidden(query, state):
    rows = palette.render("root", query, state=state)["items"]
    assert not any(r["uid"] == "ws-root-rename-current" for r in rows)


def test_cmd_on_desktop_row_switches_directly():
    row = by_uid(root("imm"), "ws-root-5")
    assert row["variables"]["ws_screen"] == "actions"  # plain Return unchanged
    cmd = row["mods"]["cmd"]
    assert json.loads(cmd["arg"]) == {"action": "switch", "id": "5"}
    assert cmd["variables"]["ws_screen"] == "execute"


def test_alt_on_create_rows_requests_all_apps():
    rows = root("stockholm", apps=APPS, description="tmux stockholm in ~/x")
    for uid, stay in (("ws-create-return", False), ("ws-create-stay", True)):
        row = by_uid(rows, uid)
        assert (
            "Microsoft Edge" not in row["subtitle"] and "⌥ all apps" in row["subtitle"]
        )
        alt = row["mods"]["alt"]
        assert json.loads(alt["arg"]) == {
            "action": "create",
            "name": "stockholm",
            "stay": stay,
            "full": True,
        }
        assert "Microsoft Edge" in alt["subtitle"]
        assert alt["variables"] == row["variables"]
        assert "full" not in json.loads(row["arg"])


def test_no_alt_without_extra_apps():
    rows = root("stockholm", apps=[{"name": "Ghostty", "opener": "ghostty"}])
    assert "mods" not in by_uid(rows, "ws-create-return")


def test_suggestions_autocomplete_before_create_and_skip_desktop_names():
    rows = root(
        "st",
        suggestions=[
            ("stockholm", "tmux stockholm in ~/x"),
            ("IMMO", "attaches tmux immo"),
        ],
    )
    uids = [r["uid"] for r in rows]
    assert uids.index("ws-suggest-stockholm") < uids.index("ws-create-return")
    suggestion = by_uid(rows, "ws-suggest-stockholm")
    assert suggestion["autocomplete"] == "stockholm" and suggestion["valid"] is False
    assert "ws-suggest-IMMO" not in uids  # already a desktop row


@pytest.fixture
def tree(tmp_path, monkeypatch):
    monkeypatch.setattr(terminal, "sessions", lambda: ["stash"])
    projects, code = tmp_path / "Projects", tmp_path / "Code"
    for path in [
        "work/2026-03_stockholm",
        "work/stats-club",
        "work/a/b/stationery",  # deeper, no README
        "work/x/docs",
        "life/y/docs",  # ambiguous generic name
    ]:
        (projects / path).mkdir(parents=True)
    (projects / "work/2026-03_stockholm/README.md").write_text("")
    (code / "stockholm-bot").mkdir(parents=True)
    return {
        "project_roots": [
            {"path": str(projects), "depth": 4},
            {"path": str(code), "depth": 1},
        ]
    }


def test_suggestions_rank_sessions_readme_and_depth(tree):
    names = [n for n, _ in terminal.suggestions("st", tree)]
    # README first, then depth across roots (the depth-1 repo beats deeper vault folders).
    assert names == ["stash", "stockholm", "stockholm-bot", "stats-club", "stationery"]
    assert terminal.suggestions("st", tree, limit=2)[1][0] == "stockholm"


def test_suggestions_skip_exact_and_ambiguous(tree):
    assert [n for n, _ in terminal.suggestions("stockholm", tree)] == ["stockholm-bot"]
    assert terminal.suggestions("doc", tree) == []
    assert terminal.suggestions("  ", tree) == []


@pytest.fixture
def two_apps(monkeypatch, tmp_path):
    monkeypatch.setattr(ws, "recipe_data", lambda *a: {})
    monkeypatch.setattr(
        ws,
        "recipe",
        lambda **k: [
            {"opener": "chromium", "name": "Edge", "extra": True},
            {"opener": "obsidian", "name": "Obsidian", "extra": True},
            {"opener": "ghostty", "name": "Ghostty"},
        ],
    )
    monkeypatch.setattr(
        terminal, "resolve", lambda *a: terminal.intent(directory=tmp_path)
    )


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], ["Ghostty"]),
        (["--full"], ["Edge", "Obsidian", "Ghostty"]),
        (["--url", "https://example.org"], ["Edge", "Ghostty"]),
        (["--note", "a/b.md"], ["Obsidian", "Ghostty"]),
    ],
)
def test_create_request_selects_apps(two_apps, args, expected):
    request = ws.create_request(ws.parser().parse_args(["create", "P", *args]))
    assert [a["name"] for a in request["apps"]] == expected


def test_recipe_needs_a_core_app(tmp_path):
    with pytest.raises(ValueError, match="at least one app without extra"):
        ws.recipe(
            data={"apps": [{"app": "/System/Applications/TextEdit.app", "extra": True}]}
        )


def test_ns_fast_path_modifiers(two_apps):
    item = ws.filter_items("P")["items"][0]
    assert "Edge" not in item["subtitle"] and "⌥ all apps" in item["subtitle"]
    assert item["mods"]["alt"]["variables"] == {"workspace_full": "1"}
    assert item["mods"]["cmd+alt"]["variables"] == {
        "workspace_stay": "1",
        "workspace_full": "1",
    }
    assert "Edge" in item["mods"]["alt"]["subtitle"]


def test_palette_action_passes_full(monkeypatch):
    sys.path.insert(0, str(ROOT / "workflows/doorplate"))
    action = load("convenience_action", "workflows/doorplate/palette-action.py")
    seen = {}

    class Workspace:
        parser = staticmethod(ws.parser)

        @staticmethod
        def operation_request(args):
            seen.update(stay=args.stay, full=args.full, name=args.name)
            return {"name": args.name}

        @staticmethod
        def send(request):
            return {"status": "complete"}

    monkeypatch.setitem(
        sys.modules, "doorplate", type("dp", (), {"workspace": Workspace})
    )
    action.perform({"action": "create", "name": "-x", "stay": True, "full": True})
    assert seen == {"stay": True, "full": True, "name": "-x"}


def test_suggestion_exclusions_apply_before_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(terminal, "sessions", lambda: [f"st{i}" for i in range(6)])
    names = terminal.suggestions("st", {}, exclude=[f"ST{i}" for i in range(5)])
    assert [n for n, _ in names] == ["st5"]


def test_session_suggestions_filling_limit_skip_folder_walk(monkeypatch):
    monkeypatch.setattr(terminal, "sessions", lambda: ["sa", "sb", "sc"])
    monkeypatch.setattr(terminal, "folders", lambda *a: pytest.fail("No walk"))
    data = {"project_roots": [{"path": "/nonexistent", "depth": 1}]}
    assert len(terminal.suggestions("s", data, limit=3)) == 3


def run_main(monkeypatch, capsys, query, *, suggest):
    class Workspace:
        @staticmethod
        def send(request, timeout=0):
            return {}

        @staticmethod
        def envelope(result, operation):
            return {"status": "complete", "data": STATE}

        @staticmethod
        def creation_preview(name):
            return APPS, "attaches tmux x"

        creation_suggestions = staticmethod(suggest)

    monkeypatch.setitem(
        sys.modules, "doorplate", type("dp", (), {"workspace": Workspace})
    )
    monkeypatch.setattr(sys, "argv", ["palette", query])
    palette.main(root=True)
    return json.loads(capsys.readouterr().out)["items"]


def test_suggestion_failure_keeps_create_rows(monkeypatch, capsys):
    def fail(*a, **k):
        raise RuntimeError("Cannot search /x: Permission denied")

    rows = run_main(monkeypatch, capsys, "stockholm", suggest=fail)
    assert by_uid(rows, "ws-create-return")["valid"] is True
    assert not any(r["uid"] == "ws-create-unavailable" for r in rows)


def test_numeric_prefix_still_suggests_and_excludes_desktops(monkeypatch, capsys):
    calls = []

    def suggest(prefix, exclude=()):
        calls.append((prefix, list(exclude)))
        return [("2026-research", "attaches tmux 2026-research")]

    rows = run_main(monkeypatch, capsys, "202", suggest=suggest)
    assert calls == [("202", ["immo", ""])]
    assert by_uid(rows, "ws-suggest-2026-research")["autocomplete"] == "2026-research"
