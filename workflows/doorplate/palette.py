#!/usr/bin/python3
"""Native Alfred workspace palette; filtering only reads workspace state."""

from __future__ import annotations

import json
import os
import subprocess
import sys


ERRORS = (
    OSError,
    ValueError,
    TypeError,
    KeyError,
    RuntimeError,
    ImportError,
    subprocess.SubprocessError,
)


def matches(query: str, text: str) -> bool:
    return all(word in text.casefold() for word in query.casefold().split())


def variables(screen: str, selected: str = "", root_query: str = "") -> dict:
    return {"ws_screen": screen, "ws_selected": selected, "ws_root_query": root_query}


def row(
    uid: str,
    title: str,
    subtitle: str,
    *,
    arg: str = "",
    target: str | None = None,
    selected: str = "",
    root_query: str = "",
    icon: str | None = None,
    valid: bool = True,
) -> dict:
    item = {
        "uid": "ws-" + uid,
        "title": title,
        "subtitle": subtitle,
        "arg": arg,
        "valid": valid,
    }
    if target is not None:
        item["variables"] = variables(target, selected, root_query)
    if icon:
        item["icon"] = {"path": icon}
    return item


def operation_row(
    uid: str,
    title: str,
    subtitle: str,
    action: str,
    *,
    icon: str | None = None,
    valid: bool = True,
    **payload,
) -> dict:
    return row(
        uid,
        title,
        subtitle,
        target="execute",
        icon=icon,
        valid=valid,
        arg=json.dumps({"action": action, **payload}, ensure_ascii=False),
    )


def back_row(root_query: str, selected: str = "", *, actions: bool = False) -> dict:
    return row(
        "back-actions" if actions else "back-root",
        "← Actions" if actions else "← Workspaces",
        "Cancel and return to desktop actions"
        if actions
        else "Return to workspace search",
        target="actions" if actions else "root",
        selected=selected if actions else "",
        root_query=root_query,
        arg="" if actions else root_query,
    )


