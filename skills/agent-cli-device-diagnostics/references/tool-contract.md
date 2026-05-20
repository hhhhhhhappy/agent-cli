# Tool Contract

Use this reference only when the exact local `agent-cli` CLI payload shape, MCP subcommand contract, or output structure matters. For transport setup (CLI vs MCP choice, bootstrap, auth), see `agent-cli-shared` references [../../agent-cli-shared/references/transport-cli.md](../../agent-cli-shared/references/transport-cli.md) and [../../agent-cli-shared/references/transport-mcp.md](../../agent-cli-shared/references/transport-mcp.md).

## Device Selection

- Pass `device_id` when multiple devices are configured.
- Omit `device_id` only when exactly one device is configured.
- Pass `timeout_sec` only when needed. The current validated range is `1` to `120`.

## Generic Rules

- `tool list` returns the supported diagnostics. Use it first before any `tool` invocation when the exact tool name or payload shape is uncertain.
- The payload must be one JSON object string.
- Long-running tools usually follow `start` → `status` → output polling → `stop`.
- `speedtest` is exposed through `tool` but maps to backend speedtest session commands.
- Do not invent tool names or payload shapes. Use `tool list` first.

## CLI

```bash
agent-cli tool list
agent-cli tool <tool_name> <json_payload>
```

Examples from the CLI help:

```bash
agent-cli tool ping {"action":"start","host":"8.8.8.8"}
agent-cli tool tcpdump {"action":"start","capture_mode":"show","capture_time":300,"local_iface":[{"interface":"wan1","expert_options":""}]}
agent-cli tool speedtest {"action":"servers"}
```

## MCP

For MCP, use the `tool` MCP tool with a `subcommand` string such as:

```json
{"subcommand":"ping {\"action\":\"start\",\"host\":\"8.8.8.8\"}"}
```

The server prepends the wrapper name automatically. The full list of exposed MCP tool names (`status`, `config`, `log`, `schema`, `tool`, `upgrade`, `reboot`) and fixed resource URIs are documented in [transport-mcp.md](../../agent-cli-shared/references/transport-mcp.md).

## Output Shape

Tool results usually surface structured JSON with fields such as:

- `device_id`
- `command`
- `ok`
- `data`
- `stderr`
- `error`

When `ok` is false, surface the `error.message`, preserve the failed command, and decide whether the failure blocks the current playbook or only narrows the next step. For structured error recovery, see [error-recovery.md](../../agent-cli-shared/references/error-recovery.md).
