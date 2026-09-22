# Workspace palette

## Goal and scope

Add `ws` (long form `workspace`) as one discoverable Alfred entry point for the existing workspace operations. Keep `sp`, `sn`, `cs`, and `ns` as fast paths. This is a thin interface over the existing operation bridge, not a second workspace implementation. First delivery covers browsing desktops, switching, Back, renaming, closing, basic creation and help. Advanced creation options remain available in the CLI; add them to the palette only after this small navigation flow is proven.

## Interaction

- Root: current desktop first, other desktops in display order, plus New workspace…, Previous desktop, and Help. Typing filters both desktop names and action aliases. Decimal queries select exact desktop numbers. Desktop rows show name, number, current marker and “Enter for actions”; selecting one never switches or closes immediately.
- Desktop actions: Switch, Rename…, Close…, and ← Workspaces. Show the selected desktop name in every action subtitle. Carry its stable ID invisibly, refresh its existence when entering the menu, and resolve again through the existing backend before mutation. If it disappeared, offer return to Workspaces, never another desktop at its former number.
- Rename: show current name as context, accept replacement text, and explicitly apply with Return. Empty names are invalid. ← Actions returns without changing anything. Names travel as data, including Unicode, quotes and punctuation.
- Create: ask for a name, then show two explicit actionable rows: Create and return here; Create and stay there. Show configured apps in subtitles. Name alone uses the existing recipe, home directory, browser new tab, blank notes window and fresh readable tmux session. ← Workspaces cancels. No creation occurs merely by browsing or entering a screen.
- Close: invoke the existing Alfred close action by stable ID, preserving its single confirmation for occupied desktops and immediate removal of empty desktops. Clearly state that windows close normally; no second confirmation layer and no bypass of app save prompts.
- Help: concise non-actionable guidance rows explain the palette, fast keywords, default creation behavior and CLI options. Include ← Workspaces.
- Entering Actions clears the search. Rename and Create start empty literal-name fields. Back remains visible regardless of input: Rename returns to unfiltered Actions, and Workspaces restores the saved root query. Escape retains Alfred's normal dismiss behavior; do not intercept keys or claim a native submenu history stack. Starting from the root keyword always resets stale drilldown state.

## Matching, ordering and visuals

Use one small shared matching helper for searchable lists: case-insensitive partial words in any order, action synonyms (`new/create`, `previous/back`, `rename/name`, `close/remove`). No new fuzzy-search dependency or typo correction in this pass. Preserve intentional ordering and stable selection; no learned ranking of destructive actions. Existing desktop, rename, close and create icons supply a consistent visual vocabulary. Action verbs and subtitles make destructive choices explicit; Close is never default in the unfiltered desktop action menu; an explicit close/remove search may select it. Its subtitle states that empty desktops close immediately. Disable Alfred Filters Results on every palette input, including literal-name screens. Use stable screen-specific item UIDs and `skipknowledge: true` on new inputs to retain selection without learned ranking.

## Implementation boundary

Use ordinary connected Script Filter inputs, item/session variables, direct inbound mode and connections that keep Alfred open during navigation. Verify actual installed plist structure and exercise a minimal root → actions → back loop. If UI automation cannot display results even for existing keywords, provisionally build the remaining screens against the observed native schema and independently test the graph and transitions; keep manual verification explicitly pending. Reuse one palette renderer with explicit screens, bounded state and existing helper functions. Navigation/filtering is read-only. A separate action runner is the only mutation entry point; it submits exactly once, closes Alfred while the operation runs and reports the final outcome. Do not use rerun for actions, shell interpolation of names, AppleScript UI navigation, global keyboard hooks, or a generic menu framework.

Put the entry point in the existing Doorplate Spaces workflow; depend on the already-required Workspace runtime. Do not create another separately installed workflow or move the current shortcuts. Handle missing runtime/backend with an actionable explanatory row. Carry only screen, selected stable desktop ID and root query in session variables; no persisted menu state or new daemon.

## Validation and delivery

1. Independent read-only plan review; adapt concrete findings before implementation.
2. Verify native chaining/back behavior in the minimal navigation loop. A UI automation gap also affecting existing keywords permits provisional implementation with graph and transition tests while manual verification is pending. If actual native chaining fails to preserve state, stop and revise the design rather than invent UI hacks. Do not claim live verification or commit before the pending manual check is resolved.
3. Tests cover exact numeric matching, aliases, disappearing targets, stale root state, literal names, the full root search → Actions → Rename → Actions → Workspaces navigation sequence, cancellation/back navigation, and absence of mutations during filtering. Check workflow graph routes and connection keep-open behavior.
4. Independent implementation review, required full pytest and bundle build. Inspect the installed palette through non-destructive navigation; any mutation smoke test uses only a uniquely named disposable workspace.
5. Commit reviewed changes under the standing authorization. No push. Report any live-UI verification gap explicitly.

## Sources

- [Connected inputs and direct inbound mode](https://www.alfredapp.com/help/workflows/inbound-configuration/)
- [Script Filter matching](https://www.alfredapp.com/help/workflows/inputs/script-filter/)
- [JSON items, variables and autocomplete](https://www.alfredapp.com/help/workflows/inputs/script-filter/json/)
- [Connection window behavior](https://www.alfredapp.com/help/workflows/advanced/alternative-actions/)

## Plan review

Independent reviewer `/root/workspace_palette_plan_review` requested three clarifications: bounded Back state, Close behavior when explicitly searched, and filtering/ranking configuration. All three are incorporated above.

## Delivery validation

Independent native implementation review found no source defects. The Claude review identified the need for a short palette lookup timeout, now capped at five seconds; its executable-file and parser concerns were checked against the actual file modes and custom parser. Native UI verification was initially blocked by computer-use focus interference. Jason subsequently tested the live palette, confirmed it works, and authorized commit and push. No further computer-use checks are needed.

The full suite passed with 323 tests, including navigation/action boundary and worker failure-path coverage; bundles were rebuilt and checked against source. The standalone Codex review command failed during nested sandbox initialization, so the native independent review covered that pass.
