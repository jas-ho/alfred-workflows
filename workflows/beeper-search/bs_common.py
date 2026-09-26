"""Find the beeper-search CLI for the Alfred workflow.

Alfred's PATH is sparse, so resolve the command from the login shell once per
cache lifetime (BEEPER_SEARCH_BIN overrides). The workflow depends on the CLI
being installed and on PATH, not on where it lives.
"""
import os
import subprocess
from pathlib import Path

CACHE = Path(os.environ.get("alfred_workflow_cache", Path.home() / "Library/Caches/com.jason.beeper-search")) / "bin-path"


def tool():
    override = os.environ.get("BEEPER_SEARCH_BIN")
    if override:
        return override
    try:
        cached = CACHE.read_text().strip()
        if cached and os.access(cached, os.X_OK):
            return cached
    except OSError:
        pass
    shell = os.environ.get("SHELL", "/bin/zsh")
    try:
        found = subprocess.run([shell, "-lic", "command -v beeper-search"], capture_output=True,
                               text=True, timeout=5).stdout.strip().splitlines()
    except (OSError, subprocess.TimeoutExpired):
        return None
    path = found[-1] if found else ""
    if not path.startswith("/"):
        return None
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(path)
    except OSError:
        pass
    return path


def env():
    """uv (the CLI's script runner) usually lives in ~/.local/bin or Homebrew."""
    extra = [str(Path.home() / ".local/bin"), "/opt/homebrew/bin", "/usr/local/bin"]
    e = {**os.environ, "PATH": os.pathsep.join(extra + [os.environ.get("PATH", "/usr/bin:/bin")])}
    e.pop("BEEPER_SEARCH_LOG", None)  # Alfred re-runs per keystroke: keep the held-out query log clean
    return e
