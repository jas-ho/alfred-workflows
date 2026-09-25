# Workspace

`ns <name>` or `newspace <name>` creates a named Mission Control desktop, opens fresh windows, and returns to the original desktop. Command-Return stays in the new desktop. The default is browser, notes, terminal in three columns, with the terminal focused last. App minimum sizes can constrain the requested layout.

## CLI

`workspace` is the single public CLI for desktop navigation, naming, creation and closure. Run `workspace --help` or `workspace COMMAND --help` for options.

| Command                                  | Behavior                                                                     |
| ---------------------------------------- | ---------------------------------------------------------------------------- |
| `list`                                   | Fresh regular desktops with names, numbers, stable IDs and active ID         |
| `switch NAME\|NUMBER` / `switch --id ID` | Navigate and verify arrival; already-current is a successful no-op           |
| `rename NAME [--id ID]`                  | Rename current or specified desktop without switching; verify saved metadata |
| `back`                                   | Use observed desktop history; verify the transition                          |
| `create NAME`                            | Create a fresh desktop and configured windows, then return unless `--stay`   |
| `close [NAME\|NUMBER\|--id ID]`          | Preview current or specified desktop; `--yes` executes and waits             |
| `check`                                  | Read-only worker, desktop, close backend and installed-app checks            |
| `result OPERATION_ID`                    | Read latest recorded outcome; never repeat an action                         |

```sh
workspace list --json
workspace switch Research
workspace rename "Research" --id 123
workspace back
workspace create "Research" --directory ~/Code/project --stay
workspace create "Research" --url https://example.com --url https://example.org
workspace create "Research" --note research/project/README.md
workspace create "Research" --tmux-session existing-agent --json
workspace close Research --json          # preview only, exit 1
workspace close --id 123 --yes --json    # use the preview's stable ID
workspace check --json
workspace result 0123456789abcdef0123456789abcdef --json
```

Numeric selectors mean desktop order, not names or IDs. Names match case-insensitively: exact match first, then unique substring. Ambiguous matches fail; use an ID from `list` instead. Desktop IDs are opaque decimal strings; they are unrelated to hexadecimal operation IDs. IDs describe live desktops and must be refreshed after removal/reboot.

`close` always previews by default, including an empty desktop. `--yes` uses a fresh window inventory, requests normal closes and verifies desktop removal. A preview reserves neither window contents nor desktop order. Shared windows stay open; app save dialogs are never answered and applications are never force-quit. A blocking window is revealed for attention. Confirmed earlier closes remain closed. The `closed` count includes only windows verified gone, and `removal_verified` is true only after the desktop disappeared. Closing the active desktop uses Back, with a same-display neighbor fallback. Alfred `cs` keeps its existing GUI confirmation and immediate empty-desktop removal.

`--json` works before or after every subcommand. It writes one object to stdout, including usage errors. Human output is the default; human errors go to stderr. Help stays text and exits 0. Exit codes: **0** complete, **1** other outcomes, **2** invalid arguments. JSON always has this envelope:

```json
{
  "schema_version": 1,
  "operation": "close",
  "operation_id": "0123456789abcdef0123456789abcdef",
  "status": "complete",
  "data": { "space_id": "123", "closed": 3, "removal_verified": true },
  "error": null
}
```

Statuses are `complete`, `running`, `confirmation_required`, `blocked`, `cancelled`, `partial`, `failed`, and `uncertain`. Errors contain `code` and `message`. `list` data contains `desktops` (`id`, `number`, `name`) and `active`; array fields remain arrays when empty. `result` preserves the original operation and outcome, so reading a running result does not exit successfully. Acknowledgment alone is not completion. On timeout, retain the returned operation ID, inspect `result` and current desktops, and do not automatically repeat the mutation. A missing result does not prove no action happened.

`check` never opens test windows or triggers permission prompts. It reports Automation permissions and Obsidian CLI readiness as unchecked; those cannot be established by the local installed-app checks.

