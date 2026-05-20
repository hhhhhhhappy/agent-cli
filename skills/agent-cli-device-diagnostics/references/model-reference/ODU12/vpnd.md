# vpnd — Problem Diagnosis

> Applicable: vpnd (VPN service) self-anomaly (signal handling failure, runtime state persistence failure, restart failure), L2TP server/client config file operation failure (config/secrets/control/chap-secrets/pap-secrets create/write failure, Remote IP conflict/insufficient range), OpenVPN client/server config file operation failure, IPC broadcast/DM channel info send failure, OpenVPN tunnel IP conflict, Cloud Connect OpenVPN anomaly, cloud JSON config error.

## Log Format Reference

| Level | Meaning | Requires Attention |
|-------|---------|-------------------|
| [ER] | ERROR | Yes |
| [WA] | WARNING | Yes |
| [IN] | INFO | For reference only |

> Note: vpnd service log prefix is `vpnd`. Manages L2TP (xl2tpd subprocess + L2TPv3 subprocess), OpenVPN (multiple client subprocesses + server subprocess), PPP authentication, Cloud Connect OpenVPN, and IPC coordination with L2 bridge / firewall / routed / sdwan services.

---

## Problem 1: Signal handler registration failure / termination signal exit / restart failure

```
vpnd [ER] cannot add handle for SIGHUP / SIGUSR1 / SIGUSR2 / SIGCHLD / SIGTERM / SIGINT
vpnd [ER] Received <signal name>; quitting...
vpnd [ER] Restart FAILED
vpnd [WA] Received SIGHUP; restarting...
```

### Solution

1. Perform device restart via Web UI
2. If persistent, contact after-sales

---

## Problem 2: Runtime state persistence failure

```
vpnd [ER] cannot dump running state to <file path>, we will not be able to recover in case of a fatal error!
vpnd [WA] failed to save/load global data / service data
```

### Solution

1. Re-deliver VPN config (L2TP server/client, OpenVPN) via Web UI / cloud platform
2. Perform device restart via Web UI

---

## Problem 3: L2TP config file operation failure / Remote IP anomaly

```
vpnd [ER] Unable to create l2tp config/secrets/chap-secrets/pap-secrets file
vpnd [ER] Unable to open l2tp config/control file / Unable to write secrets file
vpnd [ER] Remote IP address(<IP>) no range. / conflict.
```

### Solution

1. Check L2TP server PPP address pool (start_ip ~ end_ip) range via Web UI
2. Re-save L2TP config via Web UI
3. Perform device restart via Web UI

---

## Problem 4: OpenVPN config file operation failure / Cloud Connect config anomaly

```
vpnd [ER] Unable to open openvpn config file
vpnd [ER] Unable to find openvpn instance <name> classmode <mode>
vpnd [ER] invalid openvpn connector config / modify connector openvpn config format failed
```

### Solution

1. Re-save OpenVPN client/server config via Web UI
2. Re-deliver Cloud Connect OpenVPN config via cloud platform
3. Perform device restart via Web UI

---

## Problem 5: IPC broadcast / DM channel info send failure

```
vpnd [ER] broadcast msg is not ok.
vpnd [ER] openvpn broadcast destroy/create tunnel err
vpnd [ER] openvpn up/down broadcast msg is not ok.
vpnd [ER] ipsec send channel info of tunnel <N> failed, ret <error code>
```

### Solution

1. Perform device restart via Web UI
2. Check related services are running normally

---

## Problem 6: OpenVPN tunnel IP address conflict / Cloud Connect OpenVPN anomaly

```
vpnd [ER] openvpn tunnel ip conflict
vpnd [ER] openvpn tunnel ip conflict, destroy openvpn
```

### Solution

1. Modify OpenVPN config virtual IP via Web UI; ensure each instance is unique and doesn't conflict with other device interfaces
2. If IP Passthrough is simultaneously in use, check IP assignment ranges on both sides
3. Re-save OpenVPN config via Web UI

---

## Problem 7: JSON cloud config parse error

```
vpnd [ER] request json is NULL
vpnd [ER] static config loads json error,<line>:<error description>
vpnd [ER] decrypt passwd failed / password length is invalid
vpnd [ER] tunnel_auth_obj get error
vpnd [ER] NOT found key l2tp name / <function>(<line>):add client failed, tunnels are full.
vpnd [ER] broadcast msg is not ok.
vpnd [ER] failed to pack json payload/resp for l2tp status / failed to dump json to string
vpnd [ER] popen failed in get_throughput_delta on <interface>.
```

### Solution

1. Check delivered JSON config format via cloud platform
2. Ensure each L2TP client has a unique `name` field
3. Re-set PPP password and Tunnel auth password via Web UI
4. Delete unnecessary L2TP clients to free capacity
5. Re-save L2TP config via Web UI

---

## Normal INFO Logs (No Action Needed)

```
vpnd [IN] reset to default config
vpnd [IN] Received SIGUSR1; start/stop tracing / MSG: 0x<type> from service <ID>
vpnd [IN] child xl2tpd/l2tpv3 exited! / openvpn client<N>/server exited!
vpnd [IN] Interface Virtual-PPP<N>, changed state to up/down
vpnd [IN] stop/start l2tpv3d / start openvpn / update openvpn tunnels
vpnd [IN] openvpnd receive cert info / l2tp receive ipsec info
vpnd [IN] cloud connect openvpn up/down...
vpnd [IN] verify l2tpc<N> config/pw class config failed
vpnd [IN] openvpn user verify OK/failed
vpnd [IN] ppp remote ipaddress verify OK/failed
vpnd [IN] clear l2tp clients / connector's openvpn [enabled/disabled]
vpnd [IN] add/del route to client <subnet> <mask> dev <device>
```
