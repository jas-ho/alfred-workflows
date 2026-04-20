import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "workflows" / "run-command" / "run.sh"


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Isolate HOME (empty rc files) and intercept pbcopy.

    Returns a dict with:
      - env: env to pass to subprocess
      - clip: path where the fake pbcopy writes what it received
    """
    home = tmp_path / "home"
    home.mkdir()
    (home / ".zshenv").write_text("")
    (home / ".zprofile").write_text("")
    (home / ".zshrc").write_text("")

    clip = tmp_path / "clip"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    pbcopy = fake_bin / "pbcopy"
    pbcopy.write_text(f"#!/bin/sh\ncat > {clip}\n")
    pbcopy.chmod(0o755)

    env = {
        **os.environ,
        "HOME": str(home),
        "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
    }
    return {"env": env, "clip": clip}


def run(cmd: str, env) -> tuple[str, int]:
    proc = subprocess.run(
        [str(SCRIPT), cmd],
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.stdout.strip(), proc.returncode


def test_success_with_stdout_reports_output_and_copies_to_clipboard(sandbox):
    out, rc = run("echo hello", sandbox["env"])
    assert rc == 0
    assert out == "✓ hello"
    assert sandbox["clip"].read_text() == "hello"


def test_success_with_no_output_reports_no_output(sandbox):
    out, rc = run("true", sandbox["env"])
    assert rc == 0
    assert out == "✓ no output"
    assert not sandbox["clip"].exists(), "clipboard should not be touched when stdout is empty"


def test_failure_exit_code_and_stderr(sandbox):
    out, rc = run("nosuchcommand_xyzzy", sandbox["env"])
    assert rc == 0  # the wrapper itself always succeeds
    assert out.startswith("✗ exit 127")
    assert "not found" in out


def test_failure_with_explicit_nonzero_rc(sandbox):
    out, rc = run("false", sandbox["env"])
    assert rc == 0
    assert out == "✗ exit 1"


def test_multiline_stdout_is_flattened_for_notification(sandbox):
    out, rc = run("printf 'a\\nb\\nc\\n'", sandbox["env"])
    assert rc == 0
    assert out == "✓ a ↵ b ↵ c"
    assert sandbox["clip"].read_text() == "a\nb\nc"


def test_long_stdout_is_truncated_in_notification_but_full_in_clipboard(sandbox):
    out, rc = run("printf '%.0sx' {1..500}", sandbox["env"])
    assert rc == 0
    assert out.startswith("✓ ")
    # 240-char body + "✓ " prefix + trailing "…"
    body = out[len("✓ "):]
    assert body.endswith("…")
    assert len(body) == 241  # 240 chars + ellipsis
    assert len(sandbox["clip"].read_text()) == 500


def test_empty_command_is_handled_gracefully(sandbox):
    out, rc = run("", sandbox["env"])
    assert rc == 0
    assert out == "run: empty command"
    assert not sandbox["clip"].exists()


def test_rc_files_are_sourced(sandbox, tmp_path):
    # Put an alias in .zshrc and verify it expands.
    (Path(sandbox["env"]["HOME"]) / ".zshrc").write_text("alias greet='echo hi-from-rc'\n")
    out, rc = run("greet", sandbox["env"])
    assert rc == 0
    assert out == "✓ hi-from-rc"


def test_rc_interactive_guard_still_fires(sandbox):
    # Common pattern at the top of .zshrc; we need a real `-i` shell so that
    # this guard passes and the aliases below it get loaded.
    (Path(sandbox["env"]["HOME"]) / ".zshrc").write_text(
        "[[ -o interactive ]] || return\nalias greet='echo from-guarded-rc'\n"
    )
    out, rc = run("greet", sandbox["env"])
    assert rc == 0
    assert out == "✓ from-guarded-rc"


def test_zdotdir_is_respected(sandbox, tmp_path):
    # If .zshenv exports ZDOTDIR, zsh reads .zprofile/.zshrc from there.
    zdot = tmp_path / "zdot"
    zdot.mkdir()
    (zdot / ".zshrc").write_text("alias greet='echo from-zdotdir'\n")
    (Path(sandbox["env"]["HOME"]) / ".zshenv").write_text(f'export ZDOTDIR="{zdot}"\n')
    out, rc = run("greet", sandbox["env"])
    assert rc == 0
    assert out == "✓ from-zdotdir"


def test_rc_file_errors_do_not_leak_to_stderr(sandbox):
    # Simulate a broken .zshrc that writes to stderr — the wrapper should suppress it.
    (Path(sandbox["env"]["HOME"]) / ".zshrc").write_text(
        "echo 'boom' >&2\nsetopt zle\n"  # setopt zle fails in non-tty; both should be hidden
    )
    out, rc = run("echo ok", sandbox["env"])
    assert rc == 0
    assert out == "✓ ok"


def test_working_directory_is_home(sandbox):
    out, _ = run("pwd", sandbox["env"])
    assert out == f"✓ {sandbox['env']['HOME']}"


def test_special_characters_in_command(sandbox):
    # Single quotes, double quotes, $VAR, backticks — all should survive argv passing.
    out, _ = run("""echo 'a "b" c' $HOME""", sandbox["env"])
    assert out == f'✓ a "b" c {sandbox["env"]["HOME"]}'
