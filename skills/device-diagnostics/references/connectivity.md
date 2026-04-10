# Connectivity

Use when the symptom is no internet, DNS failure, intermittent reachability, or packet loss.

Read [tool-contract.md](tool-contract.md) only when the exact MCP call shape matters.

## Collection Sequence

1. Read `status basic`.
2. Read `status` and inspect routing, uplink, DNS, or connectivity-related keys that are returned.
3. Use `schema <root_key>` and inspect the returned `status` section to interpret unfamiliar runtime fields.
4. Read related config only if status suggests a configuration issue.
5. Read `tool list` before choosing active diagnostics.
6. Run ping against the default gateway, then a public IP, then a DNS name if the tool and targets are available.
7. Run traceroute only when ping narrows the problem to an upstream path.
8. Read relevant logs after narrowing the failing layer.

## Interpretation

- Gateway ping works but public IP ping fails: likely upstream or ISP/carrier problem.
- Public IP ping works but DNS name ping fails: likely DNS resolution problem.
- WAN or uplink status lacks address, gateway, or usable route: hand off to [wan.md](wan.md).
- Connectivity failures correlate with weak radio metrics or modem-session issues: hand off to [cellular.md](cellular.md).

## Handoff Notes

- Keep evidence compact and cite exact commands or resource URIs.
- If the likely fix is mutating, present the exact proposed change and ask for approval before calling `config`, `upgrade`, or `reboot`.
