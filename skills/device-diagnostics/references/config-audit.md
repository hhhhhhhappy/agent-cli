# Config Audit

Use when the device is reachable but the observed behavior does not match the intended configuration.

Read [tool-contract.md](tool-contract.md) only when the exact MCP call shape matters.

## Collection Sequence

1. Read `config list`.
2. Read only the config roots related to the symptom.
3. Read `schema <root>` and `schema <root> --validation`.
4. Compare intended config, runtime status, and logs.
5. Identify the smallest safe change that would test the hypothesis.

## Interpretation

- Missing required fields, invalid combinations, or obvious schema violations: primary configuration fault.
- Config is valid but runtime status is unhealthy: hand off to [wan.md](wan.md), [lan.md](lan.md), [cellular.md](cellular.md), or [connectivity.md](connectivity.md) based on the failing state.
- If the likely fix is mutating, present the exact proposed change and ask for approval before calling `config`.

## Handoff Notes

- Keep evidence compact and cite exact commands or resource URIs.
- Do not apply the proposed change unless the user explicitly approves it.
