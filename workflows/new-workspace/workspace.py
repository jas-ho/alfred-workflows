#!/usr/bin/python3
"""Manage named macOS desktops through the Hammerspoon GUI worker."""

from __future__ import annotations

import argparse
import fcntl
import json
import plistlib
import re
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
STATE = Path.home() / ".local/state/workspace"
CONFIG = Path.home() / ".config/workspace/default.json"
OPENERS = {"generic", "ghostty", "chromium", "obsidian"}


def recipe(path: Path | None = None) -> list[dict]:
    source = path or (CONFIG if CONFIG.exists() else ROOT / "default.json")
    data = json.loads(source.read_text())
    if not isinstance(data, dict):
        raise TypeError("Recipe must be a JSON object")
    apps = data.get("apps")
    if not isinstance(apps, list) or not 1 <= len(apps) <= 8:
        raise ValueError("Recipe must contain between 1 and 8 apps")
    seen = set()
    result = []
    for item in apps:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("opener", "generic"), str)
            or item.get("opener", "generic") not in OPENERS
        ):
            raise ValueError("Unknown app opener")
        if not isinstance(item.get("app"), str) or not item["app"]:
            raise ValueError("Each app needs an application path")
        app = Path(item["app"]).expanduser().resolve()
        with (app / "Contents/Info.plist").open("rb") as stream:
            bundle = plistlib.load(stream)["CFBundleIdentifier"]
        if bundle in seen:
            raise ValueError("Use each app only once in a recipe")
        seen.add(bundle)
        spec = {
            **item,
            "app": str(app),
            "bundle": bundle,
            "name": app.stem,
            "opener": item.get("opener", "generic"),
        }
        if spec["opener"] == "ghostty" and bundle != "com.mitchellh.ghostty":
            raise ValueError("The ghostty opener requires Ghostty")
        if spec["opener"] == "obsidian" and (
            bundle != "md.obsidian"
            or not isinstance(spec.get("vault"), str)
            or not spec["vault"]
        ):
            raise ValueError("The obsidian opener requires Obsidian and a vault name")
        if "menu" in spec and (
            not isinstance(spec["menu"], list)
            or not spec["menu"]
            or not all(isinstance(x, str) for x in spec["menu"])
        ):
            raise ValueError('menu must be a list such as ["File", "New Window"]')
        result.append(spec)
    return result


def create_request(args: argparse.Namespace) -> dict:
    name = workspace_name(args.name)
    directory = Path(args.directory).expanduser().resolve()
    if not directory.is_dir():
        raise ValueError("Directory does not exist: " + str(directory))
    apps = recipe(args.config)
    source = args.config or (CONFIG if CONFIG.exists() else ROOT / "default.json")
    layout = args.layout or json.loads(source.read_text()).get("layout", "none")
    if layout not in ("main-stack", "columns", "none"):
        raise ValueError("Layout must be main-stack, columns, or none")
    kinds = {a["opener"] for a in apps}
    for kind in ("ghostty", "chromium", "obsidian"):
        if sum(a["opener"] == kind for a in apps) > 1:
            raise ValueError("Use at most one " + kind + " opener per recipe")
    urls = args.url or []
    if any(
        urlparse(u).scheme not in ("https", "http") or not urlparse(u).netloc
        for u in urls
    ):
        raise ValueError("URLs must be absolute http:// or https:// addresses")
    if urls and "chromium" not in kinds:
        raise ValueError("--url requires a chromium opener in the recipe")
    if args.note and "obsidian" not in kinds:
        raise ValueError("--note requires an obsidian opener in the recipe")
    if args.tmux_session and (
        "ghostty" not in kinds or not re.fullmatch(r"[\w-]+", args.tmux_session)
    ):
        raise ValueError(
            "--tmux-session requires Ghostty and an exact session name (letters, digits, _ or -)"
        )
    if args.note and (Path(args.note).is_absolute() or ".." in Path(args.note).parts):
        raise ValueError("--note must be an existing vault-relative note path")
    return {
        "operation": "create",
        "name": name,
        "apps": apps,
        "directory": str(directory),
        "urls": urls,
        "note": args.note,
        "tmux_session": args.tmux_session,
        "stay": args.stay,
        "layout": layout,
        "notify": False,
    }


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False))
    temporary.replace(path)


STATUSES = {
    "complete",
    "running",
    "confirmation_required",
    "blocked",
    "cancelled",
    "partial",
    "failed",
    "uncertain",
}


