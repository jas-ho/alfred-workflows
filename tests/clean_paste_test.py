import importlib.util
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "workflows" / "clean-paste" / "clean_core.py"


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
    want = dedent(expected).strip("\n")
    assert (
        got == want
    ), f"{name} failed:\n--- got ---\n{got!r}\n--- expected ---\n{want!r}"


def expect_equal_raw(name, text, expected):
    got = clean(text)
    want = expected.strip("\n")
    assert (
        got == want
    ), f"{name} failed:\n--- got ---\n{got!r}\n--- expected ---\n{want!r}"


def test_wrapper_marker_strips_single_container():
    expect_equal(
        "wrapper marker",
        """
        ⏺ Clean Paste Check

          - Script pulls text from pbpaste, removes indentation, unwraps soft wraps, preserves structural lines, collapses blanks.
          - Workflow operates on clipboard and auto-pastes.
        """,
        """
        Clean Paste Check

        - Script pulls text from pbpaste, removes indentation, unwraps soft wraps, preserves structural lines, collapses blanks.
        - Workflow operates on clipboard and auto-pastes.
        """,
    )


def test_wrapper_marker_not_stripped_for_real_list():
    expect_equal_raw("real bullet list", "• one\n• two\n", "• one\n• two")


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


def test_indented_fence_in_list_with_blank_lines_is_preserved():
    expect_equal(
        "indented fence in list",
        """
        - Example
            ```python
            line1

            line2
            ```
        - Next
        """,
        """
        - Example
            ```python
            line1

            line2
            ```
        - Next
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


def test_numbered_list_indented_continuation_joins():
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


def test_multilevel_lists_preserve_structure():
    expect_equal(
        "nested bullets",
        "- Parent\n  - Child 1\n  - Child 2",
        "- Parent\n  - Child 1\n  - Child 2",
    )
    expect_equal(
        "parent wraps then children",
        "- Parent that wraps\n  to next line\n  - Child 1\n  - Child 2",
        "- Parent that wraps to next line\n  - Child 1\n  - Child 2",
    )
    expect_equal(
        "nested numbered sub-item wraps",
        "1. First\n   a. Sub item wraps\n      to next line\n   b. Another\n2. Second",
        "1. First\n   a. Sub item wraps to next line\n   b. Another\n2. Second",
    )
    expect_equal(
        "three-level nesting",
        "- Top\n  - Mid\n    - Deep 1\n    - Deep 2\n  - Mid 2\n- Top 2",
        "- Top\n  - Mid\n    - Deep 1\n    - Deep 2\n  - Mid 2\n- Top 2",
    )


def test_markdown_structures_do_not_merge():
    expect_equal(
        "header boundary",
        "# Heading\nnext line",
        "# Heading\nnext line",
    )
    expect_equal(
        "blockquote boundary",
        "> quote\ncontinued",
        "quote\ncontinued",
    )
    expect_equal(
        "hrule boundary",
        "---\nnext",
        "---\nnext",
    )
    expect_equal(
        "spaced hrule boundary",
        "- - -\nnext",
        "- - -\nnext",
    )


def test_table_rows_preserved():
    expect_equal(
        "box table",
        """
          ┌──────────────┬───────┬────────────────────┐
          │     Date     │ From  │        Contains    │
          └──────────────┴───────┴────────────────────┘
        """,
        """
        ┌──────────────┬───────┬────────────────────┐
        │     Date     │ From  │        Contains    │
        └──────────────┴───────┴────────────────────┘
        """,
    )
    expect_equal_raw(
        "pipe rows without separator",
        "| a | b |\n| c | d |\n",
        "| a | b |\n| c | d |",
    )
    expect_equal_raw(
        "ascii plus table",
        "+---+---+\n| a | b |\n+---+---+\n",
        "+---+---+\n| a | b |\n+---+---+",
    )


def test_tabs_preserved():
    expect_equal_raw(
        "tabs",
        "- Item\n\t\tSubitem with tabs\n",
        "- Item\n\t\tSubitem with tabs",
    )


def test_single_wrapper_like_bullet_not_stripped():
    expect_equal_raw(
        "single bullet with continuation",
        "• Buy milk\n  tomorrow\n",
        "• Buy milk tomorrow",
    )


def test_unfenced_code_under_list_not_joined():
    expect_equal_raw(
        "unfenced code under list",
        "- Example:\n    x = 1\n    y = 2\n- Next\n",
        "- Example:\n    x = 1\n    y = 2\n- Next",
    )


def test_four_digit_ordered_list_context():
    expect_equal_raw(
        "4 digit ordered list",
        "1000. item\n1001. next\n",
        "1000. item\n1001. next",
    )
    expect_equal_raw(
        "single 4 digit sentence",
        "2026. was weird\ncontinued\n",
        "2026. was weird continued",
    )


def test_markdown_blockquote_draft_strips_markers_keeps_breaks():
    # Claude Code wraps drafts (emails etc.) in markdown blockquotes.
    text = "\n".join(
        [
            "Hier der Draft:",
            "",
            "> Dear AI Office Secretariat,",
            ">",
            "> I am transitioning out of my role at Apart Research and would like to transfer my seat in the Expert Forum on Frontier AI to my successor.",
            ">",
            "> Kind regards,",
            "> Jason",
            "",
            "Soll ich ihn als Gmail-Draft anlegen?",
        ]
    )
    expected = "\n".join(
        [
            "Hier der Draft:",
            "",
            "Dear AI Office Secretariat,",
            "",
            "I am transitioning out of my role at Apart Research and would like to transfer my seat in the Expert Forum on Frontier AI to my successor.",
            "",
            "Kind regards,",
            "Jason",
            "",
            "Soll ich ihn als Gmail-Draft anlegen?",
        ]
    )
    expect_equal_raw("markdown blockquote draft", text, expected)


def test_terminal_blockquote_copy_unwraps_and_keeps_signature():
    # Copying the rendered blockquote from the terminal yields a bar glyph
    # per wrapped line; wraps should join, paragraph breaks and short
    # intentional breaks (signature) should survive.
    text = "\n".join(
        [
            "│ Please direct all future Forum communications and invitations for Apart",
            "│ to him.",
            "│",
            "│ Separately, I would like to remain part of the Expert Forum in a",
            "│ personal capacity if possible: I will continue to work on frontier AI",
            "│ evaluations and would be glad to keep contributing, whether through the",
            "│ Forum meetings, written input, or targeted workshops.",
            "│",
            "│ Kind regards,",
            "│ Jason",
        ]
    )
    expected = "\n".join(
        [
            "Please direct all future Forum communications and invitations for Apart to him.",
            "",
            "Separately, I would like to remain part of the Expert Forum in a personal capacity if possible: I will continue to work on frontier AI evaluations and would be glad to keep contributing, whether through the Forum meetings, written input, or targeted workshops.",
            "",
            "Kind regards,",
            "Jason",
        ]
    )
    expect_equal_raw("terminal blockquote copy", text, expected)


def test_quote_bar_does_not_eat_box_tables():
    expect_equal_raw(
        "box table not treated as quote",
        "│     Date     │ From  │\n",
        "│     Date     │ From  │",
    )


def test_quoted_list_lines_not_joined():
    expect_equal_raw(
        "quoted list",
        "> - one\n> - two\n",
        "- one\n- two",
    )


def test_quoted_list_continuation_joins():
    expect_equal_raw(
        "quoted list continuation",
        "> - This is a long list item which is wrapped at a standard terminal width\n"
        ">   onto another line that belongs to the same item.\n"
        "> - second\n",
        "- This is a long list item which is wrapped at a standard terminal width onto another line that belongs to the same item.\n"
        "- second",
    )


def test_quoted_fenced_code_preserved():
    expect_equal_raw(
        "quoted fence",
        "> ```python\n"
        '> first = "abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz"\n'
        '> second = "abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz"\n'
        "> ```\n",
        "```python\n"
        'first = "abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz"\n'
        'second = "abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz"\n'
        "```",
    )


def test_quoted_fence_keeps_literal_quote_chars():
    expect_equal_raw(
        "quoted fence with literal >",
        "> ```sh\n> sort input.txt > output.txt\n> ```\n",
        "```sh\nsort input.txt > output.txt\n```",
    )


def test_quoted_table_row_loses_quote_marker_keeps_table():
    expect_equal_raw(
        "quoted table row",
        "> │ A │ B │\n",
        "│ A │ B │",
    )


def test_heavy_box_table_not_treated_as_quote():
    expect_equal_raw(
        "heavy box table",
        "┃ A ┃ B ┃\n",
        "┃ A ┃ B ┃",
    )


def test_long_outlier_line_does_not_block_reflow():
    text = "\n".join(
        [
            "> See https://example.com/some/extremely/long/link/that/never/wraps/because/urls/are/one/token/and/keep/going/forever/in/one/line",
            ">",
            "> This wrapped paragraph should still be joined back together even",
            "> though the quote contains one much longer unbroken line above,",
            "> because the wrap width is inferred per paragraph.",
        ]
    )
    expected = "\n".join(
        [
            "See https://example.com/some/extremely/long/link/that/never/wraps/because/urls/are/one/token/and/keep/going/forever/in/one/line",
            "",
            "This wrapped paragraph should still be joined back together even though the quote contains one much longer unbroken line above, because the wrap width is inferred per paragraph.",
        ]
    )
    expect_equal_raw("outlier line", text, expected)


def test_markdown_table_without_outer_pipes():
    expect_equal_raw(
        "no-edge markdown table",
        "a | b\n---|---\nc | d\n",
        "a | b\n---|---\nc | d",
    )
