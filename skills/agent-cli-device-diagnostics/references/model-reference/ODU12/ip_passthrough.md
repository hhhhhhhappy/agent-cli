# ip_passthrough — Problem Diagnosis

> Applicable: ip_passthrough (IP Passthrough) service self-anomaly (signal handling failure, runtime state persistence failure, restart failure), IP Passthrough execution failure (LAN configured as WAN, WAN/LAN interface info fetch failure), invalid subnet mask length, socket/ioctl error, cloud JSON config error.

## Log Format Reference

| Level | Meaning | Requires Attention |
|-------|---------|-------------------|
| [ER] | ERROR | Yes |
| [WA] | WARNING | Yes |
| [IN] | INFO | For reference only |

> Note: ip_passthrough service log prefix is `ip_passthrough`.

---

## Problem 1: Signal handler registration failure / termination signal exit / restart failure

### Matching Logs

```
ip_passthrough [ER] cannot add handle for SIGHUP / SIGUSR1 / SIGCHLD / SIGTERM / SIGINT
ip_passthrough [ER] Received <signal name>; quitting...
ip_passthrough [ER] Restart FAILED
ip_passthrough [WA] Received SIGHUP; restarting...
```

### Diagnosis

Service failed to register signal handlers at startup, received termination signal and exited, or SIGHUP hot restart `execv` failed.

### Solution

1. Perform device restart via Web UI
2. If persistent, contact after-sales

---

## Problem 2: Runtime state persistence failure

### Matching Logs

```
ip_passthrough [ER] cannot dump running state to <file path>, we will not be able to recover in case of a fatal error!
ip_passthrough [WA] Failed to save global data
ip_passthrough [WA] Failed to load global data / gl_ip_passinfo data
```

### Solution

1. Re-save IP Passthrough config via Web UI
2. Perform device restart via Web UI

---

## Problem 3: IP Passthrough execution failure

### Matching Logs

```
ip_passthrough [ER] service[<service ID>]:do ippt faild,retry after <N>s
ip_passthrough [ER] ippt config lan[<LAN interface name>] is wan
ip_passthrough [ER] do ippt unknown result[<result code>]
```

### Diagnosis

IP Passthrough config delivered to interface service but execution failed.

### Solution

1. Check via Web UI that the downlink port selected in IP Passthrough config is correct (should be LAN, not WAN)
2. Re-save IP Passthrough config via Web UI
3. Perform device restart via Web UI

---

## Problem 4: WAN interface info fetch failure

### Matching Logs

```
ip_passthrough [ER] get wan[<interface name>] if info failed
```

### Solution

1. Check via Web UI that the WAN interface exists and name is correct
2. Ensure WAN interface is correctly configured and started
3. Perform device restart via Web UI

---

## Problem 5: Invalid subnet mask length

### Matching Logs

```
ip_passthrough [WA] invalid prefix_len:wan ip <WAN IP> is in the start or end of the subnet with mask <mask length>
ip_passthrough [WA] Please try configuring IP passthrough again after checking and modifying the mask length.
```

### Diagnosis

WAN interface IP is at the network address or broadcast address of the subnet, unable to carve out an independent IP for the LAN client.

### Solution

1. Contact carrier to adjust WAN subnet mask (e.g., /30 to /29 or larger)
2. If static IP for WAN, adjust mask length via Web UI

---

## Problem 6: Socket / IOCTL error

### Matching Logs

```
ip_passthrough [ER] socket create error
ip_passthrough [ER] ioctl error
```

### Solution

1. Perform device restart via Web UI
2. If persistent, contact after-sales

---

## Problem 7: JSON cloud config parse error

### Matching Logs

```
ip_passthrough [ER] request json is NULL
ip_passthrough [ER] static config loads json error,<line>:<error description>
ip_passthrough [ER] get wanif_info failed / get lanif_info failed, lan name <interface name>
ip_passthrough [ER] popen failed <errno>:<error description>
ip_passthrough [ER] fgets failed <errno>:<error description>
ip_passthrough [ER] open <DNSMASQ_LEASE_FILE path> failed,(<errno>):<error description>
```

### Solution

1. Check via cloud platform that delivered JSON config format is correct
2. Ensure uplink/downlink interface names match actual device interface panel names
3. Re-save IP Passthrough config via Web UI
4. Perform device restart via Web UI

---

## Normal INFO Logs (No Action Needed)

```
ip_passthrough [IN] reset to default config
ip_passthrough [IN] MSG: 0x<type> from service <ID> / Len / Content
ip_passthrough [IN] Received SIGUSR1; <start/stop> tracing to <trace file path>
ip_passthrough [IN] clear ip pasthrough firewall policies. / ip passthrough init
ip_passthrough [IN] ip_passinfo: enable-<value> mac-<MAC> wan_info <type>/<slot>/<port>,lan_info
ip_passthrough [IN] wan[<interface>] vif status is not up / vif not found
```
