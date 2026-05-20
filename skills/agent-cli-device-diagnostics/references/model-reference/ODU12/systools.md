# systools — Problem Diagnosis

> Applicable: systools (system toolset) — as a multi-tool dispatcher, diagnosis of its sub-tool anomalies: firmware upgrade (iburn) image verification/write/child process errors, password key management (passkeep/key1-encrypt) decrypt/encrypt/file errors, Python SDK/App management (inpython/pysdk_install) install/verification failure, connection tracking management (clearconntrack) backup restore failure, DNS resolution (dnsc) failure, unknown sub-command calls.

## Log Format Reference

| Level | Meaning | Requires Attention |
|-------|---------|-------------------|
| [ER] (LOG_ERR) | ERROR | Yes |
| [WA] (LOG_WARNING) | WARNING | Yes |
| [IN] (LOG_INFO) | INFO | For reference only |

> Note: systools is a multi-tool dispatcher dispatched via symlinks or command-line arguments to different sub-tools (iburn, passkeep, inpython, clearconntrack, dnsc, etc.). Log prefix is always `systools`.

---

## Problem 1: Firmware upgrade — Image file verification error (Magic / Name / Length / CRC / HMAC)

```
systools [ER] image magic error! / image name error!
systools [ER] image length error,<actual> < <expected>!
systools [ER] crc of image head/data error
systools [ER] verify or decrypt firmware failed / Bad image format! / Image hash check error!
systools [ER] check image hmac failed / This upgrade Image magic and version is error.
systools [ER] read firmware image failed, errno:<errno>(<description>)
systools [ER] firmware file doesn't exist
```

### Solution

1. Re-download correct ODU12 firmware file
2. Re-upload firmware and perform upgrade via Web UI
3. Confirm firmware MD5/SHA256 matches official release
4. Contact after-sales for correct firmware and signature

---

## Problem 2: Firmware upgrade — File/Mmap operation error

```
systools [ER] open <file path> failed errno <errno>(<description>)!
systools [ER] mmap/munmap failed.
systools [ER] unable to open Boot Flag / Boot Loader / OS Kernel / Second Kernel
systools [ER] unable to erase OS Kernel/Second Kernel / backup OS Kernel fail.
systools [ER] write Boot Loader failed! / unzip <file> err
```

---

## Problem 3: Firmware upgrade — Subprocess/Fork failure / Upgrade result error

```
systools [ER] fork failed / Upgrade IR9/Wifi board/Python/security board/firmware failed
systools [ER] unkown upgrade type <type>
systools [WA] upgrading  ret <return code>
systools [ER] %s out of memory.
```

---

## Problem 4: Password/Key management — Global password init and decryption failure

```
systools [ER] can not get key sharp! / get pass seg failed! / get key sharp failed
systools [ER] decrypt password failed! / make temp file error
systools [ER] write pass error / fail to init global pass!
systools [WA] creat symlink error or already exist / System Will Reboot After 10 Seconds!
```

### Diagnosis

passkeep tool failed during global password initialization. `fail to init global pass!` is the most severe error; device will auto-restart after 10 seconds.

---

## Problem 5: Password/Key management — Key encryption and Base64 encoding failure

```
systools [ER] can not get key sharp! / %s:get key sharp failed
systools [ER] %s:encrypt password failed! / passkeep base64_encoded error
systools [ER] open /tmp/key1 failed
```

---

## Problem 6: Python SDK / App management — Install and verification failure

Key logs include:
```
systools [ER] pyapp or sign file not exists / popen cmd:<command> failed
systools [ER] PyAPP <file> verify failure! / pyapp <name> incomplete...
systools [ER] pysdk format err / upgrade python sdk/app failed
systools [ER] python app format err / creat soft link / tar / insatll app failed
systools [ER] not install PySDK / start app json format err / unzip failed
systools [ER] json error on line <line>: <description>
```

### Solution

1. Re-upload correct Python SDK / App installation packages
2. Ensure PySDK is installed before PyApp
3. Confirm installation package signatures are valid
4. Perform device restart via Web UI and retry

---

## Problem 7-9: Connection tracking, DNS resolution, Unknown sub-command

Refer to original full documentation for problems 7 through 9.

---

## Normal INFO Logs (No Action Needed)

```
systools [IN] upgrade: <written> / <total size> / upgrade successfully/failure.
systools [IN] check image hmac OK
systools [IN] sys upgrade / sys upgrade boot / sys upgrade modem / sys upgrade fully
systools [IN] upgrade python sdk/app successfully
systools [IN] start install app <name>... / install app <name> successfully
systools [IN] PyAPP <file> verify OK! / pyapp <name> install successfully
systools [IN] save connector openvpn/ngrok conntrack info
systools [IN] clear conntrack!
```
