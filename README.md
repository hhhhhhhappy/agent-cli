# agent-cli

## 1. Introduction

`agent-cli` is a Python-based MCP server that you can control InHand Router devices over SSH.

This repository provides two main command-line entrypoints:

- `agent-cli-mcp`: starts the MCP server and exposes device operations through MCP tools
- `agent-cli-skills`: installs the bundled skill assets included in this repository

The top-level README focuses on project overview and installation. Full MCP usage details are available in [`mcp-server/README.md`](./mcp-server/README.md).

## 2. Features

- Exposes MCP tools for `status`, `config`, `log`, `schema`, `tool`, `upgrade`, and `reboot`
- Connects to remote devices over SSH through the device-side `agent_cli` entrypoint
- Supports inline device definitions with repeated `--device` arguments
- Automatically prepares runtime SSH keys and `known_hosts` data for bootstrap workflows
- Works with Claude Code through standard stdio MCP configuration
- Includes a bundled skill installer for shipping repository skills such as `device-diagnostics`

## 3. Installation

### 3.1 Prerequisites

Before installing or running this project, make sure the following tools are available:

- Python 3.6 or later
- `ssh`
- `ssh-keygen`
- `ssh-keyscan`
- Valid SSH bootstrap credentials for the target device

If you want to use `uvx`, you also need a working `uv` installation.

### 3.2 Installation Methods

#### Option A: Install with `uvx`

Use this option after the repository is available from GitHub.

If you want Claude Code to launch the MCP server through `.mcp.json`, you can edit ~/.claude.json ,add config like

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
        "name=lab-ir624,host=192.168.1.1,pass=<PASSWORD>"
      ]
    }
  }
}
```

Install the Inhand skills:

```bash
uvx --from git+https://github.com/inhandnet/agent-cli agent-cli-skills install
```

#### Option B: Manual Installation

Clone the repository and install it locally:

```bash
git clone https://github.com/inhandnet/agent-cli.git
cd agent-cli
```

## 4. Developer Options

Run the server directly from the repository without installing the package:


Install bundled skills into a custom directory:

```bash
agent-cli-skills install --dest /path/to/skills
```


The package entrypoints are defined in [`pyproject.toml`](./pyproject.toml), and the detailed MCP documentation is maintained in [`mcp-server/README.md`](./mcp-server/README.md).
