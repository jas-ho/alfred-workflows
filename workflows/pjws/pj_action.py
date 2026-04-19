#!/usr/bin/env python3
"""Alfred action: run `pjws switch <slug>` or `pjws unload <slug>`.

The filter sets the `action` workflow variable to either "switch" (default)
or "unload" (cmd+return). Alfred passes the slug as argv[1].

v2 uses ~/.local/bin/pjws (uv-installed). Alfred's PATH doesn't include
~/.local/bin, so the pjws binary is located explicitly.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ALLOWED_VERBS = {"switch", "unload"}
CANDIDATE_BINS = [
    Path.home() / ".local" / "bin" / "pjws",
    Path("/opt/homebrew/bin/pjws"),
    Path("/usr/local/bin/pjws"),
]


def _resolve_pjws() -> Path | None:
    for p in CANDIDATE_BINS:
        if p.is_file():
            return p
    return None


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("pjws: missing slug", file=sys.stderr)
        return 2
    slug = sys.argv[1].strip()
    action = os.environ.get("action", "switch")
    if action not in ALLOWED_VERBS:
        print(f"pjws: unsupported action {action!r}", file=sys.stderr)
        return 2
    pjws = _resolve_pjws()
    if pjws is None:
        print("pjws: not installed (try `uv pip install -e ~/Code/pjws`)", file=sys.stderr)
        return 127
    r = subprocess.run(
        [str(pjws), action, slug],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if r.stdout:
        sys.stdout.write(r.stdout)
    if r.stderr:
        sys.stderr.write(r.stderr)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
