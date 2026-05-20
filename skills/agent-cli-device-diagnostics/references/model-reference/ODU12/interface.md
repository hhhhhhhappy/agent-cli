# interface — Problem Diagnosis

> Applicable: interface service self-anomaly (signal handling failure, runtime state persistence failure), interface/L3/VLAN config not effective or reporting errors, DHCP/ODHCP6C/PPPoE client abnormal exit, VLAN switch chip operation failure, IP Passthrough config anomaly, Ethernet anomaly detection triggering reboot (ODU12), cloud interface JSON config parse error.

## Log Format Reference

| Level | Meaning | Requires Attention |
|-------|---------|-------------------|
| [ER] | ERROR | Yes |
| [WA] | WARNING | Yes |
| [IN] | INFO | For reference only |

> Note: interface service log prefix is `ih_if` (`#define IDENT "ih_if"` in code).

---

## Problem 1: Interface service signal handler registration failure

### Matching Logs

```
ih_if [ER] cannot add handle for SIGHUP
ih_if [ER] cannot add handle for SIGUSR1
ih_if [ER] cannot add handle for SIGCHLD
ih_if [ER] cannot add handle for SIGTERM
ih_if [ER] cannot add handle for SIGINT
```

### Diagnosis

interface service failed to register handler functions for critical signals at startup.

### Cause

1. Insufficient system resources (file descriptor exhaustion, low memory)
2. libevent event library initialization anomaly

### Solution

1. Perform device restart via Web UI
2. If persistent, contact after-sales

---

## Problem 2: Interface service received abnormal signal and exited

### Matching Logs

```
ih_if [ER] Received <signal name>; quitting...
```

### Diagnosis

interface service received termination signal and is exiting. When interface exits, all interface management functions stop; network may be disrupted.

### Cause

1. System shutdown or restart triggered SIGTERM
2. syswatcher or other management process actively terminated interface
3. interface service internally triggered anomaly causing self-exit

### Solution

1. If accompanied by system restart, normal behavior
2. If unexpected exit, perform device restart via Web UI
3. If frequent, contact after-sales

---

## Problem 3: Interface service runtime state persistence failure

### Matching Logs

```
ih_if [ER] cannot dump running state to <file path>, we will not be able to recover in case of a fatal error!
ih_if [WA] failed to save global data
ih_if [WA] failed to save if_info data / port_info data / vlan_info data / SVI / L3 / switchport / loopback / storm data
ih_if [WA] failed to load global data / if_info data / (port_info / vlan_info / SVI / L3 / switchport / loopback / storm)
```

### Diagnosis

interface service cannot persist or recover runtime state.

### Solution

1. Perform device restart via Web UI
2. Re-save interface/VLAN related config via Web UI
3. If frequent with other anomalies, contact after-sales

---

## Problem 4: Interface/VLAN/sub-interface does not exist

### Matching Logs

```
ih_if [ER] Interface <type> <slot>/<port> does not exist
ih_if [ER] SVI (VLAN <VLAN ID>) does not exist
ih_if [ER] <interface type> <type>/<slot>.<sub_iface> does not exist
ih_if [ER] the interface <interface name> don't exist
ih_if [ER] Interface <interface ID> does not exist
```

### Diagnosis

interface service found that the specified interface, SVI, sub-interface, or VLAN does not exist during config or query operations.

### Solution

1. Check via Web UI that port/VLAN numbers in interface config are correct
2. Delete invalid interface configs via Web UI
3. Re-create needed interfaces via Web UI
4. If interface exists but error persists, re-save config via Web UI

---

## Problem 5: VLAN switch chip port operation failure

### Matching Logs

```
ih_if [ER] ### vlan <VLAN ID> del port <port bitmap> errno: <error code>
ih_if [ER] ### vlan <VLAN ID> add port <port bitmap> type <type> errno: <error code>
ih_if [ER] ### sw vlan <VLAN ID> del port <port bitmap> errno: <error code>
ih_if [ER] cannot destroy vlan <VLAN ID>
```

### Diagnosis

interface service failed when operating VLAN member ports on the switch chip (gsw).

### Solution

1. Check via Web UI that VLAN config is valid (VLAN ID range, port validity)
2. Delete invalid VLAN configs
3. Re-save VLAN config via Web UI
4. Perform device restart via Web UI
5. If persistent, contact after-sales to check switch chip hardware

---

## Problem 6: IP Passthrough (ippt) config anomaly

### Matching Logs

```
ih_if [ER] ippt lport <port> is wan
ih_if [ER] ippt init error[<interface name>] l3_iface is NULL
ih_if [ER] found vlan4031 failed
ih_if [ER] ippt set access lan failed / ippt add l3 iface failed / ippt init failed
ih_if [ER] ippt shutdown/enable lport is error / ippt lport is error
ih_if [ER] default vlan not find / ippt init default vlan ip is 0 or mask is 32
ih_if [ER] ippt recover, get if info failed / ippt set lport mode failed
ih_if [ER] ippt set_access_vlan failed / ippt set_native_vlan failed
```

