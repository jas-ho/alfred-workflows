// Exercise the actual rename function with in-memory native APIs.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../workflows/doorplate/native.js'), 'utf8');

function setup(options = {}) {
    const original = {'5': {name: 'Old', icon: '🪟', color: 3, seconds: 42, future: {keep: true}},
        '3': {name: 'Other', color: 2, seconds: 6}};
    let meta = structuredClone(original), alive = true, backup, writes = 0, launched = 0;
    let reads = 0;
    const data = text => ({text, isNil: () => false,
        writeToFileAtomically: () => { backup = JSON.parse(text); return !options.backupFailure; }});
    const prefs = {
        dataForKey: () => data(JSON.stringify(meta)),
        setObjectForKey: value => { meta = JSON.parse(value.text); writes++; },
        get synchronize() { return true; },
    };
    const dollar = value => typeof value === 'string' ? {dataUsingEncoding: () => data(value)} : value;
    Object.assign(dollar, {
        NSUTF8StringEncoding: 4, NSWorkspaceLaunchWithoutActivation: 512,
        NSBundle: {bundleWithURL: () => ({objectForInfoDictionaryKey: () => options.version || '1.6.2'})},
        NSWorkspace: {sharedWorkspace: {launchApplicationAtURLOptionsConfigurationError: () => {
            launched++; alive = true; return {isNil: () => false};
        }}},
        NSString: {alloc: {initWithDataEncoding: value => value.text}},
    });
    const app = {get terminate() {
        if (options.quitFailure) return false;
        // Simulate Doorplate flushing its latest tracked time while quitting.
        meta['5'].seconds = 99;
        alive = false;
        return true;
    }};
    const context = vm.createContext({$: dollar, Ref: () => ({}),
        ObjC: {import: () => {}, unwrap: x => x},
        fakeURL: {}, fakePrefs: prefs,
        fakeRunning: () => alive ? [app] : [],
        fakeSpaces: () => ({active: options.wrongSpace || (options.changedAfterQuit && reads++ > 0 ? '3' : '5'),
            desktops: [{id: '5'}, {id: '3'}]}),
    });
    vm.runInContext(source + '\nappURL = () => fakeURL; defaults = () => fakePrefs; running = fakeRunning; spaces = fakeSpaces;', context);
    return {
        rename: () => vm.runInContext(`rename('5', 'Bücher & "Quotes"', '/backup', ${!options.anySpace})`, context),
        result: () => ({meta, original, backup, writes, launched, alive}),
    };
}

const ok = setup();
ok.rename();
const result = ok.result();
assert.equal(result.meta['5'].name, 'Bücher & "Quotes"');
assert.equal(result.meta['5'].seconds, 99);
assert.equal(result.meta['5'].icon, '🪟');
assert.deepEqual(result.meta['5'].future, {keep: true});
assert.deepEqual(result.meta['3'], result.original['3']);
assert.equal(result.backup['5'].name, 'Old');
assert.equal(result.backup['5'].seconds, 99);
assert.equal(result.launched, 1);

for (const [options, error, relaunches] of [
    [{version: '1.7.0'}, /rechecking/, 0],
    [{wrongSpace: '3'}, /target desktop changed/, 0],
    [{quitFailure: true}, /could not quit/, 0],
    [{changedAfterQuit: true}, /target desktop changed/, 1],
    [{backupFailure: true}, /back up/, 1],
]) {
    const test = setup(options);
    assert.throws(test.rename, error);
    assert.equal(test.result().writes, 0);
    assert.equal(test.result().launched, relaunches);
    assert.equal(test.result().alive, true);
}
const explicit = setup({wrongSpace: '3', anySpace: true});
explicit.rename();
assert.equal(explicit.result().meta['5'].name, 'Bücher & "Quotes"');
console.log('Native rename safety checks passed.');
