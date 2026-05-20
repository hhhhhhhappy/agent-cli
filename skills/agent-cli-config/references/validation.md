# Validation

Use this reference before any non-trivial config write.

## Schema-First Flow

```bash
agent-cli schema list
agent-cli schema system
agent-cli schema system --validation
agent-cli config get system
```

## Rules

- Validation lookups only support root keys.
- `config set` now re-runs preflight validation internally, but that does not replace the schema-first workflow.
- If the user asks for a write against an unknown root, discover roots first.
- If the requested payload conflicts with schema or validation output, stop and explain the mismatch instead of guessing.
- If the schema is broad but the write scope is small, prefer a narrower `config get` query first to understand current values.
- **Business rules obtained from `schema <root> --validation` take precedence over schema. A blocking business rule is a HARD STOP.**
  The command returns runtime validation rules including constraints, dependencies, add_rules, delete_rules, and cascade_operations.

---

## Tier Decision (MANDATORY — Gate 2.5)

> ⚠️ **Classify the operation AFTER reading `schema <root> --validation` and BEFORE building any payload. The tier determines which gates are required.**

| Operation Characteristics | Tier | Gates Required |
|---|---|---|
| Modify existing field values only (e.g., change `hostname`, toggle `enabled`, set `log_level`). No list add/delete. No `add_rules`/`delete_rules` keys in `--validation` output. No `mutex`/`conditional_lock`. No `cascade_operations`. | **Tier 1 (LIGHT)** | Gate 2 → 3 → 7 |
| Add or delete list items, OR `add_rules`/`delete_rules` keys present in `--validation` output. | **Tier 2 (STANDARD)** | Gate 1 → 2 → 3 → 4a → 4b → 4.5 → 5 → 6 → 7 |
| `mutex`, `conditional_lock`, or `cascade_operations` with cross-root effects present in `--validation` output, OR `dependencies` spanning multiple roots. | **Tier 3 (HEAVY)** | Tier 2 all + Risk Assessment Table + Rollback Plan |

### Quick Classification from `schema <root> --validation`

| If `--validation` output contains... | Minimum Tier |
|---|---|
| Only field-level validators (enums, ranges, patterns) | Tier 1 |
| `add_rules` key | Tier 2 |
| `delete_rules` key | Tier 2 |
| `mutex` key | Tier 3 |
| `conditional_lock` key | Tier 3 |
| `cascade_operations` with cross-root targets (not self-referencing) | Tier 3 |
| `dependencies.used_by` with non-empty entries referencing other roots | Tier 3 |

### Tier 1: Skip to Inline Validation
Tier 1 operations skip the tables below. Instead:
1. Validate each payload field directly against `schema <root>`: must exist, type must match, value must be in range/enum.
2. Execute `config set`.
3. Verify with Gate 7.

### Tier 2: Complete All Tables Below
### Tier 3: Complete All Tables Below + Risk Assessment at End

---

## Business Rules Check Table (MANDATORY — Gate 4a) [Tier 2/3]

> ⚠️ **You MUST fill out this table BEFORE the Schema-Payload Cross-Reference Table. Evaluate EVERY rule from `schema <root> --validation` output for the target root.**

Build this table from the target root's entry in the `schema <root> --validation` output (constraints, dependencies, add_rules, delete_rules, cascade_operations):

| # | Rule Source | Rule Type | Condition | Current Config | Blocked? |
|---|------------|-----------|-----------|----------------|----------|
| 1 | add_rules / delete_rules / constraints / dependencies | (conflict_check, reference_check, mutex, etc.) | (from json) | (value from config get) | YES / NO |
| 2 | ... | ... | ... | ... | ... |

### Fill Rules

1. **Rule Source**: Which section — `add_rules`, `delete_rules`, `constraints`, `dependencies`.
2. **Rule Type**: `conflict_check`, `reference_check`, `mutex`, `conditional_lock`, `max_items`, `protected_items`, `unique_check`, etc.
3. **Condition**: The rule's `condition` / `target` / `check` from json (e.g., `not_used_by → system.iface_cloud`, `wan_exists → lan2`).
4. **Current Config**: Run the relevant `config get` to check the condition. Write the actual value.
5. **Blocked?**: YES if the condition triggers. NO if it doesn't. Do NOT proceed if any row is YES.

### Example: DELETE WAN

| # | Rule Source | Rule Type | Condition | Current Config | Blocked? |
|---|------------|-----------|-----------|----------------|----------|
| 1 | delete_rules | reference_check | not_used_by → system.iface_cloud | `"any"` (not wan1) | NO |
| 2 | delete_rules | reference_check | not_used_by → ipsec.*.interface | `{}` (empty) | NO |
| 3 | delete_rules | reference_check | not_used_by → l2tp.server.interface | `{}` (empty) | NO |
| 4 | delete_rules | reference_check | not_used_by → ippt.uplink | `""` (empty) + ippt.enabled=false | NO |
| 5 | constraints | max_items | 1 | — | NO |

### Gate Rules (HARD STOP on any YES)

- If **any row has YES in Blocked?** → **STOP. Do not write.** Tell the user exactly which rule blocks the operation and what the current value is.
- **Only when ALL rows show NO may you proceed** to the Schema-Payload Cross-Reference Table (Gate 4b).

## Common Pattern

1. Gate 1: Discover the root (if unknown).
2. Gate 2: Read the schema + `--validation`.
3. Gate 2.5: **Classify tier** using the Tier Decision table above.
4. Gate 3: Read current config.
5. **Tier 1**: Validate inline → write → verify. Done.
6. **Tier 2**: Business Rules Check Table (Gate 4a) → Schema-Payload Cross-Reference (Gate 4b) → Cascade Operations (Gate 4.5).
7. **Tier 3**: Tier 2 all + Risk Assessment Table + Rollback Plan.
8. Gate 5: User confirmation.
9. Gate 6: Execute write.
10. Gate 7: Verify.

