#!/usr/bin/env python3
import re
import subprocess

_BULLETS = "-*•◦▪▸→▶►➤·⏺"
_WHITESPACE = " \t\u00a0"
_NUM = re.compile(r"^\d+[.)]\s")
_ALPHA = re.compile(r"^[a-zA-Z][.)]\s")
_HEADER = re.compile(r"^#{1,6}\s")
_HRULE = re.compile(r"^[-*_]{3,}$")
_BOX = "┌┬┐└┴┘│─"
_FENCE = re.compile(r"^[`~]{3}")

def is_structural(line):
    s = line.lstrip()
    if not s: return False
    if s[0] in _BULLETS and len(s) > 1 and s[1] in _WHITESPACE: return True
    if s[0] == ">": return True
    if _NUM.match(s) or _ALPHA.match(s): return True
    if _HEADER.match(s): return True
    if _HRULE.match(s): return True
    return False

def is_box_line(line):
    return sum(1 for ch in line if ch in _BOX) >= 2

def is_ascii_table_line(line):
    has_pipes = line.count("|") >= 2 and "-" in line
    has_plus = line.count("+") >= 2 and "-" in line
    return has_pipes or has_plus

def is_indented(line):
    return line and line[0] in _WHITESPACE

def is_tabbed(line):
    return line.startswith("\t")

def smart_dedent(text):
    lines = text.splitlines()
    # Count structural lines at indent 0 to distinguish a single container
    # (e.g. ⏺ wrapper) from multiple peers (e.g. numbered list items)
    structural_at_zero = sum(1 for l in lines if l.strip() and
        len(l) - len(l.lstrip(_WHITESPACE)) == 0 and is_structural(l))
    skip_structural_zero = structural_at_zero == 1
    indents = []
    in_fence = False
    prev_structural = False
    code_block_indent = None
    for line in lines:
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not line.strip():
            prev_structural = False
            code_block_indent = None
            continue
        if is_tabbed(line):
            continue
        indent_len = len(line) - len(line.lstrip(_WHITESPACE))
        if indent_len == 0 and is_structural(line) and skip_structural_zero:
            prev_structural = True
            continue
        if prev_structural and indent_len >= 4:
            code_block_indent = indent_len
            prev_structural = False
            continue
        if code_block_indent is not None and indent_len >= code_block_indent:
            continue
        if code_block_indent is not None and indent_len < code_block_indent:
            code_block_indent = None
        prev_structural = False
        indents.append(indent_len)
    trim = min(indents) if indents else 0
    if trim == 0:
        return text
    trimmed = []
    in_fence = False
    prev_structural = False
    code_block_indent = None
    for line in lines:
        if _FENCE.match(line):
            in_fence = not in_fence
            trimmed.append(line)
            continue
        if in_fence:
            trimmed.append(line)
            continue
        if is_tabbed(line):
            trimmed.append(line)
            continue
        indent_len = len(line) - len(line.lstrip(_WHITESPACE))
        if indent_len == 0 and is_structural(line) and skip_structural_zero:
            prev_structural = True
        elif prev_structural and indent_len >= 4 and code_block_indent is None:
            code_block_indent = indent_len
            prev_structural = False
        else:
            prev_structural = False
        if code_block_indent is not None and indent_len >= code_block_indent:
            trimmed.append(line)
            continue
        if code_block_indent is not None and indent_len < code_block_indent:
            code_block_indent = None
        if trim and indent_len >= trim:
            trimmed.append(line[trim:])
        else:
            trimmed.append(line)
    return "\n".join(trimmed)

def strip_leading_marker(lines):
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        m = re.match(r"^[ \t]*([\-\*•◦▪▸→▶►➤·⏺])\s+(.*)$", line)
        if m:
            lines[i] = m.group(2)
        return lines
    return lines

def clean(text):
    lines = smart_dedent(text).splitlines()
    result, current = [], []
    in_fence = False
    structural_indent = 0
    prev_structural = False
    code_block_indent = None
    def flush():
        if current: result.append(" ".join(current)); current.clear()
    for line in lines:
        s = line.rstrip()
        if _FENCE.match(s):
            flush(); result.append(s); in_fence = not in_fence; continue
        if in_fence:
            flush(); result.append(s); continue
        if is_box_line(s) or is_ascii_table_line(s):
            flush(); result.append(s); continue
        if not s:
            flush(); result.append("")
            prev_structural = False; code_block_indent = None; continue
        if is_structural(s):
            flush()
            current.append(s)
            structural_indent = len(s) - len(s.lstrip())
            prev_structural = True; code_block_indent = None
        elif is_indented(s):
            if is_tabbed(s):
                flush(); result.append(s)
                prev_structural = False; code_block_indent = None; continue
            indent_len = len(s) - len(s.lstrip())
            if code_block_indent is not None and indent_len >= code_block_indent:
                flush(); result.append(s)
            elif prev_structural and (indent_len - structural_indent) >= 4:
                code_block_indent = indent_len
                prev_structural = False
                flush(); result.append(s)
            else:
                prev_structural = False; code_block_indent = None
                current.append(s.strip())
        else:
            prev_structural = False; code_block_indent = None
            current.append(s)
    flush()
    out, prev_blank = [], False
    for line in result:
        if line == "":
            if not prev_blank and out: out.append(line)
            prev_blank = True
        else:
            out.append(line); prev_blank = False
    while out and out[-1] == "":
        out.pop()
    out = strip_leading_marker(out)
    return "\n".join(out)

def main():
    text = subprocess.run(["pbpaste"], capture_output=True, text=True, check=False).stdout
    print(clean(text))


if __name__ == "__main__":
    main()
