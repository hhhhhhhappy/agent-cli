# Error Recovery

Centralized error patterns and recovery strategies for all `agent-cli-*` skills. When an operation fails, match the error against the categories below. Do not retry blindly — follow the prescribed recovery flow.

---

## Error Categories

### 1. Connection Errors

| Symptom | Likely Cause | Recovery |
|---------|-------------|----------|
| `SSH connection refused` | Device SSH service down or wrong port | Verify device IP and port. Try `agent-cli auth --device-ip <ip>` to reconfigure. |
| `SSH connection timeout` | Device unreachable, firewall block, or wrong IP | Check IP reachability from the agent host first (local `ping`). If unreachable, the device may be offline — switch to `agent-cli-inspect` via MCP if available. |
| `Connection reset by peer` | Device mid-restart or SSH session limit | Wait 30s and retry. If persistent, check if the device is rebooting via MCP `status basic` if available. |
| `Could not resolve hostname` | DNS failure on agent host | Use direct IP address instead of hostname. |
| `Device not found` / `Unknown device_id` | Wrong `device_id` or device not configured | Run `agent-cli auth` (CLI) or check configured device list. If MCP: verify `device_id` against the `device://` fixed resources. |

### 2. Authentication & Permission Errors

| Symptom | Likely Cause | Recovery |
|---------|-------------|----------|
| `Permission denied (publickey)` | SSH key not authorized on device | Re-run `agent-cli auth` to re-bootstrap key exchange. |
| `Authentication failed` | Wrong password or expired credentials | Re-run `agent-cli auth` with correct credentials. |
| `Bad credentials` | Stored credentials invalid | Re-bootstrap with `agent-cli auth --device-ip <ip> --name <id> --overwrite`. |
| MCP `401` on vendor API | Missing or wrong `x-api-key`, `origin`, or `referer` header | Verify all 4 headers from [inhand-release-api.md](inhand-release-api.md). Do not treat as evidence of missing product. |

### 3. Configuration Errors

| Symptom | Likely Cause | Recovery |
|---------|-------------|----------|
| `config set` rejects nested key | Used `system.hostname` instead of root `system` | Use root key only. Re-read [config-write.md](../../agent-cli-config/references/config-write.md). |
| `Unknown config root` | Root not in `config list` output | Run `config list` again. Do not guess root names. |
| Schema validation error on write | Payload field type/value mismatch | Return to Gate 4b (Schema-Payload Cross-Reference Table). Fix each ✗ row. |
| Business rule blocks write | conflict_check, reference_check, mutex, etc. triggered | Return to Gate 4a (Business Rules Check Table). Explain which rule blocked and the current config value. Do not force the write. |
| `max_items` exceeded | List full | Tell user the current item count and max. Suggest removing an entry first. |
| `protected_items` violation | Attempted to delete a protected item | Tell user the item is system-protected and cannot be deleted. |
| `schema <root>` returns empty or error | Root name wrong or not a valid schema root | Use `schema list` first. Only root keys are valid (no nested paths). |

### 4. Tool Execution Errors

| Symptom | Likely Cause | Recovery |
|---------|-------------|----------|
| Tool returns `ok: false` | Operation failed on device | Read `error.message`. If retryable (timeout, busy), wait and retry once. If permanent (invalid params), fix the payload. |
| Tool timeout | Device too slow or `timeout_sec` too low | Increase `timeout_sec` up to 120 and retry. |
| `tcpdump` rejects `capture_mode` | Used mode other than `show` | Only `show` is supported. Fix `capture_mode`. |
| `tcpdump` rejects `local_iface` | Empty array or missing fields | Must be non-empty array with exactly one item in `show` mode, each with `interface` and `expert_options`. |
| `speedtest` rejects action | Unsupported action | Valid actions: `start`, `status`, `output`, `stop`, `servers`. |
| `speedtest` rejects `server_id` | Not a positive integer | `server_id` must be a positive integer when provided. |
| Ping/traceroute returns no output | Tool still running or stale session | Poll `status` first. If completed, use `output` with `start_line: 0`. |

