---
name: agent-cli-shared
version: "1.1.0"
requires: []
description: "Agent CLI setup and access foundation: first-time setup, bootstrap, auth/login, adding a device, selecting or switching device_id, choosing CLI vs MCP transport, handling SSH, connection, credential, or permission errors, and firmware release lookup before upgrade execution. Use when the user says first-time setup, initialize agent-cli, bootstrap, auth, login, add device, switch device, select device_id, SSH connection failed, connection error, bad credentials, permission denied, asks about safety checks before a risky command, or asks for firmware changelogs, version availability, official download URLs, or whether an upgrade is recommended. Not for executing routine status/log/config/diagnostic tasks, firmware upgrade execution, or reboot execution."
---

# Agent CLI Shared

Use this skill as the common preflight layer for the other `agent-cli-*` skills.

## When to Use This Skill

Use this skill **only** when the task involves:
- First-time agent-cli onboarding / setup
- Authentication or bootstrap (`auth login`, `auth bootstrap`)
- Adding or switching between devices (unknown `device_id`)
- Connection, SSH, transport, credential, or permission errors
- Safety rules, approval workflows, or write-operation guard checks
- Firmware release lookup, changelog review, version availability, official download URL selection, or upgrade recommendation before execution

## Do Not Route Other Domains Here

For routine tasks, route to the appropriate skill:
- Status / logs → `agent-cli-inspect`
- Config / schema / validation → `agent-cli-config`
- Cellular / ping / tcpdump / speedtest → `agent-cli-device-diagnostics`
- Firmware release lookup / changelog / version selection before execution → `agent-cli-shared`
- Upgrade execution / reboot execution → `agent-cli-operate`

This skill is a **dependency**, not a router or default entry point.

## Always Do First

1. Confirm whether the task should run through the local `agent-cli` CLI or through native MCP tools.
2. Confirm the target `device_id` when multiple devices are configured.
3. Default to read-only behavior until the user explicitly asks for a change.
4. Do NOT pre-load reference files speculatively. Open only the ONE reference matched by Route By Intent, and only when the inline table below does not already give you the parameters you need.
5. When you do open a reference, read only until you have the required command syntax or constraint — do not load the entire file into context unnecessarily.

## Route By Intent (use inline params first; open reference only when needed)

- **Auth / bootstrap**: `agent-cli auth [--device-ip <ip> --name <id>]`. Prompts for device IP, SSH port, web login user/password, and device name if no flags. Manage saved devices with `agent-cli auth list` and `agent-cli auth remove <name>` (or `--all`). For full global options (`--config`, `--runtime-dir`, `--timeout-sec`, `--takeover`, `--overwrite`) see [references/transport-cli.md](references/transport-cli.md).
- **Transport choice**: Prefer MCP when available (structured read-only: `status`, `config`, `log`, `schema`, `tool`, `upgrade`, `reboot`). Fall back to CLI when MCP unavailable or for auth/bootstrap. MCP fixed resource URIs: `device://<device_id>/status/basic` etc. See [references/transport-mcp.md](references/transport-mcp.md).
- **Device selection**: `device_id` required when multiple devices. Omit when exactly one. Never invent `default`.
- **Safety / approval**: Read-only by default. Explicit approval before `config set`, `upgrade`, `reboot`. Hard stops on unknown device_id / root / payload. See [references/safety.md](references/safety.md) for full gates.
- **Error recovery**: Match failure to category in [references/error-recovery.md](references/error-recovery.md). One retry for transient errors. Escalate, don't loop. Terminal results are final.
- **Firmware release lookup**: Use [references/firmware-release.md](references/firmware-release.md) for official changelog, version availability, download URL selection, or "should I upgrade?" questions. Execute upgrades only through `agent-cli-operate`.
- Use this skill for `auth` and bootstrap questions directly.
- If the user is not yet onboarded, route to the CLI bootstrap flow in [references/transport-cli.md](references/transport-cli.md).

## Cross-Skill Handoff

Use a handoff when one user task spans multiple `agent-cli-*` skills. Finish the current skill's safe evidence collection first, then pass this compact handoff package:

- `target_skill`: one of `agent-cli-inspect`, `agent-cli-config`, `agent-cli-device-diagnostics`, `agent-cli-operate`, or `agent-cli-shared`
- `reason`: why ownership changes
- `evidence`: commands/resources already checked and the key results
- `proposed_action`: exact next command, payload, or lookup to perform
- `approval_state`: `not_required`, `needed`, or `approved`
- `verification_goal`: how to confirm success after the next skill acts

Common sequences:
- Status/logs show a fault symptom → hand off to `agent-cli-device-diagnostics` with observed status/log evidence.
- Diagnostics identify a config change → hand off to `agent-cli-config` with the suspected root, required schema checks, proposed payload, and approval state.
- Config write completes → hand off back to `agent-cli-device-diagnostics` or `agent-cli-inspect` with the verification goal.
- Firmware lookup selects a target version and URL → hand off to `agent-cli-operate` only after explicit approval.
- Any path reaches reboot/upgrade execution → hand off to `agent-cli-operate`; do not execute it inside other skills.

## Operating Boundaries

- Do not invent `device_id` values, config keys, schema roots, log services, tool names, or JSON payloads.
- If exactly one device is configured, omit `device_id`. If multiple devices are configured and the user did not identify one, ask first.
- Prefer MCP for structured read-only work when those tools are available in the current agent environment.
- Prefer the CLI when MCP is unavailable or when the current environment only exposes the local `agent-cli` executable.
- Before any non-trivial config write, read schema and validation rules first.
- Before any `upgrade`, `reboot`, or disruptive diagnostic action, enforce the approval rules in [references/safety.md](references/safety.md).
