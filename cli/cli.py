from __future__ import print_function

import argparse
import errno
import getpass
import hashlib
import http.client
import json
import ntpath
import os
import socket
import stat
import subprocess
import sys
import textwrap
import threading
import time
import uuid

try:
    from .command_surface import (
        CommandSurface,
        ERR_INVALID_PARAMS,
        EXIT_BADARGS,
        EXIT_ERROR,
        EXIT_NOTFOUND,
        EXIT_OK,
        EXIT_TIMEOUT,
        JSONRPCError,
        build_inline_config,
    )
    from .ssh_bridge import BootstrapError, ConfigError, SSHBridge
except (ImportError, SystemError, ValueError):
    from command_surface import (
        CommandSurface,
        ERR_INVALID_PARAMS,
        EXIT_BADARGS,
        EXIT_ERROR,
        EXIT_NOTFOUND,
        EXIT_OK,
        EXIT_TIMEOUT,
        JSONRPCError,
        build_inline_config,
    )
    from ssh_bridge import BootstrapError, ConfigError, SSHBridge


DEFAULT_RUNTIME_DIR = os.path.join("~", ".agent-cli")
DEFAULT_CONFIG_FILE_NAME = "config.json"
DEFAULT_AGENT_API_PORT = 4888
DEFAULT_UPGRADE_TIMEOUT_SEC = 600
DEFAULT_SESSION_IDLE_TIMEOUT_SEC = 300
DEFAULT_SESSION_STATE_DIR_NAME = "sessions"
DEFAULT_SESSION_STARTUP_TIMEOUT_SEC = 5
DEFAULT_SESSION_CONNECT_TIMEOUT_SEC = 5
DEFAULT_SESSION_READ_LIMIT = 1024 * 1024
LOCAL_API_REMOTE_ADDR = "127.0.0.1"
DEFAULT_BOOTSTRAP_USER = "adm"
DEFAULT_AGENT_USER = "agent"
DEFAULT_SSH_PORT = 22


class _SSHTunnelError(Exception):
    def __init__(self, message, stderr=None):
        super(_SSHTunnelError, self).__init__(message)
        self.message = message
        self.stderr = stderr


class _SSHStreamError(OSError):
    def __init__(self, message, stderr=None):
        super(_SSHStreamError, self).__init__(message)
        self.stderr = stderr


class _SSHResponseReader(object):
    def __init__(self, process_stream):
        self._process_stream = process_stream
        self._handle = process_stream.acquire_response_reader()
        self._closed = False

    @property
    def closed(self):
        return self._closed or getattr(self._handle, "closed", False)

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._process_stream.release_response_reader()

    def readline(self, *args):
        return self._handle.readline(*args)

    def read(self, *args):
        return self._handle.read(*args)

    def __iter__(self):
        return self

    def __next__(self):
        line = self.readline()
        if line:
            return line
        raise StopIteration

    def __getattr__(self, name):
        return getattr(self._handle, name)


class _SSHProcessSocket(object):
    def __init__(self, process_stream):
        self._process_stream = process_stream

    def sendall(self, payload):
        self._process_stream.ensure_running("SSH API stream exited before the request was sent")
        try:
            self._process_stream.process.stdin.write(payload)
            self._process_stream.process.stdin.flush()
        except (AttributeError, IOError, OSError, ValueError):
            raise self._process_stream.transport_error("SSH API stream write failed")

    def makefile(self, mode):
        if "r" not in mode:
            raise ValueError("Unsupported mode for SSH API stream: {0}".format(mode))
        return _SSHResponseReader(self._process_stream)

    def close(self):
        self._process_stream.close()


class _SSHProcessStream(object):
    def __init__(self, command):
        self.process = None
        self._stderr_handle = None
        self._stderr_chunks = []
        self._stderr_thread = None
        self._response_reader_count = 0
        self._close_requested = False

        try:
            self.process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                start_new_session=True,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise _SSHStreamError(str(exc) or "Unable to start SSH API stream")

        self._stderr_handle = self.process.stderr
        self._stderr_thread = threading.Thread(
            target=self._read_stderr,
            name="agent-cli-ssh-api-stderr",
            daemon=True,
        )
        self._stderr_thread.start()

    def ensure_running(self, default_message):
        process = self.process
        if process is None:
            raise _SSHStreamError("SSH API stream is closed")
        if process.poll() is not None:
            raise self.transport_error(default_message)

    def transport_error(self, default_message):
        self._wait_for_stderr(0.2)
        stderr_text = self.stderr_text()
        return _SSHStreamError(stderr_text or default_message, stderr=stderr_text)

    def stderr_text(self):
        if not self._stderr_chunks:
            return None
        payload = b"".join(self._stderr_chunks).decode("utf-8", "replace").strip()
        return payload or None

    def acquire_response_reader(self):
        self.ensure_running("SSH API stream exited before the response was received")
        stdout_handle = self.process.stdout
        if stdout_handle is None:
            raise self.transport_error("SSH API stream stdout is unavailable")
        self._response_reader_count += 1
        return stdout_handle

    def release_response_reader(self):
        if self._response_reader_count > 0:
            self._response_reader_count -= 1
        if self._response_reader_count == 0:
            self._close_now()

    def close(self):
        self._close_requested = True
        if self._response_reader_count == 0:
            self._close_now()

    def _close_now(self):
        process = self.process
        if process is None:
            return

        stdin_handle = process.stdin
        stdout_handle = process.stdout
        stderr_handle = process.stderr
        self.process = None

        for handle in (stdin_handle, stdout_handle):
            try:
                if handle is not None:
                    handle.close()
            except (IOError, OSError, ValueError):
                pass

        try:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1)
        except (OSError, subprocess.SubprocessError):
            pass

        if stderr_handle is not None:
            try:
                stderr_handle.close()
            except (IOError, OSError, ValueError):
                pass

        self._wait_for_stderr(0.2)

    def _read_stderr(self):
        handle = self._stderr_handle
        if handle is None:
            return

        while True:
            try:
                chunk = handle.read(4096)
            except (AttributeError, IOError, OSError, ValueError):
                chunk = b""

            if not chunk:
                return

            self._stderr_chunks.append(chunk)

    def _wait_for_stderr(self, timeout_sec):
        if self._stderr_thread is not None and self._stderr_thread.is_alive():
            self._stderr_thread.join(timeout=timeout_sec)


class _SSHHTTPConnection(http.client.HTTPConnection):
    def __init__(self, tunnel, timeout=None):
        super(_SSHHTTPConnection, self).__init__(tunnel.remote_host, tunnel.remote_port, timeout=timeout)
        self._tunnel = tunnel

    def connect(self):
        self.sock = _SSHProcessSocket(_SSHProcessStream(self._tunnel.build_ssh_command()))


class _SSHAPITunnel(object):
    def __init__(self, bridge, device_id, remote_host, remote_port, timeout_sec=None):
        self.bridge = bridge
        self.device_id = device_id
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.timeout_sec = timeout_sec

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False

    def build_ssh_command(self):
        profile = self.bridge.devices[self.device_id]
        defaults = self.bridge.ssh_defaults
        return [
            self.bridge.ssh_bin,
            "-T",
            "-W",
            "{0}:{1}".format(self.remote_host, self.remote_port),
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
            "-o",
            "ControlMaster=no",
            "-o",
            "ConnectTimeout={0}".format(defaults["connect_timeout_sec"]),
            "-o",
            "LogLevel=ERROR",
            "{0}@{1}".format(profile["agent_user"], profile["device_ip"]),
        ]

    def open_http_connection(self, timeout_sec):
        return _SSHHTTPConnection(
            self,
            timeout=timeout_sec if timeout_sec is not None else self.timeout_sec,
        )


class _SessionError(Exception):
    pass


class _SessionUnavailableError(_SessionError):
    pass


class _SessionManagerError(_SessionError):
    def __init__(self, message, kind="session_manager_error"):
        super(_SessionManagerError, self).__init__(message)
        self.message = message
        self.kind = kind


class _SessionProtocolError(_SessionUnavailableError):
    pass


class _RouterCliSessionPaths(object):
    def __init__(self, runtime_dir, session_key):
        self.session_dir = os.path.join(runtime_dir, DEFAULT_SESSION_STATE_DIR_NAME)
        self.session_key = session_key
        self.state_file = os.path.join(self.session_dir, "{0}.json".format(session_key))
        self.request_file = os.path.join(self.session_dir, "{0}.request.json".format(session_key))
        self.start_lock_file = os.path.join(self.session_dir, "{0}.lock".format(session_key))


class _SessionStartLock(object):
    def __init__(self, lock_path, timeout_sec):
        self.lock_path = lock_path
        self.timeout_sec = timeout_sec
        self._fd = None

    def __enter__(self):
        deadline = time.monotonic() + self.timeout_sec
        while True:
            _ensure_private_dir(os.path.dirname(self.lock_path))
            try:
                self._fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
                return self
            except OSError as exc:
                if exc.errno != errno.EEXIST:
                    raise
                if time.monotonic() >= deadline:
                    raise _SessionUnavailableError("Timed out waiting for the session startup lock")
                time.sleep(0.05)

    def __exit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        _safe_unlink(self.lock_path)
        return False


