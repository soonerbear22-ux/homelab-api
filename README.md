# Homelab API

A FastAPI tool server that connects Open WebUI to live homelab status and Prometheus history. Built for Logan's Basecamp environment to answer operational questions using current data.

This repository contains a sanitized source snapshot recovered from the working project, plus its deployment-verification script. The original integration was tested in Open WebUI. This public copy replaces private endpoint constants with environment variables; that publication change has not been deployed to the running lab.

## Tools

| Operation | GET path | Purpose |
| --- | --- | --- |
| `get_docker_status` | `/docker/status.json` | Container names, states, images |
| `get_host_status` | `/host/status.json` | Uptime, load, RAM, swap, filesystem usage |
| `get_top_processes` | `/processes/top.json` | Processes sorted by memory |
| `get_memory_history` | `/history/memory.json` | Memory history from Prometheus |
| `get_cpu_history` | `/history/cpu.json` | CPU history from Prometheus |
| `get_disk_io_status` | `/disk/io.json` | Disk activity and bottleneck heuristics |

History accepts `1h`, `6h`, `12h`, or `24h`. FastAPI publishes the discovery schema at `/openapi.json`. The additional `/health` route is excluded from tool discovery.

## Engineering work demonstrated

- Migrated a custom diagnostic service to FastAPI with stable OpenAPI operation IDs.
- Staged and checked endpoints before switching the live integration.
- Extended the API with path-to-device resolution for disk metrics.
- Verified discovery and tool use in a fresh Open WebUI conversation.
- Removed obsolete legacy tool wrappers after confirming the new integration.

## Read next

- [Architecture](docs/architecture.md)
- [Configuration and validation](docs/operations.md)
- [Security boundaries and known limitations](docs/security.md)
- [Evidence and publication changes](docs/evidence.md)

Related: [Local AI Lab](https://github.com/soonerbear22-ux/local-ai-lab) · [Basecamp](https://github.com/soonerbear22-ux/basecamp-homelab)

This is a portfolio source snapshot, not a hardened general-purpose monitoring product. Read the security and runtime requirements before deploying.
