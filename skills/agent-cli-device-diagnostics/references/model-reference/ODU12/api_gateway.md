# api_gateway — Problem Diagnosis

> Applicable: When `api_gateway [ER]` or `api_gateway [WA]` appears in device logs, match the corresponding section to diagnose Web UI / REST API / MQTT / firmware upgrade / config import-export / packet capture tool anomalies.

## Log Format Reference

The format of api_gateway related logs in device logs is:

```
<timestamp> api_gateway [level] <message body>
```

| Level | Meaning | Requires Attention |
|-------|---------|-------------------|
| `[ER]` | ERROR, runtime error | **Yes** |
| `[WA]` | WARNING, non-fatal anomaly | **Yes** |
| `[IN]` | INFO, status change notification | For reference only |
| `[DB]` | DEBUG, debug information | Not output by default, usually no need to focus |

---

## Problem 1: api_gateway process received terminate/crash signal

### Matching Logs

```
api_gateway [IN] Received SIGTERM; quitting...
api_gateway [IN] Received SIGINT; quitting...
api_gateway [IN] Received an unknown signal; quitting...
api_gateway [ER] syswatcher crashed! I will follow to exit!
api_gateway [ER] syswatcher is not ready! I will follow to exit!
api_gateway [ER] service <service ID> crashed!
```

### Diagnosis

api_gateway received a termination signal or proactively exited due to dependent service anomaly. It saves runtime state before exiting. api_gateway is responsible for Web UI HTTP server, REST API routing, and MQTT message processing. During the exit period, all Web UI / API functions are unavailable.

### Cause

- SIGTERM: syswatcher proactively restarted api_gateway due to config change, or system shutdown
- SIGINT: triggered by Ctrl+C in a debug environment
- `syswatcher crashed`: syswatcher process exited abnormally, api_gateway follows and exits
- `service crashed`: another dependent service exited abnormally, api_gateway follows and exits
- `syswatcher is not ready`: syswatcher is still starting up and not yet ready

### Solution

1. api_gateway is managed by syswatcher and should auto-restart after exiting. If Web UI is still inaccessible after several minutes, trigger "device restart" via physical button or cloud platform
2. If `syswatcher crashed` or `service crashed` occurs repeatedly, prioritize investigating syswatcher and the corresponding service
3. If `syswatcher is not ready` appears briefly and then normalizes, can be ignored

---

## Problem 2: api_gateway restart failure

### Matching Logs

```
api_gateway [WA] Received SIGHUP; restarting...
api_gateway [ER] Restart FAILED
```

(The two logs usually appear sequentially)

### Diagnosis

SIGHUP triggered api_gateway to restart itself via execv, but the restart failed. Web UI / API services are interrupted.

### Cause

- api_gateway executable file is corrupted or missing
- Severe memory shortage

### Solution

1. Trigger "device restart" via physical button or cloud platform, syswatcher will re-launch api_gateway on startup
2. If restart still fails after reboot, re-upgrade firmware via Web UI

---

## Problem 3: Signal handler registration failure (at startup)

### Matching Logs

```
api_gateway [ER] cannot add handle for SIGHUP
api_gateway [ER] cannot add handle for SIGUSR1
api_gateway [ER] cannot add handle for SIGCHLD
api_gateway [ER] cannot add handle for SIGTERM
api_gateway [ER] cannot add handle for SIGINT
```

### Diagnosis

All libevent signal registrations failed at startup, indicating a severely anomalous api_gateway runtime environment.

### Cause

- System resources (file descriptors/memory) exhausted
- Residual zombie api_gateway processes
- libevent library corruption

### Solution

1. Trigger "device restart" via physical button or cloud platform
2. If it persists after restart, upgrade to the latest firmware version

---

## Problem 4: HTTP server startup failure

### Matching Logs

```
api_gateway [ER] Create evhttp error!
api_gateway [ER] Http bind socket error <return value> [<errno>:<error description>]!
api_gateway [ER] get loopback ip error!
api_gateway [ER] create superuser token error!
```

### Diagnosis

