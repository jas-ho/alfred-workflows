#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
import tempfile
from typing import List, Optional

DEFAULT_DELAY_SEC = 0.25


def _fail(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    sys.exit(code)


def _get_clipboard() -> str:
    try:
        return subprocess.check_output(["pbpaste"], text=True)
    except Exception as exc:
        _fail(f"Error reading clipboard: {exc}", 1)
    return ""


def _detect_items(text: str) -> List[str]:
    lines = text.splitlines()

    dash_re = re.compile(r"^\s*[-–—]\s+(.*)$")
    bullet_re = re.compile(r"^\s*[•\u2022]\s+(.*)$")
    num_re = re.compile(r"^\s*\d+[\.)]\s+(.*)$")

    def match_prefix(line: str) -> Optional[str]:
        for regex in (dash_re, bullet_re, num_re):
            m = regex.match(line)
            if m:
                return m.group(1)
        return None

    matched = 0
    nonempty = 0
    for line in lines:
        raw = line.rstrip()
        if not raw:
            continue
        nonempty += 1
        if match_prefix(raw) is not None:
            matched += 1

    list_mode = matched >= 2 or (matched >= 1 and nonempty >= 3)

    items: List[str] = []
    current: List[str] = []

    for line in lines:
        raw = line.rstrip()
        if not raw:
            continue

        if list_mode:
            content = match_prefix(raw)
            if content is not None:
                if current:
                    items.append("\n".join(current))
                    current = []
                current.append(content)
            else:
                if current:
                    current.append(raw)
                else:
                    items.append(raw)
        else:
            items.append(raw)

    if current:
        items.append("\n".join(current))

    return [i for i in (item.strip() for item in items) if i]


def _apply_output_format(fmt: str, items: List[str]) -> List[str]:
    if fmt == "Plain (newlines)":
        return items
    if fmt == "Dash list":
        return [f"- {i}" for i in items]
    if fmt == "Bullet points":
        return [f"• {i}" for i in items]
    if fmt == "Numbered list":
        return [f"{n}. {i}" for n, i in enumerate(items, 1)]
    return items


def _run_applescript(items_file: str, delay_sec: float) -> str:
    script = r'''
    on run argv
        set itemsFile to item 1 of argv
        set delaySec to (item 2 of argv) as number

        tell application "System Events"
            set frontAppID to bundle identifier of first application process whose frontmost is true
        end tell

        set itemsText to (read POSIX file itemsFile as "utf8")
        set oldDelims to AppleScript's text item delimiters
        set AppleScript's text item delimiters to (character id 31)
        set itemsList to text items of itemsText
        set AppleScript's text item delimiters to oldDelims

        -- Preserve clipboard if possible
        set savedClipboard to ""
        try
            set savedClipboard to the clipboard as text
        end try

        delay 0.2

        repeat with itemText in itemsList
            if itemText is not "" then
                tell application "System Events"
                    set currentID to bundle identifier of first application process whose frontmost is true
                end tell
                if currentID is not frontAppID then
                    if savedClipboard is not "" then
                        set the clipboard to savedClipboard
                    end if
                    return "FOCUS_CHANGED"
                end if

                set the clipboard to itemText
                tell application "System Events"
                    keystroke "v" using {command down}
                    delay 0.05
                    keystroke return
                end tell
                delay delaySec
            end if
        end repeat
        delay 0.15
        if savedClipboard is not "" then
            set the clipboard to savedClipboard
        end if

        return "OK"
    end run
    '''
    proc = subprocess.run(
        ["osascript", "-e", script, items_file, str(delay_sec)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        _fail(proc.stderr.strip() or "AppleScript failed", 1)
    return proc.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", required=True)
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SEC)
    args = parser.parse_args()

    text = _get_clipboard()
    if not text.strip():
        _fail("Clipboard is empty", 0)

    items = _detect_items(text)
    if not items:
        _fail("No items found after parsing", 0)

    items = _apply_output_format(args.format, items)

    fd, path = tempfile.mkstemp(prefix="multisend-", suffix=".txt")
    os.close(fd)
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\x1f".join(items))
        result = _run_applescript(path, args.delay)
        if result == "FOCUS_CHANGED":
            print("Focus changed; aborted.", file=sys.stderr)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


if __name__ == "__main__":
    main()
