# Workspace CLI consolidation

## Objective and scope

Expose one discoverable public `workspace` CLI for people and agents. Remove the unused `doorplate` CLI rather than adding aliases or deprecation machinery. Preserve Alfred's `sp`, `sn`, `cs`, and `ns` interactions, the existing native rename implementation, and the tested desktop/window lifecycle. Leave standalone application restart/open CLIs and agent skills out of this pass.

## Command surface

- `workspace list`: fresh regular desktops, stable IDs, names, display order, active ID.
- `workspace switch NAME|NUMBER` or `--id ID`: resolve a unique target, switch, verify arrival.
- `workspace rename NAME [--id ID]`: rename the current or specified desktop and verify saved metadata.
- `workspace back`: use Doorplate's previous-desktop behavior, verify an actual transition; report failure if none occurs.
- `workspace create NAME`: preserve current options/defaults, readable unique tmux names, partial results and respect for manual desktop switching.
- `workspace close [NAME|NUMBER|--id ID]`: resolve target (current if omitted) and return a window preview with `confirmation_required`; no mutation. `--yes` closes without our own confirmation, waits for completion, never dismisses application dialogs or force-quits. Alfred keeps its GUI confirmation and immediate empty-desktop closure.
- `workspace check`: read-only readiness report for worker, close backend, live desktop access, local configured app prerequisites; explicitly distinguish unchecked Automation permissions from verified checks. No permission prompts or test windows.
- `workspace result OPERATION_ID`: inspect a stored operation without repeating it; includes running/partial/blocked outcomes.

Every public command supports `--json` before or after the subcommand. Human output is the default. Help includes examples, defaults, target selection rules, side effects, completion semantics and retry guidance. Internal Alfred filter/action entry points move to a separate script, not public subcommands. Retain stdlib argparse: changing the dependency/runtime framework would add little value for this small already-installed CLI.

## Output contract

One JSON object on stdout in JSON mode, including errors and argument validation failures; no logs or progress on stdout. Human errors go to stderr. Envelope: `schema_version: 1`, `operation`, `operation_id` (null if not submitted), `status`, `data` object, `error` (null or `{code, message}`). Statuses: `complete`, `running`, `confirmation_required`, `blocked`, `cancelled`, `partial`, `failed`, `uncertain`. Exit 0 only for complete, 1 for other operation outcomes, 2 for invalid CLI usage. `result` uses the recorded operation outcome; a running result is not a completed success. Help exits 0 and remains text even with `--json`.

Desktop IDs are opaque decimal strings in the public API, converted to numbers only at the Hammerspoon boundary. Operation IDs are unrelated 32-character hex request IDs. Failed/partial mutations retain the operation ID and details of completed work. Timeout is never presented as proof of failure or permission to repeat a mutation.

## Architecture

Keep the file transport as the single GUI-session bridge: native desktop snapshot/rename helpers run under Hammerspoon, so agent shells do not need direct WindowServer access or working `hs` IPC. Move Doorplate's native preferences helper into the workspace implementation. Retain its backup/locking/version safeguards. Creation calls that private helper directly, never recursively calls the public CLI.

Keep the single request mailbox, expiry and result files. Hold the client lock until the worker acknowledges the request, then release it while awaiting completion. This lets another process inspect readiness/list/results during a long mutation. The worker serializes mutations and rejects another mutation as busy, while allowing bounded read-only requests. Each operation publishes its own ID and terminal result. Startup requests are never replayed.

Add a small lifecycle-operation dispatcher beside the creation worker rather than expanding one monolithic create function. It resolves stable targets from fresh native snapshots, uses native naming and Doorplate URLs for switch/back (to preserve Back history), and verifies resulting state. Bound every subprocess and poll; no retries of destructive or uncertain operations.

Extend `SpaceClose.request` with optional confirmation/notification policy and a completion callback. Existing behavior remains the default for Alfred. Return structured blocked window/app identity, closed-window count, and verified removal in the completion result. Add a read-only preview method. Tie completion to the specific request callback rather than polling global `lastResult`. Callbacks must fire exactly once on success, cancellation or stop. Avoid the self-busy guard when the workspace dispatcher invokes the close backend; preserve mutual exclusion with create/prune/warm.

