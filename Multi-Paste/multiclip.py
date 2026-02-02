#!/usr/bin/env python3
import argparse
import os
import shutil
import sqlite3
import subprocess
import sys
from typing import List, Tuple

ALFRED_DB = os.path.expanduser(
    "~/Library/Application Support/Alfred/Databases/clipboard.alfdb"
)
RESULT_FILE = "/tmp/mp-result"
SUCCESS_FILE = "/tmp/mp-success"
DEFAULT_LIMIT = 100
MAX_DISPLAY_LEN = 80
PREVIEW_MAX_LINES = 200


def _fail(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    sys.exit(code)


def _check_deps() -> None:
    if shutil.which("fzf") is None:
        _fail("Error: fzf not found in PATH", 1)


def _connect_db() -> sqlite3.Connection:
    if not os.path.isfile(ALFRED_DB):
        _fail(f"Error: Alfred clipboard database not found at {ALFRED_DB}", 1)
    conn = sqlite3.connect(ALFRED_DB, timeout=2.0)
    conn.execute("PRAGMA busy_timeout = 2000")
    return conn


def _load_rows(limit: int) -> List[Tuple[int, str]]:
    conn = _connect_db()
    try:
        cur = conn.execute(
            """
            SELECT rowid, item
            FROM clipboard
            WHERE dataType = 0
              AND item IS NOT NULL
              AND item != ''
            ORDER BY ts DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = [(int(rowid), item) for rowid, item in cur.fetchall() if item]
    finally:
        conn.close()
    return rows


def _display_line(item: str) -> Tuple[str, int, bool]:
    lines = item.splitlines()
    line_count = len(lines) if lines else 1
    first_line = lines[0] if lines else ""
    first_line = first_line.replace("\t", " ")
    truncated = False
    if len(first_line) > MAX_DISPLAY_LEN:
        first_line = first_line[:MAX_DISPLAY_LEN]
        truncated = True
    return first_line, line_count, truncated


def _write_fzf_input(rows: List[Tuple[int, str]]) -> bytes:
    parts = []
    for rowid, item in rows:
        first_line, line_count, truncated = _display_line(item)
        if line_count > 1:
            first_line = f"{first_line}  [+{line_count - 1} lines]"
        elif truncated:
            first_line = f"{first_line}..."
        record = f"{rowid}\t{first_line}"
        parts.append(record.encode("utf-8", errors="replace") + b"\0")
    return b"".join(parts)


def _run_fzf_select(rows: List[Tuple[int, str]]) -> List[int]:
    fzf_cmd = [
        "fzf",
        "--multi",
        "--read0",
        "--print0",
        "--with-nth=2..",
        "--delimiter=\t",
        "--preview",
        f"{sys.executable} {os.path.abspath(__file__)} --preview {{1}}",
        "--preview-window=right:50%:wrap",
        "--header=TAB=select  Ctrl-A=all  Ctrl-D=none  Enter=confirm",
        "--bind=ctrl-a:select-all,ctrl-d:deselect-all",
        "--reverse",
        "--height=100%",
    ]

    proc = subprocess.Popen(
        fzf_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None

    input_bytes = _write_fzf_input(rows)
    out, _ = proc.communicate(input=input_bytes)

    if proc.returncode != 0:
        sys.exit(130)

    selected = [s for s in out.split(b"\0") if s]
    if not selected:
        sys.exit(130)

    rowids: List[int] = []
    for entry in selected:
        try:
            decoded = entry.decode("utf-8", errors="replace")
            rowid_str = decoded.split("\t", 1)[0]
            rowids.append(int(rowid_str))
        except (ValueError, IndexError):
            continue

    if not rowids:
        sys.exit(130)

    return rowids


def _run_fzf_format() -> str:
    options = [
        "Dash list",
        "Numbered list",
        "Bullet points",
        "Comma separated",
        "Plain (newlines)",
    ]
    proc = subprocess.run(
        [
            "fzf",
            "--header=Select format:",
            "--height=10",
            "--reverse",
            "--no-multi",
        ],
        input="\n".join(options).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=None,
        check=False,
    )

    if proc.returncode != 0:
        sys.exit(130)

    choice = proc.stdout.decode("utf-8", errors="replace").strip()
    if not choice:
        sys.exit(130)
    return choice


def _fetch_items_by_rowid(rowids: List[int]) -> List[str]:
    conn = _connect_db()
    items_by_id = {}
    try:
        cur = conn.execute(
            "SELECT rowid, item FROM clipboard WHERE rowid IN (%s)"
            % ",".join("?" for _ in rowids),
            tuple(rowids),
        )
        for rowid, item in cur.fetchall():
            if item is not None:
                items_by_id[int(rowid)] = item
    finally:
        conn.close()

    # Preserve input order
    return [items_by_id[rid] for rid in rowids if rid in items_by_id]


def _trim_blank_lines(items: List[str]) -> List[str]:
    # Remove leading/trailing blank lines while preserving indentation.
    return [i.strip("\n") for i in items]


_def_trim_for_lists = {
    "Dash list",
    "Numbered list",
    "Bullet points",
    "Comma separated",
    "Plain (newlines)",
}


def _format_items(fmt: str, items: List[str]) -> str:
    if fmt in _def_trim_for_lists:
        items = _trim_blank_lines(items)
    if fmt == "Dash list":
        return "\n".join(f"- {i}" for i in items)
    if fmt == "Numbered list":
        return "\n".join(f"{n}. {i}" for n, i in enumerate(items, 1))
    if fmt == "Bullet points":
        return "\n".join(f"• {i}" for i in items)
    if fmt == "Comma separated":
        return ", ".join(items)
    if fmt == "Plain (newlines)":
        return "\n".join(items)
    return "\n".join(items)


def _preview(rowid: int) -> None:
    conn = _connect_db()
    try:
        cur = conn.execute(
            "SELECT item FROM clipboard WHERE rowid = ?",
            (rowid,),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if not row or row[0] is None:
        return

    item = row[0]
    lines = item.splitlines()
    if not lines:
        return

    if len(lines) > PREVIEW_MAX_LINES:
        output = "\n".join(lines[:PREVIEW_MAX_LINES])
        output += "\n... [preview truncated]"
    else:
        output = "\n".join(lines)

    sys.stdout.write(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", type=int, default=None)
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args()

    if args.version:
        print("multiclip 2.0")
        return

    if args.preview is not None:
        _preview(args.preview)
        return

    _check_deps()

    limit = int(os.environ.get("MP_LIMIT", DEFAULT_LIMIT))
    rows = _load_rows(limit)
    if not rows:
        _fail("No text clipboard items found", 1)

    rowids = _run_fzf_select(rows)
    if not rowids:
        sys.exit(130)

    fmt = _run_fzf_format()
    items = _fetch_items_by_rowid(rowids)
    if not items:
        sys.exit(130)

    output = _format_items(fmt, items)

    with open(RESULT_FILE, "w", encoding="utf-8") as handle:
        handle.write(output)

    with open(SUCCESS_FILE, "w", encoding="utf-8") as handle:
        handle.write("ok")

    print(f"✓ Copied {len(items)} item(s) as {fmt}", file=sys.stderr)


if __name__ == "__main__":
    main()
