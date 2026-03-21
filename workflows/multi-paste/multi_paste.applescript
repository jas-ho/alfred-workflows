set runID to do shell script "uuidgen | tr '[:upper:]' '[:lower:]'"
set tmpPrefix to "/tmp/mp-" & runID
set frontAppFile to tmpPrefix & "-frontapp"
set pidFile to tmpPrefix & "-pid"
set startFile to tmpPrefix & "-start"
set resultFile to tmpPrefix & "-result"
set successFile to tmpPrefix & "-success"

-- 1. Record frontmost app IMMEDIATELY (before any focus change)
tell application "System Events"
    set frontAppID to bundle identifier of first application process whose frontmost is true
end tell
do shell script "echo " & quoted form of frontAppID & " > " & quoted form of frontAppFile

-- 2. Clear this run's temp files
do shell script "rm -f " & quoted form of pidFile & " " & quoted form of resultFile & " " & quoted form of startFile & " " & quoted form of successFile

-- 3. Ensure Terminal is running
try
    do shell script "open -a Terminal"
end try

delay 0.2

-- 4. Launch wrapper in Terminal (no window creation)
set wrapperCmd to "MP_PID_FILE=" & quoted form of pidFile & " MP_START_FILE=" & quoted form of startFile & " MP_RESULT_FILE=" & quoted form of resultFile & " MP_SUCCESS_FILE=" & quoted form of successFile & " $HOME/bin/multiclip-wrapper.sh"
tell application id "com.apple.Terminal"
    activate
    set mpTab to do script wrapperCmd
end tell

-- 5. Wait for PID file to appear (max 2s)
set pidFound to false
repeat 20 times
    try
        do shell script "test -f " & quoted form of pidFile
        set pidFound to true
        exit repeat
    end try
    delay 0.1
end repeat

if not pidFound then
    do shell script "rm -f " & quoted form of frontAppFile & " " & quoted form of pidFile & " " & quoted form of resultFile & " " & quoted form of startFile & " " & quoted form of successFile
    return ""
end if

-- 6. Wait for PID to exit (max 120s)
set wrapperPID to do shell script "cat " & quoted form of pidFile
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
    set startTime to (do shell script "cat " & quoted form of startFile & " 2>/dev/null || echo 0") as integer
    set resultMtime to (do shell script "stat -f %m " & quoted form of resultFile & " 2>/dev/null || echo 0") as integer
    do shell script "test -f " & quoted form of successFile
    if resultMtime > startTime then
        set output to do shell script "cat " & quoted form of resultFile & " 2>/dev/null"
    end if
end try

-- 8. Return focus to original app
if output is not "" then
    set frontAppID to do shell script "cat " & quoted form of frontAppFile & " 2>/dev/null"
    if frontAppID is not "" then
        tell application id frontAppID to activate
    end if
end if

-- 9. Cleanup this run's temp files
do shell script "rm -f " & quoted form of frontAppFile & " " & quoted form of pidFile & " " & quoted form of resultFile & " " & quoted form of startFile & " " & quoted form of successFile

return output
