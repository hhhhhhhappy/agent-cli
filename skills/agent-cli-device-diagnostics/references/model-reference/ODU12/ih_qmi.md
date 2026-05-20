# ih_qmi — Problem Diagnosis

> Applicable: ih_qmi service (QMI client + QMI proxy) communication anomaly with cellular modem — QMAP mode/size config invalid, QMI proxy connection/message send-receive failure, PDP dial/registration status anomaly, network interface startup/IP acquisition failure, DHCPv4/v6 client subprocess anomaly, modem unresponsive timeout.

## Log Format Reference

| Level | Meaning | Requires Attention |
|-------|---------|-------------------|
| [ER] | ERROR | Yes |
| [IN] | INFO | Needs evaluation in context |

> **Important**: The ih_qmi module is unique in that most error conditions are logged at LOG_IN level (not LOG_ER/LOG_WA). Therefore, the following LOG_IN patterns should be treated as "abnormal logs requiring attention" during diagnosis. Log prefixes vary by PDP context number (`ih-qmi0`, `ih-qmi1`, etc.). QMI proxy log prefix is `ih-qmi-proxy`.

## Architecture Overview

ih_qmi consists of two processes:

| Process | Log Prefix | Responsibility |
|---------|------------|---------------|
| ih-qmi client | `ih-qmi<N>` (N=PDP number) | PDP context activation, network registration monitoring, IP config acquisition, DHCP/ODHCP6C child process management |
| ih-qmi-proxy | `ih-qmi-proxy` | Direct QMI communication with modem via `/dev/cdc-wdm`, multiplexes QMI requests/indications from multiple clients |

---

## Problem 1: QMAP config parameter invalid

### Matching Logs

```
ih-qmi-proxy [ER] invalid value, qmap_mode=<value>
ih-qmi-proxy [ER] invalid value, qmap_size=<value>
```

### Diagnosis

ih-qmi-proxy failed to read QMAP config parameters from modem NIC sysfs during initialization: `qmap_mode` or `qmap_size` values are invalid.

### Cause

1. Modem NIC driver not correctly loaded
2. Modem firmware does not support QMAP or QMAP config anomaly
3. Modem hardware not ready

### Solution

1. Perform device restart via Web UI
2. If persistent, contact after-sales (possibly modem firmware/driver issue)

---

## Problem 2: QMI proxy connection failure (client side)

### Matching Logs (LOG_IN level, requires attention)

```
ih-qmi<N> [IN] failed to create socket
ih-qmi<N> [IN] failed to bind socket
ih-qmi<N> [IN] failed to open proxy
ih-qmi<N> [IN] failed to open <QMI channel path>
ih-qmi<N> [IN] Can't get device info
ih-qmi<N> [IN] No qmi interface
```

### Diagnosis

ih-qmi client cannot connect to ih-qmi-proxy via Unix domain socket at startup, or cannot directly open `/dev/cdc-wdm` QMI channel device file.

### Cause

1. ih-qmi-proxy process not started or crashed
2. Modem not fully initialized, `/dev/cdc-wdm` device node not yet created
3. Modem USB enumeration failed
4. System socket resources exhausted

### Solution

1. Wait for modem initialization to complete before retrying (typically 30~60 seconds)
2. Perform device restart via Web UI
3. If `No qmi interface` / `Can't get device info` persists, contact after-sales

---

## Problem 3: QMI proxy message send-receive failure (proxy side)

### Matching Logs (LOG_IN level, requires attention)

```
ih-qmi-proxy [IN] failed to send control message to <sockfd>
ih-qmi-proxy [IN] failed to send control message to cdc_wdm
ih-qmi-proxy [IN] failed to send message to conn <sockfd>
ih-qmi-proxy [IN] failed to recv message from cdc_wdm <fd>
ih-qmi-proxy [IN] failed to recv message from conn <fd>
ih-qmi-proxy [IN] failed to send message
ih-qmi-proxy [IN] poll error, fd=<fd>
```

### Diagnosis

ih-qmi-proxy encountered send/recv failure or poll error when forwarding QMI messages between client and modem.

### Cause

1. Client process exited abnormally, Unix socket connection disconnected
2. Modem `/dev/cdc-wdm` device unresponsive or device file closed
3. System poll resource anomaly

### Solution

1. Perform device restart via Web UI
2. If `failed to recv message from cdc_wdm` persists, contact after-sales

---

## Problem 4: Modem unresponsive / QMI timeout

### Matching Logs (LOG_IN level, requires attention)

```
ih-qmi-proxy [IN] no response from the dev, timeout!
ih-qmi-proxy [IN] timeout, cannot get correct response!
ih-qmi-proxy [IN] failed to get time!!
ih-qmi-proxy [IN] parameter error in <function name>
ih-qmi-proxy [IN] dev is't writeable
```

### Diagnosis

ih-qmi-proxy did not receive a response from modem within the timeout period after sending QMI request, or cannot get system time, or QMI device file is not writable.

### Cause

