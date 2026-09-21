#!/usr/bin/osascript -l JavaScript
// Names are explicit: unknown custom actions get a neutral action icon.
function actionIcon(name, type) {
    const label = name.replace(/^[^:]+:\s*/, "").trim().toLowerCase();
    const icons = {
        "left half": "left", "right half": "right",
        "left 2/3": "left-two-thirds", "right 2/3": "right-two-thirds",
        "middle 2/3": "middle-two-thirds",
        "left third": "left-third", "right third": "right-third", "middle third": "middle-third",
        "upper left": "upper-left", "upper right": "upper-right",
        "lower left": "lower-left", "lower right": "lower-right",
        "maximize": "maximize", "toggle full screen": "fullscreen",
        "left & right": "split", "sidebar": "sidebar-right", "left sidebar": "sidebar-left",
        "equal thirds": "thirds", "top & bottom": "top-bottom",
        "vertical stack left": "stack-left", "vertical stack right": "stack-right",
        "move to display on the left": "display-left", "move to display on the right": "display-right",
        "move to display up": "display-up", "move to display down": "display-down",
        "use grid": "grid", "center window": "center"
    };
    return (icons[label] || (type === "Layout" ? "layout" : "action")) + ".png";
}

function buildItemsFromRawActions(rawActions) {
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
        items.push({ title: actionName, subtitle: "↵ Apply · " + actionType, match: actionName + " " + actionType, arg: actionName, icon: { path: actionIcon(actionName, actionType) } });
    }
    items.push({ title: "Center Window", subtitle: "↵ Center the current window", arg: "__CENTER__", icon: { path: "center.png" } });
    return items;
}

function run(argv) {
    const app = Application("Moom");
    const rawActions = app.listOfActions();
    const items = buildItemsFromRawActions(rawActions);
    return JSON.stringify({ items });
}
