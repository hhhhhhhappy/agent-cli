---
name: agent-cli-operate
version: "1.1.0"
requires: [agent-cli-shared]
description: "High-risk device actions: firmware upgrade and reboot only. Use when the user explicitly says upgrade firmware, update firmware, flash firmware, reboot device, restart router/gateway, power cycle, or includes upgrade/reboot as an approved recovery step. For firmware version selection, release notes, or download URLs before the upgrade, consult agent-cli-shared."
---

# Agent CLI Operate

> Read [../agent-cli-shared/SKILL.md](../agent-cli-shared/SKILL.md) first.
Use this skill for high-risk operations that directly affect device availability.

## When to Use This Skill

Use this skill **only** when the user explicitly requests:
- **Firmware upgrade**: "upgrade firmware", "firmware update", "flash new firmware"
- **Device reboot**: "reboot the device", "restart the router", "restart the gateway", "power cycle"
- **Recovery flow**: the user explicitly includes upgrade or reboot as a required recovery step

## Do Not Use This Skill

- Checking firmware versions, changelogs, or "should I upgrade?" → `agent-cli-shared`
- Restart/bounce/reset a service, WAN, LAN, cellular, or interface → `agent-cli-config`, never this skill unless the user explicitly requests whole-device reboot
- Without explicit user approval — these are destructive actions

## Route By Intent (use inline params first; open reference only when needed)

- **Firmware upgrade**: requires `agent-cli-shared` first → resolve target version + official download URL via [../agent-cli-shared/references/firmware-release.md](../agent-cli-shared/references/firmware-release.md). Then execute: `agent-cli upgrade --url <https_url>` (CLI) or `{"source_type":"url","url":"<url>"}` (MCP). See [references/upgrade.md](references/upgrade.md) for full workflow (baseline snapshot → execute → wait for reconnect → verify `status basic`).
- **Device reboot**: `agent-cli reboot` (CLI) or dedicated `reboot` MCP tool. Immediate impact — confirm explicitly. Wait up to 3 min for reconnect, retry every 15s. Verify with `status basic`. See [references/reboot.md](references/reboot.md).
- **Firmware version selection / changelog**: → `agent-cli-shared` (this skill only executes, does not look up)

## Hard Rules

1. Require explicit approval before execution.
2. Verify the target device before acting.
3. Capture a baseline status snapshot first when it will help with verification.
4. Preserve Cross-Skill Handoff evidence from `agent-cli-shared`, but re-check target device and approval before execution.
5. After completion and reconnect, verify the device state with `status basic`.
