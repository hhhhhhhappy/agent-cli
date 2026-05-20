# Overall Architecture

> Applicable: Understand the overall architecture of InHand firmware, IPC communication model, build system, and shared library hierarchy.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Web UI (www)                            │
│              Static Pages + JavaScript                      │
├─────────────────────────────────────────────────────────────┤
│              API Gateway (api_gateway)                       │
│             REST API / Session Management / JSON             │
├─────────────────────────────────────────────────────────────┤
│       CLI (cli)              │  Agent CLI (agent_cli)        │
├──────────────────────────────┴──────────────────────────────┤
│                      IPC Bus (libipc)                        │
│          Shared memory + message queues, backbone of         │
│          inter-service communication                         │
│                                                             │
│    ┌────────┬────────┬────────┬────────┬────────┐           │
│    │agent   │firewall│sys-    │sdwan   │interface│  ...     │
│    │(sub-   │        │watcher │        │         │          │
│    │service │        │        │        │         │          │
│    │manager)│        │        │        │         │          │
│    └────────┴────────┴────────┴────────┴────────┘           │
│                                                             │
│    ┌───────┬────────┬────────┬────────┬─────────┐           │
│    │httpd  │sshd    │telnetd │nginx   │dhcpd    │  ...     │
│    │(by    │(by     │(by     │(by     │(by      │          │
│    │agent  │agent   │agent   │agent   │agent    │          │
│    │mgr)   │mgr)    │mgr)    │mgr)    │mgr)     │          │
│    └───────┴────────┴────────┴────────┴─────────┘           │
├─────────────────────────────────────────────────────────────┤
│              Shared Library Layer                            │
│   libshared | libipc | libcli | libcmd | libsql_db | ...    │
│   libmosq (MQTT) | libosmofsm (state machine) |             │
│   libqmi_tiny (QMI)                                         │
├─────────────────────────────────────────────────────────────┤
│              Linux Kernel + OpenWRT                         │
└─────────────────────────────────────────────────────────────┘
```

## VIF (Virtual Interface) Model

- Each physical/logical interface corresponds to a `VIF_INFO` structure
- Contains interface name, IP, status, MTU, type (IF_TYPE_CELLULAR / IF_TYPE_FE / ...), etc.
- Services obtain all current interfaces via `ih_vif_init()`, and register change callbacks via `vif_link_change_register()`
- `IF_INFO` hierarchy: `type.slot.port.sid`

## Agent Mode

`agent` is a special daemon that manages all "non-IPC services" (NON_IPC_SVCS) that do not use ih_ipc, including:

- httpd, nginx (web servers)
- sshd, telnetd (remote login)
- dhcpc (DHCP client)
- vsftpd (FTP)
- snmpd (SNMP)
- dnsmasq (DNS/DHCP server)
- etc.

agent is responsible for starting, stopping, configuration distribution, and status monitoring of these services. Each sub-service corresponds to a `*_agent.c` file.
