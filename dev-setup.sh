#!/bin/zsh
# Set up symlinks for live Alfred workflow editing.
# Run once after cloning. Idempotent - safe to re-run.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
ALFRED_WORKFLOWS="$HOME/Library/Application Support/Alfred/Alfred.alfredpreferences/workflows"

if [ ! -d "$ALFRED_WORKFLOWS" ]; then
    echo "Error: Alfred workflows directory not found at:"
    echo "  $ALFRED_WORKFLOWS"
    echo "Is Alfred installed?"
    exit 1
fi

plist_raw() {
    local plist="$1"
    local key="$2"
    plutil -extract "$key" raw "$plist" 2>/dev/null || true
}

find_installed_target() {
    local source="$1"
    local source_info="$source/info.plist"
    local source_name source_bundle
    local target target_info target_name target_bundle
    local -a bundle_matches=()
    local -a name_matches=()

    source_name="$(plist_raw "$source_info" name)"
    source_bundle="$(plist_raw "$source_info" bundleid)"

    for target in "$ALFRED_WORKFLOWS"/user.workflow.*; do
        [ -e "$target" ] || continue
        target_info="$target/info.plist"
        [ -f "$target_info" ] || continue

        target_name="$(plist_raw "$target_info" name)"
        target_bundle="$(plist_raw "$target_info" bundleid)"

        if [ -n "$source_bundle" ] && [ "$source_bundle" != "(null)" ] && [ "$target_bundle" = "$source_bundle" ]; then
            bundle_matches+=("$target")
        fi
        if [ -n "$source_name" ] && [ "$target_name" = "$source_name" ]; then
            name_matches+=("$target")
        fi
    done

    if (( ${#bundle_matches[@]} > 0 )); then
        if (( ${#bundle_matches[@]} > 1 )); then
            echo "  WARN  $(basename "$source") (multiple bundleid matches; using first)" >&2
        fi
        echo "${bundle_matches[1]}"
        return 0
    fi

    if (( ${#name_matches[@]} > 0 )); then
        if (( ${#name_matches[@]} > 1 )); then
            echo "  WARN  $(basename "$source") (multiple name matches; using first)" >&2
        fi
        echo "${name_matches[1]}"
        return 0
    fi

    return 1
}

echo "Setting up Alfred workflow symlinks..."
echo ""

for source in "$REPO_DIR"/workflows/*/; do
    [ -d "$source" ] || continue
    source="${source%/}"
    name="$(basename "$source")"
    target="$(find_installed_target "$source" || true)"

    if [ -z "$target" ]; then
        echo "  SKIP  $name (not installed in Alfred; import from dist/ once, then re-run)"
        continue
    fi

    if [ -L "$target" ]; then
        existing=$(readlink "$target")
        if [ "$existing" = "$source" ]; then
            echo "  OK    $name (already symlinked)"
        else
            echo "  FIX   $name (symlink points elsewhere, updating)"
            rm "$target"
            ln -s "$source" "$target"
        fi
        continue
    fi

    if [ -d "$target" ]; then
        backup="${target}.bak.$(date +%Y%m%d%H%M%S)"
        echo "  LINK  $name (backing up existing to $(basename "$backup"))"
        mv "$target" "$backup"
    else
        echo "  SKIP  $name (target path missing: $(basename "$target"))"
        continue
    fi

    ln -s "$source" "$target"
done

# Set up ~/bin symlinks for Multi Paste/Send helper scripts
echo ""
echo "Setting up ~/bin symlinks..."
mkdir -p ~/bin

for pair in \
    "workflows/multi-paste/multiclip.py:multiclip.py" \
    "workflows/multi-paste/multiclip-wrapper.sh:multiclip-wrapper.sh" \
    "workflows/multi-send/multisend.py:multisend.py"; do

    src="${pair%%:*}"
    dst="${pair##*:}"

    if [ -f "$REPO_DIR/$src" ]; then
        ln -sf "$REPO_DIR/$src" ~/bin/"$dst"
        echo "  OK    ~/bin/$dst -> $src"
    fi
done

echo ""
echo "Done. Restart Alfred to pick up changes."
echo "  (Alfred menu bar icon -> Quit, then relaunch)"
