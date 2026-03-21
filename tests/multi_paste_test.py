import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MULTICLIP = ROOT / "workflows" / "multi-paste" / "multiclip.py"

spec = importlib.util.spec_from_file_location("multiclip", MULTICLIP)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


@pytest.mark.parametrize(
    ("fmt", "items", "expected"),
    [
        (
            "Dash list",
            ["1. one", "2. two", "3. three"],
            "- one\n- two\n- three",
        ),
        (
            "Numbered list",
            ["- one", "- two", "- three"],
            "1. one\n2. two\n3. three",
        ),
        (
            "Numbered list",
            ["- - nested"],
            "1. - nested",
        ),
        (
            "Plain (newlines)",
            ["- one", "2. two"],
            "- one\n2. two",
        ),
        (
            "Dash list",
            ["2026. was weird"],
            "- 2026. was weird",
        ),
    ],
)
def test_format_items_reformat_cases(fmt, items, expected):
    output = module._format_items(fmt, items)
    assert output == expected
