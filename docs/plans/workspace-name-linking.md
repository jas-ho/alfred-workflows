# Workspace name linking and palette creation

Status: implemented and reviewed on 2026-09-25 after Jason approved the revised plan. The recursive-discovery follow-up below supersedes the original exact-depth and dated-session naming rules. Scope is terminal linking and palette creation, not saved workspace configurations.

## Confirmed behavior

- Creating by name first considers running tmux sessions, then project folders at `~/Projects/<category>/<project>`, then folders at `~/Code/<repo>`.
- Matching uses trimmed names and Unicode casefold for exact equality. Folder basenames also match after removing one leading `YYYY-MM_` prefix (structural `^[0-9]{4}-[0-9]{2}_`, without calendar validation) (`stockholm` matches `2026-03_stockholm`; `stock` does not). Dates are not stripped from tmux session names.
- Same-real-path folder aliases count as one candidate. Distinct matches at the same precedence level are ambiguous: use the ordinary fresh session in home, explain ambiguity, and do not fall through to a lower level.
- Attach a matching running session. A folder match starts a session named after the full folder basename, in that folder; if that folder-named session already exists, attach it. No match retains the existing unique `ws-<name>` session in home.
- Edge and Obsidian use the unchanged recipe. No extra linked/plain choices: each Create subtitle states the terminal behavior.
- Root palette: matching desktops first, then the existing two Create choices (return first, stay second). Hide Create choices for an exact case-insensitive desktop-name match. Explicit New workspace and CLI create still permit duplicate desktop names.
- Actions-menu navigation, close semantics, keywords, layout and speed remain unchanged. Save/lock/reopen configurations are out of scope.

## Design

### 1. One resolver, project locations as data

Add a small Python module in `workflows/new-workspace/` for read-only terminal resolution. All creation entry points use it: `workspace create`, `ns`, and both root and explicit-create palette screens. Keep filesystem/session discovery separate from the pure precedence/matching function for testing. Do not add a provider framework, plugin system, project registry, fuzzy matcher or background index.

Use one optional top-level recipe setting, `project_roots`, containing an ordered list of `{path, depth}` entries. The bundled personal recipe declares `[{path: "~/Projects", depth: 2}, {path: "~/Code", depth: 1}]`; the resolver itself has no personal path defaults. Missing or empty `project_roots` disables folder lookup, not session lookup. Document the setting without automatically rewriting local overrides; no local override was present at planning time. Each root is one precedence tier and depth is exact, not recursive-to-any-depth. Depth is validated as an integer from 1 through 3 (excluding booleans). This replaces vault/repo branches with one bounded directory traversal. Paths can contain spaces and symlinks. No Git metadata, README parsing or Obsidian calls are needed.

No special folder category allowlist: the supplied tier searches all immediate category/project pairs, including archive, as specified. Ignore hidden entries and non-directories; missing roots and dangling symlinks contribute no candidates. Other enumeration/permission errors stop automatic linking and identify the offending path. Only inspect tiers needed to resolve the name: a unique session match needs no folder traversal. This deliberately favors an actionable error over silently starting in the wrong directory; an unreadable category in a needed tier can therefore block automatic creation even for another name. Validate config shape and use deterministic ordering.

Match basenames (full or date-prefix-stripped) first, then deduplicate by canonical path within each tier. Choose the first configured tier with any candidates; ambiguity is terminal. Use the canonical folder basename for session naming and canonical path for cwd, so alternate symlink names cannot create different session identities. Show the matched display path in the subtitle. This is a proposed clarification for Jason: symlink aliases name the session after their target folder.

Tmux inventory precedes folder lookup. Share executable search and invocation environment between client and helper: remove ambient `TMUX`/`TMUX_TMPDIR` so tmux selects its standard default server. Apply this same policy to the command Ghostty executes, as well as inventory, preflight and creation. Do not calculate socket paths or add a public multi-server setting. Tests can inject an explicit disposable `-S` socket into the shared helper. Use bounded subprocess calls and literal argv. A normal absent server is an empty inventory; missing executable, timeout, permission errors or malformed responses are lookup failures, not permission to create an unlinked session. For recipes without the tmux-capable Ghostty opener, skip the entire terminal resolver, including folder lookup. Multiple case-insensitive session matches are ambiguous, just like multiple folders.

Resolver output is a small terminal intent: attach existing session, create folder-named session, or ordinary unique session; plus cwd and a reason suitable for the subtitle (including ambiguity). It does not create a session or a desktop.

### 2. Explicit inputs win; the worker still owns mutations

Any explicit `--directory` or `--tmux-session` bypasses automatic name linking. Both together keep their existing meaning. Audit all callers for implicitly supplied directory defaults; current palette-action and ns paths construct arguments without an implicit directory. Change parser's directory default to unset, applying home only after resolution, so an explicitly supplied home directory is distinguishable. Keep `--tmux-session` attach-only; do not reinterpret it as create-if-missing.

