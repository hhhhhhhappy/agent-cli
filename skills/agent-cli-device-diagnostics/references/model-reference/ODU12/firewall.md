# firewall — Problem Diagnosis

> Applicable: firewall service self-anomaly (signal handling failure, fork failure, runtime state persistence failure), iptables rules not effective (VIF interface name mapping failure), IP ACL filter/NAT/port mapping/MAC filter/domain filter/policy routing/QoS/remote access config errors, TCP MSS limitation issue, cloud JSON config parse errors.

## Log Format Reference

| Level | Meaning | Requires Attention |
|-------|---------|-------------------|
| [ER] | ERROR | Yes |
| [WA] | WARNING | Yes |
| [IN] | INFO | For reference only |

> Note: firewall service log prefix is `firewall` (`#define IDENT "firewall"` in code).

---

## Problem 1: Firewall service signal handler registration failure / abnormal exit

### Matching Logs

```
firewall [ER] cannot add handle for SIGHUP
firewall [ER] cannot add handle for SIGUSR1
firewall [ER] cannot add handle for SIGCHLD
firewall [ER] cannot add handle for SIGTERM
firewall [ER] cannot add handle for SIGINT
firewall [ER] cannot add handle for SIGALRM
firewall [ER] Received <signal name>; quitting...
firewall [ER] Restart FAILED
```

### Diagnosis

firewall service failed to register handler functions for critical signals at startup, received a termination signal and is exiting, or restart failed. This causes iptables rule management to stop completely and network access control to fail.

### Cause

1. Insufficient system resources (file descriptor exhaustion, low memory)
2. libevent event library initialization anomaly
3. firewall internal state anomaly causing restart failure

### Solution

1. Perform device restart via Web UI
2. If it persists, contact after-sales

---

## Problem 2: Cloud rule queue anomaly / fork failure

### Matching Logs

```
firewall [ER] cloud rule queue is full
firewall [ER] <function name>(<line>):malloc failed
firewall [ER] [<function name>] cloud rule queue is empty
firewall [ER] fork failed
firewall [ER] Couldn't create evdns_base
```

### Diagnosis

Cloud rule queue full or empty, memory allocation failure, fork subprocess failure, libevent DNS base structure creation failure. All these will cause cloud-delivered firewall rules (ACL/NAT/QoS, etc.) to not take effect.

### Cause

1. Cloud delivered too many rules in a single batch exceeding queue capacity
2. Insufficient system memory
3. Process count reached limit, fork failed
4. libevent or DNS library initialization anomaly

### Solution

1. Reduce the number of rules delivered per batch via cloud platform, batch operations
2. Perform device restart via Web UI
3. If evdns_base continues to fail, contact after-sales

---

## Problem 3: VIF interface name mapping failure

### Matching Logs

```
firewall [ER] Can't get vif name map for IF_INFO (<type>, <number>, <number>)
firewall [ER] Can't get vif by type <type>, port <port>
firewall [ER] [<function name>]get_if_info_from_panel_name failed
firewall [ER] [<function name>]vif_get_sys_name failed
firewall [ER] [<function name>]get_vif_by_if_info failed
firewall [ER] get lan vif error
firewall [ER] get ip address failed
firewall [ER] get ipv4 address failed
firewall [ER] mgmt table is null!
```

### Diagnosis

firewall cannot obtain VIF interface name mapping or interface info when generating iptables rules. This is the most common error in the firewall module, meaning iptables rules for the corresponding interface cannot be correctly generated, and ACL/NAT/port mapping rules for that interface will not take effect.

### Cause

1. The interface (IF_INFO type/port) referenced in config does not exist in the current system
2. interface service not yet ready or crashed
3. Interface not yet created (first config or not fully initialized after restart)
4. Management port table (mgmt table) not initialized

### Solution

1. Check via Web UI that interfaces referenced in firewall rules are valid and correctly configured
2. Ensure interface service is running normally
3. Re-save firewall config via Web UI
4. Perform device restart via Web UI

---

## Problem 4: Cloud domain/IPSet file operation failure

