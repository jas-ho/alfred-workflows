"""Terminal matching, CLI boundaries and actual isolated tmux behavior."""

import importlib.util
import json
import shlex
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "workflows/new-workspace"))
import workspace_terminal as terminal  # noqa: E402

assert (
    Path(terminal.__file__).resolve()
    == ROOT / "workflows/new-workspace/workspace_terminal.py"
)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ws = load("linking_workspace", "workflows/new-workspace/workspace.py")
opener = load("linking_opener", "workflows/new-workspace/open_app.py")
palette = load("linking_palette", "workflows/doorplate/palette.py")


@pytest.fixture
def projects(tmp_path, monkeypatch):
    monkeypatch.setattr(terminal, "sessions", lambda: [])
    first, second = tmp_path / "Projects", tmp_path / "Code"
    (first / "life" / "2026-03_stockholm").mkdir(parents=True)
    (second / "stockholm").mkdir(parents=True)
    return {
        "project_roots": [
            {"path": str(first), "depth": 2},
            {"path": str(second), "depth": 1},
        ]
    }


@pytest.mark.parametrize(
    "query,expected",
    [
        ("STOCKHOLM", "2026-03_stockholm"),
        ("  stockholm  ", "2026-03_stockholm"),
        ("2026-03_stockholm", "2026-03_stockholm"),
        ("stock", None),
    ],
)
def test_exact_and_date_prefix_matching(projects, query, expected):
    result = terminal.resolve(query, projects)
    assert result["new_tmux_session"] == expected
    assert result["tmux_session"] is None
    assert result["ambiguous"] is False


def test_existing_session_precedence_and_no_folder_walk(projects, monkeypatch):
    monkeypatch.setattr(terminal, "sessions", lambda: ["Stockholm"])
    monkeypatch.setattr(
        terminal, "folders", lambda *a: pytest.fail("Unneeded folder search")
    )
    assert terminal.resolve("stockholm", projects)["tmux_session"] == "Stockholm"


def test_existing_folder_named_session_attaches(projects, monkeypatch):
    monkeypatch.setattr(terminal, "sessions", lambda: ["2026-03_STOCKHOLM"])
    result = terminal.resolve("stockholm", projects)
    assert result["tmux_session"] == "2026-03_STOCKHOLM"
    assert result["new_tmux_session"] is None


def test_ambiguity_does_not_fall_through(projects):
    root = Path(projects["project_roots"][0]["path"])
    (root / "work" / "stockholm").mkdir(parents=True)
    result = terminal.resolve("stockholm", projects)
    assert result == terminal.intent(ambiguous=True)
    assert "ambiguous" in terminal.describe(result)


@pytest.mark.parametrize(
    "sessions", [["Stockholm", "stockholm"], ["2026-03_Stockholm", "2026-03_stockholm"]]
)
def test_case_colliding_sessions_are_ambiguous(projects, monkeypatch, sessions):
    monkeypatch.setattr(terminal, "sessions", lambda: sessions)
    assert terminal.resolve("stockholm", projects)["ambiguous"]


def test_aliases_deduplicate_and_use_canonical_basename(projects):
    root = Path(projects["project_roots"][0]["path"])
    (root / "work").mkdir()
    (root / "work" / "stockholm").symlink_to(root / "life" / "2026-03_stockholm")
    result = terminal.resolve("stockholm", projects)
    assert result["new_tmux_session"] == "2026-03_stockholm"
    assert not result["ambiguous"]


def test_missing_hidden_files_and_dangling_entries_are_ignored(tmp_path):
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "file").touch()
    (tmp_path / "broken").symlink_to(tmp_path / "missing")
    assert terminal.folders(tmp_path, 1) == []
    assert terminal.folders(tmp_path / "absent", 2) == []


def test_unreadable_path_is_not_a_miss(projects, monkeypatch):
    def denied(path):
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr(terminal.os, "scandir", denied)
    with pytest.raises(RuntimeError, match="Cannot search.*Projects.*--directory ~"):
        terminal.resolve("stockholm", projects)


