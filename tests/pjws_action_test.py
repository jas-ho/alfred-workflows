"""Tests for pj_action notification-summary logic."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "workflows/pjws/pj_action.py"


def _load():
    spec = importlib.util.spec_from_file_location("pj_action", ACTION)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pj_action = _load()


SWITCH_STDOUT_ALL_OK = (
    "pjws: switch → demo\n"
    "  tmux      ok\n"
    "  obsidian  ok\n"
    "  edge      ok\n"
    "  cursor    ok\n"
)

SWITCH_STDOUT_EDGE_SKIPPED = (
    "pjws: switch → demo\n"
    "  tmux      ok\n"
    "  obsidian  ok\n"
    "  edge      skipped\n"
    "  cursor    ok\n"
    "  ↳ edge: Edge migrated to cloud storage; see PLAN-v2.md\n"
)

SWITCH_STDOUT_ALL_FAILED = (
    "pjws: switch → demo\n"
    "  tmux      failed\n"
    "  obsidian  failed\n"
    "  edge      failed\n"
    "  cursor    failed\n"
)


def test_parse_outcomes_extracts_every_adapter_line():
    assert pj_action._parse_outcomes(SWITCH_STDOUT_EDGE_SKIPPED) == {
        "tmux": "ok", "obsidian": "ok", "edge": "skipped", "cursor": "ok",
    }


def test_summary_for_switch_suppressed_when_all_ok():
    assert pj_action._summary_for_notification(
        "demo", "switch", 0, SWITCH_STDOUT_ALL_OK, "",
    ) is None


def test_summary_for_switch_flags_skipped_adapter():
    notice = pj_action._summary_for_notification(
        "demo", "switch", 0, SWITCH_STDOUT_EDGE_SKIPPED, "",
    )
    assert notice is not None
    title, subtitle, message = notice
    assert "switch demo" in title
    assert "edge=skipped" in subtitle
    assert "tmux" in message  # lists still-ok adapters


def test_summary_for_switch_flags_all_failed():
    notice = pj_action._summary_for_notification(
        "demo", "switch", 1, SWITCH_STDOUT_ALL_FAILED, "",
    )
    assert notice is not None
    _, subtitle, message = notice
    assert "edge=failed" in subtitle
    assert "no adapters succeeded" in message


def test_summary_for_switch_falls_back_when_output_unparseable():
    notice = pj_action._summary_for_notification(
        "demo", "switch", 2, "", "pjws: no project matching slug 'demo'\n",
    )
    assert notice is not None
    _, subtitle, message = notice
    assert subtitle == "unparseable outcome"
    assert "no project matching" in message


def test_summary_for_unload_silent_on_success():
    assert pj_action._summary_for_notification(
        "demo", "unload", 0, "pjws: tmux session demo killed\n", "",
    ) is None


def test_summary_for_unload_notifies_on_failure():
    notice = pj_action._summary_for_notification(
        "demo", "unload", 1, "", "pjws: busy (another pjws is running)\n",
    )
    assert notice is not None
    title, subtitle, message = notice
    assert "unload demo" in title
    assert subtitle == "failed"
    assert "busy" in message
