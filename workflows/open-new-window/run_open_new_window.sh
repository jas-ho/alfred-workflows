#!/bin/zsh
# Wrapper for the Open New Window action. Alfred passes the app path as $1.
# Derives the bundle id here (non-launching, unlike AppleScript's `id of app`)
# and hands both to the AppleScript that does the AX work.
#
# Anything echoed to stdout becomes {query} for Alfred's Post Notification
# object downstream (a filter blocks it when empty). We don't use osascript's
# `display notification` — its source may be disabled in Notification settings.
set -u

SCRIPT_DIR="${0:A:h}"
APP_PATH="$1"

if [[ ! -d "$APP_PATH" ]]; then
    echo -n "App not found: $APP_PATH"
    exit 0
fi

BUNDLE_ID=$(/usr/bin/plutil -extract CFBundleIdentifier raw "$APP_PATH/Contents/Info.plist" 2>/dev/null)
if [[ -z "$BUNDLE_ID" ]]; then
    echo -n "No bundle identifier in $APP_PATH"
    exit 0
fi

MSG=$(/usr/bin/osascript "$SCRIPT_DIR/open_new_window.applescript" "$APP_PATH" "$BUNDLE_ID" 2>&1)
RC=$?
# osascript output is single-line on success; join lines so errors stay readable
MSG="${${MSG//$'\r'/ }//$'\n'/ }"
if (( RC != 0 )); then
    # osascript itself failed (e.g. Accessibility/Automation denied) — never silent
    echo -n "Error: ${MSG:-osascript failed (exit $RC)}"
    exit 0
fi
[[ -n "${MSG// /}" ]] && echo -n "$MSG"
exit 0
