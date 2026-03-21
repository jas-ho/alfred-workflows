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

### [Edge Workspace Switcher](dist/Edge%20Workspace%20Switcher.alfredworkflow)

**Keyword:** `ew`

Quickly switch between Microsoft Edge workspaces. Lists all workspaces from Edge's cache and lets you filter/select one to switch to.

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

Remove line breaks and normalize whitespace from clipboard content, then paste. Useful for cleaning up text copied from PDFs or formatted sources. Main use case for me as of early 2026: Cleaning up terminal output of coding agents.

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
./dev-setup.sh

# Edit scripts directly - changes are picked up by Alfred instantly
vim workflows/clean-paste/clean.py

# Build distribution zips
./build.sh

# Run tests
python tests/clean_paste_test.py
```

See [CLAUDE.md](CLAUDE.md) for detailed development docs.
