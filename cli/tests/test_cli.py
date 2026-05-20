from __future__ import print_function

import io
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from unittest import mock

import cli.cli as cli_module
from cli.cli import (
    DEFAULT_UPGRADE_TIMEOUT_SEC,
    LOCAL_API_REMOTE_ADDR,
    RouterCli,
    _HTTPAPIError,
    _RouterCliSessionManager,
    _upload_filename,
    _windows_drive_path_to_posix_mount,
)
from cli.command_surface import CommandSurface


class FakeBridge(object):
    def __init__(self, config_path=None, responder=None):
        self.ssh_bin = "ssh"
        self.devices = {
            "lab-a": {
                "host": "192.0.2.10",
                "user": "agent",
                "identity_file": "/tmp/device_key",
                "bootstrap_user": "adm",
                "bootstrap_password": "secret",
                "port": 22,
            }
        }
        self.ssh_defaults = {
            "known_hosts_file": "/tmp/known_hosts",
            "control_path_dir": "/tmp/ssh-control",
            "control_persist_sec": 300,
            "command_timeout_sec": 30,
                "connect_timeout_sec": 10,
        }
        self._config = {
            "ssh_defaults": dict(self.ssh_defaults),
            "devices": {
                "lab-a": {
                    "host": "192.0.2.10",
                    "user": "agent",
                    "identity_file": "/tmp/device_key",
                    "public_key_file": "/tmp/device_key.pub",
                    "public_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITest agent-cli",
                    "bootstrap_user": "adm",
                    "bootstrap_password": "secret",
                    "port": 22,
                }
            },
        }
        self.config_path = config_path or "/tmp/agent-cli-config.json"
        self.calls = []
        self.responder = responder
        self.closed = False
        self.close_calls = 0
        self.bound_devices = []

    def has_device(self, device_id):
        return device_id in self.devices

    def get_device_ids(self):
        return ["lab-a"]

    def get_default_device_id(self):
        return "lab-a"

    def _ensure_binding(self, device_id):
        self.bound_devices.append(device_id)

    def execute(self, device_id, command=None, timeout_sec=None, **kwargs):
        del kwargs
        call = {
            "device_id": device_id,
            "command": command,
            "timeout_sec": timeout_sec,
        }
        self.calls.append(call)
        if self.responder is not None:
            response = self.responder(call)
            if response is not None:
                return response
        return {
            "device_id": device_id,
            "command": command,
            "ok": True,
            "ssh_exit_code": 0,
            "response": {"result": {"status": "ok"}},
            "stderr": None,
            "error": None,
        }

    def close(self):
        self.closed = True
        self.close_calls += 1


class FakeAuthBridge(object):
    def __init__(self):
        self.bound_devices = []
        self.closed = False

    def _ensure_binding(self, device_id):
        self.bound_devices.append(device_id)

    def close(self):
        self.closed = True


class FakeTunnel(object):
    def __init__(self):
        self.entered = False
        self.exited = False

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        self.exited = True
        return False


class FakeHTTPResponse(object):
    def __init__(self, status, payload):
        self.status = status
        if isinstance(payload, bytes):
            self._payload = payload
        elif isinstance(payload, str):
            self._payload = payload.encode("utf-8")
        elif payload is None:
            self._payload = b""
        else:
            self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload


class FakeHTTPConnection(object):
    def __init__(self, responses=None, send_error_on_call=None, send_error=None):
        self.responses = list(responses or [FakeHTTPResponse(200, {"result": "ok"})])
        self.send_error_on_call = send_error_on_call
        self.send_error = send_error or OSError("stream write failed")
        self.putrequest_calls = []
        self.putheaders = []
        self.request_calls = []
        self.sent_payloads = []
        self.closed = False
        self.endheaders_called = False
        self._send_calls = 0

    def putrequest(self, method, path, skip_host=False, skip_accept_encoding=False):
        self.putrequest_calls.append(
            {
                "method": method,
                "path": path,
                "skip_host": skip_host,
                "skip_accept_encoding": skip_accept_encoding,
            }
        )

    def putheader(self, name, value):
        self.putheaders.append((name, value))

    def endheaders(self):
        self.endheaders_called = True

    def send(self, payload):
        if self.send_error_on_call is not None and self._send_calls == self.send_error_on_call:
            raise self.send_error
        self.sent_payloads.append(payload)
        self._send_calls += 1

    def request(self, method, path, body=None, headers=None):
        self.request_calls.append(
            {
                "method": method,
                "path": path,
                "body": body,
                "headers": headers,
            }
        )

    def getresponse(self):
        if not self.responses:
            raise AssertionError("No fake HTTP responses remaining")
        return self.responses.pop(0)

    def close(self):
        self.closed = True