class _RouterCliSessionManager(object):
    def __init__(self, app, bridge, state_file, idle_timeout_sec):
        self._app = app
        self._bridge = bridge
        self._state_file = state_file
        self._idle_timeout_sec = idle_timeout_sec

    def serve(self):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        token = uuid.uuid4().hex + uuid.uuid4().hex

        try:
            listener.bind(("127.0.0.1", 0))
            listener.listen(8)
            listener_host, listener_port = listener.getsockname()
            _write_private_json(
                self._state_file,
                {
                    "pid": os.getpid(),
                    "host": listener_host,
                    "port": listener_port,
                    "token": token,
                    "created_at": int(time.time()),
                },
            )

            last_activity = time.monotonic()
            keep_running = True
            while keep_running:
                remaining = self._idle_timeout_sec - (time.monotonic() - last_activity)
                if remaining <= 0:
                    break

                listener.settimeout(remaining)
                try:
                    connection, _peer = listener.accept()
                except socket.timeout:
                    break
                except OSError:
                    break

                with connection:
                    keep_running, counted_as_activity = self._handle_connection(connection, token)
                    if counted_as_activity:
                        last_activity = time.monotonic()
        finally:
            try:
                listener.close()
            except OSError:
                pass
            _safe_unlink(self._state_file)
            self._bridge.close()

        return EXIT_OK

    def _handle_connection(self, connection, token):
        try:
            request = _read_json_message(
                connection,
                "Session manager request stream closed before a request was received",
            )
        except _SessionError as exc:
            self._write_response(
                connection,
                {
                    "ok": False,
                    "error": {
                        "kind": "invalid_request",
                        "message": str(exc) or "Invalid session manager request",
                    },
                },
            )
            return True, False

        if request.get("token") != token:
            self._write_response(
                connection,
                {
                    "ok": False,
                    "error": {
                        "kind": "invalid_token",
                        "message": "Invalid session manager token",
                    },
                },
            )
            return True, False

        action = request.get("action")
        if action == "ping":
            self._write_response(connection, {"ok": True, "pid": os.getpid()})
            return True, True
        if action == "shutdown":
            self._write_response(connection, {"ok": True})
            return False, False
        if action != "execute":
            self._write_response(
                connection,
                {
                    "ok": False,
                    "error": {
                        "kind": "invalid_action",
                        "message": "Unknown session manager action: {0}".format(action),
                    },
                },
            )
            return True, False

        validated = request.get("validated")
        if not isinstance(validated, dict):
            self._write_response(
                connection,
                {
                    "ok": False,
                    "error": {
                        "kind": "invalid_request",
                        "message": "validated must be an object",
                    },
                },
            )
            return True, False

        try:
            outcome = self._app._execute_validated_public_call(self._bridge, validated)
        except Exception as exc:
            self._write_response(
                connection,
                {
                    "ok": False,
                    "error": {
                        "kind": "session_internal_error",
                        "message": str(exc) or "Session manager request failed",
                    },
                },
            )
            return True, True

        self._write_response(connection, {"ok": True, "outcome": outcome})
        return True, True

    def _write_response(self, connection, payload):
        try:
            connection.sendall((_session_json_dumps(payload) + "\n").encode("utf-8"))
        except OSError:
            pass


def _session_json_dumps(payload):
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _ensure_private_dir(path):
    if not path:
        return
    if not os.path.isdir(path):
        os.makedirs(path, 0o700)
    if os.name == "posix":
        os.chmod(path, 0o700)


def _write_private_json(path, payload):
    parent = os.path.dirname(path)
    if parent:
        _ensure_private_dir(parent)
    with open(path, "w") as handle:
        handle.write(_session_json_dumps(payload))
    if os.name == "posix":
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def _read_json_file(path):
    with open(path, "r") as handle:
        return json.load(handle)


