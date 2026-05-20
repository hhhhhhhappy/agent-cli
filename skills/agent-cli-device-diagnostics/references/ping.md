# Ping

Use ping for basic reachability and packet-loss checks.

## CLI

```bash
agent-cli tool ping {"action":"start","host":"8.8.8.8"}
agent-cli tool ping {"action":"status"}
agent-cli tool ping {"start_line":0}
agent-cli tool ping {"action":"stop"}
```

## MCP

Use the `tool` MCP tool with:

```json
{"subcommand":"ping {\"action\":\"start\",\"host\":\"8.8.8.8\"}"}
```

## Notes

- The MCP/server contract documents default values for ping start when omitted: `interface=any`, `ping_count=4`, and `packet_size=32`.
- Use output polling when you need incremental results.
