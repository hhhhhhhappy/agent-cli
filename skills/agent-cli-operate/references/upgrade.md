# Upgrade

Use this reference for firmware upgrades only after the user has chosen the exact source.

## CLI

```bash
agent-cli upgrade --url https://example.test/fw.bin
agent-cli upgrade --file C:\\firmware\\fw.bin
```

Behavior from the CLI and command contract:

- `--url` must be an HTTP or HTTPS URL.
- `--file` is a local file path on the machine running `agent-cli`.
- The upgrade call is one-shot. It submits the request; it is not an interactive session manager for the firmware process.

## MCP

Use the dedicated `upgrade` MCP tool with either:

```json
{"source_type":"url","url":"https://example.test/fw.bin"}
```

or:

```json
{"source_type":"file","file_path":"/tmp/fw.bin"}
```

## Required Workflow

1. Confirm the target device.
2. Resolve the exact firmware version and download URL:
   - If the user has not already selected a version, consult `agent-cli-shared` (see `../agent-cli-shared/references/firmware-release.md`) to look up the official firmware, select the target version, and obtain the final download URL.
   - If the user has specified a version, verify it exists in the official firmware listing via `agent-cli-shared` before proceeding.
3. Confirm the exact source artifact or URL with the user.
4. Capture baseline state if needed, usually `status basic`.
5. Execute the upgrade after explicit approval.
6. Wait for reconnect and verify the final firmware version with `status basic`.
