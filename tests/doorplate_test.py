"""Filtering and action contracts without moving the developer's real desktops."""

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "doorplate", ROOT / "workflows/doorplate/doorplate.py"
)
assert spec is not None and spec.loader is not None
dp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dp)


@pytest.fixture
def state():
    return {
        "active": "5",
        "desktops": [
            {"id": "5", "number": 1, "name": "Research & Writing"},
            {"id": "3", "number": 2, "name": ""},
            {"id": "2", "number": 3, "name": "Bücher 📚"},
        ],
    }


@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("", ["5", "3", "2"]),
        ("research", ["5"]),
        ("writing research", ["5"]),
        ("2", ["3"]),
        ("desktop 2", ["3"]),
        ("BÜCH", ["2"]),
        ("📚", ["2"]),
    ],
)
def test_search_names_numbers_unicode(state, query, ids):
    items = dp.space_items(state, query)
    assert [json.loads(i["arg"])["id"] for i in items] == ids


def test_no_matches_is_not_actionable(state):
    assert dp.space_items(state, "missing")[0]["valid"] is False


def test_back_and_desktop_named_back_are_both_available(state):
    state["desktops"][1]["name"] = "Back"
    items = dp.space_items(state, "back")
    assert [json.loads(i["arg"])["action"] for i in items] == ["back", "switch"]


def test_rename_preview_captures_id_and_preserves_literal_text(state):
    name = 'Quotes " & $(literal) / Bücher'
    item = dp.rename_items(state, f" {name} ")[0]
    assert item["valid"]
    assert "Research & Writing" in item["title"]
    assert json.loads(item["arg"]) == {"action": "rename", "id": "5", "name": name}


def test_empty_name_and_fullscreen_are_not_actionable(state):
    assert not dp.rename_items(state, "   ")[0]["valid"]
    state["active"] = "1840"
    assert not dp.rename_items(state, "Research")[0]["valid"]


def test_switch_resolves_id_after_desktop_reorder(state, monkeypatch):
    state["desktops"][0]["number"] = 3
    monkeypatch.setattr(dp, "native", lambda *args: state)
    calls = []
    monkeypatch.setattr(dp.subprocess, "run", lambda args, **kwargs: calls.append(args))
    assert dp.perform_action({"action": "switch", "id": "5"}) == ""
    assert calls == [["/usr/bin/open", "-g", "doorplate://switch/3"]]


def test_switch_deleted_desktop_does_not_open_url(state, monkeypatch):
    monkeypatch.setattr(dp, "native", lambda *args: state)
    monkeypatch.setattr(
        dp.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("Unexpected URL launch"),
    )
    with pytest.raises(RuntimeError, match="no longer exists"):
        dp.perform_action({"action": "switch", "id": "deleted"})


def test_rename_arguments_are_separate_and_backup_is_local(tmp_path, monkeypatch):
    monkeypatch.setattr(dp, "data_dir", lambda: tmp_path)
    calls = []
    monkeypatch.setattr(dp, "native", lambda *args: calls.append(args))
    name = '"; $(literal) 🪟'
    dp.perform_action({"action": "rename", "id": "5", "name": name})
    assert len(calls) == 1
    assert calls[0][:3] == ("rename", "5", name)
    assert Path(calls[0][3]).parent == tmp_path
    assert Path(calls[0][3]).name.startswith("names-before-rename-")
    assert calls[0][4] == "current"


