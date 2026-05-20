# sntpc — Problem Diagnosis

> Applicable: sntpc (SNTP client/NTP time synchronization) service self-anomaly (signal handling failure, runtime state persistence failure, evDNS initialization failure), NTP time sync failure (socket/connection/NTP protocol error, DNS resolution anomaly), Web UI / cloud JSON config error.

## Log Format Reference

| Level | Meaning | Requires Attention |
|-------|---------|-------------------|
| [ER] | ERROR | Yes |
| [WA] | WARNING | Yes |
| [IN] | INFO | For reference only |

> Note: sntpc service log prefix is `sntpc`. Syncs system time from configured NTP server list via SNTP protocol (UDP port 123) with configurable sync interval (default 3600s).

---

## Problem 1: Signal handler registration failure

```
sntpc [WA] cannot add handle for SIGHUP / SIGUSR1 / SIGCHLD / SIGTERM / SIGINT
```

### Solution

1. Perform device restart via Web UI
2. If persistent, contact after-sales

---

## Problem 2: Runtime state persistence failure

```
sntpc [WA] cannot dump running state to <file path>
sntpc [WA] failed to save/load service data
```

### Solution

1. Re-save SNTP client config via Web UI
2. Perform device restart via Web UI

---

## Problem 3: evDNS initialization failure

### Matching Logs

```
sntpc [ER] new endns base
```

### Diagnosis

sntpc failed to create libevent DNS resolver at startup. Domain-name NTP servers (e.g., `pool.ntp.org`) cannot be resolved; only IP-address NTP servers can work.

### Solution

1. Configure NTP servers as IP addresses instead of domain names via Web UI
2. Perform device restart via Web UI
3. If persistent, contact after-sales

---

## Problem 4: NTP time sync failure (Socket / Connection / NTP protocol errors)

### Matching Logs

```
sntpc [WA] unable to create a socket
sntpc [ER] bind <IP address>
sntpc [WA] can not get ip address while starting ntp request
sntpc [WA] unable to connect to NTP server <server IP>
sntpc [ER] ntp request error: <errno>, <error description>
sntpc [WA] receive invalid packet size from NTP server
sntpc [WA] receive packet from another host <IP>:<port>
sntpc [WA] receive invalid response from NTP server
sntpc [ER] BUG!!not gl_sntpc_fd
```

### Cause

- Socket resources exhausted
- Source interface not UP or has no IP
- NTP server unreachable (network/firewall blocking UDP 123)
- NTP server response not RFC 2030 compliant or tampered
- DNS resolution failure for NTP server domain

### Solution

1. Check NTP server address is correct and reachable
2. Check source_interface is UP with valid IP
3. If using domain, confirm DNS resolution works (try switching to IP)
4. Confirm firewall not blocking UDP 123 outbound
5. Switch to alternative NTP servers (e.g., `ntp.aliyun.com`, `ntp.tencent.com`)
6. Perform device restart via Web UI

---

## Problem 5: JSON config parse error

```
sntpc [ER] request json is NULL
sntpc [ER] request json argument/invalid is invalid
sntpc [ER] sntpc loads json error,<line>:<error description>
sntpc [ER] get iface info error, iface_name:<interface name>
sntpc [ER] sntp_servers_list item error / sntpc parse item array error
sntpc [ER] Source address/interface is already specified
```

### Solution

1. Check delivered JSON config format via cloud platform / Web UI
2. Ensure source_interface matches actual device panel name
3. `source_ip` and `source_interface` are mutually exclusive; configure only one
4. Re-save SNTP config via Web UI

---

## Normal INFO Logs (No Action Needed)

```
sntpc [IN] time updated: <time string> [+/- <delta>s]
sntpc [IN] time updated by redial/gps service
sntpc [IN] failed to send time update request!
sntpc [IN] MSG: 0x<type> from service <ID> / Len: / Content:
```
