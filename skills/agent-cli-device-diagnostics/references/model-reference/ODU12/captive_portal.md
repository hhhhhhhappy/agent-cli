# captive_portal — Problem Diagnosis

> Applicable: captive_portal service self-anomaly (signal handling failure, runtime state persistence failure), HTTP/HTTPS captive portal server startup failure (SSL certificate/port binding), RADIUS authentication/accounting failure, user login/logout failure, image download failure, Wifidog proxy anomaly, SSID match error, cloud JSON config error.

## Log Format Reference

| Level | Meaning | Requires Attention |
|-------|---------|-------------------|
| [ER] | ERROR | Yes |
| [WA] | WARNING | Yes |
| [IN] | INFO | For reference only |

> Note: captive_portal service log prefix is `captive_portal`.

---

## Problem 1: Captive Portal service signal handler registration failure / abnormal exit

### Matching Logs

```
captive_portal [ER] cannot add handle for SIGHUP
captive_portal [ER] cannot add handle for SIGUSR1
captive_portal [ER] cannot add handle for SIGCHLD
captive_portal [ER] cannot add handle for SIGTERM
captive_portal [ER] cannot add handle for SIGINT
captive_portal [ER] Received <signal name>; quitting...
```

### Diagnosis

captive_portal service failed to register handler functions for critical signals at startup, or received a termination signal and is exiting.

### Cause

1. Insufficient system resources (file descriptor exhaustion, low memory)
2. libevent event library initialization anomaly

### Solution

1. Perform device restart via Web UI
2. If it persists, contact after-sales

---

## Problem 2: Runtime state persistence failure

### Matching Logs

```
captive_portal [WA] failed to save global data
captive_portal [WA] failed to save service data
captive_portal [WA] failed to load global data
captive_portal [WA] failed to load service data
```

### Diagnosis

captive_portal cannot write runtime state to the persistence file or recover state from the file.

### Cause

1. `/var/run/` partition space insufficient or read-only
2. Filesystem anomaly

### Solution

1. Re-save Captive Portal config via Web UI
2. Perform device restart via Web UI

---

## Problem 3: HTTP/HTTPS auth server startup failure

### Matching Logs

```
captive_portal [ER] SSL_CTX_new failed
captive_portal [ER] EC_KEY_new_by_curve_name failed
captive_portal [ER] SSL_CTX_set_tmp_ecdh failed
captive_portal [ER] couldn't find crt [<cert file>] or key file [<key file>]
captive_portal [ER] SSL_CTX_use_certificate_chain_file failed
captive_portal [ER] open <password file> failed, <errno>:<error description>
captive_portal [ER] read passwd from <password file> failed, <errno>:<error description>
captive_portal [ER] SSL_CTX_use_PrivateKey_file failed
captive_portal [ER] SSL_CTX_check_private_key failed
captive_portal [ER] create evhttps error(<errno>,<error description>)
captive_portal [ER] https bind socket error(<errno>,<error description>)
captive_portal [ER] create evhttp error(<errno>,<error description>)
captive_portal [ER] http bind socket error(<errno>,<error description>)
```

### Diagnosis

captive_portal cannot start the HTTP or HTTPS auth server: SSL context creation failed, certificate/key files missing or unreadable, SSL private key check failed, socket binding failed.

### Cause

1. SSL certificate/key files do not exist or are corrupted
2. Certificate password file not readable
3. Specified port already occupied by another service
4. OpenSSL library initialization anomaly
5. Bound IP address does not exist on the device
6. Elliptic curve (ECDH) parameters not supported

### Solution

1. Check Captive Portal HTTPS certificate config via Web UI
2. Ensure certificate file paths are correct and files exist
3. Check whether HTTP/HTTPS ports conflict with other services
4. Re-save Captive Portal config via Web UI
5. Perform device restart via Web UI

---

## Problem 4: Loopback IP fetch failure

### Matching Logs

```
captive_portal [ER] get loopback ip error!
```

### Diagnosis

