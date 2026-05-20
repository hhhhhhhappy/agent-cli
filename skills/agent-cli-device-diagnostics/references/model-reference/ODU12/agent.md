# agent — Problem Diagnosis

> Applicable: Agent daemon self-anomaly (signal handling failure, state persistence failure), agent-managed sub-services (dnsmasq, ddns, httpd, odhcpd, ndppd, web nginx, api_gateway, telnetd, sshd, dhcprelay, ntpd, mipc_wwan) startup failure or runtime anomaly, cloud JSON config parse error.

## Log Format Reference

| Level | Meaning | Requires Attention |
|-------|---------|-------------------|
| [ER] | ERROR | Yes |
| [WA] | WARNING | Yes |
| [IN] | INFO | For reference only |

---

## Problem 1: Agent process received abnormal signal and exited

### Matching Logs

```
agent [ER] Received an unknown signal; quitting...
agent [ER] Received SIGTERM; quitting...
agent [ER] Received SIGINT; quitting...
```

### Diagnosis

The agent process received a termination signal (SIGTERM, SIGINT, or unknown signal) and is exiting. After agent exits, all its managed sub-services (dnsmasq, httpd, sshd, telnetd, etc.) lose their guardian, potentially causing partial service disruption.

### Cause

1. System shutdown or restart triggered SIGTERM
2. syswatcher or another management process actively terminated agent
3. User sent kill signal via serial/SSH
4. System memory exhaustion caused OOM killer to send SIGKILL (in this case this log won't appear, as the process is killed directly)

### Solution

1. If accompanied by system restart, this is normal behavior, no action needed
2. If unexpected exit, perform device restart via Web UI
3. If it occurs frequently, contact after-sales to investigate memory shortage or bugs

---

## Problem 2: Agent signal handler registration failed (at startup)

### Matching Logs

```
agent [ER] cannot add handle for SIGHUP
agent [ER] cannot add handle for SIGUSR1
agent [ER] cannot add handle for SIGCHLD
agent [ER] cannot add handle for SIGTERM
agent [ER] cannot add handle for SIGINT
```

### Diagnosis

Agent failed to register handler functions for critical signals at startup. This causes agent to be unable to respond to config reload signals (SIGHUP), capture child process exit events (SIGCHLD), or properly handle termination signals.

### Cause

1. Insufficient system resources (file descriptor exhaustion, low memory)
2. libevent event library initialization anomaly
3. System signal handling resource limit reached

### Solution

1. Perform device restart via Web UI
2. If it persists after restart, contact after-sales to investigate system resources or firmware issues

---

## Problem 3: Agent runtime state persistence failure

### Matching Logs

```
agent [ER] cannot dump running state to <file path>, we will not be able to recover in case of a fatal error!
agent [WA] failed to save global data
agent [WA] failed to save <service name> service data
agent [WA] failed to load global data
agent [WA] failed to load <service name> service data
```

### Diagnosis

Agent cannot write runtime state to the persistence file (`/var/run/agent<ID>.state`), or cannot recover state from that file. This means if agent crashes abnormally and restarts, it may not be able to restore the pre-crash runtime state.

### Cause

1. `/var/run/` partition space insufficient
2. Filesystem read-only (flash lifetime exhausted or filesystem corruption)
3. Permission issues preventing file creation/writing
4. Device abnormal power loss causing state file corruption

### Solution

1. Perform device restart via Web UI
2. If the issue persists, upgrade to the latest firmware version via Web UI
3. If it occurs repeatedly with other anomalies, contact after-sales to check hardware

---

## Problem 4: Agent management info push failure

### Matching Logs

```
agent [ER] publish mgmt info return <return value>
agent [ER] send mgmt info to service <service ID> return <return value>
```

### Diagnosis

Agent failed to push management port info to other services (e.g., syswatcher, interface). This may cause incorrect port status display on the Web management page.

### Cause

1. Target service has not started yet or has crashed
2. IPC channel anomaly (message queue full, socket disconnected)
3. Target service is busy and cannot process messages in time

### Solution

1. Perform device restart via Web UI to ensure all services start properly
2. If sporadic and not affecting business, can be ignored
3. If frequent, contact after-sales to investigate IPC communication issues

---

## Problem 5: Agent received SIGHUP restart

### Matching Logs

```
agent [WA] Received SIGHUP; restarting...
```

### Diagnosis

After receiving SIGHUP signal, agent will reload configuration and restart itself and all sub-services. This is a normal configuration reload process.

### Cause

1. System triggered SIGHUP signal to notify agent to reload after config change
2. Some service restart operations triggered signal propagation

### Solution

This is normal runtime log, no action needed. If triggered frequently (e.g., multiple times per minute), check for abnormal config change loops.

---

## Problem 6: HTTPD memory overrun auto-restart

### Matching Logs

```
agent [WA] httpd's memory exceeds <memory limit> kB, restart it now!
```

### Diagnosis

httpd (HTTP service process) memory usage exceeded the preset threshold (typically several thousand kB by default). Agent proactively restarts it to prevent memory leaks from affecting device stability. Web management pages are briefly unavailable during the restart.

### Cause

1. Large number of concurrent web requests causing httpd memory growth
2. httpd has a memory leak bug
3. Uploading large files or long-running web operations consuming large amounts of memory

### Solution

1. If sporadic, no action needed; agent will auto-recover
2. If frequent, reduce the number of clients accessing Web UI simultaneously
3. Upgrade to the latest firmware version via Web UI
4. If severely impacting usage, contact after-sales

---

## Problem 7: Web Nginx missing IP address

### Matching Logs

```
agent [WA] nginx reload configuration file failed(<return value>)
agent [WA] start nginx service failed(<return value>)
agent [ER] there is no such IP address!
```

### Diagnosis

web-nginx (nginx frontend for the new Web UI) found that the IP address referenced in the config does not exist in the current system during startup or config reload. This causes Web management pages to be inaccessible.

### Cause

1. Interface has not obtained an IP address (e.g., DHCP failure, PPP dial not completed)
2. Interface config was deleted but nginx config was not updated
3. Interface is enabled but physical link is not UP

### Solution

1. Check that the interface IP configuration is correct via Web UI
2. Ensure the interface nginx binds to has properly obtained an IP address
3. If the interface is normal but the error persists, re-save the web service config via Web UI

---

## Problem 8: DNSMASQ evdns_base creation failure

### Matching Logs

```
agent [ER] Couldn't create evdns_base
```

### Diagnosis

dnsmasq DNS/DHCP service failed to create libevent's DNS resolution base structure (evdns_base) during initialization. This will cause the DNS relay function to be completely unavailable.

### Cause

1. Insufficient system memory
2. libevent library initialization anomaly
3. System resources (e.g., sockets) exhausted

### Solution

1. Perform device restart via Web UI
2. If the issue persists, contact after-sales to investigate system resources or firmware bugs

---

## Problem 9: DNSMASQ config file / Lease file operation failure

### Matching Logs

```
agent [ER] open file /etc/dnsmasq.conf failed.
agent [ER] open file <lease file path> failed
agent [ER] get pos error
```

### Diagnosis

dnsmasq cannot open the main config file `/etc/dnsmasq.conf` or DHCP lease file, causing DHCP server and DNS relay service to be unable to start or unable to record lease information.

### Cause

1. Filesystem read-only or corrupted
2. `/etc/dnsmasq.conf` accidentally deleted
3. `/var/` partition space insufficient, cannot create lease file
4. Device abnormal power loss causing file corruption

### Solution

1. Re-save DHCP service config via Web UI (will regenerate config file)
2. If the issue persists, perform device restart via Web UI
3. If still unresolved, contact after-sales to check storage hardware

---

## Problem 10: DNSMASQ VIF interface fetch failure

### Matching Logs

```
agent [ER] get ippt4031 vif failed(do ippt failed), now set extra address to pc
agent [ER] get vif(default) by if_info failed
agent [ER] get vif by if_info failed
agent [ER] Cannot get CLI name of VIF(<type>,<number>,<type2>,<number2>)
```

### Diagnosis

dnsmasq cannot obtain the VIF (Virtual Interface) information for the specified interface when configuring the DHCP server. This may be due to the interface in IP Passthrough mode or the interface specified in DHCP config not existing or being in an abnormal state.

### Cause

1. The interface specified in DHCP config has not been created or has been deleted
2. Interface status is not UP
3. IP Passthrough feature not properly configured
4. VIF type/port number does not match current system state

### Solution

1. Check via Web UI that the interface in DHCP service config is valid and UP
2. If IP Passthrough is involved, check that IP Passthrough config is correct
3. Re-save DHCP service config via Web UI
4. If the interface is correct but errors persist, check if the interface physical link is normal

---

## Problem 11: DNSMASQ MAC address format conversion anomaly

### Matching Logs

```
agent [ER] src/dest mac address null when mac format exchange
```

### Diagnosis

dnsmasq found null source or destination MAC address pointer during MAC address format conversion. This usually occurs when processing DHCP lease information or MAC-IP bindings.

### Cause

1. Corrupted records exist in DHCP lease file
2. Lease data structures in memory were abnormally modified
3. Empty MAC addresses in MAC-IP binding config

### Solution

1. Re-save DHCP service config via Web UI
2. Check MAC-IP binding list to ensure all entries have valid MAC addresses
3. If the issue persists, perform device restart via Web UI

---

## Problem 12: DNSMASQ domain resolution failure

### Matching Logs

```
agent [ER] req_node is NULL in dns_resolve
agent [ER] req_node is NULL in callback
agent [ER] [<domain>]dns resolve failed, <error description>
agent [ER] Failed to malloc req_node
```

### Diagnosis

dnsmasq's cloud domain resolution module failed while processing DNS requests. `req_node is NULL` indicates memory allocation or data structure anomaly; `dns resolve failed` indicates DNS resolution request for a specific domain failed.

### Cause

1. Memory shortage causing malloc failure
2. Upstream DNS server unreachable
3. DNS record for the domain does not exist or DNS server returned an error
4. Network connectivity issue causing DNS request timeout

### Solution

1. Check that DNS server configuration is correct via Web UI
2. Confirm device WAN-side network connectivity is normal
3. If many domains fail to resolve, check upstream DNS server status
4. Re-save DNS service config via Web UI

---

## Problem 13: DNSMASQ cloud domain config issue

### Matching Logs

```
agent [ER] Invalid cloud domain
agent [ER] cloud domains are over than <max count>, can't add more!
agent [ER] [<function name>]malloc CLOUD_DOMAIN_NODE failed, <errno>:<error description>
agent [WA] failed to save cloud domain rule data
agent [WA] failed to load cloud domain data
```

### Diagnosis

Problems with cloud-delivered domain rule configuration: invalid domain format, rule count exceeding limit, or failure to save/load rule data.

### Cause

1. Cloud platform delivered an invalid domain format
2. Number of domain rules in a single delivery exceeds device capacity
3. Memory shortage prevents allocating memory for domain nodes
4. Storage space shortage prevents rule data persistence

### Solution

1. Check the format of domain rules delivered by the cloud platform
2. Reduce the number of domain rules per delivery, deliver in batches
3. Perform device restart via Web UI to free memory
4. Contact after-sales for firmware that supports larger rule capacity

---

## Problem 14: DNSMASQ IPSet file issue

### Matching Logs

```
agent [ER] Invalid ipset file
agent [ER] Ipset file <file path> not found
agent [ER] Failed to open ipset file <file path>
```

### Diagnosis

dnsmasq found an invalid ipset file path, missing file, or unopenable file when processing ipset (IP set) updates.

### Cause

1. Cloud platform or config change delivered an invalid ipset file path
2. ipset file was referenced before being generated (timing issue)
3. Filesystem permission or space issue

### Solution

1. Check and re-save related config via Web UI
2. If cloud-delivered, check that the ipset config from cloud platform is correct
3. Perform device restart via Web UI

---

## Problem 15: DNSMASQ other config issues

### Matching Logs

```
agent [WA] failed to create resolv.conf for dhcpd & dnsrelay services
agent [WA] failed to dns name server status
```

### Diagnosis

1. Cannot create `resolv.conf` for DHCP and DNS relay services, affecting DNS resolution
2. Cannot obtain DNS name server status, causing DNS service monitoring anomaly

### Cause

1. `/etc/resolv.conf` or temp directory not writable
2. DNS server list empty or format error
3. Insufficient system resources

### Solution

1. Check and reconfigure DNS server addresses via Web UI
2. Perform device restart via Web UI
3. Check WAN-side network connectivity

---

## Problem 16: DDNS config file write failure

### Matching Logs

```
agent [ER] Write ddns config file: <config file name>.conf failed!
agent [ER] Write ddns config file: <config file path> failed!
```

### Diagnosis

Agent cannot write DDNS (Dynamic DNS) config to the config file, causing DDNS functionality to fail to start or update properly.

### Cause

1. Filesystem read-only or insufficient space
2. Target directory permission issue
3. Config file path does not exist

### Solution

1. Re-save DDNS config via Web UI / cloud platform
2. Perform device restart via Web UI
3. Check that parameters in DDNS config are complete and valid

---

## Problem 17: DDNS runtime state anomaly

### Matching Logs

```
agent [ER] get interface failed, skip
agent [ER] DDNS <number>: malformed cache file
agent [ER] DDNS SM struct of <name> has not been alloced
agent [ER] bad new_vif
```

### Diagnosis

DDNS encountered various anomalies at runtime: unable to obtain network interface info (causing the DDNS task to be skipped), DDNS cache file corruption, DDNS state machine structure not allocated, or VIF info anomaly.

### Cause

1. Network interface specified in DDNS config does not exist or has not obtained an IP
2. Device abnormal power loss causing DDNS cache file corruption
3. Memory allocation failure during DDNS task initialization
4. Invalid VIF info passed during interface status change

### Solution

1. Check via Web UI that the interface bound in DDNS config is correct and online
2. Re-save DDNS config via Web UI
3. Perform device restart via Web UI
4. If DDNS cache file keeps getting corrupted, contact after-sales to investigate storage issues

---

## Problem 18: ODHCPD service anomaly

### Matching Logs

```
agent [ER] ERROR in opening the file <config file>: <error description>
agent [ER] Can't not get vif name map for IF_INFO (<type>, <number>, <number>)
agent [ER] allocate memory failed <errno>.
```

### Diagnosis

ODHCPD (IPv6 DHCP/RA service) encountered config issues: cannot open config file (e.g., `/var/run/odhcpd.conf`), cannot obtain VIF name mapping, or memory allocation failure.

### Cause

1. ODHCPD config file does not exist or is unreadable (filesystem issue)
2. Interface (IF_INFO) referenced in config does not exist in current system
3. Insufficient system memory
4. Incomplete IPv6-related configuration

### Solution

1. Re-save IPv6 / ODHCPD related config via Web UI
2. Check that the interface referenced in config is enabled and online
3. Perform device restart via Web UI
4. If memory allocation continues to fail, contact after-sales

---

## Problem 19: NDPPD config file open failure

### Matching Logs

```
agent [ER] ERROR in opening the file <config file>: <error description>
```

### Diagnosis

NDPPD (IPv6 NDP proxy daemon) cannot open its config file (e.g., `/var/run/ndppd.conf`), causing IPv6 NDP proxy functionality to be unavailable.

### Cause

1. Config file does not exist (not yet generated on first NDPPD service startup)
2. Filesystem read-only or insufficient space
3. Incomplete IPv6 config causing config file generation failure

### Solution

1. Check that IPv6 config is complete via Web UI and re-save
2. Perform device restart via Web UI
3. If the issue persists, contact after-sales

---

## Problem 20: JSON config parse errors (Category)

The following logs all originate from the cloud web config interface (agent_cloud_web.c). Triggered when cloud-delivered JSON config has format errors, missing fields, or invalid values.

### DHCP Service

```
agent [ER] request json is NULL
agent [ER] dhcp services loads json error,<line>:<error description>
agent [ER] get iface info error, iface_name:<interface name>
agent [ER] dhcp server of <interface name> confilict.
agent [ER] alias conflict
agent [ER] ip pool conflict
agent [ER] get option object error
agent [ER] DHCP Server and DHCP Relay cannot be enabled at the same time
agent [ER] DHCP Server enable without ip pool, invalid config
agent [ER] the number of dhcp server entries reach the max limit <max count>
agent [ER] Add mac_bind of [<interface name>] failed, mac_bind list is full.
```

### DDNS

```
agent [ER] ddns provider check error! <provider> is not support
agent [ER] ddns loads json error,<line>:<error description>
agent [ER] get iface info error, iface_name:<interface name>
```

### DNS Service

```
agent [ER] dns services loads json error,<line>:<error description>
```

### General

```
agent [ER] request json is NULL
```

### Diagnosis

Cloud-delivered JSON config cannot be correctly parsed or validation failed, causing the corresponding service config to not take effect.

### Cause (by sub-module)

- **DHCP Service**: JSON format error, invalid/nonexistent interface name, DHCP Server and Relay enabled simultaneously, empty IP pool, IP pool conflict, alias conflict, DHCP entries exceeding limit, MAC bind list full
- **DDNS**: JSON format error, unsupported DDNS provider name, invalid/nonexistent interface name
- **DNS Service**: JSON format error
- **General**: Request body is empty (request json is NULL)

### Solution (applicable to all above)

1. Check via cloud platform that the delivered JSON config format conforms to device API specification
2. Ensure interface names (`iface_name`) referenced in JSON match actual device interface names
3. DHCP Server and DHCP Relay cannot be enabled on the same interface simultaneously; choose one function
4. DHCP Server must have a valid IP address pool configured (start_ip / end_ip)
5. Check if IP address pool conflicts with existing address pools or aliases
6. Reduce the number of DHCP entries to ensure they don't exceed device limits
7. When MAC bind list is full, delete unnecessary entries before adding new ones
8. Re-deliver rules one by one via cloud platform

---

## Problem 21: DNSMASQ service stuck auto-recovery

### Matching Logs

```
agent [IN] dnsmasq may be stuck, restart it.
```

### Diagnosis

Agent detected that dnsmasq may be stuck and unresponsive, proactively restarted it. This is agent's self-healing mechanism.

### Cause

1. dnsmasq entered an infinite loop or long block when processing a large number of DHCP requests or DNS queries
2. Upstream DNS server response timeout causing dnsmasq thread blocking
3. High system load causing dnsmasq scheduling delay

### Solution

1. If sporadic, this is normal self-healing, no action needed
2. If frequently triggered, reduce the number of DHCP clients or DNS query load
3. Check upstream DNS server response speed
4. Upgrade to the latest firmware version via Web UI

---

## Conditional Compilation Module Logs

The following logs **usually do not appear** on ODU12 and may only trigger under specific compilation conditions.

### SNMPD (snmpd agent entry disabled by #if 0)

```
agent [ER] ERROR in opening the file <SNMPD_CONF_FILE path>
```

Only appears when SNMP agent is explicitly enabled. ODU12 typically does not enable SNMP agent service.

### OVDPX (ovdpx agent entry disabled by #if 0)

```
agent [ER] send config response error.
```

And multiple `syslog(LOG_WARNING, ...)` level warnings. Only appears when OVDP service is explicitly enabled. ODU12 typically does not enable OVDP service.

### NGINX (only when INHAND_IP812 macro defined)

```
agent [ER] ngnix open temp config file err
agent [ER] ngnix open import config file err
agent [ER] ngnix import write config file err
agent [ER] ngnix import write config file does not exist
agent [ER] ngnix read import config file err
agent [ER] ngnix write config file err
agent [WA] SD card is not found
agent [ER] SSD harddisk is not found
```

ODU12 does not define INHAND_IP812, so these logs will not appear. If they do, the firmware version is mismatched.

### Dockerd / Portainer (only when INHAND_DOCKER macro defined)

```
agent [WA] dockerd exited status: <status code>(<error description>)
agent [WA] dockerd exited by signal with status <signal status>
agent [WA] portainer exited status: <status code>(<error description>)
agent [WA] portainer exited by signal with status <signal status>
```

ODU12 typically does not enable Docker functionality, these logs will not appear.

### RSYNC (only when INHAND_IP812 macro defined)

```
agent [WA] rsync agent exited!
```

ODU12 does not define INHAND_IP812, will not appear.

### Edge Compute / Losant (only when INHAND_IG9 macro defined)

```
agent [ER] Decompression losant edge computing image failed.(<errno>:<error description>)
agent [ER] Load losant edge computing image failed.(<errno>:<error description>)
agent [ER] Can't create losant edge computing config file.!error(<errno>):<error description>
agent [ER] Can't find losant instance!
agent [ER] popen cmd:<command> failed(<error description>)
```

ODU12 does not define INHAND_IG9, will not appear.

### DHCP Sysrepo (only when NETCONF compile option enabled)

```
agent [ER] Getting changes iter failed (<error description>).
agent [ER] reach to max mac bind num:(<max count>)
agent [ER] open file <file> failed
```

ODU12 typically does not enable NETCONF, these logs will not appear.

---

## Normal INFO Logs (No Action Needed)

The following logs indicate agent and its sub-services are running normally. Do not diagnose as problems:

```
agent [IN] stop <service name>
agent [IN] start <service name> service
agent [IN] start <service name> at port <port number>
agent [IN] start dhcp server and/or dns relay server
agent [IN] init odhcpd
agent [IN] init ndppd
agent [IN] init mipc_wwan
agent [IN] restart the dnsmasq server by ip passthrough
agent [IN] start dhcprelay, vif type[<type>], port[<port>] status not UP
agent [IN] killall -SIGKILL dnsmasq
agent [IN] killall -SIGKILL telnetd
agent [IN] killall -SIGKILL dropbear
agent [IN] stop snmp mib agent
agent [IN] Create SSH Key pair failed!!
agent [IN] MSG: 0x<message type> from service <service ID>
agent [IN] Received SIGUSR1; start/stop tracing to <file path>
agent [IN] <service name> deamon agent exited!
agent [IN] <service name> asnyc deamon agent exited!
agent [WA] Received SIGHUP; restarting...
agent [WA] agent is going to exit
agent [IN] ipv6 globally enabled/disabled, start/stop odhcpd.
agent [IN] ODHCP6C Client event <event>, interface <interface name>
agent [IN] Random prefix assignment.
agent [IN] ra_mtu changed to <MTU value>
agent [IN] update ODHCP6C info opt <option>
agent [IN] <IPv6 prefix> can not be divided.
agent [IN] <interface> assigned prefix <prefix> for interface <interface>.
agent [IN] <source interface> prefix offer [<operation>] for <destination interface>.
agent [IN] load cloud domain rule cnt <count>
agent [IN] set ip passthrough dhcp server range
agent [IN] dnsmasq may be stuck, restart it.
agent [IN] check dhcprelay enable
```

---

## General Troubleshooting Information Collection

If agent-related issues cannot be located via the sections above, please collect the following information:

1. All `agent [ER]` and `agent [WA]` lines in device logs
2. Complete logs for 1 minute before and after the fault
3. Configuration summary of agent-managed sub-services (dnsmasq, httpd, sshd, telnetd, ddns, odhcpd, ndppd, etc.)
4. Fault timestamp and any prior configuration changes (Web UI / cloud platform delivery) or device events (interface UP/DOWN, restart, etc.)
5. Impact scope description (which sub-services are unavailable, whether network connectivity is affected)
