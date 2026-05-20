# Status

Use status for runtime state snapshots.

## CLI

```bash
agent-cli status
agent-cli status list
agent-cli status basic
agent-cli status cellular
```

Behavior from the CLI help:

- No subcommand reads the aggregated status view.
- `status list` returns the available status keys.
- `status <key>` reads one status area such as `basic`, `cellular`, or `wan`.

## MCP

Use the `status` MCP tool with:

```json
{"subcommand":"list"}
```

or:

```json
{"subcommand":"basic"}
```

## Guardrails

- Do not prepend `status` inside the subcommand. Use `basic`, not `status basic`, for MCP-style subcommands.
- Do not use `status` for config lookups. Use `config get <key>` instead.