class FakeHTTPTunnel(object):
    def __init__(self, connection):
        self.connection = connection
        self.opened_timeouts = []

    def open_http_connection(self, timeout_sec):
        self.opened_timeouts.append(timeout_sec)
        return self.connection


class RouterCliTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="agent-cli-test-")
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()
        self.app = RouterCli(stdout=self.stdout, stderr=self.stderr)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_auth_writes_config_file(self):
        fake_bridge = FakeAuthBridge()

        with mock.patch("cli.cli.SSHBridge.from_config_data", return_value=fake_bridge):
            exit_code = self.app.run(
                [
                    "--runtime-dir",
                    self.temp_dir,
                    "auth",
                    "--host",
                    "192.0.2.10",
                    "--pass",
                    "secret",
                    "--name",
                    "lab-a",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(fake_bridge.bound_devices, ["lab-a"])
        self.assertTrue(fake_bridge.closed)

        config_path = os.path.join(self.temp_dir, "config.json")
        with open(config_path, "r") as handle:
            payload = json.load(handle)
        self.assertEqual(payload["devices"]["lab-a"]["host"], "192.0.2.10")
        self.assertEqual(payload["devices"]["lab-a"]["bootstrap_password"], "secret")
        self.assertEqual(
            payload["ssh_defaults"]["keys_base_dir"],
            os.path.join(self.temp_dir, "keys"),
        )

        result = json.loads(self.stdout.getvalue())
        self.assertTrue(result["ok"])
        self.assertEqual(result["device_id"], "lab-a")

    def test_auth_prompts_for_missing_values(self):
        fake_bridge = FakeAuthBridge()
        password_prompts = []
        app = RouterCli(
            stdout=self.stdout,
            stderr=self.stderr,
            stdin=io.StringIO("192.0.2.10\n\n\n"),
            password_reader=lambda prompt: password_prompts.append(prompt) or "secret",
        )

        with mock.patch("cli.cli.SSHBridge.from_config_data", return_value=fake_bridge):
            exit_code = app.run(
                [
                    "--runtime-dir",
                    self.temp_dir,
                    "auth",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(fake_bridge.bound_devices, ["192.0.2.10"])
        self.assertTrue(fake_bridge.closed)
        self.assertEqual(password_prompts, ["Password: "])

        config_path = os.path.join(self.temp_dir, "config.json")
        with open(config_path, "r") as handle:
            payload = json.load(handle)

        self.assertEqual(payload["devices"]["192.0.2.10"]["host"], "192.0.2.10")
        self.assertEqual(payload["devices"]["192.0.2.10"]["port"], 22)
        self.assertEqual(payload["devices"]["192.0.2.10"]["bootstrap_user"], "adm")
        self.assertEqual(payload["devices"]["192.0.2.10"]["bootstrap_password"], "secret")
        self.assertIn("Host: ", self.stderr.getvalue())
        self.assertIn("Port [22]: ", self.stderr.getvalue())
        self.assertIn("Bootstrap user [adm]: ", self.stderr.getvalue())

        result = json.loads(self.stdout.getvalue())
        self.assertTrue(result["ok"])
        self.assertEqual(result["device_id"], "192.0.2.10")

    def test_auth_only_prompts_for_missing_values(self):
        fake_bridge = FakeAuthBridge()
        password_prompts = []
        app = RouterCli(
            stdout=self.stdout,
            stderr=self.stderr,
            stdin=io.StringIO("\n"),
            password_reader=lambda prompt: password_prompts.append(prompt) or "secret",
        )

        with mock.patch("cli.cli.SSHBridge.from_config_data", return_value=fake_bridge):
            exit_code = app.run(
                [
                    "--runtime-dir",
                    self.temp_dir,
                    "auth",
                    "--host",
                    "192.0.2.10",
                    "--user",
                    "adm2",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(fake_bridge.bound_devices, ["192.0.2.10"])
        self.assertEqual(password_prompts, ["Password: "])
        self.assertNotIn("Host: ", self.stderr.getvalue())
        self.assertNotIn("Port [22]: ", self.stderr.getvalue())
        self.assertNotIn("Bootstrap user [adm]: ", self.stderr.getvalue())

        config_path = os.path.join(self.temp_dir, "config.json")
        with open(config_path, "r") as handle:
            payload = json.load(handle)

        self.assertEqual(payload["devices"]["192.0.2.10"]["bootstrap_user"], "adm2")
        self.assertEqual(payload["devices"]["192.0.2.10"]["port"], 22)
        self.assertEqual(payload["devices"]["192.0.2.10"]["bootstrap_password"], "secret")

    def test_general_help_includes_default_behaviors_and_topics(self):
        exit_code = self.app.run(["help"])

        self.assertEqual(exit_code, 0)
        output = self.stdout.getvalue()
        self.assertIn("status [<key>|list]", output)
        self.assertIn("tool <subcommand>", output)
        self.assertIn("`pass=` is supported for compatibility but not recommended", output)
        self.assertIn("Topics:", output)
        self.assertIn("auth, status, config, log, schema, tool, upgrade, reboot", output)
        self.assertNotIn("__sessiond", output)

    def test_dash_h_uses_same_output_as_help_command(self):
        help_stdout = io.StringIO()
        dash_h_stdout = io.StringIO()
        help_app = RouterCli(stdout=help_stdout, stderr=io.StringIO())
        dash_h_app = RouterCli(stdout=dash_h_stdout, stderr=io.StringIO())

        help_exit = help_app.run(["help"])
        dash_h_exit = dash_h_app.run(["-h"])

        self.assertEqual(help_exit, 0)
        self.assertEqual(dash_h_exit, 0)
        self.assertEqual(dash_h_stdout.getvalue(), help_stdout.getvalue())

    def test_dash_dash_help_uses_same_output_as_help_command(self):
        help_stdout = io.StringIO()
        long_help_stdout = io.StringIO()
        help_app = RouterCli(stdout=help_stdout, stderr=io.StringIO())
        long_help_app = RouterCli(stdout=long_help_stdout, stderr=io.StringIO())

        help_exit = help_app.run(["help"])
        long_help_exit = long_help_app.run(["--help"])

        self.assertEqual(help_exit, 0)
        self.assertEqual(long_help_exit, 0)
        self.assertEqual(long_help_stdout.getvalue(), help_stdout.getvalue())

    def test_subcommand_dash_h_uses_same_output_as_help_topic(self):
        topic_stdout = io.StringIO()
        dash_h_stdout = io.StringIO()
        topic_app = RouterCli(stdout=topic_stdout, stderr=io.StringIO())
        dash_h_app = RouterCli(stdout=dash_h_stdout, stderr=io.StringIO())

        topic_exit = topic_app.run(["help", "tool"])
        dash_h_exit = dash_h_app.run(["tool", "-h"])

        self.assertEqual(topic_exit, 0)
        self.assertEqual(dash_h_exit, 0)
        self.assertEqual(dash_h_stdout.getvalue(), topic_stdout.getvalue())

    def test_help_topic_dash_h_uses_same_output_as_help_topic(self):
        topic_stdout = io.StringIO()
        dash_h_stdout = io.StringIO()
        topic_app = RouterCli(stdout=topic_stdout, stderr=io.StringIO())
        dash_h_app = RouterCli(stdout=dash_h_stdout, stderr=io.StringIO())

        topic_exit = topic_app.run(["help", "status"])
        dash_h_exit = dash_h_app.run(["help", "status", "--help"])

        self.assertEqual(topic_exit, 0)
        self.assertEqual(dash_h_exit, 0)
        self.assertEqual(dash_h_stdout.getvalue(), topic_stdout.getvalue())

    def test_status_help_describes_aggregate_default(self):
        exit_code = self.app.run(["help", "status"])

        self.assertEqual(exit_code, 0)
        output = self.stdout.getvalue()
        self.assertIn("Usage:", output)
        self.assertIn("No subcommand reads the aggregated status view", output)
        self.assertIn("agent-cli status basic", output)
        self.assertIn("agent-cli status cellular", output)

    def test_config_help_describes_root_only_set_behavior(self):
        exit_code = self.app.run(["help", "config"])

        self.assertEqual(exit_code, 0)
        output = self.stdout.getvalue()
        self.assertIn("`config get <key>` accepts a query key such as `system.hostname`", output)
        self.assertIn("`config set <root> <json_payload>` only accepts a root key such as `system`", output)
        self.assertIn("agent-cli config set system {\"hostname\":\"lab-a\"}", output)

    def test_log_help_describes_default_message_log(self):
        exit_code = self.app.run(["help", "log"])

        self.assertEqual(exit_code, 0)
        output = self.stdout.getvalue()
        self.assertIn("With no service, `log` reads the default `message` log.", output)
        self.assertIn("agent-cli log --line 200", output)
        self.assertIn("agent-cli log NetworkManager --line 100", output)

    def test_schema_help_describes_root_only_validation(self):
        exit_code = self.app.run(["help", "schema"])

        self.assertEqual(exit_code, 0)
        output = self.stdout.getvalue()
        self.assertIn("schema <root> --validation", output)
        self.assertIn("nested paths such as `system.hostname` are not supported", output)
        self.assertIn("agent-cli schema system --validation", output)

    def test_tool_help_lists_known_tools_and_examples(self):
        exit_code = self.app.run(["help", "tool"])

        self.assertEqual(exit_code, 0)
        output = self.stdout.getvalue()
        self.assertIn("Current known tools are `ping`, `traceroute`, `tcpdump`, `iperf`, and `speedtest`.", output)
        self.assertIn("agent-cli tool traceroute {\"action\":\"start\",\"host\":\"8.8.8.8\"}", output)
        self.assertIn(
            "agent-cli tool tcpdump {\"action\":\"start\",\"capture_mode\":\"show\",\"capture_time\":300,\"local_iface\":[{\"interface\":\"wan1\",\"expert_options\":\"\"}]}",
            output,
        )
        self.assertIn("agent-cli tool iperf {\"action\":\"start\",\"role\":\"client\",\"command\":\"198.51.100.10\",\"capture_time\":10}", output)
        self.assertIn("agent-cli tool speedtest {\"action\":\"output\",\"start_line\":0}", output)

    def test_upgrade_help_describes_url_and_file_modes(self):
        exit_code = self.app.run(["help", "upgrade"])

        self.assertEqual(exit_code, 0)
        output = self.stdout.getvalue()
        self.assertIn("`--url` forwards a device-side firmware download URL", output)
        self.assertIn("`--file` is the agent-cli special case", output)
        self.assertIn(r"agent-cli upgrade --file C:\firmware\fw.bin", output)

    def test_status_help_appends_dynamic_list_without_losing_static_help(self):
        fake_bridge = FakeBridge()
        public_outcome = {
            "ok": True,
            "device_id": "lab-a",
            "command": "status list",
            "data": {
                "result": {
                    "status_keys": [
                        {"key": "basic", "description": "System basic info"},
                        {"key": "cellular", "description": "Cellular interface status"},
                    ]
                }
            },
            "stderr": None,
            "error": None,
        }

        with mock.patch.object(self.app, "_open_bridge", return_value=fake_bridge):
            with mock.patch.object(self.app, "_execute_validated_via_session", return_value=public_outcome):
                exit_code = self.app.run(["help", "status"])

        self.assertEqual(exit_code, 0)
        output = self.stdout.getvalue()
        self.assertIn("No subcommand reads the aggregated status view", output)
        self.assertIn("Available status:", output)
        self.assertIn("basic: System basic info", output)
        self.assertIn("cellular: Cellular interface status", output)

    def test_status_command_uses_bridge_and_emits_public_outcome(self):
        fake_bridge = FakeBridge()
        public_outcome = {
            "ok": True,
            "device_id": "lab-a",
            "command": "status basic",
            "data": {"result": {"status": "ok"}},
            "stderr": None,
            "error": None,
        }

        with mock.patch.object(self.app, "_open_bridge", return_value=fake_bridge):
            with mock.patch.object(self.app, "_execute_validated_via_session", return_value=public_outcome) as session_mock:
                exit_code = self.app.run(["status", "basic"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(fake_bridge.calls, [])
        self.assertTrue(fake_bridge.closed)
        validated = session_mock.call_args[0][2]
        self.assertEqual(validated["command"], "status basic")

        result = json.loads(self.stdout.getvalue())
        self.assertTrue(result["ok"])
        self.assertEqual(result["device_id"], "lab-a")
        self.assertEqual(result["data"]["result"]["status"], "ok")

    def test_execute_validated_via_session_reuses_manager_and_cleans_up_after_idle(self):
        validation_bridge = FakeBridge(config_path=os.path.join(self.temp_dir, "config.json"))
        options = mock.Mock(runtime_dir=self.temp_dir, takeover=False)
        validated = {
            "device_id": "lab-a",
            "command": "status basic",
        }
        manager_bridges = []
        manager_threads = []

        def fake_start(paths, session_request):
            del session_request
            manager_bridge = FakeBridge(config_path=os.path.join(self.temp_dir, "manager-config.json"))
            manager = _RouterCliSessionManager(
                self.app,
                manager_bridge,
                paths.state_file,
                idle_timeout_sec=1,
            )
            thread = threading.Thread(target=manager.serve, daemon=True)
            manager_bridges.append(manager_bridge)
            manager_threads.append(thread)
            thread.start()

        with mock.patch.object(self.app, "_start_session_manager", side_effect=fake_start):
            first = self.app._execute_validated_via_session(options, validation_bridge, validated)
            second = self.app._execute_validated_via_session(options, validation_bridge, validated)

        self.assertEqual(len(manager_bridges), 1)
        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])
        self.assertEqual(validation_bridge.calls, [])
        self.assertEqual(len(manager_bridges[0].calls), 2)

        paths = self.app._build_session_paths(
            self.temp_dir,
            validation_bridge._config,
            "lab-a",
        )
        deadline = time.time() + 3
        while time.time() < deadline and not manager_bridges[0].closed:
            time.sleep(0.05)

        manager_threads[0].join(timeout=1)
        self.assertTrue(manager_bridges[0].closed)
        self.assertFalse(os.path.exists(paths.state_file))

    def test_start_session_manager_resets_pyinstaller_environment(self):
        paths = self.app._build_session_paths(
            self.temp_dir,
            {"ssh_defaults": {}, "devices": {"lab-a": {}}},
            "lab-a",
        )

        with mock.patch.object(self.app, "_build_session_manager_command", return_value=["agent-cli.exe", "__sessiond"]):
            with mock.patch("cli.cli.subprocess.Popen") as popen_mock:
                with mock.patch.object(cli_module.sys, "frozen", True, create=True):
                    self.app._start_session_manager(paths, {"runtime_dir": self.temp_dir})

        popen_kwargs = popen_mock.call_args.kwargs
        self.assertEqual(popen_kwargs["env"]["PYINSTALLER_RESET_ENVIRONMENT"], "1")

    def test_start_session_manager_hides_console_window_on_windows(self):
        paths = self.app._build_session_paths(
            self.temp_dir,
            {"ssh_defaults": {}, "devices": {"lab-a": {}}},
            "lab-a",
        )
        fake_startupinfo = mock.Mock(dwFlags=0, wShowWindow=1)

        with mock.patch.object(self.app, "_build_session_manager_command", return_value=["agent-cli.exe", "__sessiond"]):
            with mock.patch("cli.cli.subprocess.Popen") as popen_mock:
                with mock.patch.object(cli_module.os, "name", "nt"):
                    with mock.patch.object(cli_module.subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200, create=True):
                        with mock.patch.object(cli_module.subprocess, "CREATE_NO_WINDOW", 0x08000000, create=True):
                            with mock.patch.object(cli_module.subprocess, "STARTF_USESHOWWINDOW", 0x1, create=True):
                                with mock.patch.object(cli_module.subprocess, "SW_HIDE", 0, create=True):
                                    with mock.patch.object(cli_module.subprocess, "STARTUPINFO", return_value=fake_startupinfo, create=True):
                                        self.app._start_session_manager(paths, {"runtime_dir": self.temp_dir})

        popen_kwargs = popen_mock.call_args.kwargs
        self.assertNotIn("start_new_session", popen_kwargs)
        self.assertEqual(
            popen_kwargs["creationflags"],
            0x200 | 0x08000000,
        )
        self.assertIs(popen_kwargs["startupinfo"], fake_startupinfo)
        self.assertEqual(fake_startupinfo.dwFlags, 0x1)
        self.assertEqual(fake_startupinfo.wShowWindow, 0)

    def test_upgrade_file_uploads_then_triggers_remote_upgrade(self):
        fake_bridge = FakeBridge()
        fake_tunnel = FakeTunnel()
        firmware_path = os.path.join(self.temp_dir, "fw.bin")
        with open(firmware_path, "wb") as handle:
            handle.write(b"firmware")

        with mock.patch.object(self.app, "_open_bridge", return_value=fake_bridge):
            with mock.patch.object(
                self.app,
                "_execute_validated_via_session",
                side_effect=lambda options, bridge, validated: self.app._execute_validated_public_call(bridge, validated),
            ):
                with mock.patch.object(self.app, "_open_api_tunnel", return_value=fake_tunnel) as tunnel_mock:
                    with mock.patch.object(self.app, "_api_login", return_value="token-123") as login_mock:
                        with mock.patch.object(self.app, "_api_upload_firmware", return_value={"result": "ok"}) as upload_mock:
                            with mock.patch.object(self.app, "_api_trigger_upgrade", return_value={"result": "ok"}) as upgrade_mock:
                                exit_code = self.app.run(["upgrade", "--file", firmware_path])

        self.assertEqual(exit_code, 0)
        self.assertEqual(fake_bridge.bound_devices, ["lab-a"])
        self.assertEqual(fake_bridge.calls, [])
        self.assertTrue(fake_tunnel.entered)
        self.assertTrue(fake_tunnel.exited)

        tunnel_mock.assert_called_once_with(fake_bridge, "lab-a", DEFAULT_UPGRADE_TIMEOUT_SEC)
        login_mock.assert_called_once_with(fake_tunnel, "192.0.2.10", "adm", "secret", DEFAULT_UPGRADE_TIMEOUT_SEC)
        upload_mock.assert_called_once_with(
            fake_tunnel,
            "192.0.2.10",
            "token-123",
            firmware_path,
            DEFAULT_UPGRADE_TIMEOUT_SEC,
        )
        upgrade_mock.assert_called_once_with(fake_tunnel, "192.0.2.10", "token-123", DEFAULT_UPGRADE_TIMEOUT_SEC)

        result = json.loads(self.stdout.getvalue())
        self.assertTrue(result["ok"])
        self.assertEqual(result["command"], "upgrade --file {0}".format(firmware_path))
        self.assertEqual(result["data"]["result"], "ok")

    def test_upgrade_url_uses_upgrade_default_timeout(self):
        fake_bridge = FakeBridge()

        with mock.patch.object(self.app, "_open_bridge", return_value=fake_bridge):
            with mock.patch.object(
                self.app,
                "_execute_validated_via_session",
                side_effect=lambda options, bridge, validated: self.app._execute_validated_public_call(bridge, validated),
            ):
                exit_code = self.app.run(["upgrade", "--url", "https://example/fw.bin"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(fake_bridge.calls[0]["command"], "upgrade --url https://example/fw.bin")
        self.assertEqual(fake_bridge.calls[0]["timeout_sec"], DEFAULT_UPGRADE_TIMEOUT_SEC)

    def test_upgrade_timeout_accepts_values_up_to_1800(self):
        fake_bridge = FakeBridge()

        with mock.patch.object(self.app, "_open_bridge", return_value=fake_bridge):
            with mock.patch.object(
                self.app,
                "_execute_validated_via_session",
                side_effect=lambda options, bridge, validated: self.app._execute_validated_public_call(bridge, validated),
            ):
                exit_code = self.app.run(["--timeout-sec", "1800", "upgrade", "--url", "https://example/fw.bin"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(fake_bridge.calls[0]["timeout_sec"], 1800)

    def test_upgrade_timeout_rejects_values_above_1800(self):
        fake_bridge = FakeBridge()

        with mock.patch.object(self.app, "_open_bridge", return_value=fake_bridge):
            exit_code = self.app.run(["--timeout-sec", "1801", "upgrade", "--url", "https://example/fw.bin"])

        self.assertEqual(exit_code, 4)
        self.assertIn("timeout_sec must be an integer between 1 and 1800", self.stderr.getvalue())

    def test_upgrade_file_stops_when_login_fails(self):
        fake_bridge = FakeBridge()
        fake_tunnel = FakeTunnel()
        firmware_path = os.path.join(self.temp_dir, "fw.bin")
        with open(firmware_path, "wb") as handle:
            handle.write(b"firmware")

        with mock.patch.object(self.app, "_open_bridge", return_value=fake_bridge):
            with mock.patch.object(
                self.app,
                "_execute_validated_via_session",
                side_effect=lambda options, bridge, validated: self.app._execute_validated_public_call(bridge, validated),
            ):
                with mock.patch.object(self.app, "_open_api_tunnel", return_value=fake_tunnel):
                    with mock.patch.object(
                        self.app,
                        "_api_login",
                        side_effect=_HTTPAPIError("unauthorized", "http_login_failed", "bad password"),
                    ):
                        with mock.patch.object(self.app, "_api_upload_firmware") as upload_mock:
                            with mock.patch.object(self.app, "_api_trigger_upgrade") as upgrade_mock:
                                exit_code = self.app.run(["upgrade", "--file", firmware_path])

        self.assertEqual(exit_code, 1)
        upload_mock.assert_not_called()
        upgrade_mock.assert_not_called()
        result = json.loads(self.stdout.getvalue())
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["kind"], "http_login_failed")

    def test_upgrade_file_uses_translated_local_path_when_original_path_is_missing(self):
        fake_bridge = FakeBridge()
        fake_tunnel = FakeTunnel()
        firmware_path = os.path.join(self.temp_dir, "fw.bin")
        with open(firmware_path, "wb") as handle:
            handle.write(b"firmware")

        with mock.patch.object(self.app, "_resolve_local_upgrade_path", return_value=("/missing/fw.bin", firmware_path)):
            with mock.patch.object(self.app, "_open_bridge", return_value=fake_bridge):
                with mock.patch.object(
                    self.app,
                    "_execute_validated_via_session",
                    side_effect=lambda options, bridge, validated: self.app._execute_validated_public_call(bridge, validated),
                ):
                    with mock.patch.object(self.app, "_open_api_tunnel", return_value=fake_tunnel):
                        with mock.patch.object(self.app, "_api_login", return_value="token-123"):
                            with mock.patch.object(self.app, "_api_upload_firmware", return_value={"result": "ok"}) as upload_mock:
                                with mock.patch.object(self.app, "_api_trigger_upgrade", return_value={"result": "ok"}):
                                    exit_code = self.app.run(["upgrade", "--file", "C:\\firmware\\fw.bin"])

        self.assertEqual(exit_code, 0)
        upload_mock.assert_called_once_with(
            fake_tunnel,
            "192.0.2.10",
            "token-123",
            firmware_path,
            DEFAULT_UPGRADE_TIMEOUT_SEC,
        )

    def test_api_upload_firmware_sets_expected_headers(self):
        firmware_path = os.path.join(self.temp_dir, "fw.bin")
        with open(firmware_path, "wb") as handle:
            handle.write(b"firmware")

        connection = FakeHTTPConnection()
        tunnel = FakeHTTPTunnel(connection)
        payload = self.app._api_upload_firmware(
            tunnel,
            "192.0.2.10",
            "token-123",
            firmware_path,
            DEFAULT_UPGRADE_TIMEOUT_SEC,
        )

        self.assertEqual(payload["result"], "ok")
        self.assertEqual(tunnel.opened_timeouts, [DEFAULT_UPGRADE_TIMEOUT_SEC])
        self.assertTrue(connection.endheaders_called)
        self.assertEqual(
            connection.putrequest_calls,
            [
                {
                    "method": "POST",
                    "path": "/api/v1/import/firmware",
                    "skip_host": True,
                    "skip_accept_encoding": True,
                }
            ],
        )
        headers = dict(connection.putheaders)
        self.assertEqual(headers["Host"], "192.0.2.10")
        self.assertEqual(headers["Remote-Addr"], LOCAL_API_REMOTE_ADDR)
        self.assertEqual(headers["Accept"], "*/*")
        self.assertEqual(headers["Authorization"], "Bearer token-123")
        self.assertEqual(headers["Connection"], "keep-alive")
        self.assertEqual(headers["Origin"], "https://192.0.2.10")
        self.assertEqual(headers["Referer"], "https://192.0.2.10/")
        self.assertEqual(headers["X-Requested-With"], "XMLHttpRequest")

    def test_http_json_request_adds_upgrade_api_headers(self):
        connection = FakeHTTPConnection()
        tunnel = FakeHTTPTunnel(connection)

        payload = self.app._http_json_request(
            tunnel,
            "POST",
            "/api/v1/user/login",
            {"Host": "192.0.2.10"},
            {"username": "adm", "password": "secret"},
            DEFAULT_UPGRADE_TIMEOUT_SEC,
        )

        self.assertEqual(payload["result"], "ok")
        self.assertEqual(tunnel.opened_timeouts, [DEFAULT_UPGRADE_TIMEOUT_SEC])
        request_call = connection.request_calls[0]
        self.assertEqual(request_call["method"], "POST")
        self.assertEqual(request_call["path"], "/api/v1/user/login")
        self.assertEqual(request_call["headers"]["Accept"], "*/*")
        self.assertEqual(request_call["headers"]["Connection"], "keep-alive")
        self.assertEqual(request_call["headers"]["Remote-Addr"], LOCAL_API_REMOTE_ADDR)
        self.assertEqual(request_call["headers"]["X-Requested-With"], "XMLHttpRequest")
        self.assertEqual(request_call["headers"]["Origin"], "https://192.0.2.10")
        self.assertEqual(request_call["headers"]["Referer"], "https://192.0.2.10/")

    def test_api_upload_firmware_promotes_early_http_error_response(self):
        firmware_path = os.path.join(self.temp_dir, "fw.bin")
        with open(firmware_path, "wb") as handle:
            handle.write(b"firmware")

        connection = FakeHTTPConnection(
            responses=[FakeHTTPResponse(400, {"error": "bad firmware"})],
            send_error_on_call=1,
        )
        tunnel = FakeHTTPTunnel(connection)

        with self.assertRaises(_HTTPAPIError) as ctx:
            self.app._api_upload_firmware(
                tunnel,
                "192.0.2.10",
                "token-123",
                firmware_path,
                DEFAULT_UPGRADE_TIMEOUT_SEC,
            )

        self.assertEqual(ctx.exception.kind, "http_upload_failed")
        self.assertEqual(ctx.exception.code, "internal")
        self.assertEqual(ctx.exception.message, "bad firmware")

    def test_windows_drive_path_helpers_handle_windows_style_paths(self):
        self.assertEqual(
            _windows_drive_path_to_posix_mount("C:\\firmware\\fw.bin"),
            "/mnt/c/firmware/fw.bin",
        )
        self.assertEqual(_upload_filename("C:\\firmware\\fw.bin"), "fw.bin")


if __name__ == "__main__":
    unittest.main()
