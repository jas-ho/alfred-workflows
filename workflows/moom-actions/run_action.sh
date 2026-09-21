#!/bin/sh
cd "$(dirname "$0")" || exit 1
exec /usr/bin/osascript ./run_action.applescript "$@"
