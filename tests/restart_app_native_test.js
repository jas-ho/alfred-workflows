const assert = require('node:assert/strict');
const {restartApplication} = require('../workflows/restart-app/native.js');
const target = {pid: 123, path: '/Applications/Quotes " & Comma,.app', launched: 1234};
function fixture(mode = 'normal') {
    let current = {...target}, now = 0, quits = 0, opens = [];
    return {
        api: {
            lookup: () => current,
            quit: () => { quits++; return mode !== 'refuse'; },
            now: () => now,
            wait: seconds => {now += seconds; if (mode === 'normal') current = null;},
            open: path => {opens.push(path); return mode !== 'openFail';}
        },
        state: () => ({quits, opens}),
        replace: value => {current = value;}
    };
}
let f = fixture();
assert.equal(restartApplication(f.api, target, 'restart').status, 'reopen_requested');
assert.deepEqual(f.state(), {quits: 1, opens: [target.path]});
f = fixture(); restartApplication(f.api, target, 'quit'); assert.equal(f.state().opens.length, 0);
for (const mode of ['prompt', 'refuse']) {
    f = fixture(mode); assert.throws(() => restartApplication(f.api, target, 'restart'));
    assert.equal(f.state().opens.length, 0);
}
for (const changed of [null, {...target, path:'/Applications/Other.app'}, {...target, launched:9999}]) {
    f = fixture(); f.replace(changed);
    assert.throws(() => restartApplication(f.api, target, 'restart'));
    assert.equal(f.state().quits, 0);
}
f = fixture(); assert.throws(() => restartApplication(f.api, target, 'force')); assert.equal(f.state().quits, 0);
f = fixture(); assert.throws(() => restartApplication(f.api, {...target, pid: -1}, 'restart')); assert.equal(f.state().quits, 0);
f = fixture(); f.api.open = () => false; assert.throws(() => restartApplication(f.api, target, 'restart'), /could not be reopened/);
console.log('Restart lifecycle contracts passed');
f = fixture('prompt');
f.api.wait = () => f.replace({...target, launched: 5678});
assert.throws(() => restartApplication(f.api, target, 'restart'), /identity changed/);
assert.equal(f.state().opens.length, 0);
// Exercise the real AppKit adapter: eligibility changes must not imply exit.
const vm = require('node:vm'), fs = require('node:fs');
let waits = 0, reopenedAt = -1;
const running = {isNil:()=>false, terminated:false, activationPolicy:0,
    bundleURL:{isNil:()=>false,path:target.path}, launchDate:{isNil:()=>false,timeIntervalSince1970:target.launched},
    bundleIdentifier:'test.app', localizedName:'Test App', processIdentifier:target.pid, terminate:true};
const context = {ObjC:{import:()=>{},unwrap:x=>x}, $:{
    NSWorkspace:{sharedWorkspace:{openURL:()=>{reopenedAt=waits;return true;}}},
    NSRunningApplication:{runningApplicationWithProcessIdentifier:()=>running},
    NSRunLoop:{currentRunLoop:{runUntilDate:()=>{waits++;running.activationPolicy=2;if(waits===2)running.terminated=true;}}},
    NSDate:{dateWithTimeIntervalSinceNow:x=>x}, NSURL:{fileURLWithPath:x=>x}
}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(require.resolve('../workflows/restart-app/native.js'),'utf8'),context);
context.run(['restart',JSON.stringify(target)]);
assert.equal(reopenedAt,2);
