#!/usr/bin/osascript -l JavaScript
function run(argv) {
    const app = Application("Moom");
    const rawActions = app.listOfActions();
    const items = [];
    const seen = new Set();
    for (const action of rawActions) {
        const lines = action.split("\n");
        if (lines.length < 2) continue;
        const actionType = lines[0].trim();
        const actionName = lines[1].trim();
        if (actionType === "Folder" || actionType === "Menu Separator") continue;
        if (actionName === "Examples" || actionName === "More Examples" || !actionName) continue;
        if (seen.has(actionName)) continue;
        seen.add(actionName);
        items.push({ title: actionName, subtitle: actionType, arg: actionName, icon: { path: "icon.png" } });
    }
    items.push({ title: "Center Window", subtitle: "Built-in Moom command", arg: "__CENTER__", icon: { path: "icon.png" } });
    return JSON.stringify({ items });
}