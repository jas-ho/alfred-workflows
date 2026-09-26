#!/usr/bin/env python3
"""Alfred script filter: delegate to `beeper-search --alfred QUERY` (it renders the items)."""
import json
import subprocess
import sys

from bs_common import env, tool


def error(title, subtitle=""):
    return json.dumps({"items": [{"title": title, "subtitle": subtitle, "valid": False}]})


def main():
    query = " ".join(sys.argv[1:]).strip()
    cli = tool()
    if not cli:
        return error("beeper-search not found", "Install it on your login shell's PATH or set BEEPER_SEARCH_BIN")
    try:
        # "--" keeps a query like "--deep" from being parsed as an option
        proc = subprocess.run([cli, "--alfred", "--", query], capture_output=True, text=True, env=env(), timeout=10)
    except (OSError, subprocess.TimeoutExpired) as e:
        return error("beeper-search failed", e.__class__.__name__)
    return proc.stdout if proc.returncode == 0 and proc.stdout.strip() else error(
        "beeper-search failed", (proc.stderr or f"exit {proc.returncode}").strip()[:120])


if __name__ == "__main__":
    print(main())
