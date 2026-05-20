# agent-cli

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-%3E%3D3.6-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio-purple.svg)](https://modelcontextprotocol.io/)

Host-side tooling that exposes a remote device's `agent_cli` service over SSH — built for humans and AI Agents. Inspect status, edit configuration, tail logs, run network diagnostics, push firmware, and reboot devices through a unified command surface, driven either from your shell or from an AI Agent via the bundled Claude skills.

[Install](#installation--quick-start) · [AI Agent Skills](#agent-skills) · [Devices](#device-configuration) · [Commands](#operations) · [Transport Options](#transport-options) · [Security](#security--risk-warnings-read-before-use) · [Contributing](#contributing)

## Why agent-cli?

- **Agent-Native Design** — Five structured [Skills](#agent-skills) out of the box. Claude Code and other AI Agents call `agent-cli` through the Bash tool with zero extra prompting.
- **Zero-Touch SSH Bootstrap** — First call generates keys, trusts the host, and reuses a persistent session. No manual `ssh-copy-id`, no per-call reconnect.
- **Schema-Backed Safety** — `config set` is preflighted against the device's own schema; destructive operations (`upgrade`, `reboot`) are isolated under a separate safety tier.
- **Multi-Device Out of the Box** — Repeat `--device` flags or point at a JSON config file to manage a fleet from one process.
- **Two Transports, One Backend** — Use the `agent-cli` shell command by default; switch to the `agent-mcp` MCP server when you want structured tool calls from an MCP-native client. Skills auto-detect which transport is available.

## Features

| Group     | Capabilities                                                                       |
| --------- | ---------------------------------------------------------------------------------- |
| `status`  | Read aggregated device status, list available keys, or query a single area         |
| `config`  | `config get` reads the running config; `config set` applies a root-level payload   |
| `log`     | Tail the default `message` log or read a named service log                         |
| `schema`  | List schema roots, fetch one root, or return validation rules for `config set`     |
| `tool`    | Network diagnostics: `ping`, `traceroute`, `tcpdump`, `iperf`, `speedtest`         |
| `upgrade` | Firmware upgrade from URL or via local file upload                                 |
| `reboot`  | Immediate device reboot                                                            |

## Installation & Quick Start

### Requirements

Before you start, make sure you have:

- Python `3.6`+
- OpenSSH client tools on `PATH` (`ssh`, `ssh-keygen`, `ssh-keyscan`)
- `uv` / `uvx` ([install guide](https://docs.astral.sh/uv/getting-started/installation/))
- Device credentials (username and password used for first-time bootstrap)

On Windows, enable the built-in **OpenSSH Client** feature. If `uv` is missing:

```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

### Quick Start (Human Users)

> **Note for AI assistants:** If you are an AI Agent helping the user with installation, jump directly to [Quick Start (AI Agent)](#quick-start-ai-agent).

#### Step 1 — Install CLI and Skills

```bash
# Install the agent-cli command
uv tool install --from git+https://github.com/inhandnet/agent-cli.git#subdirectory=cli agent-cli
uv tool update-shell    # only if agent-cli is not yet on PATH

# Install the Claude skills (teaches AI Agents how to drive agent-cli)
uvx --from git+https://github.com/inhandnet/agent-cli agent-cli-skills install
```

Skills are copied to `~/.claude/skills`; existing same-named directories are left untouched.

#### Step 2 — Configure a device

```bash
agent-cli auth          # interactive: prompts for host / port / bootstrap user / password
```

Example session:

```text
Host: 192.168.2.1
Port [22]: 22
Bootstrap user [adm]: adm
Password: ********
{"ok":true,"device_id":"192.168.2.1","data":{"config_path":"~/.agent-cli/config.json", ...}}
```

The first auth call writes credentials to `~/.agent-cli/config.json`, generates an SSH keypair, and seeds `known_hosts`. Subsequent calls reuse the saved profile.

Pass `--name lab-ir624` to give the device a friendly id, or `--host <ip> --name <id>` to skip prompts.

#### Step 3 — Start using

In your shell:

```bash
agent-cli status basic
agent-cli config get system.hostname
agent-cli log message --line 200
agent-cli schema system --validation
```

Or let Claude Code drive it — the bundled skills will invoke `agent-cli` for you:

> "Check whether `lab-ir624` is online and tail the last 100 lines of its message log."

### Quick Start (AI Agent)

> The following steps are for AI Agents installing `agent-cli` on behalf of a user.

**Step 1 — Install**

```bash
uv tool install --from git+https://github.com/inhandnet/agent-cli.git#subdirectory=cli agent-cli
uvx --from git+https://github.com/inhandnet/agent-cli agent-cli-skills install
```

**Step 2 — Collect device details from the user**

- `host`: device IP address (required)
- `pass`: Web login password (required)
- *(optional)* `name`: a friendly id (defaults to the host IP)
- *(optional)* `buser`: Web login user (default `adm`)
- *(optional)* `port`: SSH port (default `22`)

**Step 3 — Bootstrap**

```bash
agent-cli auth --host <HOST> --name <NAME>
# user supplies password at the prompt
```

**Step 4 — Verify**

```bash
agent-cli status basic
```

A `{"ok": true, ...}` response means SSH bootstrap completed and the session is reusable.

## Agent Skills

Skills are Claude Code playbooks that drive `agent-cli` (or `agent-mcp`) on your behalf. They are auto-discovered from `~/.claude/skills` after `agent-cli-skills install`.

| Skill                          | Description                                                                            |
| ------------------------------ | -------------------------------------------------------------------------------------- |
| `agent-cli-shared`             | Shared prompts, device selection, error recovery, transport auto-detection             |
| `agent-cli-inspect`            | Read-only inspection: status, config, log tailing                                       |
| `agent-cli-config`             | Schema-aware configuration changes with `config set` preflight                          |
| `agent-cli-device-diagnostics` | Network diagnostics workflows (`ping`, `traceroute`, `tcpdump`, `iperf`, `speedtest`)   |
| `agent-cli-operate`            | Firmware upgrade and reboot (destructive — requires explicit human approval)            |

Each skill ships transport references for both [CLI](skills/agent-cli-shared/references/transport-cli.md) and [MCP](skills/agent-cli-shared/references/transport-mcp.md), and selects the one available in the current environment.

## Device Configuration

### Inline `--device` format

Used for the MCP server and one-off CLI calls:

```text
name=<id>,host=<host>,pass=<password>[,buser=<user>][,port=<port>]
```

| Field   | Required | Default | Description           |
| ------- |:--------:| ------- | --------------------- |
| `name`  | yes      | -       | Logical device id     |
| `host`  | yes      | -       | Device IP address     |
| `pass`  | yes      | -       | Web login password    |
| `buser` | no       | `adm`   | Web login user        |
| `port`  | no       | `22`    | SSH port              |

Runtime directories: `~/.agent-cli/` for the CLI, `~/.agent-mcp/` for the MCP server. Generated keys, host metadata, and session state are written there on first use.

### JSON config file

```json
{
  "devices": {
    "lab-ir624": {
      "host": "192.168.2.1",
      "bootstrap_user": "adm",
      "bootstrap_password": "<your-device-password>"
    }
  }
}
```

```bash
agent-mcp --config /path/to/devices.json
```

## Operations

| Group     | Notes                                                               |
| --------- | ------------------------------------------------------------------- |
| `status`  | Read aggregated status, list keys, or query one area                |
| `config`  | `config get` is read-only; `config set` applies root-level payloads |
| `log`     | Reads the default `message` log or a named service                  |
| `schema`  | Lists schema roots, reads one root, or returns validation rules     |
| `tool`    | Diagnostics: `ping`, `traceroute`, `tcpdump`, `iperf`, `speedtest`  |
| `upgrade` | Firmware upgrade from URL or local file upload                      |
| `reboot`  | Immediate device reboot                                             |

### Safety levels

| Level       | Operations                              | Notes                                            |
| ----------- | --------------------------------------- | ------------------------------------------------ |
| Read-only   | `status`, `config get`, `log`, `schema` | Always safe                                      |
| Diagnostic  | `tool`                                  | May consume bandwidth or CPU                     |
| Change      | `config set`                            | Validate with `schema <root> --validation` first |
| Destructive | `upgrade`, `reboot`                     | Use only with explicit approval                  |

## Transport Options

`agent-cli` ships two transports backed by the same SSH bridge and command surface. Pick the one that matches your AI client:

### CLI transport (default)

Skills invoke the `agent-cli` binary through Claude Code's Bash tool. This is the default — once Step 1 above is done, you're already on this path.

**Use it when:** You want a single binary on `PATH`, you switch between multiple AI tools, or your client has no MCP support.

### MCP transport (optional)

Register `agent-mcp` as a stdio MCP server so MCP-native clients call structured tools instead of shell commands.

```bash
claude mcp add --transport stdio --scope project agent-mcp -- \
  uvx --from git+https://github.com/inhandnet/agent-cli agent-mcp \
  --device name=odu12,host=192.168.2.1,pass=<your-device-password>
```

Equivalent `.mcp.json`:

```json
{
  "mcpServers": {
    "agent-mcp": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/inhandnet/agent-cli",
        "agent-mcp",
        "--device", "name=odu12,host=192.168.2.1,pass=<your-device-password>"
      ],
      "env": { "PYTHONUNBUFFERED": "1" }
    }
  }
}
```

The MCP server also exposes a fixed set of read-only resources:

```text
status/basic   status/list   config/list   schema/list   log/list   tool/list
```

By default the MCP server writes diagnostic events to stderr only (your MCP client captures them in its own log). To also persist them to `~/.agent-mcp/logs/agent-mcp.log`, pass `--log-file` or set `AGENT_MCP_LOG_FILE=1`:

```json
"env": { "AGENT_MCP_LOG_FILE": "1", "PYTHONUNBUFFERED": "1" }
```

**Use it when:** Your client (Claude Code, Cursor, Claude Desktop) supports MCP and you prefer structured tool calls and finer-grained permission prompts over shell invocation.

On Windows, `python mcp-server/install_claude_code_windows.py` will run `claude mcp add` for you and seed a starter `mcp-server/config/config.json` if none exists.

## Security & Risk Warnings (Read Before Use)

This tool can be invoked by AI Agents to operate remote network devices over SSH. AI Agents carry inherent risks such as model hallucinations, unpredictable execution, and prompt injection. Once you authorize `agent-cli` with device credentials, an Agent acts under your identity within the authorized scope, and may produce high-risk outcomes including configuration drift, loss of connectivity, or unintended firmware operations. Please use with caution.

To reduce these risks, `agent-cli` enables default protections at multiple layers — schema-backed preflight for `config set`, an explicit safety tier for `upgrade` / `reboot`, and a separation of read-only resources from mutating tools. However, these risks still exist. We strongly recommend that you:

- Treat `upgrade` and `reboot` as destructive operations and require explicit human approval at the Agent level.
- Validate every `config set` with `schema <root> --validation` first.
- Keep device credentials out of shell history and source control; prefer the JSON config file with appropriate file permissions.

Please fully understand the risks before use. By using this tool you are deemed to voluntarily assume all related responsibilities.

## Repository Layout

```text
agent-cli/
|-- cli/                    # agent-cli (CLI transport)
|   |-- cli.py
|   |-- command_surface.py
|   |-- ssh_bridge.py
|   |-- tests/
|   `-- README.md
|-- mcp-server/             # agent-mcp (MCP transport)
|   |-- server.py
|   |-- ssh_bridge.py
|   |-- skills_installer.py
|   |-- install_claude_code_windows.py
|   |-- config/
|   |-- tests/
|   `-- README.md
|-- skills/                 # Bundled Claude skills
|   |-- agent-cli-config/
|   |-- agent-cli-device-diagnostics/
|   |-- agent-cli-inspect/
|   |-- agent-cli-operate/
|   `-- agent-cli-shared/
|-- pyproject.toml
|-- setup.py
|-- LICENSE
`-- README.md
```

See [cli/README.md](cli/README.md) and [mcp-server/README.md](mcp-server/README.md) for component-level details.

## Contributing

Community contributions are welcome. If you find a bug or have a feature suggestion, please open an [Issue](https://github.com/inhandnet/agent-cli/issues) or [Pull Request](https://github.com/inhandnet/agent-cli/pulls). For major changes, we recommend opening an Issue first to discuss the approach.

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
