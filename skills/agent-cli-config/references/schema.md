# Schema

Use schema to discover valid roots, fields, and validation constraints before any non-trivial config work.

## CLI

```bash
agent-cli schema list
agent-cli schema cellular
agent-cli schema system --validation
```

Behavior from the CLI help and validators:

- `schema list` returns schema roots with descriptions.
- `schema <key>` reads one root schema.
- `schema <root> --validation` only accepts a root key.
- Nested paths such as `system.hostname` are not supported in schema lookups.

## MCP

Use the `schema` MCP tool with subcommands such as:

```json
{"subcommand":"list"}
```

or:

```json
{"subcommand":"system --validation"}
```

## Guardrails

- Do not use `schema status ...`; that form is removed.
- Use schema as the source of truth for valid roots, field names, enum values, and write constraints.