def send(request: dict, timeout: float = 270) -> dict:
    """Own the mailbox until matching acknowledgment, then wait without its lock."""
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (STATE / "client.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {
                "operation": request["operation"],
                "status": "blocked",
                "error_code": "client_busy",
                "error": "Another client is awaiting worker acknowledgment; retry later.",
            }
        request = {**request, "id": uuid.uuid4().hex, "expires": time.time() + 5}
        result_path = STATE / (request["id"] + ".json")
        atomic_json(STATE / "request.json", request)
        deadline = time.monotonic() + timeout
        acknowledged = False
        latest = {}
        while time.monotonic() < deadline:
            try:
                result = json.loads(result_path.read_text())
            except (OSError, ValueError):
                result = None
            if (
                isinstance(result, dict)
                and result.get("id") == request["id"]
                and result.get("status") in STATUSES
            ):
                latest = result
                if not acknowledged:
                    fcntl.flock(lock, fcntl.LOCK_UN)
                    acknowledged = True
                if result["status"] != "running":
                    return {"operation": request["operation"], **result}
            if not acknowledged and time.time() > request["expires"] + 1:
                break
            time.sleep(0.15)
        # A timeout cannot establish whether the worker changed the desktop.
        # Never replace its operation record with this client-side observation.
        return {
            **latest,
            "status": "uncertain",
            "id": request["id"],
            "operation": request["operation"],
            "acknowledged": acknowledged,
            "error_code": "worker_timeout",
            "error": "Worker completion is unknown. Do not repeat the operation; inspect "
            "workspace result " + request["id"],
        }


def filter_items(name: str) -> dict:
    name = name.strip()
    try:
        apps = recipe()
        summary = " · ".join(a["name"] for a in apps)
        item = {
            "title": f"Create ‘{name}’" if name else "Name your new workspace",
            "subtitle": summary + " · Return here when ready · ⌘ Stay there",
            "valid": bool(name),
            "arg": name,
            "mods": {
                "cmd": {
                    "subtitle": summary + " · Stay in the new workspace",
                    "variables": {"workspace_stay": "1"},
                }
            },
        }
        return {"items": [item]}
    except (OSError, ValueError, TypeError, KeyError) as error:
        return {
            "items": [
                {
                    "title": "Check workspace configuration",
                    "subtitle": str(error),
                    "valid": False,
                }
            ]
        }


def failure_summary(result: dict, *, compact: bool = False) -> str:
    lines = [result.get("error", "Workspace setup did not complete")]
    if result.get("space_id"):
        windows = result.get("windows") or []
        apps = ", ".join(w["app"] for w in windows) or "no confirmed windows"
        lines.append(f"Kept ‘{result.get('name', 'Workspace')}’: {apps}.")
        if result.get("tmux_session"):
            lines.append("tmux: " + result["tmux_session"])
        if compact:
            lines.append("Use sp to open the desktop; do not repeat ns to resume.")
        else:
            lines.append(f"Open desktop: workspace switch --id {result['space_id']}")
    if not compact and result.get("id"):
        lines.append("Details: workspace result " + result["id"])
    if result.get("uncertain"):
        lines.append("Some actions may still have completed; inspect before retrying.")
    return "\n".join(lines)


class UsageError(ValueError):
    """Invalid arguments, rendered using the selected output format."""


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message)


def workspace_name(value: str) -> str:
    name = value.strip()
    if not name or len(name) > 120 or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise ValueError(
            "Workspace name must contain 1–120 characters without control characters"
        )
    return name


def desktop_id(value: str) -> str:
    normalized = value.lstrip("0") or "0"
    if (
        not re.fullmatch(r"[0-9]+", value)
        or len(normalized) > 16
        or not 0 < int(normalized) <= 2**53 - 1
    ):
        raise argparse.ArgumentTypeError(
            "Desktop ID must be a positive decimal integer up to 9007199254740991"
        )
    return normalized


def operation_id(value: str) -> str:
    if not re.fullmatch(r"[a-f0-9]{32}", value):
        raise argparse.ArgumentTypeError(
            "Operation ID must be 32 lowercase hexadecimal characters"
        )
    return value