HTTP server creation, port binding, or loopback IP acquisition failed. Web UI is completely inaccessible.

- `Create evhttp error!`: libevent evhttp object creation failed
- `Http bind socket error`: HTTP port is occupied or binding permission denied
- `get loopback ip error!`: loopback interface does not exist
- `create superuser token error!`: superuser token generation failed, affecting API calls requiring authentication

### Cause

- HTTP port (default 80) occupied by another process
- loopback interface (lo) not enabled
- Random number generator unavailable (affecting token generation)
- Severe memory shortage

### Solution

1. Trigger "device restart" via physical button
2. If the HTTP port was previously modified via Web UI, confirm the new port is not occupied by other services
3. Upgrade to the latest firmware

---

## Problem 5: Runtime state save failure

### Matching Logs

```
api_gateway [ER] cannot dump running state to <file path>, we will not be able to recover in case of a fatal error!
api_gateway [WA] failed to save global data
api_gateway [WA] failed to save service data
```

### Diagnosis

api_gateway failed to save runtime state file on exit. Does not affect current functionality, only affects fast recovery on next startup (must reload from original config).

### Cause

- Storage partition space insufficient
- State file corrupted due to abnormal power loss

### Solution

1. Check storage usage via Web UI system status page
2. Perform device restart to clean temporary files and reload
3. Check whether Web UI config is complete; if missing, manually supplement

---

## Problem 6: HTTP request validation errors

### Matching Logs

```
api_gateway [ER] Request is NULL!
api_gateway [ER] Request Uri Invalid!
api_gateway [ER] Request Url Invalid!
api_gateway [ER] Request path Invalid!
api_gateway [ER] Not Found Http Request Resource!!!
api_gateway [ER] Http Request Header Lose Host
api_gateway [ER] Http Request Header Lose Authorization
api_gateway [ER] request command error!command:<command ID>
api_gateway [ER] Request api is busy!
api_gateway [ER] Request parameter <parameter name> Invalid!
```

### Diagnosis

HTTP request format is invalid, missing required headers, requested non-existent API path, HTTP method mismatch, or too many concurrent requests. These errors usually come from client/frontend issues.

- `Request is NULL!`: Backend internal anomaly, request object is null
- `Request Uri/Url Invalid!`: Request URL parsing failed
- `Request path Invalid!`: Request path is invalid (e.g., path traversal attack)
- `Not Found Http Request Resource!!!`: Requested non-existent API endpoint
- `Http Request Header Lose Host`: Missing Host header (usually an invalid request)
- `Http Request Header Lose Authorization`: Authentication required but Authorization header not provided
- `request command error`: HTTP method mismatch (e.g., using GET on an endpoint requiring POST)
- `Request api is busy!`: API concurrent request limit exceeded, rate limited
- `Request parameter <name> Invalid!`: Required interface parameter missing or invalid

### Cause

| Log Keyword | Common Cause |
|-------------|-------------|
| `Request is NULL` | Internal bug, not a client issue |
| `Uri/Url Invalid` | Client code bug, proxy server incorrectly modified URL |
| `path Invalid` | Client sent path containing `..` or special characters |
| `Not Found` | Accessed non-existent API endpoint |
| `Lose Host` | Non-browser client did not properly set Host header |
| `Lose Authorization` | Not logged in or token expired |
| `request command error` | Frontend used wrong HTTP method |
| `Request api is busy` | Large number of concurrent requests in short time |
| `parameter Invalid` | Frontend form/API call missing required parameters |

### Solution

1. **`Not Found`**: Confirm the API path being called is correct; refresh browser cache and retry
2. **`Lose Authorization`**: Log into Web UI again before performing operations
3. **`Request api is busy!`**: Reduce concurrent operations, wait a moment and retry
4. **`parameter Invalid`**: Ensure API calls carry all required parameters
5. **Other URL/URI errors**: Check reverse proxy (if any) configuration; try accessing device IP directly rather than domain name
6. If `Request is NULL!` appears frequently, clean the runtime environment via device restart

---

## Problem 7: JSON parse errors (Cross-API)

