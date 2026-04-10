---
name: device-diagnostics
description: Diagnose router, gateway, and network-edge device issues through the agent-cli MCP server, and research official firmware resources from the vendor website when changelog or download lookup is needed. Use this as the single entry point for proactive status checks and troubleshooting across connectivity, cellular, WAN, LAN, performance, log, configuration-audit, and firmware-release scenarios.
---

# Device Diagnostics

## Overview

Use this skill as the single public entry point for device troubleshooting through the `agent-cli` MCP server. This file is the routing layer only: identify the primary fault domain, open the matching playbook under `references/`, and follow that file for the concrete collection and interpretation steps. The `firmware-release` playbook now covers official firmware discovery, changelog analysis, upgrade advice, and user-approved upgrade execution.

## Entry Flow

1. Confirm the target `device_id`. If the MCP server exposes exactly one device, omit it. If multiple devices are configured and the user did not identify one, ask before running commands.
2. Stay read-only by default. Do not run generic discovery outside the selected playbook.
3. Route to one primary playbook based on the user-visible symptom.
4. Route to `firmware-release` when the user asks about updates, changelog, upgrade guidance, or download links, or when the current device problem may be explained by a known firmware fix.
5. Read only the routed playbook and execute the diagnostic flow described there.
6. Pull in a second playbook only when the first playbook's evidence clearly crosses fault domains.
7. Finish with a structured result containing `Summary`, `Findings`, `Evidence`, `Gaps`, and `Next actions`.

## Operating Boundaries

- Read [references/tool-contract.md](references/tool-contract.md) before using the MCP tools when exact call shape matters.
- Read [references/playbooks.md](references/playbooks.md) only as the playbook index, then open the routed file.
- Do not read [references/inhand-release-api.md](references/inhand-release-api.md) unless the selected playbook is `firmware-release`.
- Fixed resource URIs always require the real configured `device_id`. Do not invent placeholders such as `default` in `device://<device_id>/...` URIs.
- When the selected playbook is `firmware-release`, read local `status basic` before any website request, use the normalized model prefix only for product-family lookup, prefer the exact full model for variant-specific firmware lookup, and call `poweris.inhandnetworks.com` with shell `curl` commands that explicitly set the required headers from [references/inhand-release-api.md](references/inhand-release-api.md). If the maintained `category_group` map has no entry for `model_family`, fetch the official root `category-groups?locale=en` directory once, return that catalog as evidence, and stop instead of guessing. Do not use generic `Fetch` helpers for that host.
- Treat `config`, `upgrade`, `reboot`, and active `tool` runs as potentially disruptive even when they do not permanently change configuration.
- Do not invent status keys, config keys, log services, tool names, enum values, or JSON payloads.
- Escalate from passive inspection to live diagnostics only when the selected playbook calls for it and passive data is insufficient.
- Suggest changes first. Use mutating actions only when the user explicitly asks or approves a concrete recovery step.
- Do not call `upgrade` until the user has approved the action, chosen an exact target version, and you have resolved the final official download URL for that exact artifact.

## Routing Table

- Route to [references/connectivity.md](references/connectivity.md) for no internet, DNS failure, packet loss, or intermittent reachability.
- Route to [references/cellular.md](references/cellular.md) for proactive cellular status or signal checks, SIM or carrier registration issues, APN or modem-session problems, frequent cellular disconnections, or high cellular latency.
- Route to [references/wan.md](references/wan.md) for wired uplink failure, WAN DHCP/static issues, gateway loss, or route problems.
- Route to [references/lan.md](references/lan.md) for DHCP leases, local subnet reachability, client access, or switch-port behavior.
- Route to [references/performance.md](references/performance.md) for general low throughput, high latency, jitter, or slow application traffic when the fault domain is not already isolated to cellular, WAN, or LAN.
- Route to [references/log.md](references/log.md) when logs or alarms are the clearest starting point and the failing subsystem is still unknown.
- Route to [references/config-audit.md](references/config-audit.md) when the device is reachable but the observed behavior does not match intended configuration.
- Route to [references/firmware-release.md](references/firmware-release.md) for official firmware availability, changelog analysis, upgrade advice, version-specific download URLs, approved firmware upgrade execution, or other vendor release artifacts.

## Output Contract

Always return:

- `Summary`: one sentence naming the most likely fault domain.
- `Findings`: one to three concrete conclusions.
- `Evidence`: command or resource results that support each finding.
- `Gaps`: missing evidence or uncertainty that still matters.
- `Next actions`: safe next steps, with an explicit approval gate before any mutating command.
- Write the final answer for the end user, not for an internal maintainer. Prefer plain language such as "the vendor's public site does not show this model yet" over internal labels like `model_family`, `category_group`, `product_category`, or "maintained map".
- Keep internal identifiers and API field names in working notes only. Mention them in the final answer only when they are truly necessary for support escalation or the user explicitly asks for the low-level details.