def parser() -> argparse.ArgumentParser:
    p = ArgumentParser(
        prog="workspace",
        description=__doc__,
        epilog="Examples: workspace list; workspace switch Research; workspace close --id 123 --yes; "
        "workspace --json result OPERATION_ID. Exit 0: complete; 1: other outcomes; 2: usage. "
        "Timeouts are uncertain: inspect result before retrying a mutation.",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="One schema-versioned JSON object (also accepted after command)",
    )
    commands = p.add_subparsers(dest="command", required=True)

    def command(name, help_text, description=None):
        sub = commands.add_parser(
            name, help=help_text, description=description or help_text
        )
        sub.add_argument(
            "--json",
            action="store_true",
            default=argparse.SUPPRESS,
            help="Output one JSON object, including failures",
        )
        return sub

    command("list", "List fresh desktops, names, order and stable IDs")
    targeting = "A numeric selector means current display order; names match case-insensitively, exact then unique substring. Use --id for stable targeting or numeric names."
    switch = command("switch", "Switch to a desktop and verify arrival", targeting)
    close = command(
        "close",
        "Preview windows; --yes closes windows and removes the desktop",
        targeting
        + " Omit target for current desktop. Preview never closes windows. --yes waits for verified completion; application save dialogs are never dismissed.",
    )
    for sub in (switch, close):
        sub.add_argument("query", nargs="?", metavar="NAME|NUMBER")
        sub.add_argument(
            "--id",
            dest="space_id",
            type=desktop_id,
            help="Stable decimal desktop ID; cannot combine with NAME|NUMBER",
        )
    close.add_argument(
        "--yes",
        action="store_true",
        help="Execute using a fresh inventory, without our confirmation dialog",
    )
    rename = command("rename", "Rename current desktop (or --id) and verify saved name")
    rename.add_argument("name")
    rename.add_argument("--id", dest="space_id", type=desktop_id)
    command("back", "Return to the previous desktop and verify a transition")
    create = command(
        "create",
        "Create a desktop with configured app windows",
        "Create a fresh desktop and app windows, then return to the original desktop unless --stay. Manual desktop switching is respected. Partial work is kept; inspect result before retrying.",
    )
    create.add_argument("name")
    create.add_argument(
        "--directory",
        default=str(Path.home()),
        help="Terminal working directory (default: home)",
    )
    create.add_argument(
        "--url", action="append", help="HTTP(S) URL; repeat for more tabs"
    )
    create.add_argument(
        "--note", help="Existing vault-relative note; default: empty Obsidian pane"
    )
    create.add_argument(
        "--tmux-session",
        help="Attach an existing session; default: new readable unique session",
    )
    create.add_argument(
        "--config",
        type=Path,
        help="Alternate recipe JSON (default: ~/.config/workspace/default.json or bundled recipe)",
    )
    create.add_argument(
        "--stay", action="store_true", help="Stay on the new desktop when ready"
    )
    create.add_argument(
        "--layout",
        choices=("main-stack", "columns", "none"),
        help="Window layout (default: recipe setting, otherwise none)",
    )
    command(
        "check",
        "Read-only worker, desktop and local app readiness checks",
        "Check live worker, close backend, desktop access and configured app prerequisites. Does not open test windows or prompt for permissions; Automation remains explicitly unchecked.",
    )
    result = command(
        "result",
        "Read the latest stored outcome without repeating the operation",
        "Read a fresh stored result. Running, blocked and partial outcomes are not completed success. A timeout or missing record does not prove a mutation failed; inspect desktop state before retrying.",
    )
    result.add_argument("id", type=operation_id, metavar="OPERATION_ID")
    return p


def operation_request(args: argparse.Namespace) -> dict:
    if args.command == "create":
        return create_request(args)
    request = {"operation": args.command}
    if args.command in ("switch", "close"):
        if args.query is not None and args.space_id is not None:
            raise UsageError("Use either NAME|NUMBER or --id, not both")
        if args.command == "switch" and args.query is None and args.space_id is None:
            raise UsageError("switch requires NAME|NUMBER or --id")
        if args.query is not None:
            request["query"] = workspace_name(args.query)
    if getattr(args, "space_id", None) is not None:
        request["space_id"] = args.space_id
    if args.command == "rename":
        request["name"] = workspace_name(args.name)
    if args.command == "close":
        request.update(execute=args.yes, confirm=False, notify=False)
    if args.command == "check":
        request.update(directory=str(Path.home()), urls=[])
        try:
            request["apps"] = recipe()
        except (OSError, ValueError, TypeError, KeyError) as error:
            request["apps_error"] = str(error)
    return request


SPACE_ID_KEYS = {
    "space_id",
    "origin_id",
    "active",
    "keeper",
    "target_id",
    "previous_id",
    "desktopID",
    "active_id",
}
ARRAY_KEYS = {
    "windows",
    "spaces",
    "desktops",
    "problems",
    "candidate_ids",
    "candidate_space_ids",
    "apps",
    "blocked_windows",
    "warnings",
    "urls",
}


def normalize(value, key=None):
    """Normalize Lua arrays and desktop IDs without coercing window IDs."""
    if key in ARRAY_KEYS and value == {}:
        return []
    if isinstance(value, dict):
        return {k: normalize(v, k) for k, v in value.items()}
    if isinstance(value, list):
        if key in ("spaces", "desktops", "candidate_space_ids"):
            return [
                (
                    {
                        k: str(v) if k == "id" else normalize(v, k)
                        for k, v in item.items()
                    }
                    if isinstance(item, dict)
                    else str(item)
                )
                for item in value
            ]
        return [normalize(item) for item in value]
    if (
        key in SPACE_ID_KEYS
        and isinstance(value, (int, str))
        and not isinstance(value, bool)
    ):
        return str(value)
    return value