The following logs cover all JSON interaction interfaces including tcpdump, iperf, engineer mode, config import/export, cloud platform, traffic adjustment, debug, MQTT, etc.

### Matching Logs

```
api_gateway [ER] loads json error,<line>:<error message>
api_gateway [ER] load_file json error, <file name> is not valid json file.
api_gateway [ER] Get json object tcpdump error
api_gateway [ER] Create json array error
api_gateway [ER] response json error,ret:<return value>
api_gateway [ER] Topic is invaild,topic:<topic name>
api_gateway [ER] Session List Found Error!
api_gateway [ER] Get Authorization: Error!
api_gateway [ER] json_load_file config from <file> error.
api_gateway [ER] all_config json file dump failed.
api_gateway [ER] shadow config database replace failed.
api_gateway [ER] config_blob decode failed
```

### Sub-module parse errors

#### tcpdump packet capture tool

```
api_gateway [ER] prase item tcpdump error
api_gateway [ER] prase item action error
api_gateway [ER] prase item capture_mode error
api_gateway [ER] prase item capture_time error
api_gateway [ER] prase item capture_number error
api_gateway [ER] prase item expert_options error
api_gateway [ER] prase item interface error
api_gateway [ER] prase item interface string error
api_gateway [ER] prase iface item expert_options error
api_gateway [ER] prase iface error, item is same
api_gateway [ER] Invalid capture_mode <value>
api_gateway [ER] capture_time value[<value>] error
api_gateway [ER] interface array size[<size>] error
api_gateway [ER] show mode only support one interface
api_gateway [ER] prase local interface item interface error
api_gateway [ER] expert_options Invalid,expert_options:<options>
```

#### iperf speed test tool

```
api_gateway [ER] prase item iperf error
api_gateway [ER] prase item action error
api_gateway [ER] prase item expert_options error
api_gateway [ER] prase item role error
api_gateway [ER] Parse item command error
```

#### Engineer mode

```
api_gateway [ER] parse item engineer_mode error
api_gateway [ER] parse item action error
api_gateway [ER] config_blob decode failed
```

#### Traffic usage adjustment

```
api_gateway [ER] prase item adjust_usage error
api_gateway [ER] prase item adjust_usage_unit error
api_gateway [ER] adjust_usage_unit error value:<value>
```

#### Debug tool

```
api_gateway [ER] prase item debug error
api_gateway [ER] prase item action error
api_gateway [ER] prase item command error
```

#### Application request

```
api_gateway [ER] prase item packet_size error
```

#### MQTT / Session

```
api_gateway [ER] Topic is invaild,topic:<topic name>
api_gateway [ER] Session List Found Error!
api_gateway [ER] Get Authorization: Error!
```

### Diagnosis

JSON requests from Web UI or cloud platform cannot be parsed; the corresponding operation was not executed. The specific failed function can be determined from the function context or request path in the log.

### Cause

- Request body is empty or JSON format is invalid
- JSON is missing required fields
- Field value is outside legal range (e.g., `capture_time` is negative, `adjust_usage_unit` is an unsupported unit)
- `config_blob decode failed`: Engineer mode config blob base64 decode or gunzip decompression failed
- `Topic is invaild`: MQTT topic format is invalid
- `Session List Found Error!`: Session management internal data structure anomaly

### Solution

1. **Re-execute** the corresponding operation via Web UI (e.g., restart capture, re-save engineer mode config)
2. If errors persist:
   - Enter the corresponding function page and check all input items are valid
   - Refresh browser cache (Ctrl+F5) then retry
3. If `Topic is invaild` or `Session List Found Error!`:
   - Check MQTT connection status (Web UI → Cloud Platform Connection Status)
   - Clean sessions via Web UI device restart
4. `config_blob decode failed`: Check that engineer mode config is correctly copied and pasted without truncation or extra characters

---

## Problem 8: Packet capture tool (Tcpdump) operation errors

### Matching Logs

