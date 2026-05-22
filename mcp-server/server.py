from __future__ import print_function

import argparse
import http.client
import io
import json
import ntpath
import os
import signal
import subprocess
import sys
import threading
import time
import traceback
from urllib.parse import quote, unquote, urlsplit

try:
    from .ssh_bridge import BootstrapError, ConfigError, DEFAULT_PROJECT_CONFIG_PATH, SSHBridge
except (ImportError, SystemError, ValueError):
    from ssh_bridge import BootstrapError, ConfigError, DEFAULT_PROJECT_CONFIG_PATH, SSHBridge


JSONRPC_VERSION = "2.0"

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NOTFOUND = 2
EXIT_TIMEOUT = 3
EXIT_BADARGS = 4

ERR_PARSE = -32700
ERR_INVALID_REQUEST = -32600
ERR_METHOD_NOT_FOUND = -32601
ERR_INVALID_PARAMS = -32602
ERR_INTERNAL = -32603
ERR_NOT_INITIALIZED = -32002

SUPPORTED_PROTOCOL_VERSIONS = [
    "2025-11-25",
    "2025-06-18",
    "2024-11-05",
]

SPEEDTEST_ACTIONS = [
    "start",
    "status",
    "output",
    "stop",
    "servers",
]

TCPDUMP_ACTIONS = [
    "start",
    "status",
    "stop",
    "init",
    "delete",
]

# The backend CLI supports more tcpdump modes, but MCP intentionally exposes
# only live show-mode capture to keep the external contract narrow.
TCPDUMP_CAPTURE_MODES = [
    "show",
]

SERVER_NAME = "agent-mcp-server"
SERVER_VERSION = "0.1.0"
DEFAULT_PROJECT_CONFIG_EXAMPLE_PATH = os.path.join(
    os.path.dirname(DEFAULT_PROJECT_CONFIG_PATH),
    "config.json.example",
)
DEFAULT_RUNTIME_DIR = os.path.join("~", ".agent-mcp")
DEFAULT_RUNTIME_KEYS_DIR_NAME = "keys"
DEFAULT_RUNTIME_CONTROL_PATH_DIR_NAME = "ssh-control"
DEFAULT_RUNTIME_LOGS_DIR_NAME = "logs"
DEFAULT_SERVER_LOG_FILE_NAME = "agent-mcp.log"
DEFAULT_UPGRADE_TIMEOUT_SEC = 600
MAX_UPGRADE_TIMEOUT_SEC = 1800
DEFAULT_AGENT_API_PORT = 4888
LOCAL_API_REMOTE_ADDR = "127.0.0.1"
DEVICE_SPEC_REQUIRED_FIELDS = ("name", "device_ip", "pass")
DEVICE_SPEC_FIELD_MAP = {
    "name": "name",
    "device_ip": "device_ip",
    "pass": "pass",
    "user": "user",
    "agent_user": "agent_user",
    "port": "port",
}

READ_ONLY_TOOL_ANNOTATIONS = {
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
    "readOnlyHint": True,
}

MUTATING_TOOL_ANNOTATIONS = {
    "destructiveHint": True,
    "idempotentHint": False,
    "openWorldHint": True,
    "readOnlyHint": False,
}

TOOL_SPECS = [
    {
        "name": "status",
        "title": "Status",
        "description": (
            "Run `status` or `status <subcommand>` on the remote agent_cli entrypoint. "
            "This is a read-only tool for inspecting device runtime state.\n\n"
            "Preferred workflow:\n"
            "1. Read the full status snapshot with `status`, or discover available status keys with `status list`.\n"
            "2. Read a specific status area with `status <key>` or a broad summary with `status basic`.\n"
            "3. Use the `config` MCP tool with `config list` and `config get <key>` for configuration reads.\n"
            "4. Do not invent status keys. Discover them first from the list command."
        ),
        "requires_subcommand": False,
        "accepts_subcommand": True,
        "subcommand_description": "Optional suffix appended after remote `status`; omit it for the full status output, or use `basic`, `cellular`, or `list`.",
        "annotations": READ_ONLY_TOOL_ANNOTATIONS,
    },
    {
        "name": "config",
        "title": "Config",
        "description": (
            "Run `config <subcommand>` on the remote agent_cli entrypoint. "
            "This tool reads or changes device configuration. `config set` is mutating, while `config get` is read-only.\n\n"
            "Preferred workflow:\n"
            "1. List valid config areas with `config list`.\n"
            "2. Inspect the schema with `schema <key>`.\n"
            "3. Inspect validation and side-effect rules with `schema <root_key> --validation` when constraints matter.\n"
            "4. Read current config with `config get <key>`.\n"
            "5. Apply the change with `config set <key> {<json>}`.\n"
            "6. Re-read the affected state with `config get <key>` or `status` after the change.\n"
            "Do not invent config keys, field names, enum values, or payload shapes."
        ),
        "requires_subcommand": True,
        "subcommand_description": "Suffix appended after `config`, such as `list`, `get system`, or `set system {\"hostname\":\"edge-a\"}`.",
        "annotations": MUTATING_TOOL_ANNOTATIONS,
    },
    {
        "name": "log",
        "title": "Log",
        "description": (
            "Run `log` or `log <subcommand>` on the remote agent_cli entrypoint. "
            "This is a read-only tool for retrieving service and feature logs.\n\n"
            "Preferred workflow:\n"
            "1. Discover available log services with `log list`.\n"
            "2. Read the default syslog-backed `message` log with `log`, or read a specific service with `log <service> --line <count>`.\n"
            "3. When `--line` is omitted, `log` defaults to 250 lines.\n"
            "Do not invent service names. Use `log list` first."
        ),
        "requires_subcommand": False,
        "accepts_subcommand": True,
        "subcommand_description": "Optional suffix appended after `log`; omit it for the default `message` log, or use `list` or `<service> --line <count>`.",
        "annotations": READ_ONLY_TOOL_ANNOTATIONS,
    },
    {
        "name": "schema",
        "title": "Schema",
        "description": (
            "Run `schema <subcommand>` on the remote agent_cli entrypoint. This is a read-only tool for inspecting "
            "resource schemas and validation rules.\n\n"
            "Preferred workflow:\n"
            "1. Discover available schema root keys with `schema list`.\n"
            "2. Read the schema for a resource root with `schema <key>`.\n"
            "3. The returned resource may include `config`, `status`, or both sections.\n"
            "4. Read validation rules with `schema <root_key> --validation` before any non-trivial `config` change.\n"
            "5. Use schema results as the source of truth for valid fields, types, enum values, and constraints.\n"
            "Examples: `schema wan`, `schema cellular`, `schema signal_history_info`, `schema wan --validation`.\n"
            "Schema lookups are supported only for root keys such as `wan`, `system`, or `cellular`."
        ),
        "requires_subcommand": True,
        "subcommand_description": "Suffix appended after `schema`, such as `list`, `wan`, `cellular`, `signal_history_info`, or `wan --validation`.",
        "annotations": READ_ONLY_TOOL_ANNOTATIONS,
    },
    {
        "name": "upgrade",
        "title": "Upgrade",
        "description": (
            "Run `upgrade` on the remote agent_cli entrypoint. "
            "This tool is mutating and potentially disruptive. Use it only when the user clearly requests a firmware upgrade "
            "and you have a confirmed local firmware file path on the machine running the MCP server or a device-side download URL.\n\n"
            "Important notes:\n"
            "- `source_type=file` uploads the local firmware file through the device API before triggering the upgrade.\n"
            "- This tool submits a one-shot firmware upgrade call; it does not expose `upgrade status`.\n"
            "- A successful return means the device accepted and ran the current upgrade request, not that the device has "
            "already rebooted and come back online.\n"
            "- Confirm the final firmware version after the device reconnects with `status basic`.\n\n"
            "Examples:\n"
            "- `{\\\"source_type\\\":\\\"file\\\",\\\"file_path\\\":\\\"/tmp/fw.bin\\\"}`\n"
            "- `{\\\"source_type\\\":\\\"url\\\",\\\"url\\\":\\\"https://example/fw.bin\\\"}`"
        ),
        "requires_subcommand": False,
        "input_properties": {
            "source_type": {
                "type": "string",
                "enum": ["file", "url"],
                "description": "Upgrade source type. Use `file` for a local firmware path on the MCP host or `url` for a device-side HTTP(S) download.",
            },
            "file_path": {
                "type": "string",
                "description": "Local firmware image path on the machine running the MCP server. Required when `source_type` is `file`.",
            },
            "url": {
                "type": "string",
                "description": "HTTP or HTTPS firmware URL that the device should download. Required when `source_type` is `url`.",
            },
        },
        "input_required": ["source_type"],
        "annotations": MUTATING_TOOL_ANNOTATIONS,
    },
    {
        "name": "reboot",
        "title": "Reboot",
        "description": (
            "Run `reboot` on the remote agent_cli entrypoint. "
            "This tool is mutating and disruptive. Use it only when the user explicitly requests a reboot "
            "or a confirmed recovery workflow requires it."
        ),
        "requires_subcommand": False,
        "annotations": MUTATING_TOOL_ANNOTATIONS,
    },
    {
        "name": "tool",
        "title": "Tool",
        "description": (
            "Run `tool <subcommand>` on the remote agent_cli entrypoint. "
            "Use this tool to run diagnostic and network-testing workflows such as ping, traceroute, tcpdump, iperf, and speedtest.\n\n"
            "Preferred workflow:\n"
            "1. Discover supported diagnostics with `tool list`.\n"
            "2. Start a diagnostic by passing `<tool_name> <json_payload>` in `subcommand`.\n"
            "3. Check progress with an `action` of `status`.\n"
            "4. Read accumulated output with a payload like `{\"start_line\":0}`.\n"
            "5. Stop long-running diagnostics with an `action` of `stop` when they are no longer needed.\n\n"
            "Important notes:\n"
            "- Treat diagnostic runs as active operations even when they do not change configuration.\n"
            "- Do not invent tool names or payload shapes. Use `tool list` and follow the documented request format.\n"
            "- `agent_cli` wraps flat payloads under the backend tool key automatically. For example, `ping {\"action\":\"status\"}` is sent as `{\"ping\":{\"action\":\"status\"}}`.\n"
            "- `speedtest` is exposed through this wrapper as `speedtest {\"action\":\"start\"}` and is translated to the backend speedtest session commands.\n"
            "- MCP only supports selecting the speedtest uplink by `ip`. Do not use `interface`; if the user wants to choose a test path, provide uplink IP choices instead.\n"
            "- `ping start` defaults `interface=any`, `ping_count=4`, and `packet_size=32` when omitted.\n"
            "- `traceroute start` defaults `interface=any` when omitted.\n"
            "- `tcpdump start` only supports `capture_mode` of `show` through MCP and requires `capture_time`, exactly one `local_iface` entry, and an explicit `expert_options` string on that item.\n"
            "- Some diagnostics are long-running and may need repeated status and output polling.\n\n"
            "Speedtest subcommands:\n"
            "- `speedtest {\"action\":\"servers\"}`: list available speedtest server nodes so the user can choose a `server_id`.\n"
            "- `speedtest {\"action\":\"start\"}`: start a new speedtest session. Optional fields: `server_id` and `ip`.\n"
            "- `speedtest {\"action\":\"status\"}`: read the current session state.\n"
            "- `speedtest {\"action\":\"output\",\"start_line\":0}`: read incremental result events from a given offset.\n"
            "- `speedtest {\"action\":\"stop\"}`: stop the current running speedtest session.\n\n"
            "Examples:\n"
            "- Ping start: `ping {\"action\":\"start\",\"host\":\"8.8.8.8\"}`\n"
            "- Ping status: `ping {\"action\":\"status\"}`\n"
            "- Ping output: `ping {\"start_line\":0}`\n"
            "- Ping stop: `ping {\"action\":\"stop\"}`\n"
            "- Traceroute start: `traceroute {\"action\":\"start\",\"host\":\"8.8.8.8\"}`\n"
            "- Tcpdump start: `tcpdump {\"action\":\"start\",\"capture_mode\":\"show\",\"capture_time\":300,\"local_iface\":[{\"interface\":\"wan1\",\"expert_options\":\"\"}]}`\n"
            "- Iperf client start: `iperf {\"action\":\"start\",\"role\":\"client\",\"command\":\"198.51.100.10\",\"capture_time\":10}`\n"
            "- Speedtest start with server and uplink IP: `speedtest {\"action\":\"start\",\"server_id\":12345,\"ip\":\"198.51.100.10\"}`\n"
            "- Speedtest start with server: `speedtest {\"action\":\"start\",\"server_id\":12345}`\n"
            "- Speedtest start with defaults: `speedtest {\"action\":\"start\"}`\n"
            "- Speedtest status: `speedtest {\"action\":\"status\"}`\n"
            "- Speedtest output: `speedtest {\"action\":\"output\",\"start_line\":0}`\n"
            "- Speedtest stop: `speedtest {\"action\":\"stop\"}`\n"
            "- Speedtest servers: `speedtest {\"action\":\"servers\"}`"
        ),
        "requires_subcommand": True,
        "subcommand_description": "Suffix appended after `tool`, such as `list`, `ping {\"action\":\"start\",\"host\":\"8.8.8.8\"}`, `speedtest {\"action\":\"servers\"}`, or `speedtest {\"action\":\"start\",\"server_id\":12345,\"ip\":\"198.51.100.10\"}`.",
        "annotations": MUTATING_TOOL_ANNOTATIONS,
    },
]

