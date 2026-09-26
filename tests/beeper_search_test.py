"""Beeper Search workflow launchers (rendering is tested with the CLI in ~/bin)."""
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

WF = Path(__file__).parent.parent / "workflows" / "beeper-search"


def fake_cli(tmp_path, body):
    cli = tmp_path / "beeper-search"
    cli.write_text("#!/bin/sh\n" + body)
    cli.chmod(cli.stat().st_mode | stat.S_IEXEC)
    return cli


def run(script, arg, cli, tmp_path):
    env = {**os.environ, "BEEPER_SEARCH_BIN": str(cli), "alfred_workflow_cache": str(tmp_path)}
    return subprocess.run([sys.executable, str(WF / script), arg], capture_output=True, text=True, env=env, cwd=WF)


def test_filter_passes_cli_items_through(tmp_path):
    cli = fake_cli(tmp_path, 'echo \'{"items": [{"title": "ok:\'"$2"\'"}]}\'\n')
    out = json.loads(run("bs_filter.py", "taufe emmi", cli, tmp_path).stdout)
    assert out["items"][0]["title"] == "ok:taufe emmi"


def test_filter_reports_cli_failure(tmp_path):
    cli = fake_cli(tmp_path, "echo boom >&2; exit 3\n")
    out = json.loads(run("bs_filter.py", "x y", cli, tmp_path).stdout)
    assert out["items"][0]["valid"] is False and "boom" in out["items"][0]["subtitle"]


def test_action_open_calls_cli(tmp_path):
    log = tmp_path / "args"
    cli = fake_cli(tmp_path, f'echo "$@" > {log}\n')
    res = run("bs_action.py", json.dumps({"action": "open", "chat": "c1", "message": "m1"}), cli, tmp_path)
    assert res.stdout == "" and log.read_text().split() == ["--open", "c1", "m1"]


def test_action_refuses_non_http_link(tmp_path):
    cli = fake_cli(tmp_path, "exit 0\n")
    res = run("bs_action.py", json.dumps({"action": "link", "url": "file:///etc/passwd"}), cli, tmp_path)
    assert "Refused" in res.stdout