### Diagnosis

IP Passthrough feature encountered errors during config process.

### Solution

1. Check IP Passthrough config LAN port selection via Web UI
2. Ensure the specified LAN port is correctly configured and in access mode
3. Disable and re-enable IP Passthrough via Web UI
4. Perform device restart via Web UI

---

## Problem 7: DHCP client abnormal exit

### Matching Logs

```
ih_if [ER] DHCP Client for fastethernet 0/<port> exit
ih_if [ER] DHCP Client for vlan<VLAN ID> exit
```

### Diagnosis

interface-managed DHCP client process exited abnormally.

### Solution

1. Check interface physical link
2. Check DHCP server reachability
3. Check interface DHCP config via Web UI
4. If frequent exits, switch to static IP
5. Perform device restart via Web UI

---

## Problem 8: ODHCP6C client abnormal exit

### Matching Logs

```
ih_if [ER] ODHCP6C Client for fastethernet 0/<port> exit
ih_if [ER] ODHCP6C Client for vlan<VLAN ID> exit
```

### Solution

1. Check upstream IPv6 router/server
2. Check interface physical link
3. Check interface IPv6 config via Web UI
4. Perform device restart via Web UI

---

## Problem 9: PPPoE client abnormal exit / startup failure

### Matching Logs

```
ih_if [ER] PPPD for <interface name> exit
ih_if [ER] PPPD for vlan<VLAN ID> exit
ih_if [ERR] failed to start pppoe<N>, cannot write to <file>!
ih_if [ERR] failed to start pppoe<N>, cannot write to chap/pap secrets file!
```

### Solution

1. Check PPPoE account/password config via Web UI
2. Check ISP line status
3. Re-save PPPoE config via Web UI
4. Perform device restart via Web UI

---

## Problem 10: Switch chip initialization failure

### Matching Logs

```
ih_if [ER] ### start switch failed!
ih_if [ER] ### port <port> set stp state to forwarding errno: <error code>
ih_if [ER] ### port <port> get stp state errno: <error code>
ih_if [ER] ### interface init errno: <error code>
```

### Solution

1. Perform device restart via Web UI
2. If persistent, contact after-sales to check hardware

---

## Problem 11: Port speed/duplex setting failure

### Matching Logs

```
ih_if [ER] ### PORT <port> set speed <speed value> failed(<error code>)
ih_if [ER] ### PORT <port> set duplex <duplex mode> failed(<error code>)
ih_if [ER] ### get port <port> link status/speed/duplex errno: <error code>
ih_if [ER] set speed/duplex failed
```

### Solution

1. Restore port speed/duplex to auto via Web UI
2. Check port physical connection
3. Perform device restart via Web UI
4. If persistent, contact after-sales

---

## Problem 12: MAC/FDB table operation failure

### Matching Logs

```
ih_if [ER] ### append [<MAC address>, <VLAN ID>], priority <priority> errno: <error code>
ih_if [ER] ### destroy [<MAC address>, <VLAN ID>] due to sw problem errno: <error code>
ih_if [ER] ### error: delete secure MAC <MAC> on VLAN <VLAN ID>, entry not found!
```

### Solution

1. Delete unnecessary static MAC binding entries via Web UI
2. Check that VLAN ID and port in static MAC config are correct
3. Perform device restart via Web UI

---

## Problem 13: Ethernet anomaly detection triggering reboot (ODU12 specific)

### Matching Logs

```
ih_if [WA] eth anomaly[<interface name>]: tx+<tx count> rx=0 err+<error count>(total=<total>) count=<anomaly count>/<threshold>
```

After 30 minutes:
```
ih_if [ALERT] eth anomaly[<interface name>]: sustained 30min, rebooting
```

### Diagnosis

Interface service detected Ethernet interface functional-level fault: continuous sending but no receiving, with accumulated CRC/Length errors. Device will auto-restart after 30 minutes of sustained anomaly.

### Solution

1. Check/replace Ethernet cable
2. Check peer device port
3. Replace peer device port
4. If persistent after cable and port swap, contact after-sales

---

## Problem 14: Netlink communication anomaly

### Matching Logs

```
ih_if [ER] create gsw port netlink socket failed(<errno>:<error description>)
ih_if [ER] bind gsw port netlink socket failed(<errno>:<error description>)
ih_if [ER] gsw recvfrom port netlink msg err.(<errno>:<error description>)
```

### Solution

1. Perform device restart via Web UI
2. If persistent, contact after-sales to check kernel modules

---

## Problem 15: IP address conflict

### Matching Logs

```
ih_if [ER] interface ip conflict
```

### Solution