Name is the only required input. With the Ghostty opener, an exact case-insensitive name match attaches a running tmux session first, then searches the ordered `project_roots` below. A unique folder match creates a session named after that folder without a leading `YYYY-MM_` prefix, with the folder as its working directory. An existing undated session is attached instead; if none exists, an existing full dated folder-named session from an earlier version is reused without renaming it. Folder matching also ignores a leading `YYYY-MM_` prefix: `stockholm` matches `2026-03_stockholm`, but `stock` does not. No match creates a fresh home session such as `ws-research` (`-2`, `-3`, etc. on collision). Ambiguous matches also create a fresh home session and are explained in subtitles or CLI stderr. `--directory` or `--tmux-session` bypasses automatic linking; `--directory ~` explicitly requests a fresh home session. `--tmux-session` is attach-only and does not move or detach other clients. A project directory only affects a newly created session; attaching an existing session preserves its working state. Obsidian opens an empty pane unless an existing vault-relative note is specified. It never creates a note. URLs become tabs in the single new browser window.

Every `create` means a fresh desktop, even with the same name. Terminal linking can reuse a tmux session, but never reuses a desktop or retries an operation. The command returns a nonzero exit code for partial/uncertain outcomes and keeps successful work. JSON results include the operation ID, desktop ID, confirmed window IDs/PIDs, tmux session, failed stage, and return outcome. `result` reads the recorded result without repeating the operation. A timeout does not prove that nothing was created. Human-readable failures name the kept windows/session and provide a `workspace switch --id …` command; Alfred failures point to `sp`. Inspect the partial workspace before creating another one.

## Configuration

Copy `default.json` to `~/.config/workspace/default.json` and edit it, or use `--config path.json`. The app list controls both opening order and layout order; the last window receives focus. Layouts: `columns`, `main-stack` (first window left, remaining windows stacked right), or `none`. Override for one invocation with `--layout`.

`project_roots` is an ordered list of folder search tiers. The bundled personal recipe uses:

```json
"project_roots": [
  {"path": "~/Projects", "depth": 4},
  {"path": "~/Code", "depth": 1}
]
```

Depth is a maximum (1–16): every non-hidden folder at levels 1 through that limit is eligible, regardless of README or Git markers. The defaults search Projects through level 4 and Code through level 1, including symlinked repositories. Search continues inside matching folders so nested projects remain discoverable. Directory symlinks are searched like folders, even outside the root, within the same depth limit; ancestor cycles are skipped. Earlier versions searched only the exact configured depth; existing `depth` values now include shallower levels too. If using a local recipe copied from an earlier version, raise its Projects depth to 4 to include nested projects; local overrides are not rewritten automatically. Missing or empty `project_roots` disables folder lookup but keeps session matching. No Git or vault metadata is required. Hidden entries, files, missing roots and dangling symlinks are ignored. An unreadable directory stops inference with its path and an actionable error; it is not treated as no match. The first tier with matches wins; multiple different real paths in that tier are ambiguous and do not fall through. Same-target symlinks count once and use the canonical target's basename for session naming. Folder-derived names omit one leading date prefix and otherwise preserve case and spaces; tmux-incompatible dots/colons become underscores. Existing sessions are matched by name, not by their current directory: a running `offsite` session can be reused for a newer dated `offsite` folder. Even a full dated folder query reuses its undated session when present; use an explicit `--directory` when a fresh session in that particular folder is required. Multiple casefold-equal session names are ambiguous.

Inventory, creation and attachment consistently use tmux's standard default server, ignoring ambient `TMUX` and `TMUX_TMPDIR`. Subtitles are read-only previews; execution resolves afresh. A missing attachment target or failed lookup stops creation rather than silently choosing another target. Recipes without Ghostty skip terminal linking entirely. Linking changes neither browser nor Obsidian content.

