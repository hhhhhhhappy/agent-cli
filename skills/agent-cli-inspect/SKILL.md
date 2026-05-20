---
name: agent-cli-inspect
version: "1.1.0"
requires: [agent-cli-shared]
description: "Device status, log, and current firmware version inspection: read runtime state, health, alarms, logs, and the installed firmware version without changing configuration. Use when the user says show status, is the device online, health check, status, how is the device doing, show logs, check errors, recent errors, alarms, service log, current firmware version, what firmware is running, or asks what the device is doing right now. Not for config/schema work, upgrades/reboots, active diagnostic tools, or firmware release/changelog lookups."
---

# Agent CLI Inspect

> Read [../agent-cli-shared/SKILL.md](../agent-cli-shared/SKILL.md) first.
This skill is the read-only observation layer for device status, logs, and the currently-installed firmware version (from `status basic`). It does not look up release notes, changelogs, or official firmware availability.

## When to Use This Skill

Use this skill when the user intends to:
- **Check device status**: runtime state, health, connectivity snapshot, `status`
- **Review logs**: read logs, search errors, view alarms, service output, `log`
- **Check current firmware version**: what firmware version is installed now (from `status basic`)

## Route By Intent (use inline params first; open reference only when needed)

- **Runtime state, health, connectivity**: `status list` → discover keys. `status basic` → model + firmware version. `status cellular` → signal/registration/APN. `status wan` → uplink state. See [references/status.md](references/status.md) for full key list.
- **Online/offline snapshot**: Use this skill for "is it online right now?" checks. If the user asks why it is offline, reports repeated disconnects, or wants fault investigation, switch to `agent-cli-device-diagnostics`.
- **Logs, alarms, service output**: `log list` → discover services. `log <svc> --line N` → read last N lines. Common services: `redial` (cellular dial), `NetworkManager` (cloud MQTT), `lqm` (link probe), `syswatcher` (heartbeats), `firewall` (rules). See [references/log.md](references/log.md) for correlation and overflow handling. For log pattern interpretation, route to `agent-cli-device-diagnostics`.
- **Current firmware version**: `status basic` returns `model` and `firmware` fields. This skill only reads the installed version; for release notes, changelog, or upgrade decisions → switch to `agent-cli-shared`.
- Config / schema questions → switch to `agent-cli-config`
- Cellular diagnosis, active tools (ping/tcpdump/speedtest/iperf/traceroute) → switch to `agent-cli-device-diagnostics`
- Upgrade / reboot → switch to `agent-cli-operate`

## Working Rules

1. Stay read-only.
2. Use discovery commands first when the exact key or service is unknown.
3. If the inspection result implies further action, use the Cross-Skill Handoff format from `agent-cli-shared`; do not execute mutating operations here.
