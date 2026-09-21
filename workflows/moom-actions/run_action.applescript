on run argv
    set selectedAction to item 1 of argv
    tell application "Moom"
        if selectedAction is "__CENTER__" then
            center frontmost window
        else
            run selectedAction
        end if
    end tell
end run
