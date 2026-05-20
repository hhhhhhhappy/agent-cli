# InHand Firmware — Problem Diagnosis Knowledge Base

> Applicable: When the device exhibits functional anomalies, use logs and symptoms to locate problems and find solutions.

## Diagnosis Process

```
Device Logs / Abnormal Symptoms
        │
        ▼
Select the model directory (e.g., ODU12/)
        │
        ▼
Locate the diagnostic document by module name (e.g., firewall.md)
        │
        ▼
Match specific sections (## headings) by log keywords
        │
        ▼
Execute the solution and verify recovery
```

## Search Strategy

1. First get the model from `status basic`, and only enter the matching model directory; do not guess directories when the model directory does not exist.
2. First use the service name/process name in the logs to select a module document, e.g., `NetworkManager`, `lqm`, `syswatcher`.
3. If the service name is unclear, locate the module by symptom keywords in the model directory's `index.md`; if still unclear, stop at the gap and do not batch-open all module documents.
4. After opening a module document, only search for the corresponding `## Problem` section by the error prefix, function name, or key errno in the original log text.
5. Only read one most likely module document at a time; only open the next document when the current document explicitly excludes or points to another service.
6. `common/architecture.md` should only be read when you need to understand IPC, process relationships, or cross-module dependencies.

## Product Models

| Model | Directory | Description |
|-------|-----------|-------------|
| ODU12 | [ODU12/](ODU12/index.md) | 5G Outdoor Unit |

## Common Reference

| Document | Description |
|----------|-------------|
| [common/architecture.md](common/architecture.md) | Overall system architecture reference (helps understand inter-module dependencies and IPC relationships) |

## Document Conventions

- Each document's first paragraph contains a one-line "Applicable" description
- Second-level headings (`##`) are independent diagnostic topics, starting with "Problem N:"
- Each problem includes: **Matching Logs** → **Diagnosis** → **Cause** → **Solution**
