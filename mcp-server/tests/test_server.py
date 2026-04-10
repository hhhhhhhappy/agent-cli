from __future__ import print_function

import io
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from external_mcp_server.server import (
    CATEGORY_TOOL_NAMES,
    DEFAULT_PROJECT_CONFIG_PATH,
    DEFAULT_RUNTIME_CONTROL_PATH_DIR_NAME,
    DEFAULT_RUNTIME_KEYS_DIR_NAME,
    EXIT_BADARGS,
    EXIT_NOTFOUND,
    ERR_INTERNAL,
    ERR_INVALID_PARAMS,
    ERR_NOT_INITIALIZED,
    _build_inline_config,
    _parse_device_spec,
    ExternalCliMCPServer,
    main,
    parse_args,
)
from external_mcp_server.ssh_bridge import ConfigError


class FakeBridge(object):
    def __init__(self, device_ids=None, responder=None):
        self.calls = []
        if device_ids is None:
            device_ids = ["device-a"]
        self.devices = {device_id: True for device_id in device_ids}
        self.responder = responder

    def has_device(self, device_id):
        return device_id in self.devices

    def get_device_ids(self):
        return sorted(self.devices.keys())

    def get_default_device_id(self):
        device_ids = self.get_device_ids()
        if len(device_ids) == 1:
            return device_ids[0]
        return None

    def execute(self, device_id, verb=None, target=None, args=None, timeout_sec=None, command=None):
        call = {
            "device_id": device_id,
            "verb": verb,
            "target": target,
            "args": args,
            "timeout_sec": timeout_sec,
            "command": command or "{0} {1}".format(verb, target),
        }
        self.calls.append(call)
        if self.responder is not None:
            response = self.responder(call)
            if response is not None:
                return response
        return self.ok_result(call["device_id"], call["command"], {})

    def ok_result(self, device_id, command, response):
        if isinstance(response, dict) and isinstance(response.get("status"), int):
            response = dict(response)
            response.pop("status", None)
        return {
            "device_id": device_id,
            "command": command,
            "ok": True,
            "ssh_exit_code": 0,
            "response": response,
            "stderr": None,
            "error": None,
        }


