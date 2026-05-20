# Log

Use logs when the subsystem is known or when alarms are the clearest starting point.

## Service Discovery

Run `log list` to see all available log services. The name is the daemon name as it appears in log prefixes:

```bash
agent-cli log list                    # CLI
{"subcommand":"list"}                 # MCP
```

Common services and what they cover:

| Service | Typical content |
|---------|----------------|
| `message` | Default aggregated log (no `--service` flag) |
| `NetworkManager` | AWS IoT MQTT, Shadow sync, firmware OTA, remote diagnostic tools |
| `redial` | Cellular modem dial-up, SIM detection, network registration, PDN activation |
| `lqm` | Link quality monitoring (ICMP/DNS/TCP probe results) |
| `firewall` | iptables rules, NAT, ACL |
| `agent` | DNS/DHCP (dnsmasq), DDNS, httpd, Nginx, sub-service management |
| `syswatcher` | Service heartbeats, restart triggers, memory alerts |

## Reading Strategy

### Default log

```bash
agent-cli log                         # Reads the default aggregated log
agent-cli log --line 200              # Last 200 lines
```

### Named service

```bash
agent-cli log NetworkManager --line 100
{"subcommand":"NetworkManager --line 100"}
```

### Incremental reading

When the log is too long for one read, use `--line` to reduce the window. If you still need more data, make multiple calls with decreasing `--line` values from the oldest timestamp boundary.

### MCP

Use the `log` MCP tool with subcommands such as:

```json
{"subcommand":"list"}
{"subcommand":"NetworkManager --line 100"}
```

## Multi-Service Correlation

Logs from different services share the same timestamp format. To correlate:

1. Start with the service whose error level (`[ER]`) appears first in the failure timeline.
2. Read adjacent services that commonly interact with it:

| Primary symptom service | Correlate with |
|-------------------------|----------------|
| `redial` (modem dial failure) | `lqm` (link probe triggered redial), `NetworkManager` (MQTT disconnect) |
| `NetworkManager` (cloud disconnect) | `redial` (cellular link state), `lqm` (link quality change) |
| `firewall` (rule failure) | `agent` (DNS/DHCP), `interface` (VLAN/port state) |
| `syswatcher` (service restart) | Any service that triggered the restart via heartbeat timeout |

3. Use the timestamp range to narrow each correlated log to the same time window.

## Log Truncation and Overflow

- If `--line 1000` does not reach the startup markers you need, the log buffer has been truncated.
- Reduce `--line` and read the most recent window instead. Do not loop trying to reach earlier data.
- If the log window is insufficient for diagnosis, use model-reference documents (in `agent-cli-device-diagnostics`) to infer service behavior from known patterns without full historical logs.

## Guardrails

- Do not invent service names. Use `log list` first when unsure.
- Prefer logs as supporting evidence, not as a substitute for schema or config inspection.
- For log pattern interpretation (matching error messages to root causes and solutions), route to `agent-cli-device-diagnostics` → `model-reference/index.md`.
