# Cellular

Use when the user wants to check cellular status, inspect cellular signal, understand cellular connectivity, or troubleshoot a cellular issue such as cannot connect, frequent disconnection, or high latency.

Read [tool-contract.md](tool-contract.md) only when the exact MCP call shape matters.

## Step 1: Status Gate

1. Start with `status cellular` only.
2. If `status = up`, treat the cellular link as healthy only when all of the following are true:
   - `modem_info.level >= 2`
   - `modem_info.sinr` or `ss_sinr >= 3dB`, or the field is empty
   - `data_usage.*.monthly_data.status` is not `exceed`
3. If the link is healthy and the user is only checking status, report that the cellular connection is normal and stop there. Include the key status fields you observed, such as network type, signal strength, operator, active SIM, and data-usage status.
4. Continue to Step 2 if any of the following apply:
   - `status` is `down`, `disabled`, or `detect_fail`
   - `modem_info.level <= 1`
   - `modem_info.sinr` or `ss_sinr < 3dB`
   - `data_usage.*.monthly_data.status = exceed`
   - the user reports disconnections or high latency

## Step 2: Fetch Config and Logs

1. Fetch these in parallel as needed:
   - `config get cellular`
   - `log redial --line 1000`
2. If 1000 lines do not contain the CONFIGURE phase markers `sim1 received event COMPLETED at state CONFIGURE` or `detecting modem serving cell info`, continue with the log window you have. Do not block on reaching the startup phase when the device is stuck looping in NETSEARCH.

## Field Guide

Use these fields as the first reference when interpreting `status cellular`:

| Field path | Key enums or notes |
| --- | --- |
| `status` | `up` connected, `down` not connected, `detect_fail` link probe failed, `disabled` cellular disabled |
| `link_mode` | `active` primary link, `standby` backup |
| `modem_info.sim` | `1` SIM1, `2` SIM2, `3` eSIM |
| `modem_info.reg_status` | `0` not registered, `1` registered home, `5` registered roaming |
| `modem_info.network` | `5G`, `4G`, `3G`, `2G` |
| `modem_info.submode` | `SA`, `NSA`, `LTE`, `WCDMA`, `TD-SCDMA`, `CDMA`, `GSM` |
| `modem_info.level` | Signal bars 0 to 4, where 0 is no signal and 4 is excellent |
| `modem_info.sinr` / `ss_sinr` | `>= 25dB` excellent, `>= 16dB` good, `>= 11dB` fair, `>= 3dB` poor, `< 3dB` severe interference |
| `modem_info.ss_rsrp` / `rsrp` | Prefer `ss_rsrp` for 5G or 4G; values below `-115dBm` are weak |
| `modem_info.apn` | Present only when cellular is connected; empty while disconnected, so do not use it to prove APN is configured |
| `data_usage.*.monthly_data.status` | `exceed` quota exceeded, `normal` ok, `disabled` policy disabled |

## Scenario 1: Cannot Connect

Use this scenario when `status = down`, `status = disabled`, or the status gate already showed a registration or signal problem severe enough to prevent attachment.

### 1.1 Is cellular disabled?

- If `status = disabled`, tell the user cellular is disabled and ask whether they want to enable it.
- If `status = down`, continue with the checks below.

### 1.2 Is the SIM card detected?

Search the redial log for `AT+CPIN` responses:

- `+CPIN: READY`: SIM is detected. Continue.
- `ERROR` or no response: SIM is not detected.

If the SIM is not detected:

- Check `dual_sim.enabled` and `dual_sim.priority` in `config get cellular`.
- If dual-SIM is enabled, the modem may have switched to an empty slot.
- Tell the user clearly that no SIM card was detected in the slot indicated by the log, and ask them to check that slot.

### 1.3 Signal strength

Prefer signal fields from `status cellular`, especially values under `modem_info` such as `rsrp`, `ss_rsrp`, `sinr`, and `dbm`.

If those fields are empty or `dbm = 0`, search the redial log near `detecting modem serving cell info` for a signal line like:

```text
sim1 LTE mcc:460 mnc:11 cellid:9D53512 tac:EA01 pci:103 earfcn:2452 band:B5 rssi:-89 rsrp:-102 rsrq:-14 sinr:-2
```

That line appears during the CONFIGURE phase and may be absent when the device is only looping in NETSEARCH.

Signal thresholds:

| Field | Radio | level=4 | level=3 | level=2 | level=1 |
| --- | --- | --- | --- | --- | --- |
| `ss_rsrp` / `rsrp` | 5G or 4G | `>= -95dBm` | `>= -105dBm` | `>= -115dBm` | `< -115dBm` |
| `rscp` | 3G | `>= -49dBm` | `>= -73dBm` | `>= -97dBm` | `< -97dBm` |
| `rssi` | 2G | `siglevel >= 12` | `>= 8` | `>= 5` | `< 5` where `siglevel = (rssi + 110) / 2` |

