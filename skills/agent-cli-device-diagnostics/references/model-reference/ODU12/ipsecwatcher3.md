# ipsecwatcher3 — Problem Diagnosis

> Applicable: ipsecwatcher3 (IPsec tunnel management) service self-anomaly (signal handling failure, runtime state persistence failure, restart failure), strongswan subprocess exit/tunnel operation failure, IPC/SNMP communication failure, XFRM file operation error, IPsec tunnel consecutive connection failure auto-restart device, cloud JSON config error.

## Log Format Reference

| Level | Meaning | Requires Attention |
|-------|---------|-------------------|
| [ER] | ERROR | Yes |
| [WA] | WARNING | Yes |
| [IN] | INFO | For reference only |

> Note: ipsecwatcher3 service log prefix is `ipsecwatcher3`. Manages strongswan (charon) subprocess lifecycle, responsible for IPsec tunnel config generation, start/stop, status monitoring, and statistics.

---

## Problem 1: Signal handler registration failure / termination signal exit / restart failure

### Matching Logs

```
ipsecwatcher3 [ER] cannot add handle for SIGHUP / SIGUSR1 / SIGCHLD / SIGTERM / SIGINT
ipsecwatcher3 [ER] Received <signal name>; quitting...
ipsecwatcher3 [ER] Restart FAILED
ipsecwatcher3 [WA] Received SIGHUP; restarting...
```

### Solution

1. Perform device restart via Web UI
2. If persistent, contact after-sales

---

## Problem 2: Runtime state persistence failure

### Matching Logs

```
ipsecwatcher3 [ER] cannot dump running state to <file path>, we will not be able to recover in case of a fatal error!
ipsecwatcher3 [WA] failed to save/load global data / service data
ipsecwatcher3 [ER] dump/load global/general ipsec tunnel list state failed
```

### Solution

1. Re-deliver IPsec tunnel config via Web UI / cloud platform
2. Perform device restart via Web UI

---

## Problem 3: strongswan subprocess abnormal exit / tunnel management operation failure

### Matching Logs

```
ipsecwatcher3 [ER] ipsec down tunnel <tunnel name> failed after <N> retries
ipsecwatcher3 [ER] <function name>[<line>].seek fp error[<errno>]:<error description>
ipsecwatcher3 [ER] delete config file fail. err[<errno>]:<error description>
ipsecwatcher3 [IN] child exit / strongswan existed
ipsecwatcher3 [IN] update tunnels failed <N> times, restart strongswan
```

### Solution

1. Perform device restart via Web UI
2. If consistently appearing, contact after-sales
3. Check and re-save all IPsec tunnel configs via Web UI

---

## Problem 4: IPC / SNMP message communication failure

### Matching Logs

```
ipsecwatcher3 [ER] broadcast msg is not ok.
ipsecwatcher3 [ER] request route/interface/wlan info error!
ipsecwatcher3 [ER] send snmp msg sa down/up/tunnel up fail.
```

### Solution

1. Perform device restart via Web UI
2. Check related services (routed, interface, dot11, sdwan) are running normally

---

## Problem 5: XFRM policy file operation error

```
ipsecwatcher3 [ER] ip mask input is null
ipsecwatcher3 [ER] open file <file path> failed, err[<errno>]<error description>
```

---

## Problem 6: IPsec tunnel consecutive connection failure auto-restart device

### Matching Logs

```
ipsecwatcher3 [IN] connecting ipsec tunnel <tunnel name> failed <N> times, reboot device
```

### Diagnosis

Normal IPsec or SD-WAN IPsec tunnel consecutive connection failures reached the failover `reboot_fail_times` threshold (default 10 retries, checked every 150 seconds). Device will auto-execute `reboot`.

### Solution

1. Check peer IPsec gateway is reachable and operational
2. Check tunnel config PSK/certificates via Web UI
3. Check IKE version, encryption algorithms, auth methods match peer
4. Check WAN interface status

---

## Problem 7: JSON cloud config parse errors

```
ipsecwatcher3 [ER] request json is NULL
ipsecwatcher3 [ER] ipsec loads json error,<line>:<error description>
ipsecwatcher3 [ER] get ipsec config failed
ipsecwatcher3 [ER] decrypt key failed / key length[<length>] is invalid
ipsecwatcher3 [ER] failed to pack json payload for wlan status
ipsecwatcher3 [ER] failed to dump json to string
```

### Solution

1. Check delivered JSON config format via cloud platform
2. Re-set PSK key via Web UI
3. Ensure `interface` field matches actual device panel name
4. Re-save IPsec tunnel config via Web UI

---

## Normal INFO Logs (No Action Needed)

```
ipsecwatcher3 [IN] ipsec daemon will start/stop!!!
ipsecwatcher3 [IN] reset to default config / reinit ipsecwatcher
ipsecwatcher3 [IN] start/stop strongswan daemon / update ipsec tunnels
ipsecwatcher3 [IN] ipsec create/delete config file for [<tunnel name>]
ipsecwatcher3 [IN] ipsec update, <operation> tunnel <tunnel name>
ipsecwatcher3 [IN] receive ipsec updown info / tunnel up/down/linking
ipsecwatcher3 [IN] IPsec TUNNEL[<tunnel>] sa [<src>, <dst>] link up/down
ipsecwatcher3 [IN] File ipsec.conf/secrets not exist
```
