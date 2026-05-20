# MCP Transport

Use this reference when the current agent environment exposes the native agent-cli MCP tools.

## Exposed Tool Names

The MCP server exposes these top-level tools:

```text
status
config
log
schema
tool
upgrade
reboot
```

## Device Selection

- If the MCP server exposes exactly one configured device, omit `device_id`.
- If multiple devices are configured, pass the real configured `device_id`.
- Do not invent placeholders such as `default`.

## Subcommand-Based Tools

These tools take a `subcommand` string:

- `status`
- `config`
- `log`
- `schema`
- `tool`

Examples of the underlying intent:

```json
{"subcommand":"status list"}
{"subcommand":"config get system.hostname"}
{"subcommand":"schema system --validation"}
{"subcommand":"tool speedtest {\"action\":\"servers\"}"}
```

## Dedicated Mutating Tools

`upgrade` and `reboot` have dedicated MCP tool inputs.

Upgrade uses:

```json
{"source_type":"url","url":"https://example.test/fw.bin"}
```

or:

```json
{"source_type":"file","file_path":"/tmp/fw.bin"}
```

## Fixed Resources

When the MCP environment exposes fixed read-only resource URIs, use them as cheap discovery entry points:

```text
device://<device_id>/status/basic
device://<device_id>/status/list
device://<device_id>/config/list
device://<device_id>/schema/list
device://<device_id>/log/list
device://<device_id>/tool/list
```

- Always use the real configured `device_id`. Do not invent placeholders such as `default`.
- An `Unknown resource uri` error means the `device_id` was wrong. Retry with the real `device_id` or fall back to the normal tool path.

## Transport Choice

- Prefer MCP for read-only inspection because the tool schema is structured and explicit.
- Do not invent extra MCP arguments beyond the exposed tool contract.