def render(
    screen: str,
    query: str,
    selected: str = "",
    root_query: str = "",
    *,
    state: dict | None = None,
    apps: list[dict] | None = None,
    error: str | None = None,
) -> dict:
    """Render explicit screens from injected data, with no I/O or mutations."""
    if screen == "root":
        selected, root_query = "", query
    session = variables(screen, selected, root_query)
    back = back_row(root_query, selected, actions=screen == "rename")
    if error:
        items = [row("unavailable", "Workspace unavailable", error, valid=False)]
        if screen != "root":
            items.append(back_row(root_query))
        return {"skipknowledge": True, "variables": session, "items": items}

    state = state or {"desktops": [], "active": ""}
    items = []
    if screen == "root":
        numeric = query.strip().isdecimal()
        desktops = sorted(state["desktops"], key=lambda d: d["id"] != state["active"])
        for desktop in desktops:
            label = desktop["name"] or f"Desktop {desktop['number']}"
            if numeric:
                matched = desktop["number"] == int(query.strip())
            else:
                matched = matches(query, f"{desktop['number']} desktop {label}")
            if matched:
                current = (
                    "Current desktop · " if desktop["id"] == state["active"] else ""
                )
                items.append(
                    row(
                        "root-" + desktop["id"],
                        f"{desktop['number']} · {label}",
                        current + "Enter for actions",
                        target="actions",
                        selected=desktop["id"],
                        root_query=query,
                    )
                )
        choices = [
            (
                "new create workspace",
                row(
                    "root-create",
                    "New workspace…",
                    "Name a new desktop with configured app windows",
                    target="create",
                    root_query=query,
                    icon="create.png",
                ),
            ),
            (
                "previous back desktop",
                operation_row(
                    "root-previous",
                    "Previous desktop",
                    "Return to the previously visited desktop",
                    "back",
                ),
            ),
            (
                "help guide options",
                row(
                    "root-help",
                    "Help",
                    "Palette, fast keywords and advanced CLI options",
                    target="help",
                    root_query=query,
                ),
            ),
        ]
        if not numeric:
            items.extend(item for aliases, item in choices if matches(query, aliases))
        if not items:
            items.append(
                row(
                    "root-empty",
                    "No matching workspaces or actions",
                    "Try a desktop name, exact number, new, previous or help",
                    valid=False,
                )
            )
    elif screen in ("actions", "rename"):
        desktop = next((d for d in state["desktops"] if d["id"] == selected), None)
        if desktop is None:
            items = [
                row(
                    "missing",
                    "This desktop is no longer available",
                    "Return to Workspaces and choose a live desktop",
                    valid=False,
                ),
                back_row(root_query),
            ]
        else:
            label = desktop["name"] or f"Desktop {desktop['number']}"
            context = f"{desktop['number']} · {label}"
            if screen == "actions":
                choices = [
                    (
                        "switch open go",
                        operation_row(
                            "actions-switch-" + selected,
                            "Switch",
                            context + " · Go to this desktop",
                            "switch",
                            id=selected,
                        ),
                    ),
                    (
                        "rename name",
                        row(
                            "actions-rename-" + selected,
                            "Rename…",
                            context + " · Enter a replacement name",
                            target="rename",
                            selected=selected,
                            root_query=root_query,
                            icon="DP-RENAME.png",
                        ),
                    ),
                    (
                        "close remove",
                        operation_row(
                            "actions-close-" + selected,
                            "Close…",
                            context
                            + " · Empty desktops close immediately; otherwise review normal window closes",
                            "close",
                            id=selected,
                            icon="DP-CLOSE.png",
                        ),
                    ),
                ]
                items = [item for aliases, item in choices if matches(query, aliases)]
                items.append(back)
            else:
                name = query.strip()
                items = [
                    operation_row(
                        "rename-apply-" + selected,
                        f"Rename to ‘{name}’" if name else "Type a replacement name",
                        context + " · Return applies this name",
                        "rename",
                        id=selected,
                        name=name,
                        valid=bool(name),
                        icon="DP-RENAME.png",
                    ),
                    back,
                ]
    elif screen == "create":
        name = query.strip()
        summary = " · ".join(app["name"] for app in (apps or []))
        for stay, title in [
            (False, "Create and return here"),
            (True, "Create and stay there"),
        ]:
            items.append(
                operation_row(
                    "create-stay" if stay else "create-return",
                    title,
                    (f"‘{name}’ · " if name else "Type a workspace name · ") + summary,
                    "create",
                    name=name,
                    stay=stay,
                    valid=bool(name),
                    icon="create.png",
                )
            )
        items.append(back)
    elif screen == "help":
        guidance = [
            (
                "Browse workspaces",
                "Search names or exact desktop numbers; Return opens actions",
            ),
            (
                "Fast keywords",
                "sp switches · sn renames current · cs closes · ns creates",
            ),
            (
                "Create defaults",
                "Configured apps · home directory · new browser tab · blank notes · fresh tmux session",
            ),
            (
                "Advanced creation",
                "Terminal: workspace create --help · directory, URLs, note and existing tmux session",
            ),
            (
                "Navigation and closing",
                "Back rows return; Escape dismisses · Close preserves app save prompts",
            ),
        ]
        items = [
            row(f"help-{i}", title, subtitle, valid=False)
            for i, (title, subtitle) in enumerate(guidance)
        ]
        items.append(back)
    else:
        items = [
            row(
                "unknown",
                "Reopen the workspace palette",
                "Type ws to start a fresh search",
                valid=False,
            ),
            back_row(root_query),
        ]
    return {"skipknowledge": True, "variables": session, "items": items}


def main(root: bool = False) -> None:
    query = sys.argv[1] if len(sys.argv) > 1 else ""
    screen = "root" if root else os.environ.get("ws_screen", "root")
    selected = os.environ.get("ws_selected", "")
    root_query = os.environ.get("ws_root_query", "")
    state, apps, error = None, None, None
    try:
        import doorplate as dp

        if screen in ("root", "actions", "rename"):
            result = dp.workspace.envelope(
                dp.workspace.send({"operation": "list"}, timeout=5), "list"
            )
            if result["status"] != "complete":
                detail = result.get("error") or {}
                raise RuntimeError(
                    detail.get(
                        "message", "Workspace worker did not return a desktop list"
                    )
                )
            state = result["data"]
        elif screen == "create":
            apps = dp.workspace.recipe()
    except ERRORS as failure:
        error = f"{failure} · Check Workspace installation and run workspace check in Terminal"
    print(
        json.dumps(
            render(
                screen, query, selected, root_query, state=state, apps=apps, error=error
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
