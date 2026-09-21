// AppKit bridge. Arguments stay data; application names never become source code.
function restartApplication(api, target, operation) {
    if (!target || !Number.isInteger(target.pid) || target.pid <= 0 ||
        typeof target.path !== "string" || !target.path.startsWith("/") ||
        !target.path.endsWith(".app") || !Number.isFinite(target.launched)) {
        throw new Error("Invalid application identity. Search again.");
    }
    if (operation !== "restart" && operation !== "quit") throw new Error("Unknown action.");
    const matches = app => app && app.pid === target.pid && app.path === target.path && app.launched === target.launched;
    const app = api.lookup(target.pid);
    if (!matches(app)) throw new Error("That application changed or exited. Search again.");
    if (!api.quit(app)) throw new Error("The application refused to quit.");
    const deadline = api.now() + 30;
    while (true) {
        const current = api.lookup(target.pid);
        if (!current) break;
        if (!matches(current)) throw new Error("Application identity changed while waiting. Search again.");
        if (api.now() >= deadline) throw new Error("Application is still open. Resolve any save dialog and try again.");
        api.wait(0.2);
    }
    if (operation === "restart" && !api.open(target.path)) throw new Error("Application quit, but could not be reopened.");
    return {status: operation === "restart" ? "reopen_requested" : "quit"};
}

function run(argv) {
    ObjC.import("AppKit");
    const ws = $.NSWorkspace.sharedWorkspace;
    function describe(app, listing) {
        if (!app || app.isNil() || app.terminated) return null;
        if (listing && app.activationPolicy === 2) return null;
        const url = app.bundleURL, date = app.launchDate;
        if (!url || url.isNil() || !date || date.isNil()) {
            if (listing) return null;
            throw new Error("Could not verify the running application. Search again.");
        }
        const path = ObjC.unwrap(url.path);
        if (listing && (!path.endsWith(".app") || path.includes("/Contents/"))) return null;
        const bundle = ObjC.unwrap(app.bundleIdentifier) || "";
        if (listing && (bundle === "com.apple.finder" || bundle.startsWith("com.runningwithcrayons.Alfred"))) return null;
        return {pid: Number(app.processIdentifier), path: path,
            launched: Number(date.timeIntervalSince1970), name: ObjC.unwrap(app.localizedName), bundle: bundle};
    }
    if (argv[0] === "list") {
        const apps = ws.runningApplications, results = [];
        for (let i = 0; i < apps.count; i++) {
            const app = describe(apps.objectAtIndex(i), true);
            if (app) results.push(app);
        }
        return JSON.stringify(results);
    }
    const api = {
        lookup: pid => describe($.NSRunningApplication.runningApplicationWithProcessIdentifier(pid)),
        quit: app => {
            const running = $.NSRunningApplication.runningApplicationWithProcessIdentifier(app.pid);
            const identity = describe(running, false);
            if (!identity || identity.path !== app.path || identity.launched !== app.launched) return false;
            return Boolean(running.terminate);
        },
        now: () => Date.now() / 1000,
        wait: seconds => $.NSRunLoop.currentRunLoop.runUntilDate($.NSDate.dateWithTimeIntervalSinceNow(seconds)),
        open: path => Boolean(ws.openURL($.NSURL.fileURLWithPath(path)))
    };
    return JSON.stringify(restartApplication(api, JSON.parse(argv[1]), argv[0]));
}
if (typeof module !== "undefined") module.exports = {restartApplication};
