#!/usr/bin/python3
"""The palette's sole mutation entry point; submit each selection once."""

from __future__ import annotations

import json
import sys

from palette import ERRORS


def perform(payload: dict) -> str:
    import doorplate as dp

    action = payload["action"]
    if action != "create":
        return dp.perform_action(payload)
    # Parse explicit argv, with -- protecting names that resemble CLI options.
    argv = (
        ["create"] + (["--stay"] if payload["stay"] else []) + ["--", payload["name"]]
    )
    request = dp.workspace.operation_request(dp.workspace.parser().parse_args(argv))
    result = dp.workspace.send(request)
    if result["status"] != "complete":
        message = dp.workspace.failure_summary(result, compact=True)
        if result.get("id"):
            message += "\nDetails: workspace result " + result["id"]
        return message
    return "Created workspace ‘" + request["name"] + "’"


def main() -> None:
    try:
        message = perform(json.loads(sys.argv[1] if len(sys.argv) > 1 else "{}"))
    except ERRORS as error:
        message = "Workspace: " + str(error)
    if message:
        print(message)


if __name__ == "__main__":
    main()
