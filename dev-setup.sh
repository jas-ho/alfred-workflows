#!/bin/zsh
# Set up symlinks for live Alfred workflow editing.
# Run once after cloning. Idempotent - safe to re-run.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
ALFRED_WORKFLOWS="$HOME/Library/Application Support/Alfred/Alfred.alfredpreferences/workflows"
# Backups live OUTSIDE Alfred's workflows dir so Alfred doesn't scan them and
# create ghost duplicates in the workflow list. (.gitignored.)
BACKUP_DIR="$REPO_DIR/.backups"
STAMP="$(date +%Y%m%d%H%M%S)"

if [ ! -d "$ALFRED_WORKFLOWS" ]; then
    echo "Error: Alfred workflows directory not found at:"
    echo "  $ALFRED_WORKFLOWS"
    echo "Is Alfred installed?"
    exit 1
fi

# Sweep any existing *.bak.* entries Alfred is scanning (usually residue from
# older dev-setup runs that placed backups next to the live target). Stale
# symlinks are removed; real directories are moved into $BACKUP_DIR.
sweep_stale_baks() {
    local entry base
    local moved=0
    # (N) = zsh null-glob qualifier: no error when there are no matches.
    for entry in "$ALFRED_WORKFLOWS"/*.bak.*(N); do
        [ -e "$entry" ] || continue
        base="$(basename "$entry")"
        if [ -L "$entry" ]; then
            rm "$entry"
            echo "  CLEAN  $base (stale symlink removed)"
        elif [ -d "$entry" ]; then
            mkdir -p "$BACKUP_DIR"
            mv "$entry" "$BACKUP_DIR/$base"
            echo "  CLEAN  $base -> .backups/"
            moved=1
        fi
    done
    if (( moved )); then
        echo ""
    fi
}

sweep_stale_baks

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
        # Skip stale backup entries so they can't be picked as the live target
        # (the old behavior would symlink-over them, leaving `.bak.*`-named
        # "active" workflows behind and cascading on each re-run).
        case "$(basename "$target")" in
            *.bak.*) continue ;;
        esac
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
        # zsh arrays are 1-indexed (not bash-style 0-indexed).
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
        mkdir -p "$BACKUP_DIR"
        backup="$BACKUP_DIR/$(basename "$target").bak.$STAMP"
        echo "  LINK  $name (backing up existing to .backups/$(basename "$backup"))"
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
