# Doorplate Spaces

`space` or `sp` searches desktops by name or number. `space back` returns to the previous desktop. `sn <name>` previews a new name for the current desktop; Return applies it. Fullscreen app Spaces cannot be named. The rename action briefly restarts Doorplate without activating it.

Run `./doorplate.py --help` for the equivalent CLI. Commands return JSON; failures go to stderr with exit status 1. Use `list` to obtain fresh IDs, and `rename "Name" --id ID` to name a specific desktop without switching to it. Live WindowServer access is required, so use a graphical login session; an isolated background or SSH process may not have access.

## Compatibility

Switching uses `doorplate://switch/NUMBER` and `doorplate://back`. Listing uses macOS SkyLight and Doorplate's `Doorplate.meta.v2` preference. Renaming targets the observed Doorplate 1.6.2 format and fails closed on other versions. The native helper does not perform UI scripting or request Accessibility access.

## Backup recovery

Every rename saves the previous metadata as a new `names-before-rename-*.json` file in `~/Library/Application Support/Alfred/Workflow Data/com.jason.doorplate/`. These files include all desktop names, icons, colors, shortcuts and tracked time; restoring one restores that snapshot of metadata. Other Doorplate preferences and licensing data are unaffected. Backups are not automatically removed.

To recover, quit Doorplate from its menu first. Set `backup_path` to the exact backup file you want, then run these commands in Terminal before reopening Doorplate:

```bash
backup_path="$HOME/Library/Application Support/Alfred/Workflow Data/com.jason.doorplate/names-before-rename-REPLACE_WITH_BACKUP_ID.json"
python3 -m json.tool "$backup_path" >/dev/null && defaults write app.doorplate.Doorplate Doorplate.meta.v2 -data "$(xxd -p "$backup_path" | tr -d '\n')"
open -g -a Doorplate
```
