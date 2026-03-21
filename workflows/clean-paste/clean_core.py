#!/usr/bin/env python3
import re

_WRAPPER_MARKERS = "•⏺"
_BULLETS = "-*+•◦▪▸→▶►➤·⏺"
_WHITESPACE = " \t\u00a0"
_SPACES_ONLY = " \u00a0"
_BOX = "┌┬┐└┴┘│─"

_FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
_HEADING = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+\S")
_HRULE = re.compile(
    r"^[ \t]{0,3}(?:(?:-[ \t]*){3,}|(?:_[ \t]*){3,}|(?:\*[ \t]*){3,})$"
)
_BLOCKQUOTE = re.compile(r"^[ \t]{0,3}>")
_UNORDERED = re.compile(rf"^([ \t]*)([{re.escape(_BULLETS)}])[ \t]+(.*)$")
_ORDERED = re.compile(r"^([ \t]*)(\d{1,3}[.)])[ \t]+(.*)$")
_ORDERED_ANY = re.compile(r"^([ \t]*)(\d+[.)])[ \t]+(.*)$")
_ALPHA = re.compile(r"^([ \t]*)([a-zA-Z][.)])[ \t]+(.*)$")
_WRAPPER = re.compile(rf"^([ \t]*)([{re.escape(_WRAPPER_MARKERS)}])[ \t]+(.*)$")
_MD_TABLE_SEP_CELL = re.compile(r"^:?-{3,}:?$")
_CODE_START = re.compile(
    r"^(?:def\b|class\b|return\b|if\b|elif\b|else:|for\b|while\b|try:|except\b|with\b|from\b|import\b|const\b|let\b|var\b|function\b)"
)
_CODE_ASSIGN = re.compile(r"^[A-Za-z_][\w.\[\]]*\s*[:+\-*/%]?=\s*\S")


def _leading_indent(line):
    i = 0
    while i < len(line) and line[i] in _WHITESPACE:
        i += 1
    return i


def _remove_indent(line, amount):
    i = 0
    while i < len(line) and i < amount and line[i] in _WHITESPACE:
        i += 1
    return line[i:]


def _common_dedent(lines):
    indents = []
    for line in lines:
        if not line.strip():
            continue
        if line.startswith("\t"):
            continue
        i = 0
        while i < len(line) and line[i] in _SPACES_ONLY:
            i += 1
        indents.append(i)
    trim = min(indents) if indents else 0
    if trim == 0:
        return lines
    return [_remove_indent(line, trim) if line.strip() else line for line in lines]


def _is_fence(line):
    return bool(_FENCE.match(line))


def _is_heading(line):
    return bool(_HEADING.match(line))


def _is_hrule(line):
    return bool(_HRULE.match(line))


def _is_blockquote(line):
    return bool(_BLOCKQUOTE.match(line))


def _is_box_line(line):
    return sum(1 for ch in line if ch in _BOX) >= 2


def _is_table_line(line):
    s = line.strip()
    if _is_box_line(s):
        return True
    if s.count("|") >= 2 and (s.startswith("|") or s.endswith("|")):
        return True
    if s.count("+") >= 2 and "-" in s:
        return True
    return False


def _list_indent(line):
    for pattern in (_UNORDERED, _ORDERED, _ALPHA):
        m = pattern.match(line)
        if m:
            return _leading_indent(m.group(1))
    return None


def _is_list_line(line):
    return _list_indent(line) is not None


def _prev_nonblank(lines, idx):
    i = idx - 1
    while i >= 0:
        line = lines[i].rstrip()
        if line.strip():
            return line
        i -= 1
    return None


def _next_nonblank(lines, idx):
    i = idx + 1
    while i < len(lines):
        line = lines[i].rstrip()
        if line.strip():
            return line
        i += 1
    return None


def _is_markdown_separator_row(line):
    s = line.strip()
    if "|" not in s:
        return False
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    parts = [part.strip() for part in s.split("|")]
    if len(parts) < 2:
        return False
    return all(_MD_TABLE_SEP_CELL.fullmatch(part) for part in parts)


def _is_markdown_table_line(lines, idx):
    line = lines[idx].rstrip()
    if "|" not in line:
        return False
    if _is_markdown_separator_row(line):
        return True
    prev_line = _prev_nonblank(lines, idx)
    next_line = _next_nonblank(lines, idx)
    return (
        (prev_line is not None and _is_markdown_separator_row(prev_line))
        or (next_line is not None and _is_markdown_separator_row(next_line))
    )


def _list_indent_in_context(lines, idx):
    line = lines[idx].rstrip()
    m = _UNORDERED.match(line) or _ALPHA.match(line)
    if m:
        return _leading_indent(m.group(1))
    m = _ORDERED.match(line)
    if m:
        return _leading_indent(m.group(1))
    m = _ORDERED_ANY.match(line)
    if not m:
        return None
    indent = _leading_indent(m.group(1))
    prev_line = _prev_nonblank(lines, idx)
    next_line = _next_nonblank(lines, idx)
    prev_match = prev_line is not None and _ORDERED_ANY.match(prev_line)
    next_match = next_line is not None and _ORDERED_ANY.match(next_line)
    if prev_match and _leading_indent(_ORDERED_ANY.match(prev_line).group(1)) == indent:
        return indent
    if next_match and _leading_indent(_ORDERED_ANY.match(next_line).group(1)) == indent:
        return indent
    return None


