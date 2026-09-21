// Native APIs only: no UI scripting, keystrokes, or Accessibility permission.
ObjC.import('Cocoa');

const BUNDLE = 'app.doorplate.Doorplate';
const META = 'Doorplate.meta.v2';

function fail(message) { throw new Error(message); }

function appURL() {
    const url = $.NSWorkspace.sharedWorkspace.URLForApplicationWithBundleIdentifier(BUNDLE);
    if (url && !url.isNil()) return url;
    // Launch Services may be unavailable to an isolated background process.
    // Still identify a standard install, then let spaces() explain the missing session.
    const paths = ['/Applications/Doorplate.app', ObjC.unwrap($.NSHomeDirectory()) + '/Applications/Doorplate.app'];
    for (const path of paths) {
        if ($.NSFileManager.defaultManager.fileExistsAtPath(path)) return $.NSURL.fileURLWithPath(path);
    }
    fail('Install and open Doorplate first.');
}

function defaults() {
    const prefs = $.NSUserDefaults.alloc.initWithSuiteName(BUNDLE);
    prefs.synchronize;
    return prefs;
}

function readMeta(prefs) {
    const data = prefs.dataForKey(META);
    if (!data || data.isNil()) return {};
    const text = ObjC.unwrap($.NSString.alloc.initWithDataEncoding(data, $.NSUTF8StringEncoding));
    const meta = JSON.parse(text);
    if (!meta || Array.isArray(meta) || typeof meta !== 'object') fail('Unrecognized Doorplate names format.');
    return meta;
}

function spaces() {
    $.NSBundle.bundleWithPath('/System/Library/PrivateFrameworks/SkyLight.framework').load;
    ObjC.bindFunction('SLSMainConnectionID', ['int', []]);
    ObjC.bindFunction('SLSCopyManagedDisplaySpaces', ['id', ['int']]);
    ObjC.bindFunction('SLSGetActiveSpace', ['uint64', ['int']]);
    const connection = $.SLSMainConnectionID();
    const raw = $.SLSCopyManagedDisplaySpaces(connection);
    if (!raw || raw.isNil()) fail('Cannot read live desktops. Run this workflow from Alfred in your logged-in Mac session.');
    const displays = ObjC.deepUnwrap(raw);
    const active = String($.SLSGetActiveSpace(connection));
    let number = 0;
    const desktops = [];
    displays.forEach(display => (display.Spaces || []).forEach(space => {
        if (space.type === 0) {
            if (!Number.isSafeInteger(space.ManagedSpaceID) || space.ManagedSpaceID <= 0) {
                fail('Unrecognized desktop ID. No changes made.');
            }
            desktops.push({id: String(space.ManagedSpaceID), number: ++number});
        }
    }));
    if (!desktops.length || active === '0') fail('No live desktops available.');
    return {active: active, desktops: desktops};
}

function snapshot() {
    appURL();
    const state = spaces();
    const meta = readMeta(defaults());
    state.desktops.forEach(space => { space.name = (meta[space.id] || {}).name || ''; });
    return state;
}

function running() {
    return ObjC.unwrap($.NSRunningApplication.runningApplicationsWithBundleIdentifier(BUNDLE));
}

function rename(id, name, backup, requireActive) {
    const url = appURL();
    const bundle = $.NSBundle.bundleWithURL(url);
    const version = ObjC.unwrap(bundle.objectForInfoDictionaryKey('CFBundleShortVersionString'));
    // This is a private preference format, verified against this release only.
    if (version !== '1.6.2') fail('Renaming needs rechecking for Doorplate ' + version + '. Use Doorplate’s editor for now.');
    let state = spaces();
    if ((requireActive && state.active !== id) || !state.desktops.some(s => s.id === id)) {
        fail('The target desktop changed or disappeared. Select it again.');
    }
    readMeta(defaults()); // Refuse malformed data before stopping the app.
    const apps = running();
    let shouldRelaunch = apps.length === 0;
    let failure = null;
    try {
        apps.forEach(app => {
            if (!app.terminate) fail('Doorplate could not quit. Close its dialogs and try again.');
            shouldRelaunch = true;
        });
        const deadline = Date.now() + 15000;
        while (running().length && Date.now() < deadline) $.NSThread.sleepForTimeInterval(0.1);
        if (running().length) fail('Doorplate is still quitting; no names changed. Reopen it if it closes later.');
        // Re-read after graceful termination so recent edits and tracked time survive.
        const prefs = defaults();
        const original = prefs.dataForKey(META);
        const meta = readMeta(prefs);
        state = spaces();
        if ((requireActive && state.active !== id) || !state.desktops.some(s => s.id === id)) fail('The target desktop changed or disappeared. Select it again.');
        if (original && !original.isNil() && !original.writeToFileAtomically(backup, true)) {
            fail('Could not back up Doorplate’s names; no names were changed.');
        }
        const previous = meta[id] || {icon: '', color: -1, seconds: 0};
        if (typeof previous !== 'object' || Array.isArray(previous)) fail('Unrecognized desktop metadata.');
        previous.name = name;
        meta[id] = previous;
        const data = $(JSON.stringify(meta)).dataUsingEncoding($.NSUTF8StringEncoding);
        prefs.setObjectForKey(data, META);
        if (!prefs.synchronize) fail('Could not save Doorplate’s names.');
        if ((readMeta(defaults())[id] || {}).name !== name) fail('Saved name verification failed.');
    } catch (error) {
        failure = error;
    } finally {
        if (shouldRelaunch) {
            const error = Ref();
            const app = $.NSWorkspace.sharedWorkspace.launchApplicationAtURLOptionsConfigurationError(
                url, $.NSWorkspaceLaunchWithoutActivation, $({}), error);
            if (!app || app.isNil()) {
                failure = new Error((failure ? failure.message + ' ' : '') + 'Doorplate could not relaunch. Open it manually.');
            }
        }
    }
    if (failure) throw failure;
    return {ok: true};
}

function run(argv) {
    try {
        const command = argv[0];
        if (command === 'snapshot') return JSON.stringify(snapshot());
        if (command === 'rename') return JSON.stringify(rename(argv[1], argv[2], argv[3], argv[4] !== 'any'));
        fail('Unknown native command.');
    } catch (error) {
        return JSON.stringify({error: String(error.message || error)});
    }
}