```
api_gateway [ER] action invalid, action:<action name>
api_gateway [ER] Invalid operation, tcpdump is not running!
api_gateway [ER] Invalid operation, please stop tcpdump first!
api_gateway [ER] Invalid operation, tcpdump is compressing!
api_gateway [ER] capture_mode is 'file', doesn't support GET request
api_gateway [ER] tcpdump fork error.(<errno>:<error description>)
api_gateway [ER] execlp tcpdump error.(<errno>:<error description>)
api_gateway [ER] tcpdump get iface err <return value> ifname <interface name>
api_gateway [ER] %s fork error.(<errno>:<error description>)
api_gateway [ER] execlp tcpdump error <errno>:<error description>
api_gateway [ER] tcpdump exited error!!status[<status>]
api_gateway [ER] Compress process exited error!!status[<status>]
```

### Diagnosis

Packet capture tool's start/stop/download operations encountered state conflicts or fork subprocess failures; capture functionality is abnormal.

- `fork error` / `execlp error`: tcpdump process cannot be created or executed, usually due to insufficient system resources
- `Invalid operation`: Operation order error (e.g., stopping when not started, duplicate operation during compression)
- `capture_mode is 'file'`: File mode does not support GET requests for real-time data

### Cause

- System process count or memory reached limit, fork failed
- User consecutively clicked buttons causing state conflicts
- Specified interface does not exist or is down
- GET request accessed tcpdump operations that only support POST

### Solution

1. Refresh Web UI page, wait for current capture session state to sync, then retry
2. Stop current capture first, then restart
3. Check whether the capture interface is online (Web UI → Network Status → Interfaces)
4. If the capture file is too large causing compression timeout, reduce capture time or use smaller file segments
5. After long runtime, clean residual tcpdump child processes via device restart

---

## Problem 9: Packet capture tool interface/VIF fetch errors

### Matching Logs

```
api_gateway [ER] Invalid index <index>
api_gateway [ER] No interface to restart tcpdump
api_gateway [ER] Can't find vif by iface info
api_gateway [ER] Get capture file info error
api_gateway [ER] Get panel name error(restar tcpdump)
api_gateway [ER] restart tcpdump ,create file num[<count>] is error
api_gateway [ER] fork error
api_gateway [ER] Open dir <directory> error
api_gateway [ER] malloc file info error
api_gateway [ER] [<directory>] file num too many!
api_gateway [ER] Get file <filename> stat error
api_gateway [ER] file <filename> is not pcap file
api_gateway [ER] rename file <old filename> to <new filename> error
api_gateway [ER] Remove file <filename> error
api_gateway [ER] execlp tar error
api_gateway [ER] File <file> not exist
```

### Diagnosis

The packet capture tool encountered filesystem or interface mapping errors during interface restart or file compression/packaging.

### Cause

- Capture interface has gone down or name changed (VIF not found during tcpdump restart)
- Capture file storage directory anomaly (`/tmp` partition full)
- File count exceeding limit causing `file num too many`
- Non-pcap files mixed into capture directory

### Solution

1. Ensure the capture interface is in UP state
2. Via Web UI enter "Diagnostics → Packet Capture" and clear old capture files
3. System Status → Storage, check `/tmp` partition usage
4. Perform device restart to clean temporary directory

---

## Problem 10: iperf speed test tool errors

### Matching Logs

```
api_gateway [ER] %s fork error.(<errno>:<error description>)
api_gateway [ER] invalid action <action name>
```

### Diagnosis

iperf speed test tool startup failed or operation is invalid.

### Cause

- Insufficient system resources causing iperf child process fork failure
- Invalid action parameter passed

### Solution

1. Refresh Web UI page then re-execute the speed test
2. Confirm speed test parameters (role, command, etc.) are correctly configured
3. Clean via device restart after long runtime

---

## Problem 11: Debug tool errors

### Matching Logs

```
api_gateway [ER] command check error
api_gateway [ER] <tool name> pipe error.(<errno>:<error description>)
api_gateway [ER] <tool name> fork error.(<errno>:<error description>)
api_gateway [ER] open <file> failed(errno:<errno> <error description>)!
api_gateway [ER] Failed to execute [<command>], err: <errno>, <error description>
api_gateway [ER] cmd[<command>] run time > <seconds> sec, stop it!
api_gateway [ER] invalid action <action name>
api_gateway [ER] download file failed!
api_gateway [ER] check debug file failed, invalid file format!
api_gateway [ER] delete debug file failed!
api_gateway [ER] get file info failed!
api_gateway [ER] <function name> failed ret=<return value>
```

