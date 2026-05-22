from __future__ import print_function

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import external_mcp_server.ssh_bridge as ssh_bridge_module
from external_mcp_server.ssh_bridge import (
    ConfigError,
    SSHBridge,
    _OpenSSHBootstrapClient,
    _SSHStdioSession,
)


class FakeSession(object):
    def __init__(self, results):
        self.results = list(results)
        self.commands = []
        self.closed = False

    def is_alive(self):
        return not self.closed

    def execute(self, remote_command, timeout_sec):
        self.commands.append((remote_command, timeout_sec))
        if self.results:
            return self.results.pop(0)
        return {
            "exit_code": 0,
            "stdout": b'{"ok":true,"data":{}}\n',
            "stderr": b"",
            "timed_out": False,
        }

    def close(self):
        self.closed = True


class FakeSessionFactory(object):
    def __init__(self, session_results):
        self.session_results = list(session_results)
        self.commands = []
        self.sessions = []

    def __call__(self, command):
        self.commands.append(list(command))
        results = self.session_results.pop(0) if self.session_results else []
        session = FakeSession(results)
        self.sessions.append(session)
        return session


class FakeBootstrapClient(object):
    def __init__(self, results=None):
        self.results = list(results or [])
        self.calls = []

    def run(self, profile, command, connect_timeout_sec, command_timeout_sec, known_hosts_file):
        self.calls.append(
            {
                "profile": dict(profile),
                "command": command,
                "connect_timeout_sec": connect_timeout_sec,
                "command_timeout_sec": command_timeout_sec,
                "known_hosts_file": known_hosts_file,
            }
        )
        if self.results:
            return self.results.pop(0)
        return {
            "exit_code": 0,
            "stdout": b'{"result":{"state":"created","lease_expires_at":2000}}\n',
            "stderr": b"",
        }


class SSHBridgeTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mcp-bridge-test-")
        self.known_hosts_path = os.path.join(self.temp_dir, "known_hosts")
        self.identity_path = os.path.join(self.temp_dir, "device_key")
        self.identity_pub_path = self.identity_path + ".pub"
        self.config_path = os.path.join(self.temp_dir, "devices.json")

        with open(self.known_hosts_path, "w") as handle:
            handle.write("example ssh-rsa not-a-real-known-host-key\n")
        with open(self.identity_path, "w") as handle:
            handle.write("dummy-key\n")
        with open(self.identity_pub_path, "w") as handle:
            handle.write("ssh-ed25519 not-a-real-public-key test@example\n")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def _write_config(self, payload):
        with open(self.config_path, "w") as handle:
            json.dump(payload, handle)
        os.chmod(self.config_path, 0o600)

    def _build_bridge(self, session_factory=None, bootstrap_client=None, now=1000, takeover=False):
        self._write_config(
            {
                "devices": {
                    "device-a": {
                        "device_ip": "192.0.2.1",
                        "identity_file": "./device_key",
                        "user": "adm",
                        "pass": "secret",
                    }
                }
            }
        )
        return SSHBridge(
            self.config_path,
            session_factory=session_factory,
            bootstrap_client=bootstrap_client,
            clock=lambda: now,
            takeover=takeover,
            start_renew_thread=False,
        )

    def test_builds_ssh_command_with_controlmaster(self):
        bridge = self._build_bridge(session_factory=FakeSessionFactory([]), bootstrap_client=FakeBootstrapClient())
        command = bridge.build_ssh_command("device-a", "status basic")

        self.assertIn("ControlMaster=auto", command)
        self.assertIn("ControlPersist=300", command)
        self.assertIn("ConnectTimeout=10", command)
        self.assertIn("UserKnownHostsFile={0}".format(self.known_hosts_path), command)
        self.assertEqual(command[-1], "status basic")

    def test_windows_ssh_command_omits_controlmaster_options(self):
        bridge = self._build_bridge(session_factory=FakeSessionFactory([]), bootstrap_client=FakeBootstrapClient())

        with mock.patch("external_mcp_server.ssh_bridge._is_windows", return_value=True):
            command = bridge.build_ssh_command("device-a", "status basic")

        self.assertNotIn("ControlMaster=auto", command)
        self.assertNotIn("ControlPersist=300", command)
        self.assertFalse(any(option.startswith("ControlPath=") for option in command))
        self.assertEqual(command[-1], "status basic")

    def test_single_device_bridge_exposes_default_device_id(self):
        bridge = self._build_bridge(session_factory=FakeSessionFactory([]), bootstrap_client=FakeBootstrapClient())

        self.assertEqual(bridge.get_device_ids(), ["device-a"])
        self.assertEqual(bridge.get_default_device_id(), "device-a")

    def test_multi_device_bridge_does_not_expose_default_device_id(self):
        self._write_config(
            {
                "devices": {
                    "device-b": {
                        "device_ip": "192.0.2.2",
                        "identity_file": "./device_key",
                        "user": "adm",
                        "pass": "secret-b",
                    },
                    "device-a": {
                        "device_ip": "192.0.2.1",
                        "identity_file": "./device_key",
                        "user": "adm",
                        "pass": "secret-a",
                    }
                }
            }
        )

        bridge = SSHBridge(
            self.config_path,
            session_factory=FakeSessionFactory([]),
            bootstrap_client=FakeBootstrapClient(),
            clock=lambda: 1000,
            start_renew_thread=False,
        )

        self.assertEqual(bridge.get_device_ids(), ["device-a", "device-b"])
        self.assertIsNone(bridge.get_default_device_id())

    def test_from_config_data_resolves_paths_relative_to_base_dir(self):
        config_dir = os.path.join(self.temp_dir, "runtime")
        os.makedirs(config_dir)
        with open(os.path.join(config_dir, "known_hosts"), "w") as handle:
            handle.write("example ssh-rsa not-a-real-known-host-key\n")
        with open(os.path.join(config_dir, "device_key"), "w") as handle:
            handle.write("dummy-key\n")
        with open(os.path.join(config_dir, "device_key.pub"), "w") as handle:
            handle.write("ssh-ed25519 not-a-real-public-key test@example\n")

        bridge = SSHBridge.from_config_data(
            {
                "ssh_defaults": {
                    "known_hosts_file": "./known_hosts",
                    "control_path_dir": "./ssh-control",
                },
                "devices": {
                    "device-a": {
                        "device_ip": "192.0.2.1",
                        "identity_file": "./device_key",
                        "pass": "secret",
                    }
                },
            },
            base_dir=config_dir,
            session_factory=FakeSessionFactory([]),
            bootstrap_client=FakeBootstrapClient(),
            clock=lambda: 1000,
            start_renew_thread=False,
        )

        self.assertEqual(bridge.config_path, os.path.join(config_dir, "config.json"))
        self.assertEqual(bridge.ssh_defaults["known_hosts_file"], os.path.join(config_dir, "known_hosts"))
        self.assertEqual(bridge.ssh_defaults["control_path_dir"], os.path.join(config_dir, "ssh-control"))
        self.assertEqual(bridge.devices["device-a"]["identity_file"], os.path.join(config_dir, "device_key"))
        self.assertEqual(bridge.devices["device-a"]["user"], "adm")

    def test_execute_accepts_full_command(self):
        factory = FakeSessionFactory(
            [
                [
                    {
                        "exit_code": 0,
                        "stdout": b'{"ok":true,"data":{"result":{"status":"ok"}}}\n',
                        "stderr": b"",
                        "timed_out": False,
                    }
                ]
            ]
        )
        bootstrap_client = FakeBootstrapClient()

        bridge = self._build_bridge(session_factory=factory, bootstrap_client=bootstrap_client)
        result = bridge.execute("device-a", command="status basic")

        self.assertTrue(result["ok"])
        self.assertEqual(factory.sessions[0].commands[0][0], "status basic")
        self.assertEqual(len(bootstrap_client.calls), 1)
        self.assertIn("mcp key ensure", bootstrap_client.calls[0]["command"])
        self.assertNotIn("owner_id", bootstrap_client.calls[0]["command"])

    def test_execute_with_takeover_adds_takeover_flag(self):
        factory = FakeSessionFactory(
            [
                [
                    {
                        "exit_code": 0,
                        "stdout": b'{"ok":true,"data":{}}\n',
                        "stderr": b"",
                        "timed_out": False,
                    }
                ]
            ]
        )
        bootstrap_client = FakeBootstrapClient()

        bridge = self._build_bridge(session_factory=factory, bootstrap_client=bootstrap_client, takeover=True)
        result = bridge.execute("device-a", command="status basic")

        self.assertTrue(result["ok"])
        self.assertIn("mcp key ensure --takeover", bootstrap_client.calls[0]["command"])

    def test_execute_returns_successful_structured_result(self):
        factory = FakeSessionFactory(
            [
                [
                    {
                        "exit_code": 0,
                        "stdout": b'{"ok":true,"data":{"system":{"hostname":"edge-a"}}}\n',
                        "stderr": b"",
                        "timed_out": False,
                    }
                ]
            ]
        )

        bridge = self._build_bridge(session_factory=factory, bootstrap_client=FakeBootstrapClient())
        result = bridge.execute("device-a", "set", "system.hostname", {"hostname": "edge-a"})

        self.assertTrue(result["ok"])
        self.assertEqual(result["ssh_exit_code"], 0)
        self.assertEqual(result["response"]["system"]["hostname"], "edge-a")
        self.assertIsNone(result["error"])
        self.assertEqual(factory.sessions[0].commands[0][0], 'set system.hostname {"hostname":"edge-a"}')
        self.assertEqual(factory.sessions[0].commands[0][1], 30)

    def test_execute_reuses_persistent_session_and_binding(self):
        factory = FakeSessionFactory(
            [
                [
                    {
                        "exit_code": 0,
                        "stdout": b'{"ok":true,"data":{"result":"first"}}\n',
                        "stderr": b"",
                        "timed_out": False,
                    },
                    {
                        "exit_code": 0,
                        "stdout": b'{"ok":true,"data":{"result":"second"}}\n',
                        "stderr": b"",
                        "timed_out": False,
                    },
                ]
            ]
        )
        bootstrap_client = FakeBootstrapClient(
            [
                {
                    "exit_code": 0,
                    "stdout": b'{"result":{"state":"created","lease_expires_at":2000}}\n',
                    "stderr": b"",
                }
            ]
        )

        bridge = self._build_bridge(session_factory=factory, bootstrap_client=bootstrap_client)
        first = bridge.execute("device-a", command="status basic")
        second = bridge.execute("device-a", command="config get system")

        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])
        self.assertEqual(len(factory.sessions), 1)
        self.assertEqual(len(bootstrap_client.calls), 1)
        self.assertEqual(factory.sessions[0].commands[0][0], "status basic")
        self.assertEqual(factory.sessions[0].commands[1][0], "config get system")

    def test_execute_legacy_arguments_still_work(self):
        factory = FakeSessionFactory(
            [
                [
                    {
                        "exit_code": 0,
                        "stdout": b'{"ok":true,"data":{"result":"legacy"}}\n',
                        "stderr": b"",
                        "timed_out": False,
                    }
                ]
            ]
        )

        bridge = self._build_bridge(session_factory=factory, bootstrap_client=FakeBootstrapClient())
        result = bridge.execute("device-a", "status", "basic")

        self.assertTrue(result["ok"])
        self.assertEqual(factory.sessions[0].commands[0][0], "status basic")

    def test_execute_preserves_explicit_json_null_argument(self):
        factory = FakeSessionFactory(
            [
                [
                    {
                        "exit_code": 0,
                        "stdout": b'{"ok":true,"data":{}}\n',
                        "stderr": b"",
                        "timed_out": False,
                    }
                ]
            ]
        )

        bridge = self._build_bridge(session_factory=factory, bootstrap_client=FakeBootstrapClient())
        result = bridge.execute("device-a", "set", "system.hostname", None)

        self.assertTrue(result["ok"])
        self.assertEqual(factory.sessions[0].commands[0][0], "set system.hostname null")

    def test_execute_maps_device_cli_error(self):
        factory = FakeSessionFactory(
            [
                [
                    {
                        "exit_code": 0,
                        "stdout": b'{"ok":false,"error":{"code":"bad_args","message":"Invalid Parameter","field":"hostname"}}\n',
                        "stderr": b"",
                        "timed_out": False,
                    }
                ]
            ]
        )

        bridge = self._build_bridge(session_factory=factory, bootstrap_client=FakeBootstrapClient())
        result = bridge.execute("device-a", "set", "system.hostname", {"hostname": ""})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["kind"], "device_cli_error")
        self.assertEqual(result["error"]["code"], "bad_args")
        self.assertEqual(result["error"]["field"], "hostname")
        self.assertIsNone(result["response"])

    def test_execute_maps_transport_timeout(self):
        factory = FakeSessionFactory(
            [
                [
                    {
                        "exit_code": None,
                        "stdout": b"",
                        "stderr": b"",
                        "timed_out": True,
                    }
                ]
            ]
        )

        bridge = self._build_bridge(session_factory=factory, bootstrap_client=FakeBootstrapClient())
        result = bridge.execute("device-a", command="status basic", timeout_sec=5)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["kind"], "ssh_timeout")
        self.assertIsNone(result["ssh_exit_code"])
        self.assertTrue(factory.sessions[0].closed)

    def test_timeout_drops_session_and_reconnects_without_rebootstrap(self):
        factory = FakeSessionFactory(
            [
                [
                    {
                        "exit_code": None,
                        "stdout": b"",
                        "stderr": b"",
                        "timed_out": True,
                    }
                ],
                [
                    {
                        "exit_code": 0,
                        "stdout": b'{"ok":true,"data":{"result":"ok"}}\n',
                        "stderr": b"",
                        "timed_out": False,
                    }
                ],
            ]
        )
        bootstrap_client = FakeBootstrapClient(
            [
                {
                    "exit_code": 0,
                    "stdout": b'{"result":{"state":"created","lease_expires_at":2000}}\n',
                    "stderr": b"",
                }
            ]
        )

        bridge = self._build_bridge(session_factory=factory, bootstrap_client=bootstrap_client)
        first = bridge.execute("device-a", command="status basic", timeout_sec=5)
        second = bridge.execute("device-a", command="status basic")

        self.assertFalse(first["ok"])
        self.assertTrue(second["ok"])
        self.assertEqual(len(factory.sessions), 2)
        self.assertEqual(len(bootstrap_client.calls), 1)
        self.assertTrue(factory.sessions[0].closed)

    def test_reuses_binding_without_periodic_reensure(self):
        factory = FakeSessionFactory(
            [
                [
                    {
                        "exit_code": 0,
                        "stdout": b'{"ok":true,"data":{"result":"ok"}}\n',
                        "stderr": b"",
                        "timed_out": False,
                    },
                    {
                        "exit_code": 0,
                        "stdout": b'{"ok":true,"data":{"result":"ok"}}\n',
                        "stderr": b"",
                        "timed_out": False,
                    },
                ]
            ]
        )
        bootstrap_client = FakeBootstrapClient(
            [
                {
                    "exit_code": 0,
                    "stdout": b'{"result":{"state":"created","lease_expires_at":1030}}\n',
                    "stderr": b"",
                },
                {
                    "exit_code": 0,
                    "stdout": b'{"result":{"state":"refreshed","lease_expires_at":2000}}\n',
                    "stderr": b"",
                },
            ]
        )
        now = [1000]
        bridge = self._build_bridge(
            session_factory=factory,
            bootstrap_client=bootstrap_client,
            now=now[0],
        )
        bridge._clock = lambda: now[0]

        first = bridge.execute("device-a", command="status basic")
        now[0] = 1005
        second = bridge.execute("device-a", command="status basic")

        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])
        self.assertEqual(len(bootstrap_client.calls), 1)

    def test_manual_renew_binding_reissues_ensure_for_same_key(self):
        bootstrap_client = FakeBootstrapClient(
            [
                {
                    "exit_code": 0,
                    "stdout": b'{"result":{"state":"created","lease_expires_at":2000}}\n',
                    "stderr": b"",
                },
                {
                    "exit_code": 0,
                    "stdout": b'{"result":{"state":"refreshed","lease_expires_at":2300}}\n',
                    "stderr": b"",
                },
            ]
        )
        bridge = self._build_bridge(session_factory=FakeSessionFactory([[]]), bootstrap_client=bootstrap_client)

        bridge.execute("device-a", command="status basic")
        bridge._renew_binding("device-a")

        self.assertEqual(len(bootstrap_client.calls), 2)
        self.assertIn("mcp key ensure", bootstrap_client.calls[1]["command"])

    def test_renew_binding_drops_binding_after_takeover_conflict(self):
        bootstrap_client = FakeBootstrapClient(
            [
                {
                    "exit_code": 0,
                    "stdout": b'{"result":{"state":"created","lease_expires_at":2000}}\n',
                    "stderr": b"",
                },
                {
                    "exit_code": 1,
                    "stdout": b'{"status":409,"error":"Binding Conflict","lease_expires_at":2100}\n',
                    "stderr": b"",
                },
            ]
        )
        factory = FakeSessionFactory([[]])
        bridge = self._build_bridge(session_factory=factory, bootstrap_client=bootstrap_client)

        bridge.execute("device-a", command="status basic")
        bridge._renew_binding("device-a")

        self.assertNotIn("device-a", bridge._bindings)
        self.assertTrue(factory.sessions[0].closed)

    def test_close_revokes_binding(self):
        bootstrap_client = FakeBootstrapClient(
            [
                {
                    "exit_code": 0,
                    "stdout": b'{"result":{"state":"created","lease_expires_at":2000}}\n',
                    "stderr": b"",
                },
                {
                    "exit_code": 0,
                    "stdout": b'{"result":{"state":"deleted"}}\n',
                    "stderr": b"",
                },
            ]
        )
        bridge = self._build_bridge(session_factory=FakeSessionFactory([[]]), bootstrap_client=bootstrap_client)

        bridge.execute("device-a", command="status basic")
        bridge.close()

        self.assertEqual(len(bootstrap_client.calls), 2)
        self.assertIn("mcp key revoke", bootstrap_client.calls[1]["command"])
        self.assertIn("ssh-ed25519", bootstrap_client.calls[1]["command"])

    def test_bootstrap_failure_is_returned_as_tool_error(self):
        bootstrap_client = FakeBootstrapClient(
            [
                {
                    "exit_code": 1,
                    "stdout": b'{"status":500,"error":"Local Execution Failed"}\n',
                    "stderr": b"",
                }
            ]
        )
        bridge = self._build_bridge(session_factory=FakeSessionFactory([]), bootstrap_client=bootstrap_client)

        result = bridge.execute("device-a", command="status basic")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["kind"], "bootstrap_failed")
        self.assertEqual(result["response"]["status"], 500)

    def test_invalid_config_requires_existing_known_hosts(self):
        os.unlink(self.known_hosts_path)
        self._write_config(
            {
                "devices": {
                    "device-a": {
                        "device_ip": "192.0.2.1",
                        "identity_file": "./device_key",
                        "user": "adm",
                        "pass": "secret",
                    }
                }
            }
        )

        with self.assertRaises(ConfigError):
            SSHBridge(self.config_path)

    def test_invalid_config_requires_restrictive_permissions(self):
        with open(self.config_path, "w") as handle:
            json.dump(
                {
                    "devices": {
                        "device-a": {
                            "device_ip": "192.0.2.1",
                            "identity_file": "./device_key",
                            "user": "adm",
                            "pass": "secret",
                        }
                    }
                },
                handle,
            )
        os.chmod(self.config_path, 0o644)

        with self.assertRaises(ConfigError) as ctx:
            SSHBridge(self.config_path)

        self.assertIn(self.config_path, str(ctx.exception))
        self.assertIn("644", str(ctx.exception))
        self.assertIn("chmod 600", str(ctx.exception))

    def test_auto_key_setup_uses_python36_compatible_subprocess_run(self):
        keys_base_dir = os.path.join(self.temp_dir, "keys")
        self._write_config(
            {
                "ssh_defaults": {
                    "keys_base_dir": keys_base_dir,
                },
                "devices": {
                    "device-a": {
                        "device_ip": "192.0.2.1",
                        "user": "adm",
                        "pass": "secret",
                    }
                },
            }
        )

        calls = []

        class Completed(object):
            def __init__(self, returncode=0, stdout="", stderr=""):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr

        def fake_run(command, **kwargs):
            calls.append((list(command), dict(kwargs)))
            self.assertNotIn("capture_output", kwargs)
            self.assertNotIn("text", kwargs)
            self.assertEqual(kwargs["stdout"], subprocess.PIPE)
            self.assertEqual(kwargs["stderr"], subprocess.PIPE)
            self.assertEqual(kwargs["timeout"], 60)

            if command[0] == "ssh-keygen":
                identity_file = command[command.index("-f") + 1]
                with open(identity_file, "w") as handle:
                    handle.write("dummy-key\n")
                with open(identity_file + ".pub", "w") as handle:
                    handle.write("ssh-ed25519 not-a-real-public-key test@example\n")
                return Completed(returncode=0, stdout=b"", stderr=b"")

            if command[0] == "ssh-keyscan":
                self.assertTrue(kwargs.get("universal_newlines"))
                return Completed(
                    returncode=0,
                    stdout="192.0.2.1 ssh-ed25519 not-a-real-host-key\n",
                    stderr="",
                )

            raise AssertionError("Unexpected subprocess command: {0}".format(command))

        with mock.patch("external_mcp_server.ssh_bridge.subprocess.run", side_effect=fake_run):
            bridge = SSHBridge(self.config_path)

        self.assertEqual([call[0][0] for call in calls], ["ssh-keygen", "ssh-keyscan"])
        self.assertTrue(os.path.exists(bridge.devices["device-a"]["identity_file"]))
        self.assertTrue(os.path.exists(bridge.ssh_defaults["known_hosts_file"]))

    def test_relative_keys_base_dir_resolves_relative_to_config(self):
        self._write_config(
            {
                "ssh_defaults": {
                    "keys_base_dir": "./keys",
                },
                "devices": {
                    "device-a": {
                        "device_ip": "192.0.2.1",
                        "user": "adm",
                        "pass": "secret",
                    }
                },
            }
        )

        expected_keys_base_dir = os.path.join(self.temp_dir, "keys")
        calls = []

        class Completed(object):
            def __init__(self, returncode=0, stdout="", stderr=""):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr

        def fake_run(command, **kwargs):
            calls.append(list(command))
            if command[0] == "ssh-keygen":
                identity_file = command[command.index("-f") + 1]
                with open(identity_file, "w") as handle:
                    handle.write("dummy-key\n")
                with open(identity_file + ".pub", "w") as handle:
                    handle.write("ssh-ed25519 not-a-real-public-key test@example\n")
                return Completed(returncode=0, stdout=b"", stderr=b"")
            if command[0] == "ssh-keyscan":
                return Completed(
                    returncode=0,
                    stdout="192.0.2.1 ssh-ed25519 not-a-real-host-key\n",
                    stderr="",
                )
            raise AssertionError("Unexpected subprocess command: {0}".format(command))

        with mock.patch("external_mcp_server.ssh_bridge.subprocess.run", side_effect=fake_run):
            bridge = SSHBridge(self.config_path)

        self.assertEqual(bridge.ssh_defaults["keys_base_dir"], expected_keys_base_dir)
        self.assertEqual(bridge.ssh_defaults["known_hosts_file"], os.path.join(expected_keys_base_dir, "known_hosts"))
        self.assertTrue(bridge.devices["device-a"]["identity_file"].startswith(expected_keys_base_dir))
        self.assertEqual([command[0] for command in calls], ["ssh-keygen", "ssh-keyscan"])

    def test_project_default_config_uses_project_local_keys_dir(self):
        project_config_dir = os.path.join(self.temp_dir, "config")
        project_config_path = os.path.join(project_config_dir, "config.json")
        expected_keys_base_dir = os.path.join(self.temp_dir, "keys")
        expected_control_path_dir = os.path.join(expected_keys_base_dir, "ssh-control")

        os.makedirs(project_config_dir)
        with open(project_config_path, "w") as handle:
            json.dump(
                {
                    "devices": {
                        "device-a": {
                            "device_ip": "192.0.2.1",
                            "user": "adm",
                            "pass": "secret",
                        }
                    }
                },
                handle,
            )
        os.chmod(project_config_path, 0o600)

        calls = []

        class Completed(object):
            def __init__(self, returncode=0, stdout="", stderr=""):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr

        def fake_run(command, **kwargs):
            calls.append(list(command))
            if command[0] == "ssh-keygen":
                identity_file = command[command.index("-f") + 1]
                with open(identity_file, "w") as handle:
                    handle.write("dummy-key\n")
                with open(identity_file + ".pub", "w") as handle:
                    handle.write("ssh-ed25519 not-a-real-public-key test@example\n")
                return Completed(returncode=0, stdout=b"", stderr=b"")
            if command[0] == "ssh-keyscan":
                return Completed(
                    returncode=0,
                    stdout="192.0.2.1 ssh-ed25519 not-a-real-host-key\n",
                    stderr="",
                )
            raise AssertionError("Unexpected subprocess command: {0}".format(command))

        with mock.patch.object(ssh_bridge_module, "DEFAULT_PROJECT_CONFIG_PATH", project_config_path):
            with mock.patch.object(ssh_bridge_module, "DEFAULT_PROJECT_KEYS_BASE_DIR", expected_keys_base_dir):
                with mock.patch.object(ssh_bridge_module, "DEFAULT_PROJECT_CONTROL_PATH_DIR", expected_control_path_dir):
                    with mock.patch("external_mcp_server.ssh_bridge.subprocess.run", side_effect=fake_run):
                        bridge = SSHBridge(project_config_path, start_renew_thread=False)

        self.assertEqual(bridge.ssh_defaults["keys_base_dir"], expected_keys_base_dir)
        self.assertEqual(bridge.ssh_defaults["known_hosts_file"], os.path.join(expected_keys_base_dir, "known_hosts"))
        self.assertEqual(bridge.ssh_defaults["control_path_dir"], expected_control_path_dir)
        self.assertTrue(bridge.devices["device-a"]["identity_file"].startswith(expected_keys_base_dir))
        self.assertEqual([command[0] for command in calls], ["ssh-keygen", "ssh-keyscan"])


