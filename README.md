# Alfred Workflows

Custom Alfred workflows for macOS productivity automation.

Note: [LLMs are great at one-shotting these](https://x.com/JasonObermaier/status/2017881958726975934). You should try it!

## Requirements

- [Alfred](https://www.alfredapp.com/) with Powerpack license
- macOS

Install dependencies for workflows that need them:

```bash
brew install jq cliclick fzf
```

## Workflows

### [Restart App](dist/Restart%20App.alfredworkflow)

**Keywords:** `ra` (also `rr`, `restart`, `relaunch`); add Space to enter the app list without normal Alfred results. Lists running apps with their own icons, multiword matching, compact names, and initials. Return requests a normal quit and reopens the app after it exits. Option+Return quits only; Command+Return hides an app; `rexclude` edits the hidden-app list. Save prompts and cancelled quits are not overridden. Matching uses app name; actions retain the selected path, process ID, and launch time. Finder, Alfred, and nested helper apps are excluded. macOS graphical login session required. [Details](workflows/restart-app/README.md).

### [Doorplate Spaces](dist/Doorplate%20Spaces.alfredworkflow)

**Keywords:** `space` (or `sp`) to search desktops by name or number; `space back` to jump back; `sn <name>` to rename the current desktop.

Search results show desktop numbers and mark the current desktop. Renaming previews the target before Return and refuses to change a different desktop if you switched while Alfred was open. Fullscreen app Spaces are excluded. Names stay with their Space when reordered.

Switching uses stable desktop IDs through Hammerspoon. Renaming briefly quits and relaunches Doorplate without activation, updates the selected name in its private preferences, and changes Automatic color to Transparent while preserving explicit color choices. New desktops receive this appearance when named through `sn` or the CLI; it is saved across reboots. A separate copy of the previous metadata is saved in Alfred's workflow data directory (`names-before-rename-*.json`). Other desktop metadata and app settings are preserved. The rename format targets Doorplate 1.6.2; newer versions require rechecking before renaming is enabled. No background syncing is installed. [Backup recovery](workflows/doorplate/README.md).

`cs [name or number]` closes desktops, with the current desktop listed first. Empty desktops close immediately; desktops with windows get one confirmation where you are. It preserves shared windows, stops on save prompts or changed contents, and verifies removal. Closing the active desktop returns via `space back`, with a neighbor fallback. Requires the separate Hammerspoon backend in `~/bin/hammerspoon/space-close.lua`; see [setup and behavior](workflows/doorplate/README.md#close-a-desktop). CLI: `workspace close --id ID` previews; add `--yes` to execute and wait for verified removal.

**Dependencies:** [Doorplate](https://doorplate.app/) installed and set up, Python 3, macOS. Doorplate needs its normal Accessibility permission. Closing desktops additionally uses Hammerspoon Accessibility and Mission Control automation. Run from Alfred's graphical login session.

The same implementation exposes a CLI for terminals and agents, with JSON output and nonzero exit status on failure:

```bash
workspace list
workspace switch Research
workspace switch --id 5
workspace rename "Research"             # current desktop
workspace rename "Research" --id 5      # explicit desktop, without switching
workspace back
```

Use IDs from a fresh `workspace list --json` result; explicit `--id` avoids dependence on desktop order. The shared `workspace` CLI sends operations through Hammerspoon in the logged-in GUI session, including calls from agents. See [CLI contract and installation](workflows/new-workspace/README.md#cli). The separate `doorplate` CLI has been removed.

---

### [App Launcher](dist/App%20Launcher.alfredworkflow)

**Keyword:** `a`

Launch applications using Spotlight (mdfind) instead of Alfred's native file cache. Workaround for when Alfred's filecache doesn't index all apps. Lists all .app bundles from /Applications, /System/Applications, and ~/Applications with client-side filtering, deduplication, and a short-lived cache for instant keystroke response. Focuses already-running apps rather than opening new windows. Matches words in any order, compact names, and initials, consistently with Open New Window.

**Dependencies:** Python 3

---

### [Open New Window](dist/Open%20New%20Window.alfredworkflow)

**Keywords:** `wn` (window new); `nw` and `newwin` also work. For example, `wn Safari` opens a new Safari window on this desktop. The workflow uses a window-and-plus icon; app results show each app's own icon.

Match app names, word prefixes, or initials (`gc` for Google Chrome, `vsc` or `vscode` for Visual Studio Code). Alfred learns from your selections across all three keywords. Tab completes the selected app's name; Return requests a new window on this desktop.

Requests a new window of the chosen app on the current Space, then focuses it once an additional window is detected. Uses the app's menu command while backgrounded, including recognized Cmd+N document commands (New, New File, New Document) and pop-out commands such as Beeper's "Open Chat in New Window" (opens the selected chat). Obsidian uses its CLI to open a blank window in the active vault because its menu command does nothing while unfocused. Apps without a supported command, or which require focus to create windows, show a notification. Never sends a blind Cmd+N, which could create a note or chat instead. Window placement ultimately depends on the app; existing windows are not moved between Spaces.

**Dependencies:** Python 3, Accessibility permission for Alfred. For Obsidian: [installer 1.12.7+](https://help.obsidian.md/cli), an open vault when Obsidian is already running, and **Settings → General → Command line interface** enabled.

---

### [New Workspace](dist/New%20Workspace.alfredworkflow)

**Keywords:** `ns`, `newspace`

`ns Research` creates a named desktop with fresh browser, blank Obsidian, and Ghostty windows in three columns, then returns to the original desktop. Command-Return stays in the new desktop with the terminal focused. The terminal uses a dedicated, readable tmux session name such as `ws-research`; no note is created automatically.

The same operation is available to agents as `workspace create "Research"`, with optional `--directory`, repeated `--url`, `--note`, `--tmux-session`, `--layout`, and `--stay`. The app list and layout are configurable; ordinary apps use their new-window menu, while small helpers supply tmux/URL/note behavior. Partial failures preserve completed work and produce explicit results. See [configuration, CLI, and setup](workflows/new-workspace/README.md).

**Dependencies:** Hammerspoon workspace worker, Doorplate app, Python 3; default recipe also needs tmux, Ghostty, Edge, and Obsidian with CLI enabled.

**Retired:** the previous `pj`/pjws workflow is disabled and [archived in place](workflows/pjws/ARCHIVED.md). It is no longer built. Its old project data and tmux sessions are retained.

---

### [Edge Workspace Switcher](dist/Edge%20Workspace%20Switcher.alfredworkflow)

**Keyword:** `ew`

Quickly switch between Microsoft Edge workspaces. Lists workspaces from Edge data files and lets you filter/select one to switch to. Alfred handles word matching in any order; `ew` followed by Space enters the workspace list.

**Known issue (Edge 146+ / Workspace V2):** Listing works, but opening/switching is currently broken.  
Track status in [Issue #4](https://github.com/jas-ho/alfred-workflows/issues/4).

**Dependencies:** [jq](https://jqlang.github.io/jq/)

---

### [Discord Timestamps](dist/Discord%20Timestamps.alfredworkflow)

**Keyword:** `dt`

Convert natural language dates/times to Discord timestamp formats. Type something like "tomorrow 4pm" or "next Friday" and get all Discord timestamp variants.

**Formats generated:**

- Relative time (`<t:...:R>`)
- Long/short date and time
- Long/short date
- Long/short time

**Note:** Discord now has a native `@time` feature (desktop, Jan 2026) for creating timestamps directly in chat.

---

### [Clean Paste](dist/Clean%20Paste.alfredworkflow)

**Keyword:** `clean paste` or `cp`

Remove line breaks and normalize whitespace from clipboard content, then paste. Useful for cleaning up text copied from PDFs or formatted sources. Main use case for me as of early 2026: Cleaning up terminal output of coding agents. Also strips blockquote markers (`>` or the rendered `│` bar) from drafts Claude wraps in quotes, unwrapping the wrapped lines while preserving paragraph breaks and short intentional breaks like signatures.

**Dependencies:** Python 3

---

### [Fix macOS Focus](dist/Fix%20macOS%20Focus.alfredworkflow)

**Keyword:** `ff`

Workaround for the [macOS focus stealing bug](https://hynek.me/til/macos-window-focus-desktops/). When switching between apps across desktops (e.g., via Alfred), macOS sometimes gives focus to a random app instead of the one you activated. The fix involves opening Safari with two tabs and dragging one into a separate window. Sounds crazy but it works.

**Setup:** Grant Accessibility permissions to Alfred (System Settings -> Privacy & Security -> Accessibility)

**Dependencies:** [cliclick](https://github.com/BlueM/cliclick)

---

### [Moom Actions](dist/Moom%20Actions.alfredworkflow)

**Keyword:** `wm`

Control Moom window management actions from Alfred. Lists all available Moom actions (window positions, layouts, display moves) and executes the selected one. To make this useful you'll need to configure Moom with your preferred window arrangements and give them names that are easy to fuzzy-search. For example: "Left & Right" for sending window 1 to left half and window 2 to right half; "Sidecar" for sending window 1 to left 2/3 and window 2 to left 1/3; "Monitor to left" for sending window to monitor to the left if existing; etc.

Position previews show halves, thirds, two-thirds, quarters, saved layouts, maximize, fullscreen, grid, and display moves. Unknown custom actions use a neutral fallback. The built-in Center Window entry invokes Moom’s center command directly.

**Dependencies:** [Moom](https://manytricks.com/moom/)

---

### [Smart Date](dist/Smart%20Date.alfredworkflow)

**Keyword:** `sd` or `smartdate`

Parse natural language dates and times into multiple output formats. Type something like "next tuesday", "in three months", or "tomorrow 3pm" and pick the format you need. Auto-detects whether a time component was specified and adjusts the output formats accordingly.

**Date-only formats** (e.g., `sd next tuesday`):

- ISO date (`2026-03-10`)
- European date (`10.03.2026`)
- English (`Tuesday, March 10, 2026`)
- German (`Dienstag, 10. März 2026`)
- Unix timestamp

**DateTime formats** (e.g., `sd tomorrow 3pm`):

- ISO datetime (`2026-03-10_15-00`)
- European datetime (`10.03.2026 15:00`)
- English (`Tuesday, March 10, 2026, 3:00 PM`)
- German (`Dienstag, 10. März 2026, 15:00`)
- Unix timestamp

**Supported inputs:** Named days (`next friday`), relative offsets (`in 2 days`, `three months ago`), sub-day offsets (`in 90 minutes`, `5hrs`), calendar navigation (`next month`, `last year`), specific dates (`march 15`), and word-form numbers (`in five weeks`).

---

### [Multi Paste](dist/Multi%20Paste.alfredworkflow)

**Keyword:** `mp` or `Multi Paste`

Select multiple items from Alfred's clipboard history and paste them as a formatted list. Opens a Terminal window with fzf for multi-selection (TAB to select, Ctrl-A for all, Enter to confirm), then lets you choose output format: dash list, numbered list, bullet points, comma-separated, or plain newlines. Result is auto-pasted to the original app.

**Setup:** The helper scripts need to be available in `~/bin/`:

```bash
# For development (symlinks, auto-updates):
./dev-setup.sh

# For manual install:
cp workflows/multi-paste/multiclip.py workflows/multi-paste/multiclip-wrapper.sh ~/bin/
chmod +x ~/bin/multiclip.py ~/bin/multiclip-wrapper.sh
```

**Dependencies:** [fzf](https://github.com/junegunn/fzf), Python 3

---

### [Run Command](dist/Run%20Command.alfredworkflow)

**Keyword:** `run` (or `>`)

Run a one-off shell command from Alfred without opening a Terminal window. Useful for quick commands where you want the result on your clipboard (e.g. `run date`, `run git -C ~/Code/foo rev-parse HEAD`, `run brew outdated`).

- Headless `zsh -i -l` (so `[[ -o interactive ]] || return` guards in your `.zshrc` still fire and `ZDOTDIR` is respected). Init-time stderr is discarded to hide the "can't change option: zle" noise that shows up when `-i` runs without a tty; the command's own stderr is still captured via a separate file descriptor.
- Aliases, functions, and PATH from your dotfiles are available.
- Working directory is `$HOME`, so `run ls Desktop` works.
- stdout is copied to the clipboard; a notification shows exit status and a truncated preview (newlines collapsed, 240-char cap).

**Conflict with Alfred's built-in:** if Alfred's "Terminal command" feature is enabled with prefix `>`, disable it in Alfred Preferences → Features → Terminal/Shell so this workflow's `>` keyword wins.

**Permissions:** grant Alfred.app Full Disk Access (and any other TCC permissions) in System Settings → Privacy & Security if your commands touch protected paths.

---

### [Multi Send](dist/Multi%20Send.alfredworkflow)

**Keyword:** `ms` or `Multi Send`

Send clipboard list items as separate messages. Parses the clipboard content based on format (dash list, numbered, bullets, comma-separated, or plain newlines), then sends each item as an individual message to the frontmost app with Cmd+V and Enter. Includes focus-change detection to abort if you switch apps mid-send.

**Setup:** The helper script needs to be available in `~/bin/`:

```bash
# For development (symlink, auto-updates):
./dev-setup.sh

# For manual install:
cp workflows/multi-send/multisend.py ~/bin/
chmod +x ~/bin/multisend.py
```

**Dependencies:** Python 3

---

## Installation

Download any `.alfredworkflow` file from the [`dist/`](dist/) directory and double-click to install. Some workflows require helper scripts; check the workflow's section above for setup instructions.

## Development

Workflows are stored as unpacked source directories in `workflows/`. Scripts are standalone files referenced by `info.plist` via the `scriptfile` field.

```bash
# Set up symlinks for live editing (one-time)
# Links only workflows already imported in Alfred (import from dist/ first).
./dev-setup.sh

# Edit scripts directly - changes are picked up by Alfred instantly
vim workflows/clean-paste/clean.py

# Build distribution zips
./build.sh

# Install/sync test environment
uv sync --dev

# Run all tests
uv run pytest
```

Test conventions:

- Put tests in `tests/*_test.py` (pytest-discovered).
- Prefer parametrized tests for input/output matrices.
- Keep workflow logic in small pure helpers where possible to make testing easy.

See [CLAUDE.md](CLAUDE.md) for detailed development docs.