### 5. MCP-Specific Errors

| Symptom | Likely Cause | Recovery |
|---------|-------------|----------|
| `Unknown resource uri` | Wrong `device_id` in fixed resource URI | Retry with the real configured `device_id`. Do not use `default`. Fall back to the normal `status` tool if uncertain. |
| MCP tool not found | Tool name wrong or not exposed in current environment | Check available MCP tools. Fall back to CLI if the tool is only available via `agent-cli` executable. |
| MCP subcommand parse error | JSON escaping error in subcommand string | Double-check JSON escaping. Use valid JSON inside the subcommand string. |

### 6. Firmware & Upgrade Errors

| Symptom | Likely Cause | Recovery |
|---------|-------------|----------|
| `upgrade` rejects `--url` | Not HTTP/HTTPS or URL malformed | Verify URL format. Must start with `http://` or `https://`. |
| `upgrade` rejects `--file` | File not found or path inaccessible | Verify the file exists on the agent host. For MCP, use absolute path. |
| Device unreachable after upgrade | Reboot in progress or upgrade failed | Wait up to 5 minutes. Retry connection every 30s. If still unreachable after 5 minutes, treat as upgrade failure. |
| `status basic` shows old version after upgrade | Upgrade not applied or rollback occurred | Verify the exact firmware was accepted. Check device logs if available. |
| Vendor API `401` | Missing or invalid headers | Verify all 4 headers from [inhand-release-api.md](inhand-release-api.md). Do not conclude product absence from a 401. |
| Vendor API `404` on product lookup | Product not published in public catalog | Stop. Tell user the vendor's public site does not show this product. This is a terminal result — do not brute-force other endpoints. |
| Vendor API timeout / `5xx` | Vendor site down or overloaded | Retry once after 30s. If still failing, tell user the vendor site is currently unreachable. Suggest retrying later or contacting technical support for internal release information. |
| Download URL returns error | Signed URL expired or wrong doc_id | Re-resolve via `common/documents/<doc_id>?verbose=100` to get a fresh signed URL. |

### 7. Reboot Errors

| Symptom | Likely Cause | Recovery |
|---------|-------------|----------|
| Device unreachable after reboot | Normal reboot in progress | Wait up to 3 minutes. Retry connection every 15s. |
| Device still unreachable after 3 minutes | Reboot hung or device stuck | Last resort: physical power cycle if accessible. Otherwise escalate to on-site support. |
| `reboot` command returns error | Permission denied or device busy | Check device state with `status basic` first. Retry once. |

---

## General Recovery Rules

1. **One retry only** for transient errors (timeout, busy, connection reset). After one retry, stop and report.
2. **Fix the input, not the error message**. If the error says "unknown root", run `config list` — don't guess a different root name.
3. **Escalate, don't loop**. If a recovery step fails twice with the same error, stop and escalate to the user with evidence of what was tried.
4. **Preserve evidence**. Before retrying or changing strategy, record the exact command, error message, and timestamp.
5. **Terminal results are final**. A vendor API 404, a `protected_items` violation, or a confirmed missing product in the public catalog are terminal. Do not keep searching for alternatives.

## Cross-Reference

- Safety rules and approval gates → [safety.md](safety.md)
- Config write workflow and validation tables → [../../agent-cli-config/references/validation.md](../../agent-cli-config/references/validation.md)
- CLI transport setup → [transport-cli.md](transport-cli.md)
- MCP transport and fixed resources → [transport-mcp.md](transport-mcp.md)
- Vendor API rules → [inhand-release-api.md](inhand-release-api.md)
- Firmware release lookup → [firmware-release.md](firmware-release.md)
- Tool payload contracts → [../../agent-cli-device-diagnostics/references/tool-contract.md](../../agent-cli-device-diagnostics/references/tool-contract.md)
