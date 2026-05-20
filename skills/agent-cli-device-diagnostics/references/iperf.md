# Iperf

Use iperf for controlled throughput testing when the user needs application-path performance evidence.

## CLI

```bash
agent-cli tool iperf {"action":"start","role":"client","command":"198.51.100.10","capture_time":10}
```

## MCP

Use the `tool` MCP tool with a `subcommand` string carrying the same JSON payload.

## Notes

- Use `tool list` first if the exact iperf payload contract is uncertain in the current backend version.
- Treat iperf as an active traffic-generating diagnostic and confirm before running it on sensitive links.
- Follow the generic `status`, output polling, and `stop` pattern when the backend exposes them for the current run.
