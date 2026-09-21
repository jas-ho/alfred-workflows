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


def test_rename_arguments_are_separate_and_backup_is_local(tmp_path, monkeypatch):
    monkeypatch.setattr(dp.desktop, "data_dir", lambda: tmp_path)
    calls = []
    monkeypatch.setattr(dp.desktop, "native", lambda *args: calls.append(args))
    name = '"; $(literal) 🪟'
    dp.desktop.rename("5", name, True)
    assert len(calls) == 1
    assert calls[0][:3] == ("rename", "5", name)
    assert Path(calls[0][3]).parent == tmp_path
    assert Path(calls[0][3]).name.startswith("names-before-rename-")
    assert calls[0][4] == "current"


def test_concurrent_rename_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(dp.desktop, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(
        dp.desktop, "native", lambda *args: pytest.fail("Unexpected rename")
    )
    with (tmp_path / "rename.lock").open("a") as lock:
        dp.desktop.fcntl.flock(
            lock, dp.desktop.fcntl.LOCK_EX | dp.desktop.fcntl.LOCK_NB
        )
        with pytest.raises(RuntimeError, match="already in progress"):
            dp.desktop.rename("5", "Research", True)


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
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_timed_out_rename_attempts_background_relaunch(tmp_path, monkeypatch):
    monkeypatch.setattr(dp.desktop, "data_dir", lambda: tmp_path)

    def timeout(*args):
        raise subprocess.TimeoutExpired("osascript", 60)

    monkeypatch.setattr(dp.desktop, "native", timeout)
    launches = []
    monkeypatch.setattr(
        dp.subprocess, "run", lambda args, **kwargs: launches.append(args)
    )
    with pytest.raises(subprocess.TimeoutExpired):
        dp.desktop.rename("5", "Research", True)
    assert launches == [["/usr/bin/open", "-g", "-j", "-b", "app.doorplate.Doorplate"]]


def test_close_picker_current_first_without_alfred_learning(state):
    state["active"] = "2"
    items = dp.close_items(state, "")
    assert [json.loads(i["arg"])["id"] for i in items] == ["2", "5", "3"]
    assert all("uid" not in i for i in items)
    assert items[0]["subtitle"].startswith("Current desktop")
    assert json.loads(dp.close_items(state, "writing research")[0]["arg"])["id"] == "5"
    assert not dp.close_items(state, "missing")[0]["valid"]


@pytest.mark.parametrize(
    "query,space_id,expected",
    [("research", None, "5"), ("2", None, "3"), (None, "2", "2"), (None, None, "5")],
)
def test_private_resolver_uses_stable_ids_and_explicit_numeric_order(
    state, query, space_id, expected
):
    state["desktops"][0]["name"] = "Research"
    state["desktops"][2]["name"] = "2"
    assert dp.desktop.resolve_target(state, query, space_id)["id"] == expected


def test_private_resolver_rejects_ambiguity_and_fullscreen(state):
    state["desktops"][1]["name"] = "Research too"
    with pytest.raises(ValueError, match="Multiple"):
        dp.desktop.resolve_target(state, "rese")
    state["active"] = "999"
    with pytest.raises(ValueError, match="No matching regular"):
        dp.desktop.resolve_target(state)


@pytest.mark.parametrize("sid", ["0", "-1", "2.2", "9007199254740992", "garbage"])
def test_private_helper_rejects_unsafe_ids(sid):
    with pytest.raises(ValueError):
        dp.desktop.valid_id(sid)


def test_alfred_close_uses_bridge_and_waits_for_terminal_result(monkeypatch):
    calls = []

    def send(request):
        calls.append(request)
        return {
            "id": "a" * 32,
            "operation": "close",
            "status": "complete",
            "removal_verified": True,
        }

    monkeypatch.setattr(dp.workspace, "send", send)
    assert dp.perform_action({"action": "close", "id": "5"}) == ""
    assert calls == [
        {
            "operation": "close",
            "space_id": "5",
            "execute": True,
            "confirm": True,
            "notify": True,
        }
    ]


def test_alfred_reports_blocked_result_not_success(monkeypatch):
    monkeypatch.setattr(
        dp.workspace,
        "send",
        lambda request: {
            "id": "a" * 32,
            "status": "blocked",
            "error": "App needs attention",
        },
    )
    with pytest.raises(RuntimeError, match="App needs attention"):
        dp.perform_action({"action": "close", "id": "5"})
