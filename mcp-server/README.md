# External Device CLI MCP Server

This directory contains a standalone Python MCP server that bridges MCP tool calls to the device-side CLI over SSH and uses the device-side `agent_cli` entrypoint for the operational commands.

The published package also includes a companion CLI, `agent-cli-skills`, for copying this repository's bundled skill assets into a host skills directory.

## What It Does

- Exposes seven MCP tools: `status`, `config`, `log`, `schema`, `tool`, `upgrade`, `reboot`
- Exposes fixed read-only MCP resources per configured device for status and discovery data
- Connects to a configured device over SSH using OpenSSH
- Keeps a persistent SSH stdio session per configured device
- Maintains a single active MCP lease per device and refreshes it while the server is running
- Sends each remote CLI command as one line over the session stdin
- Returns the device JSON response as both text and `structuredContent`

The device side is expected to be configured so that the `agent` SSH user lands in `agent_cli`, and `agent_cli` automatically enters stdio mode when SSH opens a non-interactive session without an original command.

## Requirements

- `python3` 3.6+
- local `ssh`, `ssh-keygen`, and `ssh-keyscan`
- SSH credentials for bootstrap (username/password)
- no third-party Python SSH library is required

For simplified configuration, no manual SSH key or known_hosts preparation is needed.

Platform notes:

- Linux/macOS: the bootstrap flow uses a temporary `/bin/sh` askpass helper.
- Windows: install the built-in OpenSSH Client feature and keep `ssh.exe`, `ssh-keygen.exe`, and `ssh-keyscan.exe` in `PATH`. The bootstrap flow also uses Windows PowerShell for the temporary askpass helper.

## Quick Start

The fastest setup path is to configure devices inline with `--device` and let the server manage runtime SSH material under `~/.agent-mcp/`.

Each `--device` value uses this format:

```text
name=<id>,device_ip=<ip>,pass=<password>[,user=<web_user>][,port=<port>]
```

Field meanings:

- `name`: required logical device id used as `device_id` in MCP tool calls
- `device_ip`: required device IP address
- `pass`: required web admin password (used once to install the SSH key)
- `user`: optional web admin username, defaults to `adm`
- `port`: optional SSH port, defaults to `22`

Repeat `--device` to configure multiple devices. On first run, the server will:

1. Create per-device SSH key directories under `~/.agent-mcp/keys/`
2. Generate ed25519 keys with `ssh-keygen`
3. Fetch host keys with `ssh-keyscan`
4. Send `mcp key ensure <public_key>` over the bootstrap SSH session
5. Reuse the generated keys and `known_hosts` on later restarts

If you need a different runtime location, pass `--runtime-dir /path/to/runtime`.

## Run

Run directly from a Git checkout:

```bash
python3 mcp-server/server.py \
  --device name=lab-ir624,device_ip=192.0.2.10,pass=replace-me
```

Run as an installed tool:

```bash
agent-mcp \
  --device name=lab-ir624,device_ip=192.0.2.10,pass=replace-me
```

Install the repository's bundled skill assets into the default `~/.claude/skills` location:

```bash
agent-cli-skills
```

Run the installer through `uvx` after publishing the repository:

```bash
uvx --from git+https://github.com/inhandnet/agent-cli agent-cli-claude-skills
```

Use `--dest /path/to/skills` to copy the bundled skills into a different directory.

Force takeover of an existing device lease:

```bash
agent-mcp \
  --device name=lab-ir624,device_ip=192.0.2.10,pass=replace-me \
  --takeover
```

## Bundled Skills

The published package currently ships these bundled skills:

- `agent-cli-config`
- `agent-cli-device-diagnostics`
- `agent-cli-inspect`
- `agent-cli-operate`
- `agent-cli-shared`

Install behavior:

- `agent-cli-skills` copies all bundled skills into `~/.claude/skills` by default
- `agent-cli-claude-skills` is a direct alias for one-command `uvx` installs into Claude Code
- `agent-cli-skills --dest /path/to/skills` overrides the destination directory
- if the target already contains a same-named skill directory, the installer fails and does not overwrite it
- installing skills is separate from configuring the MCP server; `agent-mcp` still needs to be added to Claude Code or `.mcp.json` independently

## Configure In Claude Code

Claude Code supports stdio MCP servers through the `claude mcp add` command or a project-scoped `.mcp.json` file.

References:

- https://code.claude.com/docs/en/mcp

### Recommended: `.mcp.json` With `uvx`

Once this repository is on GitHub, Claude Code can launch it directly via `uvx` without a local clone:

```json
{
  "mcpServers": {
    "agent-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/inhandnet/agent-cli",
        "agent-mcp",
        "--device",
        "name=lab-ir624,device_ip=192.0.2.10,pass=replace-me"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

Add more devices by repeating the pair:

```json
{
  "mcpServers": {
    "agent-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/inhandnet/agent-cli",
        "agent-mcp",
        "--device",
        "name=lab-a,device_ip=192.0.2.10,pass=replace-me",
        "--device",
        "name=lab-b,device_ip=192.0.2.11,pass=replace-me,user=ops,port=2222"
      ]
    }
  }
}
```

Notes:

- Claude Code stores project-scoped MCP servers in `.mcp.json`.
- Claude Code asks for approval before using project-scoped servers from `.mcp.json`.
- `uvx` will fetch the tool from your GitHub repository each time the environment is created or refreshed.

### Alternative: Add It With The Claude CLI

Use this when you want Claude Code to create `.mcp.json` for you:

```bash
claude mcp add --transport stdio --scope project agent-mcp -- \
  uvx --from git+https://github.com/inhandnet/agent-cli agent-mcp \
  --device name=lab-ir624,device_ip=192.0.2.10,pass=replace-me
