"""Validate workspace requests and helper boundaries without opening real windows."""

import importlib.util
import json
import plistlib
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "workflows/new-workspace"


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ws = load("workspace", "workspace.py")
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
    assert ws.main(["alfred-action", "Test"]) == 1
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
    monkeypatch.setattr(opener.shutil, "which", lambda _: "/opt/homebrew/bin/tmux")
    monkeypatch.setattr(opener, "run", lambda argv: calls.append(argv) or "window-id")
    request = {"tmux_session": "running-agent", "directory": "/tmp", "id": "a" * 32}
    result = opener.open_app(request, {"opener": "ghostty"})
    assert result["tmux_session"] == "running-agent"
    assert len(calls) == 1
    assert calls[0][-1] == "/opt/homebrew/bin/tmux attach-session -t =running-agent"
    assert "running-agent" not in calls[0][2]  # data is argv, not script source


def test_new_tmux_session_gets_directory_and_explicit_path(monkeypatch):
    calls = []
    monkeypatch.setattr(opener.shutil, "which", lambda _: "/opt/homebrew/bin/tmux")
    monkeypatch.setattr(opener, "run", lambda argv: calls.append(argv) or "window-id")
    monkeypatch.setenv("PATH", "/opt/homebrew/bin:/usr/bin")
    request = {"directory": '/tmp/with "quotes"', "id": "b" * 32}
    result = opener.open_app(request, {"opener": "ghostty"})
    assert calls[0] == [
        "/opt/homebrew/bin/tmux",
        "new-session",
        "-d",
        "-s",
        "ws-" + "b" * 12,
        "-c",
        request["directory"],
        "-e",
        "PATH=/opt/homebrew/bin:/usr/bin",
    ]
    assert result["tmux_session"] == "ws-" + "b" * 12


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
    with pytest.raises(RuntimeError, match="expired"):
        ws.send({"operation": "check"})
    assert json.loads((tmp_path / "request.json").read_text())["expires"] < ticks[0]
