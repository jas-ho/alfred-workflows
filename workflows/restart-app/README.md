# Restart App

Type `ra` followed by Space to browse running apps; `rr`, `restart`, and `relaunch` are aliases on the same input. Search words in any order, app initials (`ME` for Microsoft Edge), or compact names (`TextEdit`). Rows use the app’s own icon and Alfred learns frequently selected apps.

Return restarts the selected app. Option+Return quits without reopening. Command+Return hides it from this picker; `rexclude` opens the exclusion file, where removing a path makes that app visible again. The file lives in Alfred’s workflow data directory as `excluded-apps.txt`, so rebuilding the workflow does not lose preferences.

Restart means a normal quit followed by reopening the same application bundle. The selected PID, launch time, and path must still match. The workflow waits up to 30 seconds for exit; a cancelled quit or unanswered save prompt stops the restart. It never force-quits. Reopening requests the app’s normal startup behavior; restoration of windows depends on that app. It does not restore the previous process’s command-line arguments.

The native AppKit helper lists registered applications and requests termination without System Events scripting. Finder, Alfred, prohibited/background-only processes, and nested helper bundles are excluded. A graphical login session is required. Tests use a mocked lifecycle; they never quit live apps.

This replaces the two previously installed Restart App workflows. Both original workflows are disabled, with backup copies outside Alfred under the repository’s ignored `.backups/` directory. Existing excluded paths are migrated on this machine. Legacy `restart`, `relaunch`, `rr`, and `rexclude` keywords remain available.