```

`--scope project` stores the configuration in the current project's `.mcp.json`. Use `--scope local` or `--scope user` if you want a different scope.

### Windows Checkout Helper

This repository also includes a Windows-focused helper that creates the default config file when needed and runs `claude mcp add` for a local checkout:

```bash
py -3 mcp-server/install_claude_code_windows.py --scope project
```

Useful flags:

- `--takeover`: add the server with `--takeover`
- `--config <path>`: use a custom config path instead of `mcp-server/config/config.json`
- `--claude-command <path>`: override the `claude` executable
- `--python-command <path>`: override the Python launcher used to start the server

## Advanced Configuration With `--config`

`--config` is still supported for advanced cases where you want to keep device definitions in a JSON file instead of CLI arguments.

Start from `config/config.json.example`:

```json
{
  "devices": {
    "lab-ir624": {
      "device_ip": "192.0.2.10",
      "user": "adm",
      "pass": "replace-me"
    }
  }
}
```

Then run:

```bash
agent-mcp --config /path/to/devices.json
```

Notes:

- The config JSON may contain secrets such as `pass`, so it must be readable only by the current user: `chmod 600 /path/to/devices.json`.
- Relative paths are resolved relative to the config file location.
- `known_hosts_file` must already exist when you use manual key configuration.
- `identity_file` and its `.pub` counterpart must already exist when you do not use auto-generated keys.

## Tool Shape

`device_id` is the key under `devices` in the loaded config JSON file.
When the server config contains exactly one device, MCP tool calls may omit `device_id` and the server will use that configured device automatically.
When the config contains multiple devices, MCP tool calls must still pass `device_id` explicitly.

Tool names:

```text
status
config
log
schema
tool
upgrade
reboot
```

The `status` MCP tool forwards to remote `status` when `subcommand` is omitted, or to `status <subcommand>` when it is provided.
The `config` MCP tool forwards to remote `config list`, `config get ...`, and `config set ...`.
The `upgrade` MCP tool uses structured arguments instead of a free-form `subcommand`.

Example `status` call:

```json
{
  "device_id": "lab-ir624"
}
```

Example `config get` call:

```json
{
  "device_id": "lab-ir624",
  "subcommand": "get system"
}
```

Example `config set` call:

```json
{
  "device_id": "lab-ir624",
  "subcommand": "set system {\"hostname\":\"branch-ir624\"}"
}
```

Example `log` call:

```json
{
  "device_id": "lab-ir624",
  "subcommand": "agent --line 200"
}
```

Example `schema` call:

```json
{
  "device_id": "lab-ir624",
  "subcommand": "list"
}
```

Schema lookups support only root keys such as `wan` or `system`. Use `--validation` with a root key when you need config validation details:

- `schema system`
- `schema wan --validation`

Nested schema paths such as `schema system.hostname` are not supported.

Status field documentation is returned inside the `status` section of the root schema response. For example:

- `schema cellular`
- `schema system`

Example `tool` call:

```json
{
  "device_id": "lab-ir624",
  "subcommand": "ping {\"action\":\"status\"}"
}
```

Example `upgrade` call:

```json
{
  "device_id": "lab-ir624",
  "source_type": "url",
  "url": "https://example.invalid/fw.bin"
}
```

Upgrade with a local file on the machine running the MCP server:

```json
{
  "device_id": "lab-ir624",
  "source_type": "file",
  "file_path": "/tmp/fw.bin"
}
```

When `source_type` is `file`, the MCP server validates the local file, uploads it to the device API, and then triggers the upgrade. Use `source_type: "url"` when the device should download the firmware itself.

`upgrade` does not expose a separate status call. A successful return means the device accepted and ran the current upgrade request; confirm the final firmware version after the device reconnects with `status basic`.

Example `reboot` call:

```json
{
  "device_id": "lab-ir624"
}
```

## Resource Shape

The server also exposes fixed read-only resources for each configured device. Resource URIs always include `device_id`, even when only one device is configured.

URI shape:

```text
device://<device_id>/<resource-path>
```

Fixed resource paths:

```text
/status/basic
/status/list
/config/list
/schema/list
/schema/status/list
/log/list
/tool/list
```

Example resource URIs:

```text
device://lab-ir624/status/basic
device://lab-ir624/tool/list
```

`resources/read` returns the remote CLI `response` payload as JSON text with `mimeType: application/json`.

Example `resources/read` result for `device://lab-ir624/status/basic`:

```json
{
  "contents": [
    {
      "uri": "device://lab-ir624/status/basic",
      "mimeType": "application/json",
      "text": "{\"result\":{\"firmware\":\"1.0.0\"},\"status\":200}"
    }
  ]
}
```

## Tests

```bash
python3 -m pip install -e .
python3 -m unittest discover -s mcp-server/tests
```
