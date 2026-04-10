from __future__ import print_function

import argparse
import json
import os
import shutil
import subprocess
import sys


MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SERVER_SCRIPT_PATH = os.path.join(MODULE_DIR, "server.py")
DEFAULT_CONFIG_PATH = os.path.join(MODULE_DIR, "config", "config.json")
DEFAULT_CONFIG_EXAMPLE_PATH = os.path.join(MODULE_DIR, "config", "config.json.example")
DEFAULT_SERVER_NAME = "agent-cli"
DEFAULT_SCOPE = "user"


class InstallError(Exception):
    """Raised when Claude Code installer input is invalid."""


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Install this MCP server into Claude Code for a Windows checkout."
    )
    parser.add_argument(
        "--name",
        default=DEFAULT_SERVER_NAME,
        help="Claude Code MCP server name. Defaults to {0}.".format(DEFAULT_SERVER_NAME),
    )
    parser.add_argument(
        "--scope",
        choices=["local", "project", "user"],
        default=DEFAULT_SCOPE,
        help=(
            "Claude Code MCP scope passed to `claude mcp add`. "
            "Defaults to {0}.".format(DEFAULT_SCOPE)
        ),
    )
    parser.add_argument(
        "--project-dir",
        default=MODULE_DIR,
        help=(
            "Working directory used when running `claude mcp add`. "
            "Defaults to {0}.".format(MODULE_DIR)
        ),
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help="Path to the runtime config file. Defaults to {0}.".format(DEFAULT_CONFIG_PATH),
    )
    parser.add_argument(
        "--claude-command",
        default=None,
        help=(
            "Override the Claude Code CLI command. "
            "By default the installer uses `claude` from PATH."
        ),
    )
    parser.add_argument(
        "--python-command",
        default=None,
        help=(
            "Override the Python command used to launch this MCP server. "
            "By default the installer prefers `py -3`, then falls back to the current interpreter."
        ),
    )
    parser.add_argument(
        "--python-arg",
        action="append",
        default=[],
        help="Additional argument to append before server.py when --python-command is used.",
    )
    parser.add_argument(
        "--takeover",
        action="store_true",
        help="Start the server with --takeover so it can replace an existing device lease holder.",
    )
    return parser.parse_args(argv)


def ensure_config_file(config_path, example_path):
    config_path = os.path.abspath(config_path)
    if os.path.exists(config_path):
        return False

    if not os.path.exists(example_path):
        raise InstallError("Config example does not exist: {0}".format(example_path))

    config_dir = os.path.dirname(config_path)
    if config_dir and not os.path.isdir(config_dir):
        os.makedirs(config_dir)

    shutil.copyfile(example_path, config_path)
    return True


def resolve_python_command(explicit_command=None, explicit_args=None, which_func=None, sys_executable=None):
    if explicit_command:
        return explicit_command, list(explicit_args or [])

    which_func = which_func or shutil.which
    if which_func("py"):
        return "py", ["-3"]

    sys_executable = sys_executable or sys.executable
    if sys_executable and os.path.exists(sys_executable):
        return os.path.abspath(sys_executable), []

    for candidate in ["python", "python3"]:
        if which_func(candidate):
            return candidate, []

    raise InstallError(
        "Unable to find a Python launcher. Install Python 3 or pass --python-command explicitly."
    )


def resolve_claude_command(explicit_command=None, which_func=None):
    if explicit_command:
        return explicit_command

    which_func = which_func or shutil.which
    command = which_func("claude")
    if command:
        return command

    raise InstallError(
        "Unable to find the Claude Code CLI `claude` in PATH. Install Claude Code or pass --claude-command."
    )


def build_server_command(server_script_path, config_path, python_command, python_args=None, takeover=False):
    args = [python_command]
    args.extend(list(python_args or []))
    args.append(os.path.abspath(server_script_path))
    args.extend(["--config", os.path.abspath(config_path)])
    if takeover:
        args.append("--takeover")
    return args


