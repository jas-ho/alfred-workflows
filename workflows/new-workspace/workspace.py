#!/usr/bin/python3
"""Create a named desktop through the Hammerspoon GUI worker."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
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
    name = args.name.strip()
    if not name or len(name) > 120 or any(ord(c) < 32 for c in name):
        raise ValueError(
            "Workspace name must contain 1–120 characters without control characters"
        )
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
        "notify": os.environ.get("alfred_workflow_bundleid") is not None,
    }


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False))
    temporary.replace(path)


def send(request: dict, timeout: float = 270) -> dict:
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (STATE / "client.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("Another workspace request is in progress") from error
        request = {**request, "id": uuid.uuid4().hex, "expires": time.time() + 5}
        result_path = STATE / (request["id"] + ".json")
        atomic_json(STATE / "request.json", request)
        deadline = time.monotonic() + timeout
        acknowledged = False
        while time.monotonic() < deadline:
            if result_path.exists():
                result = json.loads(result_path.read_text())
                acknowledged = True
                if result.get("status") != "running":
                    if result.get("windows") == {}:
                        result["windows"] = []
                    return result
            if not acknowledged and time.time() > request["expires"] + 1:
                raise RuntimeError(
                    "Hammerspoon did not respond. Load workspace.lua; this request has expired."
                )
            time.sleep(0.15)
        return {
            "status": "uncertain",
            "id": request["id"],
            "error": "Still waiting for Hammerspoon. Do not repeat create; inspect workspace result "
            + request["id"],
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


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest="command", required=True)
    create = commands.add_parser(
        "create",
        aliases=["alfred-action"],
        help="Create a fresh desktop and configured app windows",
    )
    create.add_argument("name")
    create.add_argument("--directory", default=str(Path.home()))
    create.add_argument(
        "--url", action="append", help="HTTP(S) URL; repeat for more tabs"
    )
    create.add_argument(
        "--note", help="Existing vault-relative note; default: empty Obsidian pane"
    )
    create.add_argument(
        "--tmux-session", help="Attach an existing session instead of creating one"
    )
    create.add_argument("--config", type=Path, help="Alternate recipe JSON")
    create.add_argument("--stay", action="store_true")
    create.add_argument("--layout", choices=("main-stack", "columns", "none"))
    create.add_argument("--json", action="store_true")
    commands.add_parser("check", help="Check the GUI worker connection")
    result = commands.add_parser(
        "result", help="Read a previous operation result without repeating it"
    )
    result.add_argument("id")
    filt = commands.add_parser("filter", help=argparse.SUPPRESS)
    filt.add_argument("name", nargs="?", default="")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "filter":
            print(json.dumps(filter_items(args.name), ensure_ascii=False))
            return 0
        if args.command == "result":
            if not re.fullmatch(r"[a-f0-9]{32}", args.id):
                raise ValueError("Invalid operation ID")
            result = json.loads((STATE / (args.id + ".json")).read_text())
        else:
            result = send(
                create_request(args)
                if args.command in ("create", "alfred-action")
                else {"operation": "check"}
            )
        if args.command == "alfred-action":
            if result["status"] != "complete":
                print(result.get("error", "Workspace setup did not complete"))
        elif args.command != "create" or args.json:
            print(json.dumps(result, ensure_ascii=False))
        elif result["status"] == "complete":
            print(
                f"Created {args.name} with {len(result['windows'])} windows (desktop {result['space_id']})."
            )
        else:
            print(json.dumps(result, ensure_ascii=False), file=sys.stderr)
        return 0 if result["status"] in ("complete", "ready") else 1
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        payload = {"status": "failed", "error": str(error)}
        if args.command == "alfred-action":
            print(str(error))
        else:
            print(
                json.dumps(payload) if getattr(args, "json", False) else str(error),
                file=sys.stdout if getattr(args, "json", False) else sys.stderr,
            )
        return 1


if __name__ == "__main__":
    sys.exit(main())
