# Reboot

Use this reference only when the user explicitly requests a reboot or confirms it as a recovery step.

## CLI

```bash
agent-cli reboot
```

## MCP

Use the dedicated `reboot` MCP tool with its standard input object for the selected device.

## Required Workflow

1. Confirm the target device.
2. Confirm the reboot intent explicitly.
3. Execute the reboot.
4. Wait for reconnect.
5. Verify `status basic` after the device returns.

## Note

`reboot` happens immediately. Do not hide that impact from the user.
