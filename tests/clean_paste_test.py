import plistlib
from pathlib import Path
import zipfile
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "Clean Paste.alfredworkflow"


def load_clean():
    """Load the workflow's clean() function from the packaged plist."""
    with zipfile.ZipFile(WORKFLOW) as zf:
        plist = plistlib.loads(zf.read("info.plist"))
    script = plist["objects"][1]["config"]["script"]
    lines = []
    for line in script.splitlines():
        if line.startswith("text = subprocess.run"):
            break  # drop runtime invocation
        lines.append(line)
    namespace = {}
    exec("\n".join(lines), namespace)
    return namespace["clean"]


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
        Yes - all the emails are part of one thread. They all have subject "Re: Follow-up on Apart Research application" (replies to Kasey's original
        email).

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


def run_all():
    tests = [
        test_claude_bullet_and_box_table,
        test_codex_bullet_with_wrapped_sub_bullets,
        test_fenced_code_block_is_preserved,
        test_indented_code_under_bullet_keeps_indent,
        test_plain_wrapped_paragraph_unwraps,
        test_ascii_table_alone_keeps_shape,
        test_tabs_preserved,
    ]
    for fn in tests:
        fn()


if __name__ == "__main__":
    run_all()
