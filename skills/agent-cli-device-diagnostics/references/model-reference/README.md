# model-reference

InHand Networks embedded router/gateway firmware code reference documentation.

## Reading Conventions

- **Agent entry**: `index.md` → model `index.md` → specific document
- Each document's first paragraph contains a one-line "Applicable" description
- Second-level headings (`##`) are independent topics; do not modify them arbitrarily to maintain deep link stability
- No screenshots; status/UI described in text
- Code blocks labeled with language (`c`, `bash`, `json`, etc.)
- Cross-file references use relative paths
- Primarily in English, technical terms retained (e.g., IPC, daemon, ACL, NAT)

## Directory Structure

```
model-reference/
├── README.md              # This file
├── index.md               # Agent entry: product model list and navigation links
├── common/                # Cross-model common content
│   └── architecture.md    # Overall architecture (IPC model, build system, shared library hierarchy)
└── <MODEL>/               # Model directory (uppercase name, e.g., ODU12)
    ├── index.md           # Model entry: service list, model-specific conventions
    └── <service>.md       # Individual service documents
```
