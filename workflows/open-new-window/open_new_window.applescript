-- Open a new window of the given app on the current Space, without switching Spaces.
--
-- Mechanism: click the app's own new-window menu item via AX while the app is in
-- the background (new windows are created on the active Space), verify a window
-- actually appeared, then bring the app frontmost. Activating *first* is the bug
-- this replaces: macOS would switch to a Space that already has a window.
--
-- argv: 1 = app path, 2 = bundle id (derived by run_open_new_window.sh)
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

	try
		set target to my findNewWindowItem(proc)
	on error errMsg
		return "Menu scan failed: " & errMsg
	end try

	if target is missing value then
		-- Last resort (accepted trade-off): no discoverable new-window item.
		-- May switch Spaces for apps whose windows are all elsewhere; never silent.
		tell application "System Events"
			set frontmost of proc to true
			keystroke "n" using {command down}
		end tell
		return "No new-window menu item — sent Cmd+N"
	end if

	tell application "System Events"
		set winBefore to count of windows of proc
		click target
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
			return "Menu item clicked but no window appeared"
		end if
	end tell
	return ""
end run

-- Scan for an enabled new-window menu item. Direct items of top-level menus only
-- (deliberately non-recursive). File menu first: menu bar item 3 is File in AX
-- order (1 Apple, 2 app menu) -- verified for Edge and Finder on this machine.
-- Title match beats shortcut match: Finder's "New Finder Window" reports
-- AXMenuItemCmdModifiers=2, so a Cmd+N filter alone would miss it; in Edge,
-- char=N alone is ambiguous ("New Window" vs "New InPrivate Window").
on findNewWindowItem(proc)
	tell application "System Events"
		set barItems to menu bar items of menu bar 1 of proc
		set menuOrder to {}
		if (count of barItems) ≥ 3 then set end of menuOrder to 3
		repeat with i from 2 to count of barItems
			if i is not 3 then set end of menuOrder to i
		end repeat

		-- Pass 1: title match ("New ... Window", any language variant we use)
		repeat with i in menuOrder
			repeat with mi in (menu items of menu 1 of menu bar item i of menu bar 1 of proc)
				try
					set t to name of mi
					if t is not missing value and enabled of mi then
						if (t starts with "New" or t starts with "Neues") and (t contains "Window" or t contains "Fenster") then
							return mi
						end if
					end if
				end try
			end repeat
		end repeat

		-- Pass 2: plain Cmd+N shortcut
		repeat with i in menuOrder
			repeat with mi in (menu items of menu 1 of menu bar item i of menu bar 1 of proc)
				try
					if (value of attribute "AXMenuItemCmdChar" of mi) is "N" ¬
						and (value of attribute "AXMenuItemCmdModifiers" of mi) is 0 ¬
						and enabled of mi then
						return mi
					end if
				end try
			end repeat
		end repeat
	end tell
	return missing value
end findNewWindowItem
