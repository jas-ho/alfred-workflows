#!/bin/bash
# Build .alfredworkflow zips from source directories for distribution.
set -euo pipefail

DIST_DIR="dist"
mkdir -p "$DIST_DIR"

for workflow_dir in workflows/*/; do
    name=$(basename "$workflow_dir")
    # Get display name from info.plist (preserves casing like "macOS")
    pretty_name=$(plutil -extract name raw "$workflow_dir/info.plist" 2>/dev/null || \
        echo "$name" | sed 's/-/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2))}1')
    out="$DIST_DIR/${pretty_name}.alfredworkflow"
    echo "Building: $out"
    # Recreate archive to avoid retaining files removed from source dirs.
    rm -f "$out"
    (cd "$workflow_dir" && zip -r -X "../../$out" . -x '*.DS_Store' -x '__pycache__/*' -x '*.pyc')
done

echo "Done. Workflows in $DIST_DIR/"
