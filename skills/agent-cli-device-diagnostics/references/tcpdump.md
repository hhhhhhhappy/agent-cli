# Tcpdump

Use tcpdump for packet capture when passive status and logs are not enough.

## CLI

```bash
agent-cli tool tcpdump {"action":"start","capture_mode":"show","capture_time":300,"local_iface":[{"interface":"wan1","expert_options":""}]}
```

## MCP

Use the `tool` MCP tool with a `subcommand` string carrying the same JSON payload.

## Hard Constraints

- `capture_mode` must be `show`.
- `capture_time` must be an integer between `0` and `864000`.
- `local_iface` must be a non-empty array.
- In `show` mode, `local_iface` must contain exactly one item.
- Each `local_iface` item must include:
  - `interface` as a string
  - `expert_options` as a string
- Do not use `interface` at the top level; tcpdump expects `local_iface`.

## Other Actions

The wrapper also supports `status`, `stop`, `init`, `delete`, and incremental output with:

```json
{"start_line":0}
```
