import importlib.util
import json
import os
import plistlib
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
            "uid": "/Applications/Safari.app",
            "title": "Safari",
            "subtitle": "↵ New window on this desktop",
            "arg": "/Applications/Safari.app",
            "autocomplete": "Safari",
            "icon": {"type": "fileicon", "path": "/Applications/Safari.app"},
            "match": "Safari",
        }
    ]


@pytest.mark.parametrize(
    ("name", "short_forms"),
    [
        ("Google Chrome", ["GC", "GoogleChrome"]),
        ("Visual Studio Code", ["VSC", "vscode", "vs code"]),
        ("Microsoft Edge", ["ME", "MicrosoftEdge"]),
        ("TextEdit", ["TE", "Text Edit"]),
    ],
)
def test_app_short_forms_preserve_selection(
    monkeypatch, tmp_path, capsys, name, short_forms
):
    path = f"/Applications/{name}.app"
    item = run_list_apps(monkeypatch, tmp_path, capsys, [path])["items"][0]
    assert name in item["match"]
    assert all(term in item["match"] for term in short_forms)
    assert item["arg"] == path
    assert item["autocomplete"] == name


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


@pytest.fixture(scope="module")
def compiled_window_script(tmp_path_factory):
    compiled = tmp_path_factory.mktemp("new-window") / "workflow.scpt"
    subprocess.run(
        ["osacompile", "-o", str(compiled), str(APPLESCRIPT)],
        capture_output=True,
        text=True,
        check=True,
    )
    return compiled


@pytest.mark.parametrize(
    ("title", "rank"),
    [
        ("New Window", 1),
        ("New Finder Window", 1),
        ("New Window with Profile", 1),
        ("Neues Fenster", 1),
        ("Open Chat in New Window", 2),
        ("Open Current Tab in New Window", 2),
        ("In neuem Fenster öffnen", 2),
        ("New", 3),
        ("New…", 3),
        ("New...", 3),
        ("New File", 3),
        ("New Document", 3),
        ("New Text Document", 3),
        ("New Chat", 0),
        ("New Note", 0),
        ("New Tab", 0),
        ("Move To New Window", 0),
        ("New Private Window", 0),
        ("New InPrivate Window", 0),
        ("New Incognito Window", 0),
    ],
)
def test_window_command_selection(title, rank, compiled_window_script):
    # Invoke only the pure title classifier, without running UI automation.
    script = f"""
on run argv
    set workflow to load script POSIX file {json.dumps(str(compiled_window_script))}
    return workflow's windowCommandRank(item 1 of argv)
end run
"""
    result = subprocess.run(
        ["osascript", "-e", script, title], capture_output=True, text=True, check=True
    )
    assert int(result.stdout.strip()) == rank


@pytest.fixture
def obsidian_helper():
    spec = importlib.util.spec_from_file_location(
        "open_obsidian_window", WORKFLOW_DIR / "open_obsidian_window.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fake_obsidian(tmp_path):
    app = tmp_path / "Obsidian Test.app"
    (app / "Contents/MacOS").mkdir(parents=True)
    (app / "Contents/Info.plist").write_bytes(
        plistlib.dumps({"CFBundleExecutable": "Obsidian"})
    )
    executable = app / "Contents/MacOS/Obsidian"

    def install(script):
        executable.write_text("#!/bin/sh\n" + script + "\n")
        executable.chmod(0o755)
        return app

    return install


@pytest.mark.parametrize(
    ("script", "expected"),
    [
        ('test "$1" = command && test "$2" = id=workspace:new-window', ""),
        ("printf 'Executed command'", ""),
        ("printf 'Error: CLI disabled'", "Error: CLI disabled"),
        ("printf 'No vault available' >&2; exit 1", "No vault available"),
        ("exit 2", "Obsidian CLI exited with status 2"),
    ],
)
def test_obsidian_cli_result(obsidian_helper, fake_obsidian, script, expected):
    assert obsidian_helper.open_window(fake_obsidian(script)) == expected


def test_obsidian_cli_timeout(obsidian_helper, fake_obsidian, monkeypatch):
    monkeypatch.setattr(obsidian_helper, "CLI_TIMEOUT", 0.05)
    assert "timed out" in obsidian_helper.open_window(
        fake_obsidian("exec /bin/sleep 2")
    )


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
