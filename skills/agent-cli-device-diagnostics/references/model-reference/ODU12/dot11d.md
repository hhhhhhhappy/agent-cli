# dot11d — Problem Diagnosis

> Applicable: dot11d (Wi-Fi management) service self-anomaly (signal handling failure, runtime state persistence failure, restart failure), Wi-Fi driver/hardware anomaly (popen/fopen driver config failure, E2P verification failure, test mode residual, MAC address invalid causing auto-restart after 30 seconds), WLAN config UCI/Profile file operation failure, memory allocation failure, IPC broadcast failure, Wi-Fi config logic error (backup_if out of bounds, IP Passthrough execution failure, SSID interface conflict, AP/STA mode constraints, IP address conflict), sysrepo config sync anomaly, cloud JSON config error.

## Log Format Reference

| Level | Meaning | Requires Attention |
|-------|---------|-------------------|
| [ER] | ERROR | Yes |
| [WA] | WARNING | Yes |
| [IN] | INFO | For reference only |

> Note: dot11d service log prefix is `dot11d`. This service manages Wi-Fi 2.4G/5G dual-band (MediaTek MT7915/MT7663/MT7603 chipsets), supports AP/STA/AP-Client multi-mode, Multi-SSID, WPA/WPA2/WPA3 security configuration, interacts with the underlying Wi-Fi driver via UCI (Unified Configuration Interface), and syncs config changes via sysrepo.

---

## Problem 1: Signal handler registration failure / termination signal exit / restart failure

### Matching Logs

```
dot11d [ER] cannot add handle for SIGHUP
dot11d [ER] cannot add handle for SIGUSR1
dot11d [ER] cannot add handle for SIGCHLD
dot11d [ER] cannot add handle for SIGTERM
dot11d [ER] cannot add handle for SIGINT
dot11d [ER] Received <signal name>; quitting...
dot11d [ER] Restart FAILED
dot11d [WA] Received SIGHUP; restarting...
```

### Diagnosis

dot11d service failed to register signal handlers at startup, or received a termination signal and exited, or SIGHUP hot restart's `execv` failed. SIGCHLD handler registration failure will prevent detecting DHCP Client subprocess exits.

### Cause

1. Insufficient system resources, libevent signal event addition failed
2. Executable file path changed or permission anomaly, `execv` call failed

### Solution

1. Perform device restart via Web UI
2. If it persists, contact after-sales

---

## Problem 2: Runtime state persistence failure

### Matching Logs

```
dot11d [ER] cannot dump running state to <file path>, we will not be able to recover in case of a fatal error!
dot11d [WA] failed to save global data
dot11d [WA] failed to save service data
dot11d [WA] failed to load global data
dot11d [WA] failed to load service data
```

### Diagnosis

dot11d service cannot write/read runtime state to/from the persistence file `/var/run/dot11d<ID>.state`. If write fails, Wi-Fi config and state cannot be recovered after a service crash.

### Cause

1. `/var/run/` partition space insufficient or became read-only
2. Filesystem anomaly

### Solution

1. Re-save Wi-Fi config via Web UI
2. Perform device restart via Web UI

---

## Problem 3: Wi-Fi driver/hardware operation anomaly

### Matching Logs

```
dot11d [ER] popen <command> fail!
dot11d [ER] fopen <WLAN profile path> fail!(<errno>:<description>)
dot11d [ER] fopen <file> err.(<description>)
dot11d [ER] check wifi e2p fail!
dot11d [ER] check wifi test mode fail!
dot11d [ER] bad mac address <variable>=<invalid MAC>
dot11d [ER] bad mac address 0x<offset> <invalid MAC>
dot11d [ER] 2.4G Wi-Fi mac(<MAC address>) is invalid, restart system after 30 seconds.
```

### Diagnosis

dot11d encountered issues when operating the Wi-Fi driver:

