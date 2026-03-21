import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MULTISEND = ROOT / "workflows" / "multi-send" / "multisend.py"

spec = importlib.util.spec_from_file_location("multisend", MULTISEND)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            """- one
  - one a
  - one b
- two
""",
            ["one\n  - one a\n  - one b", "two"],
        ),
        (
            """1. parent
   1. child a
   2. child b
2. next
""",
            ["parent\n   1. child a\n   2. child b", "next"],
        ),
        (
            """  - one
    - one a
  - two
""",
            ["one\n    - one a", "two"],
        ),
    ],
)
def test_detect_items_nested_grouping(text, expected):
    items = module._detect_items(text)
    assert items == expected


def test_numbered_output_keeps_nested_lines_under_same_item():
    text = """- one
  - one a
  - one b
- two
"""
    items = module._detect_items(text)
    output = module._apply_output_format("Numbered list", items)
    assert output == ["1. one\n  - one a\n  - one b", "2. two"]
