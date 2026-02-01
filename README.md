# Alfred Workflows

Custom Alfred workflows for macOS productivity automation.

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

---

### [Clean Paste](Clean%20Paste.alfredworkflow)

**Keyword:** `clean paste` or `cp`

Remove line breaks and normalize whitespace from clipboard content, then paste. Useful for cleaning up text copied from PDFs or formatted sources.

**Dependencies:** [pandoc](https://pandoc.org/)

---

### [Fix macOS Focus](Fix%20macOS%20Focus.alfredworkflow)

**Keyword:** `ff`

Workaround for the [macOS focus stealing bug](https://hynek.me/til/macos-window-focus-desktops/). When switching between apps across desktops (e.g., via Alfred), macOS sometimes gives focus to a random app instead of the one you activated. The fix involves opening Safari with two tabs and dragging one into a separate window. This workflow triggers an external script at `~/bin/fix-macos-focus` that automates this workaround.

---

### [Moom Actions](Moom%20Actions.alfredworkflow)

**Keyword:** `wm`

Control Moom window management actions from Alfred. Lists all available Moom actions (window positions, layouts, display moves) and executes the selected one.

**Dependencies:** [Moom](https://manytricks.com/moom/)

---

### [Split Display](Split%20Display.alfredworkflow)

**Keyword:** `split <app>`

Split display between the current app and another app. The current window moves to the left half, the specified app moves to the right half.

**Example:** `split Safari` splits the screen with your current app on the left and Safari on the right.

---

## Installation

Double-click any `.alfredworkflow` file to install.

## Development

Source files (info.plist, icons) are included for Edge Workspace Switcher. The workflow files themselves are zip archives that can be extracted for inspection.
