import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / "workflows" / "open-new-window"
LIST_APPS = WORKFLOW_DIR / "list_apps.py"
APPLESCRIPT = WORKFLOW_DIR / "open_new_window.applescript"
RUN_SCRIPT = WORKFLOW_DIR / "run_open_new_window.sh"

HOME_APPS = os.path.expanduser("~/Applications")


def run_list_apps(monkeypatch, tmp_path, capsys, mdfind_paths):
    """Execute list_apps.py fresh with mdfind mocked and an isolated cache dir.

    Loading the file directly (rather than a helper function) mirrors how the
    script actually runs under Alfred: as a standalone top-level script.
    """
    monkeypatch.setattr(
        subprocess,
        "check_output",
        lambda *a, **k: "\n".join(mdfind_paths) + ("\n" if mdfind_paths else ""),
    )
    monkeypatch.setenv("alfred_workflow_cache", str(tmp_path))

    spec = importlib.util.spec_from_file_location("list_apps", LIST_APPS)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    out = capsys.readouterr().out
    return json.loads(out)


def test_nested_bundle_excluded(monkeypatch, tmp_path, capsys):
    payload = run_list_apps(
        monkeypatch,
        tmp_path,
        capsys,
        [
            "/Applications/Foo.app",
            "/Applications/Foo.app/Contents/PlugIns/Helper.app",
        ],
    )
    titles = [item["title"] for item in payload["items"]]
    assert titles == ["Foo"]


@pytest.mark.parametrize(
    ("paths", "expected_winner"),
    [
        (
            ["/Applications/Notes.app", f"{HOME_APPS}/Notes.app"],
            "/Applications/Notes.app",
        ),
        (
            [f"{HOME_APPS}/Notes.app", "/Applications/Notes.app"],
            "/Applications/Notes.app",
        ),
        (
            ["/System/Applications/Notes.app", f"{HOME_APPS}/Notes.app"],
            "/System/Applications/Notes.app",
        ),
        (
            [f"{HOME_APPS}/Notes.app", "/System/Applications/Notes.app"],
            "/System/Applications/Notes.app",
        ),
        (
            ["/Applications/Notes.app", "/System/Applications/Notes.app"],
            "/Applications/Notes.app",
        ),
        (
            ["/System/Applications/Notes.app", "/Applications/Notes.app"],
            "/Applications/Notes.app",
        ),
    ],
)
def test_dedupe_prefers_higher_priority_dir(
    monkeypatch, tmp_path, capsys, paths, expected_winner
):
    payload = run_list_apps(monkeypatch, tmp_path, capsys, paths)
    assert [item["arg"] for item in payload["items"]] == [expected_winner]


def test_item_json_structure(monkeypatch, tmp_path, capsys):
    payload = run_list_apps(monkeypatch, tmp_path, capsys, ["/Applications/Safari.app"])
    assert payload["items"] == [
        {
            "title": "Safari",
            "subtitle": "Open new window here",
            "arg": "/Applications/Safari.app",
            "autocomplete": "Safari",
            "icon": {"type": "fileicon", "path": "/Applications/Safari.app"},
            "match": "Safari",
        }
    ]


def test_empty_mdfind_output_yields_no_items(monkeypatch, tmp_path, capsys):
    payload = run_list_apps(monkeypatch, tmp_path, capsys, [])
    assert payload["items"] == []


@pytest.mark.skipif(
    not APPLESCRIPT.exists(), reason="open_new_window.applescript not yet added"
)
def test_applescript_compiles():
    proc = subprocess.run(
        ["osacompile", "-o", "/dev/null", str(APPLESCRIPT)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert (
        proc.returncode == 0
    ), f"osacompile failed\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"


@pytest.mark.skipif(
    not RUN_SCRIPT.exists(), reason="run_open_new_window.sh not yet added"
)
def test_run_script_parses():
    first_line = RUN_SCRIPT.read_text(encoding="utf-8", errors="replace").splitlines()[
        0
    ]
    if "zsh" in first_line:
        zsh = shutil.which("zsh")
        if zsh is None:
            pytest.skip("zsh not found")
        cmd = [zsh, "-n", str(RUN_SCRIPT)]
    else:
        cmd = ["bash", "-n", str(RUN_SCRIPT)]
    proc = subprocess.run(
        cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    assert (
        proc.returncode == 0
    ), f"Command failed: {' '.join(cmd)}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
