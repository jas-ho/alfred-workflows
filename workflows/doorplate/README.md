# Doorplate Spaces

`space` or `sp` searches desktops by name or number. `space back` returns to the previous desktop. `sn <name>` previews a new name for the current desktop; Return applies it. Fullscreen app Spaces cannot be named. The rename action briefly restarts Doorplate without activating it.

Run `./doorplate.py --help` for the equivalent CLI. Commands return JSON; failures go to stderr with exit status 1. Use `list` to obtain fresh IDs, and `rename "Name" --id ID` to name a specific desktop without switching to it. Live WindowServer access is required, so use a graphical login session; an isolated background or SSH process may not have access.

Naming a desktop through `sn` or the CLI also changes its Automatic color to Transparent. Explicit color choices are preserved. This happens in the same saved update as the name and survives reboot. Newly created desktops keep Doorplate's default appearance until you name them through this workflow; names entered directly in Doorplate do not trigger this rule. No background watcher is installed.

## Close a desktop

`cs [name or number]` lists desktops with the current one first. Empty desktops close immediately. If a desktop has exclusive windows, one centered confirmation summarizes the apps and window counts where you are currently working; Cancel is the default. Confirming requests normal window closes one at a time, then removes the desktop only after verifying closure. Windows shared with other desktops stay open. The last normal desktop on a display cannot be closed.

Closing another desktop does not first visit it. If the target is still active when it is ready for removal, the workflow uses Doorplate’s `space back` history to leave it, with a same-display neighbor as a fallback when Back cannot leave the target. Otherwise it stays on your current desktop. Background window inspection must succeed; an uninspectable window stops the operation instead of automatically switching to it.

Save prompts are never answered automatically. A window that remains open or changed desktop contents stops the operation; handle the prompt and run `cs` again. Earlier successful closes are not undone. Merely switching desktops does not cancel a confirmed operation: its target is the selected desktop and the specific windows you reviewed. Applications are not quit or killed.

The CLI equivalent is `doorplate close [name or number]` or `doorplate close --id ID`, defaulting to the current desktop. Its JSON `close_requested` status acknowledges the asynchronous request, not completed closure. Desktops containing exclusive windows require GUI confirmation. This is not yet an unattended agent teardown API.

Closing additionally requires Jason's Hammerspoon configuration (`~/bin/hammerspoon/space-close.lua`, loaded from `init.lua`), its Accessibility permission, `cg-real-windows`, and the `~/.local/bin/hs` IPC client. Reload Hammerspoon after backend changes. The backend is maintained in the separate `~/bin` repository and is not included in the workflow zip. Mocked backend tests: `uv run ~/bin/tests/test-space-close.py`.

## Native interface

Switching uses `doorplate://switch/NUMBER` and `doorplate://back`. Listing uses macOS SkyLight and Doorplate's `Doorplate.meta.v2` preference. Renaming targets the observed Doorplate 1.6.2 format and fails closed on other versions. The native helper does not perform UI scripting or request Accessibility access.

## Backup recovery

Every rename saves the previous metadata as a new `names-before-rename-*.json` file in `~/Library/Application Support/Alfred/Workflow Data/com.jason.doorplate/`. These files include all desktop names, icons, colors, shortcuts and tracked time; restoring one restores that snapshot of metadata. Other Doorplate preferences and licensing data are unaffected. Backups are not automatically removed.

To recover, quit Doorplate from its menu first. Set `backup_path` to the exact backup file you want, then run these commands in Terminal before reopening Doorplate:

```bash
backup_path="$HOME/Library/Application Support/Alfred/Workflow Data/com.jason.doorplate/names-before-rename-REPLACE_WITH_BACKUP_ID.json"
python3 -m json.tool "$backup_path" >/dev/null && defaults write app.doorplate.Doorplate Doorplate.meta.v2 -data "$(xxd -p "$backup_path" | tr -d '\n')"
open -g -a Doorplate
```
