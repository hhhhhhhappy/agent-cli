# Speedtest

Use speedtest when the user wants public internet bandwidth measurements instead of path-specific diagnostics.

## CLI

```bash
agent-cli tool speedtest {"action":"servers"}
agent-cli tool speedtest {"action":"start","server_id":12345,"ip":"198.51.100.10"}
agent-cli tool speedtest {"action":"status"}
agent-cli tool speedtest {"action":"output","start_line":0}
agent-cli tool speedtest {"action":"stop"}
```

## MCP

Use the `tool` MCP tool with a `subcommand` string carrying the same JSON payload.

## Hard Constraints

- Supported actions are `start`, `status`, `output`, `stop`, and `servers`.
- For `start`, `server_id` must be a positive integer when provided.
- For `start`, use `ip` to choose the uplink path. Do not use `interface`.
- `host` is not supported for speedtest.
- For `output`, `start_line` must be a non-negative integer.

## Workflow

1. Use `servers` first if the user wants to choose a test endpoint.
2. Start the session.
3. Poll `status`.
4. Read incremental results with `output`.
5. Stop the session when done.