Interpretation:

- `sinr` or `ss_sinr < 3dB`: severe interference may prevent registration.
- Signal unavailable in both status and logs: ask the user to check antenna connections and whether the device is in a shielded environment.
- `level <= 1`: weak signal may prevent registration; suggest repositioning the antenna.

### 1.4 Network registration status

Search the redial log for `AT+C5GREG?`, `AT+CEREG?`, `AT+CGREG?`, and `AT+CREG?`, then parse the `stat` value:

| stat | Meaning | Action |
| --- | --- | --- |
| `0` | Not registered, not searching, or stopped after failure | Check the SIM card first, then signal |
| `1` | Registered on the home network | Registration is normal; continue |
| `2` | Not registered, searching | If this loops in NETSEARCH, check the SIM card first, then signal |
| `3` | Registration rejected | Check the SIM card and carrier state |
| `5` | Registered while roaming | Registration is normal; confirm roaming is expected |
| `8` | Emergency services only | Treat as a SIM-side issue, same as `stat = 3` |

Important rules:

- Any registration failure, including `stat = 0`, persistent `stat = 2`, `stat = 3`, or `stat = 8`, should start with SIM-card investigation before blaming signal or configuration.
- When the SIM has a carrier-side issue, the modem may still attempt roaming registration. If `operator` shows a non-home carrier, do not assume roaming configuration is the root cause until the SIM state is ruled out.
- Use `modem_info.sim` to determine the active slot, then read `modem.<sim>.profile` in config:
  - `profile = auto`: search the redial log for `def_apn:` to confirm the matched APN. If `def_apn` is empty, auto APN matching failed and a manual APN is needed.
  - `profile = 0` through `5`: read `cellular.profile.<N>.apn`. If that field is empty, the APN is not configured and the user needs the correct APN from the carrier.

### 1.5 PDN activation

Locate the PDN activation step in the redial log and identify the activation method:

- `mipc`: typical on MTK platforms such as ODU2012, ODU2002, FWA02, FWA12, and CR602; logs include `mipc`, `MIPC_NW_PS_DETACH`, or `MIPC_NW_PS_ATTACH`
- AT-command activation: Fibocom commonly uses `AT+GTRNDIS`; Quectel commonly uses `AT+QNETDEVCTL`
- PPP: legacy dial-up devices with obvious PPP markers

Locate where activation fails and report the specific failure to the user.

If all checks above pass but the device still cannot connect, tell the user to export the device diagnostic log and contact technical support.

## Scenario 2: Frequent Disconnection

### 2.1 Link probe failure triggering redial

Search the redial log for sdwan or lqm messages that triggered a redial:

- If sdwan initiated the redial, tell the user the cellular link dropped because link probing failed and ask them to check whether the probe target is reachable.

### 2.2 Kicked by the network

Search backward from the disconnect point for:

- `modem deact cid`
- `check qnetdevstatus error`

If either appears, tell the user the network side dropped the connection. Possible causes include idle timeout, a modem switching to a network type unsupported by the SIM, or a modem anomaly. Recommend exporting the diagnostic log and contacting technical support.

## Scenario 3: High Latency

### 3.1 Signal quality

- `sinr` or `ss_sinr < 3dB`, or negative values: severe interference is the primary cause of high latency.
- `5G` normally outperforms `4G`; LTE TDD has limited uplink bandwidth, so sustained video upload can saturate it.
- Frequent `cell_id` or `pci` changes indicate frequent cell handover, such as NSA to LTE switching, which can cause latency spikes.

### 3.2 Bandwidth saturation

Ask the user to check whether any endpoint is consuming heavy cellular bandwidth, and suggest QoS or rate-limiting policies if needed.

## Handoff Rules

- Cellular session is healthy but no usable uplink address or route appears: hand off to [wan.md](wan.md).
- Cellular session is healthy and only domain lookups fail: hand off to [connectivity.md](connectivity.md).
- Repeated configuration or policy mismatch is the clearest issue: hand off to [config-audit.md](config-audit.md).

## Reporting Rules

- Use the skill-wide output contract from `SKILL.md`: `Summary`, `Findings`, `Evidence`, `Gaps`, and `Next actions`.
- In `Summary`, name the issue type explicitly when applicable: cannot connect, frequent disconnection, or high latency.
- In `Evidence`, include the exact status fields or redial-log lines that support the conclusion.
- In the cannot-connect scenario, if `status = down` and registration failed, the first item in `Next actions` must be to check the SIM card with the carrier: confirm the account is active, not suspended, and real-name verified, and suggest testing the SIM in a phone to confirm it can register normally.
- If the issue cannot be identified, tell the user to export the device diagnostic log and contact technical support.