@pytest.mark.parametrize(
    "roots",
    [
        None,
        {},
        [{"path": "~", "depth": True}],
        [{"path": "~", "depth": 0}],
        [{"path": "~", "depth": 4}],
        [{"depth": 1}],
        [{"path": "", "depth": 1}],
    ],
)
def test_root_validation(roots):
    with pytest.raises(ValueError):
        terminal.project_roots({"project_roots": roots})


def test_omitted_roots_unicode_and_punctuation(tmp_path, monkeypatch):
    monkeypatch.setattr(terminal, "sessions", lambda: ["Straße"])
    assert terminal.resolve("STRASSE", {})["tmux_session"] == "Straße"
    assert terminal.resolve("stockholm", {}) == terminal.intent()
    folder = tmp_path / "2026-13_a.b:c 'Notes'"
    folder.mkdir()
    result = terminal.resolve(
        "a.b:c 'notes'", {"project_roots": [{"path": str(tmp_path), "depth": 1}]}
    )
    assert result["new_tmux_session"] == "2026-13_a_b_c 'Notes'"
    assert result["directory"] == str(folder)


@pytest.mark.parametrize(
    "message,empty",
    [
        ("no server running on /tmp/socket", True),
        ("error connecting to /tmp/socket (No such file or directory)", True),
        ("error connecting to /tmp/socket (Permission denied)", False),
        ("server exited unexpectedly", False),
    ],
)
def test_tmux_no_server_is_distinct_from_failure(monkeypatch, message, empty):
    monkeypatch.setattr(terminal, "tmux_binary", lambda: "/tmux")
    monkeypatch.setattr(
        terminal.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 1, "", message),
    )
    if empty:
        assert terminal.sessions() == []
    else:
        with pytest.raises(RuntimeError, match="Cannot inspect"):
            terminal.sessions()


def test_tmux_timeout_and_environment(monkeypatch):
    monkeypatch.setenv("TMUX", "/wrong/server,1,0")
    monkeypatch.setenv("TMUX_TMPDIR", "/wrong")
    monkeypatch.setattr(terminal, "tmux_binary", lambda: "/tmux")

    def timeout(*a, **kw):
        assert "TMUX" not in kw["env"] and "TMUX_TMPDIR" not in kw["env"]
        assert kw["timeout"] == 2
        raise subprocess.TimeoutExpired(a[0], 2)

    monkeypatch.setattr(terminal.subprocess, "run", timeout)
    with pytest.raises(RuntimeError, match="Cannot inspect"):
        terminal.sessions()


@pytest.fixture
def fake_recipe(monkeypatch):
    monkeypatch.setattr(ws, "recipe_data", lambda *a: {})
    monkeypatch.setattr(
        ws, "recipe", lambda **k: [{"opener": "ghostty", "name": "Ghostty"}]
    )


def test_cli_and_preview_share_resolution(fake_recipe, monkeypatch, tmp_path):
    calls = []

    def resolve(name, data):
        calls.append(name)
        return terminal.intent(directory=tmp_path, new_name="Project")

    monkeypatch.setattr(terminal, "resolve", resolve)
    assert "tmux Project" in ws.filter_items("Project")["items"][0]["subtitle"]
    request = ws.create_request(ws.parser().parse_args(["create", "Project"]))
    assert request["new_tmux_session"] == "Project"
    assert request["directory"] == str(tmp_path)
    assert calls == ["Project", "Project"]  # preview is not a reservation


@pytest.mark.parametrize(
    "args", [["--directory", "~"], ["--tmux-session", "existing 'x'"]]
)
def test_explicit_overrides_bypass_resolution(fake_recipe, monkeypatch, args):
    monkeypatch.setattr(terminal, "resolve", lambda *a: pytest.fail("Must not infer"))
    request = ws.create_request(ws.parser().parse_args(["create", "Project", *args]))
    assert request["new_tmux_session"] is None


