from __future__ import print_function

import json
import os
from urllib.parse import urlsplit

try:
    from .ssh_bridge import ConfigError
except (ImportError, SystemError, ValueError):
    from ssh_bridge import ConfigError

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NOTFOUND = 2
EXIT_TIMEOUT = 3
EXIT_BADARGS = 4

ERR_INVALID_PARAMS = -32602

DEFAULT_RUNTIME_KEYS_DIR_NAME = "keys"
DEFAULT_RUNTIME_CONTROL_PATH_DIR_NAME = "ssh-control"
DEFAULT_UPGRADE_TIMEOUT_SEC = 600
MAX_UPGRADE_TIMEOUT_SEC = 1800
DEVICE_SPEC_REQUIRED_FIELDS = ("name", "host", "pass")
DEVICE_SPEC_FIELD_MAP = {
    "name": "name",
    "host": "host",
    "pass": "bootstrap_password",
    "buser": "bootstrap_user",
    "user": "user",
    "port": "port",
}

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

TCPDUMP_CAPTURE_MODES = [
    "show",
]

TOOL_SPECS = [
    {
        "name": "status",
        "requires_subcommand": False,
        "accepts_subcommand": True,
    },
    {
        "name": "config",
        "requires_subcommand": True,
    },
    {
        "name": "log",
        "requires_subcommand": False,
        "accepts_subcommand": True,
    },
    {
        "name": "schema",
        "requires_subcommand": True,
    },
    {
        "name": "upgrade",
        "requires_subcommand": False,
    },
    {
        "name": "reboot",
        "requires_subcommand": False,
    },
    {
        "name": "tool",
        "requires_subcommand": True,
    },
]


class JSONRPCError(Exception):
    def __init__(self, code, message, data=None):
        super(JSONRPCError, self).__init__(message)
        self.code = code
        self.message = message
        self.data = data


class CommandSurface(object):
    def __init__(self, bridge):
        self.bridge = bridge

    def _find_tool_spec(self, tool_name):
        for spec in TOOL_SPECS:
            if spec["name"] == tool_name:
                return spec
        return None

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
            if isinstance(error.get("details"), dict):
                normalized["details"] = error["details"]
            public["error"] = normalized

        return public

    def _execute_validated_call(self, validated):
        outcome = self.bridge.execute(
            validated["device_id"],
            command=validated["command"],
            timeout_sec=validated.get("timeout_sec"),
        )
        outcome = self._augment_outcome_for_command(validated["command"], outcome)
        return outcome

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
            raise JSONRPCError(ERR_INVALID_PARAMS, "Unknown device_id")
        return device_id

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


def _resolve_runtime_dir(runtime_dir):
    runtime_dir = runtime_dir or os.path.join("~", ".agent-cli")
    return os.path.abspath(os.path.expanduser(runtime_dir))


def _parse_device_spec(spec):
    if not isinstance(spec, str) or not spec.strip():
        raise ConfigError("--device must be a non-empty string")

    parsed = {}
    for raw_field in spec.split(","):
        field = raw_field.strip()
        if not field:
            raise ConfigError("Invalid --device value: empty field in `{0}`".format(spec))
        if "=" not in field:
            raise ConfigError("Invalid --device field `{0}`. Expected key=value pairs.".format(field))
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
        raise ConfigError("--device is missing required field(s): {0}".format(", ".join(missing_fields)))

    try:
        port = int(parsed.get("port", "22"))
    except ValueError:
        raise ConfigError("--device field `port` must be a positive integer")
    if port <= 0:
        raise ConfigError("--device field `port` must be a positive integer")

    return {
        "name": parsed["name"],
        "host": parsed["host"],
        "user": parsed.get("user", "agent"),
        "bootstrap_user": parsed.get("buser", "adm"),
        "bootstrap_password": parsed["pass"],
        "port": port,
    }


def build_inline_config(device_specs, runtime_dir):
    devices = {}
    for spec in device_specs:
        device = _parse_device_spec(spec)
        device_id = device["name"]
        if device_id in devices:
            raise ConfigError("Duplicate device name `{0}` in --device arguments".format(device_id))
        devices[device_id] = {
            "host": device["host"],
            "user": device["user"],
            "bootstrap_user": device["bootstrap_user"],
            "bootstrap_password": device["bootstrap_password"],
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
