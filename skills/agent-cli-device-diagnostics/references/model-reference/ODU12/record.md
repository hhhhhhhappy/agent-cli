# record — Problem Diagnosis

> Applicable: record (traffic recording/reporting) service data collection failure (traffic stats, device online/offline, signal history, link quality), SQLite database anomaly, cloud data report JSON packaging failure, config file read error, Wi-Fi client/WAN status fetch failure.

## Log Format Reference

| Level | Meaning | Requires Attention |
|-------|---------|-------------------|
| [ER] | ERROR | Yes |
| [WA] | WARNING | Yes |
| [IN] | INFO | For reference only |

> Note: record service log prefix is `ih_record` (`#define IDENT "ih_record"` in code).

---

## Problem 1: SQLite database anomaly

### Matching Logs

```
ih_record [ER] Can't open database:<db path>, error:<SQLite error>
ih_record [ER] sqlite3_prepare_v2 error
ih_record [ER] sqlite3_step insert2 error, rc=<return code>
ih_record [WA] table <table name> schema changed, drop it.
```

### Solution

1. Perform device restart via Web UI
2. If persistent, upgrade firmware via Web UI
3. Contact after-sales to check storage hardware

---

## Problem 2: Memory allocation failure

```
ih_record [ER] allocate memory failed, error(<errno>), reason:<description>
ih_record [ER] allocate wan/lqm memory failed / malloc failed
```

### Solution

1. Perform device restart via Web UI
2. Reduce the number of simultaneously online devices

---

## Problem 3: Data compression failure

```
ih_record [ER] status compress failed, ret[<return value>]
ih_record [ER] compress/my_compress failed, ret[<return value>]
```

---

## Problem 4: JSON data packaging/serialization failure

```
ih_record [ER] json_dumps failed / failed to pack json payload for <data category>
ih_record [ER] failed to dump json to string / prepare paload object failed
ih_record [ER] parepare wan/lan/location paload error / package wan/wifi_sta/lan/location info error
ih_record [ER] client events data too large / getting vif failed
```

---

## Problem 5: System file/command execution failure

```
ih_record [ER] Invalid parameters / Failed to open /proc/net/dev
ih_record [ER] popen failed / fgets failed
ih_record [ER] exec <command> failed![<errno>:<description>]
```

---

## Problem 6: DHCP Lease / FDB table read error

```
ih_record [WA] dnsmasq.lease table now more than / is more than <max>
ih_record [ER] file_encoding_convert failed
ih_record [ER] can't open br-lan fdb file to add fdb table
```

### Solution

1. Reduce DHCP address pool size or upgrade device
2. Perform device restart via Web UI

---

## Problem 7-11: Wi-Fi/AP, CTIOT, Time skew, Client list too large, JSON cloud config

Refer to original full documentation for problems 7 through 11.

---

## Normal INFO Logs (No Action Needed)

```
ih_record [IN] name:<name>, iface:<interface name>
ih_record [IN] init iptable rules...
ih_record [IN] handle wan/sta status change of <interface name>
ih_record [IN] wired/wireless clients <MAC> connected / disconnected
ih_record [IN] current location : [<location info>]
```
