-- Open a new window of the given app on the current Space, without switching Spaces.
--
-- Use Obsidian's CLI or the app's window menu command while backgrounded,
-- verify a window appeared, then bring the app frontmost. Activating *first*
-- can switch to a Space that already has a window. Some apps cannot create
-- background windows; report this rather than sending an unrelated shortcut.
--
-- argv: 1 = app path, 2 = bundle id, 3 = Obsidian helper path (from wrapper)
-- Returns "" on success; any non-empty return is a message the wrapper passes to
-- Alfred, which posts it as a notification (osascript's own `display notification`
-- is unreliable — its source may be disabled in macOS notification settings).

on run argv
	set appPath to item 1 of argv
	set bundleId to item 2 of argv

	tell application "System Events"
		set procs to (processes whose bundle identifier is bundleId)
		if procs is {} then
			-- Not running: a cold launch yields a window on the current Space by itself.
			do shell script "open " & quoted form of appPath
			return ""
		end if
		set proc to item 1 of procs
	end tell

	tell application "System Events"
		set winBefore to count of windows of proc
	end tell
	if bundleId is "md.obsidian" then
		-- Obsidian's Electron menu handler requires a focused BrowserWindow and
		-- silently ignores background AX presses. Its CLI dispatches directly to
		-- the active vault without activating the old window first.
		try
			do shell script "/usr/bin/python3 " & quoted form of (item 3 of argv) & " " & quoted form of appPath
		on error errMsg
			return "Obsidian CLI failed (requires Command line interface in Settings > General): " & errMsg
		end try
	else
		try
			set target to my findNewWindowItem(proc)
		on error errMsg
			return "Menu scan failed: " & errMsg
		end try
		if target is missing value then
			-- Cmd+N can create a note, chat or other content, not a window.
			return "No supported new-window command found for this app"
		end if
		tell application "System Events" to click target
	end if

	tell application "System Events"
		-- Guard: a matched item can accept the press without producing a window;
		-- activating then would reproduce the Space switch. Poll up to 3s —
		-- Electron apps can take >1s to expose the new window (codex review).
		set winAfter to winBefore
		repeat 30 times
			delay 0.1
			set winAfter to count of windows of proc
			if winAfter > winBefore then exit repeat
		end repeat
		if winAfter > winBefore then
			set frontmost of proc to true
		else
			if bundleId is "md.obsidian" then return "No Obsidian window appeared. Open a vault, use installer 1.12.7+, and enable Command line interface in Settings > General."
			return "No new window appeared; the app may require focus or not support background windows"
		end if
	end tell
	return ""
end run

-- Scan for an enabled new-window menu item. Direct items of top-level menus only
-- (deliberately non-recursive). File menu first: menu bar item 3 is File in AX
-- order (1 Apple, 2 app menu) -- verified for Edge and Finder on this machine.
-- Prefer an ordinary new window over a pop-out of the current tab/chat.
-- Never infer window creation from Cmd+N: Beeper uses it for New Chat.
on findNewWindowItem(proc)
	tell application "System Events"
		set barItems to menu bar items of menu bar 1 of proc
		set menuOrder to {}
		if (count of barItems) ≥ 3 then set end of menuOrder to 3
		repeat with i from 2 to count of barItems
			if i is not 3 then set end of menuOrder to i
		end repeat

		repeat with wantedRank from 1 to 3
			repeat with i in menuOrder
				repeat with mi in (menu items of menu 1 of menu bar item i of menu bar 1 of proc)
					try
						set t to name of mi
						if t is not missing value and enabled of mi then
							if my windowCommandRank(t) is wantedRank then
								-- Known document commands must also use plain Cmd+N.
								if wantedRank is not 3 then return mi
								if (value of attribute "AXMenuItemCmdChar" of mi) is "N" and (value of attribute "AXMenuItemCmdModifiers" of mi) is 0 then return mi
							end if
						end if
					end try
				end repeat
			end repeat
		end repeat
	end tell
	return missing value
end findNewWindowItem

on windowCommandRank(t)
	if t ends with "…" then set t to text 1 thru -2 of t
	if t ends with "..." then set t to text 1 thru -4 of t
	if t contains "Private" or t contains "Incognito" or t contains "Inkognito" then return 0
	if (t starts with "New" or t starts with "Neues") and (t contains "Window" or t contains "Fenster") then return 1
	-- Beeper: "Open Chat in New Window". Also covers tab pop-outs.
	if t starts with "Open" and t ends with "in New Window" then return 2
	if t starts with "In neuem Fenster" and t ends with "öffnen" then return 2
	if t is in {"New", "New File", "New Document", "New Text Document", "Neu", "Neue Datei", "Neues Dokument", "Neues Textdokument"} then return 3
	return 0
end windowCommandRank
