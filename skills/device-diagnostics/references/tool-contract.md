# Device CLI MCP Contract

Use this reference when the exact `agent-cli` MCP tool shape matters.

## Device Selection

- Pass `device_id` when multiple devices are configured.
- Omit `device_id` only when the server is configured with exactly one device.
- Pass `timeout_sec` only when needed. Valid values are integers from `1` to `120`.

## Fixed Resources

Prefer these for cheap, read-only discovery before calling tools:

- `device://<device_id>/status/basic`
- `device://<device_id>/status/list`
- `device://<device_id>/config/list`
- `device://<device_id>/schema/list`
- `device://<device_id>/log/list`
- `device://<device_id>/tool/list`

## Top-Level Tools

The MCP server exposes these flat top-level tools:

- `status`
- `config`
- `log`
- `schema`
- `tool`
- `upgrade`
- `reboot`

Do not model playbooks as new MCP tools. Keep diagnostics logic in this skill and call the flat tools directly.

## Category Tool Call Shape

These tools all use the same input shape:

- `status`
- `config`
- `log`
- `schema`
- `tool`

Call them with:

```json
{
  "device_id": "lab-ir624",
  "subcommand": "basic"
}
```

The server prepends the tool name automatically. For example:

- `status` with `subcommand: "basic"` becomes `status basic`
- `config` with `subcommand: "list"` becomes `config list`
- `log` with `subcommand: "list"` becomes `log list`
- `schema` with `subcommand: "wan --validation"` becomes `schema wan --validation`

## Schema Rules

- Discover supported schema roots with `schema list`.
- Use `schema <root_key>` only with top-level roots returned by `schema list`.
- Inspect the returned `config` section for configuration fields.
- Inspect the returned `status` section for runtime field explanations when that root exposes status schema.
- Do not use dotted paths such as `system.hostname`.
- Use `schema <root_key> --validation` only for top-level config roots.

## Tool Wrapper Rules

Use the `tool` MCP tool with `subcommand` in the form:

```json
{
  "subcommand": "ping {\"action\":\"start\",\"host\":\"8.8.8.8\"}"
}
```

Workflow:

1. Call `tool` with `subcommand: "list"` to discover supported diagnostics.
2. Start a diagnostic with `<tool_name> <json_payload>`.
3. Poll with `action: "status"` when the tool supports it.
4. Read accumulated output with `start_line`.
5. Stop long-running diagnostics when they are no longer needed.

Important constraints:

- Do not invent tool names or payload shapes. Use `tool list` first.
- `tool list` is cached by firmware version and is automatically augmented to include `speedtest`.
- `tcpdump start` over MCP requires `capture_mode` of `show`, an integer `capture_time`, and exactly one `local_iface` item.
- Each `tcpdump.local_iface[]` item must include `interface` and `expert_options` strings.

## Speedtest Wrapper

`speedtest` is exposed through the `tool` wrapper. Use these examples:

- Start:

```json
{
  "subcommand": "speedtest {\"action\":\"start\",\"interface\":\"wan1\"}"
}
```

- Status:

```json
{
  "subcommand": "speedtest {\"action\":\"status\"}"
}
```

- Output:

```json
{
  "subcommand": "speedtest {\"action\":\"output\",\"start_line\":0}"
}
```

Rules:

- Valid actions are `start`, `status`, `output`, `stop`, and `servers`.
- `start_line` is valid only for `output`.
- `server_id`, `host`, `interface`, and `ip` are valid only for `start`.

## Safety Model

- `status`, `log`, `schema`, `config list`, and `config get` are read-only.
- `config set`, `upgrade`, and `reboot` are mutating and require explicit user intent or approval.
- Treat active diagnostic runs under `tool` as operationally disruptive even when they do not change persistent configuration.

## Output Shape

Tool results arrive as structured JSON with:

- `device_id`
- `command`
- `ok`
- `ssh_exit_code`
- `data`
- `stderr`
- `error`

When `ok` is false, surface the `error.message`, preserve the failed command, and decide whether the failure blocks the current playbook or only narrows the next step.
