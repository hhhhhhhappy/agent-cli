---
name: agent-cli-device-diagnostics
version: "1.1.0"
requires: [agent-cli-shared]
description: "Device-side troubleshooting and evidence collection: diagnose cellular problems and investigate network symptoms with active diagnostic tools. Use when the user says cellular problem, weak signal, SIM/APN issue, registration failure, frequent disconnections, device offline, network unreachable, unstable link, redial error, high latency, packet loss, run ping/traceroute/tcpdump/iperf/speedtest, or asks to diagnose a network or connectivity problem. Prefer this skill when the user reports a fault symptom and wants diagnosis rather than a simple status snapshot. Not for config changes or executing upgrade/reboot. For firmware release lookups, consult agent-cli-shared."
---

# Agent CLI Device Diagnostics

> Read [../agent-cli-shared/SKILL.md](../agent-cli-shared/SKILL.md) first.
Use this skill for device-side troubleshooting and evidence collection. It owns two public areas: cellular diagnosis and active diagnostic tools. If the diagnostic flow requires firmware information (release notes, changelogs, version comparison), consult `agent-cli-shared` for that lookup.

## When to Use This Skill

Use this skill when the user intends to:
- **Diagnose cellular issues**: weak signal, SIM errors, APN problems, registration failure, disconnection, latency, "no internet on cellular"
- **Diagnose a network symptom with active tools**: packet loss, high latency, reachability failures, path problems, throughput tests, packet capture
- **Run active diagnostic tools**: `ping`, `traceroute`, `tcpdump`, `iperf`, `speedtest`

Simple "is it online right now?" snapshots belong to `agent-cli-inspect`. Use this skill for "why is it offline?", repeated disconnects, or fault investigation.

## Route By Intent (use inline params first; open reference only when needed)

### Device-Specific Diagnostics
- **Cellular diagnosis** (cannot connect, frequent disconnection, high latency) → [references/cellular.md](references/cellular.md)
  - Flow: `status cellular` gate → `config get cellular` + `log redial --line 1000` → SIM/registration/PDN checks
  - Pairs with model-reference for per-service log patterns when the current device model has a directory (see below).

### Log Pattern Interpretation
- **Log-based service diagnosis**: only when a specific log error pattern has been identified → [references/model-reference/index.md](references/model-reference/index.md)
  - Prerequisite: device model from `status basic`. Only navigate `model-reference/<MODEL>/` if the model directory exists.
  - Path: `index.md` → `<MODEL>/index.md` → `<service>.md` → match log pattern → execute solution.
  - Do NOT open model-reference files speculatively. Open only the ONE service document matching the identified error prefix.

### Active Diagnostic Tools (open tool reference only when running that tool)
- **Tool contract** (CLI/MCP payload shape, output structure) → [references/tool-contract.md](references/tool-contract.md)
- **Ping** (ICMP reachability): `tool ping {"action":"start","host":"8.8.8.8"}`. Defaults: `interface=any`, `ping_count=4`, `packet_size=32`. Actions: `start`, `status`, `stop`. → [references/ping.md](references/ping.md)
- **Traceroute** (path analysis): `tool traceroute {"action":"start","host":"8.8.8.8"}`. Default `interface=any`. → [references/traceroute.md](references/traceroute.md)
- **Tcpdump** (packet capture): `tool tcpdump {"action":"start","capture_mode":"show","capture_time":300,"local_iface":[{"interface":"wan1","expert_options":""}]}`. `capture_mode` MUST be `show`. `local_iface` MUST have exactly 1 item. See [references/tcpdump.md](references/tcpdump.md) for full constraints.
- **Iperf** (throughput): `tool iperf {"action":"start","role":"client","command":"<target>","capture_time":10}`. Traffic-generating — confirm before running on sensitive links. → [references/iperf.md](references/iperf.md)
- **Speedtest** (public internet bandwidth): `tool speedtest {"action":"servers"}` → choose server → `tool speedtest {"action":"start","server_id":12345,"ip":"<server_ip>"}`. Use `ip` not `interface`. Actions: `servers`, `start`, `status`, `output`, `stop`. → [references/speedtest.md](references/speedtest.md)

## Entry Flow

1. Confirm the target `device_id`. If exactly one device is configured, omit it. If multiple devices are configured and the user did not identify one, ask first.
2. Stay read-only by default. Do not run generic discovery outside the selected reference.
3. Route to one primary reference based on the user-visible symptom: `cellular`, the requested active diagnostic tool, or `model-reference` for log pattern interpretation.
4. When routing to model-reference: first obtain the device model from `status basic`, then navigate `model-reference/index.md → <MODEL>/index.md → <service>.md`, and match log patterns to the diagnostic chapters.
5. Read [references/tool-contract.md](references/tool-contract.md) only when the exact CLI or MCP payload contract matters.
6. If the task is really generic status or log observation, switch to `agent-cli-inspect`. If it is config read, schema, validation, or write work, switch to `agent-cli-config`. If it is an approved upgrade execution or reboot, switch to `agent-cli-operate`. Use the Cross-Skill Handoff format from `agent-cli-shared` when switching.
7. Finish with a structured result containing `Summary`, `Findings`, `Evidence`, `Gaps`, and `Next actions`.

## Operating Boundaries

- This skill does not route generic troubleshooting across every fault domain.
- If the investigation requires firmware information (release notes, changelogs, version comparison), consult `agent-cli-shared` for that lookup.
- Treat active `tool` runs as potentially disruptive even when they do not permanently change configuration.
- Do not execute `upgrade` or `reboot` inside this skill.
- Do not invent status keys, config keys, log services, tool names, enum values, firmware URLs, or JSON payloads.
- Escalate from passive inspection to live diagnostics only when the selected reference calls for it and passive data is insufficient.
- Suggest changes first. Use mutating actions only when the user explicitly asks or approves a concrete recovery step.
- If the investigation leads to a config change, firmware upgrade, or reboot, hand off to `agent-cli-config`, `agent-cli-shared`, or `agent-cli-operate` with evidence, proposed action, approval state, and verification goal.

## Output Contract

Always return:
- `Summary`: one sentence naming the most likely fault domain.
- `Findings`: one to three concrete conclusions.
- `Evidence`: command or resource results that support each finding.
- `Gaps`: missing evidence or uncertainty that still matters.
- `Next actions`: safe next steps, with an explicit approval gate before any mutating command.
