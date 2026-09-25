"""Public CLI schema, target policy and file mailbox concurrency contracts."""

import fcntl
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "workflows/new-workspace"
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("public_workspace", ROOT / "workspace.py")
assert spec is not None and spec.loader is not None
ws = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ws)


def response(capsys):
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert set(payload) == {
        "schema_version",
        "operation",
        "operation_id",
        "status",
        "data",
        "error",
    }
    assert payload["schema_version"] == 1
    return payload


@pytest.mark.parametrize(
    "argv",
    [
        ["--json"],
        ["--json", "doorplate"],
        ["filter", "--json"],
        ["alfred-action", "--json"],
        ["switch", "--json"],
        ["rename", "--json"],
        ["switch", "Name", "--id", "123", "--json"],
        ["close", "1", "--id", "123", "--json"],
        ["list", "--unknown", "--json"],
        ["result", "../file", "--json"],
        ["rename", " ", "--json"],
        ["rename", "a\x00b", "--json"],
        ["rename", "a" * 121, "--json"],
        ["switch", "--id", "nan", "--json"],
        ["close", "--id", "9007199254740992", "--json"],
        ["close", "--id", "0", "--json"],
        ["switch", "--id", "9" * 5000, "--json"],
    ],
)
def test_usage_errors_are_one_json_object_without_submission(argv, monkeypatch, capsys):
    monkeypatch.setattr(
        ws, "send", lambda _: pytest.fail("invalid arguments were submitted")
    )
    assert ws.main(argv) == 2
    payload = response(capsys)
    assert payload["status"] == "failed"
    assert payload["error"]["code"] == "invalid_arguments"
    assert payload["operation_id"] is None


@pytest.mark.parametrize("before", [True, False])
@pytest.mark.parametrize(
    "command",
    ["list", "back", "check", "switch", "rename", "close", "create", "result"],
)
def test_every_command_accepts_json_on_either_side(
    command, before, monkeypatch, capsys, tmp_path
):
    monkeypatch.setattr(ws, "STATE", tmp_path)
    monkeypatch.setattr(ws, "recipe", list)
    monkeypatch.setattr(ws, "create_request", lambda _: {"operation": "create"})
    ident = "b" * 32
    record = {"id": ident, "operation": command, "status": "complete"}
    (tmp_path / (ident + ".json")).write_text(json.dumps(record))
    monkeypatch.setattr(ws, "send", lambda _: record)
    argv = [command]
    if command in ("create", "rename", "switch"):
        argv.append("Name")
    elif command == "result":
        argv.append(ident)
    argv = ["--json", *argv] if before else [*argv, "--json"]
    assert ws.main(argv) == 0
    assert response(capsys)["operation_id"] == ident


@pytest.mark.parametrize("status", sorted(ws.STATUSES))
def test_only_complete_is_exit_zero(status, monkeypatch, capsys):
    monkeypatch.setattr(ws, "send", lambda _: {"id": "c" * 32, "status": status})
    assert ws.main(["list", "--json"]) == (0 if status == "complete" else 1)
    assert response(capsys)["status"] == status


@pytest.mark.parametrize(
    "argv,expected",
    [
        (["list"], {"operation": "list"}),
        (["switch", "Research"], {"operation": "switch", "query": "Research"}),
        (["switch", "2"], {"operation": "switch", "query": "2"}),
        (["switch", "--id", "00123"], {"operation": "switch", "space_id": "123"}),
        (["rename", " New Name "], {"operation": "rename", "name": "New Name"}),
        (
            ["rename", "New", "--id", "123"],
            {"operation": "rename", "name": "New", "space_id": "123"},
        ),
        (["back"], {"operation": "back"}),
        (
            ["close"],
            {"operation": "close", "execute": False, "confirm": False, "notify": False},
        ),
        (
            ["close", "--id", "123", "--yes"],
            {
                "operation": "close",
                "space_id": "123",
                "execute": True,
                "confirm": False,
                "notify": False,
            },
        ),
    ],
)
def test_operation_request_targeting_and_close_policy(argv, expected):
    assert ws.operation_request(ws.parser().parse_args(argv)) == expected


