#!/bin/zsh
exec /usr/bin/python3 "${0:A:h}/alfred.py" filter "${1:-}"
