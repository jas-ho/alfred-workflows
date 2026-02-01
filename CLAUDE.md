# Maintenance

## Structure

- `.alfredworkflow` files are zip archives containing `info.plist` + scripts + icons

## Adding/Updating Workflows

1. Export from Alfred Preferences → Workflows → right-click → Export
2. Place `.alfredworkflow` file in repo root
3. Update README.md with keyword, description, and dependencies

## Inspecting Workflows

```bash
unzip -l "Workflow Name.alfredworkflow"  # list contents
unzip -p "Workflow Name.alfredworkflow" info.plist | plutil -p -  # view config
```

## Common Patterns

- Script filters output Alfred JSON format for dynamic lists
- AppleScript via `osascript` for app automation
- `jq` for JSON parsing in bash scripts