def test_concurrent_rename_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(dp, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(dp, "native", lambda *args: pytest.fail("Unexpected rename"))
    with (tmp_path / "rename.lock").open("a") as lock:
        dp.fcntl.flock(lock, dp.fcntl.LOCK_EX | dp.fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match="already in progress"):
            dp.perform_action({"action": "rename", "id": "5", "name": "Research"})


def test_native_error_is_shown_in_filter(monkeypatch, capsys):
    def denied(*args):
        raise RuntimeError("No live desktops available.")

    monkeypatch.setattr(dp, "native", denied)
    dp.filter_main("search", "")
    item = json.loads(capsys.readouterr().out)["items"][0]
    assert not item["valid"]
    assert "No live desktops" in item["subtitle"]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is unavailable")
def test_native_bridge_rename_safety_contract():
    result = subprocess.run(
        ["node", str(ROOT / "tests/doorplate_native_test.js")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_timed_out_rename_attempts_background_relaunch(tmp_path, monkeypatch):
    monkeypatch.setattr(dp, "data_dir", lambda: tmp_path)

    def timeout(*args):
        raise subprocess.TimeoutExpired("osascript", 60)

    monkeypatch.setattr(dp, "native", timeout)
    launches = []
    monkeypatch.setattr(
        dp.subprocess, "run", lambda args, **kwargs: launches.append(args)
    )
    with pytest.raises(subprocess.TimeoutExpired):
        dp.perform_action({"action": "rename", "id": "5", "name": "Research"})
    assert launches == [["/usr/bin/open", "-g", "-j", "-b", "app.doorplate.Doorplate"]]


def test_cli_list_json(state, monkeypatch, capsys):
    monkeypatch.setattr(dp, "native", lambda *args: state)
    assert dp.cli_main(["list"]) == 0
    assert json.loads(capsys.readouterr().out) == state


def test_cli_rename_explicit_id_does_not_require_current_space(
    state, monkeypatch, capsys
):
    monkeypatch.setattr(dp, "native", lambda *args: state)
    calls = []
    monkeypatch.setattr(
        dp, "perform_action", lambda payload: calls.append(payload) or "Renamed"
    )
    assert dp.cli_main(["rename", "New Name", "--id", "3"]) == 0
    assert calls[0] == {
        "action": "rename",
        "id": "3",
        "name": "New Name",
        "require_active": False,
    }
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_cli_ambiguous_name_is_error(state, monkeypatch, capsys):
    state["desktops"][1]["name"] = "Research"
    monkeypatch.setattr(dp, "native", lambda *args: state)
    assert dp.cli_main(["switch", "rese"]) == 1
    assert "Multiple desktops" in json.loads(capsys.readouterr().err)["error"]


def test_cli_fullscreen_cannot_rename_current(state, monkeypatch, capsys):
    state["active"] = "1840"
    monkeypatch.setattr(dp, "native", lambda *args: state)
    assert dp.cli_main(["rename", "Research"]) == 1
    assert json.loads(capsys.readouterr().err)["ok"] is False


def test_close_picker_current_first_without_alfred_learning(state):
    state["active"] = "2"
    items = dp.close_items(state, "")
    assert [json.loads(i["arg"])["id"] for i in items] == ["2", "5", "3"]
    assert all("uid" not in i for i in items)
    assert items[0]["subtitle"].startswith("Current desktop")
    assert json.loads(dp.close_items(state, "writing research")[0]["arg"])["id"] == "5"
    assert not dp.close_items(state, "missing")[0]["valid"]


def test_close_deleted_desktop_never_calls_backend(state, monkeypatch):
    monkeypatch.setattr(dp, "native", lambda *args: state)
    monkeypatch.setattr(
        dp.subprocess, "run", lambda *a, **k: pytest.fail("Unexpected close")
    )
    with pytest.raises(RuntimeError, match="No matching desktop"):
        dp.perform_action({"action": "close", "id": "deleted"})


def test_close_transports_literal_name_and_stable_id(state, monkeypatch):
    import base64

    name = '"; dangerous() -- Bücher'
    state["desktops"][0]["name"] = name
    monkeypatch.setattr(dp, "native", lambda *args: state)
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, '{"status":"close_requested"}', "")

    monkeypatch.setattr(dp.subprocess, "run", run)
    assert dp.perform_action({"action": "close", "id": "5"}) == ""
    args, kwargs = calls[0]
    assert "SpaceClose.request(5," in args[-1]
    assert name not in args[-1]
    assert base64.b64encode(name.encode()).decode() in args[-1]
    assert kwargs["timeout"] == 8


@pytest.mark.parametrize("response", ['{"error":"busy"}', '{"status":"closed"}'])
def test_close_requires_backend_ack(state, monkeypatch, response):
    monkeypatch.setattr(dp, "native", lambda *args: state)
    monkeypatch.setattr(
        dp.subprocess,
        "run",
        lambda args, **kw: subprocess.CompletedProcess(args, 0, response, ""),
    )
    with pytest.raises(RuntimeError):
        dp.perform_action({"action": "close", "id": "5"})


def test_cli_close_reports_request_ack(state, monkeypatch, capsys):
    monkeypatch.setattr(dp, "native", lambda *args: state)
    calls = []
    monkeypatch.setattr(
        dp, "perform_action", lambda payload: calls.append(payload) or ""
    )
    assert dp.cli_main(["close"]) == 0
    assert calls == [{"action": "close", "id": "5"}]
    assert json.loads(capsys.readouterr().out)["status"] == "close_requested"
