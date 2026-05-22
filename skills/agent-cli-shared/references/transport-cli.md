# CLI Transport

Use this reference when the current agent environment should call the local `agent-cli` executable directly.

## Bootstrap

Use `auth` to bootstrap SSH key access and save local configuration.

```bash
agent-cli auth
agent-cli auth --device-ip 192.0.2.10 --name lab-a
agent-cli auth list
agent-cli auth remove lab-a
```

Key behavior from the CLI help:

- With no auth flags, `agent-cli auth` prompts for device IP address, SSH port, web login username and password, and the device name to save it under (defaults to the device IP).
- `--pass` exists for compatibility, but it exposes the password in process arguments while the command runs.
- Re-running `auth` for an existing device name aborts unless `--overwrite` is passed (interactive runs ask first).
- `agent-cli auth list` shows saved devices (passwords are never returned). `agent-cli auth remove <name> [<name>...]` deletes entries all-or-nothing; `agent-cli auth remove --all` wipes every saved device.
- Successful bootstrap writes local config and runtime material under the selected runtime directory.

## Global Options

Common options from the CLI help:

```text
--config <path>
--device <spec>
--runtime-dir <path>
--device-id <id>
--timeout-sec <sec>
--takeover
--overwrite
```

Inline device specs use:

```text
name=<id>,device_ip=<ip>,pass=<password>[,user=<web_user>][,port=<port>]
```

Field meanings:

- `name`: logical device id (required)
- `device_ip`: device IP address (required)
- `pass`: web login password (required; used once to install the SSH key)
- `user`: web login username (default `adm`)
- `port`: SSH port (default `22`)

## Discovery Commands

Use built-in topic help when the exact CLI syntax matters:

```bash
agent-cli help
agent-cli help status
agent-cli help config
agent-cli help tool
```

## Transport Choice

- Use CLI when MCP tools are not available in the current agent environment.
- Use CLI for bootstrap/auth because that capability is exposed directly by `agent-cli`.
- Keep working notes transport-neutral so the same workflow can map to MCP later.
