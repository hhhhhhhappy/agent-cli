from __future__ import print_function

import json
import os
import shutil
import tempfile
import unittest

import external_mcp_server.install_claude_code_windows as installer


class _CompletedProcess(object):
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class ClaudeCodeWindowsInstallerTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mcp-install-test-")
        self.server_path = os.path.join(self.temp_dir, "server.py")
        self.config_dir = os.path.join(self.temp_dir, "config")
        self.config_path = os.path.join(self.config_dir, "config.json")
        self.config_example_path = os.path.join(self.config_dir, "config.json.example")
        self.project_dir = os.path.join(self.temp_dir, "project")
        self.python_path = os.path.join(self.temp_dir, "python.exe")
        self.claude_path = os.path.join(self.temp_dir, "claude.cmd")

        with open(self.server_path, "w") as handle:
            handle.write("print('server')\n")
        os.makedirs(self.config_dir)
        os.makedirs(self.project_dir)
        with open(self.config_example_path, "w") as handle:
            json.dump({"devices": {"lab-ir624": {"device_ip": "192.0.2.10"}}}, handle)
        with open(self.python_path, "w") as handle:
            handle.write("")
        with open(self.claude_path, "w") as handle:
            handle.write("")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_ensure_config_file_copies_example_when_missing(self):
        created = installer.ensure_config_file(self.config_path, self.config_example_path)

        self.assertTrue(created)
        with open(self.config_path, "r") as handle:
            payload = json.load(handle)
        self.assertEqual(payload["devices"]["lab-ir624"]["device_ip"], "192.0.2.10")

    def test_resolve_python_command_prefers_py_launcher(self):
        command, args = installer.resolve_python_command(
            which_func=lambda name: name == "py",
            sys_executable=self.python_path,
        )

        self.assertEqual(command, "py")
        self.assertEqual(args, ["-3"])

    def test_parse_args_defaults_scope_to_user(self):
        options = installer.parse_args([])

        self.assertEqual(options.scope, "user")

    def test_build_claude_add_command_uses_stdio_scope(self):
        command = installer.build_claude_add_command(
            "claude",
            "agent-mcp",
            "project",
            ["py", "-3", self.server_path, "--config", self.config_path],
        )

        self.assertEqual(
            command,
            [
                "claude",
                "mcp",
                "add",
                "--transport",
                "stdio",
                "--scope",
                "project",
                "agent-mcp",
                "--",
                "py",
                "-3",
                self.server_path,
                "--config",
                self.config_path,
            ],
        )

    def test_install_creates_config_and_invokes_claude_add(self):
        captured = {}

        def fake_run(command, cwd, stdout, stderr, universal_newlines, check):
            captured["command"] = command
            captured["cwd"] = cwd
            captured["stdout"] = stdout
            captured["stderr"] = stderr
            captured["universal_newlines"] = universal_newlines
            captured["check"] = check
            return _CompletedProcess(returncode=0)

        result = installer.install(
            server_name="agent-mcp",
            config_path=self.config_path,
            config_example_path=self.config_example_path,
            server_script_path=self.server_path,
            project_dir=self.project_dir,
            scope="project",
            claude_command=self.claude_path,
            python_command="py",
            python_args=["-3"],
            run_func=fake_run,
        )

        self.assertTrue(result["config_created"])
        self.assertEqual(result["project_dir"], self.project_dir)
        self.assertEqual(
            captured["command"],
            [
                self.claude_path,
                "mcp",
                "add",
                "--transport",
                "stdio",
                "--scope",
                "project",
                "agent-mcp",
                "--",
                "py",
                "-3",
                self.server_path,
                "--config",
                self.config_path,
            ],
        )
        self.assertEqual(captured["cwd"], self.project_dir)
        self.assertFalse(captured["check"])

    def test_install_passes_takeover_and_falls_back_to_current_python(self):
        captured = {}

        def fake_run(command, cwd, stdout, stderr, universal_newlines, check):
            captured["command"] = command
            captured["cwd"] = cwd
            return _CompletedProcess(returncode=0)

        with open(self.config_path, "w") as handle:
            json.dump({"devices": {}}, handle)

        result = installer.install(
            server_name="agent-mcp",
            config_path=self.config_path,
            config_example_path=self.config_example_path,
            server_script_path=self.server_path,
            project_dir=self.project_dir,
            scope="user",
            claude_command=self.claude_path,
            sys_executable=self.python_path,
            which_func=lambda name: None,
            takeover=True,
            run_func=fake_run,
        )

        self.assertFalse(result["config_created"])
        self.assertEqual(result["python_command"], self.python_path)
        self.assertEqual(result["scope"], "user")
        self.assertEqual(captured["command"][-1], "--takeover")

    def test_install_defaults_scope_to_user(self):
        captured = {}

        def fake_run(command, cwd, stdout, stderr, universal_newlines, check):
            captured["command"] = command
            captured["cwd"] = cwd
            return _CompletedProcess(returncode=0)

        with open(self.config_path, "w") as handle:
            json.dump({"devices": {}}, handle)

        result = installer.install(
            server_name="agent-mcp",
            config_path=self.config_path,
            config_example_path=self.config_example_path,
            server_script_path=self.server_path,
            project_dir=self.project_dir,
            claude_command=self.claude_path,
            python_command="py",
            python_args=["-3"],
            run_func=fake_run,
        )

        self.assertEqual(result["scope"], "user")
        self.assertEqual(
            captured["command"][:7],
            [
                self.claude_path,
                "mcp",
                "add",
                "--transport",
                "stdio",
                "--scope",
                "user",
            ],
        )

    def test_install_raises_when_claude_add_fails(self):
        def fake_run(command, cwd, stdout, stderr, universal_newlines, check):
            return _CompletedProcess(returncode=1, stderr="already exists")

        with self.assertRaises(installer.InstallError) as context:
            installer.install(
                server_name="agent-mcp",
                config_path=self.config_path,
                config_example_path=self.config_example_path,
                server_script_path=self.server_path,
                project_dir=self.project_dir,
                claude_command=self.claude_path,
                python_command="py",
                python_args=["-3"],
                run_func=fake_run,
            )

        self.assertIn("claude mcp add", str(context.exception))
