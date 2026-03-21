import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MULTICLIP = ROOT / "workflows" / "multi-paste" / "multiclip.py"

spec = importlib.util.spec_from_file_location("multiclip", MULTICLIP)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_dash_list_strips_ordered_prefixes():
    output = module._format_items(
        "Dash list",
        [
            "1. one",
            "2. two",
            "3. three",
        ],
    )
    assert output == "- one\n- two\n- three"


def test_numbered_list_strips_unordered_prefixes():
    output = module._format_items(
        "Numbered list",
        [
            "- one",
            "- two",
            "- three",
        ],
    )
    assert output == "1. one\n2. two\n3. three"


def test_list_reformat_only_strips_single_marker():
    output = module._format_items(
        "Numbered list",
        ["- - nested"],
    )
    assert output == "1. - nested"


def test_plain_format_keeps_existing_list_prefixes():
    output = module._format_items(
        "Plain (newlines)",
        ["- one", "2. two"],
    )
    assert output == "- one\n2. two"


def test_dash_list_does_not_strip_year_like_prefix():
    output = module._format_items(
        "Dash list",
        ["2026. was weird"],
    )
    assert output == "- 2026. was weird"
