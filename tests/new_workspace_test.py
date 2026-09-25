"""Validate workspace requests and helper boundaries without opening real windows."""

import importlib.util
import json
import plistlib
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "workflows/new-workspace"
sys.path.insert(0, str(ROOT))


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ws = load("workspace", "workspace.py")
sys.modules["workspace"] = ws
alfred = load("workspace_alfred", "alfred.py")
opener = load("workspace_open_app", "open_app.py")


@pytest.fixture
def config(tmp_path):
    app = tmp_path / "Editor.app"
    (app / "Contents").mkdir(parents=True)
    (app / "Contents/Info.plist").write_bytes(
        plistlib.dumps({"CFBundleIdentifier": "test.editor"})
    )
    path = tmp_path / "recipe.json"
    path.write_text(json.dumps({"apps": [{"app": str(app), "menu": ["File", "New"]}]}))
    return path


def args(config, *extra):
    return ws.parser().parse_args(
        ["create", "Research", "--config", str(config), *extra]
    )


def test_generic_recipe_replaces_default_apps(config):
    request = ws.create_request(args(config))
    assert request["apps"][0]["bundle"] == "test.editor"
    assert request["apps"][0]["opener"] == "generic"
    assert request["directory"] == str(Path.home())
    assert request["note"] is None
    assert request["urls"] == []
    assert request["stay"] is False


@pytest.mark.parametrize(
    "extra",
    [
        ["--url", "javascript:alert(1)"],
        ["--url", "https://example.com"],
        ["--note", "note.md"],
        ["--tmux-session", "existing"],
        ["--directory", "/no-such-workspace-directory"],
    ],
)
def test_invalid_or_inapplicable_options_fail_before_submission(config, extra):
    with pytest.raises(ValueError):
        ws.create_request(args(config, *extra))


def test_duplicate_app_is_rejected(config):
    data = json.loads(config.read_text())
    data["apps"] *= 2
    config.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="only once"):
        ws.recipe(config)


@pytest.mark.parametrize(
    "data",
    [[], {"apps": [{"app": None}]}, {"apps": [{"app": "/some/app", "opener": []}]}],
)
def test_malformed_recipe_has_readable_alfred_error(config, monkeypatch, data):
    config.write_text(json.dumps(data))
    monkeypatch.setattr(ws, "CONFIG", config)
    item = ws.filter_items("Research")["items"][0]
    assert not item["valid"]
    assert item["title"] == "Check workspace configuration"


def test_alfred_client_failure_is_on_notification_stdout(monkeypatch, capsys):
    monkeypatch.setattr(ws, "create_request", lambda _: {})
    monkeypatch.setattr(
        ws, "send", lambda _: (_ for _ in ()).throw(RuntimeError("Worker unavailable"))
    )
    assert alfred.main(["create", "Test"]) == 1
    assert capsys.readouterr().out.strip() == "Worker unavailable"


def test_alfred_preview_preserves_literal_name_and_stay_modifier(config, monkeypatch):
    monkeypatch.setattr(ws, "CONFIG", config)
    name = 'Research "quotes" $(literal)'
    item = ws.filter_items(name)["items"][0]
    assert item["arg"] == name
    assert item["mods"]["cmd"]["variables"]["workspace_stay"] == "1"
    assert "Editor" in item["subtitle"]
    assert not ws.filter_items(" ")["items"][0]["valid"]


def test_tmux_existing_session_attaches_without_creating_or_switching(monkeypatch):
    calls = []
    monkeypatch.setattr(
        opener.terminal, "tmux_binary", lambda: "/opt/homebrew/bin/tmux"
    )
    monkeypatch.setattr(opener, "run", lambda argv: calls.append(argv) or "window-id")
    request = {"tmux_session": "running-agent", "directory": "/tmp", "id": "a" * 32}
    result = opener.open_app(request, {"opener": "ghostty"})
    assert result["tmux_session"] == "running-agent"
    assert len(calls) == 2
    assert (
        calls[-1][-1]
        == "/usr/bin/env -u TMUX -u TMUX_TMPDIR /opt/homebrew/bin/tmux attach-session -t =running-agent"
    )
    assert "running-agent" not in calls[-1][2]  # data is argv, not script source


def test_new_tmux_session_gets_directory_and_explicit_path(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        opener.terminal, "tmux_binary", lambda: "/opt/homebrew/bin/tmux"
    )
    monkeypatch.setattr(opener, "run", lambda argv: calls.append(argv) or "window-id")
    monkeypatch.setenv("PATH", "/opt/homebrew/bin:/usr/bin")
    directory = tmp_path / 'with "quotes"'
    directory.mkdir()
    request = {
        "directory": str(directory),
        "id": "b" * 32,
        "name": "Research Notes",
    }
    result = opener.open_app(request, {"opener": "ghostty"})
    assert calls[0] == [
        "/opt/homebrew/bin/tmux",
        "new-session",
        "-d",
        "-s",
        "ws-research-notes",
        "-c",
        request["directory"],
        "-e",
        "PATH=" + opener.terminal.environment()["PATH"],
    ]
    assert result["tmux_session"] == "ws-research-notes"


def test_blank_obsidian_uses_new_leaf_without_creating_a_note(monkeypatch):
    codes = []
    monkeypatch.setattr(opener, "obsidian", lambda spec, code: codes.append(code) or "")
    opener.open_app({}, {"opener": "obsidian", "vault": "Projects"})
    assert 'getLeaf("window")' in codes[0]
    assert 'type:"empty"' in codes[0]
    assert "vault.create" not in codes[0]


