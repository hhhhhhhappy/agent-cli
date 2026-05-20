# CLI Transport

Use this reference when the current agent environment should call the local `agent-cli` executable directly.

## Bootstrap

Use `auth` to bootstrap SSH key access and save local configuration.

```bash
agent-cli auth
agent-cli auth --host 192.0.2.10 --name lab-a
```

Key behavior from the CLI help:

- With no auth flags, `agent-cli auth` prompts for host, port, user, and password.
- `--pass` exists for compatibility, but it exposes the password in process arguments while the command runs.
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
```

Inline device specs use:

```text
name=<id>,host=<host>,pass=<password>[,buser=<user>][,user=<user>][,port=<port>]
```

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
