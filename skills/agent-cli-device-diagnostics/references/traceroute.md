# Traceroute

Use traceroute for path analysis when the target is reachable but routing or path quality is uncertain.

## CLI

```bash
agent-cli tool traceroute {"action":"start","host":"8.8.8.8"}
```

## MCP

Use the `tool` MCP tool with:

```json
{"subcommand":"traceroute {\"action\":\"start\",\"host\":\"8.8.8.8\"}"}
```

## Notes

- The MCP/server contract documents a default `interface=any` when omitted.
- Follow the generic `status`, output polling, and `stop` pattern when the backend exposes them for the current traceroute run.
