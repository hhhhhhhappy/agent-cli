---
name: agent-cli-config
version: "1.1.0"
requires: [agent-cli-shared]
description: "Device configuration and schema work: discover config roots, read current settings, inspect schema and validation rules, and change device configuration. Use when the user says show config, current config, config items, config get, config list, schema, validation, change config, edit parameters, modify hostname/APN/IP/DNS/WAN/LAN/VPN/system settings, set parameters, apply config, restart an interface, restart WAN interface, reset network interface, bounce the cellular interface, or validate a payload before writing. This skill owns config reads and schema lookups; it is not for runtime status/logs, firmware upgrades/reboots, or active diagnostics."
---

# Agent CLI Config

> Read [../agent-cli-shared/SKILL.md](../agent-cli-shared/SKILL.md) first.
This skill owns all config reads, schema lookups, validation checks, and config writes.

## When to Use This Skill

Use this skill when the user intends to:
- **Read configuration**: `config get`, `config list`, view current settings, query device parameters
- **Write configuration**: `config set`, change a setting, update a value, modify system/network/cellular parameters
- **Validate before writing**: run schema checks, preflight validation, verify allowed fields or payload shape
- **Discover config structure**: find available config roots, understand field types, enum values, schema, and validation rules

## Route By Intent (use inline params first; open reference only when needed)

- **Discover roots or read current values**: `config list` → roots. `config get <root>` or `config get <root>.<field>` → values. See [references/config-read.md](references/config-read.md).
- **Schema discovery**: `schema list` → roots with descriptions. `schema <root>` → field types. `schema <root> --validation` → business rules (constraints, dependencies, add_rules, delete_rules, cascade_operations). See [references/schema.md](references/schema.md).
- **Write configuration**: See Tiered Write Workflow below. Tier classification table is in [references/validation.md](references/validation.md) — open it at Gate 2.5. Full workflow gates are documented inline below and in [references/config-write.md](references/config-write.md).
- Status / logs → switch to `agent-cli-inspect`
- Upgrade / reboot → switch to `agent-cli-operate`
- Diagnostics → switch to `agent-cli-device-diagnostics`
- Restart/bounce/reset an interface or service → stay in `agent-cli-config`
- Reboot/restart the whole router, gateway, or device → switch to `agent-cli-operate`
- When entering from diagnostics or inspect, preserve the Cross-Skill Handoff evidence from `agent-cli-shared` and use it only to choose roots/verification goals; still run this skill's schema, validation, baseline, and approval gates.

## Tiered Write Workflow (MANDATORY GATED SEQUENCE)

> ⚠️ **Every step is a hard gate. You MUST NOT proceed to the next step until the current step produces concrete output. Do not skip any step. Do not proceed from memory.**

Operations are classified into three tiers after Gate 2. Higher tiers add gates; lower tiers skip gates that are unnecessary for the risk level.

---

### Gate 1: Discover Root [Tier 2/3]
- Run `config list` if the target root is unknown or uncertain.
- **You MUST know the exact root name from `config list` output before proceeding.**
- Skip for Tier 1 when the root is already known from context (e.g., user said "change system hostname").

### Gate 2: Read Schema, Validation & Business Rules [ALL TIERS]
- Run `schema <root>` to get the complete field list, types, and constraints.
- Run `schema <root> --validation` to get runtime validation rules. The command returns business rules including:
  - `constraints` — max_items, protected_items, mutex, conditional_lock, unique_check, etc.
  - `dependencies` — requires/used_by cross-module relationships
  - `add_rules` (if adding) / `delete_rules` (if deleting) — blocking conditions
  - `cascade_operations` — on_add / on_delete / on_modify side effects
- **You MUST have the `schema <root> --validation` output for this root in context. Do not proceed from memory.**

### Gate 2.5: Tier Decision [ALL TIERS — CLASSIFY BEFORE PROCEEDING]

Open [references/validation.md](references/validation.md) and classify the operation using the Tier Decision table:

| Operation Characteristics | Tier | Gates Required |
|---|---|---|
| Modify existing field values only. No list add/delete. No `add_rules`/`delete_rules` keys in `--validation`. No `mutex`/`conditional_lock`. No `cascade_operations`. | **Tier 1 (LIGHT)** | 2 → 3 → 7 |
| Add or delete list items, OR `add_rules`/`delete_rules` present in `--validation` output. | **Tier 2 (STANDARD)** | 1 → 2 → 3 → 4a → 4b → 4.5 → 5 → 6 → 7 |
| `mutex`, `conditional_lock`, `cascade_operations` with cross-root effects, OR `dependencies` spanning multiple roots. | **Tier 3 (HEAVY)** | Tier 2 all + Risk Assessment Table + Rollback Plan |

---

### Gate 3: Read Current Config (Baseline) [ALL TIERS]
- Run `config get <root>` to capture the current state.
- `config get` can target nested keys such as `system.hostname`, unlike `config set` which requires a root key.
- Required whenever the change modifies, removes, or depends on existing fields.
- **You MUST have current config output before building the new payload.**

---

## Tier 1: Field Value Change (LIGHT)

**Applies when**: modifying values of existing fields only (e.g., change `hostname`, toggle `enabled`, set `log_level`).

**Workflow**: Gate 2 → Gate 3 → validate types inline → Gate 7.

### Tier 1 Write

1. After Gate 3, validate directly against `schema <root>`:
   - Each field in your payload MUST appear in schema.
   - Each value type MUST match schema type exactly.
   - Each value MUST be within allowed range/enum from `schema <root> --validation`.
   - If any check fails → **STOP and fix.**
