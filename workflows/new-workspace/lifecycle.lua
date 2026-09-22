-- Small desktop operations. Every request owns its result, tasks and timers.
local M = {}

function M.new(root, deps)
    local self, contexts = {}, {}

    function self.run(request)
        local ctx = {tasks={}, timers={}, result={id=request.id, operation=request.operation, status='running'}}
        contexts[request.id] = ctx
        local result = ctx.result
        local mutation = request.operation ~= 'list' and request.operation ~= 'check'
                         and not (request.operation == 'close' and request.execute ~= true)
        local function finish(status, message, code)
            if ctx.finished then return end
            ctx.finished = true
            for _, timer in ipairs(ctx.timers) do timer:stop() end
            for _, task in ipairs(ctx.tasks) do if task:isRunning() then task:terminate() end end
            result.status, result.error, result.error_code = status, message, code
            deps.write(request.id, result)
            contexts[request.id] = nil
            if mutation then deps.setBusy(false) end
        end
        local function guard(fn)
            return function(...)
                if ctx.finished then return end
                local ok, err = pcall(fn, ...)
                if not ok then finish(ctx.mutated and 'uncertain' or 'failed', tostring(err), 'operation_failed') end
            end
        end
        local function after(delay, fn)
            local timer = hs.timer.doAfter(delay, guard(fn))
            table.insert(ctx.timers, timer)
        end
        local function helper(args, timeout, done)
            local settled = false
            local job = hs.task.new('/usr/bin/python3', guard(function(code, out, err)
                if settled then return end
                settled = true
                local data = hs.json.decode(out)
                if code ~= 0 or type(data) ~= 'table' or data.error then
                    finish(ctx.mutated and 'uncertain' or 'failed',
                           (type(data) == 'table' and data.error) or err or 'Invalid helper result', 'helper_failed')
                    return
                end
                done(data)
            end), args)
            assert(job, 'Could not prepare desktop helper')
            table.insert(ctx.tasks, job)
            assert(job:start(), 'Could not start desktop helper')
            after(timeout, function()
                if settled then return end
                settled = true
                finish('uncertain', 'Desktop helper timed out; inspect this operation before retrying', 'timeout')
            end)
        end
        local function copy(data)
            for key, value in pairs(data) do
                if key ~= 'id' and key ~= 'operation' and key ~= 'status' and key ~= 'error' then result[key] = value end
            end
        end
        local function verifySwitch(sid, previous)
            local deadline = hs.timer.secondsSinceEpoch() + 5
            local function poll()
                local active = hs.spaces.focusedSpace()
                if (sid and active == sid) or (not sid and active and active ~= previous) then
                    deps.observeSpace()
                    result.space_id = active
                    finish('complete')
                elseif hs.timer.secondsSinceEpoch() >= deadline then
                    finish('blocked', 'Desktop navigation was not observed. Run workspace list before retrying', 'navigation_unverified')
                else after(.15, poll) end
            end
            poll()
        end
        ctx.stop = function()
            ctx.stopReason = {message='Hammerspoon stopped; inspect completed work before retrying', code='worker_stopped'}
            if ctx.closeOwned and SpaceClose then SpaceClose.stop() end
            finish('uncertain', ctx.stopReason.message, ctx.stopReason.code)
        end
        deps.write(request.id, result) -- Admission acknowledgment before any helper/mutation.
        guard(function()
            helper({root .. '/desktop.py', 'resolve', hs.json.encode(request)}, 20, function(state)
                local operation = request.operation
                if operation == 'list' then copy(state); finish('complete'); return end
                if operation == 'check' then
                    copy(state)
                    result.busy = deps.busy()
                    result.checks.worker = true
                    result.checks.close_backend = SpaceClose ~= nil and type(SpaceClose.preview) == 'function'
                    if not result.checks.close_backend then table.insert(result.problems, 'Close backend is not loaded') end
                    if #result.problems > 0 then finish('blocked', table.concat(result.problems, '; '), 'not_ready')
                    else finish('complete') end
                    return
                end
                if operation == 'back' then
                    local previous = hs.spaces.focusedSpace()
                    assert(previous, 'Could not read current desktop')
                    local destination = deps.previousSpace()
                    ctx.mutated = true
                    if destination then
                        assert(hs.spaces.gotoSpace(destination), 'Could not return to previous desktop')
                    else
                        assert(hs.urlevent.openURL('doorplate://back'), 'Could not open Doorplate Back')
                    end
                    verifySwitch(destination, previous); return
                end
                local target = assert(state.target, 'Missing resolved desktop')
                local sid = tonumber(target.id)
                assert(sid and sid > 0 and sid <= 9007199254740991 and sid % 1 == 0, 'Invalid desktop ID')
                result.space_id, result.name = target.id, target.name ~= '' and target.name or 'Desktop ' .. target.number
                if operation == 'switch' then
                    deps.observeSpace()
                    if hs.spaces.focusedSpace() == sid then result.already_current=true; finish('complete'); return end
                    ctx.mutated = true
                    assert(hs.spaces.gotoSpace(sid), 'Could not switch to the selected desktop')
                    verifySwitch(sid); return
                end
                if operation == 'rename' then
                    ctx.mutated = true
                    helper({root .. '/desktop.py', 'rename', target.id, request.name,
                            request.space_id and 'any' or 'current'}, 80, function(data)
                        copy(data); finish('complete')
                    end)
                    return
                end
                assert(SpaceClose and type(SpaceClose.preview) == 'function', 'Close backend is not loaded')
                if request.execute ~= true then
                    local preview = SpaceClose.preview(sid)
                    if preview.error then finish('blocked', preview.error, 'preview_blocked'); return end
                    copy(preview)
                    result.recommended_command = 'workspace close --id ' .. target.id .. ' --yes'
                    finish('confirmation_required'); return
                end
                -- SpaceClose's own admission guard sees WorkspaceCreate.busy.
                -- Handoff is synchronous: no event can enter between these lines.
                deps.setBusy(false)
                local response = SpaceClose.request(sid, result.name,
                    {confirm=request.confirm ~= false, notify=request.notify == true}, guard(function(outcome)
                        copy(outcome)
                        local reason = ctx.stopReason
                        finish(outcome.status, reason and reason.message or outcome.error,
                               reason and reason.code or (outcome.error and 'close_blocked' or nil))
                    end))
                if response.error then finish('blocked', response.error, 'busy'); return end
                ctx.closeOwned, ctx.mutated = true, true
                deps.setBusy(true)
                after(240, function()
                    ctx.stopReason = {message='Close timed out; inspect this operation before retrying', code='timeout'}
                    SpaceClose.stop()
                    finish('uncertain', ctx.stopReason.message, ctx.stopReason.code)
                end)
            end)
        end)()
    end

    function self.stop()
        local pending = {}
        for _, ctx in pairs(contexts) do table.insert(pending, ctx) end
        for _, ctx in ipairs(pending) do ctx.stop() end
    end
    return self
end

return M
