# Safety Rules

These rules apply across every `agent-cli-*` skill.

## Default Mode

- Stay read-only unless the user explicitly asks for a change.
- Treat `status`, `log`, and `schema` as safe read-only operations.

## Actions Requiring Explicit Approval

Require explicit user approval before:

- `config set`
- `upgrade`
- `reboot`
- long-running or disruptive diagnostics when they may affect traffic or device behavior

## Required Pre-Checks

- Before `config set`, inspect schema first and read current config when the change is not trivial.
- Before `upgrade`, confirm the exact target version and source artifact.
- Before `reboot`, make sure the user understands it happens immediately.

## Required Post-Checks

- After `config set`, re-read the affected config or status area.
- After `upgrade`, wait for reconnect and verify the final firmware version with `status basic`.
- After `reboot`, wait for reconnect and verify `status basic`.

## Hard Stops

- Stop and ask if multiple devices are configured but the user did not identify one.
- Stop and ask if the payload shape, schema root, service name, or tool name is uncertain.
- Do not guess firmware URLs, schema roots, or config fields.

## When Errors Occur

When any operation fails, match the error against [error-recovery.md](error-recovery.md) before retrying. Follow the prescribed recovery flow for the error category. Key rules:
- One retry only for transient errors (timeout, busy, connection reset).
- Fix the input, not the error message. If the error says "unknown root", run the discovery command — don't guess.
- Escalate, don't loop. If recovery fails twice with the same error, stop and escalate with evidence.
- Terminal results (vendor API 404, protected_items violation) are final — do not keep searching.
