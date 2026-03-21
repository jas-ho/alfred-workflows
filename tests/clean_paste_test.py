import importlib.util
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "workflows" / "clean-paste" / "clean.py"


def load_clean():
    """Load the workflow's clean() function from the standalone script."""
    spec = importlib.util.spec_from_file_location("clean_paste_script", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module spec from {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.clean


clean = load_clean()


def expect_equal(name, text, expected):
    got = clean(dedent(text))
    assert (
        got == dedent(expected).strip("\n")
    ), f"{name} failed:\n--- got ---\n{got!r}\n--- expected ---\n{dedent(expected).strip()!r}"


def test_claude_bullet_and_box_table():
    expect_equal(
        "claude",
        """
        ⏺ Yes - all the emails are part of one thread. They all have subject "Re: Follow-up on Apart Research application" (replies to Kasey's original
          email).

          The thread you linked contains all the case studies:
          ┌──────────────┬───────┬────────────────────┐
          │     Date     │ From  │        Contains    │
          └──────────────┴───────┴────────────────────┘
          So Jaime can point Kasey to that single thread as the source of all the names shared in 2024.
        """,
        """
        Yes - all the emails are part of one thread. They all have subject "Re: Follow-up on Apart Research application" (replies to Kasey's original email).

        The thread you linked contains all the case studies:
        ┌──────────────┬───────┬────────────────────┐
        │     Date     │ From  │        Contains    │
        └──────────────┴───────┴────────────────────┘
        So Jaime can point Kasey to that single thread as the source of all the names shared in 2024.
        """,
    )


def test_codex_bullet_with_wrapped_sub_bullets():
    expect_equal(
        "codex",
        """
        • Clean Paste Check

          - Script pulls text from pbpaste, removes indentation, unwraps soft wraps, preserves structural lines, collapses blanks.
          - Workflow operates on clipboard and auto-pastes.
        """,
        """
        Clean Paste Check

        - Script pulls text from pbpaste, removes indentation, unwraps soft wraps, preserves structural lines, collapses blanks.
        - Workflow operates on clipboard and auto-pastes.
        """,
    )


def test_fenced_code_block_is_preserved():
    expect_equal(
        "fence",
        """
        Before

        ```python
            def foo():
                return 42
        ```

        After
        """,
        """
        Before

        ```python
            def foo():
                return 42
        ```

        After
        """,
    )


def test_indented_code_under_bullet_keeps_indent():
    expect_equal(
        "indented code",
        """
        - Example:
            def foo():
                return 42
        """,
        """
        Example:
            def foo():
                return 42
        """,
    )


def test_plain_wrapped_paragraph_unwraps():
    expect_equal(
        "wrapped",
        """
        This is a line that was
        wrapped by the agent to a short width and
        should unwrap.
        """,
        """
        This is a line that was wrapped by the agent to a short width and should unwrap.
        """,
    )


def test_ascii_table_alone_keeps_shape():
    expect_equal(
        "ascii table",
        """
          +---+---+
          | a | b |
          +---+---+
        """,
        """
        +---+---+
        | a | b |
        +---+---+
        """,
    )


def test_tabs_preserved():
    expect_equal(
        "tabs",
        "- Item\n\t\tSubitem with tabs\n",
        "Item\n\t\tSubitem with tabs",
    )


def test_numbered_list_indented_continuation_joins():
    """Wrapped numbered-list items where continuation lines are indented
    (e.g. aligned after '1. ') should join into one line per item.
    Must work regardless of base indent (raw 2-space, Typora 4-space, etc.)."""
    # Uniform 2-space indent (raw Claude output)
    expect_equal(
        "numbered list continuation (2sp)",
        """\
  1. First point starts here
  and continues on the next line
    with deeper-indented wrap.
  2. Second point is short.
""",
        """\
1. First point starts here and continues on the next line with deeper-indented wrap.
2. Second point is short.""",
    )
    # 4-space list with 7/9-space continuations (Typora-style reformat)
    expect_equal(
        "numbered list continuation (4sp Typora)",
        """\
    1. First item starts here
       continuation line
         deeper continuation.
    2. Second item.""",
        """\
1. First item starts here continuation line deeper continuation.
2. Second item.""",
    )


def test_multilevel_lists():
    """Nested lists should preserve structure while joining continuations."""
    # Nested bullets
    expect_equal(
        "nested bullets",
        "- Parent\n  - Child 1\n  - Child 2",
        "Parent\n- Child 1\n- Child 2",
    )
    # Parent wraps, then children
    expect_equal(
        "parent wraps then children",
        "- Parent that wraps\n  to next line\n  - Child 1\n  - Child 2",
        "Parent that wraps to next line\n- Child 1\n- Child 2",
    )
    # Nested numbered with wrapping sub-item
    expect_equal(
        "nested numbered sub-item wraps",
        "1. First\n   a. Sub item wraps\n      to next line\n   b. Another\n2. Second",
        "1. First\n   a. Sub item wraps to next line\n   b. Another\n2. Second",
    )
    # Three-level nesting
    expect_equal(
        "three-level nesting",
        "- Top\n  - Mid\n    - Deep 1\n    - Deep 2\n  - Mid 2\n- Top 2",
        "Top\n  - Mid\n    - Deep 1\n    - Deep 2\n  - Mid 2\n- Top 2",
    )


# Known limitation: unfenced code after prose continuation gets joined.
# If current is non-empty (accumulating prose), an indented line is treated
# as wrapped continuation rather than a code block. Fenced code (```) is
# not affected. Acceptable because Claude output almost always fences code.


def run_all():
    tests = [
        test_claude_bullet_and_box_table,
        test_codex_bullet_with_wrapped_sub_bullets,
        test_fenced_code_block_is_preserved,
        test_indented_code_under_bullet_keeps_indent,
        test_plain_wrapped_paragraph_unwraps,
        test_ascii_table_alone_keeps_shape,
        test_tabs_preserved,
        test_numbered_list_indented_continuation_joins,
        test_multilevel_lists,
    ]
    for fn in tests:
        fn()


if __name__ == "__main__":
    run_all()