class ExternalCliMCPServerTest(unittest.TestCase):
    def setUp(self):
        self.bridge = FakeBridge()
        self.server = ExternalCliMCPServer(self.bridge)

    def _initialize_server(self):
        self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"},
                },
            }
        )
        self.server.process_message(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
        )

    def test_requires_initialize_before_tool_requests(self):
        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
            }
        )

        self.assertEqual(response["error"]["code"], ERR_NOT_INITIALIZED)

    def test_requires_initialize_before_resource_requests(self):
        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "resources/list",
            }
        )

        self.assertEqual(response["error"]["code"], ERR_NOT_INITIALIZED)

    def test_initialize_advertises_resources_capability(self):
        init_response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"},
                },
            }
        )

        self.assertEqual(
            init_response["result"]["capabilities"]["resources"],
            {"subscribe": False, "listChanged": False},
        )

    def test_initialize_then_list_tools(self):
        init_response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "test-client",
                        "version": "1.0.0",
                    },
                },
            }
        )

        self.assertEqual(init_response["result"]["protocolVersion"], "2025-06-18")

        self.server.process_message(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
        )

        tools_response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
            }
        )

        tool_names = [tool["name"] for tool in tools_response["result"]["tools"]]
        self.assertEqual(tool_names, CATEGORY_TOOL_NAMES)
        self.assertIn("tool", tool_names)
        self.assertNotIn("speedtest", tool_names)

    def test_status_tool_call_executes_bridge(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "status",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "basic",
                    },
                },
            }
        )

        self.assertEqual(self.bridge.calls[0]["command"], "status basic")
        self.assertNotIn("isError", response["result"])
        self.assertEqual(response["result"]["structuredContent"]["data"], {})

    def test_status_tool_call_without_subcommand_executes_bridge(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "status",
                    "arguments": {
                        "device_id": "device-a",
                    },
                },
            }
        )

        self.assertEqual(self.bridge.calls[0]["command"], "status")
        self.assertNotIn("isError", response["result"])
        self.assertEqual(response["result"]["structuredContent"]["data"], {})

    def test_status_tool_call_with_empty_subcommand_executes_bridge(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "status",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "",
                    },
                },
            }
        )

        self.assertEqual(self.bridge.calls[0]["command"], "status")
        self.assertNotIn("isError", response["result"])
        self.assertEqual(response["result"]["structuredContent"]["data"], {})

    def test_log_tool_call_without_subcommand_executes_bridge(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "log",
                    "arguments": {
                        "device_id": "device-a",
                    },
                },
            }
        )

        self.assertEqual(self.bridge.calls[0]["command"], "log")
        self.assertNotIn("isError", response["result"])
        self.assertEqual(response["result"]["structuredContent"]["data"], {})

    def test_log_tool_call_with_empty_subcommand_executes_bridge(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "log",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "",
                    },
                },
            }
        )

        self.assertEqual(self.bridge.calls[0]["command"], "log")
        self.assertNotIn("isError", response["result"])
        self.assertEqual(response["result"]["structuredContent"]["data"], {})

    def test_log_tool_subcommand_is_optional_in_schema(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
            }
        )

        log_tool = next(tool for tool in response["result"]["tools"] if tool["name"] == "log")
        self.assertIn("subcommand", log_tool["inputSchema"]["properties"])
        self.assertNotIn("subcommand", log_tool["inputSchema"].get("required", []))

    def test_status_tool_rejects_redundant_status_prefix(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "status",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "status basic",
                    },
                },
            }
        )

        self.assertEqual(response["error"]["code"], ERR_INVALID_PARAMS)
        self.assertEqual(
            response["error"]["message"],
            "status subcommand must omit the `status` prefix; use no subcommand, `basic`, `list`, or `<key>`",
        )

    def test_show_tool_is_removed(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "show",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "status basic",
                    },
                },
            }
        )

        self.assertEqual(response["error"]["code"], ERR_INVALID_PARAMS)
        self.assertEqual(
            response["error"]["message"],
            "The `show` tool has been removed; use `status` for runtime state or `config get <key>` for configuration reads",
        )

    def test_config_tool_rejects_old_set_format(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "config",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "system {\"hostname\":\"branch-ir624\"}",
                    },
                },
            }
        )

        self.assertEqual(response["error"]["code"], ERR_INVALID_PARAMS)
        self.assertEqual(
            response["error"]["message"],
            "legacy `config <key> <payload>` is no longer supported; use `config set <key> <payload>`",
        )

    def test_config_get_tool_call_executes_bridge(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "config",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "get system",
                    },
                },
            }
        )

        self.assertEqual(self.bridge.calls[0]["command"], "config get system")
        self.assertNotIn("isError", response["result"])
        self.assertEqual(response["result"]["structuredContent"]["data"], {})

    def test_config_list_tool_call_executes_bridge(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "config",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "list",
                    },
                },
            }
        )

        self.assertEqual(
            [call["command"] for call in self.bridge.calls],
            ["status basic", "config list"],
        )
        self.assertNotIn("isError", response["result"])
        self.assertEqual(response["result"]["structuredContent"]["data"], {})

    def test_config_get_list_is_rejected(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "config",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "get list",
                    },
                },
            }
        )

        self.assertEqual(response["error"]["code"], ERR_INVALID_PARAMS)
        self.assertEqual(
            response["error"]["message"],
            "`config get list` has been renamed to `config list`",
        )

    def test_config_set_tool_call_executes_bridge(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "config",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "set system {\"hostname\":\"branch-ir624\"}",
                    },
                },
            }
        )

        self.assertEqual(self.bridge.calls[0]["command"], "config set system {\"hostname\":\"branch-ir624\"}")
        self.assertNotIn("isError", response["result"])
        self.assertEqual(response["result"]["structuredContent"]["data"], {})

    def test_schema_list_executes_bridge(self):
        def responder(call):
            if call["command"] == "schema list":
                return self.bridge.ok_result(
                    call["device_id"],
                    call["command"],
                    {
                        "status": 200,
                        "result": {
                            "schemas": [
                                {"key": "cellular", "description": "Cellular interface status"},
                                {"key": "signal_history_info", "description": "Signal history information"},
                            ]
                        },
                    },
                )
            return None

        self.bridge = FakeBridge(responder=responder)
        self.server = ExternalCliMCPServer(self.bridge)
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "schema",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "list",
                    },
                },
            }
        )

        self.assertEqual(
            [call["command"] for call in self.bridge.calls[:2]],
            ["status basic", "schema list"],
        )
        schemas = response["result"]["structuredContent"]["data"]["result"]["schemas"]
        self.assertEqual([item["key"] for item in schemas], ["cellular", "signal_history_info"])

    def test_schema_cellular_executes_bridge_and_returns_unified_schema(self):
        def responder(call):
            if call["command"] == "schema cellular":
                return self.bridge.ok_result(
                    call["device_id"],
                    call["command"],
                    {
                        "status": 200,
                        "result": {
                            "device_type": "router",
                            "resources": {
                                "cellular": {
                                    "description": "Settings for the cellular interface",
                                    "config": {
                                        "type": "object",
                                    },
                                    "status": {
                                        "type": "object",
                                        "properties": {
                                            "status": {
                                                "description": "Interface state. Common values: up connected, down disconnected, detect_fail probe failed, disabled disabled."
                                            }
                                        },
                                    },
                                },
                            },
                        },
                    },
                )
            return None

        self.bridge = FakeBridge(responder=responder)
        self.server = ExternalCliMCPServer(self.bridge)
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "schema",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "cellular",
                    },
                },
            }
        )

        outcome = response["result"]["structuredContent"]
        self.assertEqual(self.bridge.calls[0]["command"], "schema cellular")
        self.assertEqual(outcome["command"], "schema cellular")
        self.assertEqual(outcome["data"]["result"]["device_type"], "router")
        self.assertEqual(
            outcome["data"]["result"]["resources"]["cellular"]["status"]["properties"]["status"]["description"],
            "Interface state. Common values: up connected, down disconnected, detect_fail probe failed, disabled disabled.",
        )

    def test_schema_signal_history_info_executes_bridge_and_returns_status_only_schema(self):
        def responder(call):
            if call["command"] == "schema signal_history_info":
                return self.bridge.ok_result(
                    call["device_id"],
                    call["command"],
                    {
                        "status": 200,
                        "result": {
                            "device_type": "router",
                            "resources": {
                                "signal_history_info": {
                                    "description": "Signal history information",
                                    "status": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "timestamp": {
                                                    "description": "Timestamp for this signal sample."
                                                }
                                            },
                                        }
                                    },
                                },
                            },
                        },
                    },
                )
            return None

        self.bridge = FakeBridge(responder=responder)
        self.server = ExternalCliMCPServer(self.bridge)
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "schema",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "signal_history_info",
                    },
                },
            }
        )

        schema = response["result"]["structuredContent"]["data"]["result"]["resources"]["signal_history_info"]["status"]
        self.assertEqual(self.bridge.calls[0]["command"], "schema signal_history_info")
        self.assertEqual(schema["type"], "array")
        self.assertEqual(schema["items"]["properties"]["timestamp"]["description"], "Timestamp for this signal sample.")

    def test_schema_rejects_legacy_status_syntax(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "schema",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "status cellular",
                    },
                },
            }
        )

        self.assertEqual(response["error"]["code"], ERR_INVALID_PARAMS)
        self.assertEqual(
            response["error"]["message"],
            "`schema status ...` has been removed; use `schema <key>` and inspect the returned `status` section",
        )

    def test_schema_rejects_nested_path(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "schema",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "system.hostname",
                    },
                },
            }
        )

        self.assertEqual(response["error"]["code"], ERR_INVALID_PARAMS)
        self.assertEqual(
            response["error"]["message"],
            "schema only supports root keys; nested paths such as `system.hostname` are not supported",
        )

    def test_schema_config_query_still_executes_bridge(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "schema",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "wan",
                    },
                },
            }
        )

        self.assertEqual(self.bridge.calls[0]["command"], "schema wan")
        self.assertNotIn("isError", response["result"])

    def test_status_tool_call_uses_default_device_when_single_device_is_configured(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "status",
                    "arguments": {
                        "subcommand": "basic",
                    },
                },
            }
        )

        self.assertEqual(self.bridge.calls[0]["device_id"], "device-a")
        self.assertEqual(self.bridge.calls[0]["command"], "status basic")
        self.assertNotIn("isError", response["result"])

    def test_reboot_tool_call_executes_bridge_without_subcommand(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "reboot",
                    "arguments": {
                        "device_id": "device-a",
                    },
                },
            }
        )

        self.assertEqual(self.bridge.calls[0]["command"], "reboot")
        self.assertNotIn("isError", response["result"])

    def test_tool_speedtest_start_subcommand_executes_bridge(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "tool",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "speedtest {\"action\":\"start\",\"server_id\":12345,\"ip\":\"198.51.100.10\"}",
                    },
                },
            }
        )

        self.assertEqual(self.bridge.calls[0]["command"], "speedtest start --server-id 12345 --ip 198.51.100.10")
        self.assertNotIn("isError", response["result"])

    def test_tool_speedtest_rejects_host_argument(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "tool",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "speedtest {\"action\":\"start\",\"host\":\"example.test\"}",
                    },
                },
            }
        )

        self.assertEqual(response["error"]["code"], ERR_INVALID_PARAMS)
        self.assertEqual(response["error"]["message"], "host is not supported for speedtest; use server_id from `servers`")

    def test_tool_speedtest_rejects_interface_argument(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "tool",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "speedtest {\"action\":\"start\",\"interface\":\"wan1\"}",
                    },
                },
            }
        )

        self.assertEqual(response["error"]["code"], ERR_INVALID_PARAMS)
        self.assertEqual(response["error"]["message"], "interface is not supported for speedtest; use ip")

    def test_tool_speedtest_output_subcommand_uses_default_start_line(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "tool",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "speedtest {\"action\":\"output\"}",
                    },
                },
            }
        )

        self.assertEqual(self.bridge.calls[0]["command"], "speedtest output --start-line 0")
        self.assertNotIn("isError", response["result"])

    def test_tool_speedtest_rejects_hidden_format_argument(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "tool",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "speedtest {\"action\":\"start\",\"format\":\"json\"}",
                    },
                },
            }
        )

        self.assertEqual(response["error"]["code"], ERR_INVALID_PARAMS)
        self.assertEqual(response["error"]["message"], "Unknown argument: format")

    def test_tool_tcpdump_start_subcommand_executes_bridge(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "tool",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "tcpdump {\"action\":\"start\",\"capture_mode\":\"show\",\"capture_time\":60,\"local_iface\":[{\"interface\":\"vlan1\",\"expert_options\":\"\"}]}",
                    },
                },
            }
        )

        self.assertEqual(
            self.bridge.calls[0]["command"],
            "tool tcpdump {\"action\":\"start\",\"capture_mode\":\"show\",\"capture_time\":60,\"local_iface\":[{\"interface\":\"vlan1\",\"expert_options\":\"\"}]}",
        )
        self.assertNotIn("isError", response["result"])

    def test_tool_tcpdump_output_subcommand_accepts_start_line(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "tool",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "tcpdump {\"start_line\":0}",
                    },
                },
            }
        )

        self.assertEqual(self.bridge.calls[0]["command"], "tool tcpdump {\"start_line\":0}")
        self.assertNotIn("isError", response["result"])

    def test_tool_tcpdump_rejects_save_capture_mode(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "tool",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "tcpdump {\"action\":\"start\",\"capture_mode\":\"save\",\"capture_time\":60,\"local_iface\":[{\"interface\":\"vlan1\",\"expert_options\":\"\"}]}",
                    },
                },
            }
        )

        self.assertEqual(response["error"]["code"], ERR_INVALID_PARAMS)
        self.assertEqual(response["error"]["message"], "capture_mode must be one of: show")

    def test_tool_tcpdump_rejects_file_capture_mode(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "tool",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "tcpdump {\"action\":\"start\",\"capture_mode\":\"file\",\"capture_time\":60,\"local_iface\":[{\"interface\":\"vlan1\",\"expert_options\":\"\"}]}",
                    },
                },
            }
        )

        self.assertEqual(response["error"]["code"], ERR_INVALID_PARAMS)
        self.assertEqual(response["error"]["message"], "capture_mode must be one of: show")

    def test_tool_tcpdump_rejects_legacy_interface_field(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "tool",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "tcpdump {\"action\":\"start\",\"capture_mode\":\"show\",\"capture_time\":60,\"interface\":\"vlan1\"}",
                    },
                },
            }
        )

        self.assertEqual(response["error"]["code"], ERR_INVALID_PARAMS)
        self.assertEqual(response["error"]["message"], "interface is not supported for tcpdump; use local_iface")

    def test_tool_tcpdump_rejects_missing_expert_options(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "tool",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "tcpdump {\"action\":\"start\",\"capture_mode\":\"show\",\"capture_time\":60,\"local_iface\":[{\"interface\":\"vlan1\"}]}",
                    },
                },
            }
        )

        self.assertEqual(response["error"]["code"], ERR_INVALID_PARAMS)
        self.assertEqual(response["error"]["message"], "local_iface[0].expert_options must be a string")

    def test_tool_tcpdump_rejects_show_mode_with_multiple_interfaces(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "tool",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "tcpdump {\"action\":\"start\",\"capture_mode\":\"show\",\"capture_time\":60,\"local_iface\":[{\"interface\":\"vlan1\",\"expert_options\":\"\"},{\"interface\":\"wan1\",\"expert_options\":\"\"}]}",
                    },
                },
            }
        )

        self.assertEqual(response["error"]["code"], ERR_INVALID_PARAMS)
        self.assertEqual(response["error"]["message"], "show mode requires exactly one local_iface entry")

    def test_reboot_tool_rejects_subcommand(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "reboot",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "now",
                    },
                },
            }
        )

        self.assertEqual(response["error"]["code"], ERR_INVALID_PARAMS)

    def test_tool_call_rejects_unknown_tool(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "device.cli.run",
                    "arguments": {
                        "device_id": "device-a",
                        "command": "status basic",
                    },
                },
            }
        )

        self.assertEqual(response["error"]["code"], ERR_INVALID_PARAMS)

    def test_tool_call_rejects_unknown_device(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "status",
                    "arguments": {
                        "device_id": "missing-device",
                        "subcommand": "basic",
                    },
                },
            }
        )

        self.assertEqual(response["error"]["code"], ERR_INVALID_PARAMS)

    def test_tool_call_rejects_missing_device_id_when_multiple_devices_are_configured(self):
        self.bridge = FakeBridge(["device-a", "device-b"])
        self.server = ExternalCliMCPServer(self.bridge)
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "status",
                    "arguments": {
                        "subcommand": "basic",
                    },
                },
            }
        )

        self.assertEqual(response["error"]["code"], ERR_INVALID_PARAMS)
        self.assertEqual(
            response["error"]["message"],
            "device_id is required when multiple devices are configured",
        )
        self.assertEqual(
            response["error"]["data"]["configured_device_ids"],
            ["device-a", "device-b"],
        )

    def test_tools_list_marks_device_id_as_optional(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
            }
        )

        tools = {tool["name"]: tool for tool in response["result"]["tools"]}
        self.assertNotIn("device_id", tools["status"]["inputSchema"]["required"])
        self.assertNotIn("subcommand", tools["status"]["inputSchema"]["required"])
        self.assertIn("subcommand", tools["status"]["inputSchema"]["properties"])
        self.assertEqual(tools["reboot"]["inputSchema"]["required"], [])
        self.assertIn(
            "Optional when the server config contains exactly one device",
            tools["status"]["inputSchema"]["properties"]["device_id"]["description"],
        )

    def test_tools_list_includes_ping_subcommand_guidance(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
            }
        )

        tools = {tool["name"]: tool for tool in response["result"]["tools"]}
        self.assertIn("Ping subcommands:", tools["tool"]["description"])
        self.assertIn(
            "Use `list` to discover diagnostics. For ping, use `ping {\"action\":\"start\",\"host\":\"8.8.8.8\"}` to begin",
            tools["tool"]["inputSchema"]["properties"]["subcommand"]["description"],
        )
        self.assertIn(
            "`ping {\"start_line\":0}` to read output",
            tools["tool"]["inputSchema"]["properties"]["subcommand"]["description"],
        )

    def test_tool_list_includes_speedtest_wrapper(self):
        tool_list_response = {"status": 200, "result": {"tools": [{"name": "ping"}]}}

        def responder(call):
            if call["command"] == "tool list":
                return self.bridge.ok_result(call["device_id"], call["command"], tool_list_response)
            return None

        self.bridge = FakeBridge(responder=responder)
        self.server = ExternalCliMCPServer(self.bridge)
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "tool",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "list",
                    },
                },
            }
        )

        self.assertEqual(
            response["result"]["structuredContent"]["data"]["result"]["tools"],
            [{"name": "ping"}, {"name": "speedtest"}],
        )

    def test_cacheable_list_uses_cache_when_firmware_is_unchanged(self):
        firmware_versions = ["1.0.0", "1.0.0"]
        tool_list_response = {"status": 200, "result": {"tools": [{"name": "ping"}]}}

        def responder(call):
            if call["command"] == "status basic":
                return self.bridge.ok_result(
                    call["device_id"],
                    call["command"],
                    {"status": 200, "result": {"firmware": firmware_versions.pop(0)}},
                )
            if call["command"] == "tool list":
                return self.bridge.ok_result(call["device_id"], call["command"], tool_list_response)
            return None

        self.bridge = FakeBridge(responder=responder)
        self.server = ExternalCliMCPServer(self.bridge)
        self._initialize_server()

        first = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "tool",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "list",
                    },
                },
            }
        )
        second = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "tool",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "list",
                    },
                },
            }
        )

        self.assertEqual(
            [call["command"] for call in self.bridge.calls],
            ["status basic", "tool list", "status basic"],
        )
        self.assertEqual(
            first["result"]["structuredContent"]["data"]["result"]["tools"],
            second["result"]["structuredContent"]["data"]["result"]["tools"],
        )
        self.assertEqual(
            first["result"]["structuredContent"]["data"]["result"]["tools"],
            [{"name": "ping"}, {"name": "speedtest"}],
        )

    def test_cacheable_list_refreshes_when_firmware_changes(self):
        firmware_versions = ["1.0.0", "2.0.0"]
        tool_list_responses = [
            {"status": 200, "result": {"tools": [{"name": "ping"}]}},
            {"status": 200, "result": {"tools": [{"name": "tcpdump"}]}},
        ]

        def responder(call):
            if call["command"] == "status basic":
                return self.bridge.ok_result(
                    call["device_id"],
                    call["command"],
                    {"status": 200, "result": {"firmware": firmware_versions.pop(0)}},
                )
            if call["command"] == "tool list":
                return self.bridge.ok_result(call["device_id"], call["command"], tool_list_responses.pop(0))
            return None

        self.bridge = FakeBridge(responder=responder)
        self.server = ExternalCliMCPServer(self.bridge)
        self._initialize_server()

        self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "tool",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "list",
                    },
                },
            }
        )
        second = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "tool",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "list",
                    },
                },
            }
        )

        self.assertEqual(
            [call["command"] for call in self.bridge.calls],
            ["status basic", "tool list", "status basic", "tool list"],
        )
        self.assertEqual(
            second["result"]["structuredContent"]["data"]["result"]["tools"],
            [{"name": "tcpdump"}, {"name": "speedtest"}],
        )

    def test_cacheable_list_propagates_timeout(self):
        def responder(call):
            if call["command"] == "status basic":
                return self.bridge.ok_result(
                    call["device_id"],
                    call["command"],
                    {"status": 200, "result": {"firmware": "1.0.0"}},
                )
            if call["command"] == "tool list":
                return self.bridge.ok_result(
                    call["device_id"],
                    call["command"],
                    {"status": 200, "result": {"tools": [{"name": "ping"}]}},
                )
            return None

        self.bridge = FakeBridge(responder=responder)
        self.server = ExternalCliMCPServer(self.bridge)
        self._initialize_server()

        self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "tool",
                    "arguments": {
                        "device_id": "device-a",
                        "subcommand": "list",
                        "timeout_sec": 7,
                    },
                },
            }
        )

        self.assertEqual(
            [(call["command"], call["timeout_sec"]) for call in self.bridge.calls],
            [("status basic", 7), ("tool list", 7)],
        )

    def test_resources_list_returns_fixed_resources_for_each_device(self):
        self.bridge = FakeBridge(["device-b", "device-a"])
        self.server = ExternalCliMCPServer(self.bridge)
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "resources/list",
            }
        )

        resources = response["result"]["resources"]
        expected_paths = [
            "/status/basic",
            "/status/list",
            "/config/list",
            "/schema/list",
            "/log/list",
            "/tool/list",
        ]

        self.assertEqual(len(resources), 12)
        self.assertEqual(
            [resource["uri"] for resource in resources[:6]],
            ["device://device-a{0}".format(path) for path in expected_paths],
        )
        self.assertEqual(
            [resource["uri"] for resource in resources[6:]],
            ["device://device-b{0}".format(path) for path in expected_paths],
        )
        self.assertEqual(resources[0]["name"], "device-a: Basic Status")
        self.assertEqual(resources[0]["mimeType"], "application/json")

    def test_resources_read_returns_response_payload_as_text(self):
        def responder(call):
            if call["command"] == "status basic":
                return self.bridge.ok_result(
                    call["device_id"],
                    call["command"],
                    {"status": 200, "result": {"firmware": "1.0.0"}},
                )
            return None

        self.bridge = FakeBridge(responder=responder)
        self.server = ExternalCliMCPServer(self.bridge)
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "resources/read",
                "params": {
                    "uri": "device://device-a/status/basic",
                },
            }
        )

        self.assertEqual(self.bridge.calls[0]["command"], "status basic")
        self.assertEqual(
            response["result"]["contents"],
            [
                {
                    "uri": "device://device-a/status/basic",
                    "mimeType": "application/json",
                    "text": json.dumps(
                        {"result": {"firmware": "1.0.0"}},
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                }
            ],
        )

    def test_resources_read_returns_schema_list_payload(self):
        def responder(call):
            if call["command"] == "schema list":
                return self.bridge.ok_result(
                    call["device_id"],
                    call["command"],
                    {
                        "status": 200,
                        "result": {
                            "schemas": [
                                {"key": "cellular", "description": "Cellular interface status"},
                                {"key": "signal_history_info", "description": "Signal history information"},
                            ]
                        },
                    },
                )
            return None

        self.bridge = FakeBridge(responder=responder)
        self.server = ExternalCliMCPServer(self.bridge)
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "resources/read",
                "params": {
                    "uri": "device://device-a/schema/list",
                },
            }
        )

        self.assertEqual(
            [call["command"] for call in self.bridge.calls[:2]],
            ["status basic", "schema list"],
        )
        self.assertEqual(
            response["result"]["contents"][0]["uri"],
            "device://device-a/schema/list",
        )
        payload = json.loads(response["result"]["contents"][0]["text"])
        self.assertEqual(payload["result"]["schemas"][0]["key"], "cellular")

    def test_resources_read_rejects_missing_uri(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "resources/read",
                "params": {},
            }
        )

        self.assertEqual(response["error"]["code"], ERR_INVALID_PARAMS)
        self.assertEqual(response["error"]["message"], "uri must be a non-empty string")

    def test_resources_read_rejects_invalid_uri(self):
        self._initialize_server()

        for uri in [
            "http://device-a/status/basic",
            "device://device-a/status/basic?cursor=1",
            "device://device-a/not/a/resource",
        ]:
            response = self.server.process_message(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "resources/read",
                    "params": {
                        "uri": uri,
                    },
                }
            )

            self.assertEqual(response["error"]["code"], ERR_INVALID_PARAMS)

    def test_resources_read_rejects_unknown_device(self):
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "resources/read",
                "params": {
                    "uri": "device://missing-device/status/basic",
                },
            }
        )

        self.assertEqual(response["error"]["code"], ERR_INVALID_PARAMS)
        self.assertEqual(response["error"]["message"], "Unknown device_id")

    def test_resources_read_reports_execution_failure(self):
        def responder(call):
            if call["command"] == "status basic":
                return {
                    "device_id": call["device_id"],
                    "command": call["command"],
                    "ok": False,
                    "ssh_exit_code": 1,
                    "response": {"status": 500},
                    "stderr": "command failed",
                    "error": {
                        "kind": "remote_error",
                        "message": "command failed",
                    },
                }
            return None

        self.bridge = FakeBridge(responder=responder)
        self.server = ExternalCliMCPServer(self.bridge)
        self._initialize_server()

        response = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "resources/read",
                "params": {
                    "uri": "device://device-a/status/basic",
                },
            }
        )

        self.assertEqual(response["error"]["code"], ERR_INTERNAL)
        self.assertEqual(response["error"]["message"], "Resource read failed")
        self.assertEqual(response["error"]["data"]["command"], "status basic")

    def test_cacheable_resource_uses_cache_when_firmware_is_unchanged(self):
        firmware_versions = ["1.0.0", "1.0.0"]
        tool_list_response = {"status": 200, "result": {"tools": [{"name": "ping"}]}}

        def responder(call):
            if call["command"] == "status basic":
                return self.bridge.ok_result(
                    call["device_id"],
                    call["command"],
                    {"status": 200, "result": {"firmware": firmware_versions.pop(0)}},
                )
            if call["command"] == "tool list":
                return self.bridge.ok_result(call["device_id"], call["command"], tool_list_response)
            return None

        self.bridge = FakeBridge(responder=responder)
        self.server = ExternalCliMCPServer(self.bridge)
        self._initialize_server()

        first = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "resources/read",
                "params": {
                    "uri": "device://device-a/tool/list",
                },
            }
        )
        second = self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "resources/read",
                "params": {
                    "uri": "device://device-a/tool/list",
                },
            }
        )

        self.assertEqual(
            [call["command"] for call in self.bridge.calls],
            ["status basic", "tool list", "status basic"],
        )
        self.assertEqual(first["result"]["contents"], second["result"]["contents"])
        self.assertIn("{\"name\":\"speedtest\"}", first["result"]["contents"][0]["text"])

    def test_non_cacheable_resource_executes_directly_each_time(self):
        self._initialize_server()

        self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "resources/read",
                "params": {
                    "uri": "device://device-a/status/basic",
                },
            }
        )
        self.server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "resources/read",
                "params": {
                    "uri": "device://device-a/status/basic",
                },
            }
        )

        self.assertEqual(
            [call["command"] for call in self.bridge.calls],
            ["status basic", "status basic"],
        )


class ServerCliEntryPointTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mcp-server-main-")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_parse_args_defaults_to_project_config_path(self):
        options = parse_args([])

        self.assertEqual(options.config, DEFAULT_PROJECT_CONFIG_PATH)
        self.assertFalse(options.config_explicit)
        self.assertEqual(options.device, [])
        self.assertIsNone(options.runtime_dir)
        self.assertFalse(options.takeover)

    def test_parse_args_collects_inline_devices(self):
        options = parse_args(
            [
                "--device",
                "name=device-a,host=192.0.2.10,pass=secret",
                "--device",
                "name=device-b,host=192.0.2.11,pass=secret-b,port=2222",
            ]
        )

        self.assertEqual(
            options.device,
            [
                "name=device-a,host=192.0.2.10,pass=secret",
                "name=device-b,host=192.0.2.11,pass=secret-b,port=2222",
            ],
        )

    def test_parse_device_spec_accepts_short_fields(self):
        device = _parse_device_spec("name=lab-a,host=192.0.2.10,pass=secret,buser=ops,user=agent2,port=2222")

        self.assertEqual(
            device,
            {
                "name": "lab-a",
                "host": "192.0.2.10",
                "user": "agent2",
                "bootstrap_user": "ops",
                "bootstrap_password": "secret",
                "port": 2222,
            },
        )

    def test_parse_device_spec_requires_name_host_and_pass(self):
        with self.assertRaisesRegex(ConfigError, "missing required field"):
            _parse_device_spec("name=lab-a,host=192.0.2.10")

    def test_parse_device_spec_rejects_invalid_port(self):
        with self.assertRaisesRegex(ConfigError, "port"):
            _parse_device_spec("name=lab-a,host=192.0.2.10,pass=secret,port=abc")

    def test_build_inline_config_uses_runtime_dir_defaults(self):
        runtime_dir = os.path.join(self.temp_dir, "runtime")

        config = _build_inline_config(
            [
                "name=lab-a,host=192.0.2.10,pass=secret",
                "name=lab-b,host=192.0.2.11,pass=secret-b,buser=ops,port=2222",
            ],
            runtime_dir,
        )

        self.assertEqual(
            config["ssh_defaults"]["keys_base_dir"],
            os.path.join(runtime_dir, DEFAULT_RUNTIME_KEYS_DIR_NAME),
        )
        self.assertEqual(
            config["ssh_defaults"]["control_path_dir"],
            os.path.join(runtime_dir, DEFAULT_RUNTIME_CONTROL_PATH_DIR_NAME),
        )
        self.assertEqual(config["devices"]["lab-a"]["bootstrap_password"], "secret")
        self.assertEqual(config["devices"]["lab-b"]["bootstrap_user"], "ops")
        self.assertEqual(config["devices"]["lab-b"]["port"], 2222)

    def test_main_reports_missing_default_config_with_minimal_example(self):
        missing_config_path = os.path.join(self.temp_dir, "config", "config.json")

        with mock.patch("external_mcp_server.server.DEFAULT_PROJECT_CONFIG_PATH", missing_config_path):
            stderr_buffer = io.StringIO()
            with mock.patch("sys.stderr", stderr_buffer):
                with mock.patch("external_mcp_server.server.SSHBridge") as bridge_class:
                    result = main([])

        self.assertEqual(result, EXIT_NOTFOUND)
        self.assertIn(missing_config_path, stderr_buffer.getvalue())
        self.assertIn('"devices"', stderr_buffer.getvalue())
        self.assertIn("--device", stderr_buffer.getvalue())
        self.assertIn("--config /path/to/devices.json", stderr_buffer.getvalue())
        bridge_class.assert_not_called()

    def test_main_rejects_runtime_dir_without_device(self):
        stderr_buffer = io.StringIO()

        with mock.patch("sys.stderr", stderr_buffer):
            result = main(["--runtime-dir", os.path.join(self.temp_dir, "runtime")])

        self.assertEqual(result, EXIT_BADARGS)
        self.assertIn("--runtime-dir requires at least one --device", stderr_buffer.getvalue())

    def test_main_rejects_config_and_device_together(self):
        stderr_buffer = io.StringIO()

        with mock.patch("sys.stderr", stderr_buffer):
            result = main(
                [
                    "--config",
                    "/tmp/devices.json",
                    "--device",
                    "name=lab-a,host=192.0.2.10,pass=secret",
                ]
            )

        self.assertEqual(result, EXIT_BADARGS)
        self.assertIn("--config cannot be used together with --device", stderr_buffer.getvalue())

    def test_main_uses_inline_device_config_without_config_file(self):
        bridge = mock.Mock()
        stderr_buffer = io.StringIO()

        with mock.patch("external_mcp_server.server.SSHBridge.from_config_data", return_value=bridge) as bridge_factory:
            with mock.patch("external_mcp_server.server.serve") as serve_mock:
                with mock.patch("external_mcp_server.server._build_stream", side_effect=lambda handle, mode: handle):
                    with mock.patch("sys.stderr", stderr_buffer):
                        result = main(["--device", "name=lab-a,host=192.0.2.10,pass=secret"])

        self.assertEqual(result, 0)
        self.assertEqual(bridge_factory.call_count, 1)
        inline_config = bridge_factory.call_args[0][0]
        self.assertIn("lab-a", inline_config["devices"])
        self.assertTrue(
            bridge_factory.call_args.kwargs["base_dir"].endswith(".agent-cli-mcp")
        )
        serve_mock.assert_called_once()
        bridge.close.assert_called_once()
