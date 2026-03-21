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

1. Create workflow in Alfred Preferences (generates a new UUID dir)
2. `mkdir workflows/<new-name>` and move contents from Alfred's UUID dir
3. Extract substantial scripts to standalone files, set `scriptfile` in plist
4. Add UUID mapping to `dev-setup.sh`
5. Replace Alfred's UUID dir with symlink to `workflows/<new-name>/`
6. Run `./build.sh` and update README

## Modifying a Workflow

- Scripts (.py/.js/.sh): Edit directly, changes are live
- Plist config: Edit in Alfred Preferences or with `plutil`
- After changes: run `./build.sh` to update dist/ zips

## Script Patterns

- `scriptfile` field in plist references a file relative to workflow dir
- Script type codes: 0=bash, 5=zsh, 6=AppleScript, 7=JXA, 9=Python
- AppleScript (type=6) does NOT support `scriptfile` - must be inline
- Alfred sets CWD to workflow dir when running scripts

## Inspecting/Editing Plists

```bash
plutil -p workflows/<name>/info.plist                              # pretty-print
plutil -extract 'objects.0.config' json workflows/<name>/info.plist # extract field
plutil -convert xml1 workflows/<name>/info.plist                   # ensure diffable XML
```

## Testing

```bash
python tests/clean_paste_test.py
python tests/workflow_integrity_test.py
```
