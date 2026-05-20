# NetworkManager — Problem Diagnosis

> Applicable: When `NetworkManager [ER]` or `NetworkManager [WA]` appears in device logs, match corresponding sections to diagnose AWS IoT MQTT connection, cloud platform communication, Shadow config sync, firmware OTA upgrade, remote diagnostic tools, device registration function anomalies.

## Log Format Reference

| Level | Meaning | Requires Attention |
|-------|---------|-------------------|
| `[ER]` | ERROR, runtime error | **Yes** |
| `[WA]` | WARNING, non-fatal anomaly | **Yes** |
| `[IN]` | INFO, status change notification | For reference only |

---

## Problem 1: AWS IoT MQTT connection failure

### Matching Logs

```
NetworkManager [ER] Aws MQTT Connection failed with error <error>
NetworkManager [ER] Connection failed with mqtt return code <return code>
NetworkManager [ER] Aws MQTT Connection interrupted with error <error>
NetworkManager [ER] MQTT Connection failed with error <error>
NetworkManager [ER] Event Loop Group Creation failed / ClientBootstrap failed
NetworkManager [ER] Client Configuration initialization failed / MQTT Client Creation failed
NetworkManager [ER] MQTT Connection Creation failed / connection is NULL
NetworkManager [ER] Operation topic:[<topic>] failed with error <error>
NetworkManager [WA] NM destination AWS host(<host>):port(<port>) network unreachable
```

### Diagnosis

NetworkManager cannot establish or maintain MQTT long connection to AWS IoT platform. All cloud-delivered config, firmware OTA, Shadow sync, remote diagnostics are unavailable.

### Cause

- No Internet connection (cellular/WAN offline)
- AWS IoT endpoint DNS resolution failure
- AWS IoT x509 certificate/private key invalid or expired
- Device Thing not registered with AWS IoT
- AWS IoT endpoint URL misconfigured
- MQTT port (8883) blocked by firewall
- Device certificate or private key file missing

### Solution

1. Confirm Internet connectivity (Web UI → Network Status → Interfaces)
2. Check cloud platform connection config (Web UI → Network → Cloud Platform Connection)
3. Regenerate and upload certificates if expiring
4. Check DNS settings
5. If network is normal but init errors persist, perform device restart

---

## Problem 2: MQTT subscribe/unsubscribe failure

```
NetworkManager [ER] Subscribe [<topic>] failed with error <error>
NetworkManager [ER] Subscribe rejected by the broker.
NetworkManager [ER] Unsubscribe [<topic>] failed / rejected by the broker
```

### Solution

1. First confirm MQTT connection is normal (see Problem 1)
2. Check AWS IoT Policy has granted subscribe permissions for the topic

---

## Problem 3: MQTT publish message failure

```
NetworkManager [ER] publish message failed, malloc error <errno>:<description>
NetworkManager [ER] json_pack/json_dump failed in <function>:<line>
NetworkManager [ER] insert msg to pub queue failed.
NetworkManager [ER] PublishJobsUpdate failed, malloc error
NetworkManager [ER] nmMqttReport seriesDataTopic/autovpnStatusTopic Publish msg to cloud failed!
NetworkManager [ER] nmMqttReportSum <type> reporting failed!
```

### Solution

1. Confirm MQTT connection status (see Problem 1)
2. Perform device restart to clean memory and message queues
3. Adjust cloud data reporting interval or reduce reported data types

---

## Problem 4: JSON message parse errors

```
NetworkManager [ER] load msg/payload/req payload/rep payload err: on line <line>:<error>
NetworkManager [ER] Unknown topic: <topic>
NetworkManager [ER] get status_obj/requestId_obj/method_obj/result_obj/payload_obj failed!
NetworkManager [ER] mqtt message is out of order, so get data failed.
NetworkManager [ER] alerts_rules_bk json file dump failed.
```

### Solution