CATEGORY_TOOL_NAMES = [spec["name"] for spec in TOOL_SPECS]

RESOURCE_URI_SCHEME = "device"

RESOURCE_SPECS = [
    {
        "path": "/status/basic",
        "name": "Basic Status",
        "description": "Current basic device status summary.",
        "command": "status basic",
        "mime_type": "application/json",
    },
    {
        "path": "/status/list",
        "name": "Status Keys",
        "description": "Available keys under `status`.",
        "command": "status list",
        "mime_type": "application/json",
    },
    {
        "path": "/config/list",
        "name": "Config Keys",
        "description": "Available keys under `config`.",
        "command": "config list",
        "mime_type": "application/json",
    },
    {
        "path": "/schema/list",
        "name": "Schema Keys",
        "description": "Available schema root keys.",
        "command": "schema list",
        "mime_type": "application/json",
    },
    {
        "path": "/log/list",
        "name": "Log Services",
        "description": "Available log services.",
        "command": "log list",
        "mime_type": "application/json",
    },
    {
        "path": "/tool/list",
        "name": "Diagnostic Tools",
        "description": "Available diagnostic tool names, including the MCP-exposed speedtest wrapper.",
        "command": "tool list",
        "mime_type": "application/json",
    },
]


class JSONRPCError(Exception):
    def __init__(self, code, message, data=None):
        super(JSONRPCError, self).__init__(message)
        self.code = code
        self.message = message
        self.data = data


class _SSHTunnelError(Exception):
    def __init__(self, message, stderr=None):
        super(_SSHTunnelError, self).__init__(message)
        self.message = message
        self.stderr = stderr


class _HTTPAPIError(Exception):
    def __init__(self, code, kind, message, stderr=None):
        super(_HTTPAPIError, self).__init__(message)
        self.code = code
        self.kind = kind
        self.message = message
        self.stderr = stderr


class _SSHStreamError(OSError):
    def __init__(self, message, stderr=None):
        super(_SSHStreamError, self).__init__(message)
        self.stderr = stderr


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
            name="agent-mcp-ssh-api-stderr",
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


