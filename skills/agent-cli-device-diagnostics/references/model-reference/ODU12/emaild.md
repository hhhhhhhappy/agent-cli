# emaild — Problem Diagnosis

> Applicable: emaild (email notification) service self-anomaly (signal handling failure, runtime state persistence failure), SMTP connection/auth failure, SSL/TLS handshake failure, email send failure (queue full/no server/no address), email creation failure, cloud JSON config error.

## Log Format Reference

| Level | Meaning | Requires Attention |
|-------|---------|-------------------|
| [ER] | ERROR | Yes |
| [WA] | WARNING | Yes |
| [IN] | INFO | For reference only |

> Note: emaild service log prefix is `emaild`.

---

## Problem 1: Emaild service signal handler registration failure / abnormal exit

### Matching Logs

```
emaild [ER] cannot add handle for SIGHUP
emaild [ER] cannot add handle for SIGUSR1
emaild [ER] cannot add handle for SIGCHLD
emaild [ER] cannot add handle for SIGTERM
emaild [ER] cannot add handle for SIGINT
emaild [ER] Received <signal name>; quitting...
emaild [ER] Restart FAILED
emaild [ER] syswatcher crashed! I will follow to exit!
```

### Diagnosis

emaild service failed to register signal handlers at startup, received a termination signal and exited, or restart failed. When syswatcher crashes, emaild also proactively exits.

### Cause

1. Insufficient system resources
2. syswatcher service crash (IPC channel disconnected)

### Solution

1. Perform device restart via Web UI
2. If it persists, contact after-sales

---

## Problem 2: Runtime state persistence failure

### Matching Logs

```
emaild [ER] cannot dump running state to <file path>, we will not be able to recover in case of a fatal error!
emaild [WA] failed to save service data
emaild [WA] failed to load service data
```

### Diagnosis

emaild cannot write runtime state to the persistence file or recover from the file.

### Cause

1. `/var/run/` partition space insufficient or read-only
2. Filesystem anomaly

### Solution

1. Re-save email notification config via Web UI
2. Perform device restart via Web UI

---

## Problem 3: SMTP server connection failure

### Matching Logs

```
emaild [ER] Unable to locate <SMTP server IP>
emaild [ER] unable to create smtp socket
emaild [ER] unable to connect smtp server (<IP>:<port>)
```

### Diagnosis

emaild cannot resolve the SMTP server address, cannot create a socket, or cannot connect to the SMTP server.

### Cause

1. SMTP server address misconfigured or domain cannot be resolved
2. System socket resources exhausted
3. SMTP server unreachable (network unreachable, port blocked)
4. SMTP server not running

### Solution

1. Check via Web UI that SMTP server address and port are correctly configured
2. Confirm the device can reach the SMTP server (network connectivity)
3. Check whether the SMTP server is running normally
4. Try changing the SMTP server or port

---

## Problem 4: SMTP auth/session failure

### Matching Logs

```
emaild [ER] CONNECT
emaild [ER] CONN
emaild [ER] HELO
emaild [ER] LOGIN
emaild [ER] MAIL
emaild [ER] RCPT
emaild [ER] DATA
emaild [ER] QUIT
```

### Diagnosis

A step in the SMTP protocol session failed: CONNECT / HELO (handshake) / LOGIN (auth) / MAIL (sender) / RCPT (recipient) / DATA (email content) / QUIT (exit). These logs indicate the SMTP server response for the corresponding step was not the expected value.

### Cause

1. SMTP server auth requirements don't match config (login required, wrong username/password)
2. Sender email rejected by SMTP server
3. Recipient email format invalid or rejected
4. SMTP server returned an abnormal response code
5. SMTP server does not support the configured auth method

### Solution

1. Check SMTP auth config via Web UI (username, password, SSL required)
2. Confirm sender and recipient email formats are correct
3. Check if the SMTP server has whitelist restrictions on sender/recipient
4. Try changing auth method (e.g., No Auth → Require Login)

---

## Problem 5: SSL/TLS connection failure

### Matching Logs

```
emaild [ER] No SSL support initiated
emaild [ER] Use certfile
emaild [ER] Use PrivateKey
emaild [ER] Private key does not match the certificate public key
emaild [ER] STARTTLS
emaild [ER] SSL not working
emaild [ER] SSL_connect
emaild [ER] SSL_get_peer_certificate
```