1. Check via Web UI for duplicate or conflicting IP configs across interfaces
2. Change conflicting IP addresses
3. If DHCP-acquired address conflicts, check DHCP server address pool config

---

## Problem 16: Insufficient memory

### Matching Logs

```
ih_if [ER] No enough memory
ih_if [WA] failed to malloc in <function name>
```

### Solution

1. Perform device restart via Web UI
2. Delete unnecessary interface/VLAN configs
3. If persistent, contact after-sales

---

## Problem 17: IPv6 address generation failure

### Matching Logs

```
ih_if [WA] failed to generate ipv6 address from <IPv6 prefix> and interface-id: <interface ID>
```

### Solution

1. Check interface IPv6 config via Web UI
2. Switch IPv6 config to auto-acquire (SLAAC/DHCPv6)
3. Re-save IPv6 config via Web UI

---

## Problem 18: VLAN operation permission error

### Matching Logs

```
ih_if [ER] ### NULL create/destroy VLAN request from service <service ID>
ih_if [ER] the owner of vlan <VLAN ID> is <owner service ID>, so service <service ID> can not use it.
ih_if [ER] vlan <VLAN ID> does not exist, so service <service ID> can not destroy it.
```

### Solution

1. If sporadic and functionality normal, can be ignored (usually concurrent request issue)
2. Perform device restart via Web UI
3. If a specific service repeatedly fails, contact after-sales

---

## Problem 19: JSON cloud config parse errors

### Matching Logs

```
ih_if [ER] request json is NULL
ih_if [ER] switch port loads json error,<line>:<error description>
ih_if [ER] interface loads json error,<line>:<error description>
ih_if [ER] interface config interface <interface name> is invalid!
ih_if [ER] get iface info error, iface_name:<interface name>
ih_if [ER] interface ip conflict / ip or netmask invalid / primary ip config error / mtu config error
ih_if [ER] can't delete default vlan 1
ih_if [ER] LAN1 port <port> is not valid when deleting WAN1
ih_if [ER] Cannot get IF_INFO of lan1
ih_if [ER] get iface panel_name error by if:<interface name>
ih_if [ER] build sub_obj of interface_ip failed.
ih_if [ER] failed to pack json payload for <wan_traffic/switch_port/interface_ip>
ih_if [ER] failed to dump json to string
```

### Solution

1. Check via cloud platform that delivered JSON config format and parameters are valid
2. Ensure interface names match actual device interface names
3. Check IP address/mask/MTU parameter validity
4. Do not attempt to delete VLAN 1
5. Re-deliver rules one by one via cloud platform

---

## Problem 20: PPPoE config file write failure

```
ih_if [ERR] failed to start pppoe<N>, cannot write to <file>!
ih_if [ERR] failed to start pppoe<N>, cannot write to chap/pap secrets file!
```

### Solution

1. Re-save PPPoE config via Web UI
2. Perform device restart via Web UI

---

## Problem 21-24: Sub-interface / L2 Bridge / Monitor Session / Switch Config File issues

(Refer to original full documentation for detailed matching logs and solutions)

---

## ODU12 Model Differences

| Behavior | Description |
|----------|-------------|
| Ethernet anomaly detection and auto-restart | When interface has sustained TX but no RX + CRC error accumulation, auto-restart after 30 minutes |
| Interface traffic statistics | Read rx_crc_errors / rx_length_errors from `/sys/class/net/<iface>/statistics/` |

---

## Normal INFO Logs (No Action Needed)

```
ih_if [IN] MSG: 0x<message type> from service <service ID>
ih_if [IN] port <port> LINK changed, restart dhcp client / pppoe / odhcp6c.
ih_if [IN] gsw port<port> status change [<old status> -> <new status>]
ih_if [IN] Interface <name> <type>/<port>, changed state to <status>
ih_if [IN] set <interface> <IP>/<mask>
ih_if [IN] start dhcp6c/pppoe interface <name>
ih_if [IN] VLAN <VLAN ID> set name: <name>
ih_if [IN] set FDB aging time to <seconds> second(s)
ih_if [IN] port <port> set storm control / flow control / pvid / rate limit / protected / learn limit / shutdown
ih_if [IN] port <port> join/leave channel-group <number>
ih_if [IN] iface <name> ifconfig <up/down> / down interface <name>
ih_if [IN] <add/del> wan interface [<name>] / <add/del> interface (<name>) . l3_iface port[<port>]
ih_if [IN] ippt lport <port> is wan
ih_if [IN] config bridge [br-lan] mac address <MAC>
```

---

## General Troubleshooting Information Collection

1. All `ih_if [ER]` and `ih_if [WA]` lines in device logs
2. Complete logs for 2 minutes before and after the fault
3. Current interface config summary (IP/mask/VLAN/binding status for each interface)
4. Physical port link status
5. Whether there were config changes, interface plug/unplug events at or before the fault time
6. Impact scope description (which interfaces are unavailable)
