# ODU12 — Problem Diagnosis Entry

> Applicable: When the ODU12 5G outdoor unit encounters functional anomalies, use logs/symptoms to locate the corresponding module's diagnostic document.

## Model Identification

- Compile-time macro: `INHAND_ODU12`

## Diagnostic Document Index

Each document covers one service/module, organized in the structure of "Log Pattern → Diagnosis → Solution".

### System Core

| Module | Document | Typical Symptoms |
|--------|----------|------------------|
| syswatcher | [syswatcher.md](syswatcher.md) | Service heartbeat timeout/abnormal exit/startup failure, mass interface DOWN triggering reboot, critically low memory auto-reboot, startup config load failure, filesystem read-only recovery failure, cloud system config JSON error |
| api_gateway | [api_gateway.md](api_gateway.md) | Web UI access anomaly, REST API returning errors, firmware upgrade failure, config import/export anomaly, packet capture/speed test tool anomaly |
| agent | [agent.md](agent.md) | dnsmasq DNS/DHCP anomaly, DDNS update failure, httpd memory overrun, ODHCPD/NDPPD startup failure, Web Nginx anomaly, cloud JSON config parse error, agent self signal/status anomaly |
| systools | [systools.md](systools.md) | Firmware upgrade failure (image verification/Flash write/fork), password init/decrypt failure causing auto-reboot, Python SDK/App install verification failure, conntrack restore failure, DNS resolution failure, unknown sub-command |

### Network

| Module | Document | Typical Symptoms |
|--------|----------|------------------|
| firewall | [firewall.md](firewall.md) | iptables rules not effective, NAT/ACL/port mapping anomaly, remote access unreachable |
| interface | [interface.md](interface.md) | Interface/VLAN nonexistent, VLAN switch chip operation failure, IP Passthrough anomaly, DHCP/ODHCP6C/PPPoE client exit, Ethernet anomaly triggering reboot, port speed/duplex error, MAC/FDB operation failure, IP conflict, cloud interface JSON config error |
| routed | [routed.md](routed.md) | Routing protocol subprocess startup/exit anomaly, static route config failure, zebra netlink communication anomaly, RIP/OSPF/BGP config error, prefix-list/access-list/key-chain full, cloud routing JSON config error |
| NetworkManager | [NetworkManager.md](NetworkManager.md) | AWS IoT MQTT connection failure, Shadow config out of sync, firmware OTA failure, remote diagnostic tool anomaly |
| dot11d | [dot11d.md](dot11d.md) | Wi-Fi 2.4G/5G not working, AP/STA/Multi-SSID config failure, Wi-Fi E2P/calibration/test mode anomaly causing auto-reboot, MAC address invalid, UCI config write failure, IPC broadcast failure, sysrepo sync anomaly, cloud JSON config error |
| xdsl | (TBD) | DSL connection anomaly |

### WAN / Connection

| Module | Document | Typical Symptoms |
|--------|----------|------------------|
| redial2 | (TBD) | Modem dial failure, no redial on disconnect |
| ih_qmi | [ih_qmi.md](ih_qmi.md) | Modem QMI communication anomaly, QMAP config invalid, PDP dial/IP acquisition failure, network registration anomaly, DHCP subprocess anomaly, modem unresponsive timeout, proxy message send/receive failure |
| mipc_wwan | [mipc_wwan.md](mipc_wwan.md) | WWAN data channel anomaly, modem crash/not ready, APN/PDP activation failure, 464-XLAT/NAT46 operation failure, IPv6 RS/RA socket error, Redial IPC communication failure, memory allocation failure |
| sdwan | [sdwan.md](sdwan.md) | Multi-WAN link switch failure, AutoVPN config error, Cloud Connect VPN anomaly, IPC message send failure, uplink outage triggering reboot |
| vpnd | [vpnd.md](vpnd.md) | L2TP server/client connection failure, config file create/write failure, OpenVPN client/server anomaly, Cloud Connect OpenVPN anomaly, tunnel IP conflict, broadcast/IPC communication failure, signal/reboot anomaly, cloud JSON config error |
| ipsecwatcher3 | [ipsecwatcher3.md](ipsecwatcher3.md) | IPsec tunnel unreachable/cannot connect, strongswan subprocess exit, consecutive tunnel failure auto-reboot device, signal/reboot anomaly, runtime state persistence failure, IPC/SNMP communication failure, cloud JSON config error |
| tunnel | [tunnel.md](tunnel.md) | GRE/VXLAN tunnel unreachable, tunnel create/delete failure, AutoVPN VXLAN anomaly, signal/reboot anomaly, runtime state persistence failure, cloud JSON config error |
| ip_passthrough | [ip_passthrough.md](ip_passthrough.md) | IP Passthrough execution failure, signal/reboot anomaly, runtime state persistence failure, interface info fetch failure, invalid subnet mask, socket/ioctl error, cloud JSON config error |

### Monitoring & Alerts

| Module | Document | Typical Symptoms |
|--------|----------|------------------|
| emaild | [emaild.md](emaild.md) | SMTP connection/auth failure, SSL/TLS handshake anomaly, email send failure, transmit queue full, cloud JSON config error |
| events | [events.md](events.md) | SQLite database anomaly, event record/trigger failure, client event node anomaly, cloud alert rule JSON error |
| lqm | [lqm.md](lqm.md) | Link detection thread anomaly, ICMP/ICMPv6 detection failure, DNS detection config/resolution failure, detection target unreachable, socket creation failure |

### Cloud / IoT

| Module | Document | Typical Symptoms |
|--------|----------|------------------|
| captive_portal | [captive_portal.md](captive_portal.md) | Portal auth server startup failure, RADIUS authentication/accounting failure, user login/logout anomaly, portal page download failure, Wifidog proxy anomaly, cloud config JSON error |

### Basic Services

| Module | Document | Typical Symptoms |
|--------|----------|------------------|
| sntpc | [sntpc.md](sntpc.md) | NTP time sync failure, DNS resolution of NTP domain failure, evDNS init failure, signal/persistence anomaly, cloud/Web UI JSON config error |
| record | [record.md](record.md) | Traffic record/report failure, SQLite database anomaly, JSON data packaging failure, client data collection anomaly |

---

## Common Reference

| Document | Description |
|----------|-------------|
| [../common/architecture.md](../common/architecture.md) | Overall system architecture (IPC model, build system, shared library hierarchy) — helps understand inter-module relationships in logs |

## How to Use

1. Confirm the model is ODU12 or a compatible variant via `status basic`.
2. Extract service name/process name prefixes from collected logs, e.g., `NetworkManager`, `lqm`, `syswatcher`, `ih_qmi`.
3. When the service name is clear, open only the corresponding document; when unclear, first use the typical symptoms table above to locate the most likely document.
4. In the corresponding diagnostic document, search for `## Problem` sections by error prefix, function name, errno, or key phrases from the original log.
5. Only open a second module document when the current one clearly does not match, or when the solution requires checking another service.
6. Execute the solution based on the diagnostic conclusion and verify recovery; when involving config writes, reboot, or upgrade, hand off via the cross-skill handoff mechanism in `agent-cli-shared`.
