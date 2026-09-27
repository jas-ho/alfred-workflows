"""Find the beeper-search CLI for the Alfred workflow.

Alfred's PATH is sparse, so resolve the command from the login shell once per
cache lifetime (BEEPER_SEARCH_BIN overrides). The workflow depends on the CLI
being installed and on PATH, not on where it lives.
"""
import json
import os
import subprocess
import time
from pathlib import Path

CACHE = Path(os.environ.get("alfred_workflow_cache", Path.home() / "Library/Caches/com.jason.beeper-search")) / "bin-path"


def _resolve():
    """(cli path, login-shell PATH) from one login-shell call, marker-delimited against rc noise."""
    shell = os.environ.get("SHELL", "/bin/zsh")
    script = 'printf "\\n@@BS@@%s@@%s@@\\n" "$(command -v beeper-search)" "$PATH"'
    try:
        out = subprocess.run([shell, "-lic", script], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None, None
    for line in reversed(out.splitlines()):
        if line.startswith("@@BS@@") and line.endswith("@@"):
            path, _, shell_path = line[6:-2].partition("@@")
            if path.startswith("/") and os.path.isfile(path) and os.access(path, os.X_OK):
                return path, shell_path
    return None, None


def _cached():
    try:
        entry = json.loads(CACHE.read_text())
        if (isinstance(entry, list) and len(entry) == 2 and all(isinstance(x, str) for x in entry)
                and entry[0].startswith("/") and os.path.isfile(entry[0]) and os.access(entry[0], os.X_OK)
                and time.time() - CACHE.stat().st_mtime < 86400):
            return entry[0], entry[1]
    except (OSError, ValueError):
        pass
    return None, None   # missing, stale or malformed: resolve again


def tool():
    """Path of the beeper-search CLI (BEEPER_SEARCH_BIN overrides), cached for a day."""
    path, shell_path = _cached()
    if not path:
        path, shell_path = _resolve()
        if path:
            try:
                CACHE.parent.mkdir(parents=True, exist_ok=True)
                tmp = CACHE.with_suffix(f".{os.getpid()}")
                tmp.write_text(json.dumps([path, shell_path]))
                os.replace(tmp, CACHE)   # atomic: Alfred terminates superseded runs mid-write
            except OSError:
                pass
    if shell_path:
        os.environ["BS_LOGIN_PATH"] = shell_path   # dependencies (uv, beeper) come from the login PATH
    return os.environ.get("BEEPER_SEARCH_BIN") or path


def env():
    """uv (the CLI's script runner) usually lives in ~/.local/bin or Homebrew."""
    extra = [os.environ.get("BS_LOGIN_PATH", ""), str(Path.home() / ".local/bin"), "/opt/homebrew/bin", "/usr/local/bin"]
    e = {**os.environ, "PATH": os.pathsep.join([p for p in extra if p] + [os.environ.get("PATH", "/usr/bin:/bin")])}
    e.pop("BEEPER_SEARCH_LOG", None)  # Alfred re-runs per keystroke: keep the held-out query log clean
    return e
