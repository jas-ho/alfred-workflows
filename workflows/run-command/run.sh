#!/bin/zsh
# Run an ad-hoc shell command entered in Alfred.
# Alfred passes the command as $1 (scriptargtype=argv). Output goes to:
#   - stdout: single-line status + truncated output for Alfred's Post Notification
#   - clipboard (pbcopy): full stdout, if non-empty
# A real interactive login shell runs the command so .zprofile / .zshrc apply.

setopt pipefail
unsetopt err_exit

cmd="$1"
if [[ -z "$cmd" ]]; then
  print -r -- "run: empty command"
  exit 0
fi

cd "$HOME" 2>/dev/null || true

tmp_out=$(mktemp -t run-out)
tmp_err=$(mktemp -t run-err)
trap 'rm -f "$tmp_out" "$tmp_err"' EXIT

# Run a real interactive login shell so rc guards like `[[ -o interactive ]] || return`
# and ZDOTDIR behave normally. The snag: without a tty, `zsh -i` emits init-time
# noise (e.g. "can't change option: zle" when .zshrc runs setopt/bindkey for the
# line editor). We separate init-time stderr from command stderr by opening fd 9
# pointed at tmp_err, then inside the shell redirecting fd 2 to fd 9 AFTER rc
# files have been sourced. Init stderr hits /dev/null; command stderr hits tmp_err.
/bin/zsh -i -l -c 'exec 2>&9; eval "$1"' _ "$cmd" >"$tmp_out" 2>/dev/null 9>"$tmp_err"
rc=$?

stdout=$(<"$tmp_out")
stderr=$(<"$tmp_err")

if [[ -n "$stdout" ]]; then
  printf '%s' "$stdout" | pbcopy
fi

format_body() {
  local text="$1"
  local -i limit=240
  # Collapse newlines so the notification renders as one line.
  text="${text//$'\n'/ ↵ }"
  if (( ${#text} > limit )); then
    # zsh substring syntax; `${text:0:$limit}` would work too but this is clearer.
    text="${text[1,limit]}…"
  fi
  print -r -- "$text"
}

if (( rc == 0 )); then
  if [[ -n "$stdout" ]]; then
    body="✓ $(format_body "$stdout")"
  elif [[ -n "$stderr" ]]; then
    body="✓ (stderr) $(format_body "$stderr")"
  else
    body="✓ no output"
  fi
else
  if [[ -n "$stderr" ]]; then
    body="✗ exit $rc · $(format_body "$stderr")"
  elif [[ -n "$stdout" ]]; then
    body="✗ exit $rc · $(format_body "$stdout")"
  else
    body="✗ exit $rc"
  fi
fi

print -r -- "$body"
