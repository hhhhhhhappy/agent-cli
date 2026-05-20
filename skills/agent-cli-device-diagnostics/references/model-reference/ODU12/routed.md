# routed — Problem Diagnosis

> Applicable: routed service self-anomaly (signal handling failure, runtime state persistence failure, subprocess management anomaly), routing protocol subprocess (zebra/ripd/ospfd/bgpd) startup failure or abnormal exit, static route config failure, dynamic routing protocol (RIP/OSPF/BGP) config error, policy routing/route policy (route-map/prefix-list/access-list) config anomaly, netlink kernel communication anomaly, cloud routing JSON config parse error.

## Log Format Reference

| Level | Meaning | Requires Attention |
|-------|---------|-------------------|
| [ER] | ERROR | Yes |
| [WA] | WARNING | Yes |
| [IN] | INFO | For reference only |

> Note: InHand management log prefix: `routed`. Standard FRR daemon logs use `zlog()` macro with prefixes `zebra`, `ripd`, `ospfd`, `bgpd`.

---

## Problem 1: Routed service signal handler registration failure

```
routed [ER] cannot add handle for SIGHUP / SIGUSR1 / SIGCHLD / SIGTERM / SIGINT
```

### Solution

1. Perform device restart via Web UI
2. If persistent, contact after-sales

---

## Problem 2: Routed service received abnormal signal and exited

```
routed [ER] Received <signal name>; quitting...
```

---

## Problem 3: Routed service received SIGHUP restart

```
routed [WA] Received SIGHUP; restarting...
```

> Normal runtime log, no action needed.

---

## Problem 4: Routing protocol subprocess startup failure

```
routed [ER] start zebra/ripd/ospfd/bgpd service failed(<return value>)
```

### Solution

1. If the routing protocol is not needed, disable it in config
2. Check routing protocol config via Web UI
3. Perform device restart via Web UI

---

## Problem 5: Routing protocol subprocess abnormal exit

```
routed [ER] zebra/ripd/ospf is dead, pid is <PID>, sigchld pid is <PID>
```

### Solution

1. Subprocess will auto-restart; observe recovery
2. If repeatedly crashing, check routing protocol config via Web UI
3. Perform device restart via Web UI

---

## Problem 6: Routed service runtime state persistence failure

```
routed [ER] cannot dump running state to <file path>
routed [WA] failed to save/load global data / service data
```

---

## Problem 7: Static route config failure

```
routed [WA] invalid table info / open <file path> failed
routed [ER] rtnetlink failed <return value> / vif_info is null
```

---

## Problem 8: Zebra Netlink communication anomaly

```
zebra [ERR] Can't open/bind <socket> socket: <error>
zebra [ERR] <socket> sendto failed / recvmsg overrun / EOF
zebra [ERR] netlink_talk sendmsg() error
zebra [ERR] Can't raise/lower privileges
```

---

## Problem 9-11: RIP / OSPF / BGP config errors

Key logs include:
```
routed [ER] rip network already set / version already set / neighbor error / netmask err
routed [ER] ospf area type hasn't correspondent / redistribute get type str err
routed [ER] The peer has already set / peers have reach the max!
bgpd [ERR] Malformed AS path / Martian nexthop / LOCAL_PREF attribute length error
```

### Solution

1. Check for duplicate config commands
2. Verify subnet mask format
3. Delete conflicting configs then re-save via Web UI

---

## Problem 12: BGP protocol message parse errors

```
bgpd [ERR] Malformed AS path from <peer>
bgpd [ERR] Origin attribute length/value invalid
bgpd [ERR] Nexthop attribute length error / Martian nexthop
bgpd [ERR] Bad originator ID/cluster list length
bgpd [WA] can't set sockopt TCP_MD5SIG on socket / bind to interface failed
```

---

## Problem 13: Prefix-list / Access-list / Key Chain config errors

```
routed [ER] cannot find key chain <name> id <ID>
routed [ER] key chain is full / access-list already configured
routed [ER] prefix-list sequence number <seq> overflow
```

---

## Problem 14-19: Restart failure, Zebra privilege/forward control, IPv6 static route, VIF info, JSON cloud config, Sysrepo

Refer to original full documentation for problems 14 through 19.

---

## Normal INFO Logs (No Action Needed)

```
routed [IN] reset to default config / MSG: 0x<type> from service <ID>
routed [IN] start rip/ospf/bgp / stop zebra/ripd/ospfd/bgpd
routed [IN] static route action netmask exchange err
routed [IN] flushing all/non-default static routes
zebra [IN]: <netlink receive buffer info>
bgpd [IN] SIGHUP received
ospfd [IN] ospfTrapNbrStateChange trap sent: <peer> now <state>
```
