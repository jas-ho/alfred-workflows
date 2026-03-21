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

# Workflow name -> installed UUID mapping
# These are specific to your Alfred installation. On a fresh machine,
# import the workflow once from dist/ to get a UUID, then add it here.
typeset -A UUIDS=(
    clean-paste           "user.workflow.09D15CF0-DFF0-4570-A571-A1389DC9D4E1"
    discord-timestamps    "user.workflow.1FAFA37D-0205-4BBD-BD2A-EE8FB277013E"
    edge-workspace-switcher "user.workflow.36FB57F7-E96E-429A-B3B0-25A3DAA451FE"
    fix-macos-focus       "user.workflow.39B4598F-AF39-4AA2-887E-B4EE72072475"
    moom-actions          "user.workflow.7D62C6B5-A9A6-4E37-A4D8-D0132007C023"
    multi-paste           "user.workflow.4609357C-0269-400E-8CE3-8AF2A34C0C0E"
    multi-send            "user.workflow.90C619B6-35F6-4F75-9903-D162EC852D83"
    smart-date            "user.workflow.D4A7E2B1-3F5C-4A8D-B9E6-1C2D3E4F5A6B"
)

echo "Setting up Alfred workflow symlinks..."
echo ""

for name uuid in "${(@kv)UUIDS}"; do
    target="$ALFRED_WORKFLOWS/$uuid"
    source="$REPO_DIR/workflows/$name"

    if [ ! -d "$source" ]; then
        echo "  SKIP  $name (source dir missing)"
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
        backup="${target}.bak"
        echo "  LINK  $name (backing up existing to $(basename "$backup"))"
        if [ -d "$backup" ]; then
            rm -rf "$backup"
        fi
        mv "$target" "$backup"
    else
        echo "  LINK  $name (new install)"
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
