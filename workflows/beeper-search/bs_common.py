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
    """(cli path, login PATH, BEEPER_SEARCH_LOG) from one login-shell call, marker-delimited against rc noise."""
    shell = os.environ.get("SHELL", "/bin/zsh")
    script = 'printf "\\n@@BS@@%s@@%s@@%s@@\\n" "$(command -v beeper-search)" "$PATH" "$BEEPER_SEARCH_LOG"'
    try:
        out = subprocess.run([shell, "-lic", script], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None, None, ""
    for line in reversed(out.splitlines()):
        if line.startswith("@@BS@@") and line.endswith("@@"):
            parts = line[6:-2].split("@@")
            if len(parts) == 3 and parts[0].startswith("/") and os.path.isfile(parts[0]) and os.access(parts[0], os.X_OK):
                return parts[0], parts[1], parts[2]
    return None, None, ""


def _cached():
    try:
        entry = json.loads(CACHE.read_text())
        if (isinstance(entry, list) and len(entry) == 3 and all(isinstance(x, str) for x in entry)
                and entry[0].startswith("/") and os.path.isfile(entry[0]) and os.access(entry[0], os.X_OK)
                and time.time() - CACHE.stat().st_mtime < 86400):
            return entry[0], entry[1], entry[2]
    except (OSError, ValueError):
        pass
    return None, None, ""   # missing, stale or malformed: resolve again


def tool():
    """Path of the beeper-search CLI (BEEPER_SEARCH_BIN overrides), cached for a day."""
    path, shell_path, log = _cached()
    if not path:
        path, shell_path, log = _resolve()
        if path:
            try:
                CACHE.parent.mkdir(parents=True, exist_ok=True)
                tmp = CACHE.with_suffix(f".{os.getpid()}")
                tmp.write_text(json.dumps([path, shell_path, log]))
                os.replace(tmp, CACHE)   # atomic: Alfred terminates superseded runs mid-write
            except OSError:
                pass
    if shell_path:
        os.environ["BS_LOGIN_PATH"] = shell_path   # dependencies (uv, beeper) come from the login PATH
    os.environ["BS_LOGIN_LOG"] = log or ""          # your .zshrc opt-in for the query log
    return os.environ.get("BEEPER_SEARCH_BIN") or path


def env():
    """uv (the CLI's script runner) usually lives in ~/.local/bin or Homebrew."""
    extra = [os.environ.get("BS_LOGIN_PATH", ""), str(Path.home() / ".local/bin"), "/opt/homebrew/bin", "/usr/local/bin"]
    e = {**os.environ, "PATH": os.pathsep.join([p for p in extra if p] + [os.environ.get("PATH", "/usr/bin:/bin")])}
    e.pop("BEEPER_SEARCH_LOG", None)  # Alfred re-runs per keystroke: keep the held-out query log clean
    return e


def log_pick(arg):
    """Record the final query and the row acted on, detached (the action never waits on it).

    Only if logging is on in the login shell; only allowlisted fields, sent on stdin.
    """
    try:
        cli = tool()
        if os.environ.get("BS_LOGIN_LOG") != "1" or not cli or not isinstance(arg.get("query"), str):
            return
        pick = {k: arg.get(k) for k in ("query", "rank", "conversation", "action")}
        proc = subprocess.Popen([cli, "--_log-pick"], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, env={**env(), "BEEPER_SEARCH_LOG": "1"},
                                text=True, start_new_session=True)
        proc.stdin.write(json.dumps(pick))
        proc.stdin.close()
    except (OSError, ValueError):
        pass
