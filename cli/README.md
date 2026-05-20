# agent-cli

`agent-cli` is a Windows-oriented CLI for reaching `agent_cli` on a remote device over SSH.

## Prerequisites

- Windows OpenSSH Client (`ssh.exe`, `ssh-keygen.exe`, `ssh-keyscan.exe`) on `PATH`
- `uv` installed locally

Install `uv` on Windows with:

```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

## Install From GitHub

Install `agent-cli` directly from this repository:

```powershell
uv tool install --from git+https://github.com/inhandnet/agent-cli.git#subdirectory=cli agent-cli
```

If the command is not available in a new shell yet, run:

```powershell
uv tool update-shell
```

Then verify the install:

```powershell
agent-cli --help
```

## Recommended First Use

For a first-time setup, prefer bootstrapping and saving the device profile with:

```powershell
agent-cli auth
```

With no auth flags, `agent-cli auth` interactively prompts for host, port, bootstrap user, and password, then writes the saved config to `~/.agent-cli/config.json`.

After that, you can use the saved device profile instead of repeating `--device` on every command:

```powershell
agent-cli status basic
agent-cli config get system.hostname
agent-cli schema system --validation
```

If you do not want to save a config yet, inline device mode is still supported:

```powershell
agent-cli --device name=lab-ir624,host=192.0.2.10,pass=replace-me status basic
```