1. Modem firmware hung or response slow
2. Modem processing other high-priority operations (e.g., cell handover)
3. `/dev/cdc-wdm` device entered an abnormal state (unwritable)
4. System clock anomaly causing `gettimeofday` failure

### Solution

1. Perform device restart via Web UI
2. If modem timeout occurs frequently, contact after-sales

---

## Problem 5: PDP dial failure / network registration anomaly / IP acquisition failure

### Matching Logs (LOG_IN level, requires attention)

```
ih-qmi<N> [IN] connection state change to disconnected, exiting ...
ih-qmi<N> [IN] keep online mode, reconnecting...
ih-qmi<N> [IN] failed to start network interface
ih-qmi<N> [IN] ipv4 network interface down
ih-qmi<N> [IN] ipv6 network interface down
ih-qmi<N> [IN] failed to stop network interface
ih-qmi<N> [IN] failed to get ipv4 address
ih-qmi<N> [IN] failed to get ipv6 address
ih-qmi<N> [IN] ipv4 failed to bind mux data port
ih-qmi<N> [IN] ipv6 failed to bind mux data port
ih-qmi<N> [IN] failed to enable ipv4
ih-qmi<N> [IN] failed to enable ipv6
ih-qmi<N> [IN] failed to set ethernet mode
ih-qmi<N> [IN] Failed to init profile
```

### Diagnosis

ih-qmi client encountered errors in the PDP context activation flow.

### Cause

1. SIM card not properly inserted, unpaid, or data service not activated
2. Network registered by modem does not support IPv4/IPv6
3. APN configuration error
4. Weak carrier network signal or poor coverage
5. Modem firmware incompatible with QMI commands
6. `Failed to init profile` indicates insufficient client startup parameters

### Solution

1. Check SIM card status and signal strength via Web UI
2. Check APN configuration via Web UI
3. Confirm local carrier network coverage is normal
4. Perform device restart via Web UI
5. If `core network is ipv6 only.` appears but IPv4 is configured, adjust IP type config

---

## Problem 6: DHCPv4 / DHCPv6 subprocess anomaly

### Matching Logs (LOG_IN level, requires attention)

```
ih-qmi<N> [IN] failed to create socket
ih-qmi<N> [IN] stop udhcpc / dhcpc exit, pid: <PID> / start udhcpc
ih-qmi<N> [IN] stop odhcp6c / odhcp6c exit, pid: <PID> / start odhcp6c
```

### Diagnosis

DHCPv4 client (`udhcpc`) or DHCPv6 client (`odhcp6c`) managed by ih-qmi client — start/stop and exit events. If start→exit loop occurs repeatedly, DHCP acquisition continues to fail.

### Solution

1. Wait 30~60 seconds for DHCP retry (client will auto-restart DHCP subprocess)
2. Perform device restart via Web UI
3. Check if IP Passthrough or other features affecting DHCP are simultaneously enabled

---

## Problem 7: QMI proxy initialization failure

### Matching Logs (LOG_IN level, requires attention)

```
ih-qmi-proxy [IN] Failed to init proxy profile, sleep <N> seconds, retries:<count>
ih-qmi-proxy [IN] waitting modem ...
ih-qmi-proxy [IN] Can't get device info
ih-qmi-proxy [IN] No qmi interface
```

### Diagnosis

ih-qmi-proxy cannot initialize modem device config at startup.

### Solution

1. Wait for modem initialization (typically 30~90 seconds after startup)
2. If retries exceed 20 without success, perform device restart via Web UI
3. If persistent, contact after-sales

---

## Normal INFO Logs (No Action Needed)

```
ih-qmi-proxy [IN] server name:<name> / qmi sync ok / conn node counts:<N>, mesg node counts:<M>
ih-qmi<N> [IN] connect to <server> sockfd=<fd> / ih-qmi<N> running...
ih-qmi<N> [IN] registration_state/cs_attach_state/ps_attach_state/connection_status:0x<value>
ih-qmi<N> [IN] ipv4/ipv6 connection status changed, new status(<value>):<description>
ih-qmi<N> [IN] ipv4/ipv6 address/gateway/netmask/dns: <IP>
ih-qmi<N> [IN] ipv4/ipv6 enabled / core network is ipv6 only.
ih-qmi<N> [IN] start ipv4/ipv6 netwok interface ... / Received SIGUSR2 signal
ih-qmi<N> [IN] Alarm timer timeout! / call_end_reason*/registration state/service domain...
ih-qmi<N> [IN] set ethernet <IP/802.3> mode ok
ih-qmi<N> [IN] find <rootdir>/<device> idVendor=0x<VID> idProduct=0x<PID>
```

---

## General Troubleshooting Information Collection

1. All `ih-qmi` and `ih-qmi-proxy` prefixed lines in device logs
2. Complete logs for 3 minutes before and after the fault
3. Modem registration status and signal strength
4. SIM card status
5. APN configuration correctness
6. `call_end_reason` series log reason code values
7. Modem model and firmware version
