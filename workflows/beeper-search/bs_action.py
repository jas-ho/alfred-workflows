#!/usr/bin/env python3
"""Alfred action: open the chat at the message, copy the text, or open a link.

Anything written to stdout becomes a notification (errors only).
"""
import json
import subprocess
import sys
from urllib.parse import urlsplit

from bs_common import env, tool


def valid_url(url):
    if not isinstance(url, str) or any(ord(c) <= 0x20 or ord(c) == 0x7f for c in url):
        return False
    try:
        parts = urlsplit(url)
        return parts.scheme in ("http", "https") and bool(parts.hostname)
    except ValueError:  # e.g. "https://[broken"
        return False


def main():
    try:
        arg = json.loads(sys.argv[1])
    except (IndexError, json.JSONDecodeError):
        return "Invalid selection"
    action = arg.get("action") if isinstance(arg, dict) else None
    try:
        if action == "copy" and isinstance(arg.get("text"), str):
            done = subprocess.run(["pbcopy"], input=arg["text"], text=True, capture_output=True, timeout=5)
            return "" if done.returncode == 0 else "Copy failed"
        if action == "link":
            url = arg.get("url")  # unwrapped and validated by beeper-search; checked again here
            if not valid_url(url):
                return "Refused to open a malformed link"
            done = subprocess.run(["open", url], capture_output=True, timeout=10)
            return "" if done.returncode == 0 else "Could not open the link"
        if action == "open" and all(isinstance(arg.get(k), str) and arg[k] for k in ("chat", "message")):
            cli = tool()
            if not cli:
                return "beeper-search not found"
            done = subprocess.run([cli, "--open", arg["chat"], arg["message"]], env=env(),
                                  capture_output=True, text=True, timeout=25)
            return "" if done.returncode == 0 else ("Could not open in Beeper: " + (done.stderr.strip() or f"exit {done.returncode}"))[:200]
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"Beeper Search: {action} failed ({error.__class__.__name__})"
    return "Invalid selection"


if __name__ == "__main__":
    sys.stdout.write(main())