def envelope(result: dict, operation: str, request_id=None) -> dict:
    if not isinstance(result, dict) or result.get("status") not in STATUSES:
        raise ValueError("Invalid worker result")
    error = result.get("error")
    return {
        "schema_version": 1,
        "operation": result.get("operation", operation),
        "operation_id": result.get("id", request_id),
        "status": result["status"],
        "data": normalize(
            {
                k: v
                for k, v in result.items()
                if k not in ("operation", "id", "status", "error", "error_code")
            }
        ),
        "error": {
            "code": result.get("error_code", "operation_failed"),
            "message": str(error),
        }
        if error
        else None,
    }


def human_output(payload: dict) -> str:
    data, status, operation = payload["data"], payload["status"], payload["operation"]
    if payload["error"] and operation == "create":
        return failure_summary(
            {
                **data,
                "id": payload["operation_id"],
                "error": payload["error"]["message"],
                "status": status,
            }
        )
    if status == "confirmation_required":
        windows = data.get("windows", [])
        lines = [
            f"Desktop {data.get('space_id')}: {len(windows)} windows would be closed."
        ]
        lines.extend(
            f"  {w.get('app', w.get('bundle', 'App'))}: {w.get('title', '')}"
            for w in windows
        )
        lines.append(f"Confirm: workspace close --id {data.get('space_id')} --yes")
        return "\n".join(lines)
    if operation == "list" and status == "complete":
        spaces = data.get("spaces", data.get("desktops", []))
        return (
            "\n".join(
                f"{'*' if str(s.get('id')) == str(data.get('active')) else ' '} {s.get('number', s.get('index', s.get('order', i)))}: {s.get('name', '')} (id {s.get('id')})"
                for i, s in enumerate(spaces, 1)
            )
            or "No regular desktops."
        )
    if operation == "create" and status == "complete":
        return f"Created {data.get('name', 'workspace')} with {len(data.get('windows', []))} windows (desktop {data.get('space_id')})."
    if status == "complete" and operation in ("switch", "back"):
        return f"On desktop {data.get('space_id')}" + (
            f": {data['name']}" if data.get("name") else "."
        )
    if status == "complete" and operation == "rename":
        return f"Renamed desktop {data.get('space_id')} to {data.get('name')}."
    if status == "complete" and operation == "close":
        return (
            f"Closed {data.get('name', 'desktop')} and {data.get('closed', 0)} windows."
        )
    if status == "complete" and operation == "check":
        return "Workspace worker ready. Live desktops, close backend and configured apps available.\nAutomation permissions and Obsidian CLI readiness: unchecked."
    lines = [
        payload["error"]["message"]
        if payload["error"]
        else f"{operation.capitalize()}: {status.replace('_', ' ')}."
    ]
    if data:
        lines.append(json.dumps(data, ensure_ascii=False, indent=2))
    if status != "complete" and payload["operation_id"]:
        lines.append("Details: workspace result " + payload["operation_id"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    options = argv[: argv.index("--")] if "--" in argv else argv
    json_output = "--json" in options
    operation = next((arg for arg in options if not arg.startswith("-")), "unknown")
    request_id = None
    exit_code = None
    try:
        args = parser().parse_args(argv)
        json_output = args.json
        operation = args.command
        if args.command == "result":
            request_id = args.id
            result = json.loads((STATE / (args.id + ".json")).read_text())
            if not isinstance(result, dict) or result.get("id") != args.id:
                raise ValueError("Stored result does not match the operation ID")
        else:
            try:
                request = operation_request(args)
            except (OSError, ValueError, TypeError, KeyError) as error:
                raise UsageError(str(error)) from error
            result = send(request)
        payload = envelope(result, operation, request_id)
    except SystemExit as error:
        return (
            error.code
            if isinstance(error.code, int)
            else 0
            if error.code is None
            else 1
        )
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        exit_code = 2 if isinstance(error, UsageError) else 1
        code = "invalid_arguments" if exit_code == 2 else "client_error"
        if isinstance(error, FileNotFoundError) and operation == "result":
            code = "result_not_found"
        payload = envelope(
            {"status": "failed", "error_code": code, "error": str(error)},
            operation,
            request_id,
        )
    if json_output:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(
            human_output(payload), file=sys.stderr if payload["error"] else sys.stdout
        )
    return (
        exit_code
        if exit_code is not None
        else (0 if payload["status"] == "complete" else 1)
    )


if __name__ == "__main__":
    sys.exit(main())