---

## Schema-Payload Cross-Reference Table (MANDATORY — Gate 4b)

> ⚠️ **You MUST fill out this table before constructing the final `config set` payload. Each row MUST match the schema output exactly.**

Build this table from the `schema <root>` and `schema <root> --validation` output:

| # | Schema Field | Schema Type | Allowed/Required | Your Payload Value | Type Match? | Value Match? |
|---|-------------|-------------|-----------------|-------------------|-------------|-------------|
| 1 | (from schema) | (string/int/bool/array/object) | (required/optional, enums, ranges) | (what you plan to send) | ✓/✗ | ✓/✗ |
| 2 | ... | ... | ... | ... | ... | ... |

### Fill Rules

1. **Schema Field**: Copy exactly from `schema <root>` output — do not rename, abbreviate, or invent.
2. **Schema Type**: Use the exact type from schema (`string`, `integer`, `boolean`, `array`, `object`).
3. **Allowed/Required**: From `schema <root> --validation` — note if the field is required, and list allowed enums, ranges, or patterns.
4. **Your Payload Value**: The value you intend to send. Use the schema type as-is (e.g., `true` not `"true"` for boolean).
5. **Type Match?**: ✓ if payload value type matches schema type. ✗ if mismatched.
6. **Value Match?**: ✓ if value is within allowed range/enum and required fields are present. ✗ if out-of-range or missing required.

### Gate Rules (HARD STOP on any ✗)

- If **any row has ✗ in Type Match?** → **STOP. Do not write.** Fix the type mismatch first.
- If **any row has ✗ in Value Match?** → **STOP. Do not write.** Fix the value first.
- If **a schema field is required but missing from your payload** → **STOP. Do not write.** Add it first.
- **Only when ALL rows show ✓ in both columns may you proceed** to Gate 5 (User Confirmation).

### Example (Correct)

For `schema system` output showing:
```
hostname: string (required, max 63 chars, pattern: ^[a-zA-Z0-9-]+$)
log_level: string (optional, enum: debug|info|warn|error)
```

| # | Schema Field | Schema Type | Allowed/Required | Your Payload Value | Type Match? | Value Match? |
|---|-------------|-------------|-----------------|-------------------|-------------|-------------|
| 1 | hostname | string | required, max 63, pattern `^[a-zA-Z0-9-]+$` | `"lab-router-01"` | ✓ | ✓ |
| 2 | log_level | string | optional, enum: debug\|info\|warn\|error | `"warn"` | ✓ | ✓ |

### Example (Violation — would trigger STOP)

| # | Schema Field | Schema Type | Allowed/Required | Your Payload Value | Type Match? | Value Match? |
|---|-------------|-------------|-----------------|-------------------|-------------|-------------|
| 1 | hostname | string | required, max 63, pattern `^[a-zA-Z0-9-]+$` | `"lab router!"` | ✓ | ✗ ← contains space and `!` |
| 2 | log_level | string | optional, enum: debug\|info\|warn\|error | `"verbose"` | ✓ | ✗ ← not in enum |
| 3 | enable_ssl | boolean | optional | `"true"` | ✗ ← string, not boolean | ✗ |

---

## Risk Assessment Table (MANDATORY — Tier 3 only)

> ⚠️ **Complete this table BEFORE Gate 5 (User Confirmation). Evaluate every cross-module risk from `schema <root> --validation` output.**

Build this table from `mutex`, `conditional_lock`, and cross-root `cascade_operations` entries in `schema <root> --validation`:

| # | Risk | Source | Affected Roots | Impact | Mitigation |
|---|------|--------|---------------|--------|------------|
| 1 | (e.g., Enabling IPPT disables IPsec) | mutex → ippt.enabled | ippt, ipsec | Active VPN tunnels will drop | Confirm user accepts VPN downtime; capture ipsec config for rollback |
| 2 | (e.g., Adding WAN locks LAN2) | conditional_lock → wan_exists | wan, lan2 | LAN2 becomes read-only | Inform user LAN2 will be locked; no rollback needed |
| 3 | ... | ... | ... | ... | ... |

### Fill Rules

1. **Risk**: Describe the user-visible consequence in plain language.
2. **Source**: Which `--validation` key triggered this row (`mutex`, `conditional_lock`, `cascade_operations.on_add`, etc.).
3. **Affected Roots**: List every config root that will change as a side effect (including cascade targets).
4. **Impact**: What the user will observe (service disruption, feature lock, data loss).
5. **Mitigation**: How to handle it — user acceptance, pre-capture for rollback, warning, or no action needed.

### Gate Rules

- Every row in `mutex` and `conditional_lock` MUST appear in this table.
- Every cross-root `cascade_operations` entry MUST appear in this table.
- If any Risk has unacceptable Impact and no Mitigation → **STOP. Do not proceed.**
- Present this table alongside the payload in Gate 5 (User Confirmation).

### Rollback Plan (MANDATORY — Tier 3 only)

1. **Capture snapshots**: For every root in the "Affected Roots" column, run `config get <root>` BEFORE writing. Store the raw output.
2. **Prepare rollback payloads**: For each captured root, extract the fields that will be modified and build a restore payload.
3. **Present with confirmation**: Show the rollback plan alongside the Risk Assessment Table in Gate 5.
4. **After write**: Confirm the user does not want rollback before proceeding to Gate 7.

Example rollback plan:

```
Affected roots: ippt, ipsec

ippt snapshot: {"enabled": false, ...}
ipsec snapshot: {"tunnels": {...}, ...}

Rollback commands:
  config set ippt {"enabled": false}
  config set ipsec <snapshot_payload>
```