def _looks_like_code(line):
    s = line.strip()
    if not s:
        return False
    if _is_fence(s):
        return True
    if _CODE_START.match(s):
        return True
    if _CODE_ASSIGN.match(s):
        return True
    if s.endswith(("{", "}", ";")):
        return True
    if "::" in s:
        return True
    return False


def _strip_single_wrapper_marker(lines):
    first_idx = None
    for i, line in enumerate(lines):
        if line.strip():
            first_idx = i
            break
    if first_idx is None:
        return lines

    m = _WRAPPER.match(lines[first_idx])
    if not m:
        return lines

    base_indent = _leading_indent(m.group(1))
    followers = [line for line in lines[first_idx + 1 :] if line.strip()]
    if not followers:
        return lines

    min_indent = min(_leading_indent(line) for line in followers)
    if min_indent <= base_indent:
        return lines

    if any(_is_list_line(line) and _leading_indent(line) <= base_indent for line in followers):
        return lines

    saw_blank = any(not line.strip() for line in lines[first_idx + 1 :])
    indented_children = [
        line for line in lines[first_idx + 1 :] if line.strip() and _leading_indent(line) > base_indent
    ]
    indented_structural = any(
        _is_list_line(line)
        or _is_blockquote(line)
        or _is_fence(line)
        or _is_table_line(line)
        or _is_heading(line)
        or _is_hrule(line)
        for line in indented_children
    )
    if not (saw_blank and (indented_structural or len(indented_children) >= 2)):
        return lines

    out = list(lines)
    out[first_idx] = m.group(1) + m.group(3)
    shift = min_indent - base_indent
    for i in range(first_idx + 1, len(out)):
        if out[i].strip():
            out[i] = _remove_indent(out[i], shift)
    return out


def clean(text):
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = _common_dedent(lines)
    lines = _strip_single_wrapper_marker(lines)

    result = []
    paragraph = []
    list_line = None
    list_indent = 0
    list_had_wrap = False
    in_fence = False
    in_code = False
    code_indent = 0

    def flush_paragraph():
        if paragraph:
            result.append(" ".join(paragraph))
            paragraph.clear()

    def flush_list():
        nonlocal list_line, list_had_wrap
        if list_line is not None:
            result.append(list_line)
            list_line = None
            list_had_wrap = False

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        indent = _leading_indent(line)

        if in_fence:
            result.append(line)
            if _is_fence(line):
                in_fence = False
            i += 1
            continue

        if in_code:
            if line == "":
                result.append("")
                i += 1
                continue
            if line.startswith("\t") or indent >= code_indent:
                result.append(line)
                i += 1
                continue
            in_code = False
            continue

        if line == "":
            flush_paragraph()
            flush_list()
            result.append("")
            i += 1
            continue

        if _is_fence(line):
            flush_paragraph()
            flush_list()
            result.append(line)
            in_fence = True
            i += 1
            continue

        if (
            _is_heading(line)
            or _is_hrule(line)
            or _is_blockquote(line)
            or _is_table_line(line)
            or _is_markdown_table_line(lines, i)
        ):
            flush_paragraph()
            flush_list()
            result.append(line)
            i += 1
            continue

        next_list_indent = _list_indent_in_context(lines, i)
        if next_list_indent is not None:
            flush_paragraph()
            flush_list()
            list_line = line
            list_indent = next_list_indent
            list_had_wrap = False
            i += 1
            continue

        if list_line is not None:
            if line.startswith("\t"):
                flush_list()
                result.append(line)
                in_code = True
                code_indent = indent if not line.startswith("\t") else list_indent + 4
                i += 1
                continue
            if indent >= list_indent + 4:
                if list_had_wrap:
                    list_line += " " + line.strip()
                    i += 1
                    continue
                parent_colon = list_line.rstrip().endswith(":")
                flush_list()
                result.append(line)
                in_code = parent_colon or _looks_like_code(line)
                code_indent = indent
                i += 1
                continue
            if indent >= list_indent:
                list_line += " " + line.strip()
                list_had_wrap = True
                i += 1
                continue
            flush_list()

        if line.startswith("\t") or indent >= 4:
            flush_paragraph()
            result.append(line)
            in_code = True
            code_indent = indent if not line.startswith("\t") else 4
            i += 1
            continue

        paragraph.append(line.strip())
        i += 1

    flush_paragraph()
    flush_list()

    out = []
    for line in result:
        if line == "":
            if out and out[-1] != "":
                out.append("")
            continue
        out.append(line)
    while out and out[-1] == "":
        out.pop()

    return "\n".join(out)