An ordinary app can use its own menu command without adding application-specific code:

```json
{
  "layout": "columns",
  "apps": [
    {
      "app": "/System/Library/CoreServices/Finder.app",
      "menu": ["File", "New Finder Window"]
    },
    { "app": "/Applications/Ghostty.app", "opener": "ghostty" }
  ]
}
```

The default opener is `generic`, using File → New Window unless `menu` is specified. For an app that isn't running, it launches once and identifies the resulting window. Apps that restore several windows, open only a document picker, or cannot open a window in the background may need a dedicated helper. The operation stops with an explicit result when it cannot identify exactly one new window or verify its desktop. It does not move pre-existing windows or blindly repeat a creation command.

Specialized openers are `ghostty` (tmux), `chromium` (Edge/compatible scripting dictionary, URLs), and `obsidian` (requires `vault`). They provide content setup; the desktop worker handles identification, placement verification, layout, and return for every app. Use each app once; at most one of each specialized opener. Extending those helpers doesn't require changing desktop management.

## Installation

Requires macOS, Hammerspoon with Accessibility permission, the Doorplate app, and the configured apps. The default also requires tmux and Obsidian's CLI enabled. Obsidian's configured vault must be available. Hammerspoon needs Automation permission for Ghostty and Edge; macOS prompts on first use. Allow these prompts to finish setup.

Link `workspace.py` as `~/.local/bin/workspace`, link this workflow directory as `~/.local/share/workspace`, and create `~/.local/state/workspace` with mode 0700. Add this to Hammerspoon's init (already installed in Jason's tracked configuration):

```lua
local root = os.getenv("HOME") .. "/.local/share/workspace"
local state = os.getenv("HOME") .. "/.local/state/workspace"
WorkspaceCreate = dofile(root .. "/workspace.lua").start(root, state)
-- Chain this cleanup into any existing shutdown callback.
hs.shutdownCallback = function()
    WorkspaceCreate.stop()
    if SpaceClose then SpaceClose.stop() end
end
```

The close backend in `~/bin/hammerspoon/space-close.lua` must also be installed and wired to the existing window classifier/cache; it lives in the separate bin repository. Reload Hammerspoon, then run `workspace check`. Install the Alfred workflow normally or use the repository's development symlink. Hammerspoon and Doorplate need to start at login for this to work after reboot.

The CLI submits local JSON data to a Hammerspoon directory watcher. Hammerspoon executes GUI operations in the logged-in session; the caller need not have a working Hammerspoon IPC connection. Clients hold the mailbox lock until a matching per-operation acknowledgment, then release it while awaiting completion. Mutations are serialized; read-only requests can run during them. Requests expire if unacknowledged, and startup requests are not replayed. On orderly reload/shutdown, owned tasks and timers stop and interrupted operations record an uncertain outcome. Abrupt death can leave a running record; no automatic replay or rollback occurs. Results remain in `~/.local/state/workspace` for diagnosis. The worker coordinates its busy state with the existing close/prune operations in Jason's Hammerspoon configuration.

Setup briefly visits the new desktop. Success and ordinary failure both attempt to restore the original stable Space ID, unless `--stay` requests the new one. If you switch desktops during setup, it stops opening more windows and leaves you where you moved; results record `return_skipped: "desktop_changed"`. An app command already in progress may still complete, so inspect partial results before retrying. If Hammerspoon quits or the original desktop disappears, restoration cannot be guaranteed; partial work remains available for inspection.

## Agent boundary

Agents decide whether a task deserves its own workspace and supply the name, directory, URLs, note, and optional existing tmux session. The CLI performs only the requested setup. It resolves terminal links by name as described above; it does not launch an agent, synchronize project state, or manage the lifetime of tmux sessions. Use `workspace close --id ID` to inspect a target and add `--yes` when closure is intended; Alfred users can use `cs`. Closing windows does not manage tmux session lifetime.