captive_portal cannot get the loopback interface IP address, causing inability to bind the auth server to the correct address.

### Cause

1. loopback interface not configured or does not exist
2. interface service not ready

### Solution

1. Check loopback interface config via Web UI
2. Perform device restart via Web UI

---

## Problem 5: RADIUS authentication/accounting failure

### Matching Logs

```
captive_portal [ER] rc_read_config failed
captive_portal [ER] rc_avpair_add SERVICE_TYPE failed
captive_portal [ER] rc_avpair_add FRAMED_IP_ADDRESS failed
captive_portal [ER] rc_avpair_add CALLING_STATION_ID failed
captive_portal [ER] rc_avpair_add CALLED_STATION_ID failed
captive_portal [ER] rc_avpair_add USER_NAME failed
captive_portal [ER] rc_avpair_add USER_PASSWORD failed
captive_portal [ER] rc_avpair_add NAS_IDENTIFIER failed
captive_portal [ER] rc_avpair_add PW_NAS_IP_ADDRESS failed
captive_portal [ER] rc_avpair_add SESSION_ID failed
captive_portal [ER] rc_avpair_add CLASS failed
captive_portal [ER] rc_avpair_add ACCOUNTING_STATUS failed
captive_portal [ER] rc_auth failed
captive_portal [ER] rc_acct failed
captive_portal [ER] not found session id
```

### Diagnosis

User authentication or accounting using the RADIUS server failed: RADIUS config read failure, cannot add auth/authz/accounting attributes (AVPair), RADIUS auth request failed, RADIUS accounting request failed.

### Cause

1. RADIUS config file (`/etc/radcli/radius.conf`) does not exist or has format error
2. RADIUS server unreachable
3. RADIUS shared secret mismatch
4. User attributes (IP/MAC/username, etc.) fetch failed
5. RADIUS session ID not generated

### Solution

1. Check RADIUS server address and port config via Web UI
2. Ensure RADIUS server is reachable
3. Check that the shared secret is correct
4. Re-save Captive Portal config via Web UI
5. If using internal auth, check username and password config

---

## Problem 6: RADIUS config file cannot be opened

### Matching Logs

```
captive_portal [ER] open file[<RADIUS config file>] failed(<errno>,<error description>)
captive_portal [ER] open file[<RADIUS shared secret file>] failed(<errno>,<error description>)
```

### Diagnosis

RADIUS config file or shared secret file cannot be opened.

### Cause

1. File does not exist (not generated or has been deleted)
2. Filesystem read-only or file permission issue

### Solution

1. Re-save Captive Portal RADIUS config via Web UI
2. Perform device restart via Web UI

---

## Problem 7: User request processing errors

### Matching Logs

```
captive_portal [ER] response buffer is NULL!
captive_portal [ER] allocated evbuffer error!
captive_portal [ER] <function name>: evhttp request is NULL!
captive_portal [ER] <function name>: allocated evbuffer error(<errno>, <error description>)
captive_portal [ER] [<function name>] Invalid params
captive_portal [ER] <function name>: get uri failed(<errno>, <error description>)
captive_portal [ER] <function name>: get query failed(<errno>, <error description>)
captive_portal [ER] <function name>: parse query failed(<errno>, <error description>)
captive_portal [ER] Invalid request header
captive_portal [ER] <function name>: invalid request type(<type>)
captive_portal [ER] request body get error!
captive_portal [ER] malloc body buffer error!
captive_portal [ER] not found captive portal config by uuid
captive_portal [ER] ssid check failed
captive_portal [ER] not found '<parameter name>' parameter
```

### Diagnosis

Various errors encountered during HTTP request processing: request is null, buffer allocation failure, URI/Query parameter fetch/parse failure, invalid request header, request method error, config query failure, SSID verification failure, missing required parameters.

### Cause

1. Client sent an abnormally formatted HTTP request
2. Insufficient memory
3. Requested captive portal UUID does not exist
4. Client's connected SSID does not match configuration
5. URL missing necessary parameters (e.g., uuid/token/stage)

### Solution

