# tunnel — Problem Diagnosis

> Applicable: tunnel service self-anomaly (signal handling failure, runtime state persistence failure, restart failure), GRE/VXLAN tunnel create/delete failure (resource exhaustion, WAN/LAN interface anomaly, IPC broadcast failure), AutoVPN VXLAN config anomaly, cloud JSON config error.

## Log Format Reference

| Level | Meaning | Requires Attention |
|-------|---------|-------------------|
| [ER] | ERROR | Yes |
| [WA] | WARNING | Yes |
| [IN] | INFO | For reference only |

> Note: tunnel service log prefix is `tunnel`. Supports GRE, VXLAN (including AutoVPN VXLAN), max tunnel count 500 (ODU12).

---

## Problem 1: Signal handler registration failure / termination signal exit / restart failure

```
tunnel [ER] cannot add handle for SIGHUP / SIGUSR1 / SIGCHLD / SIGTERM / SIGINT / SIGALRM
tunnel [ER] Received <signal name>; quitting...
tunnel [ER] Restart FAILED
tunnel [WA] Received SIGHUP; restarting...
```

### Solution

1. Perform device restart via Web UI
2. If persistent, contact after-sales

---

## Problem 2: Runtime state persistence failure

```
tunnel [ER] cannot dump running state to <file path>
tunnel [WA] failed to save/load global data / tunnel data
tunnel [ER] dump file/load file is NULL
tunnel [ER] dump/load global/gre/vxlan/autovpn tunnel state/list failed
```

### Solution

1. Re-deliver GRE / VXLAN tunnel config via Web UI
2. Perform device restart via Web UI

---

## Problem 3: Tunnel resource exhaustion (list full / memory allocation failure / ID Stack anomaly)

```
tunnel [ER] tunnel list is full! / malloc tunnel node failed
tunnel [ER] id stack is empty/full! / id is invalid! / get tunnel id failed
tunnel [ER] tunnel num is too large / add gre/vxlan tunnel failed, tunnels are full.
tunnel [ER] create gre/vxlan node failed / add vxlan config <VNI> failed
```

### Diagnosis

Total GRE + VXLAN + AutoVPN VXLAN tunnel count reached 500 limit, GRE Tunnel ID pool exhausted, or malloc failed.

### Solution

1. Delete unnecessary GRE/VXLAN tunnels via Web UI
2. Reduce number of tunnels delivered per batch via cloud platform
3. Perform device restart via Web UI

---

## Problem 4: Create Tunnel with WAN/LAN interface anomaly

```
tunnel [ER] get <WAN interface> if_info failed
tunnel [ER] wan interface <WAN interface> is not up
tunnel [ER] wan interface <WAN interface> doesn't have ip address
tunnel [ER] get lan interface err / tunnel is null
```

### Solution

1. Check tunnel `interface` field matches actual device WAN panel name and is UP
2. Ensure WAN has valid IPv4 address
3. For IP Passthrough usage, close IP Passthrough to allow tunnel operations

---

## Problem 5: Unknown tunnel type / IPC broadcast failure

```
tunnel [ER] unknown type/type!
tunnel [ER] broadcast msg is not ok.
tunnel [ER] func[<function>] send ipc msg failed
```

---

## Problem 6: AutoVPN VXLAN config anomaly

```
tunnel [ER] AUTOVPN vxlan config is null / msg len error
tunnel [ER] invalid autovpn action <action code>
tunnel [ER] vxlan vni <VNI> invalid / create vxlan node failed
```

---

## Problem 7: JSON cloud config parse error

```
tunnel [ER] query/request json is NULL
tunnel [ER] static config loads json error,<line>:<error description>
tunnel [ER] json pack <tunnel name> failed
tunnel [ER] gre/vxlan <field> is empty/conflict
tunnel [ER] gre local_vip/peer_vip conflict
tunnel [ER] add gre/vxlan tunnel failed, tunnels are full.
tunnel [ER] unknown type/type!
```

### Solution

1. Check delivered JSON config format via cloud platform
2. Ensure each tunnel has unique name, local_vip/peer_vip/VNI no conflict
3. Ensure required fields are filled
4. Delete unnecessary tunnels to free capacity

---

## Normal INFO Logs (No Action Needed)

```
tunnel [IN] Received SIGUSR1; start/stop tracing / Received SIGALRM, send timer reset
tunnel [IN] MSG: 0x<type> from service <ID> / Len: / Content:
tunnel [IN] update/del vxlan config <VNI> / add vxlan config <VNI>
tunnel [IN] update autovpn vxlan config
tunnel [IN] interface <tunnel interface>, changed state to up/down
```
