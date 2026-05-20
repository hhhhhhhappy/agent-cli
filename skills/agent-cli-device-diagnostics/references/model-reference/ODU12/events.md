# events — Problem Diagnosis

> Applicable: events (event recording/alerting) service self-anomaly (runtime state persistence failure), SQLite database anomaly, event record/trigger failure, client event node anomaly, cloud alert rule JSON parse error, alert rule load/save failure.

## Log Format Reference

| Level | Meaning | Requires Attention |
|-------|---------|-------------------|
| [ER] | ERROR | Yes |
| [WA] | WARNING | Yes |
| [IN] | INFO | For reference only |

> Note: events service log prefix is `events`.

---

## Problem 1: Runtime state persistence failure

### Matching Logs

```
events [ER] cannot dump running state to <file path>, we will not be able to recover in case of a fatal error!
events [WA] failed to save service data
events [WA] failed to save client event data
events [WA] failed to load service data
events [WA] failed to load client event data
events [WA] failed to malloc client event data
events [WA] failed to open tmp file for events backup.
```

### Diagnosis

events service cannot write runtime state (event records, client event data) to the persistence file or recover from the file, or cannot create/open event backup temp files.

### Cause

1. `/var/run/` or `/tmp/` partition space insufficient or read-only
2. Filesystem anomaly
3. Insufficient memory

### Solution

1. Perform device restart via Web UI
2. If it persists, contact after-sales

---

## Problem 2: SQLite database anomaly

### Matching Logs

```
events [ER] failed to open tmp file for events backup.
events [ER] DB of events_db (<database file>) open failed.
events [ERR] SQL '<SQL statement>' error: <error message>
```

### Diagnosis

events service cannot create/open the event database file, or SQL execution error.

### Cause

1. Database file corruption
2. Database file partition full or read-only
3. SQL syntax error or schema incompatibility

### Solution

1. Perform device restart via Web UI
2. If it persists, contact after-sales to check storage

---

## Problem 3: Client event node anomaly

### Matching Logs

```
events [ER] <function name>: client_node is null!
events [ER] malloc client node failed
```

### Diagnosis

events service processing client events (device online/offline, etc.) with null client node or memory allocation failure.

### Cause

1. Event data incomplete (missing client info)
2. Insufficient system memory

### Solution

1. If sporadic, may be due to incomplete client info, can be ignored
2. If frequently accompanied by memory allocation failure, perform device restart via Web UI

---

## Problem 4: Cloud alert rule config error

### Matching Logs

```
events [ER] gl_myinfo.priv.cloud_alerts loads json error,<line>:<error description>
events [ER] get cloud alert rules_array failed
```

### Diagnosis

events service failed to load cloud alert rule JSON config.

### Cause

1. Cloud alert rule JSON format invalid
2. rules_array field missing or format error

### Solution

1. Check alert rule JSON config format via cloud platform
2. Ensure rule config includes rules_array field

---

## Problem 5: Event trigger with missing parameters

### Matching Logs

```
events [ER] event:<event code> some args lost
events [ER] uplink switch event: currentSim or previousSim is empty
events [ER] get time from timestamp failed
```

### Diagnosis

Missing necessary parameters when event triggered: generic event parameters missing, uplink switch event with empty currentSim/previousSim, timestamp fetch failure.

### Cause

1. Event source (e.g., redial, sdwan) passed incomplete parameters
2. Modem SIM card info not ready
3. System time anomaly

### Solution

1. If sporadic, may be parameters not yet ready when event reported
2. Check SIM card status
3. Check system time sync (NTP) status
4. Perform device restart via Web UI

---

## Problem 6: JSON cloud config parse error

### Matching Logs

```
events [ER] static config loads json error,<line>:<error description>
events [ER] get email_out is not a array!
events [ER] request json is NULL
events [ER] request json argument is invalid
events [ER] request json is invalid
```

### Diagnosis

Cloud-delivered events config (e.g., alert email notification config) JSON format error or parameter invalid.

### Cause

1. JSON is empty or format invalid
2. Email notification recipient list is not a JSON array

### Solution

1. Check event/alert config JSON format via cloud platform
2. Ensure recipient list uses JSON array format

---

## Normal INFO Logs (No Action Needed)

```
events [IN] save current log to flash!
events [IN] triggering events: <event description>
```

---

## General Troubleshooting Information Collection

1. All `events [ER]` and `events [WA]` lines in device logs
2. Complete logs for 2 minutes before and after the fault
3. Current event config summary (alert rules, email notification settings)
4. Whether there were alert events triggered at or before the fault time
5. Impact scope description (which alerts were not correctly recorded or notified)