class ExternalCliMCPServer(object):
    # List commands whose responses can be cached per device firmware version.
    _CACHEABLE_LISTS = {
        "status list",
        "config list",
        "log list",
        "schema list",
        "tool list",
    }

    def __init__(self, bridge, server_name=SERVER_NAME, server_version=SERVER_VERSION, protocol_versions=None):
        self.bridge = bridge
        self.server_name = server_name
        self.server_version = server_version
        self.protocol_versions = protocol_versions or list(SUPPORTED_PROTOCOL_VERSIONS)
        self.state = "awaiting_initialize"
        # Cache structure: {device_id: {"firmware": "v1.0.0", "lists": {command: data}}}
        self._list_cache = {}
        self._log_handle = None
        self._diagnostic_context = None

    def set_log_handle(self, log_handle):
        self._log_handle = log_handle

    def _log_diagnostic(self, category, message, **fields):
        handle = self._log_handle
        if handle is None:
            return

        parts = [
            "[{0}]".format(time.strftime("%Y-%m-%d %H:%M:%S")),
            "[{0}]".format(category),
            message,
        ]
        for key in sorted(fields):
            value = fields[key]
            if value is None:
                continue
            parts.append("{0}={1}".format(key, _format_log_value(value)))

        try:
            handle.write(" ".join(parts) + "\n")
            handle.flush()
        except (AttributeError, IOError, OSError, ValueError):
            pass

    def _log_upgrade_event(self, message, **fields):
        context = self._diagnostic_context or {}
        merged = dict(fields)
        if "trace_id" not in merged and context.get("trace_id") is not None:
            merged["trace_id"] = context.get("trace_id")
        if "device_id" not in merged and context.get("device_id") is not None:
            merged["device_id"] = context.get("device_id")
        self._log_diagnostic("upgrade", message, **merged)

    def _extract_firmware_version(self, response):
        if not isinstance(response, dict):
            return None

        candidates = [response.get("firmware")]
        result = response.get("result")
        if isinstance(result, dict):
            candidates.append(result.get("firmware"))

        for candidate in candidates:
            if isinstance(candidate, str):
                version = candidate.strip()
                if version:
                    return version

        return None

    def _get_device_firmware(self, device_id, timeout_sec=None):
        """Return the device firmware version, or None when it cannot be read."""
        result = self.bridge.execute(device_id, command="status basic", timeout_sec=timeout_sec)
        if result.get("ok"):
            return self._extract_firmware_version(result.get("response"))
        return None

    def _get_cached_list(self, device_id, command, timeout_sec=None):
        """Return a cached list response and refresh it when firmware changes."""
        current_fw = self._get_device_firmware(device_id, timeout_sec=timeout_sec)

        # Disable caching when the firmware version cannot be determined.
        if current_fw is None:
            return self._augment_outcome_for_command(
                command,
                self.bridge.execute(device_id, command=command, timeout_sec=timeout_sec),
            )

        # Look up the cache bucket for this device.
        device_cache = self._list_cache.get(device_id)

        # Case 1: nothing cached yet, or the firmware version changed.
        if device_cache is None or device_cache.get("firmware") != current_fw:
            # Refresh the response from the device.
            result = self._augment_outcome_for_command(
                command,
                self.bridge.execute(device_id, command=command, timeout_sec=timeout_sec),
            )
            if result.get("ok"):
                # Replace the device cache so all list results match the current firmware.
                self._list_cache[device_id] = {
                    "firmware": current_fw,
                    "lists": {command: result}
                }
            return result

        # Case 2: firmware is unchanged and this command is already cached.
        if command in device_cache.get("lists", {}):
            return device_cache["lists"][command]

        # Case 3: firmware is unchanged, but this command has not been cached yet.
        result = self._augment_outcome_for_command(
            command,
            self.bridge.execute(device_id, command=command, timeout_sec=timeout_sec),
        )
        if result.get("ok"):
            device_cache["lists"][command] = result
        return result

    def _augment_outcome_for_command(self, command, outcome):
        if command != "tool list" or not isinstance(outcome, dict) or not outcome.get("ok"):
            return outcome

        response = outcome.get("response")
        if not isinstance(response, dict):
            return outcome

        result = response.get("result")
        if not isinstance(result, dict):
            return outcome

        tools = result.get("tools")
        if not isinstance(tools, list):
            return outcome

        for item in tools:
            if isinstance(item, dict) and item.get("name") == "speedtest":
                return outcome

        new_result = dict(result)
        new_result["tools"] = list(tools) + [{"name": "speedtest"}]

        new_response = dict(response)
        new_response["result"] = new_result

        augmented = dict(outcome)
        augmented["response"] = new_response
        return augmented

    def _public_outcome(self, outcome):
        if not isinstance(outcome, dict):
            return outcome

        public = dict(outcome)
        public["data"] = public.pop("response", None)

        error = public.get("error")
        if isinstance(error, dict):
            normalized = {
                "code": error.get("code") if isinstance(error.get("code"), str) and error.get("code") else "internal",
                "message": error.get("message") if isinstance(error.get("message"), str) and error.get("message") else "Unknown error",
            }
            if isinstance(error.get("kind"), str) and error.get("kind"):
                normalized["kind"] = error["kind"]
            if isinstance(error.get("field"), str) and error.get("field"):
                normalized["field"] = error["field"]
            public["error"] = normalized

        return public

    def process_message(self, message):
        if isinstance(message, list):
            return self._process_batch(message)
        return self._process_single(message)

    def _process_batch(self, messages):
        if not messages:
            return self._error_response(None, JSONRPCError(ERR_INVALID_REQUEST, "Empty batch is not allowed"))

        for message in messages:
            if isinstance(message, dict) and message.get("method") == "initialize":
                return self._error_response(None, JSONRPCError(ERR_INVALID_REQUEST, "initialize request must not be batched"))

        responses = []
        for message in messages:
            response = self._process_single(message)
            if response is not None:
                responses.append(response)

        return responses or None

    def _process_single(self, message):
        if not isinstance(message, dict):
            return self._error_response(None, JSONRPCError(ERR_INVALID_REQUEST, "Request must be an object"))

        if message.get("jsonrpc") != JSONRPC_VERSION:
            return self._error_response(message.get("id"), JSONRPCError(ERR_INVALID_REQUEST, "jsonrpc must be 2.0"))

        method = message.get("method")
        request_id = message.get("id")
        is_notification = "id" not in message

        if not isinstance(method, str) or not method:
            return self._error_response(request_id, JSONRPCError(ERR_INVALID_REQUEST, "method must be a non-empty string"))

        if method == "ping":
            if is_notification:
                return None
            return self._result_response(request_id, {})

        if self.state == "awaiting_initialize":
            if method != "initialize":
                if is_notification:
                    return None
                return self._error_response(request_id, JSONRPCError(ERR_NOT_INITIALIZED, "Server not initialized"))
            if is_notification:
                return self._error_response(None, JSONRPCError(ERR_INVALID_REQUEST, "initialize must be a request"))
            return self._handle_initialize(request_id, message.get("params"))

        if method == "initialize":
            return self._error_response(request_id, JSONRPCError(ERR_INVALID_REQUEST, "Server is already initialized"))

        if method == "notifications/initialized":
            self.state = "ready"
            return None

        if method.startswith("notifications/"):
            return None

        if self.state != "ready":
            if is_notification:
                return None
            return self._error_response(request_id, JSONRPCError(ERR_NOT_INITIALIZED, "Client has not sent notifications/initialized"))

        if method == "tools/list":
            if is_notification:
                return None
            return self._result_response(request_id, {"tools": self._tool_definitions()})

        if method == "resources/list":
            if is_notification:
                return None
            return self._handle_resources_list(request_id, message.get("params"))

        if method == "resources/read":
            if is_notification:
                return None
            return self._handle_resources_read(request_id, message.get("params"))

        if method == "tools/call":
            if is_notification:
                return None
            return self._handle_tools_call(request_id, message.get("params"))

        return self._error_response(request_id, JSONRPCError(ERR_METHOD_NOT_FOUND, "Method not found"))

    def _handle_initialize(self, request_id, params):
        if not isinstance(params, dict):
            return self._error_response(request_id, JSONRPCError(ERR_INVALID_PARAMS, "initialize params must be an object"))

        requested_version = params.get("protocolVersion")
        if requested_version not in self.protocol_versions:
            return self._error_response(
                request_id,
                JSONRPCError(
                    ERR_INVALID_PARAMS,
                    "Unsupported protocol version",
                    {
                        "supported": self.protocol_versions,
                        "requested": requested_version,
                    },
                ),
            )

        self.state = "awaiting_initialized"

        result = {
            "protocolVersion": requested_version,
            "capabilities": {
                "resources": {
                    "subscribe": False,
                    "listChanged": False,
                },
                "tools": {
                    "listChanged": False,
                },
            },
            "serverInfo": {
                "name": self.server_name,
                "version": self.server_version,
            },
            "instructions": (
                "This server provides remote access to device CLI over SSH. Use it to inspect device status, "
                "inspect configuration schemas, read logs, run diagnostics, and apply configuration changes.\n\n"
                "Preferred workflow:\n"
                "1. Identify the target device with `device_id`. If the server config contains exactly one device, "
                "you may omit `device_id` and the server will use that configured device.\n"
                "2. Prefer read-only discovery before making changes.\n"
                "3. To inspect runtime state, use `status` for a full snapshot or `status list` first, then `status <key>`.\n"
                "4. Use `schema <key>` to inspect the available `config` and `status` schema sections for a resource root.\n"
                "5. To inspect configuration, use `config list` first, then `config get <key>`.\n"
                "6. Before any `config` change, inspect the schema with `schema <key>` and, when relevant, "
                "`schema <root_key> --validation`.\n"
                "7. Do not invent config keys, field names, enum values, or command shapes. Discover them first.\n"
                "8. Treat `config set`, `upgrade`, `reboot`, and state-changing `tool` operations as destructive actions. "
                "Use them only when the user clearly requests a change or when a confirmed workflow requires it. `config get` is read-only.\n"
                "9. If the request is ambiguous, gather more information with read-only tools before attempting changes.\n\n"
                "Tool guidance:\n"
                "- `status`: read runtime status\n"
                "- `device://<device_id>/...`: read fixed status and discovery resources\n"
                "- `schema`: inspect unified resource schemas and validation constraints\n"
                "- `config`: read or apply configuration changes\n"
                "- `log`: inspect service logs\n"
                "- `tool`: run diagnostics such as ping, traceroute, tcpdump, iperf, and speedtest\n"
                "- `upgrade`: install firmware\n"
                "- `reboot`: reboot the device"
            ),
        }
        return self._result_response(request_id, result)

    def _handle_tools_call(self, request_id, params):
        if not isinstance(params, dict):
            return self._error_response(request_id, JSONRPCError(ERR_INVALID_PARAMS, "tools/call params must be an object"))

        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        try:
            if tool_name == "show":
                raise JSONRPCError(
                    ERR_INVALID_PARAMS,
                    "The `show` tool has been removed; use `status` for runtime state or `config get <key>` for configuration reads",
                )
            tool_spec = self._find_tool_spec(tool_name)
            if tool_spec is None:
                raise JSONRPCError(ERR_INVALID_PARAMS, "Unknown tool")
            validated = self._validate_tool_arguments(tool_spec, arguments)
        except JSONRPCError as exc:
            return self._error_response(request_id, exc)

        outcome = self._execute_validated_call(validated)
        public_outcome = self._public_outcome(outcome)

        result = {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(public_outcome, separators=(",", ":"), sort_keys=True),
                }
            ],
            "structuredContent": public_outcome,
        }
        if not public_outcome["ok"]:
            result["isError"] = True

        return self._result_response(request_id, result)

    def _handle_resources_list(self, request_id, params):
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return self._error_response(request_id, JSONRPCError(ERR_INVALID_PARAMS, "resources/list params must be an object"))
        self._reject_unknown_arguments(params, [])
        return self._result_response(request_id, {"resources": self._resource_definitions()})

    def _handle_resources_read(self, request_id, params):
        if not isinstance(params, dict):
            return self._error_response(request_id, JSONRPCError(ERR_INVALID_PARAMS, "resources/read params must be an object"))

        try:
            self._reject_unknown_arguments(params, ["uri"])
            resource = self._parse_resource_uri(params.get("uri"))
        except JSONRPCError as exc:
            return self._error_response(request_id, exc)

        outcome = self._execute_validated_call(
            {
                "device_id": resource["device_id"],
                "command": resource["resource_spec"]["command"],
            }
        )
        public_outcome = self._public_outcome(outcome)
        if not outcome["ok"]:
            return self._error_response(
                request_id,
                JSONRPCError(ERR_INTERNAL, "Resource read failed", public_outcome),
            )

        return self._result_response(
            request_id,
            {
                "contents": [
                    {
                        "uri": resource["uri"],
                        "mimeType": resource["resource_spec"]["mime_type"],
                        "text": json.dumps(public_outcome["data"], separators=(",", ":"), sort_keys=True),
                    }
                ]
            },
        )

    def _find_tool_spec(self, tool_name):
        for spec in TOOL_SPECS:
            if spec["name"] == tool_name:
                return spec
        return None

    def _execute_validated_call(self, validated):
        device_id = validated["device_id"]
        command = validated["command"]
        timeout_sec = validated.get("timeout_sec")

        if validated.get("local_upgrade_file") is not None:
            return self._execute_upgrade_file(validated)

        # Route cacheable list commands through the firmware-aware cache.
        if command in self._CACHEABLE_LISTS:
            return self._get_cached_list(device_id, command, timeout_sec=timeout_sec)

        # Execute non-cacheable commands directly.
        return self._augment_outcome_for_command(
            command,
            self.bridge.execute(
                device_id,
                command=command,
                timeout_sec=timeout_sec,
            ),
        )

    def _validate_tool_arguments(self, tool_spec, arguments):
        if tool_spec["name"] == "status":
            return self._validate_status_arguments(arguments)
        if tool_spec["name"] == "config":
            return self._validate_config_arguments(arguments)
        if tool_spec["name"] == "upgrade":
            return self._validate_upgrade_arguments(arguments)
        if tool_spec["name"] == "tool":
            return self._validate_tool_wrapper_arguments(arguments)
        if tool_spec["name"] == "schema":
            return self._validate_schema_arguments(arguments)
        return self._validate_category_tool_arguments(tool_spec, arguments)

    def _validate_status_arguments(self, arguments):
        validated = self._validate_category_tool_arguments(self._find_tool_spec("status"), arguments)
        if validated["command"] == "status":
            return validated

        subcommand = validated["command"][len("status "):]

        if subcommand == "status" or subcommand.startswith("status "):
            raise JSONRPCError(
                ERR_INVALID_PARAMS,
                "status subcommand must omit the `status` prefix; use no subcommand, `basic`, `list`, or `<key>`",
            )
        if subcommand == "config" or subcommand.startswith("config "):
            raise JSONRPCError(
                ERR_INVALID_PARAMS,
                "status does not support config lookups; use the `config` tool with `get <key>`",
            )

        return validated

    def _validate_config_arguments(self, arguments):
        validated = self._validate_category_tool_arguments(self._find_tool_spec("config"), arguments)
        subcommand = validated["command"][len("config "):]

        if subcommand == "list":
            return validated
        if subcommand.startswith("list "):
            raise JSONRPCError(ERR_INVALID_PARAMS, "config list does not accept additional arguments")

        if subcommand == "get" or subcommand.startswith("get "):
            query = subcommand[len("get"):].strip()
            if not query:
                raise JSONRPCError(ERR_INVALID_PARAMS, "config query must be specified after `config get`")
            if query == "list":
                raise JSONRPCError(ERR_INVALID_PARAMS, "`config get list` has been renamed to `config list`")
            return validated

        if subcommand == "set" or subcommand.startswith("set "):
            remainder = subcommand[len("set"):].strip()
            parts = remainder.split(None, 1)
            if len(parts) != 2:
                raise JSONRPCError(ERR_INVALID_PARAMS, "config key and payload must be specified after `config set`")
            self._require_token(parts[0], "config key")
            self._require_command(parts[1], "config payload")
            return validated

        parts = subcommand.split(None, 1)
        if len(parts) == 2:
            raise JSONRPCError(
                ERR_INVALID_PARAMS,
                "legacy `config <key> <payload>` is no longer supported; use `config set <key> <payload>`",
            )

        raise JSONRPCError(
            ERR_INVALID_PARAMS,
            "config subcommand must be `list`, start with `get`, or start with `set`; use `config list` for discovery, `config get <key>` for reads, or `config set <key> <payload>` for writes",
        )

    def _validate_schema_arguments(self, arguments):
        validated = self._validate_category_tool_arguments(self._find_tool_spec("schema"), arguments)
        subcommand = validated["command"][len("schema "):]

        if subcommand == "list":
            return validated
        if subcommand.startswith("list "):
            raise JSONRPCError(ERR_INVALID_PARAMS, "schema list does not accept additional arguments")
        if subcommand == "status":
            raise JSONRPCError(
                ERR_INVALID_PARAMS,
                "`schema status ...` has been removed; use `schema <key>` and inspect the returned `status` section",
            )
        if subcommand.startswith("status "):
            raise JSONRPCError(
                ERR_INVALID_PARAMS,
                "`schema status ...` has been removed; use `schema <key>` and inspect the returned `status` section",
            )
        if subcommand == "--validation":
            raise JSONRPCError(ERR_INVALID_PARAMS, "schema key must be specified before `--validation`")
        if subcommand.endswith(" --validation"):
            query = subcommand[: -len(" --validation")].strip()
            self._require_token(query, "schema key")
            if "." in query:
                raise JSONRPCError(
                    ERR_INVALID_PARAMS,
                    "schema only supports root keys; nested paths such as `system.hostname` are not supported",
                )
            return validated
        self._require_token(subcommand, "schema key")
        if "." in subcommand:
            raise JSONRPCError(
                ERR_INVALID_PARAMS,
                "schema only supports root keys; nested paths such as `system.hostname` are not supported",
            )

        return validated

    def _validate_upgrade_arguments(self, arguments):
        if not isinstance(arguments, dict):
            raise JSONRPCError(ERR_INVALID_PARAMS, "Tool arguments must be an object")

        self._reject_unknown_arguments(arguments, ["device_id", "timeout_sec", "source_type", "file_path", "url"])

        validated = {
            "device_id": self._resolve_device_id(arguments),
            "command": "upgrade",
        }
        timeout_sec = self._validate_timeout(arguments.get("timeout_sec"), maximum=MAX_UPGRADE_TIMEOUT_SEC)

        source_type = arguments.get("source_type")
        if source_type not in ("file", "url"):
            raise JSONRPCError(ERR_INVALID_PARAMS, "source_type must be `file` or `url`")

        if source_type == "file":
            if "url" in arguments:
                raise JSONRPCError(ERR_INVALID_PARAMS, "url is not supported when source_type is `file`")
            file_path = self._require_command(arguments.get("file_path"), "file_path")
            validated["local_upgrade_file"] = file_path
            validated["command"] = "upgrade --file {0}".format(file_path)
        else:
            if "file_path" in arguments:
                raise JSONRPCError(ERR_INVALID_PARAMS, "file_path is not supported when source_type is `url`")
            validated["command"] = "upgrade --url {0}".format(self._require_upgrade_url(arguments.get("url")))

        if timeout_sec is not None:
            validated["timeout_sec"] = timeout_sec
        else:
            validated["timeout_sec"] = max(
                self.bridge.ssh_defaults["command_timeout_sec"],
                DEFAULT_UPGRADE_TIMEOUT_SEC,
            )

        return validated

    def _execute_upgrade_file(self, validated):
        raw_local_path = validated["local_upgrade_file"]
        timeout_sec = validated.get("timeout_sec")
        device_id = validated["device_id"]
        public_command = validated["command"]
        current_stage = "resolve_local_file"
        timeout = None
        file_size = None
        previous_context = self._diagnostic_context
        self._diagnostic_context = {
            "trace_id": _build_trace_id("upgrade", device_id),
            "device_id": device_id,
        }

        self._log_upgrade_event(
            "starting file upgrade",
            source_path=raw_local_path,
            timeout_sec=timeout_sec,
        )

        try:
            try:
                local_path, translated_path = self._resolve_local_upgrade_path(raw_local_path)
            except (OSError, ValueError) as exc:
                self._log_upgrade_event(
                    "local file inspection failed",
                    stage=current_stage,
                    error_type=exc.__class__.__name__,
                    error=str(exc),
                )
                return self._build_local_error_outcome(
                    device_id=device_id,
                    command=public_command,
                    code="bad_args",
                    kind="local_file_invalid",
                    message="Failed to inspect local upgrade file `{0}`: {1}".format(raw_local_path, exc),
                )

            self._log_upgrade_event(
                "resolved local file path",
                local_path=local_path,
                translated_path=translated_path,
            )

            try:
                path_exists = os.path.exists(local_path)
                if not path_exists and translated_path is not None:
                    path_exists = os.path.exists(translated_path)
                    if path_exists:
                        local_path = translated_path
                        self._log_upgrade_event(
                            "using translated local file path",
                            local_path=local_path,
                        )

                if not path_exists:
                    checked_paths = [local_path]
                    if translated_path is not None and translated_path != local_path:
                        checked_paths.append(translated_path)
                    self._log_upgrade_event(
                        "local upgrade file was not found",
                        stage=current_stage,
                        checked_paths=checked_paths,
                    )
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
                    self._log_upgrade_event(
                        "local upgrade file is not a regular file",
                        stage=current_stage,
                        local_path=local_path,
                    )
                    return self._build_local_error_outcome(
                        device_id=device_id,
                        command=public_command,
                        code="bad_args",
                        kind="local_file_invalid",
                        message="Local upgrade file is not a regular file: {0}".format(local_path),
                    )
                if not os.access(local_path, os.R_OK):
                    self._log_upgrade_event(
                        "local upgrade file is not readable",
                        stage=current_stage,
                        local_path=local_path,
                    )
                    return self._build_local_error_outcome(
                        device_id=device_id,
                        command=public_command,
                        code="bad_args",
                        kind="local_file_unreadable",
                        message="Local upgrade file is not readable: {0}".format(local_path),
                    )
                file_size = os.path.getsize(local_path)
            except (OSError, ValueError) as exc:
                self._log_upgrade_event(
                    "local file inspection failed",
                    stage=current_stage,
                    error_type=exc.__class__.__name__,
                    error=str(exc),
                )
                return self._build_local_error_outcome(
                    device_id=device_id,
                    command=public_command,
                    code="bad_args",
                    kind="local_file_invalid",
                    message="Failed to inspect local upgrade file `{0}`: {1}".format(raw_local_path, exc),
                )

            self._log_upgrade_event(
                "local file ready",
                local_path=local_path,
                file_size=file_size,
            )

            current_stage = "ensure_binding"
            self._log_upgrade_event("ensuring SSH binding")
            try:
                self.bridge._ensure_binding(device_id)
            except BootstrapError as exc:
                self._log_upgrade_event(
                    "SSH binding failed",
                    stage=current_stage,
                    error_kind=exc.kind,
                    error=exc.message,
                    stderr_preview=_preview_text(exc.stderr),
                )
                return self._build_local_error_outcome(
                    device_id=device_id,
                    command=public_command,
                    code=self._bridge_error_code(exc.kind),
                    kind=exc.kind,
                    message=exc.message,
                    stderr=exc.stderr,
                )

            profile = self.bridge.devices[device_id]
            timeout = timeout_sec or self.bridge.ssh_defaults["command_timeout_sec"]
            host_header = profile["device_ip"]
            self._log_upgrade_event(
                "prepared API upgrade session",
                host=host_header,
                timeout_sec=timeout,
            )
            if file_size is not None and timeout:
                required_mbps = ((file_size * 8.0) / float(timeout)) / 1000000.0
                if file_size >= 50 * 1024 * 1024:
                    self._log_upgrade_event(
                        "large firmware upload may hit timeout",
                        file_size=file_size,
                        timeout_sec=timeout,
                        required_mbps=round(required_mbps, 2),
                    )

            current_stage = "open_api_tunnel"
            self._log_upgrade_event("opening API tunnel")
            try:
                with self._open_api_tunnel(device_id, timeout) as tunnel:
                    current_stage = "login"
                    self._log_upgrade_event("starting API login")
                    token = self._api_login(
                        tunnel,
                        host_header,
                        profile["user"],
                        profile["pass"],
                        timeout,
                    )
                    self._log_upgrade_event("API login completed")

                    current_stage = "upload"
                    self._log_upgrade_event(
                        "starting firmware upload",
                        local_path=local_path,
                        file_size=file_size,
                    )
                    self._api_upload_firmware(
                        tunnel,
                        host_header,
                        token,
                        local_path,
                        timeout,
                    )
                    self._log_upgrade_event("firmware upload completed")

                    current_stage = "trigger_upgrade"
                    self._log_upgrade_event("triggering remote upgrade")
                    upgrade_payload = self._api_trigger_upgrade(
                        tunnel,
                        host_header,
                        token,
                        timeout,
                    )
                    self._log_upgrade_event(
                        "remote upgrade accepted",
                        response_preview=_preview_json(upgrade_payload),
                    )
            except _SSHTunnelError as exc:
                self._log_upgrade_event(
                    "SSH tunnel error during upgrade",
                    stage=current_stage,
                    error=exc.message,
                    stderr_preview=_preview_text(exc.stderr),
                )
                return self._build_local_error_outcome(
                    device_id=device_id,
                    command=public_command,
                    code="transport_error",
                    kind="ssh_tunnel_error",
                    message=exc.message,
                    stderr=exc.stderr,
                )
            except _HTTPAPIError as exc:
                self._log_upgrade_event(
                    "HTTP API error during upgrade",
                    stage=current_stage,
                    error_kind=exc.kind,
                    error_code=exc.code,
                    error=exc.message,
                    stderr_preview=_preview_text(exc.stderr),
                )
                return self._build_local_error_outcome(
                    device_id=device_id,
                    command=public_command,
                    code=exc.code,
                    kind=exc.kind,
                    message=exc.message,
                    stderr=exc.stderr,
                )
            except Exception as exc:
                self._log_upgrade_event(
                    "unexpected exception during file upgrade",
                    stage=current_stage,
                    error_type=exc.__class__.__name__,
                    error=str(exc),
                )
                raise

            self._log_upgrade_event("file upgrade request completed")
            return {
                "device_id": device_id,
                "command": public_command,
                "ok": True,
                "ssh_exit_code": None,
                "response": upgrade_payload,
                "stderr": None,
                "error": None,
            }
        finally:
            self._diagnostic_context = previous_context

    def _resolve_local_upgrade_path(self, raw_path):
        local_path = os.path.abspath(os.path.expanduser(raw_path))
        translated_path = None

        if os.name != "nt":
            translated_path = _windows_drive_path_to_posix_mount(raw_path)
            if translated_path is not None:
                translated_path = os.path.abspath(os.path.expanduser(translated_path))

        return local_path, translated_path

    def _open_api_tunnel(self, device_id, timeout_sec):
        return _SSHAPITunnel(
            self.bridge,
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
        boundary = "----------------agent-mcp-{0}-{1}".format(os.getpid(), int(time.time()))
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
        bytes_sent = 0
        next_progress_percent = 10
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
            self._log_upgrade_event(
                "upload request headers sent",
                host=host_header,
                remote_addr=LOCAL_API_REMOTE_ADDR,
                origin="https://{0}".format(host_header),
                referer="https://{0}/".format(host_header),
                filename=filename,
                file_size=file_size,
                content_length=content_length,
            )
            with open(local_path, "rb") as handle:
                while True:
                    chunk = handle.read(64 * 1024)
                    if not chunk:
                        break
                    connection.send(chunk)
                    bytes_sent += len(chunk)
                    if file_size > 0:
                        percent = int((bytes_sent * 100) / file_size)
                        while percent >= next_progress_percent and next_progress_percent < 100:
                            self._log_upgrade_event(
                                "upload progress",
                                bytes_sent=bytes_sent,
                                file_size=file_size,
                                percent=next_progress_percent,
                            )
                            next_progress_percent += 10
            connection.send(epilogue)
            self._log_upgrade_event(
                "upload body sent",
                bytes_sent=bytes_sent,
                content_length=content_length,
            )
            return self._read_http_response(connection, "upload")
        except _SSHStreamError as exc:
            percent = 0
            if file_size > 0:
                percent = int((bytes_sent * 100) / file_size)
            self._log_upgrade_event(
                "upload stream write failed",
                bytes_sent=bytes_sent,
                file_size=file_size,
                percent=percent,
                error=str(exc),
                stderr_preview=_preview_text(exc.stderr),
            )
            early_error = self._try_read_upload_error_response(connection)
            if early_error is not None:
                raise early_error
            raise _SSHTunnelError(exc.args[0] if exc.args else "SSH tunnel request failed", stderr=exc.stderr)
        except (OSError, http.client.HTTPException) as exc:
            percent = 0
            if file_size > 0:
                percent = int((bytes_sent * 100) / file_size)
            self._log_upgrade_event(
                "upload HTTP transport failed",
                bytes_sent=bytes_sent,
                file_size=file_size,
                percent=percent,
                error_type=exc.__class__.__name__,
                error=str(exc),
            )
            early_error = self._try_read_upload_error_response(connection)
            if early_error is not None:
                raise early_error
            raise _HTTPAPIError("transport_error", "http_upload_transport_error", str(exc) or "Firmware upload failed")
        finally:
            connection.close()

    def _try_read_upload_error_response(self, connection):
        try:
            self._log_upgrade_event("attempting to read early upload error response")
            payload = self._read_http_response(connection, "upload")
            self._log_upgrade_event(
                "received unexpected early upload response",
                response_preview=_preview_json(payload),
            )
        except _HTTPAPIError as exc:
            self._log_upgrade_event(
                "captured early upload HTTP error response",
                error_kind=exc.kind,
                error_code=exc.code,
                error=exc.message,
                stderr_preview=_preview_text(exc.stderr),
            )
            return exc
        except (_SSHStreamError, OSError, http.client.HTTPException, ValueError) as exc:
            self._log_upgrade_event(
                "no early upload HTTP response available",
                error_type=exc.__class__.__name__,
                error=str(exc),
            )
        return None

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
            self._log_upgrade_event(
                "sending HTTP API request",
                step=step,
                method=method,
                path=path,
                host=merged_headers.get("Host"),
                remote_addr=merged_headers.get("Remote-Addr"),
                origin=merged_headers.get("Origin"),
                referer=merged_headers.get("Referer"),
                connection_header=merged_headers.get("Connection"),
                has_authorization="Authorization" in merged_headers,
                body_bytes=len(body),
            )
            connection.request(method, path, body=body, headers=merged_headers)
            return self._read_http_response(connection, step)
        except _SSHStreamError as exc:
            raise _SSHTunnelError(exc.args[0] if exc.args else "SSH tunnel request failed", stderr=exc.stderr)
        except (OSError, http.client.HTTPException) as exc:
            kind = "http_login_transport_error" if path == "/api/v1/user/login" else "http_upgrade_transport_error"
            raise _HTTPAPIError("transport_error", kind, str(exc) or "HTTP request failed")
        finally:
            connection.close()

    def _read_http_response(self, connection, step):
        response = connection.getresponse()
        raw = response.read()
        payload = None
        text = raw.decode("utf-8", "replace").strip() if raw else ""

        if step in ("login", "upload", "upgrade"):
            self._log_upgrade_event(
                "received HTTP response",
                step=step,
                http_status=response.status,
                body_bytes=len(raw),
                body_preview=_preview_text(text),
            )

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
        if isinstance(payload, dict) and isinstance(payload.get("error"), str) and payload.get("error"):
            message = payload.get("error")
        elif text:
            message = text
        else:
            message = "HTTP {0} request failed with status {1}".format(step, http_status)

        if step in ("login", "upload", "upgrade"):
            self._log_upgrade_event(
                "HTTP API returned an error response",
                step=step,
                http_status=http_status,
                message_preview=_preview_text(message),
                body_preview=_preview_text(text),
            )

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

    def _validate_tool_wrapper_arguments(self, arguments):
        validated = self._validate_category_tool_arguments(self._find_tool_spec("tool"), arguments)
        subcommand = validated["command"][len("tool "):]
        tool_name, payload_text = self._split_tool_subcommand(subcommand)

        if tool_name == "tcpdump":
            tcpdump_arguments = self._parse_tool_json_payload(payload_text, tool_name)
            self._validate_tcpdump_arguments(tcpdump_arguments)
            return validated

        if tool_name != "speedtest":
            return validated

        speedtest_arguments = self._parse_tool_json_payload(payload_text, tool_name)
        speedtest_arguments["device_id"] = validated["device_id"]
        if "timeout_sec" in validated:
            speedtest_arguments["timeout_sec"] = validated["timeout_sec"]
        return self._validate_speedtest_arguments(speedtest_arguments)

    def _validate_tcpdump_arguments(self, arguments):
        if not isinstance(arguments, dict):
            raise JSONRPCError(ERR_INVALID_PARAMS, "tcpdump payload must be a JSON object")

        if "start_line" in arguments:
            self._reject_unknown_arguments(arguments, ["start_line"])
            start_line = arguments.get("start_line")
            if not isinstance(start_line, int) or start_line < 0:
                raise JSONRPCError(ERR_INVALID_PARAMS, "start_line must be a non-negative integer")
            return

        action = arguments.get("action")
        if action not in TCPDUMP_ACTIONS:
            raise JSONRPCError(
                ERR_INVALID_PARAMS,
                "action must be one of: {0}".format(", ".join(TCPDUMP_ACTIONS)),
            )

        if action == "start":
            if "interface" in arguments:
                raise JSONRPCError(ERR_INVALID_PARAMS, "interface is not supported for tcpdump; use local_iface")
            self._reject_unknown_arguments(arguments, ["action", "capture_mode", "capture_time", "local_iface"])

            capture_mode = arguments.get("capture_mode")
            if capture_mode not in TCPDUMP_CAPTURE_MODES:
                raise JSONRPCError(
                    ERR_INVALID_PARAMS,
                    "capture_mode must be one of: {0}".format(", ".join(TCPDUMP_CAPTURE_MODES)),
                )

            capture_time = arguments.get("capture_time")
            if not isinstance(capture_time, int) or capture_time < 0 or capture_time > 864000:
                raise JSONRPCError(ERR_INVALID_PARAMS, "capture_time must be an integer between 0 and 864000")

            local_iface = arguments.get("local_iface")
            if not isinstance(local_iface, list) or not local_iface:
                raise JSONRPCError(ERR_INVALID_PARAMS, "local_iface must be a non-empty array")

            if capture_mode == "show" and len(local_iface) != 1:
                raise JSONRPCError(ERR_INVALID_PARAMS, "show mode requires exactly one local_iface entry")

            for index, item in enumerate(local_iface):
                if not isinstance(item, dict):
                    raise JSONRPCError(ERR_INVALID_PARAMS, "local_iface items must be objects")
                if not isinstance(item.get("interface"), str):
                    raise JSONRPCError(
                        ERR_INVALID_PARAMS,
                        "local_iface[{0}].interface must be a string".format(index),
                    )
                if not isinstance(item.get("expert_options"), str):
                    raise JSONRPCError(
                        ERR_INVALID_PARAMS,
                        "local_iface[{0}].expert_options must be a string".format(index),
                    )
            return

        if action == "delete":
            self._reject_unknown_arguments(arguments, ["action", "capture_mode"])
            capture_mode = arguments.get("capture_mode")
            if capture_mode not in TCPDUMP_CAPTURE_MODES:
                raise JSONRPCError(
                    ERR_INVALID_PARAMS,
                    "capture_mode must be one of: {0}".format(", ".join(TCPDUMP_CAPTURE_MODES)),
                )
            return

        self._reject_unknown_arguments(arguments, ["action"])

    def _split_tool_subcommand(self, subcommand):
        parts = subcommand.split(None, 1)
        tool_name = parts[0]
        payload_text = ""
        if len(parts) == 2:
            payload_text = parts[1].strip()
        return tool_name, payload_text

    def _parse_tool_json_payload(self, payload_text, tool_name):
        if not payload_text:
            raise JSONRPCError(ERR_INVALID_PARAMS, "{0} payload must be a JSON object".format(tool_name))

        try:
            payload = json.loads(payload_text)
        except (TypeError, ValueError):
            raise JSONRPCError(ERR_INVALID_PARAMS, "{0} payload must be a valid JSON object".format(tool_name))

        if not isinstance(payload, dict):
            raise JSONRPCError(ERR_INVALID_PARAMS, "{0} payload must be a JSON object".format(tool_name))

        return payload

    def _validate_category_tool_arguments(self, tool_spec, arguments):
        if not isinstance(arguments, dict):
            raise JSONRPCError(ERR_INVALID_PARAMS, "Tool arguments must be an object")

        allowed_keys = ["device_id", "timeout_sec"]
        if tool_spec["requires_subcommand"] or tool_spec.get("accepts_subcommand"):
            allowed_keys.append("subcommand")
        self._reject_unknown_arguments(arguments, allowed_keys)

        validated = {
            "device_id": self._resolve_device_id(arguments),
            "command": tool_spec["name"],
        }
        timeout_sec = self._validate_timeout(arguments.get("timeout_sec"))

        if tool_spec["requires_subcommand"]:
            subcommand = self._require_command(arguments.get("subcommand"), "subcommand")
            validated["command"] = "{0} {1}".format(tool_spec["name"], subcommand)
        elif tool_spec.get("accepts_subcommand"):
            if "subcommand" in arguments:
                raw_subcommand = arguments.get("subcommand")
                if not (isinstance(raw_subcommand, str) and not raw_subcommand.strip()):
                    subcommand = self._require_command(raw_subcommand, "subcommand")
                    validated["command"] = "{0} {1}".format(tool_spec["name"], subcommand)
        elif "subcommand" in arguments:
            raise JSONRPCError(ERR_INVALID_PARAMS, "subcommand is not supported for {0}".format(tool_spec["name"]))

        if timeout_sec is not None:
            validated["timeout_sec"] = timeout_sec

        return validated

    def _validate_speedtest_arguments(self, arguments):
        if not isinstance(arguments, dict):
            raise JSONRPCError(ERR_INVALID_PARAMS, "Tool arguments must be an object")

        allowed_keys = [
            "device_id",
            "timeout_sec",
            "action",
            "server_id",
            "host",
            "interface",
            "ip",
            "start_line",
        ]
        self._reject_unknown_arguments(arguments, allowed_keys)

        action = arguments.get("action")
        if action not in SPEEDTEST_ACTIONS:
            raise JSONRPCError(ERR_INVALID_PARAMS, "action must be one of: {0}".format(", ".join(SPEEDTEST_ACTIONS)))

        validated = {
            "device_id": self._resolve_device_id(arguments),
            "command": "speedtest {0}".format(action),
        }
        timeout_sec = self._validate_timeout(arguments.get("timeout_sec"))

        if action == "start":
            if "start_line" in arguments:
                raise JSONRPCError(ERR_INVALID_PARAMS, "start_line is not supported for action start")

            if "host" in arguments:
                raise JSONRPCError(ERR_INVALID_PARAMS, "host is not supported for speedtest; use server_id from `servers`")

            if "interface" in arguments:
                raise JSONRPCError(ERR_INVALID_PARAMS, "interface is not supported for speedtest; use ip")

            if "server_id" in arguments:
                server_id = arguments.get("server_id")
                if not isinstance(server_id, int) or server_id < 1:
                    raise JSONRPCError(ERR_INVALID_PARAMS, "server_id must be a positive integer")
                validated["command"] += " --server-id {0}".format(server_id)

            if "ip" in arguments:
                validated["command"] += " --ip {0}".format(self._require_token(arguments.get("ip"), "ip"))

        elif action == "output":
            unsupported = [key for key in ("server_id", "host", "interface", "ip") if key in arguments]
            if unsupported:
                raise JSONRPCError(ERR_INVALID_PARAMS, "{0} is not supported for action output".format(unsupported[0]))

            start_line = arguments.get("start_line", 0)
            if not isinstance(start_line, int) or start_line < 0:
                raise JSONRPCError(ERR_INVALID_PARAMS, "start_line must be a non-negative integer")
            validated["command"] += " --start-line {0}".format(start_line)

        else:
            unsupported = [key for key in ("server_id", "host", "interface", "ip", "start_line") if key in arguments]
            if unsupported:
                raise JSONRPCError(ERR_INVALID_PARAMS, "{0} is not supported for action {1}".format(unsupported[0], action))

        if timeout_sec is not None:
            validated["timeout_sec"] = timeout_sec

        return validated

    def _resolve_device_id(self, arguments):
        if "device_id" in arguments:
            return self._require_known_device(arguments.get("device_id"))

        default_device_id_getter = getattr(self.bridge, "get_default_device_id", None)
        if callable(default_device_id_getter):
            default_device_id = default_device_id_getter()
            if default_device_id is not None:
                return self._require_known_device(default_device_id)

        device_ids_getter = getattr(self.bridge, "get_device_ids", None)
        configured_device_ids = []
        if callable(device_ids_getter):
            configured_device_ids = list(device_ids_getter())

        raise JSONRPCError(
            ERR_INVALID_PARAMS,
            "device_id is required when multiple devices are configured",
            {
                "configured_device_ids": configured_device_ids,
            },
        )

    def _require_known_device(self, value):
        device_id = self._require_token(value, "device_id")
        if not self.bridge.has_device(device_id):
            raise JSONRPCError(
                ERR_INVALID_PARAMS,
                "Unknown device_id",
                {"configured_device_ids": self._list_configured_device_ids()},
            )
        return device_id

    def _list_configured_device_ids(self):
        device_ids_getter = getattr(self.bridge, "get_device_ids", None)
        if callable(device_ids_getter):
            return list(device_ids_getter())
        return []

    def _validate_timeout(self, timeout_sec, maximum=120):
        if timeout_sec is None:
            return None
        if not isinstance(timeout_sec, int) or timeout_sec < 1 or timeout_sec > maximum:
            raise JSONRPCError(
                ERR_INVALID_PARAMS,
                "timeout_sec must be an integer between 1 and {0}".format(maximum),
            )
        return timeout_sec

    def _reject_unknown_arguments(self, arguments, allowed_keys):
        allowed = set(allowed_keys)
        unknown_keys = sorted([key for key in arguments.keys() if key not in allowed])
        if unknown_keys:
            raise JSONRPCError(ERR_INVALID_PARAMS, "Unknown argument: {0}".format(unknown_keys[0]))

    def _require_token(self, value, field_name):
        if not isinstance(value, str) or not value:
            raise JSONRPCError(ERR_INVALID_PARAMS, "{0} must be a non-empty string".format(field_name))
        if any(character.isspace() for character in value):
            raise JSONRPCError(ERR_INVALID_PARAMS, "{0} must not contain whitespace".format(field_name))
        if "\n" in value or "\r" in value:
            raise JSONRPCError(ERR_INVALID_PARAMS, "{0} must not contain newlines".format(field_name))
        return value

    def _require_command(self, value, field_name):
        if not isinstance(value, str) or not value.strip():
            raise JSONRPCError(ERR_INVALID_PARAMS, "{0} must be a non-empty string".format(field_name))
        if "\n" in value or "\r" in value:
            raise JSONRPCError(ERR_INVALID_PARAMS, "{0} must not contain newlines".format(field_name))
        return value.strip()

    def _require_upgrade_url(self, value):
        url = self._require_command(value, "url")
        if any(character.isspace() for character in url):
            raise JSONRPCError(ERR_INVALID_PARAMS, "url must not contain whitespace")

        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise JSONRPCError(ERR_INVALID_PARAMS, "url must be an http or https URL")

        return url

    def _resource_definitions(self):
        return [
            self._resource_definition(device_id, resource_spec)
            for device_id in self.bridge.get_device_ids()
            for resource_spec in RESOURCE_SPECS
        ]

    def _resource_definition(self, device_id, resource_spec):
        return {
            "uri": self._build_resource_uri(device_id, resource_spec),
            "name": "{0}: {1}".format(device_id, resource_spec["name"]),
            "description": resource_spec["description"],
            "mimeType": resource_spec["mime_type"],
        }

    def _build_resource_uri(self, device_id, resource_spec):
        return "{0}://{1}{2}".format(
            RESOURCE_URI_SCHEME,
            quote(device_id, safe=""),
            resource_spec["path"],
        )

    def _parse_resource_uri(self, value):
        uri = self._require_token(value, "uri")
        parsed = urlsplit(uri)
        if parsed.scheme != RESOURCE_URI_SCHEME or not parsed.netloc or parsed.query or parsed.fragment:
            raise JSONRPCError(ERR_INVALID_PARAMS, "Invalid resource uri")

        resource_spec = self._find_resource_spec(parsed.path)
        if resource_spec is None:
            raise JSONRPCError(ERR_INVALID_PARAMS, "Unknown resource uri")

        device_id = self._require_known_device(unquote(parsed.netloc))
        return {
            "device_id": device_id,
            "resource_spec": resource_spec,
            "uri": self._build_resource_uri(device_id, resource_spec),
        }

    def _find_resource_spec(self, path):
        for spec in RESOURCE_SPECS:
            if spec["path"] == path:
                return spec
        return None

    def _tool_definitions(self):
        return [self._tool_definition(spec) for spec in TOOL_SPECS]

    def _tool_definition(self, tool_spec):
        properties = {
            "device_id": {
                "type": "string",
                "description": "Configured device identifier. Optional when the server config contains exactly one device.",
            },
            "timeout_sec": {
                "type": "integer",
                "minimum": 1,
                "maximum": 120,
                "description": "Optional per-call SSH timeout override in seconds.",
            },
        }
        if tool_spec["name"] == "upgrade":
            properties["timeout_sec"] = {
                "type": "integer",
                "minimum": 1,
                "maximum": MAX_UPGRADE_TIMEOUT_SEC,
                "description": (
                    "Optional per-call upgrade timeout override in seconds. "
                    "When omitted, upgrades default to a higher timeout for firmware transfer."
                ),
            }
        required = []

        if tool_spec["requires_subcommand"] or tool_spec.get("accepts_subcommand"):
            properties["subcommand"] = {
                "type": "string",
                "description": tool_spec["subcommand_description"],
            }
            if tool_spec["requires_subcommand"]:
                required.append("subcommand")
        properties.update(tool_spec.get("input_properties", {}))
        required.extend(tool_spec.get("input_required", []))

        return {
            "name": tool_spec["name"],
            "title": tool_spec["title"],
            "description": tool_spec["description"],
            "inputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
            "outputSchema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "device_id": {"type": "string"},
                    "command": {"type": "string"},
                    "ok": {"type": "boolean"},
                    "ssh_exit_code": {"type": ["integer", "null"]},
                    "data": {},
                    "stderr": {"type": ["string", "null"]},
                    "error": {
                        "type": ["object", "null"],
                        "properties": {
                            "code": {"type": "string"},
                            "kind": {"type": "string"},
                            "message": {"type": "string"},
                            "field": {"type": ["string", "null"]},
                        },
                        "required": ["code", "message"],
                        "additionalProperties": True,
                    },
                },
                "required": ["device_id", "command", "ok", "ssh_exit_code", "data", "stderr", "error"],
                "additionalProperties": False,
            },
            "annotations": tool_spec["annotations"],
        }

    def _build_local_error_outcome(self, device_id, command, code, kind, message, stderr=None):
        return {
            "device_id": device_id,
            "command": command,
            "ok": False,
            "ssh_exit_code": None,
            "response": None,
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

    def _result_response(self, request_id, result):
        return {
            "jsonrpc": JSONRPC_VERSION,
            "id": request_id,
            "result": result,
        }

    def _error_response(self, request_id, error):
        payload = {
            "jsonrpc": JSONRPC_VERSION,
            "id": request_id,
            "error": {
                "code": error.code,
                "message": error.message,
            },
        }
        if error.data is not None:
            payload["error"]["data"] = error.data
        return payload


def _build_stream(handle, mode):
    # On Windows, return the original handle because stdin/stdout cannot be reopened via fileno().
    if sys.platform == "win32":
        return handle
    return io.open(handle.fileno(), mode, encoding="utf-8", newline="\n", closefd=False)


class _MultiWriter(object):
    def __init__(self, *handles):
        self._handles = [handle for handle in handles if handle is not None]

    def write(self, payload):
        for handle in self._handles:
            handle.write(payload)

    def flush(self):
        for handle in self._handles:
            handle.flush()


def _format_log_value(value):
    if isinstance(value, float):
        return "{0:.2f}".format(value)
    if isinstance(value, (int, bool)) or value is None:
        return json.dumps(value, sort_keys=True)
    if isinstance(value, (list, dict, tuple)):
        return json.dumps(value, sort_keys=True)
    return json.dumps(str(value))


def _preview_text(value, limit=200):
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "...(truncated)"


def _preview_json(value, limit=200):
    try:
        payload = json.dumps(value, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError):
        payload = str(value)
    return _preview_text(payload, limit=limit)


def _build_trace_id(prefix, device_id):
    return "{0}-{1}-{2}".format(prefix, device_id, int(time.time() * 1000))


def _open_server_log_file(runtime_dir):
    log_path = _resolve_server_log_path(runtime_dir)
    log_dir = os.path.dirname(log_path)
    os.makedirs(log_dir, mode=0o700, exist_ok=True)
    return log_path, io.open(log_path, "a", encoding="utf-8", newline="\n")


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


def _paths_equal(left, right):
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


class _StoreConfigPathAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
        setattr(namespace, "config_explicit", True)


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ConfigError(message)


def _format_missing_default_config_error(config_path):
    example_payload = {
        "devices": {
            "lab-ir624": {
                "device_ip": "192.0.2.10",
                "pass": "replace-me",
                "user": "adm",
            }
        }
    }
    return "\n".join(
        [
            "Configuration error: default config file does not exist: {0}".format(config_path),
            "Create the file with mode 0600. Minimal example:",
            json.dumps(example_payload, indent=2, sort_keys=True),
            "Starter template: {0}".format(DEFAULT_PROJECT_CONFIG_EXAMPLE_PATH),
            "Or start without a config file by passing one or more --device values.",
            "Use --config /path/to/devices.json to load a config from a different location.",
        ]
    )


def _resolve_runtime_dir(runtime_dir):
    runtime_dir = runtime_dir or DEFAULT_RUNTIME_DIR
    return os.path.abspath(os.path.expanduser(runtime_dir))


def _resolve_log_dir(runtime_dir):
    return os.path.join(_resolve_runtime_dir(runtime_dir), DEFAULT_RUNTIME_LOGS_DIR_NAME)


def _resolve_server_log_path(runtime_dir):
    return os.path.join(_resolve_log_dir(runtime_dir), DEFAULT_SERVER_LOG_FILE_NAME)


def _parse_device_spec(spec):
    if not isinstance(spec, str) or not spec.strip():
        raise ConfigError("--device must be a non-empty string")

    parsed = {}
    for raw_field in spec.split(","):
        field = raw_field.strip()
        if not field:
            raise ConfigError("Invalid --device value: empty field in `{0}`".format(spec))
        if "=" not in field:
            raise ConfigError(
                "Invalid --device field `{0}`. Expected key=value pairs.".format(field)
            )
        key, value = field.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key not in DEVICE_SPEC_FIELD_MAP:
            raise ConfigError("Unsupported --device field `{0}`".format(key))
        if not value:
            raise ConfigError("--device field `{0}` must be a non-empty string".format(key))
        if key in parsed:
            raise ConfigError("Duplicate --device field `{0}`".format(key))
        parsed[key] = value

    missing_fields = [field for field in DEVICE_SPEC_REQUIRED_FIELDS if field not in parsed]
    if missing_fields:
        raise ConfigError(
            "--device is missing required field(s): {0}".format(", ".join(missing_fields))
        )

    try:
        port = int(parsed.get("port", "22"))
    except ValueError:
        raise ConfigError("--device field `port` must be a positive integer")
    if port <= 0:
        raise ConfigError("--device field `port` must be a positive integer")

    return {
        "name": parsed["name"],
        "device_ip": parsed["device_ip"],
        "agent_user": parsed.get("agent_user", "agent"),
        "user": parsed.get("user", "adm"),
        "pass": parsed["pass"],
        "port": port,
    }


def _build_inline_config(device_specs, runtime_dir):
    devices = {}
    for spec in device_specs:
        device = _parse_device_spec(spec)
        device_id = device["name"]
        if device_id in devices:
            raise ConfigError("Duplicate device name `{0}` in --device arguments".format(device_id))
        devices[device_id] = {
            "device_ip": device["device_ip"],
            "agent_user": device["agent_user"],
            "user": device["user"],
            "pass": device["pass"],
            "port": device["port"],
        }

    resolved_runtime_dir = _resolve_runtime_dir(runtime_dir)
    return {
        "ssh_defaults": {
            "keys_base_dir": os.path.join(resolved_runtime_dir, DEFAULT_RUNTIME_KEYS_DIR_NAME),
            "control_path_dir": os.path.join(resolved_runtime_dir, DEFAULT_RUNTIME_CONTROL_PATH_DIR_NAME),
        },
        "devices": devices,
    }


def _write_json_line(stdout_handle, payload):
    stdout_handle.write(json.dumps(payload, separators=(",", ":"), sort_keys=True))
    stdout_handle.write("\n")
    stdout_handle.flush()


def serve(server, stdin_handle, stdout_handle, stderr_handle):
    for raw_line in stdin_handle:
        line = raw_line.strip()
        if not line:
            continue

        try:
            message = json.loads(line)
        except ValueError:
            _write_json_line(
                stdout_handle,
                {
                    "jsonrpc": JSONRPC_VERSION,
                    "id": None,
                    "error": {
                        "code": ERR_PARSE,
                        "message": "Parse error",
                    },
                },
            )
            continue

        try:
            response = server.process_message(message)
        except JSONRPCError as exc:
            request_id = message.get("id") if isinstance(message, dict) else None
            response = server._error_response(request_id, exc)
        except Exception as exc:
            stderr_handle.write("Unhandled server error: {0}\n".format(exc))
            stderr_handle.write(traceback.format_exc())
            stderr_handle.flush()
            request_id = message.get("id") if isinstance(message, dict) else None
            response = server._error_response(request_id, JSONRPCError(ERR_INTERNAL, "Internal error"))

        if response is not None:
            _write_json_line(stdout_handle, response)


def parse_args(argv):
    parser = _ArgumentParser(description="External MCP server for remote device CLI execution.")
    parser.set_defaults(config=DEFAULT_PROJECT_CONFIG_PATH, config_explicit=False)
    parser.add_argument(
        "--config",
        action=_StoreConfigPathAction,
        help="Path to the device configuration JSON file. Defaults to {0}.".format(DEFAULT_PROJECT_CONFIG_PATH),
    )
    parser.add_argument(
        "--device",
        action="append",
        default=[],
        help=(
            "Inline device definition: "
            "name=<id>,device_ip=<ip>,pass=<password>[,user=<web_user>][,port=<port>]. "
            "Repeat --device to configure multiple devices without a JSON config file."
        ),
    )
    parser.add_argument(
        "--runtime-dir",
        default=None,
        help=(
            "Base directory for generated SSH keys, known_hosts, and control sockets when using --device. "
            "Defaults to {0}.".format(_resolve_runtime_dir(DEFAULT_RUNTIME_DIR))
        ),
    )
    parser.add_argument("--takeover", action="store_true", help="Force takeover when another MCP server currently holds the device lease.")
    parser.add_argument(
        "--log-file",
        action="store_true",
        default=os.environ.get("AGENT_MCP_LOG_FILE") == "1",
        help=(
            "Write diagnostic events to {0} in addition to stderr. "
            "Off by default; events still go to stderr (captured by your MCP client). "
            "Also enabled when AGENT_MCP_LOG_FILE=1.".format(
                os.path.join(_resolve_log_dir(DEFAULT_RUNTIME_DIR), DEFAULT_SERVER_LOG_FILE_NAME)
            )
        ),
    )
    return parser.parse_args(argv)


def _handle_termination_signal(signum, frame):
    raise SystemExit(0)


def main(argv=None):
    options = parse_args(argv if argv is not None else sys.argv[1:])
    try:
        if options.device:
            if options.config_explicit:
                print("Configuration error: --config cannot be used together with --device", file=sys.stderr)
                return EXIT_BADARGS
            inline_config = _build_inline_config(options.device, options.runtime_dir)
            bridge = SSHBridge.from_config_data(
                inline_config,
                base_dir=_resolve_runtime_dir(options.runtime_dir),
                takeover=options.takeover,
            )
        else:
            if options.runtime_dir is not None:
                print("Configuration error: --runtime-dir requires at least one --device", file=sys.stderr)
                return EXIT_BADARGS
            config_path = os.path.abspath(options.config)
            if not os.path.exists(config_path):
                if _paths_equal(config_path, DEFAULT_PROJECT_CONFIG_PATH):
                    print(_format_missing_default_config_error(config_path), file=sys.stderr)
                else:
                    print("Configuration error: config file does not exist: {0}".format(config_path), file=sys.stderr)
                return EXIT_NOTFOUND
            bridge = SSHBridge(config_path, takeover=options.takeover)
    except ConfigError as exc:
        print("Configuration error: {0}".format(exc), file=sys.stderr)
        return EXIT_BADARGS

    stdin_handle = _build_stream(sys.stdin, "r")
    stdout_handle = _build_stream(sys.stdout, "w")
    stderr_handle = _build_stream(sys.stderr, "w")
    log_runtime_dir = options.runtime_dir if options.device else None
    log_path = _resolve_server_log_path(log_runtime_dir)
    log_file_handle = None
    log_writer = stderr_handle
    if options.log_file:
        try:
            log_path, log_file_handle = _open_server_log_file(log_runtime_dir)
            log_writer = _MultiWriter(stderr_handle, log_file_handle)
        except (IOError, OSError) as exc:
            try:
                stderr_handle.write(
                    "Warning: unable to open MCP diagnostic log file {0}: {1}\n".format(log_path, exc)
                )
                stderr_handle.flush()
            except (AttributeError, IOError, OSError, ValueError):
                pass

    server = ExternalCliMCPServer(bridge)
    server.set_log_handle(log_writer)
    if log_file_handle is not None:
        server._log_diagnostic("server", "diagnostic logging initialized", log_path=log_path)
    signal.signal(signal.SIGINT, _handle_termination_signal)
    # Windows may not expose SIGTERM, so guard the handler registration.
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_termination_signal)

    try:
        serve(server, stdin_handle, stdout_handle, log_writer)
    finally:
        try:
            if log_file_handle is not None:
                log_file_handle.close()
        finally:
            bridge.close()
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