Alfred picker scripts keep their filtering, icons and keywords; route their actions through the same public operation implementation using a separate adapter. The picker may use live native snapshot reads for responsiveness if the shared transport adds visible latency, but mutations must share the operation dispatcher. Remove the installed `~/.local/bin/doorplate` symlink only after references have been migrated and smoke checks pass; trash the unused link rather than deleting it irrecoverably. Retain the Doorplate application and workflow name/icons; these are not public CLI aliases.

## Validation and delivery

1. Independent plan review; adapt this document before implementation.
2. Implement the public contract/transport/lifecycle backend and thin Alfred adapters. Add regression tests for JSON usage failures, stable target resolution, true completion, blocked close, exact request callback isolation, mailbox acknowledgment/locking, startup no-replay, busy mutations/read-only access, malformed requests, timeout uncertainty, and existing create behavior.
3. Independent implementation review. Resolve real findings before live deployment. Cross-model review remains preferred where available; the Claude CLI has repeatedly returned `Execution error` in this session, so document fallback to independent native Codex review if it remains unavailable.
4. Run required pytest, backend Lua scenarios, syntax/lint/type checks and build bundles. Verify bundle contents against sources. Live smoke: help, check, list, one uniquely named disposable empty workspace with rename/switch/back/preview/close, exact ID cleanup; do not close existing user windows. If desktop manipulation would interfere with active user testing, finish read-only validation and defer only the live smoke.
5. Commit coherent reviewed changes in the Alfred and bin repositories, update installation links, verify clean status. No push unless requested. Final response states the public commands, validation, commits and any genuine limitations.

## Non-goals

No compatibility CLI, agent-launching framework, automatic retry/recovery engine, session garbage collector, schema generator, plugin system, parallel app creation, broad dotfile cleanup, or standalone app-control CLI.

## Plan review decisions

- Acknowledgment means the first atomically published matching per-ID result after admission/validation; only then may the client release the mailbox lock. Neither missing acknowledgment nor timeout proves that no mutation occurred. Preserve the operation ID in both cases and do not rewrite the worker's running record from the client.
- A close preview returns the stable `space_id` and recommends `workspace close --id ID --yes`. Confirmation uses a fresh window inventory. There is deliberately no preview-token subsystem.
- Numeric positional selectors mean current desktop order; numeric names can be addressed through `--id`. Otherwise use exact case-insensitive names, then a unique substring; ambiguity is an error. Switching to the current desktop is a verified successful no-op. Back with no observed transition reports blocked, not successful navigation.
- Close preview accepts an explicit infrastructure-window exclusion and does not use or mutate active request context. An accepted close calls its completion callback exactly once; synchronous rejection returns an error and does not call it. Completion includes `removal_verified`, actual confirmed close count, and blocked window identity when known.
- Add an explicit worker stop hook invoked by Hammerspoon shutdown/reload: cancel owned timers/tasks and record an uncertain terminal result for accepted work, without restoring focus or replaying mutations. Abrupt process death remains uncertain; client timeout/result guidance must not promise rollback or cancellation.
- Normalize backend records at one Python envelope boundary; preserve arrays and stringify desktop IDs while rejecting numeric IDs outside the safe integer range. Report only verified window closes, including earlier successful requests in a partially blocked batch where observable.
- Prepare the disposable empty desktop through the existing Hammerspoon helper for smoke testing. Do not add empty recipes solely for test setup.

## Delivery validation

Independent plan review and final implementation review completed; concrete findings were fixed. Automated CLI/worker tests, mocked close scenarios, syntax/lint/type checks and archive verification cover the implementation. The old installed worker answered the readiness probe, but the new worker could not be loaded from this session: native UI control returned `cgWindowNotFound`, and Launch Services refused the existing Hammerspoon reload URL even outside the shell sandbox. Live desktop smoke testing therefore remains pending after a Hammerspoon reload. The unused `doorplate` CLI link was moved to Trash; `workspace` remains installed through its existing source symlink. No user desktop or window was closed during this pass.
