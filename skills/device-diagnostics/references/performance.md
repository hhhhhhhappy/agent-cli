# Performance

Use when the complaint is low throughput, high latency, jitter, or slow application traffic.

Read [tool-contract.md](tool-contract.md) only when the exact MCP call shape matters.

## Collection Sequence

1. Read `status basic` and the relevant status keys for the affected interface.
2. Use `schema <root_key>` and inspect the returned `status` section to interpret unfamiliar runtime fields.
3. Read logs for retransmits, interface flaps, modem instability, or queue pressure when available.
4. Read `tool list` before choosing an active diagnostic.
5. Use `speedtest` for general upstream throughput when the remote environment permits it.
6. Use `iperf` only when the user or environment provides a reachable peer.
7. Use `tcpdump` only when packet capture is necessary and the extra output is justified.
8. Stop long-running diagnostics after collecting the needed evidence.

## Interpretation

- Low throughput across every test path: likely carrier, WAN, or cellular capacity issue.
- Good raw throughput but poor name resolution or session setup: hand off to [connectivity.md](connectivity.md).
- Only one interface or transport is degraded: hand off to [wan.md](wan.md) or [cellular.md](cellular.md).

## Handoff Notes

- Keep evidence compact and cite exact commands or resource URIs.
- If the likely fix is mutating, present the exact proposed change and ask for approval before calling `config`, `upgrade`, or `reboot`.
