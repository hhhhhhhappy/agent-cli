from __future__ import print_function

import json
import os
import queue
import re
import stat
import subprocess
import tempfile
import threading
import time


DEFAULT_CONNECT_TIMEOUT_SEC = 10
DEFAULT_COMMAND_TIMEOUT_SEC = 60
DEFAULT_CONTROL_PERSIST_SEC = 300
DEFAULT_CONTROL_PATH_DIR_NAME = "ssh-control"
DEFAULT_KNOWN_HOSTS_FILE_NAME = "known_hosts"
DEFAULT_BOOTSTRAP_USER = "adm"
DEFAULT_AGENT_USER = "agent"
DEFAULT_LEASE_TTL_SEC = 300
DEFAULT_LEASE_RENEW_INTERVAL_SEC = 100
DEFAULT_LEASE_RETRY_INTERVAL_SEC = 5
DEFAULT_KEY_TYPE = "ed25519"
DEFAULT_KEY_BITS = 256
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PROJECT_CONFIG_DIR_NAME = "config"
DEFAULT_PROJECT_CONFIG_FILE_NAME = "config.json"
DEFAULT_PROJECT_KEYS_DIR_NAME = "keys"
DEFAULT_PROJECT_CONFIG_PATH = os.path.join(
    MODULE_DIR,
    DEFAULT_PROJECT_CONFIG_DIR_NAME,
    DEFAULT_PROJECT_CONFIG_FILE_NAME,
)
DEFAULT_PROJECT_KEYS_BASE_DIR = os.path.join(MODULE_DIR, DEFAULT_PROJECT_KEYS_DIR_NAME)
DEFAULT_PROJECT_CONTROL_PATH_DIR = os.path.join(
    DEFAULT_PROJECT_KEYS_BASE_DIR,
    DEFAULT_CONTROL_PATH_DIR_NAME,
)
ARGS_UNSET = object()


def _is_windows():
    return os.name == "nt"


class ConfigError(Exception):
    """Raised when the MCP server configuration is invalid."""


class BootstrapError(Exception):
    def __init__(self, kind, message, stderr=None, response=None):
        super(BootstrapError, self).__init__(message)
        self.kind = kind
        self.message = message
        self.stderr = stderr
        self.response = response


class _RunnerSession(object):
    def __init__(self, command, runner):
        self.command = list(command)
        self._runner = runner
        self._closed = False

    def is_alive(self):
        return not self._closed

    def execute(self, remote_command, timeout_sec):
        if self._closed:
            return {
                "exit_code": 255,
                "stdout": b"",
                "stderr": b"SSH session is closed",
                "timed_out": False,
            }
        return self._runner(self.command + [remote_command], timeout_sec)

    def close(self):
        self._closed = True


