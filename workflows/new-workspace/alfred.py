#!/usr/bin/python3
"""Private Alfred adapter; public commands live in workspace.py."""

from __future__ import annotations

import json
import sys

import workspace


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "filter":
        print(
            json.dumps(
                workspace.filter_items(argv[1] if len(argv) > 1 else ""),
                ensure_ascii=False,
            )
        )
        return 0
    try:
        args = workspace.parser().parse_args(argv)
        request = workspace.operation_request(args)
        request["notify"] = True
        if args.command == "close":
            request.update(execute=True, confirm=True)
        result = workspace.send(request)
        if result["status"] != "complete":
            print(workspace.failure_summary(result, compact=True))
        return 0 if result["status"] == "complete" else 1
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        print(str(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