1. Check via cloud platform / Web UI that Captive Portal config UUID is correct
2. Ensure client's connected SSID matches the SSID in Captive Portal config
3. Check whether client page correctly concatenated URL parameters
4. Perform device restart via Web UI to free memory

---

## Problem 8: User login/creation failure

### Matching Logs

```
captive_portal [ER] <function name>: invalid user info!
captive_portal [ER] the number of user is full!
captive_portal [ER] <function name>: too many user login!
captive_portal [ER] <function name>: invalid parameter!
captive_portal [ER] create new user failed(ip: <IP>, mac: <MAC>)!
captive_portal [ER] invalid username
captive_portal [ER] invalid password
captive_portal [ER] not found ip
captive_portal [ER] not found mac
captive_portal [ER] not found ssid
captive_portal [ER] not found username
captive_portal [ER] not found response
captive_portal [ER] not found chap_id
captive_portal [ER] not found challenge
captive_portal [ER] password hex to char failed
captive_portal [ER] challenge hex to char failed
captive_portal [ER] radius auth failed
captive_portal [ER] unknown splash type
captive_portal [ER] unknown server type
captive_portal [ER] unknown content type
```

### Diagnosis

Errors encountered during user login authentication: invalid user info, user count reached limit, IP/MAC/SSID/username/password or other required fields missing or invalid, RADIUS authentication failed.

### Cause

1. Simultaneously online users exceed device limit
2. Login request missing IP/MAC/SSID or other info
3. Username or password is empty or invalid
4. Password/Challenge HEX format conversion failed
5. RADIUS server denied authentication
6. splash type/server type/content type not in supported range
7. Internal auth server does not support form submission

### Solution

1. Reduce the number of simultaneously online users, or contact after-sales for firmware supporting more users
2. Ensure login page submitted request contains complete fields
3. Check that username and password meet requirements (non-empty, correct format)
4. If using RADIUS, check RADIUS server logs
5. Check auth type config via Web UI

---

## Problem 9: Image/Portal resource download failure

### Matching Logs

```
captive_portal [ER] <function name>(<line>):need more param
captive_portal [ER] get filename failed
captive_portal [ER] open save file (<filename>) fail!
captive_portal [ER] curl init fail!
captive_portal [ER] download file (<filename>) fail!
captive_portal [ER] fork error.(<errno>:<error description>)
```

### Diagnosis

captive_portal failed when downloading images or resources needed by the Portal page: missing parameters, curl initialization failure, file creation failure, download failure, fork subprocess failure.

### Cause

1. Download URL not provided or invalid
2. curl library initialization failure
3. Save path not writable or insufficient space
4. Download URL unreachable
5. System process count reached limit

### Solution

1. Check that image/resource URLs in Captive Portal config are correct
2. Ensure the servers corresponding to the URLs are reachable
3. Re-save Captive Portal config via Web UI
4. Perform device restart via Web UI

---

## Problem 10: Wifidog proxy anomaly

### Matching Logs

```
captive_portal [ER] func[<function name>] get dot11 ipc msg failed
captive_portal [ER] get ssid gateway ip address failed
captive_portal [ER] get vlan_id failed
captive_portal [ER] get ssid failed
captive_portal [ER] get profile_name failed
captive_portal [ER] func[<function name>] send ipc msg failed
captive_portal [ER] wifidog ssid config update failed
captive_portal [ER] wifidog get mac failed
```

### Diagnosis

Wifidog (wireless auth proxy) functionality anomaly: cannot obtain SSID info from dot11d, cannot get gateway IP/VLAN ID/SSID/profile_name, IPC communication failure, MAC address fetch failure.

### Cause

1. dot11d (Wi-Fi management service) not running or not responding
2. Wi-Fi SSID/VLAN not correctly configured
3. wifidog service not running
4. IPC channel anomaly

### Solution

1. Check whether Wi-Fi functionality is enabled
2. If the device does not involve Wi-Fi, this issue can be ignored
3. Perform device restart via Web UI

---

## Problem 11: JSON cloud config parse errors