### Diagnosis

The debug tool's command validation, fork execution, or result file download failed.

### Cause

- `command check error`: Command is not in the whitelist, blocked by security policy
- `fork/pipe error`: Insufficient system resources
- `run time > X sec`: Debug command execution timed out, automatically terminated
- `download/delete file failed`: Debug result file operation failed

### Solution

1. Confirm the executed debug command is in the device-supported whitelist
2. Reduce command execution time or narrow output scope to avoid timeout
3. Check device storage space (Web UI → System Status → Storage)
4. For long-uncleaned debug files, enter the debug tool page via Web UI to manually delete

---

## Problem 12: Firmware upgrade errors

### Matching Logs

```
api_gateway [ER] firmware file doesn't exist
api_gateway [ER] firmware name format err
api_gateway [ER] Cannot find out <product name> in <firmware name>.
api_gateway [ER] not found firmware name
api_gateway [ER] image length is too short!image size:<size>
api_gateway [ER] verify or decrypt firmware failed
api_gateway [ER] check firmware failed, invalid firmware!
api_gateway [ER] download file error
api_gateway [ER] download file failed!
api_gateway [ER] iburn error
api_gateway [ER] upgrade failure.
api_gateway [ER] can not open <file>
api_gateway [ER] write error
api_gateway [ER] evbuffer_new error
api_gateway [ER] firmware file exist, delete it

api_gateway [ER] cmd is NULL
api_gateway [ER] str[<string>] invalid
```

### Diagnosis

During the firmware upgrade process, file download, verification, decryption, or flashing step failed. The upgrade did not take effect; the device continues running the original firmware.

### Cause

- `firmware name format err`: Firmware filename does not conform to naming convention
- `Cannot find out <product name>`: Uploaded firmware is not applicable to the current device model
- `image length is too short`: Firmware file size anomaly (incomplete or corrupted)
- `verify or decrypt firmware failed`: Firmware signature verification or decryption failed; file tampered with or corrupted
- `download file error/failed`: Network interruption or insufficient storage during firmware download
- `iburn error`: Firmware write to flash failed
- `evbuffer_new error`: Insufficient memory

### Solution

1. Confirm firmware filename format is correct and is for the current device model (ODU12)
2. Re-upload firmware file via Web UI "System → Firmware Upgrade"
3. Ensure device has sufficient storage space (Web UI → System Status → Storage)
4. If network is unstable, download firmware locally first then upload via Web UI (instead of URL upgrade)
5. If `iburn error` occurs repeatedly, contact after-sales to check hardware status

---

## Problem 13: FIT image verification errors (firmware upgrade internal check)

The following logs come from the libfdt FIT image verification module, corresponding to internal integrity checks during firmware upgrade:

### Matching Logs

```
api_gateway [IN] Can't get '<property>' property from FIT <address>, node: offset <offset>, name <node name> (<description>)
api_gateway [IN] Can't set '<property>' property for '<node>' node (<description>)
api_gateway [IN] Unsupported hash alogrithm
api_gateway [IN] error!<algorithm> for '<node>' hash node in '<image>' image node
api_gateway [IN] Can't find images parent node '<path>' (<description>)
api_gateway [IN] Wrong image format: no description
api_gateway [IN] Wrong image format: description is not match!
api_gateway [IN] Wrong image format: no images node
api_gateway [IN] Bad image format!
api_gateway [IN] Image hash check error!
api_gateway [IN] fw check failure.
api_gateway [IN] get file type failed
```

### Diagnosis

Firmware FIT image format is invalid, description info mismatch, or signature/hash verification failed. Firmware upgrade will be aborted.

### Cause

- Firmware file is not standard FIT format
- Firmware file is corrupted or truncated
- Firmware signature/hash does not match expected value

### Solution

