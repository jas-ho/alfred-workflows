#!/usr/bin/env python3
"""Alfred action: run `pjws switch <slug>` or `pjws unload <slug>`.

The filter sets the `action` workflow variable to either "switch" (default)
or "unload" (cmd+return). Alfred passes the slug as argv[1].

v2 uses ~/.local/bin/pjws (uv-shim → `uv run --project ~/Code/pjws`).
Alfred's PATH is sparse so the pjws binary is located explicitly.

Alfred silently swallows subprocess stderr from script actions unless
explicitly wired to surface it. We fire a macOS notification for any
outcome that isn't all-green, so the user isn't left wondering whether
their switch actually landed.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


ALLOWED_VERBS = {"switch", "unload"}
CANDIDATE_BINS = [
    Path.home() / ".local" / "bin" / "pjws",
    Path("/opt/homebrew/bin/pjws"),
    Path("/usr/local/bin/pjws"),
]

# Matches a line from format_summary like "  edge      skipped".
_OUTCOME_LINE = re.compile(r"^\s{2}(\w+)\s+(ok|deferred|failed|skipped)\s*$")


def _resolve_pjws() -> Path | None:
    for p in CANDIDATE_BINS:
        if p.is_file():
            return p
    return None


def _notify(title: str, subtitle: str, message: str) -> None:
    """Fire a macOS notification via osascript. Best-effort; never raises."""
    # AppleScript string literals escape `\` → `\\` and `"` → `\"`.
    def _lit(s: str) -> str:
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

    script = (
        f"display notification {_lit(message)} "
        f"with title {_lit(title)} subtitle {_lit(subtitle)}"
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def _parse_outcomes(stdout: str) -> dict[str, str]:
    """Extract {adapter: status} from `pjws switch` stdout. Empty on parse miss."""
    out: dict[str, str] = {}
    for line in stdout.splitlines():
        m = _OUTCOME_LINE.match(line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def _summary_for_notification(
    slug: str, action: str, rc: int, stdout: str, stderr: str,
) -> tuple[str, str, str] | None:
    """Return (title, subtitle, message) if the user should be notified, else None.

    Notify policy:
    - `unload`: notify only on non-zero rc (success is quiet — user asked
      for a cleanup and got it).
    - `switch`: notify unless every adapter reported `ok`. Any skipped /
      deferred / failed counts as "something worth flagging" since those
      are the outcomes Alfred would otherwise swallow silently.
    """
    if action == "unload":
        if rc == 0:
            return None
        msg = (stderr or stdout or "tmux kill-session failed").strip().splitlines()[-1][:140]
        return (f"pjws: unload {slug}", "failed", msg)

    outcomes = _parse_outcomes(stdout)
    if outcomes and all(v == "ok" for v in outcomes.values()):
        return None
    if not outcomes:
        # Parse miss — fall back to stderr or rc so we at least flag something.
        msg = (stderr or stdout or f"pjws exited {rc}").strip().splitlines()[-1][:140]
        return (f"pjws: switch {slug}", "unparseable outcome", msg)
    parts = [f"{a}={s}" for a, s in outcomes.items() if s != "ok"]
    parts_ok = [a for a, s in outcomes.items() if s == "ok"]
    subtitle = " · ".join(parts) if parts else "all ok"
    detail = ", ".join(parts_ok)
    message = f"ok: {detail}" if detail else "no adapters succeeded"
    return (f"pjws: switch {slug}", subtitle, message)


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
        _notify("pjws: not installed", slug, "Run ~/Code/pjws/scripts/install.sh")
        print("pjws: not installed (run ~/Code/pjws/scripts/install.sh)", file=sys.stderr)
        return 127
    r = subprocess.run(
        [str(pjws), action, slug],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if r.stdout:
        sys.stdout.write(r.stdout)
    if r.stderr:
        sys.stderr.write(r.stderr)
    notice = _summary_for_notification(slug, action, r.returncode, r.stdout, r.stderr)
    if notice is not None:
        _notify(*notice)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
