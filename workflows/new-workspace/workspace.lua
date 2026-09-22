-- Runs in Hammerspoon's GUI session. CLI requests are data, never Lua source.
local M = {}

local function contains(xs, value)
    for _, x in ipairs(xs or {}) do if x == value then return true end end
    return false
end

local function appWindows(bundle)
    local app = hs.application.get(bundle)
    local result = {}
    if app then
        for _, w in ipairs(app:allWindows()) do
            if w:isStandard() then result[w:id()] = w end
        end
    end
    return result
end

function M.start(root, dir)
    local self = {busy=false}
    local current
    -- Doorplate restarts when naming a desktop, so its in-memory Back history
    -- cannot own navigation. Observe stable IDs, including manual Space changes.
    local activeSpace, previousSpace = hs.spaces.focusedSpace(), nil
    local function observeSpace()
        if WinJumpWarmTimer ~= nil then return end
        local sid = hs.spaces.focusedSpace()
        if not sid or sid == activeSpace then return end
        if activeSpace and hs.spaces.spaceType(activeSpace) == 'user' then previousSpace = activeSpace end
        activeSpace = sid
    end
    function self.previousSpace()
        observeSpace()
        if previousSpace and previousSpace ~= activeSpace and hs.spaces.spaceType(previousSpace) == 'user' then
            return previousSpace
        end
    end
    self.spaceWatcher = hs.spaces.watcher.new(observeSpace):start()
    local startupRequest = hs.json.read(dir .. '/request.json')
    local startupID = type(startupRequest) == 'table' and startupRequest.id or nil
    local function write(id, result)
        local path = dir .. '/' .. id .. '.json'
        assert(hs.json.write(result, path .. '.tmp', false, true))
        assert(os.rename(path .. '.tmp', path))
    end
    local function busy()
        return self.busy or SpacePruneBusy or (SpaceClose and SpaceClose.busy) or WinJumpWarmTimer ~= nil
    end
    local lifecycle = dofile(root .. '/lifecycle.lua').new(root, {
        write=write, busy=busy, setBusy=function(value) self.busy=value end,
        previousSpace=self.previousSpace, observeSpace=observeSpace,
    })

    local function create(request)
        local ctx = {request=request, result={id=request.id, operation='create', status='running',
                     name=request.name, windows={}, stage='preflight'}, timers={}, tasks={}}
        current = ctx
        self.busy = true
        local result = ctx.result
        local finish, fail
        local function save() write(request.id, result) end
        local function trySave()
            local ok, err = pcall(save)
            if not ok then print('workspace: could not save result ' .. request.id .. ': ' .. tostring(err)) end
            return ok, err
        end
        ctx.stop = function()
            if ctx.finished then return end
            ctx.finished = true
            for _, timer in ipairs(ctx.timers) do timer:stop() end
            for _, task in ipairs(ctx.tasks) do if task:isRunning() then task:terminate() end end
            result.status, result.error_code = 'uncertain', 'worker_stopped'
            result.error = 'Hammerspoon stopped; inspect completed work before retrying'
            result.return_skipped = 'worker_stopped'
            current, self.busy = nil, false
            trySave()
        end
        local function checkFocus()
            if ctx.expectedSpace and hs.spaces.focusedSpace() ~= ctx.expectedSpace then
                result.focus_changed = true
                error('Desktop changed during setup; completed work was kept', 0)
            end
        end
        local function guard(fn)
            return function(...)
                if current ~= ctx or ctx.finished then return end
                local ok, err = pcall(fn, ...)
                if not ok then fail(tostring(err)) end
            end
        end
        local function after(seconds, fn)
            local timer = hs.timer.doAfter(seconds, guard(fn))
            table.insert(ctx.timers, timer)
            return timer
        end
        local function waitFor(predicate, seconds, done)
            local deadline = hs.timer.secondsSinceEpoch() + seconds
            local function poll()
                if predicate() then done(true)
                elseif hs.timer.secondsSinceEpoch() >= deadline then done(false)
                else after(.15, poll) end
            end
            poll()
        end
        local function switchTo(destination, done)
            local function attempt(retry)
                if hs.spaces.focusedSpace() == destination then done(true); return end
                local ok, err = pcall(function() assert(hs.spaces.gotoSpace(destination)) end)
                local function checked(reached)
                    if reached then done(true); return end
                    pcall(hs.spaces.closeMissionControl)
                    if retry then after(.5, function() attempt(false) end)
                    else done(false, tostring(err or 'Desktop switch was not confirmed')) end
                end
                if ok then
                    waitFor(function() return hs.spaces.focusedSpace() == destination end, 3, checked)
                else checked(false) end
            end
            attempt(true)
        end
        local function publish()
            ctx.finished = true
            for _, timer in ipairs(ctx.timers) do timer:stop() end
            result.status = result.error and (result.space_id and 'partial'
                or (result.creation_attempted and 'uncertain' or 'failed')) or 'complete'
            if result.status == 'uncertain' then result.uncertain = true end
            self.busy = false
            current = nil
            trySave()
            if request.notify and not result.error then
                hs.alert.show('Created ' .. request.name, 4)
            end
        end
        finish = function()
            if ctx.finishing then return end
            ctx.finishing = true
            for _, task in ipairs(ctx.tasks) do
                if task:isRunning() then result.uncertain = true; task:terminate() end
            end
            if result.focus_changed or (ctx.expectedSpace and hs.spaces.focusedSpace() ~= ctx.expectedSpace) then
                result.focus_changed = true
                result.return_skipped = 'desktop_changed'
                result.returned = false
                result.error = result.error or 'Desktop changed during setup; completed work was kept'
                result.failed_stage = result.failed_stage or result.stage
                publish(); return
            end
            result.stage = 'return'
            -- Storage may already be unavailable when fail() calls finish().
            -- Restoration and cleanup must not depend on another successful write.
            local saved, err = trySave()
            if not saved then
                result.error = result.error or tostring(err)
                result.failed_stage = result.failed_stage or result.stage
            end
            local destination = request.stay and result.space_id or result.origin_id
            if not destination then publish(); return end
            switchTo(destination, function(reached, err)
                result.returned = reached
                if not reached then
                    result.return_error = err
                    result.error = result.error or result.return_error
                end
                -- Focus only the exact original window, if it still belongs to the original Space.
                if reached and not request.stay and ctx.focus then
                    local spaces = hs.spaces.windowSpaces(ctx.focus:id())
                    if contains(spaces, destination) then pcall(function() ctx.focus:focus() end) end
                end
                publish()
            end)
        end
        fail = function(message)
            result.error = result.error or message
            result.failed_stage = result.failed_stage or result.stage
            if ctx.finishing then publish() else finish() end
        end
        local function task(command, args, timeout, done)
            local settled = false
            local timer
            local job = hs.task.new(command, guard(function(code, out, err)
                if settled or ctx.finishing then return end
                settled = true
                if timer then timer:stop() end
                done(code, out, err)
            end), args)
            assert(job, 'Could not start helper: ' .. command)
            table.insert(ctx.tasks, job)
            assert(job:start(), 'Could not launch helper: ' .. command)
            timer = after(timeout, function()
                if settled then return end
                settled = true
                job:terminate()
                result.uncertain = true
                fail('Helper timed out; its outcome is uncertain. Do not repeat create automatically.')
            end)
        end
        local function helper(mode, index, done)
            local args = {root .. '/open_app.py', mode, hs.json.encode(request)}
            if index then table.insert(args, tostring(index - 1)) end
            task('/usr/bin/python3', args, 65, done)
        end
        local function onTarget()
            checkFocus()
            assert(hs.spaces.focusedSpace() == result.space_id,
                   'Desktop changed during setup; completed windows were kept')
        end
        local function layout()
            onTarget()
            local lastWindow
            for _, item in ipairs(result.windows) do
                local w = appWindows(item.bundle)[item.id]
                local spaces = hs.spaces.windowSpaces(item.id)
                assert(w and w:application():pid() == item.pid and type(spaces) == 'table'
                       and #spaces == 1 and spaces[1] == result.space_id,
                       'A new window moved or disappeared during setup')
                lastWindow = w
            end
            if lastWindow then lastWindow:focus() end
            if request.layout == 'none' then finish(); return end
            result.stage = 'layout'; save()
            local screen = hs.screen.find(ctx.display)
            assert(screen, 'Display disappeared')
            local frame = screen:frame()
            local n = #result.windows
            for i, item in ipairs(result.windows) do
                local w = appWindows(item.bundle)[item.id]
                assert(w and w:application():pid() == item.pid, 'A new window disappeared before layout')
                local x, y, width, height = (i-1)/n, 0, 1/n, 1
                if request.layout == 'main-stack' and n > 1 then
                    if i == 1 then x, y, width, height = 0, 0, .5, 1
                    else x, y, width, height = .5, (i-2)/(n-1), .5, 1/(n-1) end
                end
                w:setFrame(hs.geometry.rect(frame.x+x*frame.w,frame.y+y*frame.h,
                                           width*frame.w,height*frame.h), 0)
            end
            finish()
        end
        local openNext
        openNext = function(index)
            local spec = request.apps[index]
            if not spec then layout(); return end
            onTarget()
            result.stage = 'open:' .. spec.name; save()
            local before = appWindows(spec.bundle)
            local function identify(code, output, err)
                local details = {}
                if output ~= '' then details = hs.json.decode(output) or {} end
                if details.tmux_session then result.tmux_session = details.tmux_session; save() end
                if code ~= 0 then
                    result.uncertain = true
                    fail(spec.name .. ': ' .. (err ~= '' and err or output)); return
                end
                local found = {}
                waitFor(function()
                    found = {}
                    for id, w in pairs(appWindows(spec.bundle)) do
                        if not before[id] then table.insert(found, w) end
                    end
                    return #found > 0
                end, 5, function(appeared)
                    if not appeared or #found ~= 1 then
                        result.uncertain = true
                        result.candidate_ids = {}
                        for _, w in ipairs(found) do table.insert(result.candidate_ids, w:id()) end
                        fail(spec.name .. ': could not identify exactly one new window'); return
                    end
                    local w = found[1]
                    local item = {id=w:id(),pid=w:application():pid(),bundle=spec.bundle,
                                  app=spec.name,details=details}
                    table.insert(result.windows, item)
                    if details.tmux_session then result.tmux_session = details.tmux_session end
                    save()
                    waitFor(function()
                        local spaces = hs.spaces.windowSpaces(w:id())
                        item.spaces = spaces
                        return type(spaces) == 'table' and #spaces == 1 and spaces[1] == result.space_id
                    end, 3, function(placed)
                        item.placed = placed
                        if not placed then fail(spec.name .. ': new window is not on the new desktop'); return end
                        onTarget()
                        openNext(index + 1)
                    end)
                end)
            end
            if spec.opener ~= 'generic' then
                if spec.opener == 'ghostty' then
                    result.tmux_session = request.tmux_session
                    save()
                end
                helper('open', index, identify); return
            end
            local app = hs.application.get(spec.bundle)
            if not app then
                task('/usr/bin/open', {'-g', '-a', spec.app}, 15, identify)
            else
                local menu = spec.menu or {'File', 'New Window'}
                local item = app:findMenuItem(menu)
                assert(item and item.enabled, spec.name .. ': no enabled new-window menu; set menu in the recipe')
                assert(app:selectMenuItem(menu), spec.name .. ': new-window command failed')
                identify(0, '', '')
            end
        end
        local function enter()
            checkFocus()
            result.stage = 'enter'; save()
            switchTo(result.space_id, function(reached)
                assert(reached, 'Could not enter the new desktop')
                ctx.expectedSpace = result.space_id
                after(.5, function() openNext(1) end)
            end)
        end
        local function addDesktop()
            checkFocus()
            result.stage = 'create'; save()
            local before = hs.spaces.allSpaces()[ctx.display]
            assert(before, 'Display disappeared')
            result.creation_attempted = true; save()
            assert(hs.spaces.addSpaceToScreen(ctx.display))
            local added = {}
            waitFor(function()
                added = {}
                for _, sid in ipairs(hs.spaces.allSpaces()[ctx.display] or {}) do
                    if not contains(before, sid) then table.insert(added, sid) end
                end
                return #added > 0
            end, 3, function(created)
                if not created or #added ~= 1 then result.candidate_space_ids = added end
                assert(created and #added == 1, 'Could not identify the newly created desktop')
                result.space_id = added[1]
                checkFocus()
                result.stage = 'rename'; save()
                task('/usr/bin/python3', {root .. '/desktop.py',
                     'rename', tostring(result.space_id), request.name, 'any'}, 80, function(code, out, err)
                    assert(code == 0, 'Naming failed: ' .. err .. out)
                    enter()
                end)
            end)
        end
        guard(function()
            result.origin_id = hs.spaces.focusedSpace()
            ctx.expectedSpace = result.origin_id
            ctx.focus = hs.window.focusedWindow()
            ctx.display = hs.spaces.spaceDisplay(result.origin_id)
            assert(hs.spaces.spaceType(result.origin_id) == 'user', 'Start from a regular desktop')
            save()
            after(240, function() result.uncertain=true; fail('Workspace setup timed out') end)
            helper('preflight', nil, function(code, out, err)
                assert(code == 0, 'Preflight failed: ' .. err .. out)
                addDesktop()
            end)
        end)()
    end

    local function receive()
        if self.stopped then return end
        local request = hs.json.read(dir .. '/request.json')
        if type(request) ~= 'table' or type(request.id) ~= 'string'
            or not request.id:match('^[a-f0-9]+$') or #request.id ~= 32 then return end
        if request.id == startupID then return end
        if hs.fs.attributes(dir .. '/' .. request.id .. '.json') then return end
        local function reject(message)
            write(request.id, {id=request.id,operation=request.operation,status='failed',error=message})
        end
        if type(request.expires) ~= 'number' or request.expires < hs.timer.secondsSinceEpoch() then
            reject('Request expired; no action taken'); return
        end
        local operations = {create=true,list=true,check=true,switch=true,rename=true,back=true,close=true}
        if not operations[request.operation] then reject('Unknown operation'); return end
        local mutation = request.operation ~= 'list' and request.operation ~= 'check'
                         and not (request.operation == 'close' and request.execute ~= true)
        if mutation and busy() then
            write(request.id, {id=request.id,operation=request.operation,status='blocked',
                  error_code='busy',error='Another desktop operation is in progress'}); return
        end
        if request.operation ~= 'create' then
            if mutation then self.busy=true end
            lifecycle.run(request); return
        end
        if type(request.name) ~= 'string' or request.name == '' or type(request.apps) ~= 'table'
            or #request.apps < 1 or #request.apps > 8 then reject('Invalid create request'); return end
        create(request)
    end
    self.watcher = hs.pathwatcher.new(dir, receive):start()
    function self.stop()
        if self.stopped then return end
        self.stopped = true
        self.watcher:stop()
        self.spaceWatcher:stop()
        if current then current.stop() end
        lifecycle.stop()
    end
    -- Do not replay a request left by an interrupted process or previous login.
    return self
end

return M
