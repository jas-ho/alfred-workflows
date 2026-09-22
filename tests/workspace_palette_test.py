"""Palette transitions and mutation boundaries without touching real desktops."""

import importlib.util
import json
import plistlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "workflows/doorplate"
sys.path.insert(0, str(WORKFLOW))
palette = importlib.import_module("palette")
doorplate = importlib.import_module("doorplate")

spec = importlib.util.spec_from_file_location(
    "palette_action", WORKFLOW / "palette-action.py"
)
assert spec is not None and spec.loader is not None
action = importlib.util.module_from_spec(spec)
spec.loader.exec_module(action)


@pytest.fixture
def state():
    return {
        "active": "12",
        "desktops": [
            {"id": "5", "number": 1, "name": "Research & Writing"},
            {"id": "3", "number": 2, "name": ""},
            {"id": "12", "number": 12, "name": "2"},
        ],
    }


def select(result, uid):
    return next(i for i in result["items"] if i["uid"] == "ws-" + uid)


def follow(item, state):
    env = item["variables"]
    return palette.render(
        env["ws_screen"],
        item["arg"],
        env["ws_selected"],
        env["ws_root_query"],
        state=state,
    )


def test_root_order_numeric_match_and_stale_state_reset(state):
    result = palette.render("root", "", "999", "stale", state=state)
    assert result["variables"] == palette.variables("root")
    assert [i["uid"] for i in result["items"][:3]] == [
        "ws-root-12",
        "ws-root-5",
        "ws-root-3",
    ]
    result = palette.render("root", "2", state=state)
    assert [i["uid"] for i in result["items"]] == ["ws-root-3"]
    assert "Current" not in result["items"][0]["subtitle"]
    assert result["items"][0]["arg"] == ""


@pytest.mark.parametrize(
    "query,uid",
    [
        ("new", "root-create"),
        ("create", "root-create"),
        ("prev", "root-previous"),
        ("back", "root-previous"),
        ("help", "root-help"),
        ("writing research", "root-5"),
    ],
)
def test_root_matching(state, query, uid):
    assert select(palette.render("root", query, state=state), uid)


def test_full_back_sequence_preserves_root_query_and_selected_id(state):
    root = palette.render("root", "research", state=state)
    actions = follow(select(root, "root-5"), state)
    assert actions["variables"] == palette.variables("actions", "5", "research")
    rename = follow(select(actions, "actions-rename-5"), state)
    assert not rename["items"][0]["valid"]
    rename = palette.render("rename", "replacement", "5", "research", state=state)
    restored = follow(select(rename, "back-actions"), state)
    assert restored["items"][0]["title"] == "Switch"
    root = follow(select(restored, "back-root"), state)
    assert root["variables"] == palette.variables("root", "", "research")
    assert root["items"][0]["uid"] == "ws-root-5"


@pytest.mark.parametrize("screen", ["actions", "rename"])
def test_disappeared_target_never_uses_old_number(state, screen):
    result = palette.render(screen, "", "999", "research", state=state)
    assert len(result["items"]) == 2
    assert not result["items"][0]["valid"]
    assert result["items"][1]["variables"]["ws_screen"] == "root"


def test_action_search_keeps_back_and_explicit_close_warning(state):
    items = palette.render("actions", "remove", "5", state=state)["items"]
    assert [i["title"] for i in items] == ["Close…", "← Workspaces"]
    assert "Empty desktops close immediately" in items[0]["subtitle"]
    assert json.loads(items[0]["arg"]) == {"action": "close", "id": "5"}
    assert (
        palette.render("actions", "missing", "5", state=state)["items"][0]["title"]
        == "← Workspaces"
    )


@pytest.mark.parametrize(
    "name", ["--stay", 'Quotes " & $(literal) / Bücher 📚', "new close back"]
)
def test_literal_name_screens_do_not_filter_actions(state, name):
    renamed = palette.render("rename", name, "5", state=state)["items"]
    assert json.loads(renamed[0]["arg"])["name"] == name
    created = palette.render("create", name, apps=[{"name": "Browser"}])["items"]
    assert len(created) == 3
    assert [json.loads(i["arg"])["stay"] for i in created[:2]] == [False, True]
    assert all(json.loads(i["arg"])["name"] == name for i in created[:2])
    assert "Browser" in created[0]["subtitle"]


@pytest.mark.parametrize("screen", ["rename", "create"])
def test_whitespace_name_cannot_execute(state, screen):
    items = palette.render(screen, "   ", "5", state=state)["items"]
    assert all(not item["valid"] for item in items[:-1])
    assert items[-1]["variables"]["ws_screen"] in ("root", "actions")


