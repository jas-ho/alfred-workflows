# Doorplate Spaces

`ws` or `workspace` opens the workspace palette. Search by name, words in any order, or exact desktop number. The current desktop appears first. Return on a desktop opens Switch, Rename…, and Close…; selection alone does not switch desktops. These actions retain the selected stable desktop ID even if desktop order changes.

New workspace… accepts a name and offers Create and return here or Create and stay there, showing the configured apps. It uses the existing recipe and defaults: home directory, browser new tab, blank notes window and a fresh readable tmux session. Advanced directory, URL, note and existing-session options remain in `workspace create --help`.

Rename and creation start with empty name fields. Back rows remain available while typing: Rename returns to Actions, and Workspaces restores the root search. Escape dismisses Alfred. Typing `ws` again starts fresh. Help lists the fast keywords and CLI options. Close is below Switch and Rename unless explicitly searched; empty desktops close immediately, and occupied desktops retain the single confirmation described below.

`space` or `sp` searches desktops by name or number. A numeric query matches the exact desktop number, as it does in `cs` and the CLI. `space back` returns to the previous desktop. `sn <name>` previews a new name for the current desktop; Return applies it. Fullscreen app Spaces cannot be named. The rename action briefly restarts Doorplate without activating it.

The public CLI is `workspace`; run `workspace --help`. Alfred mutations use the same Hammerspoon operation bridge. The standalone `doorplate` CLI has been removed. See [CLI contract and setup](../new-workspace/README.md#cli).

Naming a desktop through `sn` or the CLI also changes its Automatic color to Transparent. Explicit color choices are preserved. This happens in the same saved update as the name and survives reboot. Newly created desktops keep Doorplate's default appearance until you name them through this workflow; names entered directly in Doorplate do not trigger this rule. No background watcher is installed.

## Close a desktop

`cs [name or number]` lists desktops with the current one first. Empty desktops close immediately. If a desktop has exclusive windows, one centered confirmation summarizes the apps and window counts where you are currently working; Cancel is the default. Confirming requests normal window closes concurrently across apps, one outstanding close per app, then removes the desktop only after verifying closure. Windows shared with other desktops stay open. The last normal desktop on a display cannot be closed.

Closing another desktop does not first visit it. If the target is still active when it is ready for removal, the workflow returns to the previously visited desktop, captured when close was invoked. Hammerspoon observes desktop changes, so renaming (which restarts Doorplate) preserves this history. If no usable history exists after a Hammerspoon reload, it tries Doorplate Back, then a same-display neighbor. Otherwise it stays on your current desktop. Background window inspection must succeed; an uninspectable window stops the operation instead of automatically switching to it.

Save prompts are never answered automatically. A window that remains open or changed desktop contents stops the operation; handle the prompt and run `cs` again. Earlier successful closes are not undone. Merely switching desktops does not cancel a confirmed operation: its target is the selected desktop and the specific windows you reviewed. Applications are not quit or killed.

`workspace close [name or number]` or `workspace close --id ID` defaults to a read-only preview of the current or selected desktop. Add `--yes` to execute without the workflow confirmation and wait for verified removal. App save prompts remain untouched. Use the stable ID returned by the preview.

Closing requires the shared workspace worker and Jason's Hammerspoon configuration (`~/bin/hammerspoon/space-close.lua`, loaded from `init.lua`), Accessibility permission, and `cg-real-windows`. No `hs` IPC client is needed. Reload Hammerspoon after backend changes. The backend is maintained in the separate `~/bin` repository and is not included in the workflow zip. Mocked backend tests: `uv run ~/bin/tests/test-space-close.py`.

## Native interface

Switching targets stable desktop IDs. Back and close share Hammerspoon’s observed history, which survives Doorplate restarts but resets when Hammerspoon reloads. `doorplate://back` is used only when no observed history is available. Listing uses macOS SkyLight and Doorplate's `Doorplate.meta.v2` preference. Renaming targets the observed Doorplate 1.6.2 format and fails closed on other versions. The native helper does not perform UI scripting or request Accessibility access.

## Backup recovery

Every rename saves the previous metadata as a new `names-before-rename-*.json` file in `~/Library/Application Support/Alfred/Workflow Data/com.jason.doorplate/`. These files include all desktop names, icons, colors, shortcuts and tracked time; restoring one restores that snapshot of metadata. Other Doorplate preferences and licensing data are unaffected. Backups are not automatically removed.

To recover, quit Doorplate from its menu first. Set `backup_path` to the exact backup file you want, then run these commands in Terminal before reopening Doorplate:

```bash
backup_path="$HOME/Library/Application Support/Alfred/Workflow Data/com.jason.doorplate/names-before-rename-REPLACE_WITH_BACKUP_ID.json"
python3 -m json.tool "$backup_path" >/dev/null && defaults write app.doorplate.Doorplate Doorplate.meta.v2 -data "$(xxd -p "$backup_path" | tr -d '\n')"
open -g -a Doorplate
```