### Matching Logs

```
firewall [ER] cloud_domain is NULL in callback
firewall [ER] cloud domains are over than 256, can't add more!
firewall [ER] [<function name>]malloc CLOUD_DOMAIN_NODE failed, <errno>:<error description>
firewall [ER] [<function name>]fopen <file> failed, <errno>:<error description>
firewall [ER] failed to open <file>, <errno>:<error description>
```

### Diagnosis

firewall encountered errors when processing cloud-delivered domain rules or ipset files: domain count exceeded limit (256), memory allocation failure, cannot open ipset config file.

### Cause

1. Cloud platform delivered too many domains in a single batch (exceeding 256)
2. Insufficient system memory
3. ipset config file (e.g., `/etc/dnsmasq.cloud.ipset`) does not exist or is not writable
4. Filesystem space insufficient

### Solution

1. Reduce the number of domains delivered via cloud platform
2. Perform device restart via Web UI
3. If ipset file is frequently unwritable, contact after-sales to check filesystem

---

## Problem 5: Runtime state persistence failure

### Matching Logs

```
firewall [ER] cannot dump running state to <file path>, we will not be able to recover in case of a fatal error!
firewall [WA] failed to save global data
firewall [WA] failed to save global data for <NAT/tcp mss/IP ACL>
firewall [WA] failed to load global data for <NAT/IP ACL/tcp mss>
firewall [WA] failed to load data of IP ACL
firewall [WA] failed to insert/append IP ACL while loading state
firewall [WA] failed to load data of filter interface
firewall [WA] failed to load global data for NAT interface
firewall [WA] failed to append NAT rule while loading state
firewall [WA] failed to load tcp mss value for interface
firewall [WA] failed to set tcp mss for interface
```

### Diagnosis

firewall cannot write runtime state (ACL rules, NAT rules, TCP MSS config, etc.) to the persistence file, or cannot recover from the file. After restart, firewall rules may be lost or inconsistent.

### Cause

1. `/var/run/` partition space insufficient or read-only
2. Abnormal power loss causing state file corruption
3. Rule data structures in state file incompatible with current code version
4. Filesystem fault

### Solution

1. Re-deliver firewall rules via Web UI / cloud platform
2. Perform device restart via Web UI
3. If frequent, contact after-sales

---

## Problem 6: TCP MSS value anomaly

### Matching Logs

```
firewall [ER] cannot alloc memory for mss
firewall [ER] tcpmss <value> is too small
```

### Diagnosis

TCP MSS (Maximum Segment Size) value configured too small, or memory allocation failure.

### Cause

1. Configured TCP MSS value is less than the minimum legal value
2. Insufficient memory

### Solution

1. Adjust TCP MSS value to legal range via Web UI (recommended >= 500)

---

## Problem 7: QoS config file/classifier/policy issues

### Matching Logs

```
firewall [ER] Can not open <QoS config file>
firewall [ER] Not enougth memory
firewall [ER] Bad interface default max-bandwidth
firewall [ER] Classifier <name> is not defined
firewall [ER] Lack of view infomation
firewall [ER] Can not find classifier <name>
firewall [ER] Can not find policy <name>
firewall [WA] failed to save/load classifiers/policys/interface/policy entries data
```

### Diagnosis

QoS module cannot open config file, referenced undefined classifier or policy, interface default bandwidth value invalid, QoS state data save/load failed.

### Cause

1. QoS config file (e.g., `/etc/qos.conf`) does not exist or was deleted
2. Classifier or policy referenced in config but not defined
3. Interface maximum bandwidth configured as 0 or invalid
4. Insufficient memory
5. State data corruption

### Solution

1. Check via Web UI that QoS config's classifiers and policies are completely defined
2. Ensure referenced classifier/policy names exist in config
3. Check that interface bandwidth config values are valid
4. Re-save QoS config via Web UI

---

## Problem 8: Policy routing config issues

### Matching Logs

