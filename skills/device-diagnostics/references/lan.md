# LAN

Use when the issue is local addressing, DHCP leases, client access, switch ports, or subnet reachability.

Read [tool-contract.md](tool-contract.md) only when the exact MCP call shape matters.

## Collection Sequence

1. Read `status basic`.
2. Read `status` and inspect LAN, DHCP, switch-port, bridge, or client-related keys that are returned.
3. Read the corresponding config roots only after the failing component is narrowed.
4. Read logs for DHCP, switching, bridge, or access-control services when present.
5. Use active diagnostics only when passive evidence does not explain the local failure.

## Interpretation

- Clients do not receive leases or appear on the wrong subnet: LAN or DHCP fault.
- A single access port is down or error-prone while the rest of the device is healthy: likely switch-port or physical issue.
- LAN looks healthy but upstream access fails for all clients: hand off to [connectivity.md](connectivity.md) or [wan.md](wan.md).

## Handoff Notes

- Keep evidence compact and cite exact commands or resource URIs.
- If the likely fix is mutating, present the exact proposed change and ask for approval before calling `config`, `upgrade`, or `reboot`.
