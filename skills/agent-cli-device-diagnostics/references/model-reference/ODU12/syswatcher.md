# syswatcher — Problem Diagnosis

> Applicable: syswatcher (system watchdog daemon) self-anomaly (signal handling failure, insufficient memory), managed services (various IPC sub-services) startup failure/heartbeat timeout/abnormal exit, startup config load failure, mass interface DOWN events triggering reboot, filesystem read-only recovery failure, cloud system config JSON parse error.

## Log Format Reference

| Level | Meaning | Requires Attention |
|-------|---------|-------------------|
| [ER] | ERROR | Yes |
| [WA] | WARNING | Yes |
| [IN] | INFO | For reference only |

---

## Problem 1: Mass IPC_EVENT_DOWN triggering system reboot

```
syswatcher [ER] Mass IPC_EVENT_DOWN detected! <N> events in <window> seconds, scheduling system reboot in <delay> seconds
```

### Diagnosis

syswatcher detected too many interface DOWN events within the detection window, determining mass interfaces are abnormally disconnected. Device will auto-restart.

### Solution

1. Check physical network connections
2. If device restores after reboot, normal self-healing behavior
3. If frequent, check modem signal quality and SIM card status
4. Upgrade to latest firmware via Web UI

---

## Problem 2: Critical service multiple exits triggering system reboot

```
syswatcher [ER] service <service name> (<service ID>) is exited!
syswatcher [IN] service <service name> will be restarted in <delay> seconds!
syswatcher [ALERT] Critical service <name> has restart <N> times, reboot system now!
```

---

## Problem 3: interface service multiple heartbeat timeouts triggering reboot (ODU12 specific)

```
syswatcher [WA] service <service name>(<service ID>) heartbeat timeout!
syswatcher [WA] service <service name>(<service ID>) may died,restart it!
syswatcher [WA] service <service name>(<service ID>) may died too many times, reboot!
```

> Only when service ID is `IH_SVC_IF` (interface service).

---

## Problem 4: Critically low memory triggering system reboot (ODU12 specific)

```
syswatcher [WA] memory is too low(0x<free bytes> Bytes), reboot system!
```

### Diagnosis

System free memory is below the minimum threshold (10MB or value configured in `/etc/min_memory`). Immediate reboot to prevent system crash.

---

## Problem 5: Service startup failure

```
syswatcher [ER] service <service name> (<service ID>) failed to startup!
```

---

## Problem 6: Service abnormal exit

```
syswatcher [ER] service <service name> (<service ID>) is exited!
syswatcher [IN] service <service name> will be restarted in <delay> seconds!
```

---

## Problem 7: Service heartbeat timeout

```
syswatcher [WA] service <service name>(<service ID>) heartbeat timeout!
syswatcher [WA] service <service name>(<service ID>) may died,restart it!
```

---

## Problem 8: Out of memory cannot start service

```
syswatcher [ER] Out of memory! Cannot start service <service name> (<service ID>)!
```

---

## Problem 9: Memory low triggering cache drop (ODU12 specific)

```
syswatcher [WA] memory(0x<free bytes> Bytes) is lower than <threshold>MB, drop cache!
```

### Diagnosis

Free memory below 80MB threshold; syswatcher auto-executes `echo 3 > /proc/sys/vm/drop_caches` to reclaim caches. Minimum 5-minute interval between two drops.

---

## Problem 10-22: Process name/args, startup config, startup timeout, command execution, signal handler, service func init, Boot Flag, filesystem read-only, internal anomaly, system info push, JSON config, sys init, config reset

Refer to original full documentation for detailed logs and solutions for problems 10 through 22.

---

## ODU12 Model Differences

| Behavior | Description |
|----------|-------------|
| Critically low memory auto-reboot | Triggered when free memory < 10MB (or `/etc/min_memory` value) |
| Memory low drop cache | Every 5 minutes when free memory < 80MB |
| interface service multiple timeout reboot | Direct system restart after consecutive interface heartbeat timeouts |
| Read-only filesystem recovery | Auto-attempt UBI data partition rebuild on read-only detection |

---

## Normal INFO Logs (No Action Needed)

```
syswatcher [IN] Received SIGTERM; quitting... / Received SIGUSR1; start/stop tracing
syswatcher [IN] dispatch startup config finished(status:<code>).
syswatcher [IN] normal/abnormal termination of syslogd/login service
syswatcher [IN] all services are ready,dispatch startup config.
syswatcher [IN] service <name> (<ID>) is stopped / will be restarted
syswatcher [IN] stopping all services... / all services exited / <N> service(s) will be killed!
syswatcher [IN] system started :<start time> / software version:<version>
syswatcher [IN] model:<model> / pn: <pn> / security chip version/check
syswatcher [IN] init timezone <tz> / iptables was restored
syswatcher [IN] Device time is synced, set time:<time>
```
