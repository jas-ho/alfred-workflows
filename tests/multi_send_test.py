import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MULTISEND = ROOT / "workflows" / "multi-send" / "multisend.py"

spec = importlib.util.spec_from_file_location("multisend", MULTISEND)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_detect_items_groups_nested_dash_lists_with_parent():
    text = """- one
  - one a
  - one b
- two
"""
    items = module._detect_items(text)
    assert items == ["one\n  - one a\n  - one b", "two"]


def test_detect_items_groups_nested_numbered_lists_with_parent():
    text = """1. parent
   1. child a
   2. child b
2. next
"""
    items = module._detect_items(text)
    assert items == ["parent\n   1. child a\n   2. child b", "next"]


def test_numbered_output_keeps_nested_lines_under_same_item():
    text = """- one
  - one a
  - one b
- two
"""
    items = module._detect_items(text)
    output = module._apply_output_format("Numbered list", items)
    assert output == ["1. one\n  - one a\n  - one b", "2. two"]


def test_top_level_indent_baseline_respected():
    text = """  - one
    - one a
  - two
"""
    items = module._detect_items(text)
    assert items == ["one\n    - one a", "two"]
