# New Workspace

`ns <name>` or `newspace <name>` creates a named Mission Control desktop, opens fresh windows, and returns to the original desktop. Command-Return stays in the new desktop. The default is browser, notes, terminal in three columns, with the terminal focused last. App minimum sizes can constrain the requested layout.

## CLI

```sh
workspace create "Research"
workspace create "Research" --directory ~/Code/project --stay
workspace create "Research" --url https://example.com --url https://example.org
workspace create "Research" --note research/project/README.md
workspace create "Research" --tmux-session existing-agent --json
workspace check
workspace result <operation-id>
```

Name is the only required input. The terminal defaults to home and a unique new tmux session. `--tmux-session` attaches an existing session without moving or detaching its other clients. A project directory only affects a newly created session; attaching an existing session preserves its working state. Obsidian opens an empty pane unless an existing vault-relative note is specified. It never creates a note. URLs become tabs in the single new browser window.

Every `create` means a fresh desktop, even with the same name. There is no implicit reuse or retry. The command returns a nonzero exit code for partial/uncertain outcomes and keeps successful work. JSON results include the operation ID, desktop ID, confirmed window IDs/PIDs, tmux session, failed stage, and return outcome. `result` reads the recorded result without repeating the operation. A timeout does not prove that nothing was created.

## Configuration

Copy `default.json` to `~/.config/workspace/default.json` and edit it, or use `--config path.json`. The app list controls both opening order and layout order; the last window receives focus. Layouts: `columns`, `main-stack` (first window left, remaining windows stacked right), or `none`. Override for one invocation with `--layout`.

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

Requires macOS, Hammerspoon with Accessibility permission, the Doorplate CLI installed at `~/.local/bin/doorplate`, and the configured apps. The default also requires tmux and Obsidian's CLI enabled. Obsidian's configured vault must be available. Hammerspoon needs Automation permission for Ghostty and Edge; macOS prompts on first use. Allow these prompts to finish setup.

Link `workspace.py` as `~/.local/bin/workspace`, link this workflow directory as `~/.local/share/workspace`, and create `~/.local/state/workspace` with mode 0700. Add this to Hammerspoon's init (already installed in Jason's tracked configuration):

```lua
local root = os.getenv("HOME") .. "/.local/share/workspace"
local state = os.getenv("HOME") .. "/.local/state/workspace"
WorkspaceCreate = dofile(root .. "/workspace.lua").start(root, state)
```

Reload Hammerspoon, then run `workspace check`. Install the Alfred workflow normally or use the repository's development symlink. Hammerspoon and Doorplate need to start at login for this to work after reboot.

The CLI submits local JSON data to a Hammerspoon directory watcher. Hammerspoon executes GUI operations in the logged-in session; the caller need not have a working Hammerspoon IPC connection. Calls are serialized, requests expire if unacknowledged, and startup requests are not replayed. Results remain in `~/.local/state/workspace` for diagnosis. The worker coordinates its busy state with the existing close/prune operations in Jason's Hammerspoon configuration.

Setup briefly visits the new desktop. Success and ordinary failure both attempt to restore the original stable Space ID, unless `--stay` requests the new one. If Hammerspoon quits or the original desktop disappears, restoration cannot be guaranteed; partial work remains available for inspection.

## Agent boundary

Agents decide whether a task deserves its own workspace and supply the name, directory, URLs, note, and optional existing tmux session. The CLI performs only the requested setup. It does not infer a project from a name, launch an agent, synchronize project state, or manage the lifetime of tmux sessions. Use the existing `cs`/Doorplate close action to close the desktop's windows normally.