Translate resolver intent to the existing `directory` / `tmux_session` request fields, plus one private field for a requested new session name. Existing callers that omit the new field keep their existing behavior. Keep this terminal detail out of Lua except for any necessary result propagation; the app helper already owns tmux launch.

Use these session policies:

| Intent                                       | Name                                                                                                               | Execution                                                                                                                                                                                                           |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Existing session / explicit `--tmux-session` | Exact discovered/supplied name                                                                                     | Attach only; disappearing target is an error.                                                                                                                                                                       |
| Folder match                                 | Canonical basename, preserving case, Unicode, spaces and date prefix; replace tmux-incompatible `.` / `:` with `_` | Attach a unique casefold-equal existing name, otherwise atomically create this name in the folder. If creation fails, verify that the exact session now exists and attach it; otherwise surface the original error. |
| Unmatched or ambiguous                       | Existing `ws-<slug>[-N]` policy                                                                                    | Keep the current unique-name collision loop; always create a fresh session in home.                                                                                                                                 |

Reject control characters in session names. Share the literal nonempty/control-free validator between automatic and explicit attachment; support folder names with spaces without a separate CLI whitelist. Use literal argv, exact `=name` targets and shell quoting all the way through Ghostty. Test quotes, dollar signs, semicolons, backticks, leading `-`/`=`, Unicode and rejected newlines. Show the actual session name when transformed. Different folder basenames can normalize to the same session name: attachment is name-based as requested, not a guarantee of session cwd. The resolver alone performs casefold lookup: a unique hit becomes an ordinary attach intent, multiple hits are ambiguous, and only no hit produces the private new-name field. The helper only creates that literal name or verifies its exact existence after a failure; it does not choose case variants. A case-variant name created concurrently can remain a separate session, consistent with tmux’s case-sensitive names; do not add locking machinery for this edge case.

Resolve afresh when Return executes or the CLI constructs its request. Palette descriptions are previews, not reservations; do not cache authoritative intent in a row. Then freeze the resolved request for this operation. The helper checks that the directory still exists immediately before session creation, for inferred and explicit directories; do not rely on tmux to reject a missing cwd. Test removal between resolution and this check. This is a best-effort filesystem check, not an atomic guarantee against concurrent deletion. Lookup/config failures stop CLI creation before desktop mutation, with a nonzero exit and the existing JSON error envelope when requested; ns shows the corresponding actionable error. Folder-lookup errors name the path and the CLI opt-out `--directory ~`; explicit New workspace is not an opt-out and still resolves names. Tmux failures suggest restoring tmux access, since an explicit directory cannot eliminate that dependency. Worker-time failures preserve existing partial-result behavior.

Keep the existing result schema and persisted results: the worker already reports actual `tmux_session` identity, including partial failures. The CLI can emit an informational ambiguity notice to stderr (also with --json, whose stdout remains one object); no extra result fields or client-only fields that disappear from `workspace result`. Do not add a new public CLI subcommand solely for UI preview.

### 3. Shared Create rows and independent error handling

Extract one Create-row builder used by root and explicit-create screens. Return/stay order, payloads and literal-name handling remain identical. Subtitles put terminal intent early enough to see, e.g. `attaches tmux immo`, `tmux in ~/Projects/life/immo`, or `ambiguous project name · new tmux in ~`, followed by the existing app summary. Unmatched/ambiguous subtitles explicitly say a new session will be created, rather than implying a stable reusable session. Use one description function for terminal intent in both the palette and ns fast path; the two-row palette builder stays separate from ns's modifier-based UI.

Empty input retains the root menu. Preserve numeric desktop lookup and action shortcuts (`new`, `previous`, `help`): existing matching desktop/action rows stay ahead of Create choices. For every nonempty valid name without an exact stored desktop-name match, offer Create rows after those existing rows. Numeric queries remain positional for desktop matching, while Create explicitly shows the literal proposed name. Compare exact names with trim/casefold; do not normalize date prefixes or do fuzzy matching for desktop identity.

An unavailable recipe or terminal lookup disables only the Create choices and explains why; already-fetched desktop/action rows remain usable. When an exact desktop match hides Create, hide any Create-only error row too. A failed desktop inventory must not be interpreted as no matching desktop. No creation while typing. Skip lookup on empty input and exact desktop matches; otherwise resolve once per filter request. Share one exact-match predicate between rendering and the I/O layer so hidden Create choices do not trigger terminal lookup. Use bounded traversal and session lookup without a persistent cache. Do not add generic performance machinery before measuring actual latency.

## Delivery plan after Jason's review

