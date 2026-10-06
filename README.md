# Homelab API

A FastAPI/OpenAPI tool server connecting Open WebUI to live infrastructure telemetry and semantic homelab knowledge. Built for the Middle-earth Homelab infrastructure, now hosted on Hornburg.

**Updated September 26, 2026 — application version 1.1.0.** This public source is a sanitized copy of the inspected deployment: thirteen GET operations, robust Docker inventory, retrieval, dependency health, Proxmox inventory, and a combined audit.

## Operations

| Operation | GET path | Purpose |
| --- | --- | --- |
| `get_docker_status` | `/docker/status.json` | Container state and image metadata fallback |
| `get_host_status` | `/host/status.json` | Uptime, load, RAM, swap, filesystem use |
| `get_top_processes` | `/processes/top.json` | Processes by memory use |
| `get_memory_history` | `/history/memory.json` | Prometheus memory history |
| `get_cpu_history` | `/history/cpu.json` | Prometheus CPU history |
| `get_disk_io_status` | `/disk/io.json` | Disk activity and bottleneck heuristics |
| `search_homelab_knowledge` | `/knowledge/search.json` | Query embeddings and provenance-bearing Qdrant results |
| `get_ai_worker_status` | `/ai-worker/status.json` | TCP reachability and embedding-service HTTP health |
| `get_knowledge_pipeline_health` | `/knowledge/health.json` | Real embedding, collection check, and vector query |
| `get_basecamp_status` | `/basecamp/status.json` | Authenticated Proxmox host telemetry |
| `get_basecamp_guests` | `/basecamp/guests.json` | VM/LXC inventory and resource observations |
| `get_basecamp_storage` | `/basecamp/storage.json` | Proxmox storage inventory |
| `get_full_homelab_audit` | `/audit/full.json` | Seven component groups, partial errors, conservative derived facts |

The additional `/health` route is excluded from discovery. History accepts `1h`, `6h`, `12h`, or `24h`. Search requires `query`; `limit` is 1–10, default 5.

## Engineering work

- Migrated custom tools to stable OpenAPI operations and tested discovery in Open WebUI.
- Added semantic search using Qwen3-Embedding-4B and Qdrant with source/section metadata.
- Added a combined audit that retains successful components when another component fails.
- Kept ambiguous metrics separate from confirmed faults, including VM memory accounting and Qdrant index counters.
- Preserved container inventory when an image metadata lookup fails.
- Added eleven mocked regression checks for contracts, validation, provenance, failure handling, and certificate verification.

## Current infrastructure alignment — October 6, 2026

The Proxmox node is `hornburg`; `/basecamp/*` routes and operation IDs intentionally remain for connector compatibility. Six-guest live deployment was verified in the October 3 [completion evidence](docs/evidence.md). The independent [monitoring triangle](https://github.com/soonerbear22-ux/basecamp-homelab/blob/main/docs/monitoring.md) is verified outside this API; HTTP `/health` alone does not establish every downstream dependency. This documentation pass does not rebuild/deploy the API or synchronize Local AI material.

The repository audit logic now recognizes the current six-guest topology (100–105), including Jellyfin, media automation, and Arda. This repository change does not by itself prove the live deployed API has been updated.

A fresh deployment audit retrieved 7/7 component groups. It found the knowledge pipeline operational against **101 points / two baseline sources**, which differs from the earlier expansion report. [Evidence and limits](docs/evidence.md) explain the discrepancy.

## Read next

- [Architecture](docs/architecture.md)
- [Configuration and verification](docs/operations.md)
- [Security and limitations](docs/security.md)
- [Evidence and publication differences](docs/evidence.md)

Related: [Local AI Lab](https://github.com/soonerbear22-ux/local-ai-lab) · [Middle-earth Homelab](https://github.com/soonerbear22-ux/basecamp-homelab)

The public copy externalizes private endpoints and enables Proxmox certificate verification. These publication adaptations have not been deployed to the running lab. This repository is a lab-specific implementation, not a hardened general-purpose monitoring service.