def _safe_unlink(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def _read_json_message(connection, eof_message):
    payload = b""
    while True:
        if len(payload) > DEFAULT_SESSION_READ_LIMIT:
            raise _SessionProtocolError("Session manager message exceeded the maximum size")
        try:
            chunk = connection.recv(4096)
        except socket.timeout:
            raise _SessionUnavailableError("Timed out waiting for the session manager response")
        except OSError as exc:
            raise _SessionUnavailableError(str(exc) or "Failed to read from the session manager")

        if not chunk:
            break

        payload += chunk
        if b"\n" in payload:
            payload = payload.split(b"\n", 1)[0]
            break

    if not payload:
        raise _SessionUnavailableError(eof_message)

    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError:
        raise _SessionProtocolError("Session manager response was not valid UTF-8")

    try:
        message = json.loads(decoded)
    except ValueError:
        raise _SessionProtocolError("Session manager message was not valid JSON")

    if not isinstance(message, dict):
        raise _SessionProtocolError("Session manager message must be a JSON object")
    return message


def _build_session_key(config_data, device_id):
    digest = hashlib.sha256()
    digest.update(device_id.encode("utf-8"))
    digest.update(b"\0")
    digest.update(_session_json_dumps(config_data).encode("utf-8"))
    return digest.hexdigest()


def _load_session_state(paths):
    if not os.path.exists(paths.state_file):
        raise _SessionUnavailableError("Session manager state file is missing")

    try:
        payload = _read_json_file(paths.state_file)
    except (IOError, OSError, ValueError) as exc:
        raise _SessionUnavailableError("Unable to read the session manager state: {0}".format(exc))

    if not isinstance(payload, dict):
        raise _SessionUnavailableError("Session manager state must be a JSON object")

    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        kind = error.get("kind", "session_start_failed")
        raise _SessionManagerError(
            message if isinstance(message, str) and message else "Session manager startup failed",
            kind=kind,
        )

    host = payload.get("host")
    port = payload.get("port")
    token = payload.get("token")
    if not isinstance(host, str) or not host:
        raise _SessionUnavailableError("Session manager state was missing the host")
    if not isinstance(port, int) or port <= 0:
        raise _SessionUnavailableError("Session manager state was missing the port")
    if not isinstance(token, str) or not token:
        raise _SessionUnavailableError("Session manager state was missing the token")
    return payload


def _request_session_manager(state, payload, timeout_sec):
    request_payload = dict(payload)
    request_payload["token"] = state["token"]
    encoded = (_session_json_dumps(request_payload) + "\n").encode("utf-8")

    try:
        connection = socket.create_connection((state["host"], state["port"]), timeout=timeout_sec)
    except OSError as exc:
        raise _SessionUnavailableError(str(exc) or "Unable to connect to the session manager")

    try:
        connection.settimeout(timeout_sec)
        connection.sendall(encoded)
        response = _read_json_message(
            connection,
            "Session manager closed the connection before returning a response",
        )
    except OSError as exc:
        raise _SessionUnavailableError(str(exc) or "Session manager request failed")
    finally:
        try:
            connection.close()
        except OSError:
            pass

    if response.get("ok") is False:
        error = response.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            kind = error.get("kind", "session_manager_error")
            if kind == "invalid_token":
                raise _SessionUnavailableError(
                    message if isinstance(message, str) and message else "Session manager token mismatch"
                )
            raise _SessionManagerError(
                message if isinstance(message, str) and message else "Session manager request failed",
                kind=kind,
            )
        raise _SessionManagerError("Session manager request failed")

    if response.get("ok") is not True:
        raise _SessionProtocolError("Session manager response did not include an ok flag")

    return response


class RouterCli(object):
    def __init__(self, stdout=None, stderr=None, stdin=None, password_reader=None):
        self.stdout = stdout or sys.stdout
        self.stderr = stderr or sys.stderr
        self.stdin = stdin or sys.stdin
        self._password_reader = password_reader or self._default_password_reader

    def run(self, argv=None):
        raw_argv = argv if argv is not None else sys.argv[1:]
        help_options = parse_help_args(raw_argv)
        if help_options is not None:
            return self._run_help(help_options)

        options = parse_args(raw_argv)

        if options.command_name == "__sessiond":
            return self._run_session_manager(options)
        if options.command_name == "help":
            return self._run_help(options)
        if options.command_name == "auth":
            return self._run_auth(options)

        try:
            bridge = self._open_bridge(options)
        except ConfigError as exc:
            print("Configuration error: {0}".format(exc), file=self.stderr)
            return EXIT_BADARGS

        try:
            server = CommandSurface(bridge)
            validated = self._validate_command(server, options)
            outcome = self._execute_validated_via_session(options, bridge, validated)
            return self._write_public_outcome(outcome)
        except JSONRPCError as exc:
            print(exc.message, file=self.stderr)
            data = exc.data if isinstance(exc.data, dict) else None
            if data:
                configured_ids = data.get("configured_device_ids")
                if isinstance(configured_ids, list) and configured_ids:
                    print(
                        "Configured devices: {0}".format(", ".join(str(x) for x in configured_ids)),
                        file=self.stderr,
                    )
                    print(
                        "Pass --device-id <name> to select one, or run `agent-cli auth list` for details.",
                        file=self.stderr,
                    )
            return self._exit_code_from_error_code("bad_args")
        finally:
            bridge.close()

    def _run_help(self, options):
        domain = options.domain
        if domain is None:
            self.stdout.write(self._render_general_help())
            return EXIT_OK

        domain = domain.strip()
        if not domain:
            self.stdout.write(self._render_general_help())
            return EXIT_OK

        renderer = {
            "status": self._render_status_help,
            "config": self._render_config_help,
            "log": self._render_log_help,
            "schema": self._render_schema_help,
            "tool": self._render_tool_help,
            "upgrade": self._render_upgrade_help,
            "reboot": self._render_reboot_help,
            "auth": self._render_auth_help,
            "help": lambda: self._render_general_help(),
        }.get(domain)
        if renderer is None:
            print("Unknown help topic: {0}".format(domain), file=self.stderr)
            return EXIT_BADARGS

        dynamic = self._try_collect_dynamic_help(domain, options)
        self.stdout.write(renderer())
        if dynamic:
            self.stdout.write(dynamic)
        return EXIT_OK

    def _run_auth(self, options):
        auth_args = list(getattr(options, "auth_args", None) or [])
        if auth_args:
            action = auth_args[0]
            if action == "list":
                return self._run_auth_list(options, auth_args[1:])
            if action == "remove":
                return self._run_auth_remove(options, auth_args[1:])
            print(
                "Unknown auth subcommand: {0}. Use `list`, `remove <name>`, or omit for bootstrap.".format(action),
                file=self.stderr,
            )
            return EXIT_BADARGS

        runtime_dir = self._resolve_runtime_dir(options.runtime_dir)
        config_path = self._resolve_config_path(options.config, runtime_dir)
        takeover = bool(options.auth_takeover or options.takeover)
        existing_names = self._read_existing_device_names(config_path)

        try:
            self._collect_auth_options(options, existing_names=existing_names)
        except ConfigError as exc:
            print("Configuration error: {0}".format(exc), file=self.stderr)
            return EXIT_BADARGS

        device_name = options.name
        device_spec = self._build_auth_device_spec(options, device_name)
        inline_config = build_inline_config([device_spec], runtime_dir)

        try:
            bridge = SSHBridge.from_config_data(
                inline_config,
                base_dir=runtime_dir,
                takeover=takeover,
                start_renew_thread=False,
            )
        except ConfigError as exc:
            print("Configuration error: {0}".format(exc), file=self.stderr)
            return EXIT_BADARGS

        try:
            bridge._ensure_binding(device_name)
        except BootstrapError as exc:
            result = {
                "ok": False,
                "device_id": device_name,
                "error": {
                    "code": self._bridge_error_code(exc.kind),
                    "kind": exc.kind,
                    "message": exc.message,
                },
            }
            self._write_json(result)
            return self._exit_code_from_error_code(result["error"]["code"])
        finally:
            bridge.close()

        merged_config = self._merge_auth_config(
            config_path,
            runtime_dir,
            device_name,
            options,
        )
        self._write_config_file(config_path, merged_config)

        self._write_json(
            {
                "ok": True,
                "device_id": device_name,
                "data": {
                    "config_path": config_path,
                    "runtime_dir": runtime_dir,
                    "device_ip": options.device_ip,
                    "port": options.port,
                    "user": options.user,
                    "agent_user": options.agent_user,
                },
            }
        )
        return EXIT_OK

    def _run_auth_list(self, options, extra):
        if extra:
            print("auth list does not accept additional arguments", file=self.stderr)
            return EXIT_BADARGS

        runtime_dir = self._resolve_runtime_dir(options.runtime_dir)
        config_path = self._resolve_config_path(options.config, runtime_dir)

        devices = []
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as handle:
                    payload = json.load(handle)
            except (IOError, OSError, ValueError) as exc:
                print("Configuration error: {0}".format(exc), file=self.stderr)
                return EXIT_BADARGS

            raw_devices = payload.get("devices") if isinstance(payload, dict) else None
            if isinstance(raw_devices, dict):
                for name in sorted(raw_devices.keys()):
                    entry = raw_devices[name]
                    if not isinstance(entry, dict):
                        continue
                    devices.append({
                        "name": name,
                        "device_ip": entry.get("device_ip"),
                        "port": entry.get("port"),
                        "agent_user": entry.get("agent_user"),
                        "user": entry.get("user"),
                    })

        self._write_json({
            "ok": True,
            "data": {
                "config_path": config_path,
                "runtime_dir": runtime_dir,
                "devices": devices,
            },
        })
        return EXIT_OK

    def _run_auth_remove(self, options, extra):
        remove_all = False
        names = []
        seen = set()
        for arg in extra:
            if arg == "--all":
                remove_all = True
                continue
            if not arg or arg.startswith("-"):
                print("auth remove does not accept argument: {0}".format(arg), file=self.stderr)
                return EXIT_BADARGS
            if arg in seen:
                continue
            seen.add(arg)
            names.append(arg)

        if remove_all and names:
            print("auth remove --all does not accept device names", file=self.stderr)
            return EXIT_BADARGS
        if not remove_all and not names:
            print(
                "auth remove requires one or more device names, or --all to remove every saved device",
                file=self.stderr,
            )
            return EXIT_BADARGS

        runtime_dir = self._resolve_runtime_dir(options.runtime_dir)
        config_path = self._resolve_config_path(options.config, runtime_dir)

        if not os.path.exists(config_path):
            self._write_json({
                "ok": False,
                "error": {
                    "code": "not_found",
                    "kind": "config_missing",
                    "message": "config file does not exist: {0}".format(config_path),
                },
            })
            return EXIT_NOTFOUND

        try:
            with open(config_path, "r") as handle:
                payload = json.load(handle)
        except (IOError, OSError, ValueError) as exc:
            print("Configuration error: {0}".format(exc), file=self.stderr)
            return EXIT_BADARGS

        if not isinstance(payload, dict):
            print("Configuration error: top-level config must be a JSON object", file=self.stderr)
            return EXIT_BADARGS

        raw_devices = payload.get("devices")
        devices = raw_devices if isinstance(raw_devices, dict) else {}

        if remove_all:
            removed = sorted(devices.keys())
            payload["devices"] = {}
            self._write_config_file(config_path, payload)
            self._write_json({
                "ok": True,
                "data": {
                    "config_path": config_path,
                    "removed": removed,
                    "remaining_devices": [],
                },
            })
            return EXIT_OK

        missing = [n for n in names if n not in devices]
        if missing:
            self._write_json({
                "ok": False,
                "error": {
                    "code": "not_found",
                    "kind": "device_not_found",
                    "message": "device(s) not saved in {0}: {1}".format(config_path, ", ".join(missing)),
                    "details": {"missing": missing},
                },
            })
            return EXIT_NOTFOUND

        remaining = dict(devices)
        for name in names:
            del remaining[name]
        payload["devices"] = remaining
        self._write_config_file(config_path, payload)

        result = {
            "ok": True,
            "data": {
                "config_path": config_path,
                "removed": list(names),
                "remaining_devices": sorted(remaining.keys()),
            },
        }
        if len(names) == 1:
            result["device_id"] = names[0]
        self._write_json(result)
        return EXIT_OK

    def _run_session_manager(self, options):
        try:
            session_request = _read_json_file(options.session_request_file)
            _safe_unlink(options.session_request_file)
            bridge = self._create_session_bridge(session_request)
            idle_timeout_sec = session_request.get("idle_timeout_sec", DEFAULT_SESSION_IDLE_TIMEOUT_SEC)
            if not isinstance(idle_timeout_sec, int) or idle_timeout_sec <= 0:
                raise ConfigError("idle_timeout_sec must be a positive integer")
        except ConfigError as exc:
            _write_private_json(
                options.session_state_file,
                {
                    "error": {
                        "kind": "session_start_failed",
                        "message": str(exc),
                    }
                },
            )
            return EXIT_BADARGS
        except Exception as exc:
            _write_private_json(
                options.session_state_file,
                {
                    "error": {
                        "kind": "session_start_failed",
                        "message": str(exc) or "Unable to start the session manager",
                    }
                },
            )
            return EXIT_ERROR

        manager = _RouterCliSessionManager(
            self,
            bridge,
            options.session_state_file,
            idle_timeout_sec=idle_timeout_sec,
        )
        try:
            return manager.serve()
        except Exception as exc:
            _write_private_json(
                options.session_state_file,
                {
                    "error": {
                        "kind": "session_runtime_failed",
                        "message": str(exc) or "Session manager exited unexpectedly",
                    }
                },
            )
            return EXIT_ERROR

    def _create_session_bridge(self, session_request):
        if not isinstance(session_request, dict):
            raise ConfigError("session request must be a JSON object")

        config_data = session_request.get("config_data")
        base_dir = session_request.get("base_dir")
        if not isinstance(base_dir, str) or not base_dir:
            raise ConfigError("session request was missing base_dir")

        return SSHBridge.from_config_data(
            config_data,
            base_dir=base_dir,
            takeover=bool(session_request.get("takeover")),
            start_renew_thread=True,
        )

    def _execute_validated_public_call(self, bridge, validated):
        server = CommandSurface(bridge)
        if validated.get("local_upgrade_file") is not None:
            return self._execute_upgrade_file(server, bridge, validated)

        outcome = server._execute_validated_call(validated)
        return server._public_outcome(outcome)

    def _execute_validated_via_session(self, options, bridge, validated):
        session_request = self._build_session_request(options, bridge, validated)
        paths = self._build_session_paths(
            session_request["runtime_dir"],
            session_request["config_data"],
            session_request["device_id"],
        )
        request_timeout_sec = self._session_request_timeout_sec(bridge, validated)
        request_payload = {
            "action": "execute",
            "validated": validated,
        }

        try:
            return self._request_existing_session(paths, request_payload, request_timeout_sec)
        except _SessionUnavailableError:
            self._clear_session_state(paths)
        except _SessionManagerError as exc:
            if exc.kind in ("session_start_failed", "session_runtime_failed"):
                self._clear_session_state(paths)
            else:
                return self._session_error_outcome(validated, exc.kind, exc.message)

        try:
            with _SessionStartLock(paths.start_lock_file, DEFAULT_SESSION_STARTUP_TIMEOUT_SEC):
                try:
                    return self._request_existing_session(paths, request_payload, request_timeout_sec)
                except _SessionManagerError as exc:
                    if exc.kind in ("session_start_failed", "session_runtime_failed"):
                        self._clear_session_state(paths)
                    else:
                        return self._session_error_outcome(validated, exc.kind, exc.message)
                except _SessionUnavailableError:
                    self._clear_session_state(paths)

                self._start_session_manager(paths, session_request)
                return self._wait_for_session_manager(paths, request_payload, request_timeout_sec)
        except _SessionManagerError as exc:
            return self._session_error_outcome(validated, exc.kind, exc.message)
        except (IOError, OSError, subprocess.SubprocessError, _SessionUnavailableError) as exc:
            return self._session_error_outcome(
                validated,
                "session_unavailable",
                str(exc) or "Unable to start or reach the local session manager",
            )

    def _build_session_request(self, options, bridge, validated):
        runtime_dir = self._resolve_runtime_dir(options.runtime_dir)
        return {
            "runtime_dir": runtime_dir,
            "device_id": validated["device_id"],
            "config_data": bridge._config,
            "base_dir": os.path.dirname(bridge.config_path),
            "takeover": bool(options.takeover),
            "idle_timeout_sec": DEFAULT_SESSION_IDLE_TIMEOUT_SEC,
        }

    def _build_session_paths(self, runtime_dir, config_data, device_id):
        return _RouterCliSessionPaths(
            runtime_dir,
            _build_session_key(config_data, device_id),
        )

    def _session_request_timeout_sec(self, bridge, validated):
        timeout_sec = validated.get("timeout_sec") or bridge.ssh_defaults["command_timeout_sec"]
        if validated.get("local_upgrade_file") is not None:
            timeout_sec = max(timeout_sec, DEFAULT_UPGRADE_TIMEOUT_SEC)
        return max(DEFAULT_SESSION_CONNECT_TIMEOUT_SEC, timeout_sec + 5)

    def _request_existing_session(self, paths, request_payload, timeout_sec):
        state = _load_session_state(paths)
        response = _request_session_manager(state, request_payload, timeout_sec)
        outcome = response.get("outcome")
        if not isinstance(outcome, dict):
            raise _SessionProtocolError("Session manager response was missing the command outcome")
        return outcome

    def _wait_for_session_manager(self, paths, request_payload, timeout_sec):
        deadline = time.monotonic() + DEFAULT_SESSION_STARTUP_TIMEOUT_SEC
        last_error = None
        while time.monotonic() < deadline:
            try:
                return self._request_existing_session(paths, request_payload, timeout_sec)
            except _SessionUnavailableError as exc:
                last_error = exc
                time.sleep(0.05)

        raise _SessionUnavailableError(
            str(last_error) if last_error is not None else "Timed out waiting for the session manager to start"
        )

    def _start_session_manager(self, paths, session_request):
        _write_private_json(paths.request_file, session_request)
        command = self._build_session_manager_command(paths)
        env = os.environ.copy()
        popen_kwargs = {
            "close_fds": True,
            "env": env,
        }

        if os.name != "nt":
            popen_kwargs["start_new_session"] = True

        # PyInstaller onefile children must reset their bootloader environment so
        # they unpack into an independent temp dir instead of pinning the parent's
        # _MEI directory and blocking process exit on Windows.
        if getattr(sys, "frozen", False):
            env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"

        if os.name == "nt":
            creationflags = 0
            create_new_process_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            creationflags |= create_new_process_group | create_no_window
            if creationflags:
                popen_kwargs["creationflags"] = creationflags

            startupinfo_factory = getattr(subprocess, "STARTUPINFO", None)
            startf_use_show_window = getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
            sw_hide = getattr(subprocess, "SW_HIDE", 0)
            if startupinfo_factory is not None and startf_use_show_window:
                startupinfo = startupinfo_factory()
                startupinfo.dwFlags |= startf_use_show_window
                startupinfo.wShowWindow = sw_hide
                popen_kwargs["startupinfo"] = startupinfo

        with open(os.devnull, "rb") as devnull_in:
            with open(os.devnull, "ab") as devnull_out:
                subprocess.Popen(
                    command,
                    stdin=devnull_in,
                    stdout=devnull_out,
                    stderr=devnull_out,
                    **popen_kwargs
                )

    def _build_session_manager_command(self, paths):
        command = self._build_self_command()
        command.extend(
            [
                "__sessiond",
                "--session-state-file",
                paths.state_file,
                "--session-request-file",
                paths.request_file,
            ]
        )
        return command

    def _build_self_command(self):
        if getattr(sys, "frozen", False):
            return [sys.executable]
        module_entrypoint = os.path.join(os.path.dirname(os.path.abspath(__file__)), "__main__.py")
        return [sys.executable, module_entrypoint]

    def _clear_session_state(self, paths):
        _safe_unlink(paths.state_file)
        _safe_unlink(paths.request_file)

    def _session_error_outcome(self, validated, kind, message):
        return self._build_local_error_outcome(
            device_id=validated.get("device_id"),
            command=validated.get("command"),
            code="internal",
            kind=kind,
            message=message if isinstance(message, str) and message else "Local session manager request failed",
        )

    def _default_password_reader(self, prompt):
        return getpass.getpass(prompt=prompt, stream=self.stderr)

    def _collect_auth_options(self, options, existing_names=None):
        if existing_names is None:
            existing_names = set()

        prompt_all_auth_fields = (
            options.device_ip is None
            and options.port is None
            and options.user is None
            and options.password is None
        )

        if options.device_ip is None or options.password is None:
            self.stderr.write(
                "Set up access to a device. Use the same username and password you use\n"
                "to log into the device's web admin page. agent-cli only uses them once\n"
                "to install an SSH key, then connects as the agent user.\n\n"
            )
            self.stderr.flush()

        options.device_ip = self._resolve_auth_text_option(
            options.device_ip,
            "Device IP address",
            prompt_if_missing=True,
            error_message="auth host must be a non-empty string",
        )
        options.port = self._resolve_auth_port_option(options.port, prompt_if_missing=prompt_all_auth_fields)
        options.user = self._resolve_auth_text_option(
            options.user,
            "Web login username",
            default=DEFAULT_BOOTSTRAP_USER,
            prompt_if_missing=prompt_all_auth_fields,
            error_message="auth bootstrap user must be a non-empty string",
        )
        options.password = self._resolve_auth_password_option(options.password)

        if options.agent_user is None:
            options.agent_user = DEFAULT_AGENT_USER
        elif isinstance(options.agent_user, str):
            options.agent_user = options.agent_user.strip()
        if not options.agent_user:
            raise ConfigError("auth agent user must be a non-empty string")

        options.name = self._resolve_auth_device_name(
            options.name,
            options.device_ip,
            existing_names=existing_names,
            overwrite=bool(getattr(options, "overwrite", False)),
            prompt_if_missing=prompt_all_auth_fields,
        )

    def _resolve_auth_text_option(self, value, label, default=None, prompt_if_missing=False, error_message=None):
        if value is None:
            if default is not None and not prompt_if_missing:
                return default
            return self._prompt_required_auth_text(label, default=default)

        normalized = value.strip() if isinstance(value, str) else ""
        if normalized:
            return normalized

        raise ConfigError(error_message or "{0} must be a non-empty string".format(label.lower()))

    def _resolve_auth_port_option(self, value, prompt_if_missing=False):
        if value is None:
            if not prompt_if_missing:
                return DEFAULT_SSH_PORT
            while True:
                raw = self._prompt_required_auth_text("SSH port", default=str(DEFAULT_SSH_PORT))
                try:
                    port = int(raw)
                except ValueError:
                    self.stderr.write("Port must be a positive integer.\n")
                    continue
                if port > 0:
                    return port
                self.stderr.write("Port must be a positive integer.\n")

        if value <= 0:
            raise ConfigError("auth port must be a positive integer")
        return value

    def _resolve_auth_password_option(self, value):
        if value is None:
            return self._prompt_required_auth_text("Web login password", secret=True)
        if value:
            return value
        raise ConfigError("auth password must be a non-empty string")

    def _resolve_auth_device_name(self, value, host, existing_names, overwrite, prompt_if_missing):
        if value is not None:
            normalized = value.strip() if isinstance(value, str) else ""
            if not normalized:
                raise ConfigError("auth device name must be a non-empty string")
            if normalized in existing_names and not overwrite:
                raise ConfigError(
                    "device {0!r} already exists in the config file; "
                    "pass --overwrite to replace it, or use `auth remove {0}` first".format(normalized)
                )
            return normalized

        if not prompt_if_missing:
            default = host
            if default in existing_names and not overwrite:
                raise ConfigError(
                    "device {0!r} already exists in the config file; "
                    "pass --name to choose a different name, --overwrite to replace it, "
                    "or use `auth remove {0}` first".format(default)
                )
            return default

        while True:
            candidate = self._prompt_required_auth_text("Device name", default=host)
            if candidate not in existing_names or overwrite:
                return candidate
            if self._prompt_yes_no(
                "Device {0!r} already exists. Overwrite?".format(candidate)
            ):
                return candidate

    def _prompt_yes_no(self, label):
        prompt = "{0} [y/N]: ".format(label)
        self.stderr.write(prompt)
        self.stderr.flush()
        value = self.stdin.readline()
        if value == "":
            raise ConfigError("authentication input cancelled")
        answer = value.rstrip("\r\n").strip().lower()
        return answer in ("y", "yes")

    def _read_existing_device_names(self, config_path):
        if not os.path.exists(config_path):
            return set()
        try:
            with open(config_path, "r") as handle:
                payload = json.load(handle)
        except (IOError, OSError, ValueError):
            return set()
        if not isinstance(payload, dict):
            return set()
        devices = payload.get("devices")
        if not isinstance(devices, dict):
            return set()
        return set(devices.keys())

    def _prompt_required_auth_text(self, label, default=None, secret=False):
        while True:
            value = self._prompt_auth_text(label, default=default, secret=secret)
            if value:
                return value
            print("Configuration error: {0} cannot be empty".format(label.lower()), file=self.stderr)

    def _prompt_auth_text(self, label, default=None, secret=False):
        prompt = "{0}: ".format(label)
        if default is not None:
            prompt = "{0} [{1}]: ".format(label, default)

        if secret:
            try:
                value = self._password_reader(prompt)
            except (EOFError, KeyboardInterrupt):
                raise ConfigError("authentication input cancelled")
        else:
            self.stderr.write(prompt)
            self.stderr.flush()
            value = self.stdin.readline()
            if value == "":
                raise ConfigError("authentication input cancelled")
            value = value.rstrip("\r\n").strip()

        if not value and default is not None:
            return default
        return value

    def _validate_command(self, server, options):
        arguments = {}
        if options.device_id is not None:
            arguments["device_id"] = options.device_id
        if options.timeout_sec is not None:
            arguments["timeout_sec"] = options.timeout_sec

        if options.command_name == "status":
            subcommand = _join_args(options.command_args)
            if subcommand is not None:
                arguments["subcommand"] = subcommand
            return server._validate_status_arguments(arguments)
        if options.command_name == "config":
            arguments["subcommand"] = _join_required_args(options.command_args)
            return server._validate_config_arguments(arguments)
        if options.command_name == "log":
            subcommand = _join_args(options.command_args)
            if subcommand is not None:
                arguments["subcommand"] = subcommand
            return server._validate_category_tool_arguments(server._find_tool_spec("log"), arguments)
        if options.command_name == "schema":
            arguments["subcommand"] = _join_required_args(options.command_args)
            return server._validate_schema_arguments(arguments)
        if options.command_name == "tool":
            arguments["subcommand"] = _join_required_args(options.command_args)
            return server._validate_tool_wrapper_arguments(arguments)
        if options.command_name == "reboot":
            return server._validate_category_tool_arguments(server._find_tool_spec("reboot"), arguments)
        if options.command_name == "upgrade":
            if options.url is not None:
                arguments["source_type"] = "url"
                arguments["url"] = options.url
            else:
                arguments["source_type"] = "file"
                arguments["file_path"] = options.file
            return server._validate_upgrade_arguments(arguments)

        raise JSONRPCError(ERR_INVALID_PARAMS, "Unknown command")

    def _execute_upgrade_file(self, server, bridge, validated):
        raw_local_path = validated["local_upgrade_file"]
        timeout_sec = validated.get("timeout_sec")
        device_id = validated["device_id"]
        public_command = validated["command"]

        try:
            local_path, translated_path = self._resolve_local_upgrade_path(raw_local_path)
        except (OSError, ValueError) as exc:
            return self._build_local_error_outcome(
                device_id=device_id,
                command=public_command,
                code="bad_args",
                kind="local_file_invalid",
                message="Failed to inspect local upgrade file `{0}`: {1}".format(raw_local_path, exc),
            )

        try:
            path_exists = os.path.exists(local_path)
            if not path_exists and translated_path is not None:
                path_exists = os.path.exists(translated_path)
                if path_exists:
                    local_path = translated_path
        except (OSError, ValueError) as exc:
            return self._build_local_error_outcome(
                device_id=device_id,
                command=public_command,
                code="bad_args",
                kind="local_file_invalid",
                message="Failed to inspect local upgrade file `{0}`: {1}".format(raw_local_path, exc),
            )

        if not path_exists:
            checked_paths = [local_path]
            if translated_path is not None and translated_path != local_path:
                checked_paths.append(translated_path)
            return self._build_local_error_outcome(
                device_id=device_id,
                command=public_command,
                code="bad_args",
                kind="local_file_not_found",
                message="Local upgrade file does not exist: {0}. Checked: {1}".format(
                    raw_local_path,
                    ", ".join(checked_paths),
                ),
            )
        if not os.path.isfile(local_path):
            return self._build_local_error_outcome(
                device_id=device_id,
                command=public_command,
                code="bad_args",
                kind="local_file_invalid",
                message="Local upgrade file is not a regular file: {0}".format(local_path),
            )
        if not os.access(local_path, os.R_OK):
            return self._build_local_error_outcome(
                device_id=device_id,
                command=public_command,
                code="bad_args",
                kind="local_file_unreadable",
                message="Local upgrade file is not readable: {0}".format(local_path),
            )

        try:
            bridge._ensure_binding(device_id)
        except BootstrapError as exc:
            return self._build_local_error_outcome(
                device_id=device_id,
                command=public_command,
                code=self._bridge_error_code(exc.kind),
                kind=exc.kind,
                message=exc.message,
            )

        profile = bridge.devices[device_id]
        timeout = timeout_sec or max(
            bridge.ssh_defaults["command_timeout_sec"],
            DEFAULT_UPGRADE_TIMEOUT_SEC,
        )
        host_header = profile["device_ip"]

        try:
            with self._open_api_tunnel(bridge, device_id, timeout) as tunnel:
                token = self._api_login(
                    tunnel,
                    host_header,
                    profile["user"],
                    profile["pass"],
                    timeout,
                )
                self._api_upload_firmware(
                    tunnel,
                    host_header,
                    token,
                    local_path,
                    timeout,
                )
                upgrade_payload = self._api_trigger_upgrade(
                    tunnel,
                    host_header,
                    token,
                    timeout,
                )
        except _SSHTunnelError as exc:
            return self._build_local_error_outcome(
                device_id=device_id,
                command=public_command,
                code="transport_error",
                kind="ssh_tunnel_error",
                message=exc.message,
                stderr=exc.stderr,
            )
        except _HTTPAPIError as exc:
            return self._build_local_error_outcome(
                device_id=device_id,
                command=public_command,
                code=exc.code,
                kind=exc.kind,
                message=exc.message,
                stderr=exc.stderr,
            )
        except Exception as exc:
            return self._build_local_error_outcome(
                device_id=device_id,
                command=public_command,
                code="internal",
                kind="upgrade_internal_error",
                message=str(exc) or "Upgrade failed unexpectedly",
            )

        return {
            "device_id": device_id,
            "command": public_command,
            "ok": True,
            "ssh_exit_code": None,
            "data": upgrade_payload,
            "stderr": None,
            "error": None,
        }

    def _open_api_tunnel(self, bridge, device_id, timeout_sec):
        return _SSHAPITunnel(
            bridge,
            device_id,
            "127.0.0.1",
            DEFAULT_AGENT_API_PORT,
            timeout_sec=timeout_sec,
        )

    def _api_login(self, tunnel, host_header, username, password, timeout_sec):
        payload = self._http_json_request(
            tunnel,
            "POST",
            "/api/v1/user/login",
            {"Host": host_header},
            {"username": username, "password": password},
            timeout_sec,
        )
        result = payload.get("result") if isinstance(payload, dict) else None
        token = result.get("token") if isinstance(result, dict) else None
        if not isinstance(token, str) or not token:
            raise _HTTPAPIError(
                "unauthorized",
                "http_login_invalid_response",
                "Login response did not include a token",
            )
        return token

    def _api_upload_firmware(self, tunnel, host_header, token, local_path, timeout_sec):
        boundary = "----------------agent-cli-{0}-{1}".format(os.getpid(), int(time.time()))
        filename = _upload_filename(local_path)
        file_size = os.path.getsize(local_path)
        preamble = (
            "--{0}\r\n"
            "Content-Disposition: form-data; name=\"file\"; filename=\"{1}\"\r\n"
            "Content-Type: application/octet-stream\r\n"
            "\r\n"
        ).format(boundary, filename).encode("utf-8")
        epilogue = ("\r\n--{0}--\r\n".format(boundary)).encode("utf-8")
        content_length = len(preamble) + file_size + len(epilogue)

        connection = tunnel.open_http_connection(timeout_sec)
        try:
            connection.putrequest(
                "POST",
                "/api/v1/import/firmware",
                skip_host=True,
                skip_accept_encoding=True,
            )
            connection.putheader("Host", host_header)
            connection.putheader("Remote-Addr", LOCAL_API_REMOTE_ADDR)
            connection.putheader("Accept", "*/*")
            connection.putheader("Authorization", "Bearer {0}".format(token))
            connection.putheader("Connection", "keep-alive")
            connection.putheader("Content-Type", "multipart/form-data; boundary={0}".format(boundary))
            connection.putheader("Content-Length", str(content_length))
            connection.putheader("Origin", "https://{0}".format(host_header))
            connection.putheader("Referer", "https://{0}/".format(host_header))
            connection.putheader("X-Requested-With", "XMLHttpRequest")
            connection.endheaders()
            connection.send(preamble)
            with open(local_path, "rb") as handle:
                while True:
                    chunk = handle.read(64 * 1024)
                    if not chunk:
                        break
                    connection.send(chunk)
            connection.send(epilogue)
            return self._read_http_response(connection, "upload")
        except _SSHStreamError as exc:
            early_error = self._try_read_upload_error_response(connection)
            if early_error is not None:
                raise early_error
            raise _SSHTunnelError(exc.args[0] if exc.args else "SSH tunnel request failed", stderr=exc.stderr)
        except (OSError, http.client.HTTPException, ValueError) as exc:
            early_error = self._try_read_upload_error_response(connection)
            if early_error is not None:
                raise early_error
            raise _HTTPAPIError("transport_error", "http_upload_transport_error", str(exc) or "Firmware upload failed")
        finally:
            connection.close()

    def _api_trigger_upgrade(self, tunnel, host_header, token, timeout_sec):
        return self._http_json_request(
            tunnel,
            "POST",
            "/api/v1/upgrade",
            {
                "Host": host_header,
                "Authorization": "Bearer {0}".format(token),
            },
            {},
            timeout_sec,
        )

    def _http_json_request(self, tunnel, method, path, headers, payload, timeout_sec):
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        step = "login" if path == "/api/v1/user/login" else "upgrade"
        merged_headers = {
            "Accept": "*/*",
            "Content-Type": "application/json",
            "Connection": "keep-alive",
            "Remote-Addr": LOCAL_API_REMOTE_ADDR,
            "X-Requested-With": "XMLHttpRequest",
        }
        merged_headers.update(headers)
        host_header = merged_headers.get("Host")
        if isinstance(host_header, str) and host_header:
            merged_headers.setdefault("Origin", "https://{0}".format(host_header))
            merged_headers.setdefault("Referer", "https://{0}/".format(host_header))
        connection = tunnel.open_http_connection(timeout_sec)
        try:
            connection.request(method, path, body=body, headers=merged_headers)
            return self._read_http_response(connection, step)
        except _SSHStreamError as exc:
            raise _SSHTunnelError(exc.args[0] if exc.args else "SSH tunnel request failed", stderr=exc.stderr)
        except (OSError, http.client.HTTPException) as exc:
            kind = "http_login_transport_error" if step == "login" else "http_upgrade_transport_error"
            raise _HTTPAPIError("transport_error", kind, str(exc) or "HTTP request failed")
        finally:
            connection.close()

    def _try_read_upload_error_response(self, connection):
        try:
            self._read_http_response(connection, "upload")
        except _HTTPAPIError as exc:
            return exc
        except (_SSHStreamError, OSError, http.client.HTTPException, ValueError):
            return None
        return None

    def _read_http_response(self, connection, step):
        response = connection.getresponse()
        raw = response.read()
        payload = None
        text = raw.decode("utf-8", "replace").strip() if raw else ""

        if text:
            try:
                payload = json.loads(text)
            except ValueError:
                raise _HTTPAPIError(
                    "internal",
                    "http_{0}_invalid_json".format(step),
                    "HTTP {0} response was not valid JSON".format(step),
                    stderr=text,
                )

        if response.status < 200 or response.status >= 300:
            raise self._http_api_error(step, response.status, payload, text)

        if isinstance(payload, dict) and isinstance(payload.get("error"), str) and payload.get("error"):
            raise self._http_api_error(step, response.status, payload, text)

        if payload is None:
            raise _HTTPAPIError(
                "internal",
                "http_{0}_empty_response".format(step),
                "HTTP {0} response was empty".format(step),
            )

        return payload

    def _http_api_error(self, step, http_status, payload, text):
        message = None
        if isinstance(payload, dict) and isinstance(payload.get("error"), str) and payload.get("error"):
            message = payload.get("error")
        elif text:
            message = text
        else:
            message = "HTTP {0} request failed with status {1}".format(step, http_status)

        if step == "login":
            if http_status in (401, 403) or "password" in message.lower() or "authorization" in message.lower():
                code = "unauthorized"
            else:
                code = "bad_args" if http_status == 400 else "internal"
        elif http_status in (401, 403):
            code = "unauthorized"
        else:
            code = "internal"

        return _HTTPAPIError(
            code,
            "http_{0}_failed".format(step),
            message,
            stderr=text or None,
        )

    def _open_bridge(self, options):
        runtime_dir = self._resolve_runtime_dir(options.runtime_dir)
        if options.device:
            if options.config is not None:
                raise ConfigError("--config cannot be used together with --device")
            inline_config = build_inline_config(options.device, runtime_dir)
            return SSHBridge.from_config_data(
                inline_config,
                base_dir=runtime_dir,
                takeover=options.takeover,
                start_renew_thread=False,
            )

        config_path = self._resolve_config_path(options.config, runtime_dir)
        if not os.path.exists(config_path):
            raise ConfigError(
                "config file does not exist: {0}. Run `agent-cli auth` first, or use --device.".format(
                    config_path
                )
            )
        return SSHBridge(config_path, takeover=options.takeover, start_renew_thread=False)

    def _write_public_outcome(self, outcome):
        self._write_json(outcome)
        if outcome.get("ok"):
            return EXIT_OK
        return self._exit_code_from_error_code(outcome.get("error", {}).get("code"))

    def _build_local_error_outcome(self, device_id, command, code, kind, message, stderr=None):
        return {
            "device_id": device_id,
            "command": command,
            "ok": False,
            "ssh_exit_code": None,
            "data": None,
            "stderr": stderr,
            "error": {
                "code": code,
                "kind": kind,
                "message": message,
            },
        }

    def _bridge_error_code(self, kind):
        if kind in ("bootstrap_auth_error",):
            return "unauthorized"
        if kind in ("bootstrap_conflict",):
            return "conflict"
        if kind in ("bootstrap_transport_error",):
            return "transport_error"
        return "internal"

    def _exit_code_from_error_code(self, code):
        if code in ("2", "not_found"):
            return EXIT_NOTFOUND
        if code in ("3", "timeout"):
            return EXIT_TIMEOUT
        if code in ("4", "bad_args"):
            return EXIT_BADARGS
        return EXIT_ERROR

    def _resolve_runtime_dir(self, value):
        runtime_dir = value or DEFAULT_RUNTIME_DIR
        return os.path.abspath(os.path.expanduser(runtime_dir))

    def _resolve_config_path(self, value, runtime_dir):
        if value:
            return os.path.abspath(os.path.expanduser(value))
        return os.path.join(runtime_dir, DEFAULT_CONFIG_FILE_NAME)

    def _resolve_local_upgrade_path(self, raw_path):
        local_path = os.path.abspath(os.path.expanduser(raw_path))
        translated_path = None

        if os.name != "nt":
            translated_path = _windows_drive_path_to_posix_mount(raw_path)
            if translated_path is not None:
                translated_path = os.path.abspath(os.path.expanduser(translated_path))

        return local_path, translated_path

    def _build_auth_device_spec(self, options, device_name):
        parts = [
            "name={0}".format(device_name),
            "device_ip={0}".format(options.device_ip),
            "pass={0}".format(options.password),
            "user={0}".format(options.user),
            "agent_user={0}".format(options.agent_user),
            "port={0}".format(options.port),
        ]
        return ",".join(parts)

    def _merge_auth_config(self, config_path, runtime_dir, device_name, options):
        if os.path.exists(config_path):
            with open(config_path, "r") as handle:
                try:
                    payload = json.load(handle)
                except ValueError as exc:
                    raise ConfigError("Unable to load config {0}: {1}".format(config_path, exc))
        else:
            payload = {}

        if not isinstance(payload, dict):
            raise ConfigError("Top-level config must be a JSON object")

        ssh_defaults = payload.get("ssh_defaults", {})
        devices = payload.get("devices", {})
        if ssh_defaults and not isinstance(ssh_defaults, dict):
            raise ConfigError("ssh_defaults must be an object")
        if devices and not isinstance(devices, dict):
            raise ConfigError("devices must be an object")

        payload["ssh_defaults"] = {
            "keys_base_dir": os.path.join(runtime_dir, "keys"),
            "control_path_dir": os.path.join(runtime_dir, "ssh-control"),
        }
        payload["devices"] = dict(devices)
        payload["devices"][device_name] = {
            "device_ip": options.device_ip,
            "agent_user": options.agent_user,
            "user": options.user,
            "pass": options.password,
            "port": options.port,
        }
        return payload

    def _write_config_file(self, config_path, payload):
        parent = os.path.dirname(config_path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)

        with open(config_path, "w") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")

        if os.name == "posix":
            os.chmod(config_path, stat.S_IRUSR | stat.S_IWUSR)

    def _write_json(self, payload):
        json.dump(payload, self.stdout, separators=(",", ":"), sort_keys=True)
        self.stdout.write("\n")
        self.stdout.flush()

    def _render_general_help(self):
        return textwrap.dedent(
            """\
            agent-cli commands:
              auth                      Bootstrap SSH key access and save local config
              auth list                 List saved devices in the config file
              auth remove <name>...     Remove one or more saved devices (use --all to remove every device)
              help [topic]              Show general help or help for one topic
              status [<key>|list]       Read all status, list status keys, or read one status key
              config <subcommand>       Discover config roots, read one key, or write one root payload
              log [<service>]           Read default logs, list services, or read one service with --line
              schema <subcommand>       List schema roots, read one root schema, or show validation rules
              tool <subcommand>         List tools or run <tool_name> <json_payload>
              upgrade --url <url>       Ask the device to download firmware from an HTTP(S) URL
              upgrade --file <path>     Upload a Windows local firmware file through the local API tunnel
              reboot                    Reboot the device

            Global options:
              --config <path>           Read saved devices from a config file
              --device <spec>           Inline device spec: name=<id>,device_ip=<ip>,pass=<password>[,user=<web_user>][,agent_user=<agent_user>][,port=<port>] (`pass=` is visible in process arguments)
              --runtime-dir <path>      Runtime directory for keys, known_hosts, and default config
              --device-id <id>          Select the target device when multiple devices are configured
              --timeout-sec <sec>       Per-command SSH timeout override
              --takeover                Force takeover of the current key lease or session

            Topics:
              auth, status, config, log, schema, tool, upgrade, reboot
            """
        )

    def _render_auth_help(self):
        return textwrap.dedent(
            """\
            Usage:
              agent-cli auth [--device-ip <ip>] [--port <port>] [--user <web_user>] [--pass <password>] [--name <device_name>] [--agent-user <agent_user>] [--takeover] [--overwrite]
              agent-cli auth list
              agent-cli auth remove <name> [<name>...]
              agent-cli auth remove --all

            Behavior:
              `agent-cli auth` with no auth flags prompts for device IP address, SSH port, web login username and password, and the device name to save it under.
              Missing values still use defaults for --port, --user, and the device name (defaults to the device IP), and prompt for a missing device IP or password.
              `--pass` is kept for compatibility with existing scripts, but the password is visible in process arguments while the command runs.
              If the chosen device name already exists in the config file, interactive runs ask before overwriting; non-interactive runs abort unless --overwrite is given.
              `auth list` prints the device entries saved in the config file (passwords are never returned).
              `auth remove <name>...` deletes one or more device entries; the operation is all-or-nothing and aborts if any name is unknown.
              `auth remove --all` deletes every saved device entry. SSH key files under the runtime directory are left in place.

            Examples:
              agent-cli auth
              agent-cli auth --device-ip 192.0.2.10 --name lab-a
              agent-cli auth --device-ip 192.0.2.10 --name lab-a --overwrite
              agent-cli auth list
              agent-cli auth remove lab-a
              agent-cli auth remove lab-a lab-b
              agent-cli auth remove --all
            """
        )

    def _render_status_help(self):
        return textwrap.dedent(
            """\
            Usage:
              agent-cli status
              agent-cli status list
              agent-cli status <key>

            Behavior:
              No subcommand reads the aggregated status view for all available status roots.
              `status list` returns the available status keys.
              `status <key>` reads one key such as `basic`, `cellular`, or `wan`.

            Examples:
              agent-cli status
              agent-cli status basic
              agent-cli status cellular
            """
        )

    def _render_config_help(self):
        return textwrap.dedent(
            """\
            Usage:
              agent-cli config list
              agent-cli config get <key>
              agent-cli config set <root> <json_payload>

            Behavior:
              `config list` returns the available config roots.
              `config get <key>` accepts a query key such as `system.hostname`.
              `config set <root> <json_payload>` only accepts a root key such as `system`; the JSON payload is wrapped under that root automatically.

            Examples:
              agent-cli config list
              agent-cli config get system.hostname
              agent-cli config set system {"hostname":"lab-a"}
            """
        )

    def _render_log_help(self):
        return textwrap.dedent(
            """\
            Usage:
              agent-cli log
              agent-cli log --line <count>
              agent-cli log list
              agent-cli log <service> [--line <count>]

            Behavior:
              With no service, `log` reads the default `message` log.
              `log list` returns the available services.
              `--line` can be used with the default `message` log or with one named service.

            Examples:
              agent-cli log
              agent-cli log --line 200
              agent-cli log NetworkManager --line 100
            """
        )

    def _render_schema_help(self):
        return textwrap.dedent(
            """\
            Usage:
              agent-cli schema list
              agent-cli schema <key>
              agent-cli schema <root> --validation

            Behavior:
              `schema list` returns schema roots with descriptions.
              `schema <key>` reads the schema for one root key.
              `schema <root> --validation` only accepts a root key; nested paths such as `system.hostname` are not supported.

            Examples:
              agent-cli schema list
              agent-cli schema cellular
              agent-cli schema system --validation
            """
        )

    def _render_tool_help(self):
        return textwrap.dedent(
            """\
            Usage:
              agent-cli tool list
              agent-cli tool <tool_name> <json_payload>

            Behavior:
              `tool list` returns the supported diagnostics. Current known tools are `ping`, `traceroute`, `tcpdump`, `iperf`, and `speedtest`.
              The payload must be a single JSON object string. Do not invent tool names or payload shapes; use `tool list` first when possible.
              Long-running tools usually follow `start`, `status`, output polling, and `stop`.
              `speedtest` is exposed through `tool` but is translated to the backend speedtest session commands.

            Examples:
              agent-cli tool list
              agent-cli tool ping {"action":"start","host":"8.8.8.8"}
              agent-cli tool ping {"action":"status"}
              agent-cli tool ping {"start_line":0}
              agent-cli tool traceroute {"action":"start","host":"8.8.8.8"}
              agent-cli tool tcpdump {"action":"start","capture_mode":"show","capture_time":300,"local_iface":[{"interface":"wan1","expert_options":""}]}
              agent-cli tool iperf {"action":"start","role":"client","command":"198.51.100.10","capture_time":10}
              agent-cli tool speedtest {"action":"servers"}
              agent-cli tool speedtest {"action":"start","server_id":12345,"ip":"198.51.100.10"}
              agent-cli tool speedtest {"action":"status"}
              agent-cli tool speedtest {"action":"output","start_line":0}
              agent-cli tool speedtest {"action":"stop"}
            """
        )

    def _render_upgrade_help(self):
        return textwrap.dedent(
            """\
            Usage:
              agent-cli upgrade --url <http_or_https_url>
              agent-cli upgrade --file <windows_local_file>

            Behavior:
              `--url` forwards a device-side firmware download URL and should be an HTTP or HTTPS URL.
              `--file` is the agent-cli special case: it treats the argument as a Windows local firmware path and uploads it through the local API tunnel before triggering the upgrade.

            Examples:
              agent-cli upgrade --url https://example.test/fw.bin
              agent-cli upgrade --file C:\\firmware\\fw.bin
            """
        )

    def _render_reboot_help(self):
        return textwrap.dedent(
            """\
            Usage:
              agent-cli reboot

            Behavior:
              Reboots the target device immediately.
            """
        )

    def _try_collect_dynamic_help(self, domain, options):
        list_commands = {
            "status": "status list",
            "config": "config list",
            "log": "log list",
            "schema": "schema list",
            "tool": "tool list",
        }
        command = list_commands.get(domain)
        if command is None:
            return ""

        try:
            bridge = self._open_bridge(options)
        except ConfigError:
            return ""

        try:
            server = CommandSurface(bridge)
            validated = {
                "device_id": server._resolve_device_id(
                    {"device_id": options.device_id} if options.device_id else {}
                ),
                "command": command,
            }
            public = self._execute_validated_via_session(
                options,
                bridge,
                validated,
            )
            if not public.get("ok"):
                return ""
            return self._format_dynamic_list(domain, public.get("data"))
        except Exception:
            return ""
        finally:
            bridge.close()

    def _format_dynamic_list(self, domain, data):
        if not isinstance(data, dict):
            return ""
        result = data.get("result")
        if not isinstance(result, dict):
            return ""

        key_map = {
            "status": "status_keys",
            "config": "config_keys",
            "log": "services",
            "schema": "schemas",
            "tool": "tools",
        }
        items = result.get(key_map[domain])
        if not isinstance(items, list) or not items:
            return ""

        lines = ["Available {0}:".format(domain)]
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("key") or item.get("service") or item.get("name")
            if not isinstance(name, str):
                continue
            description = item.get("description")
            if isinstance(description, str) and description:
                lines.append("  {0}: {1}".format(name, description))
            else:
                lines.append("  {0}".format(name))
        if len(lines) == 1:
            return ""
        return "\n".join(lines) + "\n"


def _join_args(parts):
    if not parts:
        return None
    joined = " ".join(parts).strip()
    return joined or None


def _join_required_args(parts):
    joined = _join_args(parts)
    if joined is None:
        raise JSONRPCError(ERR_INVALID_PARAMS, "subcommand must be a non-empty string")
    return joined


def _windows_drive_path_to_posix_mount(path):
    if not isinstance(path, str):
        return None
    if len(path) < 3 or path[1] != ":" or not path[0].isalpha() or path[2] not in ("\\", "/"):
        return None

    drive_letter = path[0].lower()
    suffix = path[2:].replace("\\", "/").lstrip("/")
    return os.path.join("/mnt", drive_letter, suffix)


def _upload_filename(path):
    filename = os.path.basename(path)
    windows_filename = ntpath.basename(path)
    if filename == path and windows_filename:
        return windows_filename
    return filename


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Windows-oriented agent-cli wrapper for remote agent_cli access.",
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="store_true", dest="_ignored_help", help=argparse.SUPPRESS)
    parser.add_argument("--config", default=None, help="Path to a saved agent-cli device config file.")
    parser.add_argument(
        "--device",
        action="append",
        default=[],
        help="Inline device definition: name=<id>,device_ip=<ip>,pass=<password>[,user=<web_user>][,agent_user=<agent_user>][,port=<port>]. The password is visible in process arguments while the command runs.",
    )
    parser.add_argument(
        "--runtime-dir",
        default=None,
        help="Runtime directory for generated SSH keys, known_hosts, and the default config file.",
    )
    parser.add_argument("--takeover", action="store_true", help="Force takeover when another client currently holds the device lease.")
    parser.add_argument("--device-id", default=None, help="Target device id when multiple devices are configured.")
    parser.add_argument("--timeout-sec", type=int, default=None, help="Optional per-command SSH timeout override in seconds.")

    subparsers = parser.add_subparsers(dest="command_name")
    subparsers.required = True

    auth_parser = subparsers.add_parser("auth", add_help=False, help="Bootstrap SSH access and store device configuration.")
    auth_parser.add_argument("-h", "--help", action="store_true", dest="_ignored_help", help=argparse.SUPPRESS)
    auth_parser.add_argument("--name", default=None, help="Local device name. Defaults to the device IP value.")
    auth_parser.add_argument("--device-ip", default=None, help="Device IP address. Prompted if omitted.")
    auth_parser.add_argument("--user", default=None, help="Web admin username used once to install the SSH key. Prompted if omitted; defaults to adm.")
    auth_parser.add_argument("--agent-user", default=DEFAULT_AGENT_USER, help="Runtime SSH username. Defaults to agent.")
    auth_parser.add_argument("--pass", dest="password", default=None, help="Web admin password. Supported for compatibility, but visible in process arguments while the command runs.")
    auth_parser.add_argument("--port", type=int, default=None, help="SSH port. Prompted if omitted; defaults to 22.")
    auth_parser.add_argument("--takeover", dest="auth_takeover", action="store_true", help="Force takeover if another client currently holds the key lease.")
    auth_parser.add_argument("--overwrite", action="store_true", help="Replace an existing device entry with the same name without confirmation.")
    auth_parser.set_defaults(auth_takeover=False, overwrite=False)
    auth_parser.add_argument("auth_args", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)

    sessiond_parser = subparsers.add_parser("__sessiond", add_help=False, help=argparse.SUPPRESS)
    sessiond_parser.add_argument("--session-state-file", required=True, help=argparse.SUPPRESS)
    sessiond_parser.add_argument("--session-request-file", required=True, help=argparse.SUPPRESS)

    help_parser = subparsers.add_parser("help", add_help=False, help="Show general help or help for a specific topic.")
    help_parser.add_argument("-h", "--help", action="store_true", dest="_ignored_help", help=argparse.SUPPRESS)
    help_parser.add_argument("domain", nargs="?", default=None)

    for name in ("status", "config", "log", "schema", "tool"):
        command_parser = subparsers.add_parser(name, add_help=False)
        command_parser.add_argument("-h", "--help", action="store_true", dest="_ignored_help", help=argparse.SUPPRESS)
        command_parser.add_argument("command_args", nargs=argparse.REMAINDER)

    upgrade_parser = subparsers.add_parser("upgrade", add_help=False)
    upgrade_parser.add_argument("-h", "--help", action="store_true", dest="_ignored_help", help=argparse.SUPPRESS)
    group = upgrade_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", default=None, help="HTTP or HTTPS firmware URL to fetch from the device.")
    group.add_argument("--file", default=None, help="Windows local firmware file path to upload before upgrade.")

    reboot_parser = subparsers.add_parser("reboot", add_help=False)
    reboot_parser.add_argument("-h", "--help", action="store_true", dest="_ignored_help", help=argparse.SUPPRESS)

    return parser.parse_args(argv)