def test_browser_urls_are_arguments_not_script_code(monkeypatch):
    calls = []
    monkeypatch.setattr(opener, "run", lambda argv: calls.append(argv) or "123")
    urls = ['https://example.com/?q="&x=$(literal)', "https://example.org"]
    opener.open_app(
        {"urls": urls},
        {"opener": "chromium", "app": "/Applications/Microsoft Edge.app"},
    )
    assert calls[0][-2:] == urls
    assert urls[0] not in calls[0][2]


def test_cli_error_text_with_exit_zero_is_failure(monkeypatch):
    monkeypatch.setattr(
        opener.subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(
            a[0], 0, "Error: CLI disabled", ""
        ),
    )
    with pytest.raises(RuntimeError, match="CLI disabled"):
        opener.run(["obsidian"])


def test_transport_expiry_leaves_no_replayable_request(tmp_path, monkeypatch):
    monkeypatch.setattr(ws, "STATE", tmp_path)
    ticks = [0]
    monkeypatch.setattr(ws.time, "time", lambda: ticks[0])
    monkeypatch.setattr(ws.time, "monotonic", lambda: ticks[0])
    monkeypatch.setattr(ws.time, "sleep", lambda n: ticks.__setitem__(0, ticks[0] + n))
    result = ws.send({"operation": "check"})
    assert result["status"] == "uncertain"
    assert result["id"]
    assert result["acknowledged"] is False
    assert json.loads((tmp_path / "request.json").read_text())["expires"] < ticks[0]


@pytest.mark.parametrize(
    "name,session",
    [
        ("Research Notes", "ws-research-notes"),
        ("Budget: Q4.2026", "ws-budget-q4-2026"),
        ("!!!", "ws-workspace"),
        ("Grüße", "ws-grüße"),
    ],
)
def test_readable_tmux_name_and_collision_suffix(monkeypatch, name, session):
    calls = []

    def run(argv):
        calls.append(argv)
        if "new-session" in argv and argv[4] in (session, session + "-2"):
            raise RuntimeError("duplicate session: " + argv[4])
        return "native-window"

    monkeypatch.setattr(opener.terminal, "tmux_binary", lambda: "/tmux")
    monkeypatch.setattr(opener, "run", run)
    result = opener.open_app({"directory": "/tmp", "name": name}, {"opener": "ghostty"})
    assert result["tmux_session"] == session + "-3"
    assert len(calls) == 5
    assert shlex.split(calls[-1][-1])[-1] == "=" + session + "-3"


def test_tmux_creation_errors_are_not_retried(monkeypatch):
    calls = []

    def run(argv):
        calls.append(argv)
        raise RuntimeError("permission denied")

    monkeypatch.setattr(opener.terminal, "tmux_binary", lambda: "/tmux")
    monkeypatch.setattr(opener, "run", run)
    with pytest.raises(RuntimeError, match="permission denied"):
        opener.open_app({"directory": "/tmp", "name": "Test"}, {"opener": "ghostty"})
    assert len(calls) == 1


def test_ghostty_failure_preserves_created_tmux_identity(monkeypatch):
    def run(argv):
        if "new-session" in argv or "has-session" in argv:
            return ""
        raise RuntimeError("Automation permission denied")

    monkeypatch.setattr(opener.terminal, "tmux_binary", lambda: "/tmux")
    monkeypatch.setattr(opener, "run", run)
    with pytest.raises(opener.WindowOpenError) as caught:
        opener.open_app({"directory": "/tmp", "name": "Test"}, {"opener": "ghostty"})
    assert caught.value.session == "ws-test"


@pytest.mark.parametrize("command", ["create", "alfred"])
def test_partial_creation_message_explains_kept_work_and_next_step(
    monkeypatch, capsys, command
):
    result = {
        "status": "partial",
        "error": "Obsidian did not open",
        "name": "Research",
        "space_id": 123,
        "id": "a" * 32,
        "windows": [{"app": "Edge"}],
        "tmux_session": "ws-research",
    }
    monkeypatch.setattr(ws, "create_request", lambda _: {})
    monkeypatch.setattr(ws, "send", lambda _: result)
    run = alfred.main if command == "alfred" else ws.main
    assert run(["create", "Research"]) == 1
    output = capsys.readouterr()
    message = output.out if command == "alfred" else output.err
    assert "Edge" in message and "Research" in message and "ws-research" in message
    if command == "create":
        assert "workspace switch --id 123" in message
        assert "workspace result " + "a" * 32 in message
    else:
        assert "Use sp" in message


def test_json_failure_remains_machine_readable(monkeypatch, capsys):
    result = {"status": "partial", "error": "App failed", "space_id": 123}
    monkeypatch.setattr(ws, "create_request", lambda _: {})
    monkeypatch.setattr(ws, "send", lambda _: result)
    assert ws.main(["create", "Test", "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "partial"
    assert payload["data"]["space_id"] == "123"
    assert payload["error"]["message"] == "App failed"


def test_private_alfred_close_keeps_gui_confirmation_and_notifications(monkeypatch):
    requests = []
    monkeypatch.setattr(
        ws, "send", lambda request: requests.append(request) or {"status": "complete"}
    )
    assert alfred.main(["close"]) == 0
    assert requests == [
        {"operation": "close", "execute": True, "confirm": True, "notify": True}
    ]
