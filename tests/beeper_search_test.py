"""Beeper Search workflow launchers (rendering is tested with the CLI in ~/bin)."""
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

WF = Path(__file__).parent.parent / "workflows" / "beeper-search"


def fake_cli(tmp_path, body):
    cli = tmp_path / "beeper-search"
    cli.write_text("#!/bin/sh\n" + body)
    cli.chmod(cli.stat().st_mode | stat.S_IEXEC)
    return cli


def run(script, arg, cli, tmp_path, **extra):
    env = {**os.environ, "BEEPER_SEARCH_BIN": str(cli), "alfred_workflow_cache": str(tmp_path), **extra}
    return subprocess.run([sys.executable, str(WF / script), arg], capture_output=True, text=True, env=env, cwd=WF)


def test_filter_passes_cli_items_through(tmp_path):
    cli = fake_cli(tmp_path, 'echo \'{"items": [{"title": "ok:\'"$3"\'"}]}\'\n')
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


@pytest.mark.parametrize("url", ["https://[broken", "file:///etc/passwd", "https://ok.example/a b", ""])
def test_action_rejects_malformed_links(tmp_path, url):
    cli = fake_cli(tmp_path, "exit 0\n")
    res = run("bs_action.py", json.dumps({"action": "link", "url": url}), cli, tmp_path)
    assert "Refused" in res.stdout and res.returncode == 0


def test_malformed_cache_is_a_miss(tmp_path):
    (tmp_path / "bin-path").write_text(json.dumps(["relative/path", 5, ""]))
    sys.path.insert(0, str(WF))
    import bs_common
    bs_common.CACHE = tmp_path / "bin-path"
    assert bs_common._cached() == (None, None, "")


def recording_cli(tmp_path):
    """Fake CLI that appends {"argv": [...], "stdin": "..."} per call (exact argument boundaries)."""
    log = tmp_path / "calls.jsonl"
    cli = tmp_path / "beeper-search"
    cli.write_text(f"""#!{sys.executable}
import json, sys
data = sys.stdin.read() if "--_log-pick" in sys.argv else ""
with open({str(log)!r}, "a") as f:
    f.write(json.dumps({{"argv": sys.argv[1:], "stdin": data}}) + "\\n")
""")
    cli.chmod(cli.stat().st_mode | stat.S_IEXEC)
    return cli, log


def calls(log, n, wait=3.0):
    import time
    deadline = time.time() + wait            # the pick logger is detached: give it a moment
    while time.time() < deadline and (not log.exists() or len(log.read_text().splitlines()) < n):
        time.sleep(0.05)
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def cache(tmp_path, cli, opt_in):
    (tmp_path / "bin-path").write_text(json.dumps([str(cli), os.environ.get("PATH", ""), opt_in]))


@pytest.mark.parametrize("query", ["taufe emmi", "--help", "-hello"])
def test_pick_logged_after_action_via_stdin(tmp_path, query):
    cli, log = recording_cli(tmp_path)
    cache(tmp_path, cli, "1")
    arg = {"action": "copy", "text": "SECRET-BODY", "query": query, "rank": 2, "conversation": "p1"}
    res = run("bs_action.py", json.dumps(arg), cli, tmp_path)
    assert res.stdout == ""
    [pick] = calls(log, 1)
    assert pick["argv"] == ["--_log-pick"]
    assert json.loads(pick["stdin"]) == {"query": query, "rank": 2, "conversation": "p1", "action": "copy"}
    assert "SECRET-BODY" not in json.dumps(pick)


def test_open_runs_before_the_pick_is_logged(tmp_path):
    cli, log = recording_cli(tmp_path)
    cache(tmp_path, cli, "1")
    arg = {"action": "open", "chat": "c1", "message": "m1", "query": "x", "rank": 1, "conversation": "p1"}
    run("bs_action.py", json.dumps(arg), cli, tmp_path)
    got = calls(log, 2)
    assert got[0]["argv"] == ["--open", "c1", "m1"] and got[1]["argv"] == ["--_log-pick"]


def test_pick_not_logged_without_opt_in(tmp_path):
    cli, log = recording_cli(tmp_path)
    cache(tmp_path, cli, "")
    arg = {"action": "open", "chat": "c1", "message": "m1", "query": "x", "rank": 1, "conversation": "p1"}
    run("bs_action.py", json.dumps(arg), cli, tmp_path)
    assert [c["argv"] for c in calls(log, 2, wait=1.0)] == [["--open", "c1", "m1"]]


def test_old_two_element_cache_is_a_miss(tmp_path):
    cli, _ = recording_cli(tmp_path)
    (tmp_path / "bin-path").write_text(json.dumps([str(cli), "/usr/bin"]))
    sys.path.insert(0, str(WF))
    import bs_common
    bs_common.CACHE = tmp_path / "bin-path"
    assert bs_common._cached() == (None, None, "")