1. Re-download the correct model firmware file from official channels
2. Re-upload and upgrade via Web UI
3. Verify firmware file integrity (e.g., MD5 check)

---

## Problem 14: Config import/export errors

### Matching Logs

```
api_gateway [ER] download file error
api_gateway [ER] import config file invalid
api_gateway [ER] import config failure.
api_gateway [ER] check config file failed, invalid file format!
api_gateway [ER] json_load_file config from <file> error.
api_gateway [ER] can not get all config from shadow!
api_gateway [ER] can not get svi_obj[<service name>] from all config
api_gateway [ER] all_config json file dump failed.
api_gateway [ER] shadow config database replace failed.
api_gateway [ER] load_file json error, <file> is not valid json file.
api_gateway [ER] can not get value from key:<key name>
api_gateway [ER] can not get value string from key:<key name>
api_gateway [ER] encrypt string[<value>] is error
api_gateway [ER] can not set new value to key:<key name>
api_gateway [ER] <function name>(<line>):input invalid
api_gateway [ER] can not encrypt key:<key name>, value[<value>]
```

### Diagnosis

Config file export, import, or encryption processing failed. Config backup/restore functionality is unavailable.

### Cause

- Imported config file is not valid JSON format
- Config file structure is incomplete or version incompatible
- `can not get all config from shadow`: Config database read failed
- `encrypt string is error`: Encrypted field in config (e.g., password) has abnormal length or format
- `shadow config database replace failed`: Config database write failed (insufficient storage space)

### Solution

1. Confirm the imported config file is a complete JSON file exported by this device or same-model device
2. Do not modify config file structure in a text editor (especially do not modify encrypted fields)
3. Re-export/import via Web UI "System → Config Management"
4. If `shadow config database replace failed` occurs repeatedly, check storage space then perform device restart

---

## Problem 15: Factory reset errors

### Matching Logs

```
api_gateway [ER] Can't unlink shadow db, restore failed.
api_gateway [ER] Can't unlink shadow backup db, restore failed.
api_gateway [ER] Can't unlink NM db, restore failed.
api_gateway [ER] Can't unlink events db, restore failed.
api_gateway [ER] Can't unlink ih_record db, restore failed.
api_gateway [ER] Can't unlink service db, restore failed.
api_gateway [ER] Can't unlink timezone file, restore failed.
api_gateway [ER] Execute command failed: <command>
api_gateway [ER] clear events db failed.
```

### Diagnosis

During factory reset, some database files or config deletions failed; restoration is incomplete. The device may retain old configuration.

### Cause

- Some database files are occupied by other processes (file locks)
- Storage media anomaly (read-only mount or bad blocks)
- `Execute command failed`: Factory reset script execution failed

### Solution

1. Re-execute via Web UI "System → Maintenance → Factory Reset"
2. Perform device hard reset (via physical button or reset hole)
3. If failures persist, contact after-sales to check storage hardware status

---

## Problem 16: Engineer mode config blob decryption errors

### Matching Logs

```
api_gateway [ER] em_script: base64 decode failed
api_gateway [ER] em_script: gunzip failed
api_gateway [ER] em_script: JSON parse: <error message>
api_gateway [ER] em_script: invalid blob fields
api_gateway [ER] em_script: seed decode failed
api_gateway [ER] em_script: EVP_PKEY_new_raw_private_key failed
api_gateway [ER] em_script: get raw public key failed
api_gateway [ER] em_script: OpenSSH PEM serialize failed
api_gateway [ER] em_script: PEM base64 encode failed
api_gateway [ER] em_script: output truncated (<written> >= <buffer size>)
```

### Diagnosis

The engineer mode config blob decryption pipeline (base64 decode → gunzip decompress → JSON parse → seed decrypt → key derivation → PEM export) failed at some step.

### Cause

- `base64 decode failed`: Input base64 blob format error
- `gunzip failed`: Blob decompression failed; data may be truncated
- `invalid blob fields`: JSON missing required fields (e.g., type, seed, blob)
- `seed decode failed` / `EVP_PKEY_new_raw_private_key failed`: Seed or private key format is invalid
- `output truncated`: Output buffer too small

