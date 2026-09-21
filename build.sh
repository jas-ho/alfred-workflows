#!/bin/bash
# Build .alfredworkflow zips from source directories for distribution.
set -euo pipefail

DIST_DIR="dist"
mkdir -p "$DIST_DIR"

for workflow_dir in workflows/*/; do
    name=$(basename "$workflow_dir")
    # Get display name from info.plist (preserves casing like "macOS")
    pretty_name=$(plutil -extract name raw "$workflow_dir/info.plist" 2>/dev/null ||
        echo "$name" | sed 's/-/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2))}1')
    out="$DIST_DIR/${pretty_name}.alfredworkflow"
    echo "Building: $out"
    # Build a fresh archive before replacing the previous one. This also avoids
    # retaining files removed from source dirs, without deleting a good build first.
    archive=$(
        python3 - "$DIST_DIR" <<'PY'
import os
import sys
import tempfile
import zipfile

fd, path = tempfile.mkstemp(prefix=".build.", suffix=".alfredworkflow", dir=sys.argv[1])
with os.fdopen(fd, "wb") as handle:
    with zipfile.ZipFile(handle, "w"):
        pass
print(os.path.abspath(path))
PY
    )
    (cd "$workflow_dir" && zip -r -X "$archive" . -x '*.DS_Store' -x '__pycache__/*' -x '*.pyc')
    mv "$archive" "$out"
done

echo "Done. Workflows in $DIST_DIR/"