def test_recipe_without_ghostty_skips_resolution(fake_recipe, monkeypatch):
    monkeypatch.setattr(
        ws, "recipe", lambda **k: [{"opener": "generic", "name": "Editor"}]
    )
    monkeypatch.setattr(terminal, "resolve", lambda *a: pytest.fail("Must not infer"))
    assert (
        ws.create_request(ws.parser().parse_args(["create", "Project"]))["tmux_session"]
        is None
    )


def test_lookup_failure_cli_json_before_mutation(fake_recipe, monkeypatch, capsys):
    def fail(*a):
        raise RuntimeError("Cannot inspect tmux sessions")

    monkeypatch.setattr(terminal, "resolve", fail)
    monkeypatch.setattr(ws, "send", lambda *a: pytest.fail("No desktop mutation"))
    assert ws.main(["create", "Test", "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed" and payload["error"]["code"] == "client_error"
    assert not ws.filter_items("Test")["items"][0]["valid"]


@pytest.mark.parametrize(
    "query,expected",
    [
        ("", []),
        ("im", [False, True]),
        ("Immo", []),
        ("  IMMO ", []),
        ("no match", [False, True]),
        ("1", [False, True]),
        ("new", [False, True]),
    ],
)
def test_palette_create_visibility_and_order(query, expected):
    state = {"desktops": [{"id": "5", "number": 1, "name": "immo"}], "active": "5"}
    rows = palette.render("root", query, state=state, description="attaches tmux immo")[
        "items"
    ]
    creates = [r for r in rows if r["uid"].startswith("ws-create-")]
    assert [json.loads(r["arg"])["stay"] for r in creates] == expected
    if creates:
        assert rows[-2:] == creates
        assert json.loads(creates[0]["arg"])["name"] == query.strip()
        assert "attaches tmux immo" in creates[0]["subtitle"]
        explicit = palette.render("create", query, description="attaches tmux immo")[
            "items"
        ]
        assert creates == explicit[:2]


def test_create_errors_leave_navigation_and_hide_on_exact_match():
    state = {"desktops": [{"id": "5", "number": 1, "name": "immo"}], "active": "5"}
    rows = palette.render("root", "im", state=state, create_error="tmux unavailable")[
        "items"
    ]
    assert rows[0]["variables"]["ws_screen"] == "actions"
    assert rows[-1]["subtitle"] == "tmux unavailable"
    rows = palette.render("root", "IMMO", state=state, create_error="tmux unavailable")[
        "items"
    ]
    assert len(rows) == 1


def test_removed_cwd_stops_before_session_creation(tmp_path, monkeypatch):
    monkeypatch.setattr(terminal, "tmux_binary", lambda: "/tmux")
    monkeypatch.setattr(opener, "run", lambda *a: pytest.fail("No launch"))
    with pytest.raises(RuntimeError, match="Directory does not exist"):
        opener.open_app(
            {"directory": str(tmp_path / "removed"), "new_tmux_session": "project"},
            {"opener": "ghostty"},
        )


@pytest.fixture
def isolated_tmux(monkeypatch, tmp_path):
    binary = shutil.which("tmux", path=terminal.environment()["PATH"])
    if not binary or not shutil.which("trash"):
        pytest.skip("isolated tmux check requires tmux and trash")
    (ROOT / "tmp").mkdir(exist_ok=True)
    # Keep the socket below macOS’s 104-byte Unix socket path limit.
    socket = str(ROOT / "tmp" / ("tm-" + uuid.uuid4().hex + ".sock"))
    wrapper = tmp_path / "tmux"
    wrapper.write_text(
        "#!/bin/sh\nexec "
        + shlex.join([binary, "-f", "/dev/null", "-S", socket])
        + ' "$@"\n'
    )
    wrapper.chmod(0o700)
    monkeypatch.setattr(terminal, "tmux_binary", lambda: str(wrapper))
    try:
        yield str(wrapper)
    finally:
        subprocess.run([str(wrapper), "kill-server"], capture_output=True, timeout=5)
        if Path(socket).exists():
            subprocess.run(["trash", socket], check=True, timeout=5)


def test_real_tmux_named_create_attach_race_and_cwd(
    isolated_tmux, tmp_path, monkeypatch
):
    real_run = opener.run
    launches = []

    def run(argv):
        if argv[0] == "/usr/bin/osascript":
            launches.append(shlex.split(argv[-1]))
            return "test-window"
        return real_run(argv)

    monkeypatch.setattr(opener, "run", run)
    assert terminal.sessions() == []
    request = {
        "directory": str(tmp_path),
        "new_tmux_session": "Folder 'Notes'",
        "name": "Notes",
    }
    first = opener.open_app(request, {"opener": "ghostty"})
    second = opener.open_app(
        request, {"opener": "ghostty"}
    )  # session appeared after resolution
    assert first["tmux_session"] == second["tmux_session"] == "Folder 'Notes'"
    assert terminal.sessions() == ["Folder 'Notes'"]
    cwd = real_run(
        [
            isolated_tmux,
            "list-panes",
            "-t",
            "=Folder 'Notes'",
            "-F",
            "#{pane_current_path}",
        ]
    )
    assert Path(cwd).resolve() == tmp_path.resolve()
    assert launches[0][-1] == "=Folder 'Notes'"


@pytest.mark.parametrize(
    "name",
    [
        "single'quote",
        'double"quote',
        "$HOME;`touch injected`",
        "-leading",
        "=leading",
        "Grüße",
    ],
)
def test_attach_shell_command_preserves_literal_name(tmp_path, monkeypatch, name):
    recorder = tmp_path / "tmux"
    output = tmp_path / "args.json"
    recorder.write_text(
        "#!"
        + sys.executable
        + "\nimport sys, json, os\nfrom pathlib import Path\nPath("
        + repr(str(output))
        + ').write_text(json.dumps([sys.argv[1:], os.environ.get("TMUX"), os.environ.get("TMUX_TMPDIR")]))\n'
    )
    recorder.chmod(0o700)
    monkeypatch.setattr(terminal, "tmux_binary", lambda: str(recorder))
    monkeypatch.setenv("TMUX", "unwanted")
    monkeypatch.setenv("TMUX_TMPDIR", "unwanted")

    def run(argv):
        if argv[0] != "/usr/bin/osascript":
            return ""
        subprocess.run(["/bin/sh", "-c", argv[-1]], cwd=tmp_path, check=True)
        return "test-window"

    monkeypatch.setattr(opener, "run", run)
    opener.open_app(
        {"tmux_session": terminal.session_name(name), "directory": str(tmp_path)},
        {"opener": "ghostty"},
    )
    assert json.loads(output.read_text()) == [
        ["attach-session", "-t", "=" + name],
        None,
        None,
    ]
    assert not (tmp_path / "injected").exists()


@pytest.mark.parametrize(
    "name", ["", "bad\nname", "bad\x00name", "bad\x85name", "foo:1", "foo.1"]
)
def test_control_characters_rejected(name):
    with pytest.raises(ValueError):
        terminal.session_name(name)


def test_attachment_disappearing_after_preflight_stops_before_ghostty(
    tmp_path, monkeypatch
):
    calls = []
    monkeypatch.setattr(terminal, "tmux_binary", lambda: "/tmux")

    def run(argv):
        calls.append(argv)
        assert argv[0] != "/usr/bin/osascript"
        if len(calls) > 1:
            raise RuntimeError("session disappeared")
        return ""

    monkeypatch.setattr(opener, "run", run)
    request = {
        "directory": str(tmp_path),
        "tmux_session": "running",
        "apps": [{"opener": "ghostty"}],
    }
    opener.preflight(request)
    with pytest.raises(opener.WindowOpenError, match="session disappeared"):
        opener.open_app(request, request["apps"][0])
    assert len(calls) == 2


def test_unicode_normalization_for_folders_sessions_and_desktops(tmp_path, monkeypatch):
    folder = tmp_path / "Gru\u0308ße"
    folder.mkdir()
    monkeypatch.setattr(terminal, "sessions", lambda: [])
    data = {"project_roots": [{"path": str(tmp_path), "depth": 1}]}
    assert terminal.resolve("GRÜSSE", data)["directory"] == str(folder)
    monkeypatch.setattr(terminal, "sessions", lambda: ["Gru\u0308ße"])
    assert terminal.resolve("Grüße", {})["tmux_session"] == "Gru\u0308ße"
    state = {
        "desktops": [{"id": "1", "number": 1, "name": "Gru\u0308ße"}],
        "active": "1",
    }
    rows = palette.render("root", "Grüße", state=state)["items"]
    assert len(rows) == 1 and rows[0]["variables"]["ws_screen"] == "actions"


def test_empty_running_tmux_server_inventory(monkeypatch):
    monkeypatch.setattr(terminal, "tmux_binary", lambda: "/tmux")
    monkeypatch.setattr(
        terminal.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, "", ""),
    )
    assert terminal.sessions() == []


def test_symlink_loops_are_ignored_at_each_depth(tmp_path):
    (tmp_path / "loop").symlink_to(tmp_path / "loop")
    (tmp_path / "category").mkdir()
    (tmp_path / "category" / "loop").symlink_to(tmp_path / "category" / "loop")
    assert terminal.folders(tmp_path, 1) == [tmp_path / "category"]
    assert terminal.folders(tmp_path, 2) == []


def test_check_reports_invalid_roots(fake_recipe, monkeypatch):
    monkeypatch.setattr(ws, "recipe_data", lambda *a: {"project_roots": None})
    request = ws.operation_request(ws.parser().parse_args(["check"]))
    assert "project_roots" in request["apps_error"]


def test_exact_match_navigation_does_not_lookup_terminal(monkeypatch, capsys):
    import types

    state = {"desktops": [{"id": "1", "number": 1, "name": "immo"}], "active": "1"}
    fake_workspace = types.SimpleNamespace(
        send=lambda *a, **k: {"status": "complete", **state},
        envelope=lambda result, _: {"status": "complete", "data": state},
        creation_preview=lambda *a: pytest.fail(
            "Hidden Create must not delay navigation"
        ),
    )
    monkeypatch.setitem(
        sys.modules, "doorplate", types.SimpleNamespace(workspace=fake_workspace)
    )
    monkeypatch.setattr(sys, "argv", ["palette.py", "IMMO"])
    palette.main(root=True)
    rows = json.loads(capsys.readouterr().out)["items"]
    assert len(rows) == 1


@pytest.mark.parametrize("name", ["-leading", "=leading", "Grüße"])
def test_real_tmux_exact_literal_names(isolated_tmux, tmp_path, name):
    opener.new_session(isolated_tmux, name, str(tmp_path))
    assert terminal.sessions() == [name]
    opener.run([isolated_tmux, "has-session", "-t", "=" + name])


def test_older_workspace_installation_keeps_desktop_navigation(monkeypatch, capsys):
    import types

    state = {"desktops": [{"id": "1", "number": 1, "name": "immo"}], "active": "1"}
    legacy = types.SimpleNamespace(
        send=lambda *a, **k: {"status": "complete", **state},
        envelope=lambda result, _: {"status": "complete", "data": state},
    )
    monkeypatch.setitem(
        sys.modules, "doorplate", types.SimpleNamespace(workspace=legacy)
    )
    monkeypatch.setattr(sys, "argv", ["palette.py", "im"])
    palette.main(root=True)
    rows = json.loads(capsys.readouterr().out)["items"]
    assert rows[0]["variables"]["ws_screen"] == "actions"
    assert not rows[1]["valid"]
    assert "Update New Workspace" in rows[1]["subtitle"]
