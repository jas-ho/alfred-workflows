#!/usr/bin/env python3
"""Alfred Script Filter: delegate to `pjws alfred-items`.

v2 lives at ~/.local/bin/pjws (installed via `uv pip install -e ~/Code/pjws`).
Alfred's inherited PATH is sparse, so we probe a few common locations and
fall back to a clear error item rather than silently showing nothing.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


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


def _error_item(title: str, subtitle: str) -> None:
    json.dump({"items": [{
        "title": title, "subtitle": subtitle, "valid": False,
    }]}, sys.stdout)


def main() -> int:
    pjws = _resolve_pjws()
    if pjws is None:
        _error_item(
            "pjws not installed",
            "Run `~/Code/pjws/scripts/install.sh` then reload Alfred.",
        )
        return 0
    r = subprocess.run(
        [str(pjws), "alfred-items"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if r.returncode != 0:
        _error_item(
            "pjws error",
            (r.stderr or r.stdout or "unknown").strip().splitlines()[-1][:120],
        )
        return 0
    sys.stdout.write(r.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
