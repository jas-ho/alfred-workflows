#!/usr/bin/python3
"""App-specific content setup. Hammerspoon owns window identity and placement."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import unicodedata
from pathlib import Path


class WindowOpenError(RuntimeError):
    def __init__(self, message: str, session: str):
        super().__init__(message)
        self.session = session


def interrupted(signum, frame):
    # subprocess.run kills and reaps its child when this unwinds communicate().
    # Already-delivered application actions may still complete; never retry them.
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    raise RuntimeError("App helper interrupted; inspect state before retrying")


def run(argv: list[str], timeout: int = 30) -> str:
    result = subprocess.run(
        argv, capture_output=True, text=True, timeout=timeout, check=False
    )
    output = result.stdout.strip()
    if result.returncode or any(
        line.lstrip().lower().startswith("error:")
        for line in (output + "\n" + result.stderr).splitlines()
    ):
        raise RuntimeError(result.stderr.strip() or output or "App command failed")
    return output


def obsidian(spec: dict, code: str) -> str:
    return run(
        [
            str(Path(spec["app"]) / "Contents/MacOS/Obsidian"),
            "vault=" + spec["vault"],
            "eval",
            "code=" + code,
        ]
    )


def preflight(request: dict) -> dict:
    """Check prerequisites before creating a desktop; never create content here."""
    for spec in request["apps"]:
        if spec["opener"] == "ghostty":
            tmux = shutil.which("tmux")
            if not tmux:
                raise RuntimeError("tmux is not installed")
            if request.get("tmux_session"):
                run([tmux, "has-session", "-t", "=" + request["tmux_session"]])
        if spec["opener"] == "obsidian":
            note = json.dumps(request.get("note"))
            obsidian(
                spec,
                "(function(){const p=" + note + ";"
                'if(p && !app.vault.getFileByPath(p)) throw new Error("Note does not exist: "+p);'
                "return app.vault.getName()})()",
            )
    return {"ok": True}


def ghostty_script() -> str:
    # Arguments travel as argv, never interpolated into AppleScript source.
    return """on run argv
tell application "Ghostty"
    set cfg to new surface configuration
    set initial working directory of cfg to item 1 of argv
    set command of cfg to item 2 of argv
    set w to new window with configuration cfg
    return id of w
end tell
end run"""


def chromium_script() -> str:
    return """on run argv
set appPath to item 1 of argv
using terms from application "Microsoft Edge"
    tell application appPath
        set w to make new window
        if (count argv) > 1 then
            set URL of active tab of w to item 2 of argv
            repeat with i from 3 to count argv
                make new tab at end of tabs of w with properties {URL:item i of argv}
            end repeat
        end if
        return id of w
    end tell
end using terms from
end run"""


def open_app(request: dict, spec: dict) -> dict:
    kind = spec["opener"]
    if kind == "ghostty":
        tmux = shutil.which("tmux")
        if not tmux:
            raise RuntimeError("tmux is not installed")
        session = request.get("tmux_session") or ""
        if not session:
            slug = re.sub(
                r"[^\w-]+",
                "-",
                unicodedata.normalize("NFKC", request["name"]).lower(),
            )
            base = "ws-" + (slug.strip("-_")[:60] or "workspace")
            for number in range(1, 101):
                session = base if number == 1 else f"{base}-{number}"
                try:
                    run(
                        [
                            tmux,
                            "new-session",
                            "-d",
                            "-s",
                            session,
                            "-c",
                            request["directory"],
                            "-e",
                            "PATH=" + os.environ["PATH"],
                        ]
                    )
                    break
                except RuntimeError as error:
                    # new-session is atomic. Only a name collision is retried;
                    # never attach an existing session or repeat an uncertain launch.
                    if str(error).strip() != "duplicate session: " + session:
                        raise
            else:
                raise RuntimeError("Too many tmux sessions named " + base)
        # No send-keys, switch-client, or detach-other-clients: only the new window attaches.
        command = shlex.join([tmux, "attach-session", "-t", "=" + session])
        try:
            native_id = run(
                [
                    "/usr/bin/osascript",
                    "-e",
                    ghostty_script(),
                    request["directory"],
                    command,
                ]
            )
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            raise WindowOpenError(str(error), session) from error
        return {"native_id": native_id, "tmux_session": session}
    if kind == "chromium":
        native_id = run(
            [
                "/usr/bin/osascript",
                "-e",
                chromium_script(),
                spec["app"],
                *request.get("urls", []),
            ]
        )
        return {"native_id": native_id}
    if kind == "obsidian":
        note = json.dumps(request.get("note"))
        code = "(async()=>{const p=" + note + ";"
        code += "const file=p?app.vault.getFileByPath(p):null;"
        code += 'if(p&&!file)throw new Error("Note does not exist: "+p);'
        code += 'const leaf=app.workspace.getLeaf("window");'
        code += 'if(file)await leaf.openFile(file);else await leaf.setViewState({type:"empty",state:{}});'
        code += "return leaf.id})()"
        obsidian(spec, code)
        return {"content": request.get("note") or "empty", "vault": spec["vault"]}
    raise ValueError("Unknown specialized opener: " + kind)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, interrupted)
    os.environ["PATH"] = ":".join(
        [
            str(Path.home() / "bin"),
            str(Path.home() / ".local/bin"),
            str(Path.home() / ".volta/bin"),
            "/opt/homebrew/bin",
            "/opt/homebrew/sbin",
            "/usr/local/bin",
            "/usr/bin",
            "/bin",
            "/usr/sbin",
            "/sbin",
        ]
    )
    try:
        request = json.loads(sys.argv[2])
        result = (
            preflight(request)
            if sys.argv[1] == "preflight"
            else open_app(request, request["apps"][int(sys.argv[3])])
        )
        print(json.dumps(result))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        if isinstance(error, WindowOpenError):
            print(json.dumps({"tmux_session": error.session}))
        print(str(error), file=sys.stderr)
        sys.exit(1)
