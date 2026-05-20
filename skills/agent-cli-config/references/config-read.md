# Config Read

Use config reads to discover roots and inspect current values.

## CLI

```bash
agent-cli config list
agent-cli config get system.hostname
agent-cli config get wan
```

Behavior from the CLI help:

- `config list` returns the available config roots.
- `config get <key>` accepts a query key such as `system.hostname`.

## MCP

Use the `config` MCP tool with subcommands such as:

```json
{"subcommand":"list"}
```

or:

```json
{"subcommand":"get system.hostname"}
```

## Guardrails

- Prefer `config list` when the correct root is not yet known.
- Use read results as the baseline before making changes.
