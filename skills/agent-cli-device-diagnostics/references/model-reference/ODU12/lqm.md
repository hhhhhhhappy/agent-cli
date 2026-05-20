# lqm — Problem Diagnosis

> Applicable: lqm (Link Quality Monitoring) service self-anomaly (thread creation/cancellation failure, runtime state persistence failure), ICMP/ICMPv6 detection error, DNS detection config/resolution failure, TCP detection failure, detection target unreachable, socket creation failure, cloud JSON config error.

## Log Format Reference

| Level | Meaning | Requires Attention |
|-------|---------|-------------------|
| [ER] | ERROR | Yes |
| [WA] | WARNING | Yes |
| [IN] | INFO | For reference only |

> Note: lqm service log prefix is `lqm`.

---

## Problem 1: Detection thread creation/management failure

### Matching Logs

```
lqm [ER] <function name>(<line>):malloc node failed
lqm [ER] pthread_detach/pthread_setcancelstate/pthread_setcanceltype failed.
lqm [ER] detect/update/dequeue thread create failed
lqm [ER] threads create failed / thread create failed.
lqm [ER] pthread_mutex_init/pthread_cond_init failed.
lqm [ER] semget err / SETVAL INIT ERR
```

### Solution

1. Perform device restart via Web UI
2. If persistent, contact after-sales

---

## Problem 2: Detection thread exit/cancellation failure

```
lqm [ER] <function name>(<line>):cancel icmp/dns/tcp detect thread failed
lqm [ER] pthread cancel <thread ID> failed ret=(<return value>:<error description>).
```

---

## Problem 3: Socket creation/close error

### Matching Logs

```
lqm [ER] sockfd on <interface> create failed.
lqm [ER] sockfd6 on <interface> create failed.
lqm [ER] close sockfd(<fd>) error / socket error / setsockopt error.
lqm [ER] bind src_ip faild / bind src_ipv6 faild
```

### Solution

1. Check if the detected interface has a valid IP address
2. Re-save LQM config via Web UI
3. Perform device restart via Web UI

---

## Problem 4: ICMP/ICMPv6 detection send-receive error

```
lqm [ER] icmp/icmpv6 packet send on <interface>(<target IP>) failed.
lqm [ER] proto4/proto6 sendto error / addr_helper error.
lqm [ER] packet is not icmp packet / invalid icmp/icmpv6 packet / ICMP detect info wrong!
```

### Solution

1. Check LQM detection target IP is reachable via Web UI
2. Re-save LQM config via Web UI
3. Check system time accuracy (NTP sync)

---

## Problem 5: DNS detection config validation failure

```
lqm [ER] lqm_dns_validate_config, config is NULL / dns_server1/2 are empty / domain1/2 are empty
lqm [ER] dns_server1/2 is invalid / timeout/detect_interval/retry_interval/max_retry_count is invalid
```

### Solution

1. Check and complete DNS detection config via Web UI
2. Ensure timeout > 0, interval > 0, etc.

---

## Problem 6: DNS resolution failure

```
lqm [ER] lqm_dns_resolve_hostname_by_iface, no DNS server on <interface>
lqm [ER] failed to resolve <domain> on <interface>
lqm [ER] domain <domain> resolve failed on <interface>, keep old ip
```

---

## Problem 7: Detection interface/target config error

```
lqm [ER] get iface err by gl_uplink_ifnames <interface name>
lqm [ER] vif <interface> ipv4 address is null.
lqm [ER] detect is disabled / detect_mode is not supported
lqm [ER] detect target ip init failed,thread exit
```

### Solution

1. Check LQM detection interface config via Web UI
2. Ensure detection interface has valid IP and is UP
3. Confirm LQM is enabled

---

## Problem 8-12: System command / runtime state / IPC / JSON / TCP errors

Refer to problem descriptions 8-12 in the original full documentation.

---

## Normal INFO Logs (No Action Needed)

```
lqm [IN] MSG: 0x<type> from service <ID>
lqm [IN] Link quality monitoer enabled/disabled.
lqm [IN] <interface>: re-resolve detect target (<domain>), target_ip=<IP>
lqm [IN] use (<target IP>) detect target ip,create sockfd(<fd>) of <interface>
lqm [IN] domain <domain> resolved to <IP> on <interface>
lqm [IN] ICMP/ICMPv6 time exceeded packet received, so keep rtt=0.
```
