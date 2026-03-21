import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SMART_DATE = ROOT / "workflows" / "smart-date" / "smart_date.js"
MOOM_ACTIONS = ROOT / "workflows" / "moom-actions" / "moom_actions.js"


def _load_jxa_script(path: Path) -> str:
    script = path.read_text(encoding="utf-8")
    if script.startswith("#!"):
        script = "\n".join(script.splitlines()[1:])
    # Avoid Alfred's JXA entrypoint auto-calling run(argv) in test invocations.
    script = re.sub(r"\bfunction\s+run\s*\(", "function __workflow_run(", script, count=1)
    return script


def _eval_jxa(path: Path, expression: str):
    osascript = shutil.which("osascript")
    if osascript is None:
        pytest.skip("osascript not found")

    script = _load_jxa_script(path)
    proc = subprocess.run(
        [osascript, "-l", "JavaScript", "-e", script + f"\nJSON.stringify({expression});"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.returncode == 0, (
        f"JXA evaluation failed for {path.name}\n"
        f"stdout:\n{proc.stdout}\n"
        f"stderr:\n{proc.stderr}"
    )
    return json.loads(proc.stdout.strip())


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("three days ago", "3 days ago"),
        ("half an hour", "30 minutes"),
        ("next month", "in 1 month"),
    ],
)
def test_smart_date_normalize_query(query, expected):
    got = _eval_jxa(SMART_DATE, f"normalizeQuery({json.dumps(query)})")
    assert got == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("3pm", True),
        ("next tuesday", False),
        ("14:30", True),
    ],
)
def test_smart_date_detect_time_component(query, expected):
    got = _eval_jxa(SMART_DATE, f"detectTimeComponent({json.dumps(query)})")
    assert got is expected


def test_smart_date_format_item_shape():
    got = _eval_jxa(
        SMART_DATE,
        """(() => {
            var unix = 1700000000;
            var date = $.NSDate.dateWithTimeIntervalSince1970(unix);
            return {
                dateOnly: formatDateOnly(date, unix),
                dateTime: formatDateTime(date, unix)
            };
        })()""",
    )
    for key in ("dateOnly", "dateTime"):
        items = got[key]
        assert len(items) == 5
        for item in items:
            assert set(item.keys()) == {"title", "subtitle", "arg", "text"}
            assert set(item["text"].keys()) == {"copy", "largetype"}
        assert items[-1]["arg"] == "1700000000"
        assert items[-1]["subtitle"] == "Unix Timestamp"


def test_moom_actions_filter_and_dedup():
    raw_actions = [
        "Window Position\nLeft Half",
        "Window Position\nLeft Half",
        "Folder\nLayouts",
        "Menu Separator\n---",
        "Window Position\nExamples",
        "Window Position\nMore Examples",
        "Window Position\n",
        "Window Position\nRight Half",
    ]
    got = _eval_jxa(
        MOOM_ACTIONS,
        f"buildItemsFromRawActions({json.dumps(raw_actions)})",
    )
    assert [item["title"] for item in got] == ["Left Half", "Right Half", "Center Window"]
    assert got[-1]["arg"] == "__CENTER__"