### Matching Logs

```
captive_portal [ER] request json is NULL
captive_portal [ER] portal json error,<line>:<error description>
captive_portal [ER] add captive portal failed, config is full!
captive_portal [ER] captive portal name conflict
captive_portal [ER] portal ssid conflict
captive_portal [ER] portal walled garden conflict
captive_portal [ER] invalid color[<color value>]
captive_portal [ER] show cp config to json failed
captive_portal [ER] show wifidog config to json failed
captive_portal [ER] loads cp/json response json error,<line>:<error description>
captive_portal [ER] dumps response json error
captive_portal [ER] <function name>(<line>):malloc failed
captive_portal [ER] <function name>(<line>):Failed to duplicate a string.
```

### Diagnosis

Errors when cloud delivers Captive Portal config or queries config: JSON is empty or format error, config full, name/SSID/Walled Garden conflict, invalid color value, memory shortage, string duplication failure.

### Cause

1. Cloud platform delivered invalid JSON config
2. Captive Portal config entry count exceeds system limit
3. Config name duplicates another Captive Portal
4. SSID occupied by another config
5. Walled Garden (auth-free domain/IP) conflicts with existing config
6. Color value format invalid
7. Insufficient memory

### Solution

1. Check JSON config format via cloud platform
2. Delete unwanted Captive Portal configs
3. Ensure config name/SSID does not conflict with existing configs
4. Reduce Walled Garden entry count
5. Use valid color format (e.g., RRGGBB hex)
6. Perform device restart via Web UI

---

## Problem 12: User status record persistence failure

### Matching Logs

```
captive_portal [WA] open <record file> filed(<errno>,<error description>)
captive_portal [WA] failed to save user info(<errno>,<error description>)
captive_portal [WA] failed to load user info(ret=<ret>,<errno>,<error description>)
```

### Diagnosis

captive_portal cannot save authenticated user info to the Flash record file or load from the file.

### Cause

1. Flash record file path not writable
2. Filesystem space insufficient
3. File corruption

### Solution

1. Perform device restart via Web UI
2. If it persists, contact after-sales

---

## Normal INFO Logs (No Action Needed)

The following logs indicate the captive_portal service is running normally. Do not diagnose as problems:

```
captive_portal [IN] Stop wifidog http/https auth server...
captive_portal [IN] Start wifidog http auth server(ip: <IP>, port: <port>)
captive_portal [IN] libevent:[<level>] [<message>]
captive_portal [IN] receive IPC_MSG_DOT11_CONFIG_INFO
captive_portal [IN] portal ssid ip change, [<old IP>] ==> [<new IP>]
captive_portal [IN] portal ssid change, [<old SSID>] ==> [<new SSID>]
captive_portal [IN] portal ssid enable change, [<old val>] ==> [<new val>]
captive_portal [IN] portal set ifname [<interface name>]
captive_portal [IN] MSG: 0x<type> from service <ID>
captive_portal [IN] Received SIGUSR1; start/stop tracing to <file>
captive_portal [IN] portal image download child(pid:<PID>) exited by signal with status <status>
captive_portal [IN] user(ip: <IP>, mac: <MAC>) activity duration time(<seconds> s) exceeds limit(<limit> s)
captive_portal [IN] user(ip: <IP>, mac: <MAC>) traffic(<bytes> bytes) exceeds limit(<limit> bytes)
captive_portal [IN] wifidog is not running, start it
captive_portal [IN] start wifidog
captive_portal [IN] stop wifidog
captive_portal [WA] Received SIGHUP; restarting...
```

---

## General Troubleshooting Information Collection

If captive_portal related issues cannot be located via the sections above, please collect the following information:

1. All `captive_portal [ER]` and `captive_portal [WA]` lines in device logs
2. Complete logs for 2 minutes before and after the fault
3. Current Captive Portal config summary (auth method, RADIUS config, SSID, Walled Garden)
4. Whether there were config changes at or before the fault time
5. Impact scope description (which SSIDs/users had authentication failures)
