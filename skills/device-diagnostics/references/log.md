# Log

Use when repeated errors, alarms, or service failures are the clearest starting point and the right subsystem is not yet known.

Read [tool-contract.md](tool-contract.md) only when the exact MCP call shape matters.

## Collection Sequence

1. Read `log list`.
2. Start with the service most closely tied to the user-visible symptom.
3. Read a small number of lines first, then expand only if the error pattern is unclear.
4. Correlate the error timestamps with current status and recent diagnostics.
5. Route into the appropriate playbook once the failing subsystem is identified.

## Interpretation

- DHCP, PPP, modem, or routing errors should redirect to the matching domain playbook.
- Repeated permission, auth, or policy errors often need [config-audit.md](config-audit.md).
- If logs are noisy but status is healthy, call out the uncertainty instead of overstating a conclusion.

## Handoff Notes

- Route to [wan.md](wan.md), [cellular.md](cellular.md), [connectivity.md](connectivity.md), or [lan.md](lan.md) once the failing subsystem is clear.
- Keep evidence compact and cite exact commands or resource URIs.
