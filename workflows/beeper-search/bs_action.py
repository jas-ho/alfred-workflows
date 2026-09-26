#!/usr/bin/env python3
"""Alfred action: open the chat at the message, copy the text, or open a link.

Anything written to stdout becomes a notification (errors only).
"""
import json
import subprocess
import sys

from bs_common import env, tool


def main():
    try:
        arg = json.loads(sys.argv[1])
    except (IndexError, json.JSONDecodeError):
        return "Invalid selection"
    action = arg.get("action")
    if action == "copy":
        subprocess.run(["pbcopy"], input=arg.get("text", ""), text=True, check=False)
        return ""
    if action == "link":
        url = arg.get("url", "")  # unwrapped and validated by beeper-search
        if not url.startswith(("https://", "http://")) or any(c.isspace() for c in url):
            return "Refused to open a malformed link"
        subprocess.run(["open", url], check=False, capture_output=True)
        return ""
    cli = tool()
    if not cli:
        return "beeper-search not found"
    proc = subprocess.run([cli, "--open", arg["chat"], arg["message"]], env=env(), capture_output=True, text=True, timeout=20)
    return "" if proc.returncode == 0 else ("Could not open in Beeper: " + (proc.stderr.strip() or f"exit {proc.returncode}"))[:200]


if __name__ == "__main__":
    sys.stdout.write(main())
