#!/usr/bin/env python3
"""Alfred Script Filter: list all apps via mdfind with short-lived cache."""

import json
import os
import subprocess
import tempfile
import time

CACHE_TTL = 5  # seconds

cache_dir = os.environ.get("alfred_workflow_cache", "/tmp/app-launcher-cache")
os.makedirs(cache_dir, exist_ok=True)
cache_file = os.path.join(cache_dir, "apps.json")

# Use cache if fresh
try:
    age = time.time() - os.path.getmtime(cache_file)
    if age <= CACHE_TTL:
        with open(cache_file) as f:
            print(f.read(), end="")
        raise SystemExit(0)
except FileNotFoundError:
    pass

# Build app list from mdfind
apps = subprocess.check_output(
    ["mdfind", 'kMDItemContentType == "com.apple.application-bundle"'],
    text=True,
).splitlines()

# Only include apps from standard locations (skip internal helpers/agents)
# Priority order: prefer /Applications over ~/Applications for same-name apps
APP_DIRS = ("/Applications", "/System/Applications", os.path.expanduser("~/Applications"))
apps = [p for p in apps
        if any(p.startswith(d) for d in APP_DIRS)
        and "/Contents/" not in p]

# Deduplicate by app name, preferring paths earlier in APP_DIRS
seen = {}
for path in apps:
    name = os.path.basename(path).removesuffix(".app").lower()
    if name not in seen:
        seen[name] = path
    else:
        # Keep the one from the higher-priority directory
        existing = seen[name]
        for d in APP_DIRS:
            if existing.startswith(d):
                break  # existing wins
            if path.startswith(d):
                seen[name] = path
                break
apps = list(seen.values())

items = []
for path in sorted(apps, key=lambda p: os.path.basename(p).lower()):
    name = os.path.basename(path).removesuffix(".app")
    items.append({
        "title": name,
        "subtitle": path,
        "arg": path,
        "autocomplete": name,
        "icon": {"type": "fileicon", "path": path},
        "match": name,
    })

result = json.dumps({"items": items})

fd, tmp = tempfile.mkstemp(dir=cache_dir, suffix=".json")
with os.fdopen(fd, "w") as f:
    f.write(result)
os.replace(tmp, cache_file)

print(result, end="")
