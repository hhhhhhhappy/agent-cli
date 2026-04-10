# agent-cli

A Python-based MCP server that lets AI assistants control InHand Router devices over SSH.

## Overview

`agent_cli` CLI over an SSH session. Once configured, Claude (or any MCP-capable client) can query device status, read and write configuration, retrieve logs, run network diagnostics, and perform firmware upgrades — all through natural language.

## Features

- **7 MCP tools**: `status`, `config`, `log`, `schema`, `tool`, `upgrade`, `reboot`
- **Read-only MCP resources** for fast status and discovery lookups
- **Zero-touch SSH bootstrap**: on first run, generates ed25519 keys, fetches host keys, and registers the public key on the device automatically
- **Persistent SSH session** per device — one live stdio connection, no per-call reconnect overhead
- **Multi-device support** via repeated `--device` arguments
- **Bundled skill installer** for shipping AI diagnostic skills such as `device-diagnostics`
- **Works with Claude Code** through standard stdio MCP configuration

## Prerequisites

| Requirement                  | Notes                                         |
| ---------------------------- | --------------------------------------------- |
| Python 3.6+                  |                                               |
| ssh, ssh-keygen, ssh-keyscan | Standard OpenSSH client tools                 |
| Valid bootstrap credentials  | Username + password for the target device     |
| uv / uvx                     | Only needed for the `uvx` installation method |

**Windows**: install the built-in **OpenSSH Client** feature and ensure `ssh.exe`, `ssh-keygen.exe`, and `ssh-keyscan.exe` are on `PATH`. If `uvx` is not available, install it with:

```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

## Installation

### Option A — `uvx` (recommended)

No local clone needed. Claude Code fetches and runs the server directly from GitHub.

**Use the Claude CLI** to create `.mcp.json` for you:

```bash
claude mcp add agent-cli  --transport stdio  -- uvx --from git+https://github.com/inhandnet/agent-cli agent-cli-mcp --device name=odu2012,host=192.168.1.1,pass=<PASSWORD>,port=22
```

**Or add to `.claude.json`** :

```json
{
  "mcpServers": {
    "agent-cli": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/inhandnet/agent-cli",
        "agent-cli-mcp",
        "--device",
        "name=odu2012,host=192.168.1.1,pass=<PASSWORD>,port=22"
      ]
    }
  }
}
```

**Install the bundled skills**:

```bash
uvx --from git+https://github.com/inhandnet/agent-cli agent-cli-skills install
```

### Option B — Local Checkout

```bash
git clone https://github.com/inhandnet/agent-cli.git
cd agent-cli

# Windows helper — creates the default config and runs claude mcp add
python mcp-server/install_claude_code_windows.py 
```

Then edit `mcp-server/config/config.json` with your device credentials:

```json
{
  "devices": {
    "odu2012": {
      "host": "192.168.1.1",
      "bootstrap_user": "adm",
      "bootstrap_password": "replace-me",
      "port": "22"
    }
  }
}
```

| Field   | Required | Default | Description                                              |
| ------- |:--------:| ------- | -------------------------------------------------------- |
| `name`  | yes      | —       | Logical device ID; used as `device_id` in MCP tool calls |
| `host`  | yes      | —       | Device IP address or hostname                            |
| `pass`  | yes      | —       | Bootstrap password (used only on first connection)       |
| `buser` | no       | `adm`   | Bootstrap SSH username                                   |
| `port`  | no       | `22`    | SSH port                                                 |

## SSH Key PATH

On first connection to a device, the server will creat SSH Key:

1. If use `Option B` per-device key directory under  `agent-cli/mcp-server/keys/<device_id>/`
2. If use `Option A`,a per-device key directory under  `~/.agent-cli-mcp/keys/<device_id>/`


## Bundled Skill: `device-diagnostics`

After running `agent-cli-skills install`, the `device-diagnostics` skill is available in Claude conversations. It automatically routes to the appropriate diagnostic flow based on the symptoms described.

| Scenario           | Symptoms                                                       |
| ------------------ | -------------------------------------------------------------- |
| `connectivity`     | No internet, DNS failure, packet loss, intermittent connection |
| `cellular`         | SIM / carrier registration, APN, signal, cellular disconnect   |
| `wan`              | Wired uplink failure, DHCP / static IP, gateway loss           |
| `lan`              | DHCP leases, local subnet, client connectivity                 |
| `performance`      | Low throughput, high latency, jitter                           |
| `log`              | Unknown failing subsystem — start from logs                    |
| `config-audit`     | Device reachable but behavior doesn't match config             |
| `firmware-release` | Firmware version query, changelog, upgrade recommendation      |

Diagnostic output format: **Summary → Findings → Evidence → Gaps → Next actions**

## Operation Safety Levels

| Level       | Operations                              | Notes                           |
| ----------- | --------------------------------------- | ------------------------------- |
| Read-only   | `status`, `config get`, `log`, `schema` | Safe at any time                |
| Diagnostic  | `tool` (ping, traceroute, …)            | Minor runtime impact            |
| Change      | `config set`                            | Validate with `schema` first    |
| Destructive | `upgrade`, `reboot`                     | Requires explicit user approval |

## Direct SSH Usage

After the MCP server has registered a key, you can also invoke `agent_cli` directly over SSH:

> On first connection to a device, the server will creat SSH Key:
> 
> 1. If use `Option B` per-device key directory under `agent-cli/mcp-server/keys/<device_id>/agent_key_<TIMESTAMP>/`
> 2. If use `Option A`,a per-device key directory under `~/.agent-cli-mcp/keys/<device_id>/agent_key_<TIMESTAMP>/`

```bash
SSH="ssh -i ~/.agent-cli-mcp/keys/odu2012/agent_key_20260410_190423/agent_key -p 22 agent@192.168.1.1"

$SSH "status basic"
$SSH "status cellular"
$SSH "config get cellular"
$SSH 'config set cellular {"apn":"internet.example.com"}'
$SSH "schema wan --validation"
$SSH "log agent --line 100"
$SSH 'tool ping {"action":"start","host":"8.8.8.8"}'
$SSH "upgrade --url https://example.com/fw.bin"
$SSH "reboot"
```

All commands return a single-line JSON response:

```json
{ "ok": true, "data": { ... } }
{ "ok": false, "error": { "code": "...", "message": "..." } }
```

| Code | Constant      | Meaning                        |
| ---- | ------------- | ------------------------------ |
| 0    | EXIT_OK       | success                        |
| 1    | EXIT_ERROR    | general / unexpected error     |
| 2    | EXIT_NOTFOUND | resource not found             |
| 3    | EXIT_TIMEOUT  | transport / service timeout    |
| 4    | EXIT_BADARGS  | invalid command-line arguments |

## Project Structure

```
agent-cli/
├── mcp-server/
│   ├── server.py              # MCP server entrypoint
│   ├── ssh_bridge.py          # SSH session management
│   ├── config/
│   │   └── config.json.example
│   ├── tests/
│   └── README.md              # Detailed MCP documentation
├── pyproject.toml
└── README.md
```

## License

See [LICENSE](./LICENSE) for details.
