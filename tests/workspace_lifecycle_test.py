"""Exercise request admission and lifecycle callbacks without desktop mutations."""

import pytest

from workspace_worker_test import fail_result_writes, runtime

SETUP = r"""
snapshot = {active='1',desktops={{id='1',name='Original',number=1},{id='2',name='Target',number=2}},
            target={id='2',name='Target',number=2},checks={},problems={}}
local oldNew = hs.task.new
hs.task.new = function(command, cb, args)
 if args[2] ~= 'resolve' then return oldNew(command,cb,args) end
 local job = {running=false}
 function job:isRunning() return self.running end
 function job:terminate() self.running=false end
 function job:start()
  self.running=true
  if hangResolve then return self end
  later(.01,function()self.running=false;cb(0,snapshot,'')end)
  return self
 end
 return job
end
local gotoSpace = hs.spaces.gotoSpace
hs.spaces.gotoSpace = function(sid)
 if noNavigation then return true end
 return gotoSpace(sid)
end
hs.urlevent = {openURL=function(url)
 urls=(urls or 0)+1
 if not noNavigation then focused=2 end
 return true
end}
SpaceClose = {
 busy=false,
 preview=function(sid)
  previews=(previews or 0)+1
  return {space_id=sid,windows={},shared=0,display='display',keeper=1}
 end,
 request=function(sid,label,options,callback)
  assert(not worker.busy, 'dispatcher did not hand off its busy guard')
  closeCalls=(closeCalls or 0)+1
  closeOptions=options
  closeCallback=callback
  SpaceClose.busy=true
  return {status='close_requested'}
 end,
 stop=function()
  SpaceClose.busy=false
  closeCallback({status='uncertain',space_id=2,error='worker stopped',removal_verified=false})
 end,
}
function submit(letter, operation, execute)
 local id=string.rep(letter,32)
 files['state/request.json']={id=id,expires=now+5,operation=operation,space_id='2',execute=execute,confirm=false}
 receive()
 return id
end
function result(letter) return files['state/'..string.rep(letter,32)..'.json'] end
"""


def setup():
    lua, worker = runtime()
    lua.globals().worker = worker
    lua.execute(SETUP)
    return lua, worker


@pytest.mark.parametrize("operation", ["switch", "close"])
def test_admission_write_failure_prevents_dispatch_and_releases_busy(operation):
    lua, worker = setup()
    fail_result_writes(lua)
    lua.globals().submit("b", operation, True)
    assert not worker.busy
    assert len(lua.globals().queue) == 0  # No resolution helper was started.
    assert lua.globals().focused == 1
    assert lua.globals().closeCalls is None
    lua.execute("hs.json.write=savedWrite")
    lua.globals().submit("c", "switch", False)
    lua.globals().pump()
    assert lua.globals().result("c")["status"] == "complete"


def test_terminal_write_failure_releases_busy_and_detaches_context():
    lua, worker = setup()
    fail_result_writes(lua, "result.status ~= 'running'")
    lua.globals().submit("b", "switch", False)
    lua.globals().pump()
    assert lua.globals().focused == 2
    assert not worker.busy
    assert lua.globals().result("b")["status"] == "running"
    attempts = lua.globals().writeAttempts
    worker.stop()
    assert lua.globals().writeAttempts == attempts


def test_read_result_write_failure_preserves_another_operations_busy_flag():
    lua, worker = setup()
    worker.busy = True
    fail_result_writes(lua, "result.status ~= 'running'")
    lua.globals().submit("b", "list", False)
    lua.globals().pump()
    assert worker.busy


def test_shutdown_write_failure_still_cancels_owned_close():
    lua, worker = setup()
    lua.globals().submit("b", "close", True)
    lua.execute("table.remove(queue,1).fn()")
    fail_result_writes(lua)
    worker.stop()
    assert not worker.busy
    assert not lua.globals().SpaceClose.busy
    attempts = lua.globals().writeAttempts
    lua.globals().pump()
    assert lua.globals().writeAttempts == attempts


def test_list_admitted_while_mutation_busy_and_does_not_clear_it():
    lua, worker = setup()
    worker.busy = True
    lua.globals().submit("b", "list", False)
    assert lua.globals().result("b")["status"] == "running"
    lua.globals().pump()
    assert lua.globals().result("b")["status"] == "complete"
    assert worker.busy
    lua.globals().submit("c", "rename", False)
    assert lua.globals().result("c")["status"] == "blocked"


def test_preview_never_executes_close_even_for_empty_target():
    lua, worker = setup()
    lua.globals().submit("b", "close", False)
    lua.globals().pump()
    result = lua.globals().result("b")
    assert result["status"] == "confirmation_required"
    assert result["space_id"] == 2
    assert "--id 2 --yes" in result["recommended_command"]
    assert lua.globals().closeCalls is None
    assert not worker.busy


