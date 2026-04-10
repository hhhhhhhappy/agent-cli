# WAN

Use when the problem is limited to a wired or uplink interface, WAN DHCP/static behavior, gateway loss, or route selection.

Read [tool-contract.md](tool-contract.md) only when the exact MCP call shape matters.

## Collection Sequence

1. Read `status basic`.
2. Read `status` and inspect uplink or interface keys that are returned.
3. Read `config list` and then only the relevant uplink config roots.
4. Read `schema <root>` and `schema <root> --validation` before suggesting a configuration fix.
5. Run ping or traceroute from the affected interface only when passive evidence is insufficient.
6. Read logs for DHCP, routing, PPP, or link events if available.

## Interpretation

- Interface down, no carrier, or missing lease: physical, DHCP, or upstream access problem.
- Interface has address but no correct gateway or route: routing or policy problem.
- Status and config disagree on intended uplink behavior: hand off to [config-audit.md](config-audit.md).
- WAN is healthy and only local clients fail: hand off to [lan.md](lan.md).

## Handoff Notes

- Keep evidence compact and cite exact commands or resource URIs.
- If the likely fix is mutating, present the exact proposed change and ask for approval before calling `config`, `upgrade`, or `reboot`.
