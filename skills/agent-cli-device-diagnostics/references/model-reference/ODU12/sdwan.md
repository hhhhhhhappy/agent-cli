# sdwand — Problem Diagnosis

> Applicable: sdwand (SD-WAN service) self-anomaly (signal handling failure, runtime state persistence failure), Multi-WAN link switch/path selection failure, AutoVPN config error (IPsec/VXLAN tunnels), Cloud Connect VPN config failure, VIF interface lookup failure, IPC message send failure (redial/xdsl/ipsecwatcher/LQM), uplink outage triggering reboot, cloud JSON config error.

## Log Format Reference

| Level | Meaning | Requires Attention |
|-------|---------|-------------------|
| [ER] | ERROR | Yes |
| [WA] | WARNING | Yes |
| [IN] | INFO | For reference only |

> Note: sdwand service log prefix is `sdwand`.

---

## Problem 1: Sdwand service signal handler registration failure / abnormal exit

```
sdwand [ER] cannot add handle for SIGHUP / SIGUSR1 / SIGCHLD / SIGTERM / SIGINT
sdwand [ER] Received <signal name>; quitting...
sdwand [ER] Restart FAILED
```

---

## Problem 2: Runtime state persistence failure

```
sdwand [ER] cannot dump running state to <file path>
sdwand [WA] failed to save/load global data / service data
```

---

## Problem 3: All uplinks down triggering reboot

### Matching Logs

```
sdwand [ER] have no uplink work for <N>m reboot
```

### Diagnosis

sdwand detected all uplinks (WAN) are down for the specified duration, triggering device restart to attempt recovery.

### Solution

1. Check physical connections and signal status of all WAN links
2. Confirm backup WAN is correctly configured and available
3. Adjust reboot delay via Web UI if needed

---

## Problem 4: AutoVPN config error

```
sdwand [ER] autovpn config is null / illegal version/role/loopback ip/peer/tunnel vip/tunnel_id
sdwand [ER] peers limit <limit>, add failed / peer role/mode error / invalid peer config
sdwand [ER] invalid subnets config / invalid autovpn config
sdwand [ER] get autovpn config failed / can't add status instance for peer
sdwand [ER] autovpn update vxlan failed, malloc fail
```

### Solution

1. Check AutoVPN config parameters via cloud platform / Web UI
2. Ensure role (hub/spoke) is correctly configured
3. Verify loopback IP / tunnel VIP format
4. Reduce peer count (do not exceed system limit)

---

## Problem 5: Cloud Connect config error

```
sdwand [ER] request json is NULL / invalid cloud connect json data
sdwand [ER] send the delete/add cloud connect openvpn msg to vpnd is not ok.
sdwand [ER] get the device's virtual ip/subnet/openvpn config string failed
sdwand [ER] reach the upper terminals limit / open openvpn config file failed
sdwand [ER] invalid cloud connect config / get/delete cloud connect config failed
```

---

## Problem 6: Multi-WAN VIF interface lookup/resolution failure

```
sdwand [ER] no vif match to interface <interface name>!
sdwand [ER] host :<hostname> not found! errno[<error code>]
sdwand [ER] get server IP failed! / no data found in json!
```

---

## Problem 7: IPC message send failure

```
sdwand [ER] send msg to redial/xdsl/ipsecwatcher/LQM is not ok.
sdwand [ER] autovpn request to switch hub failed.
```

---

## Problem 8-10: Detection thread, JSON cloud config, IPsec status errors

Refer to original full documentation for problems 8 through 10.

---

## Normal INFO Logs (No Action Needed)

```
sdwand [IN] changed sdwan reboot delay while uplink down to <N> minutes
sdwand [IN] Received SIGUSR1; start/stop tracing to <file>
sdwand [IN] have no uplink work, at uptime <N>s
sdwand [IN] add multi wan config of <interface> / multi wan config sla
sdwand [IN] try to switch cellular SIM card / restart cellular
sdwand [IN] found backup path with higher/lower priority!
sdwand [IN] wan [<interface>] on line! / primary wan on line!
sdwand [IN] autovpn clear all config / udpate autovpn config OK
sdwand [IN] update peer <peer ID> ipsec config / subnet full
sdwand [IN] cloud switch was disabled so stop cloud connect
sdwand [IN] cloud connect already connected not need to start again
sdwand [WA] Received SIGHUP; restarting...
```