```
firewall [ER] policy route table is full
firewall [ER] failed to open <policy route ipset file>, <errno>:<error description>
firewall [ER] get policy route table id failed!
firewall [WA] failed to save/load global data
firewall [WA] Failed to update policy route, reload all rules.
```

### Diagnosis

Policy routing table full, cannot open ipset config file, cannot get routing table ID, policy routing rule load failure.

### Cause

1. Policy route entry count exceeds device limit
2. Policy route ipset config file inaccessible
3. Routing table ID allocation failed
4. Policy route config data save/load failed

### Solution

1. Delete unnecessary policy route rules
2. Re-save policy route config via Web UI
3. Re-deliver rules one by one via cloud platform

---

## Problem 9: NAT rule errors (bad new_vif / bad VIF DOWN)

### Matching Logs

```
firewall [ER] bad new_vif
firewall [WA] bad VIF DOWN event
firewall [ER] dump/load nat rule state failed
```

### Diagnosis

NAT module received invalid VIF info when processing VIF interface change events.

### Cause

1. VIF interface info was corrupted during transmission
2. Interface status change event timing anomaly

### Solution

1. Re-save NAT config via Web UI
2. Perform device restart via Web UI

---

## Problem 10: JSON config parse errors (Category)

The following logs come from various cloud web sub-modules (`fw_acl_cloud_web`, `fw_portmap_cloud_web`, `fw_macfilter_cloud_web`, `fw_domain_filter_cloud_web`, `fw_nat_cloud_web`, `fw_remote_access`, `fw_policy_route`, `fw_qos_new`).

### ACL (Access Control List)

```
firewall [ER] request json is NULL
firewall [ER] ipsec loads json error,<line>:<error description>
firewall [ER] failed to open <ACL_IPSET_FILE>, <errno>:<error description>
firewall [WA] failed to save/load global acl data
firewall [WA] failed to save/load acl inbound/outbound rule data
```

### Port Mapping

```
firewall [ER] request json is NULL
firewall [ER] ipsec loads json error,<line>:<error description>
firewall [ER] [<function name>] malloc failed
firewall [WA] failed to save/load global portmap data
firewall [WA] failed to save/load portmap rule data
```

### MAC Filter

```
firewall [ER] request json is NULL
firewall [ER] mac loads json error,<line>:<error description>
firewall [ER] invalid mac address <MAC address>
firewall [ER] [<function name>] malloc failed
firewall [WA] failed to save/load global mac filter data
firewall [WA] failed to save/load mac filter rule data
```

### Domain Filter

```
firewall [ER] request json is NULL
firewall [ER] domain loads json error,<line>:<error description>
firewall [ER] failed to create <DOMAIN_FILTER_IPSET_FILE>, <errno>:<error description>
firewall [ER] domain filter rule is NULL in dns_resolve/callback
firewall [ER] domain [<domain>] resolve times over than <max>, giving up!
firewall [ER] failed to open <DOMAIN_FILTER_IPSET_FILE>, <errno>:<error description>
firewall [ER] malloc failed
firewall [ER] invalid domain
firewall [ER] error domain filter mode, <value>
firewall [WA] failed to save/load global domain filter data
firewall [WA] failed to save/load domain filter rule data
```

### NAT

```
firewall [ER] nat root is not object/array
firewall [ER] request json is NULL
firewall [ER] nat loads json error,<line>:<error description>
firewall [ER] nat rule protocol/action/source/destination is illegal
firewall [ER] the sequence number is illegal
firewall [ER] the type is illegal
firewall [ER] sequence/name/uuid conflict
firewall [ER] malloc failed
firewall [ER] set nat rule failed
```

### Policy Route

```
firewall [ER] request json is NULL
firewall [ER] policy_route loads json error,<line>:<error description>
firewall [ER] <error message>
```

### QoS (New)

```
firewall [ER] request json is NULL
firewall [ER] qos loads json error,<line>:<error description>
firewall [ER] get iface info error, iface_name:<interface name>
```

### Remote Access

```
firewall [ER] request json is NULL
firewall [ER] admin access loads json error,<line>:<error description>
firewall [WA] failed to save global remote access data
firewall [WA] failed to load global portmap data
```