2. Build the payload and execute `config set <root> <json_payload>`.
   - User confirmation is recommended but NOT a hard gate for Tier 1.
   - Only use a root key (e.g., `system`), never a nested key.
3. Proceed to Gate 7 for verification.

---

## Tier 2: List Structure Change (STANDARD)

**Applies when**: adding/deleting list items, or `add_rules`/`delete_rules` present in validation output.

### Gate 4: Business Rules & Schema Audit (MANDATORY — SEE validation.md)
Open [references/validation.md](references/validation.md). Complete BOTH tables in order:

**4a. Business Rules Check Table** — validate against `schema <root> --validation` output:
- **ADD**: check `add_rules` (conflict_check, reference_check), `constraints` (max_items)
- **DELETE**: check `delete_rules` (reference_check), `constraints` (protected_items, builtin_only)
- **ALL**: check `constraints` (mutex, conditional_lock, unique_check, reserved_name), `dependencies` (requires)
- Every rule must be evaluated against current config. If blocked → **STOP and explain why.**

**4b. Schema-Payload Cross-Reference Table** — validate against `schema <root>` output:
- Every payload field vs schema: type match, value match, required fields present.
- If any ✗ → **STOP. Fix before proceeding.**

### Gate 4.5: Cascade Operations
Read `cascade_operations` from `schema <root> --validation` output. Process by operation type:

| Operation | Process |
|-----------|---------|
| **ADD** | `on_add` — for each entry, create defaults (use `fixed_uuid` if given). Add to payload or as separate `config set` calls. |
| **DELETE** | `on_delete` — for each entry: `fixed_uuid` → use directly; otherwise `config get <target_root>` + filter by `match_field == match_value` → collect UUIDs → `config set <root> {"<uuid>": null, ...}` per root. |
| **MODIFY** | `on_modify` — for each `sync` entry, update the referenced field in the target root. |

**Cascade operations are NOT optional. Every cascade entry MUST be processed.**

### Gate 5: User Confirmation
- Present the cross-reference table and the final JSON payload to the user.
- **You MUST receive explicit user approval (e.g., "yes", "confirm", "apply") before Gate 6.**

### Gate 6: Execute Write
- Run `config set <root> <json_payload>`.
- Only use a root key (e.g., `system`), never a nested key.
- The command performs built-in preflight validation; treat any failure as a hard stop.

---

## Tier 3: Cross-Module Risk (HEAVY)

**Applies when**: `mutex`, `conditional_lock`, or cross-root `cascade_operations` present in validation output.

### Tier 3 Additions (on top of Tier 2)

Complete the **Risk Assessment Table** and **Rollback Plan** from [references/validation.md](references/validation.md) **BEFORE Gate 5 (User Confirmation)**.

### Risk Assessment Table

| # | Risk | Source | Affected Roots | Impact | Mitigation |
|---|------|--------|---------------|--------|------------|
| 1 | (from mutex/conditional_lock/cascade_operations) | (rule name) | (which roots) | (what happens) | (how to handle) |

### Rollback Plan
1. Capture `config get <affected_root>` for every root in the "Affected Roots" column BEFORE writing.
2. For each root, prepare the rollback payload (the captured values).
3. Present the rollback plan alongside the payload in Gate 5 confirmation.

---

### Gate 7: Post-Write Verification [ALL TIERS]
- Run `config get <root>` to confirm the change took effect.
- Check related status areas if the change has side effects.
- For Tier 3: verify all affected roots match expected state.
- If the change was requested by diagnostics, hand off back to `agent-cli-device-diagnostics` with the write result and verification goal.

## Hard Boundaries (VIOLATION = HARD STOP)

| Rule | Applies To | If Violated |
|------|-----------|-------------|
| Tier MUST be classified at Gate 2.5 before proceeding | ALL | **STOP** — use the Tier Decision table in [validation.md](references/validation.md) |
| `config set` MUST use a root key (e.g., `system`), never a nested key | ALL | **STOP** — nested keys are rejected by the CLI |
| Every payload field MUST appear in `schema <root>` output | ALL | **STOP** — report the unknown field, do not guess |
| Every payload field type MUST match schema type exactly (string/int/bool/array/object) | ALL | **STOP** — fix the type mismatch before writing |
| Every payload value MUST be within allowed range/enum from `schema <root> --validation` | ALL | **STOP** — fix the out-of-range value before writing |
| Roots and field names MUST come from `config list` / `schema` output, never from context, memory, or guessing | ALL | **STOP** — run the discovery command first |
| If schema output is NOT in context at write time | ALL | **STOP** — return to Gate 2, read schema first |
| If a Tier 2 operation did NOT complete the Business Rules Check Table (Gate 4a) | Tier 2/3 | **STOP** — return to Gate 4a |
| If a Tier 2 operation did NOT complete the Schema-Payload Cross-Reference Table (Gate 4b) | Tier 2/3 | **STOP** — return to Gate 4b |
| If `cascade_operations` exist for this operation type and are NOT processed (Gate 4.5) | Tier 2/3 | **STOP** — return to Gate 4.5, do not skip cascade entries |
| If a business rule blocks the operation (reference_check, conflict_check, mutex, protected_items, etc.) | Tier 2/3 | **STOP** — explain the blocking rule to the user, do not force the write |
| If a Tier 3 operation did NOT complete the Risk Assessment Table | Tier 3 | **STOP** — return to validation.md, complete risk assessment |
| If a Tier 3 operation did NOT prepare a Rollback Plan | Tier 3 | **STOP** — capture affected root snapshots, prepare rollback payloads |
