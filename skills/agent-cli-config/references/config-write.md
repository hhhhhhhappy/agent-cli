# Config Write

Use this reference for actual configuration changes.

## CLI

```bash
agent-cli config set system {"hostname":"lab-a"}
agent-cli config set wan {"uplinks":[{"name":"wan1","enabled":true}]}
```

Behavior from the CLI help:

- `config set <root> <json_payload>` only accepts a root key such as `system`.
- The payload is wrapped under that root automatically by the CLI contract.
- `config set` performs built-in preflight validation before apply and returns a validation summary on success.

## MCP

Use the `config` MCP tool with a `subcommand` string such as:

```json
{"subcommand":"set system {\"hostname\":\"lab-a\"}"}
```

## Business Rules & Cascade Operations

Before writing, run `schema <root> --validation` for the target root. Check ALL rule types returned.

### add_rules / delete_rules (blocking checks)
- **ADD**: check `add_rules` — conflict_check (target already exists?), reference_check (target used by another module?).
- **DELETE**: check `delete_rules` — reference_check (target referenced by another module?).
- If blocked → **STOP and explain to user**. Do not propose workarounds that violate the rule.

### constraints (module-level limits)
- `max_items` / `protected_items` / `builtin_only` — check before ADD or DELETE.
- `mutex` — check if another module state (e.g., ippt.enabled) disables this one.
- `conditional_lock` — check cross-module conditions (e.g., WAN exists → LAN2 locked).
- `unique_check` / `reserved_name` / `port_distinct` / `pair_check` — validate payload values.

### dependencies (cross-module)
- `requires` + `check` — the referenced dependency (e.g., LAN for WiFi) must exist in current config.
  - If missing → **STOP. Tell user to create the dependency first.**
- `used_by` + `check_field` — if deleting, check who references this item.

### cascade_operations (side effects — ALL operation types)

| Op | cascade_operations | Action |
|----|-------------------|--------|
| ADD | `on_add` | Create default entries. `fixed_uuid` → use directly. Include in payload or as separate `config set` calls. |
| DELETE | `on_delete` | For each entry: `fixed_uuid` → use directly. Otherwise → `config get <target_root>` → filter by `match_field == match_value` → `config set <root> {"<uuid>": null, ...}` per root. |
| MODIFY | `on_modify` | For `sync` entries → update the `field` in the target root to match the modified value. |

**Cascade operations are NOT optional. Every entry MUST be executed.**

## Pre-Write Gate (MANDATORY — check before executing)

> ⚠️ **Before you run `config set`, verify ALL applicable items for your tier. If any is false, STOP and return to the missing gate.**

### All Tiers
- [ ] Gate 2: `schema <root>` output is in context (NOT from memory)
- [ ] Gate 2: `schema <root> --validation` output is in context
- [ ] Gate 2.5: Tier has been classified
- [ ] Gate 3: Current config baseline has been read (if modifying existing fields)
- [ ] Every payload field appears in schema, type matches, value in range/enum

### Tier 2/3 Additional
- [ ] Gate 4a: Business Rules Check Table in validation.md is COMPLETE — all add_rules/delete_rules/constraints/dependencies checked
- [ ] Gate 4a: No business rule blocks the operation. If blocked, STOP.
- [ ] Gate 4b: Schema-Payload Cross-Reference Table in validation.md is COMPLETE
- [ ] Gate 4b: ALL rows in the cross-reference table show ✓ for both Type Match? and Value Match?
- [ ] Gate 4.5: cascade_operations (on_add/on_delete/on_modify) processed — all cascade payloads collected, ready to execute
- [ ] Gate 5: User has explicitly approved the payload

### Tier 3 Additional
- [ ] Risk Assessment Table is COMPLETE — all mutex/conditional_lock/cross-root cascade entries evaluated
- [ ] Rollback Plan is prepared — snapshots captured for all affected roots

## Required Steps

1. Classify tier at Gate 2.5 using the Tier Decision table in [validation.md](validation.md).
2. **Tier 1**: Inline validate → write → verify (Gate 2 → 3 → 7).
3. **Tier 2**: Full gate sequence including Business Rules Check Table, Schema-Payload Cross-Reference Table, and cascade operations (see [SKILL.md](../SKILL.md)).
4. **Tier 3**: Tier 2 all + Risk Assessment Table + Rollback Plan.
5. Confirm user intent before writing (mandatory for Tier 2/3, recommended for Tier 1).
6. Apply one root payload. Expect the command to block on schema or runtime validation failures.
7. Verify with `config get <root>` and related status areas.

## Restarting a Network Interface

When the user asks to restart WAN, reset a network interface, or bounce the cellular interface, use `config set` to disable and re-enable the target interface. This is a **Tier 2** operation (two sequential config writes).

1. Read current config with `config get <root>` to capture the current state.
2. Disable the interface via `config set` (e.g., set `enabled: false` on the target uplink).
3. Wait briefly, then re-enable the interface via `config set` (e.g., set `enabled: true`).
4. Verify with `config get <root>` that the interface is back up.

Follow the Tier 2 (STANDARD) gate workflow for both the disable and enable steps.

## Guardrails

- Do not use nested keys with `config set`.
- Do not guess payload shape from memory when schema is available.
- If the Pre-Write Gate checklist above has any unchecked item, do NOT execute `config set`.
- After `config set` succeeds and validation passes, still verify with `config get <root>`.
