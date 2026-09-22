#!/usr/bin/python3
"""Alfred desktop pickers; mutations use the shared workspace operation bridge."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# The New Workspace installation owns the CLI and native implementation.
WORKSPACE_ROOT = Path.home() / ".local/share/workspace"
if not WORKSPACE_ROOT.is_dir():
    WORKSPACE_ROOT = Path(__file__).resolve().parents[1] / "new-workspace"
sys.path.insert(0, str(WORKSPACE_ROOT))
import desktop
import workspace

native = desktop.native


def error_item(message: str) -> dict:
    return {"title": "Doorplate", "subtitle": message, "valid": False}


def action_arg(action: str, **kwargs) -> str:
    return json.dumps({"action": action, **kwargs}, ensure_ascii=False)


def matches(space: dict, query: str) -> bool:
    text = query.strip().casefold()
    if text.isdecimal():
        return space["number"] == int(text)
    return all(
        t in f"{space['number']} desktop {space['name']}".casefold()
        for t in text.split()
    )


def space_items(state: dict, query: str) -> list[dict]:
    items = []
    for space in state["desktops"]:
        number, name = space["number"], space["name"]
        label = name or f"Desktop {number}"
        if not matches(space, query):
            continue
        current = space["id"] == state["active"]
        items.append(
            {
                "title": f"{number} · {label}",
                "subtitle": "Current desktop" if current else "Switch to this desktop",
                "arg": action_arg("switch", id=space["id"]),
                "valid": True,
            }
        )
    if query.strip().casefold() in ("back", "previous"):
        items.insert(
            0,
            {
                "title": "Back to previous desktop",
                "subtitle": "Return to the previously visited desktop",
                "arg": action_arg("back"),
                "valid": True,
            },
        )
    return items or [error_item("No matching desktops.")]


def rename_items(state: dict, query: str) -> list[dict]:
    current = next((s for s in state["desktops"] if s["id"] == state["active"]), None)
    if current is None:
        return [
            error_item(
                "Switch to a regular desktop first; fullscreen Spaces cannot be named."
            )
        ]
    name = query.strip()
    label = current["name"] or f"Desktop {current['number']}"
    return [
        {
            "title": f"Rename {label} to {name}"
            if name
            else "Type a name for this desktop",
            "subtitle": f"Desktop {current['number']} · {label}",
            "icon": {"path": "DP-RENAME.png"},
            "arg": action_arg("rename", id=current["id"], name=name),
            "valid": bool(name),
        }
    ]


def close_items(state: dict, query: str) -> list[dict]:
    desktops = sorted(state["desktops"], key=lambda s: s["id"] != state["active"])
    items = []
    for space in desktops:
        if not matches(space, query):
            continue
        label = space["name"] or f"Desktop {space['number']}"
        current = "Current desktop · " if space["id"] == state["active"] else ""
        items.append(
            {
                "title": f"Close {space['number']} · {label}…",
                "subtitle": current
                + "Empty desktops close immediately; otherwise review windows",
                "icon": {"path": "DP-CLOSE.png"},
                "arg": action_arg("close", id=space["id"]),
                "valid": True,
            }
        )
    return items or [error_item("No matching desktops.")]


def filter_main(mode: str, query: str) -> None:
    try:
        state = native("snapshot")
        items = {"rename": rename_items, "close": close_items}.get(mode, space_items)(
            state, query
        )
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        items = [error_item(str(error))]
    print(json.dumps({"items": items}, ensure_ascii=False))


def perform_action(payload: dict) -> str:
    action = payload["action"]
    if action not in ("switch", "rename", "close", "back"):
        raise ValueError("Unknown desktop action")
    request = {"operation": action}
    if action != "back":
        request["space_id"] = desktop.valid_id(payload["id"])
    if action == "rename":
        request["name"] = payload["name"]
    if action == "close":
        request.update(execute=True, confirm=True, notify=False)
    result = workspace.envelope(workspace.send(request), action)
    if result["status"] not in ("complete", "cancelled"):
        error = result.get("error")
        message = error["message"] if error else "Desktop operation did not complete"
        if result.get("operation_id"):
            message += " (workspace result " + result["operation_id"] + ")"
        raise RuntimeError(message)
    if action == "rename":
        return "Desktop renamed to " + payload["name"]
    if action == "close" and result["status"] == "complete":
        return result["data"].get("message", "Desktop closed")
    return ""


def action_main(raw: str) -> None:
    try:
        message = perform_action(json.loads(raw))
    except (
        RuntimeError,
        OSError,
        ValueError,
        TypeError,
        KeyError,
        subprocess.SubprocessError,
    ) as error:
        message = f"Workspace: {error}"
    if message:
        print(message)