| Log | Meaning |
|-----|---------|
| `popen ... fail!` | Executing `iwpriv`/`iwconfig`/`mtk_factory_rw.sh` or other Wi-Fi driver commands failed |
| `fopen wlan profile fail!` | Cannot open MediaTek Wi-Fi driver config file (MT7663/MT7603 profile) |
| `check wifi e2p fail!` | **ODU12 specific**: Wi-Fi E2P (EEPROM) verification failed, calibration data anomaly |
| `check wifi test mode fail!` | **ODU12 specific**: Wi-Fi chip is still in factory test mode |
| `bad mac address` | Wi-Fi MAC address read from bootenv/E2P has invalid format |
| `MAC is invalid, restart system` | 2.4G Wi-Fi interface MAC address is `00:00:00:*`, **device will auto-restart after 30 seconds** |

### Cause

1. Wi-Fi driver kernel module (mt7915/mt7663/mt7603) not loaded or loading failed
2. Wi-Fi E2P calibration data corrupted (may be caused by abnormal power loss)
3. Wi-Fi chip did not exit factory test mode
4. Wi-Fi MAC address in bootenv not burned or has format error
5. Wi-Fi chip hardware fault

### Solution

1. Perform device restart via Web UI
2. If `E2P fail` / `test mode fail` occurs repeatedly, contact after-sales (may need to re-burn Wi-Fi calibration data)
3. If MAC address invalid occurs repeatedly, contact after-sales to check hardware

---

## Problem 4: WLAN config UCI / Profile file operation failure

### Matching Logs

```
dot11d [ER] uci set failed, config or section or option is null
dot11d [ER] uci set failed, alloc error
dot11d [ER] uci set failed, value is null
dot11d [ER] open wlan config file <file path> err
dot11d [ER] fopen <profile path> fail!(<errno>:<description>)
dot11d [ER] cannot open <UCI_TMP_FILE>
```

### Diagnosis

