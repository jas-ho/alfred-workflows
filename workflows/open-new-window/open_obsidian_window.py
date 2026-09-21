#!/usr/bin/env python3
"""Dispatch Obsidian's new-window command with a real subprocess timeout."""

import plistlib
import subprocess
import sys
from pathlib import Path

CLI_TIMEOUT = 8


def open_window(app_path):
    app_path = Path(app_path)
    try:
        with (app_path / "Contents/Info.plist").open("rb") as stream:
            executable = plistlib.load(stream)["CFBundleExecutable"]
        result = subprocess.run(
            [
                str(app_path / "Contents/MacOS" / executable),
                "command",
                "id=workspace:new-window",
            ],
            capture_output=True,
            text=True,
            timeout=CLI_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return f"Obsidian CLI timed out after {CLI_TIMEOUT} seconds"
    except (OSError, ValueError, KeyError) as error:
        return str(error)

    output = (result.stdout + "\n" + result.stderr).strip()
    # Some CLI failures are reported in text despite an exit status of zero.
    if result.returncode or any(
        line.lstrip().lower().startswith("error:") for line in output.splitlines()
    ):
        return output or f"Obsidian CLI exited with status {result.returncode}"
    return ""


if __name__ == "__main__":
    message = open_window(sys.argv[1])
    if message:
        print(message, file=sys.stderr)
        sys.exit(1)