def test_filter_only_submits_read_only_list(monkeypatch, capsys, state):
    requests = []

    def send(request, *, timeout):
        assert timeout == 5
        requests.append(request)
        return {"id": "a" * 32, "operation": "list", "status": "complete", **state}

    monkeypatch.setattr(doorplate.workspace, "send", send)
    monkeypatch.setattr(sys, "argv", ["palette-root.py", "2"])
    monkeypatch.setenv("ws_screen", "execute")
    monkeypatch.setenv("ws_selected", "999")
    palette.main(root=True)
    result = json.loads(capsys.readouterr().out)
    assert requests == [{"operation": "list"}]
    assert result["items"][0]["variables"]["ws_selected"] == "3"


def test_worker_failure_is_explanatory_and_retains_back(monkeypatch, capsys):
    monkeypatch.setattr(
        doorplate.workspace,
        "send",
        lambda request, **kwargs: {
            "id": "a" * 32,
            "status": "failed",
            "error": "Worker unavailable",
        },
    )
    monkeypatch.setattr(sys, "argv", ["palette.py", ""])
    monkeypatch.setenv("ws_screen", "actions")
    palette.main()
    result = json.loads(capsys.readouterr().out)
    assert not result["items"][0]["valid"]
    assert "workspace check" in result["items"][0]["subtitle"]
    assert result["items"][1]["title"] == "← Workspaces"


@pytest.mark.parametrize("stay", [False, True])
def test_create_once_uses_parser_defaults_and_literal_name(monkeypatch, stay):
    requests = []
    monkeypatch.setattr(
        doorplate.workspace,
        "operation_request",
        lambda args: {
            "operation": args.command,
            "name": args.name,
            "stay": args.stay,
            "directory": args.directory,
        },
    )
    monkeypatch.setattr(
        doorplate.workspace,
        "send",
        lambda request: requests.append(request) or {"status": "complete"},
    )
    assert "Created workspace" in action.perform(
        {"action": "create", "name": "--stay", "stay": stay}
    )
    assert requests == [
        {
            "operation": "create",
            "name": "--stay",
            "stay": stay,
            "directory": str(Path.home()),
        }
    ]


def test_close_reuses_existing_confirmation_bridge_once(monkeypatch):
    requests = []
    monkeypatch.setattr(
        doorplate.workspace,
        "send",
        lambda request: requests.append(request)
        or {"id": "a" * 32, "status": "cancelled"},
    )
    assert action.perform({"action": "close", "id": "5"}) == ""
    assert requests == [
        {
            "operation": "close",
            "space_id": "5",
            "execute": True,
            "confirm": True,
            "notify": False,
        }
    ]


def test_partial_create_reports_kept_work_and_operation_id(monkeypatch):
    monkeypatch.setattr(
        doorplate.workspace, "operation_request", lambda args: {"operation": "create"}
    )
    calls = []
    monkeypatch.setattr(
        doorplate.workspace,
        "send",
        lambda request: calls.append(request)
        or {
            "id": "a" * 32,
            "status": "partial",
            "error": "Window failed",
            "space_id": "5",
            "name": "Test",
            "windows": [],
        },
    )
    result = action.perform({"action": "create", "name": "Test", "stay": False})
    assert "Kept" in result and "workspace result " + "a" * 32 in result
    assert len(calls) == 1


def test_native_graph_routes_navigation_and_mutation_separately():
    data = plistlib.loads((WORKFLOW / "info.plist").read_bytes())
    objects = {o["uid"]: o for o in data["objects"]}
    assert objects["WS-ROOT"]["config"]["keyword"] == "ws||workspace"
    for uid in ("WS-ROOT", "WS-MENU"):
        cfg = objects[uid]["config"]
        assert cfg["alfredfiltersresults"] is False
        assert cfg["argumenttype"] == 1
        assert objects[uid].get("inboundconfig", {}).get("inputmode", 0) == 0
        assert data["connections"][uid] == [
            {
                "destinationuid": "WS-ROUTE",
                "modifiers": 0,
                "modifiersubtext": "",
                "vitoclose": True,
            }
        ]
    conditions = objects["WS-ROUTE"]["config"]["conditions"]
    edges = data["connections"]["WS-ROUTE"]

    def route(screen):
        output = next(
            (c["uid"] for c in conditions if c["matchstring"] == screen), None
        )
        return next(edge for edge in edges if edge.get("sourceoutputuid") == output)

    assert route("root")["destinationuid"] == "WS-ROOT"
    for screen in ("actions", "rename", "create", "help"):
        assert route(screen)["destinationuid"] == "WS-MENU"
        assert route(screen)["vitoclose"] is True
    assert route("execute")["destinationuid"] == "WS-ACTION"
    assert route("execute")["vitoclose"] is False
    assert objects["WS-ACTION"]["config"]["concurrently"] is False
    for uid in ("DP-SEARCH", "DP-RENAME", "DP-CLOSE"):
        assert data["connections"][uid][0]["destinationuid"] == "DP-ACTION"