def test_close_result_is_callback_owned_and_late_callback_cannot_overwrite():
    lua, worker = setup()
    lua.globals().submit("b", "close", True)
    # Run only the native resolution callback; keep the close pending.
    lua.execute("table.remove(queue,1).fn()")
    assert worker.busy
    assert lua.globals().result("b")["status"] == "running"
    lua.execute(
        "SpaceClose.busy=false;closeCallback({status='blocked',space_id=2,closed=1,removal_verified=false,error='App blocked',blocked_window={id=9,app='Editor'}})"
    )
    result = lua.globals().result("b")
    assert result["status"] == "blocked"
    assert result["closed"] == 1
    assert result["blocked_window"]["app"] == "Editor"
    assert not worker.busy
    lua.execute("closeCallback({status='complete'});pump()")
    assert lua.globals().result("b")["status"] == "blocked"


def test_stop_cancels_close_and_late_callbacks_without_focus_change():
    lua, worker = setup()
    lua.globals().submit("b", "close", True)
    lua.execute("table.remove(queue,1).fn()")
    worker.stop()
    lua.globals().pump()
    assert lua.globals().result("b")["status"] == "uncertain"
    assert lua.globals().result("b")["error_code"] == "worker_stopped"
    assert lua.globals().focused == 1
    assert not worker.busy


def test_close_timeout_retains_its_reason_and_confirmed_progress():
    lua, _ = setup()
    lua.globals().submit("b", "close", True)
    lua.globals().pump()
    result = lua.globals().result("b")
    assert result["status"] == "uncertain"
    assert result["error_code"] == "timeout"
    assert result["removal_verified"] is False


def test_switch_requires_observed_arrival_and_current_is_noop():
    lua, _ = setup()
    lua.globals().noNavigation = True
    lua.globals().submit("b", "switch", False)
    lua.globals().pump()
    assert lua.globals().result("b")["status"] == "blocked"
    lua.globals().focused = 2
    lua.globals().submit("c", "switch", False)
    lua.globals().pump()
    assert lua.globals().result("c")["status"] == "complete"
    assert lua.globals().result("c")["already_current"]
    assert lua.globals().urls is None


def test_back_no_transition_is_blocked():
    lua, _ = setup()
    lua.globals().noNavigation = True
    lua.globals().submit("b", "back", False)
    lua.globals().pump()
    assert lua.globals().result("b")["status"] == "blocked"


def test_back_survives_rename_without_doorplate_history():
    lua, worker = setup()
    lua.globals().submit("b", "switch", False)
    lua.globals().pump()
    assert worker.previousSpace() == 1
    lua.execute(
        "files['state/request.json']={id=string.rep('c',32),expires=now+5,operation='rename',name='test2',space_id='2'};receive();pump()"
    )
    assert lua.globals().result("c")["status"] == "complete"
    lua.execute("hs.urlevent.openURL=function()error('Doorplate history was reset')end")
    lua.globals().submit("d", "back", False)
    lua.globals().pump()
    assert lua.globals().result("d")["status"] == "complete"
    assert lua.globals().focused == 1
    assert (
        lua.globals().urls is None
    )  # Neither switch nor Back depends on Doorplate history.


def test_manual_navigation_updates_history_and_warming_does_not():
    lua, worker = setup()
    assert worker.previousSpace() is None
    lua.execute("focused=2;spaceChanged()")
    assert worker.previousSpace() == 1
    lua.execute(
        "WinJumpWarmTimer={};focused=3;spaceChanged();focused=2;spaceChanged();WinJumpWarmTimer=nil"
    )
    assert worker.previousSpace() == 1
    worker.stop()
    assert worker.spaceWatcher.stopped


def test_read_helper_timeout_does_not_clear_another_mutations_busy_flag():
    lua, worker = setup()
    worker.busy = True
    lua.globals().hangResolve = True
    lua.globals().submit("b", "list", False)
    lua.globals().pump()
    assert lua.globals().result("b")["status"] == "uncertain"
    assert worker.busy


def test_create_stop_preserves_progress_and_does_not_restore_focus():
    lua, worker = runtime()
    lua.execute(
        "files['state/request.json']={id=string.rep('a',32),expires=5,operation='create',name='Test',apps={{name='One',bundle='one',opener='chromium'}}};receive()"
    )
    worker.stop()
    lua.globals().focused = 2
    lua.globals().pump()
    result = lua.globals().files["state/" + "a" * 32 + ".json"]
    assert result["status"] == "uncertain"
    assert lua.globals().focused == 2
    assert len(lua.globals().spaces) == 2


def test_ambiguous_created_desktop_is_uncertain_with_candidates():
    lua, _ = runtime()
    lua.execute("hs.spaces.addSpaceToScreen=function()spaces={1,2,3,4};return true end")
    result = lua.globals().request(False)
    assert result["status"] == "uncertain"
    assert result["creation_attempted"]
    assert list(result["candidate_space_ids"].values()) == [3, 4]
    assert result["uncertain"]
