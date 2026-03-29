# Alfred Workflows

## Structure

- `workflows/<name>/` - source directories (symlinked into Alfred for live editing)
- `dist/` - built .alfredworkflow zips for distribution (run `./build.sh`)
- `tests/` - regression tests

## Development

1. Run `./dev-setup.sh` once to set up symlinks
2. Edit scripts directly in `workflows/<name>/` - Alfred picks up changes instantly
3. To edit workflow config (keywords, connections, UI): use Alfred Preferences
   (changes write back to the symlinked info.plist in the repo)
4. Run `plutil -convert xml1 workflows/<name>/info.plist` after Alfred edits
   (Alfred may save as binary plist)

## Adding a New Workflow

**GUI-first** (when designing UI in Alfred):
1. Create workflow in Alfred Preferences (generates a new UUID dir)
2. `mkdir workflows/<new-name>` and move contents from Alfred's UUID dir
3. Extract substantial scripts to standalone files and wire them via `scriptfile`

**Code-first** (when you already know the plist structure):
1. `mkdir workflows/<new-name>` and create `info.plist` + scripts
   (use an existing workflow like `smart-date` as a reference for plist structure)
2. Run `./build.sh` to create the `.alfredworkflow` zip
3. `open "dist/<Name>.alfredworkflow"` to import into Alfred

**Both paths then:**
4. Set a stable `bundleid` in `info.plist` (convention: `com.jason.<name>`)
5. Run `./dev-setup.sh` to symlink the workflow dir into Alfred
6. Complete the checklist below

## Completion Checklist

After adding or modifying a workflow:
- [ ] `uv run pytest` passes
- [ ] `./build.sh` to update dist/ zips
- [ ] README.md updated (add entry under `## Workflows` for new workflows)
- [ ] `codex review --uncommitted` for a second opinion on non-trivial changes

## Modifying a Workflow

- Scripts (.py/.js/.sh): Edit directly, changes are live
- Plist config: Edit in Alfred Preferences or with `plutil`

## Script Patterns

- `scriptfile` field in plist references a file relative to workflow dir
- Preferred in this repo: type `8` (External Script) + executable script files
- For AppleScript-heavy workflows, keep logic in `.applescript` and invoke it from a shell wrapper scriptfile
- Alfred sets CWD to workflow dir when running scripts

## Inspecting/Editing Plists

```bash
plutil -p workflows/<name>/info.plist                              # pretty-print
plutil -extract 'objects.0.config' json workflows/<name>/info.plist # extract field
plutil -convert xml1 workflows/<name>/info.plist                   # ensure diffable XML
```

## Testing

```bash
uv sync --dev
uv run pytest
```

Conventions:
- Add tests under `tests/*_test.py` so pytest discovers them.
- Use `@pytest.mark.parametrize` for table-driven behavior checks.
- Prefer extracting pure helper functions from workflow scripts when logic needs unit tests.
