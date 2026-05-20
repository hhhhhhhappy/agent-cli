# mipc_wwan — Problem Diagnosis

> Applicable: mipc_wwan (MIPC WWAN data channel management) service self-anomaly (signal handling failure, restart failure), modem status anomaly (modem not ready/modem crash), Redial IPC communication failure, APN/PDP dial-related (APN config fetch failure, PDP address anomaly, IMSI fetch failure, IA APN set failure), 464-XLAT/NAT46 device operation failure, IPv6 RS/RA socket error, memory allocation failure, interface data validation error (invalid profile/index/URC/TLV).

## Log Format Reference

| Level | Meaning | Requires Attention |
|-------|---------|-------------------|
| [ER] | ERROR | Yes |
| [WA] | WARNING | Yes |
| [IN] | INFO | For reference only |

> Note: mipc_wwan service log prefix is `mipc_wwan`. Communicates with modem via MIPC (MediaTek IPC) protocol.

---

## Problem 1: Signal handler registration failure / termination signal exit

### Matching Logs

```
mipc_wwan [ER] cannot add handle for SIGHUP / SIGUSR1 / SIGCHLD / SIGTERM / SIGINT
mipc_wwan [ER] Received <signal name>; quitting...
mipc_wwan [WA] Received SIGHUP; restarting...
```

### Solution

1. Perform device restart via Web UI
2. If persistent, contact after-sales

---

## Problem 2: Modem status anomaly (not ready / crashed)

### Matching Logs

```
mipc_wwan [ER] Modem is not ready!
mipc_wwan [ER] Modem is not ready, maybe MD Crashed.
```

### Solution

1. If at startup, wait for modem initialization (30~90 seconds)
2. If `MD Crashed` frequently, perform device restart via Web UI
3. Contact after-sales if persistent

---

## Problem 3: Redial IPC communication failure

```
mipc_wwan [ER] sent msg to redial is not ok.
mipc_wwan [ER] sent class3 apn to redial is not ok.
```

---

## Problem 4: APN / PDP config related errors

```
mipc_wwan [ER] Error to get APN profile / Error to get IMSI / Wrong PDP address:<offset>
mipc_wwan [ER] cannot get radio state
mipc_wwan [IN] apn is empty or cid is invalid
mipc_wwan [IN] can not activate <APN> result: 0x<result code>
mipc_wwan [IN] can not get imsi / invalid mnc_len <value>
```

### Solution

1. Check SIM card status via Web UI
2. Check APN config (APN name, PDP type, CID)
3. Perform device restart via Web UI

---

## Problem 5: 464-XLAT / NAT46 device operation failure

```
mipc_wwan [ER] can not open <NAT46_CONTROL_FILE> for writing
mipc_wwan [ER] can not create/destroy 464-xlat dev <system interface name>
```

### Solution

1. Perform device restart via Web UI
2. Disable CLAT if IPv6-only network IPv4 access is not needed

---

## Problem 6: IPv6 Router Solicitation / ICMP6 Socket error

```
mipc_wwan [WA] WARNING: setsockopt(<option>) err[<errno>]:<description>
mipc_wwan [ER] failed to send icmp6 packet to:<dest IP> err[<errno>]:<description>
mipc_wwan [ER] recvfrom returned error <errno> / packet too short / packet isn't router advertisement
```

### Solution

1. If device only uses IPv4, can ignore
2. Perform device restart via Web UI

---

## Problem 7: Memory allocation failure

```
mipc_wwan [ER] allocate memory failed <errno>. / calloc error / failed to calloc
```

---

## Problem 8: Interface/data validation error

```
mipc_wwan [WA] invalid profile / invalid profile index / invalid urc type / tlv is invalid
```

---

## Normal INFO Logs (No Action Needed)

```
mipc_wwan [IN] add/edit profile <N> <APN name> <PDP type> / PS status:<status>
mipc_wwan [IN] modem deact cid:<CID> / PDN(cid<CID>) was deactivated
mipc_wwan [IN] IMSI:<value> / radio state SW/HW / APN Profile count / IA apn/pdp_type/roaming_type
mipc_wwan [IN] sys_name/raw_name/cid/apn/ip_type/ipv4/ipv6/dns/mtu/prefix_len
mipc_wwan [IN] IPv4 addr changed / IPv6 link addr changed
```