### Diagnosis

SMTP over SSL/TLS connection failed.

### Cause

1. SMTP config did not enable SSL/TLS but attempted encrypted connection
2. Certificate file and private key do not match
3. SMTP server does not support STARTTLS
4. SSL library initialization anomaly
5. SMTP server certificate not trusted

### Solution

1. Check SSL/TLS config via Web UI (whether encryption needed, certificate settings)
2. If SSL/TLS is not needed, disable it in config
3. If SMTP server uses self-signed certificate, confirm the device trusts that certificate
4. Re-save email notification config via Web UI

---

## Problem 6: SMTP initialization failure

### Matching Logs

```
emaild [ER] unable to init smtp
```

### Diagnosis

emaild cannot initialize the SMTP client; email functionality is completely unavailable.

### Cause

1. SMTP library initialization anomaly
2. Insufficient system resources

### Solution

1. Perform device restart via Web UI
2. Contact after-sales

---

## Problem 7: Email creation/send failure

### Matching Logs

```
emaild [ER] unable to create email
emaild [ER] no email server
emaild [ER] no email addr
emaild [ER] email send failed,err(<error code>)
emaild [ER] trans queue is full,drop alarm
```

### Diagnosis

Email creation failed (missing necessary info), no SMTP server configured, no recipient address, email send failed, transmit queue full causing alert to be dropped.

### Cause

1. SMTP server address not configured
2. Recipient email address empty or not configured
3. Email transmit queue full (large number of alert emails generated in short time)
4. SMTP server connection or auth failure causing send failure

### Solution

1. Configure SMTP server address and recipient email via Web UI
2. Reduce alert trigger frequency
3. Check if there were prior SMTP connection/auth failure logs
4. Re-save email notification config via Web UI

---

## Problem 8: Transmit thread creation failure

### Matching Logs

```
emaild [ER] unable to create trans thread,err(<error code>)
```

### Diagnosis

emaild cannot create the email transmit thread; emails cannot be sent out.

### Cause

1. System thread resources exhausted
2. pthread library anomaly

### Solution

1. Perform device restart via Web UI
2. If it persists, contact after-sales

---

## Problem 9: Out of memory

### Matching Logs

```
emaild [ER] <function name> out of memory.
```

### Diagnosis

SMTP client memory allocation failed during base64 encoding or other operations.

### Cause

1. Insufficient system memory
2. Email content too large, exceeding available memory

### Solution

1. Perform device restart via Web UI
2. Reduce email notification content size

---

## Problem 10: JSON cloud config parse error

### Matching Logs

```
emaild [ER] static config loads json error,<line>:<error description>
emaild [ER] get receiver is not a array!
emaild [ER] request json is NULL
emaild [ER] request json argument is invalid
emaild [ER] request json is invalid
```

### Diagnosis

Cloud-delivered emaild config JSON format error or parameters invalid.

### Cause

1. JSON is empty or format invalid
2. Recipient list is not a JSON array format

### Solution

1. Check email config JSON format via cloud platform
2. Ensure recipient list uses JSON array format

---

## Normal INFO Logs (No Action Needed)

```
emaild [IN] my_cb_timer
emaild [IN] Received SIGUSR1; start/stop tracing to <file>
emaild [IN] sigchld_cb
emaild [IN] MSG: 0x<type> from service <ID>
emaild [IN] Creating SSL connection to host
emaild [IN] SSL connection using <cipher suite>
emaild [IN] email inform <alert code>
emaild [IN] email thread runing
emaild [IN] email thread exited. <N> emails success,<M> emails failed
emaild [IN] unable to create email
emaild [IN] email send failed,err(<error code>)
emaild [IN] reason:trans queue is full
emaild [IN] send email failed;
emaild [IN] SERVER/FROM/TO/TITLE/CONTENT
emaild [WA] Received SIGHUP; restarting...
```

---

## General Troubleshooting Information Collection

1. All `emaild [ER]` and `emaild [WA]` lines in device logs
2. Complete logs for 2 minutes before and after the fault
3. Current email notification config (SMTP server, sender, recipient, SSL config)
4. Whether there were alert events triggering email sends at or before the fault time
5. SMTP server reachability and status