def test_check_reports_recipe_failure_without_skipping_live_checks(monkeypatch):
    monkeypatch.setattr(
        ws, "recipe", lambda **kwargs: (_ for _ in ()).throw(ValueError("Missing app"))
    )
    request = ws.operation_request(ws.parser().parse_args(["check"]))
    assert request["operation"] == "check"
    assert request["apps_error"] == "Missing app"
    assert request["urls"] == []
    assert request["directory"] == str(Path.home())


def test_ids_and_lua_empty_arrays_normalize_at_public_boundary():
    result = {
        "id": "d" * 32,
        "operation": "list",
        "status": "complete",
        "active": 123,
        "spaces": [{"id": 123, "name": "Research"}],
        "keeper": 456,
        "windows": [{"id": 789, "spaces": [123], "space_id": 123}],
        "warnings": {},
        "checks": {"worker": True},
    }
    payload = ws.envelope(result, "list")
    assert payload["data"]["active"] == "123"
    assert payload["data"]["keeper"] == "456"
    assert payload["data"]["spaces"][0]["id"] == "123"
    assert payload["data"]["windows"][0] == {
        "id": 789,
        "spaces": ["123"],
        "space_id": "123",
    }
    assert payload["data"]["warnings"] == []
    assert payload["data"]["checks"] == {"worker": True}
    assert (
        ws.envelope(
            {
                "status": "partial",
                "windows": {},
                "error": "Denied",
                "error_code": "permission_denied",
            },
            "create",
        )["data"]["windows"]
        == []
    )
    assert result["active"] == 123  # conversion never changes the stored record


def test_result_reads_fresh_record_and_never_submits(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ws, "STATE", tmp_path)
    monkeypatch.setattr(
        ws, "send", lambda _: pytest.fail("result submitted an operation")
    )
    ident = "e" * 32
    path = tmp_path / (ident + ".json")
    for status in ("running", "partial", "complete"):
        raw = json.dumps(
            {"id": ident, "operation": "create", "status": status, "space_id": 123}
        )
        path.write_text(raw)
        assert ws.main(["result", ident, "--json"]) == (
            0 if status == "complete" else 1
        )
        payload = response(capsys)
        assert payload["operation"] == "create"
        assert payload["status"] == status
        assert payload["data"]["space_id"] == "123"
        assert path.read_text() == raw


def test_result_missing_retains_requested_operation_id(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ws, "STATE", tmp_path)
    ident = "f" * 32
    assert ws.main(["result", ident, "--json"]) == 1
    payload = response(capsys)
    assert payload["operation_id"] == ident
    assert payload["error"]["code"] == "result_not_found"


def test_help_remains_text_and_documents_retry(monkeypatch, capsys):
    monkeypatch.setattr(
        ws, "send", lambda _: pytest.fail("help submitted an operation")
    )
    assert ws.main(["--json", "--help"]) == 0
    captured = capsys.readouterr()
    assert "usage: workspace" in captured.out
    assert "uncertain" in captured.out and "result" in captured.out
    assert "alfred-action" not in captured.out and "filter" not in captured.out
    assert captured.err == ""


def clock(monkeypatch):
    ticks = [0.0]
    monkeypatch.setattr(ws.time, "time", lambda: ticks[0])
    monkeypatch.setattr(ws.time, "monotonic", lambda: ticks[0])
    return ticks


def lock_available(path):
    with path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True


