# Diagnostic Playbooks

Use one primary playbook per investigation. Pull in a second playbook only when the first playbook produces evidence that clearly crosses fault domains.

This file is the index only. Do not execute diagnostics from this page; open the routed playbook and follow that file.

- [connectivity.md](connectivity.md): no internet, DNS failure, packet loss, or intermittent reachability
- [cellular.md](cellular.md): SIM, carrier registration, APN, modem session, or radio signal issues
- [wan.md](wan.md): wired uplink failure, WAN DHCP/static problems, gateway loss, or route issues
- [lan.md](lan.md): DHCP leases, local subnet reachability, client access, or switch-port behavior
- [performance.md](performance.md): low throughput, high latency, jitter, or slow application traffic
- [log.md](log.md): logs or alarms are the clearest starting point and the failing subsystem is unknown
- [config-audit.md](config-audit.md): runtime behavior does not match intended configuration
- [firmware-release.md](firmware-release.md): official firmware availability, changelog analysis, upgrade advice, version-specific download URLs, approved firmware upgrade execution, or other vendor release artifacts