class OpenSSHBootstrapClientTest(unittest.TestCase):
    def test_windows_askpass_script_uses_cmd_wrapper(self):
        client = _OpenSSHBootstrapClient()
        temp_dir = tempfile.mkdtemp(prefix="mcp-askpass-test-")

        try:
            with mock.patch("external_mcp_server.ssh_bridge._is_windows", return_value=True):
                askpass_path = client._create_askpass_script(temp_dir)
                env = client._build_askpass_env(askpass_path, "secret")
            with open(askpass_path, "r") as handle:
                contents = handle.read()
        finally:
            shutil.rmtree(temp_dir)

        self.assertTrue(askpass_path.endswith(".cmd"))
        self.assertEqual(env["SSH_ASKPASS"], askpass_path)
        self.assertEqual(env["MCP_BOOTSTRAP_PASSWORD"], "secret")
        self.assertNotIn("DISPLAY", env)

        self.assertIn("@echo off", contents)
        self.assertIn("powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass", contents)
        self.assertIn("MCP_BOOTSTRAP_PASSWORD", contents)

    def test_windows_bootstrap_uses_askpass_and_sends_command_over_stdin(self):
        client = _OpenSSHBootstrapClient(ssh_bin="ssh")
        profile = {
            "user": "adm",
            "pass": "secret",
            "device_ip": "192.0.2.1",
            "port": 22,
        }
        captured = {}

        class FakeProcess(object):
            def __init__(self, command, env):
                self.command = list(command)
                self.env = dict(env)
                self.returncode = 0

            def communicate(self, input=None, timeout=None):
                captured["input"] = input
                captured["timeout"] = timeout
                return (
                    b'{"status": 200, "command": "mcp key ensure ssh-ed25519 AAAATEST"}\n',
                    b"",
                )

        def fake_popen(command, stdin=None, stdout=None, stderr=None, env=None, start_new_session=None):
            captured["stdin"] = stdin
            captured["stdout"] = stdout
            captured["stderr"] = stderr
            captured["env"] = dict(env)
            captured["start_new_session"] = start_new_session
            return FakeProcess(command, env)

        with mock.patch("external_mcp_server.ssh_bridge._is_windows", return_value=True):
            with mock.patch("external_mcp_server.ssh_bridge.subprocess.Popen", side_effect=fake_popen):
                result = client.run(
                    profile,
                    "mcp key ensure ssh-ed25519 AAAATEST",
                    10,
                    5,
                    os.path.join(tempfile.gettempdir(), "known_hosts"),
                )

        self.assertEqual(result["exit_code"], 0)
        self.assertIn(b'"command": "mcp key ensure ssh-ed25519 AAAATEST"', result["stdout"])
        self.assertEqual(captured["input"], b"mcp key ensure ssh-ed25519 AAAATEST\n")
        self.assertEqual(captured["timeout"], 5)
        self.assertTrue(captured["start_new_session"])
        self.assertEqual(captured["env"]["MCP_BOOTSTRAP_PASSWORD"], "secret")
        self.assertEqual(captured["env"]["SSH_ASKPASS_REQUIRE"], "force")
        self.assertTrue(captured["env"]["SSH_ASKPASS"].endswith("askpass.cmd"))


class SSHStdioSessionTest(unittest.TestCase):
    def test_execute_reads_line_oriented_stdout_and_stderr(self):
        session = _SSHStdioSession(
            [
                sys.executable,
                "-c",
                (
                    "import sys; "
                    "line = sys.stdin.buffer.readline(); "
                    "sys.stderr.write('warn\\n'); "
                    "sys.stderr.flush(); "
                    "sys.stdout.buffer.write(line); "
                    "sys.stdout.buffer.flush()"
                ),
            ]
        )

        try:
            result = session.execute("status basic", 2)
        finally:
            session.close()

        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout"], b"status basic")
        self.assertEqual(result["stderr"], b"warn\n")
        self.assertFalse(result["timed_out"])

    def test_execute_times_out_without_selecting_on_pipes(self):
        session = _SSHStdioSession(
            [
                sys.executable,
                "-c",
                (
                    "import sys, time; "
                    "sys.stdin.buffer.readline(); "
                    "time.sleep(1.0); "
                    "sys.stdout.write('late\\n'); "
                    "sys.stdout.flush()"
                ),
            ]
        )

        try:
            result = session.execute("status basic", 0.2)
        finally:
            session.close()

        self.assertTrue(result["timed_out"])
        self.assertIsNone(result["stdout"])
