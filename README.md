# Alfred Workflows

Custom Alfred workflows for macOS productivity automation.

Note: [LLMs are great at one-shotting these](https://x.com/JasonObermaier/status/2017881958726975934). You should try it!

## Requirements

- [Alfred](https://www.alfredapp.com/) with Powerpack license
- macOS

Install dependencies for workflows that need them:

```bash
brew install jq pandoc cliclick
```

## Workflows

### [Edge Workspace Switcher](Edge%20Workspace%20Switcher.alfredworkflow)

**Keyword:** `ew`

Quickly switch between Microsoft Edge workspaces. Lists all workspaces from Edge's cache and lets you filter/select one to switch to.

**Dependencies:** [jq](https://jqlang.github.io/jq/)

---

### [Discord Timestamps](Discord%20Timestamps.alfredworkflow)

**Keyword:** `dt`

Convert natural language dates/times to Discord timestamp formats. Type something like "tomorrow 4pm" or "next Friday" and get all Discord timestamp variants.

**Formats generated:**
- Relative time (`<t:...:R>`)
- Long/short date and time
- Long/short date
- Long/short time

**Note:** Discord now has a native `@time` feature (desktop, Jan 2026) for creating timestamps directly in chat.

---

### [Clean Paste](Clean%20Paste.alfredworkflow)

**Keyword:** `clean paste` or `cp`

Remove line breaks and normalize whitespace from clipboard content, then paste. Useful for cleaning up text copied from PDFs or formatted sources. Main use case for me as of early 2026: Cleaning up terminal output of coding agents.

**Dependencies:** [pandoc](https://pandoc.org/)

---

### [Fix macOS Focus](Fix%20macOS%20Focus.alfredworkflow)

**Keyword:** `ff`

Workaround for the [macOS focus stealing bug](https://hynek.me/til/macos-window-focus-desktops/). When switching between apps across desktops (e.g., via Alfred), macOS sometimes gives focus to a random app instead of the one you activated. The fix involves opening Safari with two tabs and dragging one into a separate window. Sounds crazy but it works.

**Setup:** Grant Accessibility permissions to Alfred (System Settings → Privacy & Security → Accessibility)

**Dependencies:** [cliclick](https://github.com/BlueM/cliclick)

---

### [Moom Actions](Moom%20Actions.alfredworkflow)

**Keyword:** `wm`

Control Moom window management actions from Alfred. Lists all available Moom actions (window positions, layouts, display moves) and executes the selected one. To make this useful you'll need to configure Moom with your preferred window arrangements and give them files that are easy to fuzzy-search. For example: "Left & Right" for sending window 1 to left half and window 2 to right half; "Sidecar" for sending window 1 to left 2/3 and window 2 to left 1/3; "Monitor to left" for sending window to monitor to the left if existing; etc.

**Dependencies:** [Moom](https://manytricks.com/moom/)

---

### [Multi-Paste](Multi-Paste.alfredworkflow)

**Keyword:** `mp` or `Multi Paste`

Select multiple items from Alfred's clipboard history and paste them as a formatted list. Opens a Terminal window with fzf for multi-selection (TAB to select, Ctrl-A for all, Enter to confirm), then lets you choose output format: dash list, numbered list, bullet points, comma-separated, or plain newlines. Result is auto-pasted to the original app.

**Setup:** Copy helper scripts to your PATH:
```bash
cp Multi-Paste/multiclip.py Multi-Paste/multiclip-wrapper.sh ~/bin/
chmod +x ~/bin/multiclip.py ~/bin/multiclip-wrapper.sh
```

**Dependencies:** [fzf](https://github.com/junegunn/fzf), Python 3

---

### [Multi Send](Multi%20Send.alfredworkflow)

**Keyword:** `ms` or `Multi Send`

Send clipboard list items as separate messages. Parses the clipboard content based on format (dash list, numbered, bullets, comma-separated, or plain newlines), then sends each item as an individual message to the frontmost app with Cmd+V and Enter. Includes focus-change detection to abort if you switch apps mid-send.

**Setup:** Copy helper script to your PATH:
```bash
cp Multi-Send/multisend.py ~/bin/
chmod +x ~/bin/multisend.py
```

**Dependencies:** Python 3

---

## Installation

Double-click any `.alfredworkflow` file to install.

## Development

The `.alfredworkflow` files are zip archives that can be extracted for inspection:

```bash
unzip -l "Workflow Name.alfredworkflow"  # list contents
unzip -p "Workflow Name.alfredworkflow" info.plist | plutil -p -  # view config
```
