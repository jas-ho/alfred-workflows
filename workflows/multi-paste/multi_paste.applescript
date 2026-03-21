on run argv
set scriptDir to item 1 of argv
set runID to do shell script "uuidgen | tr '[:upper:]' '[:lower:]'"
set tmpPrefix to "/tmp/mp-" & runID
set frontAppFile to tmpPrefix & "-frontapp"
set pidFile to tmpPrefix & "-pid"
set startFile to tmpPrefix & "-start"
set resultFile to tmpPrefix & "-result"
set successFile to tmpPrefix & "-success"
set terminalWasRunning to false

-- 1. Record frontmost app IMMEDIATELY (before any focus change)
tell application "System Events"
    set frontAppID to bundle identifier of first application process whose frontmost is true
    set terminalWasRunning to (exists process "Terminal")
end tell
do shell script "echo " & quoted form of frontAppID & " > " & quoted form of frontAppFile

-- 2. Clear this run's temp files
do shell script "rm -f " & quoted form of pidFile & " " & quoted form of resultFile & " " & quoted form of startFile & " " & quoted form of successFile

-- 3. Launch wrapper in Terminal
set wrapperPath to scriptDir & "/multiclip-wrapper.sh"
set wrapperCmd to "MP_PID_FILE=" & quoted form of pidFile & " MP_START_FILE=" & quoted form of startFile & " MP_RESULT_FILE=" & quoted form of resultFile & " MP_SUCCESS_FILE=" & quoted form of successFile & " " & quoted form of wrapperPath
tell application id "com.apple.Terminal"
    activate
    if terminalWasRunning then
        set mpTab to do script wrapperCmd
    else
        set mpWindow to front window
        set mpTab to selected tab of mpWindow
        do script wrapperCmd in mpTab
    end if
end tell

-- 4. Wait for PID file to appear (max 2s)
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
    try
        if terminalWasRunning then
            tell application id "com.apple.Terminal"
                if exists mpTab then
                    if (count of tabs of (window of mpTab)) > 1 then
                        close mpTab
                    else
                        close (window of mpTab)
                    end if
                end if
            end tell
        else
            tell application id "com.apple.Terminal"
                if (exists mpTab) and (busy of mpTab is false) then
                    close (window of mpTab)
                end if
            end tell
        end if
    end try
    do shell script "rm -f " & quoted form of frontAppFile & " " & quoted form of pidFile & " " & quoted form of resultFile & " " & quoted form of startFile & " " & quoted form of successFile
    return ""
end if

-- 5. Wait for PID to exit (max 120s)
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

-- 6. Read result if success marker exists and is fresh
set output to ""
try
    set startTime to (do shell script "cat " & quoted form of startFile & " 2>/dev/null || echo 0") as integer
    set resultMtime to (do shell script "stat -f %m " & quoted form of resultFile & " 2>/dev/null || echo 0") as integer
    do shell script "test -f " & quoted form of successFile
    if resultMtime > startTime then
        set output to do shell script "cat " & quoted form of resultFile & " 2>/dev/null"
    end if
end try

-- 7. Return focus to original app
if output is not "" then
    set frontAppID to do shell script "cat " & quoted form of frontAppFile & " 2>/dev/null"
    if frontAppID is not "" then
        tell application id frontAppID to activate
    end if
end if

-- 8. Close the Terminal tab/window created for this run
try
    if terminalWasRunning then
        tell application id "com.apple.Terminal"
            if (exists mpTab) and (busy of mpTab is false) then
                if (count of tabs of (window of mpTab)) > 1 then
                    close mpTab
                else
                    close (window of mpTab)
                end if
            end if
        end tell
    else
        tell application id "com.apple.Terminal"
            if (exists mpTab) and (busy of mpTab is false) then
                close (window of mpTab)
            end if
        end tell
    end if
end try

-- 9. Cleanup this run's temp files
do shell script "rm -f " & quoted form of frontAppFile & " " & quoted form of pidFile & " " & quoted form of resultFile & " " & quoted form of startFile & " " & quoted form of successFile

return output
end run
