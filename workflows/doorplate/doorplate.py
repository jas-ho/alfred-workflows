#!/usr/bin/python3
"""Alfred and CLI search/rename for Doorplate. Native bridge uses live Space IDs."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def native(*args: str) -> dict:
    result = subprocess.run(
        ["/usr/bin/osascript", "-l", "JavaScript", str(ROOT / "native.js"), *args],
        capture_output=True,
        text=True,
        timeout=60 if args[0] == "rename" else 15,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Doorplate helper failed.")
    payload = json.loads(result.stdout)
    if "error" in payload:
        raise RuntimeError(payload["error"])
    return payload


def error_item(message: str) -> dict:
    return {"title": "Doorplate", "subtitle": message, "valid": False}


def action_arg(action: str, **kwargs) -> str:
    return json.dumps({"action": action, **kwargs}, ensure_ascii=False)


def space_items(state: dict, query: str) -> list[dict]:
    terms = query.casefold().split()
    items = []
    for space in state["desktops"]:
        number, name = space["number"], space["name"]
        label = name or f"Desktop {number}"
        if not all(t in f"{number} desktop {name}".casefold() for t in terms):
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
                "subtitle": "Doorplate’s jump back",
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


def filter_main(mode: str, query: str) -> None:
    try:
        state = native("snapshot")
        items = (
            rename_items(state, query)
            if mode == "rename"
            else space_items(state, query)
        )
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        items = [error_item(str(error))]
    print(json.dumps({"items": items}, ensure_ascii=False))


def data_dir() -> Path:
    path = Path(
        os.environ.get("alfred_workflow_data")
        or (
            Path.home()
            / "Library/Application Support/Alfred/Workflow Data/com.jason.doorplate"
        )
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def perform_action(payload: dict) -> str:
    action = payload["action"]
    if action == "back":
        url = "doorplate://back"
    elif action == "switch":
        # Resolve the stable ID again: desktop order may have changed since filtering.
        state = native("snapshot")
        target = next((s for s in state["desktops"] if s["id"] == payload["id"]), None)
        if target is None:
            raise RuntimeError("That desktop no longer exists. Search again.")
        url = f"doorplate://switch/{target['number']}"
    elif action == "rename":
        name = payload["name"].strip()
        if not name:
            raise RuntimeError("Enter a desktop name.")
        directory = data_dir()
        # Serialize writers: each rename briefly stops and restarts Doorplate.
        with (directory / "rename.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError(
                    "A rename is already in progress. Try again."
                ) from None
            backup = directory / f"names-before-rename-{uuid.uuid4().hex}.json"
            try:
                native(
                    "rename",
                    payload["id"],
                    name,
                    str(backup),
                    "current" if payload.get("require_active", True) else "any",
                )
            except (RuntimeError, OSError, ValueError, subprocess.SubprocessError):
                # A killed/hung osascript cannot execute its own finally block.
                # Best effort recovery, without taking focus or masking the error.
                try:
                    subprocess.run(
                        ["/usr/bin/open", "-g", "-j", "-b", "app.doorplate.Doorplate"],
                        capture_output=True,
                        timeout=10,
                    )
                except (OSError, subprocess.SubprocessError):
                    pass
                raise
        return f"Desktop renamed to {name}"
    else:
        raise RuntimeError("Unknown Doorplate action.")
    subprocess.run(
        ["/usr/bin/open", "-g", url],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return ""


def action_main(raw: str) -> None:
    try:
        message = perform_action(json.loads(raw))
    except (
        RuntimeError,
        OSError,
        ValueError,
        KeyError,
        subprocess.SubprocessError,
    ) as error:
        message = f"Doorplate: {error}"
    # Alfred's notification object displays nonempty output, including failures.
    if message:
        print(message)


def resolve_target(state: dict, query: str | None, space_id: str | None) -> dict:
    spaces = state["desktops"]
    if space_id is not None:
        matches = [s for s in spaces if s["id"] == space_id]
    else:
        query = (query or "").strip().casefold()
        exact = [
            s
            for s in spaces
            if s["name"].casefold() == query or str(s["number"]) == query
        ]
        matches = exact or [s for s in spaces if query in s["name"].casefold()]
    if not matches:
        raise RuntimeError("No matching desktop. Run doorplate list.")
    if len(matches) != 1:
        raise RuntimeError("Multiple desktops match. Use --id from doorplate list.")
    return matches[0]


def cli_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Control Doorplate from a graphical macOS login session. Outputs JSON."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "list", help="List live desktops, stable IDs, names, and the active Space ID"
    )
    switch = commands.add_parser(
        "switch", help="Switch by unique name, number, or stable ID"
    )
    switch.add_argument("query", nargs="?")
    switch.add_argument("--id", dest="space_id")
    rename = commands.add_parser(
        "rename", help="Name the current desktop, or an explicit --id without switching"
    )
    rename.add_argument("name")
    rename.add_argument("--id", dest="space_id")
    commands.add_parser("back", help="Return to Doorplate’s previous desktop")
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            output = native("snapshot")
        else:
            payload = {"action": args.command}
            if args.command == "switch":
                if bool(args.query) == bool(args.space_id):
                    raise RuntimeError(
                        "Specify either a name/number or --id, not both."
                    )
                payload["id"] = resolve_target(
                    native("snapshot"), args.query, args.space_id
                )["id"]
            elif args.command == "rename":
                state = native("snapshot")
                target = resolve_target(state, None, args.space_id or state["active"])
                payload.update(
                    id=target["id"],
                    name=args.name,
                    require_active=args.space_id is None,
                )
            message = perform_action(payload)
            output = {"ok": True, **payload}
            if message:
                output["message"] = message
        print(json.dumps(output, ensure_ascii=False))
        return 0
    except (
        RuntimeError,
        OSError,
        ValueError,
        KeyError,
        subprocess.SubprocessError,
    ) as error:
        print(
            json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(cli_main())