def test_mailbox_lock_released_only_after_matching_ack(tmp_path, monkeypatch):
    monkeypatch.setattr(ws, "STATE", tmp_path)
    ticks = clock(monkeypatch)
    locks = []

    def step(seconds):
        ticks[0] += seconds
        request = json.loads((tmp_path / "request.json").read_text())
        path = tmp_path / (request["id"] + ".json")
        available = lock_available(tmp_path / "client.lock")
        locks.append(available)
        if len(locks) == 1:
            path.write_text(json.dumps({"id": "wrong", "status": "complete"}))
        elif len(locks) == 2:
            path.write_text(json.dumps({"id": request["id"], "status": "running"}))
        else:
            path.write_text(json.dumps({"id": request["id"], "status": "complete"}))

    monkeypatch.setattr(ws.time, "sleep", step)
    result = ws.send({"operation": "list"})
    assert result["status"] == "complete"
    assert locks == [False, False, True]


def test_timeout_keeps_worker_record_and_partial_details(tmp_path, monkeypatch):
    monkeypatch.setattr(ws, "STATE", tmp_path)
    ticks = clock(monkeypatch)

    def step(seconds):
        ticks[0] += seconds
        request = json.loads((tmp_path / "request.json").read_text())
        (tmp_path / (request["id"] + ".json")).write_text(
            json.dumps(
                {
                    "id": request["id"],
                    "operation": "create",
                    "status": "running",
                    "space_id": 123,
                }
            )
        )

    monkeypatch.setattr(ws.time, "sleep", step)
    result = ws.send({"operation": "create"}, timeout=0.5)
    stored = json.loads((tmp_path / (result["id"] + ".json")).read_text())
    assert result["status"] == "uncertain"
    assert result["space_id"] == 123 and result["acknowledged"] is True
    assert stored["status"] == "running"
    assert lock_available(tmp_path / "client.lock")


@pytest.mark.parametrize("acknowledged", [False, True])
@pytest.mark.parametrize(
    "operation_request,read_only",
    [
        ({"operation": "list"}, True),
        ({"operation": "check"}, True),
        ({"operation": "close", "execute": False}, True),
        ({"operation": "close", "execute": True}, False),
        ({"operation": "create"}, False),
        ({"operation": "rename"}, False),
        ({"operation": "switch"}, False),
        ({"operation": "back"}, False),
    ],
)
def test_timeout_retry_guidance_only_allows_read_operations(
    tmp_path, monkeypatch, acknowledged, operation_request, read_only
):
    monkeypatch.setattr(ws, "STATE", tmp_path)
    ticks = clock(monkeypatch)

    def step(seconds):
        ticks[0] += seconds
        if acknowledged:
            submitted = json.loads((tmp_path / "request.json").read_text())
            (tmp_path / (submitted["id"] + ".json")).write_text(
                json.dumps({"id": submitted["id"], "status": "running"})
            )

    monkeypatch.setattr(ws.time, "sleep", step)
    result = ws.send(operation_request, timeout=0.5)
    assert result["status"] == "uncertain"
    assert result["acknowledged"] is acknowledged
    assert ("can be retried" in result["error"]) is read_only
    assert ("Do not repeat" in result["error"]) is not read_only
    assert "workspace result " + result["id"] in result["error"]


def test_busy_client_does_not_overwrite_mailbox(tmp_path, monkeypatch):
    monkeypatch.setattr(ws, "STATE", tmp_path)
    mailbox = tmp_path / "request.json"
    mailbox.write_text('{"existing": true}')
    with (tmp_path / "client.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = ws.send({"operation": "close"})
    assert result["status"] == "blocked"
    assert result["error_code"] == "client_busy"
    assert "id" not in result
    assert mailbox.read_text() == '{"existing": true}'


def test_human_list_uses_native_desktop_numbers_and_active_id(monkeypatch, capsys):
    monkeypatch.setattr(
        ws,
        "send",
        lambda _: {
            "status": "complete",
            "active": "123",
            "desktops": [{"id": "123", "number": 3, "name": "Research"}],
        },
    )
    assert ws.main(["list"]) == 0
    assert capsys.readouterr().out == "* 3: Research (id 123)\n"
