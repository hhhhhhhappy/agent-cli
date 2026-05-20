# agent-cli

This repository contains the host-side tooling for exposing a remote device's `agent_cli` service over SSH:

- `agent-cli`: a Windows-oriented CLI for one-off commands and scripts
- `agent-mcp`: a stdio MCP server for Claude Code and other MCP clients
- `agent-cli-skills`: installers for the bundled Claude skills in this repository

Both the CLI and the MCP server bootstrap SSH access on first use, then reuse generated keys and known_hosts data from a local runtime directory.

Detailed component docs:

- [cli/README.md](cli/README.md)
- [mcp-server/README.md](mcp-server/README.md)

## Highlights

- Seven remote operation groups: `status`, `config`, `log`, `schema`, `tool`, `upgrade`, `reboot`
- Fixed read-only MCP resources for discovery: `status/basic`, `status/list`, `config/list`, `schema/list`, `log/list`, `tool/list`
- Zero-touch SSH bootstrap with local OpenSSH tools
- Inline multi-device setup with repeated `--device` flags
- Optional JSON config files for saved device definitions
- Persistent per-device SSH sessions instead of reconnecting on every call
- Schema-backed preflight validation for `config set`
- Bundled Claude skills for inspection, configuration, diagnostics, and operations

## Packages

| Package / command | Source | Purpose |
| ----------------- | ------ | ------- |
| `agent-cli` | `cli/` subdirectory | Windows-oriented CLI wrapper for remote `agent_cli` access |
| `agent-mcp` | repository root package | MCP server that forwards tool calls to the device over SSH |
| `agent-cli-skills` | repository root package | Copies bundled skills into a Claude skills directory |

## Requirements

| Requirement | Notes |
| ----------- | ----- |
| Python 3.6+ | Required for both the CLI and MCP server |
| `ssh`, `ssh-keygen`, `ssh-keyscan` | Standard OpenSSH client tools |
| Bootstrap credentials | Username and password for the target device |
| `uv` / `uvx` | Needed only for the install flows shown below |

Windows note:
Install the built-in OpenSSH Client feature and keep `ssh.exe`, `ssh-keygen.exe`, and `ssh-keyscan.exe` on `PATH`.

If `uv` or `uvx` is not installed on Windows:

```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

## Quick Start

### Run the MCP server with `uvx`

This is the shortest path for Claude Code. Project-scoped MCP entries are stored in `.mcp.json`.

```bash
claude mcp add --transport stdio --scope project agent-mcp -- uvx --from git+https://github.com/inhandnet/agent-cli agent-mcp --device name=odu12,host=192.168.2.1,pass=<replace-me>
```

Equivalent `.mcp.json` entry:

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
        "name=odu12,host=192.168.2.1,pass=<replace-me>"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

Repeat `--device` to register more than one router.

### Run from a local checkout

```bash
git clone https://github.com/inhandnet/agent-cli.git
cd agent-cli
```

On Windows, the repository also ships a helper that creates a starter config file and runs `claude mcp add` for you:

```powershell
python mcp-server/install_claude_code_windows.py
```

By default, that helper creates `mcp-server/config/config.json` from `mcp-server/config/config.json.example` when the file does not already exist.

### Install the Windows CLI

```powershell
uv tool install --from git+https://github.com/inhandnet/agent-cli.git#subdirectory=cli agent-cli
```

If the command is not available in a new shell yet:

```powershell
uv tool update-shell
```

Recommended first-time flow for `agent-cli`:

```powershell
agent-cli auth
```

`agent-cli auth` prompts for host, port, bootstrap user, and password, then saves the device profile to `~/.agent-cli/config.json`.

After that, you can usually run commands without repeating `--device` every time:

```powershell
agent-cli status basic
agent-cli config get system.hostname
agent-cli schema system --validation
```

If you prefer not to save a local config yet, you can still use inline `--device` on each command:

Example one-off commands:

```powershell
agent-cli --device name=lab-ir624,host=192.0.2.10,pass=replace-me status basic
agent-cli --device name=lab-ir624,host=192.0.2.10,pass=replace-me config get system.hostname
agent-cli --device name=lab-ir624,host=192.0.2.10,pass=replace-me schema system --validation
```

## Device Configuration

### Inline `--device` format

Every `--device` value uses this format:

```text
name=<id>,host=<host>,pass=<password>[,buser=<user>][,port=<port>]
```

| Field | Required | Default | Description |
| ----- | :------: | ------- | ----------- |
| `name` | yes | - | Logical device id |
| `host` | yes | - | Device IP address |
| `pass` | yes | - | Bootstrap password used during first-time key registration |
| `buser` | no | `adm` | Device Web Login user name |
| `port` | no | `22` | SSH port |

Runtime directories:

- `agent-cli` defaults to `~/.agent-cli/`
- `agent-mcp` defaults to `~/.agent-mcp/`

On first use, the selected runtime directory stores generated keys, host metadata, and session state.

### JSON config file format

If you prefer saved device definitions instead of inline `--device` flags, use `--config` with a JSON file:

```json
{
  "devices": {
    "lab-ir624": {
      "host": "192.168.2.1",
      "bootstrap_user": "adm",
      "bootstrap_password": "<replace-me>"
    }
  }
}
```

Example:

```bash
agent-mcp --config /path/to/devices.json
```

## Supported Operations

| Group | Notes |
| ----- | ----- |
| `status` | Read aggregated status, list status keys, or query one status area |
| `config` | `config get` is read-only; `config set` applies root-level payloads |
| `log` | Reads the default `message` log or named services |
| `schema` | Lists schema roots, reads one root, or shows validation rules |
| `tool` | Diagnostics including `ping`, `traceroute`, `tcpdump`, `iperf`, and `speedtest` |
| `upgrade` | Firmware upgrade from a URL or local file upload |
| `reboot` | Immediate device reboot |

Operational safety levels:

| Level | Operations | Notes |
| ----- | ---------- | ----- |
| Read-only | `status`, `config get`, `log`, `schema` | Safe at any time |
| Diagnostic | `tool` | Can consume bandwidth or system resources |
| Change | `config set` | Validate with `schema <root> --validation` first |
| Destructive | `upgrade`, `reboot` | Use only with explicit approval |

## Bundled Claude Skills

Install the bundled skills into the default Claude skills directory:

```bash
uvx --from git+https://github.com/inhandnet/agent-cli agent-cli-skills install
```

Or use the alias intended for one-command Claude setups:

```bash
uvx --from git+https://github.com/inhandnet/agent-cli agent-cli-claude-skills
```

Default destination: `~/.claude/skills`

Bundled skill directories:

- `agent-cli-config`
- `agent-cli-device-diagnostics`
- `agent-cli-inspect`
- `agent-cli-operate`
- `agent-cli-shared`

The installer does not overwrite an existing same-named skill directory.

## Repository Layout

```text
agent-cli/
|-- cli/
|   |-- cli.py
|   |-- command_surface.py
|   |-- config_preflight.py
|   |-- tests/
|   `-- README.md
|-- mcp-server/
|   |-- server.py
|   |-- ssh_bridge.py
|   |-- install_claude_code_windows.py
|   |-- skills_installer.py
|   |-- config/
|   |-- tests/
|   `-- README.md
|-- skills/
|   |-- agent-cli-config/
|   |-- agent-cli-device-diagnostics/
|   |-- agent-cli-inspect/
|   |-- agent-cli-operate/
|   `-- agent-cli-shared/
|-- pyproject.toml
|-- setup.py
`-- README.md
```
