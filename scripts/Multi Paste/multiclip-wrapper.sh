#!/bin/bash
# multiclip-wrapper.sh - PID management wrapper for Alfred integration

set -euo pipefail

# Add fzf to PATH (installed at ~/.fzf/bin)
export PATH="$HOME/.fzf/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

PID_FILE="/tmp/mp-pid"
START_FILE="/tmp/mp-start"
RESULT_FILE="/tmp/mp-result"
SUCCESS_FILE="/tmp/mp-success"

# Write our PID immediately so AppleScript can track us
echo $$ > "$PID_FILE"

# Write start timestamp for freshness check
date +%s > "$START_FILE"

# Clear any stale result/success from previous runs
> "$RESULT_FILE"
rm -f "$SUCCESS_FILE"

# Run main script
~/bin/multiclip.py
exit_code=$?

# If cancelled or error, ensure result is empty and no success marker
if [[ $exit_code -ne 0 ]]; then
    > "$RESULT_FILE"
    rm -f "$SUCCESS_FILE"
fi

exit $exit_code
