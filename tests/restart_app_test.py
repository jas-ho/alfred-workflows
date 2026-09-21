"""Restart selection/lifecycle checks without quitting any live application."""

import importlib.util
import json
import plistlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "workflows/restart-app"
spec = importlib.util.spec_from_file_location("restart_app", DIR / "restart_app.py")
assert spec and spec.loader
ra = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ra)


def test_restart_keeps_identity_and_literal_names():
    apps = [
        {
            "pid": 42,
            "path": '/Applications/Comma, "Name".app',
            "name": 'Comma, "Name"',
            "launched": 1.25,
        }
    ]
    row = ra.items(apps)[0]
    assert json.loads(row["arg"])["target"] == apps[0]
    assert json.loads(row["mods"]["alt"]["arg"])["action"] == "quit"
    assert row["icon"]["path"] == apps[0]["path"]
    assert not ra.items(apps, [apps[0]["path"]])[0]["valid"]


def test_restart_matching_terms():
    assert "Text Edit" in ra.match_terms("TextEdit")
    assert "TE" in ra.match_terms("TextEdit")
    assert "vscode" in ra.match_terms("Visual Studio Code")
    assert "Microsoft Edge" in ra.match_terms("Microsoft Edge")


def test_restart_aliases_share_one_filter_and_native_alfred_matching():
    config = plistlib.loads((DIR / "info.plist").read_bytes())
    filters = [
        o["config"]
        for o in config["objects"]
        if o["type"] == "alfred.workflow.input.scriptfilter"
    ]
    assert len(filters) == 1
    assert filters[0]["keyword"] == "ra||rr||restart||relaunch"
    assert filters[0]["alfredfiltersresults"] is True
    assert filters[0]["alfredfiltersresultsmatchmode"] == 2


def test_restart_native_lifecycle():
    result = subprocess.run(
        ["node", str(ROOT / "tests/restart_app_native_test.js")],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
