"""Smoke tests for the pjws Alfred script filter.

v2's filter is a thin subprocess shim to `pjws alfred-items`. The heavy
lifting (discovery, state parsing, item construction) lives in the `pjws`
Python package and is exercised by its own test suite under ~/Code/pjws.
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FILTER = ROOT / "workflows/pjws/pj_filter.py"


def _load_filter_module():
    spec = importlib.util.spec_from_file_location("pj_filter", FILTER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pj_filter = _load_filter_module()


def test_resolve_pjws_prefers_user_local_bin(tmp_path, monkeypatch):
    fake = tmp_path / ".local" / "bin" / "pjws"
    fake.parent.mkdir(parents=True)
    fake.write_text("#!/bin/sh\nexit 0\n")
    fake.chmod(0o755)
    monkeypatch.setattr(
        pj_filter,
        "CANDIDATE_BINS",
        [fake, Path("/nonexistent/pjws")],
    )
    assert pj_filter._resolve_pjws() == fake


def test_resolve_pjws_returns_none_when_missing(monkeypatch):
    monkeypatch.setattr(
        pj_filter,
        "CANDIDATE_BINS",
        [Path("/nonexistent/a"), Path("/nonexistent/b")],
    )
    assert pj_filter._resolve_pjws() is None


def test_script_emits_error_item_when_pjws_missing(tmp_path, monkeypatch):
    env = dict(os.environ)
    env["PATH"] = "/nonexistent"
    empty_home = tmp_path / "home"
    (empty_home / ".local" / "bin").mkdir(parents=True)
    env["HOME"] = str(empty_home)
    r = subprocess.run(
        [sys.executable, str(FILTER)],
        capture_output=True, text=True, env=env,
    )
    assert r.returncode == 0
    payload = json.loads(r.stdout)
    assert len(payload["items"]) == 1
    assert payload["items"][0].get("valid") is False
    assert "install" in payload["items"][0]["subtitle"].lower()


def test_script_forwards_pjws_alfred_items_stdout(tmp_path):
    shim = tmp_path / "pjws"
    expected = json.dumps({"items": [{"title": "x", "arg": "x"}]})
    shim.write_text(
        f'#!/bin/sh\n'
        f'case "$1" in\n'
        f'  alfred-items) printf %s {json.dumps(expected)} ;;\n'
        f'  *) echo "unknown verb: $1" >&2 ; exit 2 ;;\n'
        f'esac\n'
    )
    shim.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{tmp_path}:{env.get('PATH', '')}"
    home = tmp_path / "home"
    (home / ".local" / "bin").mkdir(parents=True)
    (home / ".local" / "bin" / "pjws").symlink_to(shim)
    env["HOME"] = str(home)
    r = subprocess.run(
        [sys.executable, str(FILTER)],
        capture_output=True, text=True, env=env,
    )
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == json.loads(expected)


def test_script_surfaces_pjws_error_as_alfred_item(tmp_path):
    home = tmp_path / "home"
    (home / ".local" / "bin").mkdir(parents=True)
    shim = home / ".local" / "bin" / "pjws"
    shim.write_text(
        "#!/bin/sh\n"
        "echo 'boom: something broke' >&2\n"
        "exit 3\n"
    )
    shim.chmod(0o755)
    env = dict(os.environ)
    env["HOME"] = str(home)
    r = subprocess.run(
        [sys.executable, str(FILTER)],
        capture_output=True, text=True, env=env,
    )
    assert r.returncode == 0
    payload = json.loads(r.stdout)
    assert len(payload["items"]) == 1
    assert payload["items"][0].get("valid") is False
    assert "boom" in payload["items"][0]["subtitle"]