def parse_help_args(argv):
    args = list(argv or [])
    if not args:
        return None

    global_options = _extract_help_global_options(args)
    remaining = global_options["remaining"]
    if not remaining:
        return None

    first_help_index = None
    for index, value in enumerate(remaining):
        if value in ("-h", "--help"):
            first_help_index = index
            break

    if first_help_index is None:
        if remaining[0] == "help":
            domain = remaining[1] if len(remaining) > 1 and remaining[1] not in ("-h", "--help") else None
            return _build_help_options(global_options, domain)
        return None

    domain = None
    if first_help_index > 0:
        candidate = remaining[0]
        if candidate == "help":
            if len(remaining) > 1 and remaining[1] not in ("-h", "--help"):
                domain = remaining[1]
        elif candidate != "__sessiond":
            domain = candidate

    return _build_help_options(global_options, domain)


def _extract_help_global_options(args):
    values = {
        "config": None,
        "device": [],
        "runtime_dir": None,
        "takeover": False,
        "device_id": None,
        "timeout_sec": None,
        "remaining": [],
    }
    index = 0
    while index < len(args):
        arg = args[index]

        if arg == "--takeover":
            values["takeover"] = True
            index += 1
            continue

        if arg in ("--config", "--device", "--runtime-dir", "--device-id", "--timeout-sec"):
            if index + 1 >= len(args):
                values["remaining"] = args[index:]
                return values
            _set_help_global_option(values, arg, args[index + 1])
            index += 2
            continue

        matched_inline = False
        for option_name in ("--config", "--device", "--runtime-dir", "--device-id", "--timeout-sec"):
            prefix = option_name + "="
            if arg.startswith(prefix):
                _set_help_global_option(values, option_name, arg[len(prefix):])
                matched_inline = True
                break
        if matched_inline:
            index += 1
            continue

        values["remaining"] = args[index:]
        return values

    values["remaining"] = []
    return values


def _set_help_global_option(values, option_name, option_value):
    if option_name == "--config":
        values["config"] = option_value
    elif option_name == "--device":
        values["device"].append(option_value)
    elif option_name == "--runtime-dir":
        values["runtime_dir"] = option_value
    elif option_name == "--device-id":
        values["device_id"] = option_value
    elif option_name == "--timeout-sec":
        try:
            values["timeout_sec"] = int(option_value)
        except (TypeError, ValueError):
            values["timeout_sec"] = option_value


def _build_help_options(global_options, domain):
    return argparse.Namespace(
        command_name="help",
        domain=domain,
        config=global_options["config"],
        device=list(global_options["device"]),
        runtime_dir=global_options["runtime_dir"],
        takeover=global_options["takeover"],
        device_id=global_options["device_id"],
        timeout_sec=global_options["timeout_sec"],
    )


def main(argv=None):
    return RouterCli().run(argv)


class _HTTPAPIError(Exception):
    def __init__(self, code, kind, message, stderr=None):
        super(_HTTPAPIError, self).__init__(message)
        self.code = code
        self.kind = kind
        self.message = message
        self.stderr = stderr


if __name__ == "__main__":
    raise SystemExit(main())