### Solution

1. Confirm the config blob obtained from cloud platform is complete and unmodified
2. Re-deliver engineer mode config from cloud platform
3. Check that the key matches the current device

---

## Problem 17: Python SDK / App import-export errors

### Matching Logs

```
api_gateway [ER] import python sdk is too big <size>!
api_gateway [ER] download file error
api_gateway [ER] upgrade python sdk failure.
api_gateway [ER] import python app is too big <size>!
api_gateway [ER] download python app error
api_gateway [ER] import python app config is too big <size>!
api_gateway [ER] download python app config error
api_gateway [ER] creat <path> failed(<errno>:<error description>)
api_gateway [ER] import python file failure.
api_gateway [ER] open directory <directory> failed(<errno>:<error description>)
api_gateway [ER] Request parameter <parameter name> Invalid!
```

### Diagnosis

Python SDK upgrade or Python app/config import failed due to file too large or download failure.

### Cause

- Python SDK file exceeds the device's allowed maximum size
- Network instability causing download interruption
- Insufficient device storage space
- Correct app name parameter not specified

### Solution

1. Check whether Python SDK file size exceeds device limits
2. Re-upload Python SDK / App via Web UI
3. Check storage space (Web UI → System Status → Storage)
4. Confirm app name parameter is correctly filled in

---

## Problem 18: Portal asset upload errors

### Matching Logs

```
api_gateway [ER] logo[<filename>] format invalid!
api_gateway [ER] check portal logo file failed, invalid file!
api_gateway [ER] download portal logo file failed!
api_gateway [ER] background image[<filename>] format invalid!
api_gateway [ER] check portal background image file failed, invalid file!
api_gateway [ER] download portal background image file failed!
api_gateway [ER] Request parameter <parameter name> Invalid!
```

### Diagnosis

Captive Portal logo or background image upload failed.

### Cause

- Image format not supported (only specific formats like PNG/JPG supported)
- Image file corrupted
- Network download failed
- Missing UUID parameter

### Solution

1. Confirm uploaded image format and size meet Portal requirements
2. Re-upload images via Web UI "Network → Captive Portal"
3. Ensure image files are not corrupted

---

## Problem 19: Cloud platform connection/config errors

### Matching Logs

```
api_gateway [ER] Not find current cloud.
api_gateway [ER] NOT support the input cloud platform.
api_gateway [ER] Not find file, now create new awscloud json file.
api_gateway [ER] write new server to json file failed.
api_gateway [ER] popen failed in get_throughput_delta on <interface name>.
api_gateway [ER] get iface err by ifname <interface name>
api_gateway [ER] get info of modem failed.
```

### Diagnosis

Cloud platform configuration or connection-related operations failed.

### Cause

- `Not find current cloud`: No cloud platform connection currently configured
- `NOT support the input cloud platform`: Unsupported cloud platform type specified
- `write new server to json file failed`: Cloud platform config write failed (insufficient storage)
- `popen failed`: popen system call failed when getting interface throughput
- `get iface err by ifname`: Specified uplink interface does not exist
- `get info of modem failed`: Modem info fetch failed (modem not ready)

### Solution

1. Check and configure cloud platform connection via Web UI "Network → Cloud Platform Connection"
2. Confirm the selected cloud platform type is in the device support list
3. Ensure device storage space is sufficient
4. Confirm uplink interface is online (e.g., cellular1 modem has dialed successfully)

---

## Problem 20: Modem firmware upgrade errors

### Matching Logs

```
api_gateway [ER] err_reason:<error message>
api_gateway [ER] iburn error
```

### Diagnosis

Modem module firmware upgrade failed.

### Cause

- Modem firmware file mismatch or corruption
- Modem communication anomaly
- `iburn error`: Firmware flashing failed

### Solution

1. Confirm modem firmware file is applicable to the current modem model
2. Re-upload and upgrade via Web UI "System → Modem Upgrade"
3. Ensure modem is in normal working state
4. If failures persist, contact after-sales

---

## Normal INFO Logs (No Action Needed)

