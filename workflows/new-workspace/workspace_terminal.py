"""Read-only terminal linking and shared tmux invocation policy."""

from __future__ import annotations

import errno
import os
import re
import shutil
import stat
import subprocess
import unicodedata
from pathlib import Path


def environment() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("TMUX", None)
    env.pop("TMUX_TMPDIR", None)
    env["PATH"] = ":".join(
        [str(Path.home() / p) for p in ("bin", ".local/bin", ".volta/bin")]
        + [
            "/opt/homebrew/bin",
            "/opt/homebrew/sbin",
            "/usr/local/bin",
            "/usr/bin",
            "/bin",
            "/usr/sbin",
            "/sbin",
        ]
    )
    return env


def tmux_binary() -> str:
    binary = shutil.which("tmux", path=environment()["PATH"])
    if not binary:
        raise RuntimeError(
            "tmux is not installed; restore tmux access before creating a workspace"
        )
    return binary


def session_name(name: str) -> str:
    if not name or any(c in ":." or unicodedata.category(c) == "Cc" for c in name):
        raise ValueError(
            "tmux session name must be nonempty, without dots, colons or control characters"
        )
    return name


def sessions() -> list[str]:
    try:
        result = subprocess.run(
            [tmux_binary(), "list-sessions", "-F", "#{session_name}"],
            env=environment(),
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError(f"Cannot inspect tmux sessions: {error}") from error
    if result.returncode:
        message = result.stderr.strip()
        if message.startswith("no server running on ") or (
            message.startswith("error connecting to ")
            and message.endswith("(No such file or directory)")
        ):
            return []
        raise RuntimeError(
            "Cannot inspect tmux sessions: " + (message or "tmux failed")
        )
    if not result.stdout:
        return []
    names = result.stdout.removesuffix("\n").split("\n")
    if len(names) != len(set(names)):
        raise RuntimeError("Cannot inspect tmux sessions: malformed session inventory")
    try:
        for name in names:
            session_name(name)
    except ValueError as error:
        raise RuntimeError(
            "Cannot inspect tmux sessions: malformed session inventory"
        ) from error
    return names


def key(name: str) -> str:
    return unicodedata.normalize("NFC", name).strip().casefold()


def project_roots(data: dict) -> list[tuple[Path, int]]:
    roots = data.get("project_roots", [])
    if not isinstance(roots, list):
        raise ValueError("project_roots must be an ordered list of {path, depth}")
    result = []
    for item in roots:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("path"), str)
            or not item["path"].strip()
            or type(item.get("depth")) is not int
            or not 1 <= item["depth"] <= 3
        ):
            raise ValueError(
                "Each project_roots entry needs a path and integer depth from 1 to 3"
            )
        result.append((Path(item["path"]).expanduser(), item["depth"]))
    return result


def folders(root: Path, depth: int) -> list[Path]:
    """Enumerate an exact depth; missing paths are empty, inaccessible paths fail."""
    try:
        if not stat.S_ISDIR(root.stat().st_mode):
            return []
        with os.scandir(root) as entries:
            children = sorted(
                (Path(e.path) for e in entries if not e.name.startswith("."))
            )
        result = []
        for child in children:
            if depth > 1:
                result.extend(folders(child, depth - 1))
            else:
                try:
                    if stat.S_ISDIR(child.stat().st_mode):
                        result.append(child)
                except OSError as error:
                    if error.errno not in (errno.ENOENT, errno.ELOOP):
                        raise
        return result
    except OSError as error:
        if error.errno in (errno.ENOENT, errno.ELOOP):
            return []
        raise RuntimeError(
            f"Cannot search {error.filename or root}: {error.strerror}; "
            "fix access or use workspace create NAME --directory ~"
        ) from error


def folder_matches(name: str, candidates: list[Path]) -> list[Path]:
    matched: set[Path] = set()
    for path in candidates:
        if key(name) in (
            key(path.name),
            key(re.sub(r"^[0-9]{4}-[0-9]{2}_", "", path.name, count=1)),
        ):
            matched.add(path.resolve())
    return sorted(matched)


def intent(*, session=None, directory=None, new_name=None, ambiguous=False) -> dict:
    return {
        "tmux_session": session,
        "directory": str(directory or Path.home()),
        "new_tmux_session": new_name,
        "ambiguous": ambiguous,
    }


def session_match(name: str, names: list[str]) -> list[str]:
    return [s for s in names if key(s) == key(name)]


def resolve(name: str, data: dict) -> dict:
    roots = project_roots(data)
    names = sessions()
    matches = session_match(name, names)
    if matches:
        return (
            intent(session=matches[0]) if len(matches) == 1 else intent(ambiguous=True)
        )
    for root, depth in roots:
        folder_hits = folder_matches(name, folders(root, depth))
        if len(folder_hits) > 1:
            return intent(ambiguous=True)
        if folder_hits:
            folder = folder_hits[0]
            derived = session_name(folder.name.replace(".", "_").replace(":", "_"))
            existing = session_match(derived, names)
            if len(existing) > 1:
                return intent(ambiguous=True)
            return intent(
                session=existing[0] if existing else None,
                directory=folder,
                new_name=None if existing else derived,
            )
    return intent()


def describe(value: dict) -> str:
    if value["tmux_session"]:
        return "attaches tmux " + value["tmux_session"]
    if value["new_tmux_session"]:
        directory = value["directory"]
        home = str(Path.home())
        if directory.startswith(home + "/"):
            directory = "~" + directory[len(home) :]
        return f"tmux {value['new_tmux_session']} in {directory}"
    prefix = "ambiguous name · " if value["ambiguous"] else ""
    return prefix + "new tmux session in ~"