1. Implement and fixture-test resolver/config precedence; wire CLI request construction and opener support for folder-named new sessions.
2. Share Create rows across palette screens and the fast-path subtitle logic. Keep UI filtering read-only and execution literal/one-shot.
3. Update CLI help, root/workflow README and the short shared workspace skill's now-obsolete claim that omission always creates a new tmux session. Check start/spawn explicit-session integration stays compatible; no new skill logic.
4. Run the full `uv run pytest` suite, syntax/lint checks proportionate to changed files, and `./build.sh`; verify affected archives contain the new shared module and current sources. Independent cross-model diff review plus the repo's `codex review --uncommitted` check; report tool failures rather than claiming review succeeded. Do not control the Alfred UI during automated checks, given the earlier focus problems.
5. Read-only local matching checks and measured per-query latency; where practical, exercise session creation/attach in an isolated disposable tmux server without touching existing sessions. Any GUI smoke test uses a clearly disposable workspace and preserves user work. Review and commit only intended files following the user's implementation approval.

## Acceptance cases

- Existing session beats folder; first folder tier beats later; case-insensitive exact matches work, substrings do not.
- Full and stripped dated folder names match, folder-named existing sessions reattach; no-date stripping for session matching.
- Same-real-path aliases collapse; distinct same-tier folders and case-colliding sessions are ambiguous; no precedence fallthrough.
- No match/ambiguity produce ordinary unique home sessions; explicit directory/session bypass linking (`--directory ~` is the CLI opt-out); no Ghostty recipe skips all terminal resolution.
- Root configuration omitted/custom/empty/malformed, missing/unreadable directories, dangling aliases, spaces and punctuation have defined outcomes.
- Tmux no-server, timeout, permission denial, literal names with spaces/punctuation, differing caller environments and create collision/disappearance behave distinctly; only verified existence of the exact folder-session name after create failure may change create to attach; directory removal before the helper check stops creation; no client switching or session killing.
- Root with zero/partial/exact matches, numeric names, command-like names, empty input and invalid names has correct action/create ordering and literal payloads; no obsolete no-match placeholder alongside Create rows.
- Lookup failures cause nonzero CLI errors before mutation and valid JSON error output; Create-only failures do not break desktop navigation or leak into exact-match results; previews never mutate; execution re-resolves once and existing partial-result behavior remains intact.
- Browser/note content and app recipe are unchanged by terminal linking. Existing CLI JSON contract and explicit-session start/spawn use still work.

## Review disposition

Opus 5.5 reviewed the proposal in two completed rounds: REVISE, then APPROVED. The earlier interrupted run is not counted as approval. Incorporated findings cover create/attach races, CLI error semantics, hidden Create errors, consistent matching, caller defaults and simpler config/server handling. Final non-blocking notes clarified helper ownership, cwd revalidation and exact-session verification after a create failure. Rejected the suggestion that explicit New workspace bypasses linking: it does not under the confirmed UX. Review artifacts are local under `tmp/workspace-linking-opus-review/`.

Implementation review clarified two matching boundaries: normalize Unicode to NFC before casefolding, and reject dots/colons in explicit tmux session names because tmux interprets them as target syntax. Existing attachment targets are rechecked immediately before launching Ghostty.

Implementation validation: 385 tests passed, including isolated real tmux creation/attachment and cwd checks; ruff and mypy passed with the project Python environment. Both archives were rebuilt and their sources verified. Opus 5.5 approved after three implementation-review rounds; native Codex follow-up found no blockers. The dedicated `codex review --uncommitted` launcher failed at sandbox initialization on both attempts, so the native review replaced that check. Read-only live resolver checks took roughly 6–13 ms median per query; full GUI creation was not driven during this change.

## Recursive-discovery follow-up

Jason confirmed marker-free recursive exact-name search, with maximum depth 4 for Projects and 1 for Code. `depth` now includes all levels from 1 to the configured maximum (1–16). Nested folders remain eligible even under another project; no README, Git marker, category allowlist or project-stop rule is added. Ancestor cycles are skipped, directory aliases still deduplicate by real path, and unreadable directories still produce an error. Scanning examines directory entries, not file contents. Both distinct `fellows-integration` folders remain untouched and ambiguous when no exact session wins.

New folder-derived sessions strip one leading `YYYY-MM_` prefix. After exact typed-session precedence and unique folder resolution, prefer an existing undated session, then a legacy full folder-named session, otherwise create the undated session. Existing sessions are never renamed. Case collisions and multiple matching folders retain the existing ambiguity behavior.

The follow-up adds regression cases for levels 1–4, nested projects beneath a parent README, the maximum boundary, same names at different depths, recursive aliases/cycles, dated-session migration and real tmux reattachment. No GUI creation is needed for these resolver changes; Jason already exercised the previous version’s full creation path successfully.

Follow-up validation: 401 tests passed; lint and type checks passed using the project Python environment. Opus 5.5 approved after one revision; native Codex review found no issues (the dedicated review CLI still failed at sandbox initialization). Final live resolver medians were about 6 ms for a session match and 25–26 ms for folder lookup, with a no-session simulation confirming the depth-3 project resolves after reboot. The workflow archive was rebuilt and verified.
