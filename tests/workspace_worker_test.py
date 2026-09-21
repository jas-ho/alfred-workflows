"""Exercise the GUI state machine in Lua without touching the desktop."""

from pathlib import Path

import pytest
from lupa import LuaRuntime

MODULE = Path(__file__).resolve().parents[1] / "workflows/new-workspace/workspace.lua"
FIXTURE = r"""
now, queue, files, wins, jobs, focused, spaces = 0, {}, {}, {}, {}, 1, {1,2}
function later(delay, fn)
 local t={at=now+delay,fn=fn}; function t:stop() self.stopped=true end
 table.insert(queue,t);return t
end
function pump()
 for _=1,5000 do
  table.sort(queue,function(a,b)return a.at<b.at end)
  local t=table.remove(queue,1);if not t then return end
  if not t.stopped then now=t.at;t.fn() end
 end
 error('timer loop')
end
function add(id, bundle, sid)
 local w={wid=id,bundle=bundle,spaces={sid},pid=50}
 function w:id()return self.wid end
 function w:isStandard()return true end
 function w:application()return {pid=function()return self.pid end}end
 function w:focus()lastFocus=self.wid end
 function w:setFrame(f)self.frame=f end
 wins[id]=w;return w
end
function app(bundle)
 local a={}
 function a:allWindows()local r={};for _,w in pairs(wins)do if w.bundle==bundle then table.insert(r,w)end end;return r end
 function a:findMenuItem()return {enabled=true}end
 function a:selectMenuItem()add(200,bundle,focused);return true end
 return a
end
os.rename=function(a,b)files[b]=files[a];files[a]=nil;return true end
hs={
 json={read=function(p)return files[p]end,decode=function(x)if x=='{}' then return {} end;return x end,encode=function(x)return x end,
  write=function(x,p)files[p]=x;return true end},
 fs={attributes=function(p)return files[p]~=nil end},
 pathwatcher={new=function(_,fn)receive=fn;return {start=function(s)return s end}end},
 timer={doAfter=later,secondsSinceEpoch=function()return now end},
 application={get=app},
 window={focusedWindow=function()return originalWindow end},
 screen={find=function()return {frame=function()return {x=0,y=0,w=1200,h=900}end}end},
 geometry={rect=function(x,y,w,h)return {x=x,y=y,w=w,h=h}end},
 spaces={focusedSpace=function()return focused end,spaceDisplay=function()return 'display' end,
  spaceType=function()return 'user'end,allSpaces=function()return {display=spaces}end,
  addSpaceToScreen=function()spaces={1,2,3};return true end,
  closeMissionControl=function()end,
  gotoSpace=function(s)
   if enterFailsOnce and s==3 then enterFailsOnce=false;return nil,'child is nil' end
   if not (returnFails and s==1)then focused=s end;return true
  end,
  windowSpaces=function(id)return wins[id] and wins[id].spaces or {}end},
 alert={show=function()end},
 task={new=function(command,cb,args)
  local t={running=false};table.insert(jobs,args)
  function t:isRunning()return self.running end
  function t:terminate()self.running=false end
  function t:start()
   self.running=true
   if hangOpen and args[2]=='open' then return self end
   later(.01,function()
    self.running=false
    if args[2]=='preflight' and preflightFails then cb(1,'','prerequisite missing');return end
    if args[2]=='rename' and renameFails then cb(1,'','naming failed');return end
    if args[2]=='open' then
     local idx=tonumber(args[4])+1;local spec=args[3].apps[idx]
     if failSecond and idx==2 then cb(1,'','second app failed');return end
     add(100+idx,spec.bundle,wrongSpace and 1 or focused)
     if ambiguous then add(900,spec.bundle,focused)end
     cb(0,'{}','');return
    end
    cb(0,'{}','')
   end);return self
  end
  return t
 end}
}
function request(stay)
 files['state/request.json']={id=string.rep('a',32),expires=now+5,operation='create',name='Test',
  stay=stay,layout='columns',directory='/tmp',apps={
   {name='One',bundle='one',opener='chromium'},
   {name='Two',bundle='two',opener='obsidian'}}}
 receive();pump()
 return files['state/'..string.rep('a',32)..'.json']
end
"""


def runtime():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(FIXTURE)
    module = lua.execute(MODULE.read_text())
    worker = module.start("root", "state")
    return lua, worker


def test_default_return_layout_and_focus():
    lua, worker = runtime()
    result = lua.globals().request(False)
    assert result["status"] == "complete"
    assert lua.globals().focused == 1
    assert lua.globals().lastFocus == 102
    assert lua.globals().wins[101]["frame"]["x"] == 0
    assert lua.globals().wins[102]["frame"]["x"] == 600
    assert not worker.busy


def test_stay_targets_new_desktop():
    lua, _ = runtime()
    result = lua.globals().request(True)
    assert result["status"] == "complete"
    assert lua.globals().focused == 3


def test_transient_switch_failure_retries_switch_not_creation():
    lua, _ = runtime()
    lua.globals().enterFailsOnce = True
    result = lua.globals().request(False)
    assert result["status"] == "complete"
    assert len(result["windows"]) == 2
    assert len([a for a in lua.globals().jobs.values() if a[2] == "open"]) == 2


@pytest.mark.parametrize("original_space,expected_focus", [(1, 700), (2, 102)])
def test_original_window_only_focused_if_still_on_origin(
    original_space, expected_focus
):
    lua, _ = runtime()
    lua.globals().originalWindow = lua.globals().add(700, "old", original_space)
    result = lua.globals().request(False)
    assert result["status"] == "complete"
    assert lua.globals().lastFocus == expected_focus


@pytest.mark.parametrize(
    "flag,stage,count,status",
    [
        ("preflightFails", "preflight", 0, "failed"),
        ("renameFails", "rename", 0, "partial"),
        ("failSecond", "open:Two", 1, "partial"),
        ("wrongSpace", "open:One", 1, "partial"),
        ("ambiguous", "open:One", 0, "partial"),
        ("hangOpen", "open:One", 0, "partial"),
    ],
)
def test_failure_preserves_progress_returns_and_never_retries(
    flag, stage, count, status
):
    lua, worker = runtime()
    lua.globals()[flag] = True
    result = lua.globals().request(False)
    assert result["status"] == status
    assert result["failed_stage"] == stage
    assert len(result["windows"]) == count
    assert lua.globals().focused == 1
    assert not worker.busy
    opens = [args for args in lua.globals().jobs.values() if args[2] == "open"]
    assert len(opens) <= 2


def test_restore_failure_is_not_success():
    lua, _ = runtime()
    lua.globals().returnFails = True
    result = lua.globals().request(False)
    assert result["status"] == "partial"
    assert not result["returned"]
    assert result["return_error"]


def test_completed_request_is_not_replayed():
    lua, _ = runtime()
    lua.globals().request(False)
    before = len(lua.globals().jobs)
    lua.globals().receive()
    lua.globals().pump()
    assert len(lua.globals().jobs) == before


def test_startup_request_is_never_replayed_on_another_filesystem_event():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(FIXTURE)
    lua.execute(
        "files['state/request.json']={id=string.rep('a',32),expires=5,operation='check'}"
    )
    module = lua.execute(MODULE.read_text())
    module.start("root", "state")
    lua.globals().receive()
    assert lua.globals().files["state/" + "a" * 32 + ".json"] is None