dot11d failed when writing Wi-Fi config files (hostapd/wpa_supplicant's `/etc/config/wireless`) via UCI or directly operating profile files. UCI operation failure may be due to null pointers for config/section/option/value or memory allocation failure.

### Cause

1. The corresponding section or option does not exist in the UCI config tree
2. Insufficient system memory (`malloc` failure)
3. Directory where Wi-Fi config files reside does not exist or is read-only
4. UCI backend file corruption

### Solution

1. Re-save Wi-Fi config via Web UI
2. Perform device restart via Web UI
3. If it persists, contact after-sales

---

## Problem 5: Memory allocation failure

### Matching Logs

```
dot11d [ER] allocate memory failed, error(<errno>), reason:<description>
```

### Diagnosis

`malloc` memory allocation failed during Wi-Fi driver config generation (mt_cfg.c). May cause incomplete Wi-Fi config, with some SSID or radio configs lost.

### Cause

1. Insufficient system available memory
2. Too many Multi-SSIDs configured, exceeding memory requirements

### Solution

1. Perform device restart via Web UI
2. Reduce Multi-SSID count (delete unnecessary extra SSID configs)
3. If it persists, contact after-sales

---

## Problem 6: IPC broadcast failure

### Matching Logs

```
dot11d [ER] broadcast msg is not ok.
dot11d [ER] broadcast wlan interface status msg is not ok.
dot11d [ER] broadcast wlan ap interface status msg is not ok.
dot11d [ER] broadcast wlan sta interface status msg is not ok.
```

### Diagnosis

When Wi-Fi interface UP/DOWN/CREATE/DESTROY status changes occur, dot11d failed to broadcast VIF status changes to other services (interface, bridge, routed, etc.) via IPC or failed to notify sysrepo of WLAN status. This prevents other services from timely sensing Wi-Fi interface changes.

### Cause

1. Target service not ready or crashed
2. IPC message queue full

### Solution

1. Perform device restart via Web UI
2. If it persists, contact after-sales

---

## Problem 7: Wi-Fi config logic errors

### Matching Logs

```
dot11d [ER] do ip passthrough failed
dot11d [ER] wifi backup_if index(<index>) is out of range, ignore
dot11d [ER] wlan ap config interface is invaild!
dot11d [ER] wlan sta config interface is invalid!
dot11d [ER] sta config only support in primary ssid
dot11d [ER] wlan interface <name> conflict with [<old UUID>]:[<new UUID>]
dot11d [ER] ip address conflicts to other interface
dot11d [ER] failed to send bridge request, opertaion is <Add/Del>
```

### Diagnosis

dot11d encountered constraint conflicts or resource shortages when processing Wi-Fi config logic:

| Log | Meaning |
|-----|---------|
| `do ip passthrough failed` | IP Passthrough functionality co-execution with Wi-Fi config failed |
| `backup_if index out of range` | Wi-Fi backup interface index exceeded legal range (0~3) |
| `ap/sta config interface is invalid` | Configured interface is not a valid WLAN interface |
| `sta config only support in primary ssid` | STA mode is only allowed on the primary SSID |
| `wlan interface conflict` | Newly configured WLAN interface name conflicts with existing config |
| `ip address conflicts` | Configured static IP conflicts with other device interface IPs |
| `failed to send bridge request` | Sending bridge add/delete request to bridge service failed |
| WiFi reloading failed | Wi-Fi config reload failed (e.g., 2.4G AP + 5G STA configured simultaneously causing dual STA conflict) |

### Cause

1. IP Passthrough's interface service execution failed
2. backup_if config value exceeds 0~3 range
3. Non-WLAN interface (e.g., GE/SVI port) configured as WLAN AP/STA
4. Non-primary SSID incorrectly configured as STA mode in multi-SSID scenario
5. Multi-SSID interface UUID conflicts with existing config
6. Static IP subnet overlaps with LAN/WAN/VLAN interface IP networks
7. bridge service not ready

### Solution

1. Check via Web UI that Wi-Fi config's backup_if index is correct (0~3)
2. Confirm STA mode is only enabled on primary SSID
3. Check that Multi-SSID interface names are unique
4. Modify static IP so it does not conflict with other device interfaces
5. Avoid configuring both 2.4G and 5G as STA mode simultaneously
6. Re-save Wi-Fi config via Web UI

---

## Problem 8: Sysrepo config sync anomaly

### Matching Logs

```
dot11d [ER] Getting changes iter failed (<error description>).
dot11d [ER] Find path error
dot11d [IN] can't find the wlan config storage location
dot11d [IN] Multiple SSIDs only support AP mode!!!
dot11d [IN] Another band is already in STA mode!!!
```

### Diagnosis

dot11d encountered errors when syncing Wi-Fi config changes with NETCONF/YANG data store via sysrepo.

### Cause

1. sysrepo service (sysrepod) not running or connection disconnected
2. WLAN config node missing from YANG data model
3. Multi-SSID + STA mode configured (Multi-SSID only supports AP)
4. 2.4G and 5G both configured as STA mode (hardware limitation)

### Solution

1. Re-save Wi-Fi config via Web UI (will trigger sysrepo re-sync)
2. Change Multi-SSID config to AP mode; STA mode only on primary SSID
3. Ensure only one band uses STA mode
4. Perform device restart via Web UI

---

## Problem 9: JSON cloud config parse errors

> The following logs come from the JSON processing path when the cloud platform/Web UI delivers WLAN config (AP/STA config + status query in `dot11_cloud_web.c`).

### 9.1 JSON request body is empty

```
dot11d [ER] request json is NULL
```

### 9.2 JSON parse format error

```
dot11d [ER] wlan loads json error,<line>:<error description>
dot11d [ER] %s
```

> `%s` log is the generic output of JSON node validation error messages.

### 9.3 AP config validation error

```
dot11d [ER] get wlan_ap config failed
dot11d [ER] wlan ap config interface is invaild!
dot11d [ER] wlan interface <name> conflict with [<old UUID>]:[<new UUID>]
dot11d [ER] broadcast wlan ap interface status msg is not ok.
```

### 9.4 STA config validation error

```
dot11d [ER] wlan sta config interface is invalid!
dot11d [ER] sta config only support in primary ssid
dot11d [ER] ip address conflicts to other interface
dot11d [ER] broadcast wlan sta interface status msg is not ok.
```

### 9.5 Bridge request failure

```
dot11d [ER] failed to send bridge request, opertaion is <Add/Del>
```

### 9.6 Status query JSON serialization failure

```
dot11d [ER] failed to pack json payload for wlan status
dot11d [ER] failed to dump json to string
```

### Diagnosis

Errors when cloud or Web UI delivers WLAN AP/STA config: JSON empty or format invalid, AP config object empty, interface name invalid, interface UUID conflict, STA mode configured outside primary SSID, static IP conflict with other interfaces, bridge operation IPC failure, status query JSON serialization failure.

### Cause

1. Cloud-delivered config JSON is empty or contains syntax errors
2. AP config sub-object is null
3. `interface` field specified is not a valid WLAN interface
4. Multi-SSID AP UUID conflicts with existing config
5. STA mode configured on non-primary SSID (sid ≠ 0)
6. `static_ip` subnet overlaps with other device interface IP networks
7. bridge service not ready

### Solution (applicable to all above)

1. Check via cloud platform that the delivered JSON config format is correct
2. Ensure AP config interface name is a valid WLAN interface (e.g., Wlan1, Wlan2)
3. STA mode only configured on primary SSID
4. Modify static_ip so it does not conflict with other device interfaces
5. Re-save Wi-Fi config via Web UI

---

## Normal INFO Logs (No Action Needed)

The following logs indicate the dot11d service is running normally. Do not diagnose as problems:

```
dot11d [IN] reset to default config
dot11d [IN] MSG: 0x<message type> from service <service ID>
dot11d [IN]     Len: <message length>
dot11d [IN]     Content: <message content>
dot11d [IN] Received SIGUSR1; <start/stop> tracing to <trace file path>
dot11d [IN] restart timer config...... / started
dot11d [IN] dot11 sys work mode update [<old mode> -> <new mode>]
dot11d [IN] wlan 2g connect to ssid <SSID>, channel <channel>
dot11d [IN] wlan 5g connect to ssid <SSID>, channel <channel>
dot11d [IN] Interface Wlan<N>, changed state to up, iface <interface name>
dot11d [IN] Interface Wlan<N>, changed state to down, iface <interface name>
dot11d [IN] Wi-Fi reloading end.
dot11d [IN] Wi-Fi reloading failed! after <N> seconds try again.
dot11d [IN] DHCP Client for dot11radio<N> exit
dot11d [IN] generate WLAN AP config / generate WLAN STA config
dot11d [IN] init wlan config
dot11d [IN] Clearing ip for dot11 radio interface <interface name>
dot11d [IN] start dhcp wlan mac <MAC>
dot11d [IN] dot11 send request for add <interface> to wan / vlan <VLAN_ID>
dot11d [IN] SSID[<SSID>] guest [<status>]
dot11d [IN] dhcp get wlan mac addr <MAC>
dot11d [IN] RENEW:IP address getting from dhcp server conflicts to other interface
dot11d [IN] BOUND:IP address getting from dhcp server conflicts to other interface
dot11d [IN] cannot open wlan profile err
dot11d [IN] open wlan ap/sta profile <file> err:<description>(<errno>)
dot11d [IN] Cann't get wan/vlan ifname!
dot11d [IN] Multiple SSIDs only support AP mode
dot11d [IN] Another band is already in STA mode!!!
dot11d [IN] The dot11radio interface is null / config is null
dot11d [IN] enter wlan config interface <type> <slot> <port>
dot11d [IN] add/modify/delete ap/sta config
dot11d [IN] init dot11 sysrepo
```

---

## General Troubleshooting Information Collection

If dot11d related issues cannot be located via the sections above, please collect the following information:

1. All `dot11d [ER]` and `dot11d [WA]` lines in device logs
2. Complete logs for 2 minutes before and after the fault
3. Current Wi-Fi config (2.4G/5G operating mode, AP/STA mode, SSID, security type, channel, Multi-SSID list, VLAN binding, static IP)
4. Wi-Fi interface status (VIF UP/DOWN)
5. Whether Wi-Fi driver modules are loaded (mt7915/mt7663/mt7603)
6. Device model Wi-Fi hardware type (Does ODU12 use MT7915? Or another?)
7. Whether there were Wi-Fi config changes, channel switches, or WAN interface status changes at or before the fault time
