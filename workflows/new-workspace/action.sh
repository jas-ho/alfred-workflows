#!/bin/zsh
args=(create)
[[ "${workspace_stay:-0}" == 1 ]] && args+=(--stay)
[[ "${workspace_full:-0}" == 1 ]] && args+=(--full)
args+=(-- "$1")
exec /usr/bin/python3 "${0:A:h}/alfred.py" "${args[@]}"
