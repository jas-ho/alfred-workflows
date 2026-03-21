-- 1. Record frontmost app IMMEDIATELY (before any focus change)
tell application "System Events"
    set frontAppID to bundle identifier of first application process whose frontmost is true
end tell
do shell script "echo " & quoted form of frontAppID & " > /tmp/mp-frontapp"

-- 2. Clear stale temp files
do shell script "rm -f /tmp/mp-pid /tmp/mp-result /tmp/mp-start /tmp/mp-success"

-- 3. Ensure Terminal is running
try
    do shell script "open -a Terminal"
end try

delay 0.2

-- 4. Launch wrapper in Terminal (no window creation)
tell application id "com.apple.Terminal"
    activate
    set mpTab to do script "$HOME/bin/multiclip-wrapper.sh"
end tell

-- 5. Wait for PID file to appear (max 2s)
set pidFound to false
repeat 20 times
    try
        do shell script "test -f /tmp/mp-pid"
        set pidFound to true
        exit repeat
    end try
    delay 0.1
end repeat

if not pidFound then
    return ""
end if

-- 6. Wait for PID to exit (max 120s)
set wrapperPID to do shell script "cat /tmp/mp-pid"
set waited to 0
repeat while waited < 120
    try
        do shell script "ps -p " & wrapperPID & " > /dev/null 2>&1"
        delay 0.1
        set waited to waited + 0.1
    on error
        exit repeat
    end try
end repeat

-- 7. Read result if success marker exists and is fresh
set output to ""
try
    set startTime to (do shell script "cat /tmp/mp-start 2>/dev/null || echo 0") as integer
    set resultMtime to (do shell script "stat -f %m /tmp/mp-result 2>/dev/null || echo 0") as integer
    do shell script "test -f /tmp/mp-success"
    if resultMtime > startTime then
        set output to do shell script "cat /tmp/mp-result 2>/dev/null"
    end if
end try

-- 8. Return focus to original app
if output is not "" then
    set frontAppID to do shell script "cat /tmp/mp-frontapp 2>/dev/null"
    if frontAppID is not "" then
        tell application id frontAppID to activate
    end if
end if

return output