The following logs indicate normal functionality. Do not diagnose as problems:

```
api_gateway [IN] Received SIGTERM; quitting...
api_gateway [IN] Received SIGINT; quitting...
api_gateway [IN] Received an unknown signal; quitting...
api_gateway [IN] Received SIGUSR1; start tracing to <file>
api_gateway [IN] Received SIGUSR1; stop tracing to <file>
api_gateway [IN] libevent:[<level>] [<message>]
api_gateway [IN] Http server not enable!
api_gateway [IN] Start http at ip:<IP>, port:<port>, timeout <timeout>
api_gateway [IN] prepare to load config...
api_gateway [IN] reset to default config
api_gateway [IN] MSG: 0x<message type> from service <service ID>
api_gateway [IN]     Len: <length>
api_gateway [IN]     Content: <content>
api_gateway [IN] tcpdump file[<file>] exist time more than <seconds>s, unlink it.
api_gateway [IN] tcpdump begin:[tcpdump -i <interface> -C <size> -W <count> -s0 -w <file> <options>]
api_gateway [IN] tcpdump is running,killall tcpdump
api_gateway [IN] compress is running,kill it
api_gateway [IN] compress process exited completely!!
api_gateway [IN] tcpdump exited completely!! Begin to compress file...
api_gateway [IN] import config...
api_gateway [IN] import python config...
api_gateway [IN] import python app...
api_gateway [IN] upgrade firmware...
api_gateway [IN] upgrade firmware [<firmware name>]
api_gateway [IN] upgrade modem firmware...
api_gateway [IN] upgrade type:<type>
api_gateway [IN] upgrade successfully
api_gateway [IN] upgrade python sdk...
api_gateway [IN] upgrade config form imported file:[<file>]...
api_gateway [IN] reboot system ...
api_gateway [IN] config file check ok.
api_gateway [IN] download <app name> log
api_gateway [IN] update python app config:<path>
api_gateway [IN] export <app name> config
api_gateway [IN] Loopback1 ip change,ip:<IP>,restart http...
api_gateway [IN] Http Request login new
api_gateway [IN] create running config object failed.
api_gateway [IN] running conf is empty, create it.
api_gateway [IN] create running object failed.
api_gateway [IN] create running return object failed.
api_gateway [IN] Load json from default config failed
api_gateway [IN] Load json from running config failed
api_gateway [IN] get object <node name> from running config failed
api_gateway [IN] find the <name>'s uplink config from running config
api_gateway [IN] find the <name>'s static route config from running config
api_gateway [IN] getting running of <query>
api_gateway [IN] payload or root object is null
api_gateway [IN] data want to shaping is illegal
api_gateway [IN] handle json root error code[<code>] :[<data>]
api_gateway [IN] create new app payload object failed
api_gateway [IN] find node <node name> which need to shaping
api_gateway [IN] node <node name> not need to shaping just merge it
api_gateway [IN] get the node <node> name <name>'s uuid is <uuid>
api_gateway [IN] request topic:<topic>,payload len:<length>
api_gateway [IN] request topic:<topic>,payload:<content>
api_gateway [IN] em_script: generated <bytes> bytes for <server>:<port>
api_gateway [IN] fw check successfully.
api_gateway [IN] restore=> clear config shadow db succeeded.
api_gateway [IN] restore=> clear NM msg db succeeded.
api_gateway [IN] restore=> clear events db succeeded.
api_gateway [IN] restore=> clear record db succeeded.
api_gateway [IN] restore=> clear service db succeeded.
```

---

## General Troubleshooting Information Collection

If api_gateway related issues cannot be located via the sections above, please collect the following information:

1. All `api_gateway [ER]` and `api_gateway [WA]` lines in device logs
2. Complete logs for 1 minute before and after the fault
3. Whether Web UI is currently accessible; if accessible, the specific page and parameters of the faulty operation
4. Whether the following events occurred at or before the fault time: firmware upgrade, config import, engineer mode operation, cloud platform config change
5. Device storage and memory usage
6. If firmware upgrade is involved, provide firmware filename and version number
