#!/usr/bin/python3
"""Private GUI-session helper for live desktop identity and saved names."""

from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def interrupted(signum, frame):
    # Raising inside subprocess.run makes it kill and reap its child before
    # unwinding the rename lock and running Doorplate recovery.
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    raise RuntimeError("Desktop helper interrupted; inspect state before retrying")


def native(*args: str) -> dict:
    result = subprocess.run(
        [
            "/usr/bin/osascript",
            "-l",
            "JavaScript",
            str(ROOT / "desktop_native.js"),
            *args,
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=60 if args[0] == "rename" else 15,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Desktop helper failed")
    payload = json.loads(result.stdout)
    if "error" in payload:
        raise RuntimeError(payload["error"])
    return payload


def data_dir() -> Path:
    # Preserve existing backup location; it is independent of the invoking workflow.
    path = (
        Path.home()
        / "Library/Application Support/Alfred/Workflow Data/com.jason.doorplate"
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def valid_id(value: str) -> str:
    if (
        not isinstance(value, str)
        or not re.fullmatch(r"[1-9][0-9]*", value)
        or int(value) > 9007199254740991
    ):
        raise ValueError("Invalid desktop ID; use an ID from workspace list")
    return value


def resolve_target(
    state: dict, query: str | None = None, space_id: str | None = None
) -> dict:
    spaces = state["desktops"]
    if query is not None and space_id is not None:
        raise ValueError("Specify either a name/number or --id")
    if space_id is not None:
        matches = [s for s in spaces if s["id"] == valid_id(space_id)]
    elif query is None:
        matches = [s for s in spaces if s["id"] == state["active"]]
    else:
        text = query.strip().casefold()
        if not text:
            raise ValueError("Enter a desktop name or number")
        if text.isdecimal():
            matches = [s for s in spaces if s["number"] == int(text)]
        else:
            exact = [s for s in spaces if s["name"].casefold() == text]
            matches = exact or [s for s in spaces if text in s["name"].casefold()]
    if not matches:
        raise ValueError("No matching regular desktop. Run workspace list")
    if len(matches) != 1:
        raise ValueError("Multiple desktops match. Use --id from workspace list")
    return matches[0]


def rename(space_id: str, name: str, require_active: bool = False) -> dict:
    valid_id(space_id)
    name = name.strip()
    if not name or len(name) > 120 or any(ord(c) < 32 for c in name):
        raise ValueError(
            "Desktop name must contain 1–120 characters without control characters"
        )
    directory = data_dir()
    with (directory / "rename.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("A rename is already in progress. Try again") from None
        backup = directory / f"names-before-rename-{uuid.uuid4().hex}.json"
        try:
            native(
                "rename",
                space_id,
                name,
                str(backup),
                "current" if require_active else "any",
            )
        except (RuntimeError, OSError, ValueError, subprocess.SubprocessError):
            # A terminated native helper cannot execute its own relaunch finally block.
            try:
                subprocess.run(
                    ["/usr/bin/open", "-g", "-j", "-b", "app.doorplate.Doorplate"],
                    capture_output=True,
                    check=False,
                    timeout=10,
                )
            except (OSError, subprocess.SubprocessError):
                pass
            raise
    return {"space_id": space_id, "name": name, "backup": str(backup)}


def inspect(request: dict) -> dict:
    state = native("snapshot")
    operation = request["operation"]
    if operation in ("rename", "switch", "close"):
        state["target"] = resolve_target(
            state, request.get("query"), request.get("space_id")
        )
    if operation == "check":
        # Do not launch an app, send Apple events, or trigger TCC prompts here.
        problems = [request["apps_error"]] if request.get("apps_error") else []
        for app in request.get("apps", []):
            if not Path(app["app"]).is_dir():
                problems.append("App unavailable: " + app["app"])
            if app["opener"] == "ghostty" and not shutil.which(
                "tmux", path="/opt/homebrew/bin:/usr/local/bin:" + os.defpath
            ):
                problems.append("tmux is not installed")
        state["checks"] = {
            "live_desktops": True,
            "configured_apps": not problems,
            "automation_permissions": "unchecked",
            "obsidian_cli": "unchecked",
        }
        state["problems"] = problems
    return state


def main(argv: list[str]) -> int:
    try:
        if argv[0] == "rename":
            result = rename(argv[1], argv[2], len(argv) > 3 and argv[3] == "current")
        elif argv[0] == "resolve":
            result = inspect(json.loads(argv[1]))
        elif argv[0] == "snapshot":
            result = native("snapshot")
        else:
            raise ValueError("Unknown private helper operation")
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (
        OSError,
        RuntimeError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        subprocess.SubprocessError,
    ) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, interrupted)
    raise SystemExit(main(sys.argv[1:]))
