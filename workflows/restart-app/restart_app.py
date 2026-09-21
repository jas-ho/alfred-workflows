#!/usr/bin/env python3
"""Alfred running-app picker and graceful restart actions."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

NATIVE = Path(__file__).with_name("native.js")


def match_terms(name):
    words = re.sub(r"([a-z])([A-Z])", r"\1 \2", name).split()
    terms = [name, " ".join(words)]
    if len(words) > 1:
        terms.extend(["".join(words), "".join(w[0] for w in words)])
    if name.casefold().startswith("visual studio code"):
        terms.append("vscode vs code")
    return " ".join(dict.fromkeys(terms))


def native(mode, target=None):
    args = ["/usr/bin/osascript", "-l", "JavaScript", str(NATIVE), mode]
    if target is not None:
        args.append(json.dumps(target))
    result = subprocess.run(
        args, capture_output=True, text=True, timeout=40, check=False
    )
    if result.returncode:
        raise RuntimeError(
            result.stderr.strip() or "Could not reach running applications."
        )
    return json.loads(result.stdout)


def exclusions_path():
    root = os.environ.get("alfred_workflow_data") or str(
        Path.home()
        / "Library/Application Support/Alfred/Workflow Data/com.jason.restart-app"
    )
    return Path(root) / "excluded-apps.txt"


def items(apps, excluded=()):
    rows = []
    for app in sorted(apps, key=lambda a: (a["name"].casefold(), a["path"], a["pid"])):
        if app["path"] in excluded:
            continue
        payload = json.dumps({"action": "restart", "target": app})
        rows.append(
            {
                "uid": app["path"],
                "title": app["name"],
                "subtitle": "↵ Restart app · ⌥↵ Quit only · ⌘↵ Hide from this list",
                "arg": payload,
                "autocomplete": app["name"],
                "match": match_terms(app["name"]),
                "icon": {"type": "fileicon", "path": app["path"]},
                "mods": {
                    "alt": {
                        "subtitle": "Quit app without reopening",
                        "arg": json.dumps({"action": "quit", "target": app}),
                    },
                    "cmd": {
                        "subtitle": "Hide app from this list (rexclude to edit)",
                        "arg": json.dumps({"action": "exclude", "target": app}),
                    },
                },
            }
        )
    return rows or [
        {
            "title": "No running apps to restart",
            "subtitle": "Open an app, or use rexclude to check hidden apps",
            "valid": False,
        }
    ]


def main(argv):
    mode = argv[0]
    try:
        if mode == "filter":
            path = exclusions_path()
            excluded = path.read_text().splitlines() if path.exists() else []
            print(
                json.dumps(
                    {"items": items(native("list"), excluded)}, ensure_ascii=False
                )
            )
        elif mode == "exclusions":
            path = exclusions_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
            subprocess.run(["/usr/bin/open", "-t", str(path)], check=True)
        elif mode == "action":
            payload = json.loads(argv[1])
            action, target = payload["action"], payload["target"]
            if action == "exclude":
                path = exclusions_path()
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a") as f:
                    f.write(target["path"] + "\n")
                print("Hidden from Restart App. Use rexclude to edit.")
            else:
                native(action, target)
        else:
            raise ValueError("Unknown command")
    except (
        OSError,
        RuntimeError,
        ValueError,
        KeyError,
        subprocess.SubprocessError,
    ) as error:
        if mode == "filter":
            print(
                json.dumps(
                    {
                        "items": [
                            {
                                "title": "Could not list running apps",
                                "subtitle": str(error),
                                "valid": False,
                            }
                        ]
                    }
                )
            )
        else:
            print(str(error))  # Connected to Alfred's notification output.
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