def build_claude_add_command(claude_command, server_name, scope, server_command):
    return [
        claude_command,
        "mcp",
        "add",
        "--transport",
        "stdio",
        "--scope",
        scope,
        server_name,
        "--",
    ] + list(server_command)


def run_command(command, cwd, run_func=None):
    run_func = run_func or subprocess.run
    return run_func(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        check=False,
    )


def install(server_name,
            config_path,
            config_example_path=DEFAULT_CONFIG_EXAMPLE_PATH,
            server_script_path=DEFAULT_SERVER_SCRIPT_PATH,
            scope=DEFAULT_SCOPE,
            project_dir=MODULE_DIR,
            claude_command=None,
            python_command=None,
            python_args=None,
            takeover=False,
            which_func=None,
            run_func=None,
            sys_executable=None):
    if not server_name:
        raise InstallError("Server name must not be empty")
    if scope not in ("local", "project", "user"):
        raise InstallError("Unsupported scope: {0}".format(scope))

    server_script_path = os.path.abspath(server_script_path)
    if not os.path.exists(server_script_path):
        raise InstallError("Server script does not exist: {0}".format(server_script_path))
    project_dir = os.path.abspath(project_dir)
    if not os.path.isdir(project_dir):
        raise InstallError("Project directory does not exist: {0}".format(project_dir))

    config_created = ensure_config_file(config_path, config_example_path)
    resolved_claude_command = resolve_claude_command(
        explicit_command=claude_command,
        which_func=which_func,
    )
    command, resolved_python_args = resolve_python_command(
        explicit_command=python_command,
        explicit_args=python_args,
        which_func=which_func,
        sys_executable=sys_executable,
    )
    server_command = build_server_command(
        server_script_path,
        config_path,
        command,
        python_args=resolved_python_args,
        takeover=takeover,
    )
    add_command = build_claude_add_command(
        resolved_claude_command,
        server_name,
        scope,
        server_command,
    )
    result = run_command(add_command, cwd=project_dir, run_func=run_func)
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip() or "Unknown error"
        raise InstallError("`claude mcp add` failed: {0}".format(details))

    return {
        "config_created": config_created,
        "config_path": os.path.abspath(config_path),
        "claude_command": resolved_claude_command,
        "project_dir": project_dir,
        "scope": scope,
        "python_command": command,
        "python_args": resolved_python_args,
        "server_command": server_command,
        "server_name": server_name,
        "add_command": add_command,
    }


def main(argv=None):
    options = parse_args(argv if argv is not None else sys.argv[1:])

    if os.name != "nt":
        print(
            "Warning: this installer targets Windows and runs a Windows-oriented Claude Code install flow.",
            file=sys.stderr,
        )

    try:
        result = install(
            server_name=options.name,
            config_path=options.config,
            scope=options.scope,
            project_dir=options.project_dir,
            claude_command=options.claude_command,
            python_command=options.python_command,
            python_args=options.python_arg,
            takeover=options.takeover,
        )
    except InstallError as exc:
        print("Install failed: {0}".format(exc), file=sys.stderr)
        return 2

    if result["config_created"]:
        print("Created starter runtime config: {0}".format(result["config_path"]))
    print("Claude Code CLI: {0}".format(result["claude_command"]))
    print("Project directory: {0}".format(result["project_dir"]))
    print("Registered MCP server: {0}".format(result["server_name"]))
    print("Scope: {0}".format(result["scope"]))
    print("Server command: {0}".format(json.dumps(result["server_command"])))
    print("Next: edit {0} with your device info, then open {1} in Claude Code.".format(
        result["config_path"],
        result["project_dir"],
    ))
    if result["scope"] == "project":
        print("Claude Code should create or update .mcp.json in that project directory.")
        print("Claude Code will ask you to approve the project-scoped MCP server from .mcp.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