1. Confirm cloud-delivered JSON format is correct
2. If `mqtt message is out of order` appears frequently, check uplink signal strength and latency
3. Perform device restart to clean message queues

---

## Problem 5: IoT Jobs / Firmware OTA upgrade errors

```
NetworkManager [ER] Jobs Error <error code> occurred
NetworkManager [ER] BUG: currentVersion is unknown!
NetworkManager [ER] firmware name format err / check firmware failed, invalid firmware!
NetworkManager [ER] fw upgrade is running
NetworkManager [ER] fork failed / ++++ nm_download_file failed!
NetworkManager [ER] start_daemon iburn fw:[<firmware path>] failed!
NetworkManager [ER] FW upgrade process exit abnormally / FW burn failed.
NetworkManager [ER] download firmware finished, but NM disconnect
NetworkManager [ER] FW burn ok, but NM disconnect, just reboot
```

### Solution

1. Confirm firmware is for the correct device model (ODU12)
2. Check Job status via cloud platform, confirm firmware URL is accessible
3. Ensure sufficient device storage space
4. If `FW burn failed` repeatedly, contact after-sales

---

## Problem 6: Device Shadow sync error

```
NetworkManager [ER] Error subscribing to shadow delta/delta accepted/delta rejected: <error>
NetworkManager [ER] Error processing shadow delta / Error on shadow accepted / Error on subscription
```

### Solution

1. Confirm MQTT connection is normal
2. Check AWS IoT Policy has granted Shadow topic permissions
3. Check Device Shadow state and Delta content via AWS IoT console

---

## Problem 7: Device Registration error

```
NetworkManager [ER] AWS Device Register Thing Name/Keys And Certificate response is null
NetworkManager [ER] CreateKeysAndCertificate failed with statusCode <code>, errorMessage <msg>
NetworkManager [ER] Error subscribing to RegisterThing accepted/rejected
NetworkManager [WA] RegisterThing failed with statusCode <code>
```

### Solution

1. Check AWS IoT Fleet Provisioning Template config
2. Confirm device Claim certificate correctly uploaded
3. Check AWS IoT Policy permissions

---

## Problem 8: Remote diagnostic tool (Tcpdump/Ping/Traceroute) errors

```
NetworkManager [ER] tcpdump_start/ping_start/traceroute_start: request is invalid!
NetworkManager [ER] payload/metadata/requestId/streamId is not found in request!
NetworkManager [ER] interface is not found / is not link up / is invalid!
NetworkManager [ER] tcpdump fork error / execlp tcpdump error / exec failed!
NetworkManager [ER] tool[<N>] is not supported!
NetworkManager [ER] get nmTools action[<action>]/tool[<tool name>] failed.
```

### Solution

1. Ensure target interface is UP
2. Re-deliver diagnostic request via cloud platform with complete and valid parameters
3. If fork fails, device may be at process/memory limit; restart via Web UI

---

## Problem 9-19: Thread/process, SQLite, File upload/download, Netconf, Certificate, License, Ngrok, Remote Access, Signal, Memory, Interface errors

Refer to original full documentation for detailed matching logs, diagnosis, causes, and solutions for problems 9 through 19.

---

## Normal INFO Logs (No Action Needed)

Key normal logs include:
```
NetworkManager [IN] Aws MQTT Connection completed / Connecting / Connection Failed / Connection resumed / Disconnect completed
NetworkManager [IN] method: / NM Server topic:[<topic>] / NM Server Msg:[<msg>]
NetworkManager [IN] tcpdump process begin/pid running / file uploading/cancel upload
NetworkManager [IN] FW burn ok. / firmware download job has been canceled.
NetworkManager [IN] burning firmware ... / Downloading modem firmware ... / Modem has been upgraded.
NetworkManager [IN] System reboot.... / System restore....
NetworkManager [IN] MSG: 0x<type> from service <ID> / Len: / Content:
NetworkManager [IN] retry connecting after <N>s...
NetworkManager [IN] Config update data > 120KB, now report by stream.
```