class _SSHStdioSession(object):
    def __init__(self, command):
        self.command = list(command)
        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        self._event_queue = queue.Queue()
        self._stdout_buffer = b""
        self._stderr_buffer = b""
        self._stdout_eof = False
        self._stderr_eof = False
        self._stdout_thread = threading.Thread(
            target=self._read_stream,
            args=(self.process.stdout, "stdout"),
            daemon=True,
        )
        self._stderr_thread = threading.Thread(
            target=self._read_stream,
            args=(self.process.stderr, "stderr"),
            daemon=True,
        )
        self._stdout_thread.start()
        self._stderr_thread.start()

    def is_alive(self):
        return self.process is not None and self.process.poll() is None

    def execute(self, remote_command, timeout_sec):
        if not self.is_alive():
            return self._result_from_process()

        if not self._write_command(remote_command):
            return self._result_from_process()

        return self._read_response(timeout_sec)

    def close(self):
        process = self.process
        if process is None:
            return

        try:
            if process.stdin is not None:
                process.stdin.close()
        except IOError:
            pass

        if process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=1)
            except (OSError, TypeError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                except OSError:
                    pass
                try:
                    process.wait(timeout=1)
                except (OSError, TypeError, subprocess.TimeoutExpired):
                    pass

        for handle in (process.stdout, process.stderr):
            try:
                if handle is not None:
                    handle.close()
            except IOError:
                pass

        for thread in (self._stdout_thread, self._stderr_thread):
            if thread is not None and thread.is_alive():
                thread.join(timeout=0.2)

        self.process = None

    def _write_command(self, remote_command):
        payload = (remote_command + "\n").encode("utf-8")

        try:
            self.process.stdin.write(payload)
            self.process.stdin.flush()
            return True
        except (AttributeError, IOError, OSError):
            return False

    def _read_response(self, timeout_sec):
        deadline = time.monotonic() + timeout_sec

        while True:
            self._drain_pending_events()
            stdout_line = self._pop_stdout_line()
            if stdout_line is not None:
                self._collect_events_for(0.05)
                return {
                    "exit_code": 0,
                    "stdout": stdout_line,
                    "stderr": self._take_stderr(),
                    "timed_out": False,
                }

            if self.process.poll() is not None:
                self._wait_for_readers(0.2)
                self._drain_pending_events()
                stdout_line = self._pop_stdout_line()
                if stdout_line is not None:
                    return {
                        "exit_code": self.process.returncode,
                        "stdout": stdout_line,
                        "stderr": self._take_stderr(),
                        "timed_out": False,
                    }
                return {
                    "exit_code": self.process.returncode,
                    "stdout": self._take_stdout(),
                    "stderr": self._take_stderr(),
                    "timed_out": False,
                }

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return {
                    "exit_code": None,
                    "stdout": None,
                    "stderr": self._take_stderr(),
                    "timed_out": True,
                }

            try:
                event = self._event_queue.get(timeout=remaining)
            except queue.Empty:
                return {
                    "exit_code": None,
                    "stdout": None,
                    "stderr": self._take_stderr(),
                    "timed_out": True,
                }

            self._handle_stream_event(event)

    def _read_stream(self, handle, stream_name):
        reader = getattr(handle, "read1", None)
        if reader is None:
            reader = handle.read

        while True:
            try:
                chunk = reader(4096)
            except (AttributeError, IOError, OSError, ValueError):
                chunk = b""

            if not chunk:
                self._event_queue.put((stream_name, None))
                return

            self._event_queue.put((stream_name, chunk))

    def _wait_for_readers(self, timeout_sec):
        deadline = time.monotonic() + timeout_sec
        for thread in (self._stdout_thread, self._stderr_thread):
            if thread is None or not thread.is_alive():
                continue
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            thread.join(remaining)

    def _collect_events_for(self, timeout_sec):
        deadline = time.monotonic() + timeout_sec
        self._drain_pending_events()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            try:
                event = self._event_queue.get(timeout=remaining)
            except queue.Empty:
                return
            self._handle_stream_event(event)

    def _drain_pending_events(self):
        while True:
            try:
                event = self._event_queue.get_nowait()
            except queue.Empty:
                return
            self._handle_stream_event(event)

    def _handle_stream_event(self, event):
        stream_name, chunk = event
        if chunk is None:
            if stream_name == "stdout":
                self._stdout_eof = True
            elif stream_name == "stderr":
                self._stderr_eof = True
            return

        if stream_name == "stdout":
            self._stdout_buffer += chunk
        elif stream_name == "stderr":
            self._stderr_buffer += chunk

    def _pop_stdout_line(self):
        newline_index = self._stdout_buffer.find(b"\n")
        if newline_index < 0:
            return None

        line = self._stdout_buffer[:newline_index]
        self._stdout_buffer = self._stdout_buffer[newline_index + 1 :]
        if line.endswith(b"\r"):
            line = line[:-1]
        return line

    def _take_stdout(self):
        payload = self._stdout_buffer
        self._stdout_buffer = b""
        return payload

    def _take_stderr(self):
        payload = self._stderr_buffer
        self._stderr_buffer = b""
        return payload

    def _result_from_process(self):
        stderr_data = self._take_stderr()
        stdout_data = self._take_stdout()

        if self.process is None:
            return {
                "exit_code": 255,
                "stdout": stdout_data,
                "stderr": stderr_data or b"SSH session is closed",
                "timed_out": False,
            }

        self._wait_for_readers(0.2)
        self._drain_pending_events()
        stdout_data += self._take_stdout()
        stderr_data += self._take_stderr()
        exit_code = self.process.poll()
        if exit_code is None:
            exit_code = 255
        return {
            "exit_code": exit_code,
            "stdout": stdout_data,
            "stderr": stderr_data,
            "timed_out": False,
        }


class _OpenSSHBootstrapClient(object):
    def __init__(self, ssh_bin="ssh"):
        self.ssh_bin = ssh_bin

    def _create_askpass_script(self, temp_dir):
        if _is_windows():
            askpass_path = os.path.join(temp_dir, "askpass.cmd")
            with open(askpass_path, "w") as handle:
                handle.write("@echo off\r\n")
                handle.write(
                    "powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass "
                    "-Command \"[Console]::Out.WriteLine($env:MCP_BOOTSTRAP_PASSWORD)\"\r\n"
                )
            return askpass_path

        askpass_path = os.path.join(temp_dir, "askpass.sh")
        with open(askpass_path, "w") as handle:
            handle.write("#!/bin/sh\n")
            handle.write('printf "%s\\n" "$MCP_BOOTSTRAP_PASSWORD"\n')
        os.chmod(askpass_path, 0o700)
        return askpass_path

    def _build_askpass_env(self, askpass_path, password):
        env = os.environ.copy()
        env.update(
            {
                "SSH_ASKPASS": askpass_path,
                "SSH_ASKPASS_REQUIRE": "force",
                "MCP_BOOTSTRAP_PASSWORD": password,
            }
        )
        if _is_windows():
            env.pop("DISPLAY", None)
        else:
            env["DISPLAY"] = env.get("DISPLAY", ":0")
        return env

    def _run_askpass_bootstrap(self, ssh_command, password, command, command_timeout_sec):
        with tempfile.TemporaryDirectory(prefix="mcp-bootstrap-") as temp_dir:
            askpass_path = self._create_askpass_script(temp_dir)
            env = self._build_askpass_env(askpass_path, password)

            process = None
            try:
                process = subprocess.Popen(
                    ssh_command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    start_new_session=True,
                )
                stdout_data, stderr_data = process.communicate(
                    input=(command + "\n").encode("utf-8"),
                    timeout=command_timeout_sec,
                )
            except subprocess.TimeoutExpired as exc:
                if process is not None:
                    try:
                        process.kill()
                    except OSError:
                        pass
                    try:
                        process.communicate()
                    except (OSError, subprocess.SubprocessError):
                        pass
                raise OSError(str(exc) or "Unable to start bootstrap SSH transport")
            except OSError as exc:
                if process is not None:
                    try:
                        process.kill()
                    except OSError:
                        pass
                raise OSError(str(exc) or "Unable to start bootstrap SSH transport")

        return {
            "exit_code": process.returncode,
            "stdout": stdout_data,
            "stderr": stderr_data,
        }

    def run(self, profile, command, connect_timeout_sec, command_timeout_sec, known_hosts_file):
        user_at_host = "{0}@{1}".format(profile["bootstrap_user"], profile["host"])
        ssh_command = [
            self.ssh_bin,
            "-T",
            "-p",
            str(profile["port"]),
            "-o",
            "BatchMode=no",
            "-o",
            "PubkeyAuthentication=no",
            "-o",
            "PreferredAuthentications=password",
            "-o",
            "NumberOfPasswordPrompts=1",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "UserKnownHostsFile={0}".format(known_hosts_file),
            "-o",
            "ConnectTimeout={0}".format(connect_timeout_sec),
            "-o",
            "LogLevel=ERROR",
            user_at_host,
        ]

        return self._run_askpass_bootstrap(
            ssh_command,
            profile["bootstrap_password"],
            command,
            command_timeout_sec,
        )


class SSHBridge(object):
    def __init__(
        self,
        config_path,
        config_data=None,
        ssh_bin="ssh",
        runner=None,
        session_factory=None,
        bootstrap_client=None,
        lease_ttl_sec=DEFAULT_LEASE_TTL_SEC,
        takeover=False,
        clock=None,
        start_renew_thread=True,
    ):
        self.config_path = os.path.abspath(config_path)
        self.ssh_bin = ssh_bin
        self._config_dir = os.path.dirname(self.config_path)
        if config_data is None:
            self._validate_config_file_permissions()
            self._config = self._load_config(self.config_path)
        else:
            self._config = self._normalize_config(config_data, self.config_path)
        self.ssh_defaults = self._config["ssh_defaults"]
        self.devices = self._config["devices"]
        self.lease_ttl_sec = self._validate_positive_int(lease_ttl_sec, "lease_ttl_sec")
        self.takeover = bool(takeover)
        self._clock = clock or time.time
        self._bootstrap_client = bootstrap_client or _OpenSSHBootstrapClient(self.ssh_bin)
        self._sessions = {}
        self._bindings = {}
        self._state_lock = threading.RLock()
        self._closed = False
        self._renew_event = threading.Event()
        self._renew_thread = None
        if session_factory is not None:
            self._session_factory = session_factory
        elif runner is not None:
            self._session_factory = lambda command: _RunnerSession(command, runner)
        else:
            self._session_factory = _SSHStdioSession
        self._ensure_control_path_dir()
        self._ensure_agent_keys_and_known_hosts()
        if start_renew_thread:
            self._renew_thread = threading.Thread(target=self._renew_loop, name="mcp-lease-renew", daemon=True)
            self._renew_thread.start()

    @classmethod
    def from_config_data(cls, config_data, base_dir, **kwargs):
        if not isinstance(base_dir, str) or not base_dir.strip():
            raise ConfigError("base_dir must be a non-empty path")
        base_dir_path = os.path.expanduser(base_dir.strip())
        if not os.path.isabs(base_dir_path):
            base_dir_path = os.path.abspath(base_dir_path)
        synthetic_config_path = os.path.join(base_dir_path, DEFAULT_PROJECT_CONFIG_FILE_NAME)
        return cls(synthetic_config_path, config_data=config_data, **kwargs)

    def has_device(self, device_id):
        return device_id in self.devices

    def get_device_ids(self):
        return sorted(self.devices.keys())

    def get_default_device_id(self):
        device_ids = self.get_device_ids()
        if len(device_ids) == 1:
            return device_ids[0]
        return None

    def close(self):
        with self._state_lock:
            if self._closed:
                return
            self._closed = True
            self._renew_event.set()

        if self._renew_thread is not None:
            self._renew_thread.join(timeout=1)

        for device_id in list(self._sessions.keys()):
            self._drop_session(device_id)
        for device_id in list(self._bindings.keys()):
            try:
                self._revoke_binding(device_id)
            except BootstrapError:
                pass

    def execute(self, device_id, verb=ARGS_UNSET, target=ARGS_UNSET, args=ARGS_UNSET, timeout_sec=None, command=ARGS_UNSET):
        remote_command = self.build_remote_command(verb=verb, target=target, args=args, command=command)
        command_timeout = timeout_sec or self.ssh_defaults["command_timeout_sec"]

        try:
            self._ensure_binding(device_id)
            session = self._get_session(device_id)
            run_result = session.execute(remote_command, command_timeout)
        except BootstrapError as exc:
            return {
                "device_id": device_id,
                "command": remote_command,
                "ok": False,
                "ssh_exit_code": None,
                "response": exc.response,
                "stderr": exc.stderr,
                "error": {
                    "kind": exc.kind,
                    "code": self._error_code_from_kind(exc.kind),
                    "message": exc.message,
                },
            }
        except (IOError, OSError, subprocess.SubprocessError) as exc:
            self._drop_session(device_id)
            return {
                "device_id": device_id,
                "command": remote_command,
                "ok": False,
                "ssh_exit_code": None,
                "response": None,
                "stderr": None,
                "error": {
                    "kind": "ssh_transport_error",
                    "code": "transport_error",
                    "message": str(exc) or "Unable to start SSH transport",
                },
            }

        stdout_text = self._normalize_output(run_result.get("stdout"))
        stderr_text = self._normalize_output(run_result.get("stderr"))
        ssh_exit_code = run_result.get("exit_code")

        response = None
        error = None
        ok = False

        if run_result.get("timed_out"):
            self._drop_session(device_id)
            error = {
                "kind": "ssh_timeout",
                "code": "timeout",
                "message": "SSH command timed out",
            }
        else:
            response, error = self._decode_response(stdout_text, ssh_exit_code, stderr_text)
            ok = error is None
            if ssh_exit_code not in (None, 0):
                self._drop_session(device_id)

        return {
            "device_id": device_id,
            "command": remote_command,
            "ok": ok,
            "ssh_exit_code": ssh_exit_code,
            "response": response,
            "stderr": stderr_text,
            "error": error,
        }

    def build_remote_command(self, verb=ARGS_UNSET, target=ARGS_UNSET, args=ARGS_UNSET, command=ARGS_UNSET):
        if command is not ARGS_UNSET:
            if not isinstance(command, str) or not command:
                raise ValueError("command must be a non-empty string")
            return command

        if verb is ARGS_UNSET or target is ARGS_UNSET:
            raise ValueError("verb and target are required when command is not provided")

        if args is ARGS_UNSET:
            return "{0} {1}".format(verb, target)

        json_args = json.dumps(args, separators=(",", ":"), sort_keys=True)
        return "{0} {1} {2}".format(verb, target, json_args)

    def build_ssh_command(self, device_id, remote_command=ARGS_UNSET):
        profile = self.devices[device_id]
        defaults = self.ssh_defaults

        user_at_host = "{0}@{1}".format(profile["user"], profile["host"])

        command = [
            self.ssh_bin,
            "-T",
            "-p",
            str(profile["port"]),
            "-i",
            profile["identity_file"],
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "UserKnownHostsFile={0}".format(defaults["known_hosts_file"]),
        ]

        if not _is_windows():
            control_path = os.path.join(defaults["control_path_dir"], "%C")
            command.extend(
                [
                    "-o",
                    "ControlMaster=auto",
                    "-o",
                    "ControlPersist={0}".format(defaults["control_persist_sec"]),
                    "-o",
                    "ControlPath={0}".format(control_path),
                ]
            )

        command.extend(
            [
                "-o",
                "ConnectTimeout={0}".format(defaults["connect_timeout_sec"]),
                "-o",
                "LogLevel=ERROR",
                user_at_host,
            ]
        )
        if remote_command is not ARGS_UNSET:
            command.append(remote_command)

        return command

    def _ensure_binding(self, device_id):
        now = int(self._clock())

        with self._state_lock:
            binding = self._bindings.get(device_id)
            if binding and (binding["local_expires_at"] > now):
                return
            if binding and (binding["local_expires_at"] <= now):
                self._bindings.pop(device_id, None)

        profile = self.devices[device_id]
        self._run_bootstrap_command(device_id, "ensure", profile["public_key"], takeover=self.takeover)
        with self._state_lock:
            self._bindings[device_id] = self._make_binding(profile["public_key"], int(self._clock()))
        self._renew_event.set()

    def _revoke_binding(self, device_id):
        with self._state_lock:
            binding = self._bindings.get(device_id)
        if not binding:
            return

        try:
            self._run_bootstrap_command(device_id, "revoke", binding["public_key"])
        finally:
            with self._state_lock:
                self._bindings.pop(device_id, None)
            self._renew_event.set()

    def _make_binding(self, public_key, now):
        return {
            "public_key": public_key,
            "local_expires_at": now + self.lease_ttl_sec,
            "next_renew_at": now + DEFAULT_LEASE_RENEW_INTERVAL_SEC,
        }

    def _renew_loop(self):
        while True:
            if self._closed:
                return

            now = int(self._clock())
            next_due_at = None
            due_device_ids = []

            with self._state_lock:
                for device_id, binding in list(self._bindings.items()):
                    if binding["local_expires_at"] <= now:
                        self._bindings.pop(device_id, None)
                        continue
                    if binding["next_renew_at"] <= now:
                        due_device_ids.append(device_id)
                    elif next_due_at is None or binding["next_renew_at"] < next_due_at:
                        next_due_at = binding["next_renew_at"]

            if due_device_ids:
                for device_id in due_device_ids:
                    self._renew_binding(device_id)
                continue

            if next_due_at is None:
                timeout = None
            else:
                timeout = max(0, next_due_at - int(self._clock()))

            if self._renew_event.wait(timeout):
                self._renew_event.clear()

    def _renew_binding(self, device_id):
        now = int(self._clock())
        with self._state_lock:
            binding = self._bindings.get(device_id)
        if not binding:
            return

        try:
            self._run_bootstrap_command(device_id, "ensure", binding["public_key"])
        except BootstrapError as exc:
            if exc.kind == "bootstrap_conflict":
                self._drop_session(device_id)
                with self._state_lock:
                    self._bindings.pop(device_id, None)
                self._renew_event.set()
                return
            now = int(self._clock())
            with self._state_lock:
                binding = self._bindings.get(device_id)
                if not binding:
                    return
                if binding["local_expires_at"] <= now:
                    self._bindings.pop(device_id, None)
                    return
                binding["next_renew_at"] = now + DEFAULT_LEASE_RETRY_INTERVAL_SEC
            self._renew_event.set()
            return

        with self._state_lock:
            self._bindings[device_id] = self._make_binding(binding["public_key"], int(self._clock()))
        self._renew_event.set()

    def _run_bootstrap_command(self, device_id, action, public_key=None, takeover=False):
        profile = self.devices[device_id]
        defaults = self.ssh_defaults
        try:
            command = self._build_bootstrap_command_line(action, public_key=public_key, takeover=takeover)
        except ValueError as exc:
            raise BootstrapError("bootstrap_invalid_command", str(exc))

        try:
            run_result = self._bootstrap_client.run(
                profile,
                command,
                defaults["connect_timeout_sec"],
                defaults["command_timeout_sec"],
                defaults["known_hosts_file"],
            )
        except (IOError, OSError, subprocess.SubprocessError) as exc:
            message = str(exc) or "Unable to start bootstrap SSH transport"
            kind = "bootstrap_transport_error"
            if "auth" in message.lower():
                kind = "bootstrap_auth_error"
            raise BootstrapError(kind, message)

        stdout_text = self._normalize_output(run_result.get("stdout"))
        stderr_text = self._normalize_output(run_result.get("stderr"))
        exit_code = run_result.get("exit_code")
        response = None

        if stdout_text:
            try:
                response = json.loads(stdout_text)
            except ValueError:
                raise BootstrapError(
                    "bootstrap_invalid_json",
                    "Bootstrap command stdout was not valid JSON",
                    stderr=stderr_text,
                )

        if exit_code == 0:
            return response or {}

        if exit_code == 255 and response is None:
            kind = "bootstrap_transport_error"
            message = stderr_text or "Bootstrap command failed"
            if "permission denied" in message.lower():
                kind = "bootstrap_auth_error"
            raise BootstrapError(kind, message, stderr=stderr_text, response=response)

        if isinstance(response, dict):
            status = response.get("status")
            error_message = response.get("error")
            if status == 409:
                raise BootstrapError(
                    "bootstrap_conflict",
                    error_message or "Binding Conflict",
                    stderr=stderr_text,
                    response=response,
                )
            if isinstance(error_message, str) and error_message:
                raise BootstrapError(
                    "bootstrap_failed",
                    error_message,
                    stderr=stderr_text,
                    response=response,
                )

        raise BootstrapError(
            "bootstrap_failed",
            stderr_text or "Bootstrap command failed",
            stderr=stderr_text,
            response=response,
        )

    def _build_bootstrap_command_line(self, action, public_key=None, takeover=False):
        if not isinstance(public_key, str) or not public_key.strip():
            raise ValueError("public_key must be a non-empty string")
        if "\n" in public_key or "\r" in public_key:
            raise ValueError("public_key must not contain newlines")

        normalized_key = public_key.strip()

        if action == "ensure":
            command = "mcp key ensure"
            if takeover:
                command += " --takeover"
        elif action == "revoke":
            command = "mcp key revoke"
        else:
            raise ValueError("Unknown bootstrap action: {0}".format(action))

        # Bootstrap SSH lands in the device CLI parser, so send the raw MCP
        # command line over stdin instead of encoding argv as JSON.
        return "{0} {1}".format(command, normalized_key)

    def _get_session(self, device_id):
        session = self._sessions.get(device_id)
        if session is not None and session.is_alive():
            return session

        if session is not None:
            self._drop_session(device_id)

        session = self._session_factory(self.build_ssh_command(device_id))
        self._sessions[device_id] = session
        return session

    def _drop_session(self, device_id):
        session = self._sessions.pop(device_id, None)
        if session is not None:
            session.close()

    def _load_config(self, config_path):
        try:
            with open(config_path, "r") as handle:
                raw = json.load(handle)
        except (IOError, ValueError) as exc:
            raise ConfigError("Unable to load config {0}: {1}".format(config_path, exc))

        return self._normalize_config(raw, config_path)

    def _normalize_config(self, raw, config_path):
        config_path = os.path.abspath(config_path)

        if not isinstance(raw, dict):
            raise ConfigError("Top-level config must be a JSON object")

        defaults = raw.get("ssh_defaults", {})
        devices = raw.get("devices")

        if not isinstance(defaults, dict):
            raise ConfigError("ssh_defaults must be an object")
        if not isinstance(devices, dict) or not devices:
            raise ConfigError("devices must be a non-empty object")

        use_project_layout_defaults = self._paths_equal(config_path, DEFAULT_PROJECT_CONFIG_PATH)

        # If keys_base_dir is set, default known_hosts to a path under it
        keys_base_dir = defaults.get("keys_base_dir")
        if not keys_base_dir and use_project_layout_defaults:
            keys_base_dir = DEFAULT_PROJECT_KEYS_BASE_DIR
        if keys_base_dir:
            keys_base_dir_path = self._resolve_required_path(
                keys_base_dir,
                "ssh_defaults.keys_base_dir",
                must_exist=False,
            )
            known_hosts_default = os.path.join(keys_base_dir_path, DEFAULT_KNOWN_HOSTS_FILE_NAME)
        else:
            keys_base_dir_path = None
            known_hosts_default = os.path.join(self._config_dir, DEFAULT_KNOWN_HOSTS_FILE_NAME)
        if use_project_layout_defaults and "control_path_dir" not in defaults:
            control_path_default = DEFAULT_PROJECT_CONTROL_PATH_DIR
        else:
            control_path_default = os.path.join(self._config_dir, DEFAULT_CONTROL_PATH_DIR_NAME)

        # Determine if we're in auto-key mode (known_hosts can be auto-generated)
        auto_key_mode = bool(keys_base_dir_path)
        known_hosts_path = self._resolve_path(
            defaults.get("known_hosts_file", known_hosts_default)
        )

        # In auto-key mode, known_hosts doesn't need to exist yet
        if not auto_key_mode and not os.path.exists(known_hosts_path):
            raise ConfigError("ssh_defaults.known_hosts_file does not exist: {0}".format(known_hosts_path))

        normalized_defaults = {
            "connect_timeout_sec": self._validate_positive_int(
                defaults.get("connect_timeout_sec", DEFAULT_CONNECT_TIMEOUT_SEC),
                "ssh_defaults.connect_timeout_sec",
            ),
            "command_timeout_sec": self._validate_positive_int(
                defaults.get("command_timeout_sec", DEFAULT_COMMAND_TIMEOUT_SEC),
                "ssh_defaults.command_timeout_sec",
            ),
            "control_persist_sec": self._validate_non_negative_int(
                defaults.get("control_persist_sec", DEFAULT_CONTROL_PERSIST_SEC),
                "ssh_defaults.control_persist_sec",
            ),
            "known_hosts_file": known_hosts_path,
            "control_path_dir": self._resolve_required_path(
                defaults.get("control_path_dir", control_path_default),
                "ssh_defaults.control_path_dir",
                must_exist=False,
            ),
            "keys_base_dir": keys_base_dir_path,
        }

        normalized_devices = {}

        for device_id, device in devices.items():
            if not isinstance(device_id, str) or not device_id:
                raise ConfigError("device ids must be non-empty strings")
            if not isinstance(device, dict):
                raise ConfigError("Device {0} must be an object".format(device_id))

            # Check if identity_file is explicitly configured
            explicit_identity = device.get("identity_file")

            if explicit_identity:
                # Manual key configuration - validate files exist
                identity_file = self._resolve_required_path(
                    explicit_identity,
                    "devices.{0}.identity_file".format(device_id),
                    must_exist=True,
                )
                public_key_file = self._resolve_required_path(
                    device.get("public_key_file", identity_file + ".pub"),
                    "devices.{0}.public_key_file".format(device_id),
                    must_exist=True,
                )
                public_key = self._load_public_key(
                    public_key_file,
                    "devices.{0}.public_key_file".format(device_id),
                )
            elif keys_base_dir_path:
                # Auto-key mode: defer key generation to _ensure_agent_keys
                identity_file = None
                public_key_file = None
                public_key = None
            else:
                raise ConfigError(
                    "devices.{0}.identity_file is required when ssh_defaults.keys_base_dir is not set".format(device_id)
                )

            normalized_devices[device_id] = {
                "host": self._require_string(device.get("host"), "devices.{0}.host".format(device_id)),
                "user": self._require_string(
                    device.get("user", DEFAULT_AGENT_USER),
                    "devices.{0}.user".format(device_id),
                ),
                "identity_file": identity_file,
                "public_key_file": public_key_file,
                "public_key": public_key,
                "bootstrap_user": self._require_string(
                    device.get("bootstrap_user", DEFAULT_BOOTSTRAP_USER),
                    "devices.{0}.bootstrap_user".format(device_id),
                ),
                "bootstrap_password": self._require_string(
                    device.get("bootstrap_password"),
                    "devices.{0}.bootstrap_password".format(device_id),
                ),
                "port": self._validate_positive_int(
                    device.get("port", 22),
                    "devices.{0}.port".format(device_id),
                ),
            }

        return {
            "ssh_defaults": normalized_defaults,
            "devices": normalized_devices,
        }

    def _ensure_control_path_dir(self):
        control_path_dir = self.ssh_defaults["control_path_dir"]
        try:
            if not os.path.isdir(control_path_dir):
                os.makedirs(control_path_dir, 0o700)
            os.chmod(control_path_dir, 0o700)
        except OSError as exc:
            raise ConfigError("Unable to prepare control_path_dir {0}: {1}".format(control_path_dir, exc))

    def _ensure_agent_keys_and_known_hosts(self):
        """Ensure SSH keys and known_hosts exist for devices configured with keys_base_dir.

        For each device without explicit identity_file, creates a dedicated
        key directory under keys_base_dir, generates ed25519 key pair,
        and ensures host keys are in known_hosts.
        """
        keys_base_dir = self.ssh_defaults.get("keys_base_dir")
        if not keys_base_dir:
            return

        for device_id, profile in self.devices.items():
            # Skip if device already has explicit identity_file configured
            if profile.get("identity_file") and profile.get("public_key_file"):
                # Even for explicit identity, ensure known_hosts has the host key
                self._ensure_host_key_in_known_hosts(profile)
                continue

            device_key_dir = os.path.join(keys_base_dir, device_id)

            # Check for existing agent_key_* directory
            existing_key_dir = self._find_existing_key_dir(device_key_dir)

            if existing_key_dir:
                identity_file = os.path.join(existing_key_dir, "agent_key")
                public_key_file = identity_file + ".pub"
            else:
                # Create new key directory with timestamp
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                new_key_dir = os.path.join(device_key_dir, "agent_key_{0}".format(timestamp))
                try:
                    os.makedirs(new_key_dir, 0o700)
                except OSError as exc:
                    raise ConfigError("Unable to create key directory {0}: {1}".format(new_key_dir, exc))

                identity_file = os.path.join(new_key_dir, "agent_key")
                public_key_file = identity_file + ".pub"

                # Generate SSH key pair using ssh-keygen
                self._generate_ssh_key(identity_file, device_id)

            # Update device profile with auto-generated key paths
            profile["identity_file"] = identity_file
            profile["public_key_file"] = public_key_file
            profile["public_key"] = self._load_public_key(
                public_key_file, "devices.{0}.public_key_file".format(device_id)
            )

            # Ensure host key is in known_hosts
            self._ensure_host_key_in_known_hosts(profile)

    def _find_existing_key_dir(self, device_key_dir):
        """Find existing agent_key_* directory under device_key_dir."""
        if not os.path.isdir(device_key_dir):
            return None
        try:
            entries = os.listdir(device_key_dir)
            for entry in entries:
                if entry.startswith("agent_key_"):
                    full_path = os.path.join(device_key_dir, entry)
                    if os.path.isdir(full_path):
                        return full_path
        except OSError:
            pass
        return None

    def _ensure_host_key_in_known_hosts(self, profile):
        """Ensure device host key is in known_hosts file.

        Uses ssh-keyscan to fetch host keys if not already present.
        """
        known_hosts_file = self.ssh_defaults["known_hosts_file"]
        host = profile["host"]
        port = profile["port"]

        # Check if host already in known_hosts
        if self._host_in_known_hosts(known_hosts_file, host, port):
            return

        # Fetch host keys using ssh-keyscan
        try:
            result = subprocess.run(
                ["ssh-keyscan", "-p", str(port), "-t", "rsa,ecdsa,ed25519", host],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=30,
            )
            if result.returncode != 0 or not result.stdout.strip():
                raise ConfigError(
                    "Failed to fetch host key for {0}:{1}: {2}".format(
                        host, port, result.stderr or "ssh-keyscan returned no output"
                    )
                )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ConfigError(
                "Failed to fetch host key for {0}:{1}: {2}".format(host, port, exc)
            )

        # Append to known_hosts file (create if not exists)
        try:
            # Ensure parent directory exists
            known_hosts_dir = os.path.dirname(known_hosts_file)
            if known_hosts_dir and not os.path.exists(known_hosts_dir):
                os.makedirs(known_hosts_dir, 0o700)

            with open(known_hosts_file, "a") as f:
                f.write(result.stdout)
            os.chmod(known_hosts_file, 0o600)
        except OSError as exc:
            raise ConfigError(
                "Failed to write known_hosts file {0}: {1}".format(known_hosts_file, exc)
            )

    def _host_in_known_hosts(self, known_hosts_file, host, port):
        """Check if host is already in known_hosts file."""
        if not os.path.exists(known_hosts_file):
            return False

        # For port 22, check both hostname and [hostname]:22 formats
        # For non-standard ports, check [hostname]:port format
        search_patterns = []
        if port == 22:
            search_patterns.append(host)
            search_patterns.append("[{0}]:22".format(host))
        else:
            search_patterns.append("[{0}]:{1}".format(host, port))

        try:
            with open(known_hosts_file, "r") as f:
                content = f.read()
                for pattern in search_patterns:
                    # Check for pattern at start of line or after whitespace
                    if re.search(r"(^|\s)" + re.escape(pattern) + r"[\s,]", content):
                        return True
        except (IOError, OSError):
            return False

        return False

    def _generate_ssh_key(self, identity_file, device_id):
        """Generate SSH key pair using ssh-keygen."""
        try:
            subprocess.run(
                [
                    "ssh-keygen",
                    "-t", DEFAULT_KEY_TYPE,
                    "-b", str(DEFAULT_KEY_BITS),
                    "-f", identity_file,
                    "-N", "",
                    "-C", "mcp-agent-{0}".format(device_id),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
            )
            # Set proper permissions
            os.chmod(identity_file, 0o600)
            os.chmod(identity_file + ".pub", 0o644)
        except subprocess.CalledProcessError as exc:
            raise ConfigError(
                "Failed to generate SSH key for device {0}: {1}".format(device_id, exc.stderr.decode("utf-8", "replace"))
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ConfigError(
                "Failed to generate SSH key for device {0}: {1}".format(device_id, exc)
            )

    def _resolve_path(self, value):
        """Resolve a path, making it absolute relative to config dir if needed."""
        if not isinstance(value, str):
            return value
        path = os.path.expanduser(value.strip())
        if not os.path.isabs(path):
            path = os.path.abspath(os.path.join(self._config_dir, path))
        return path

    def _resolve_required_path(self, value, field_name, must_exist):
        path = self._require_string(value, field_name)
        path = os.path.expanduser(path)
        if not os.path.isabs(path):
            path = os.path.abspath(os.path.join(self._config_dir, path))
        if must_exist and not os.path.exists(path):
            raise ConfigError("{0} does not exist: {1}".format(field_name, path))
        return path

    def _paths_equal(self, left, right):
        return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))

    def _require_string(self, value, field_name):
        if not isinstance(value, str) or not value.strip():
            raise ConfigError("{0} must be a non-empty string".format(field_name))
        return value.strip()

    def _validate_positive_int(self, value, field_name):
        if not isinstance(value, int) or value <= 0:
            raise ConfigError("{0} must be a positive integer".format(field_name))
        return value

    def _validate_non_negative_int(self, value, field_name):
        if not isinstance(value, int) or value < 0:
            raise ConfigError("{0} must be a non-negative integer".format(field_name))
        return value

    def _normalize_output(self, value):
        if value is None:
            return None
        if isinstance(value, bytes):
            value = value.decode("utf-8", "replace")
        value = value.strip()
        return value or None

    def _decode_response(self, stdout_text, ssh_exit_code, stderr_text):
        payload = None

        if stdout_text:
            try:
                payload = json.loads(stdout_text)
            except ValueError:
                return None, {
                    "kind": "invalid_device_json",
                    "code": "internal",
                    "message": "Device CLI stdout was not valid JSON",
                }

        if ssh_exit_code == 0:
            if payload is None:
                return None, {
                    "kind": "invalid_device_json",
                    "code": "internal",
                    "message": "Device CLI produced empty stdout",
                }
            if not isinstance(payload, dict):
                return None, {
                    "kind": "invalid_device_json",
                    "code": "internal",
                    "message": "Device CLI stdout did not follow the output contract",
                }
            if payload.get("ok") is True:
                if "data" not in payload:
                    return None, {
                        "kind": "invalid_device_json",
                        "code": "internal",
                        "message": "Device CLI success payload was missing data",
                    }
                return payload.get("data"), None
            if payload.get("ok") is False:
                return None, self._decode_cli_error(payload)
            return None, {
                "kind": "invalid_device_json",
                "code": "internal",
                "message": "Device CLI stdout did not follow the output contract",
            }

        if ssh_exit_code == 255 and payload is None:
            return None, {
                "kind": "ssh_transport_error",
                "code": "transport_error",
                "message": stderr_text or "SSH transport failed",
            }

        if isinstance(payload, dict) and payload.get("ok") is False:
            return None, self._decode_cli_error(payload)

        if isinstance(payload, dict) and payload.get("ok") is True and "data" in payload:
            return payload.get("data"), {
                "kind": "ssh_command_failed",
                "code": self._error_code_from_exit_code(ssh_exit_code),
                "message": stderr_text or "SSH command failed",
            }

        return None, {
            "kind": "ssh_command_failed",
            "code": self._error_code_from_exit_code(ssh_exit_code),
            "message": stderr_text or "SSH command failed",
        }

    def _decode_cli_error(self, payload):
        error = payload.get("error")
        if not isinstance(error, dict):
            return {
                "kind": "invalid_device_json",
                "code": "internal",
                "message": "Device CLI error payload was malformed",
            }

        message = error.get("message")
        field = error.get("field")
        decoded = {
            "kind": "device_cli_error",
            "code": self._normalize_error_code(error.get("code")),
            "message": message if isinstance(message, str) and message else "Device CLI reported an error",
        }
        if isinstance(field, str) and field:
            decoded["field"] = field
        return decoded

    def _normalize_error_code(self, code):
        if isinstance(code, str) and code:
            return code
        return "internal"

    def _error_code_from_exit_code(self, exit_code):
        if exit_code == 2:
            return "not_found"
        if exit_code == 3:
            return "timeout"
        if exit_code == 4:
            return "bad_args"
        return "internal"

    def _error_code_from_kind(self, kind):
        if kind in ("ssh_timeout",):
            return "timeout"
        if kind in ("ssh_transport_error", "bootstrap_transport_error"):
            return "transport_error"
        if kind in ("bootstrap_conflict",):
            return "conflict"
        if kind in ("bootstrap_auth_error",):
            return "unauthorized"
        if kind in ("device_cli_error",):
            return "internal"
        return "internal"

    def _validate_config_file_permissions(self):
        if os.name != "posix":
            return

        try:
            mode = stat.S_IMODE(os.stat(self.config_path).st_mode)
        except OSError as exc:
            raise ConfigError("Unable to stat config {0}: {1}".format(self.config_path, exc))

        if mode & 0o077:
            raise ConfigError(
                "Config file permissions must be 0600 or stricter: {0} is {1:o}. "
                "Remove group/other access, for example `chmod 600 {0}`. "
                "If the file lives on a shared or read-only mount that does not support chmod, "
                "move it to a local path such as your home directory."
                .format(self.config_path, mode)
            )

    def _load_public_key(self, path, field_name):
        try:
            with open(path, "r") as handle:
                lines = [line.strip() for line in handle.readlines() if line.strip()]
        except IOError as exc:
            raise ConfigError("Unable to load {0}: {1}".format(field_name, exc))

        if len(lines) != 1:
            raise ConfigError("{0} must contain exactly one public key".format(field_name))

        parts = lines[0].split()
        if len(parts) < 2:
            raise ConfigError("{0} does not contain a valid SSH public key".format(field_name))
        return lines[0]
