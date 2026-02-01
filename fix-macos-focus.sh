#!/bin/bash
# fix-macos-focus: Workaround for macOS window focus bug
# https://hynek.me/til/macos-window-focus-desktops/
#
# The bug: switching apps across desktops sometimes leaves windows in a
# broken focus state. The fix: drag a Safari tab into a new window.
# This script automates that workaround.

set -e

# Position Safari window at a known location so we can calculate tab positions
WINDOW_X=100
WINDOW_Y=100
WINDOW_WIDTH=800
WINDOW_HEIGHT=600

# Tab bar is ~52px from top of window
TAB_Y=$((WINDOW_Y + 52))
TAB_X=$((WINDOW_X + 200))

# Drag distance (down and slightly right to create new window)
DRAG_Y=$((TAB_Y + 150))
DRAG_X=$((TAB_X + 50))

# Step 1: Set up Safari with a window and create a new tab
osascript <<EOF
tell application "Safari"
    activate
    if (count of windows) = 0 then
        make new document with properties {URL:"about:blank"}
    end if
    set bounds of front window to {${WINDOW_X}, ${WINDOW_Y}, $((WINDOW_X + WINDOW_WIDTH)), $((WINDOW_Y + WINDOW_HEIGHT))}
    tell front window
        set newTab to make new tab with properties {URL:"about:blank"}
        set current tab to newTab
    end tell
end tell
EOF

sleep 0.5

# Step 2: Drag the tab to create a new window
cliclick dd:${TAB_X},${TAB_Y} w:50 du:${DRAG_X},${DRAG_Y}

sleep 0.3

# Step 3: Quit Safari
osascript -e 'tell application "Safari" to quit'

echo "Focus fix applied!"
