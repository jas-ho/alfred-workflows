#!/usr/bin/env python3
"""Alfred action: run `pjws <verb> <name>`.

Alfred passes the project name as argv[1]; the verb comes from the
`verb` env var set by the script filter (`switch` on return, `unload`
on cmd+return). Defaults to `switch` — `pjws switch` already falls
back to `load` when the project isn't loaded yet.

The pjws binary lives at ~/.config/pjws/bin/pjws (chezmoi-managed).
Using the absolute path rather than PATH lookup because Alfred's
inherited PATH is sparse (no ~/.local/bin, no ~/bin).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PJWS_BIN = Path.home() / ".config/pjws/bin/pjws"
ALLOWED_VERBS = {"load", "switch", "unload"}


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("pjws: missing project name", file=sys.stderr)
        return 2
    name = sys.argv[1].strip()
    verb = os.environ.get("verb", "switch")
    if verb not in ALLOWED_VERBS:
        print(f"pjws: unsupported verb {verb!r}", file=sys.stderr)
        return 2
    if not PJWS_BIN.is_file():
        print(f"pjws: orchestrator not found at {PJWS_BIN}", file=sys.stderr)
        return 127
    r = subprocess.run(
        [str(PJWS_BIN), verb, name],
        capture_output=True, text=True,
    )
    if r.stdout:
        sys.stdout.write(r.stdout)
    if r.stderr:
        sys.stderr.write(r.stderr)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
