#!/bin/zsh
exec /usr/bin/python3 "${0:A:h}/workspace.py" filter "${1:-}"