### Diagnosis

When cloud delivers firewall config via JSON, the JSON format is invalid, field values are invalid, rules conflict, or config data save/load failed.

### Cause

- **JSON format error**: Cloud-delivered config is invalid
- **Invalid interface name**: Interface referenced in config does not exist on device
- **Illegal fields**: protocol/action/type/sequence values not in allowed range
- **Rule conflict**: UUID conflict, sequence number conflict, name conflict, domain conflict, MAC address conflict
- **ipset file error**: Cannot open or create ipset config file
- **DNS resolution failure**: Domain filter rule's domain resolution timeout (exceeded retry limit)
- **Invalid MAC address**: MAC address format error
- **Insufficient memory**: malloc failed
- **Rule count exceeded**: ACL/port mapping/MAC filter/NAT rules full

### Solution (applicable to all sub-modules above)

1. Check via cloud platform that delivered JSON config format and field validity are correct
2. Ensure interface names referenced in config match actual device interface names
3. Check that enum field values (protocol/action/type, etc.) are valid
4. Check whether sequence numbers/UUID/names conflict with existing rules
5. Reduce rule count, delete unnecessary rules
6. Ensure MAC address format is correct (e.g., `AA:BB:CC:DD:EE:FF`)
7. Domains in domain filter rules must be valid FQDN
8. Re-deliver rules one by one via cloud platform
9. Perform device restart via Web UI

---

## Problem 11: NAT rule config validity check failure

### Matching Logs

```
firewall [ER] nat rule protocol is illegal, rule uuid=<UUID>
firewall [ER] nat rule action is illegal, rule uuid=<UUID>
firewall [ER] the source is illegal
firewall [ER] the destination is illegal
firewall [ER] the source and destination is illegal
firewall [ER] the translation is illegal
firewall [ER] the source port is illegal
firewall [ER] the destination port is illegal
firewall [ER] the translation port is illegal
firewall [ER] the type is illegal
firewall [ER] the sequence number is illegal
firewall [ER] sequence conflict, rule uuid=<UUID>
firewall [ER] name conflict, rule uuid=<UUID>, conf uuid=<UUID>
firewall [ER] uuid conflict, rule uuid=<UUID>
```

### Diagnosis

Cloud-delivered NAT rule has invalid field values or rule conflicts.

### Solution

1. Check via cloud platform that all NAT rule field values are valid
2. Ensure no conflicts with existing rules (rename or modify UUID)
3. Delete conflicting rules then re-deliver via cloud platform

---

## Normal INFO Logs (No Action Needed)

```
firewall [IN] updated acl rules / policy route rules / portmap rules / mac filter rules / domain filter rules
firewall [IN] clear conntrack
firewall [IN] reset to default config
firewall [IN] MSG: 0x<type> from service <ID>
firewall [IN] Received SIGALRM, send timer reset to config_proc
firewall [IN] add/del/modify acl/nat/portmap/macfilter/domainfilter rule
firewall [IN] flush portmap/acl/macfilter/domainfilter/remote access rule
firewall [IN] enable remote access rule / set remote/local access rule / set ippt remote access rule
firewall [IN] get uplink interface's vif_info failed
firewall [IN] ACL Filter apply
firewall [IN] Send ACL MSG to SVC<ID>, ACL number = <number>
firewall [IN] type [<type>] updates firewall rules finished
firewall [IN] iptables -t nat ...
firewall [IN] acl info has reached the maximum
firewall [IN] macfilter/portmap/domainfilter rule has reached the maximum
```

---

## General Troubleshooting Information Collection

1. All `firewall [ER]` and `firewall [WA]` lines in device logs
2. Complete logs for 2 minutes before and after the fault
3. Current firewall config summary (ACL rule count, NAT rules, port mapping, MAC filter, domain filter, policy routing, QoS, remote access config)
4. Whether there were config changes at or before the fault time (Web UI / cloud delivery)
5. Impact scope description (which traffic was incorrectly blocked or allowed)
