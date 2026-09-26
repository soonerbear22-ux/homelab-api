# Configuration and verification

[Home](../README.md)

## Runtime

The recovered Dockerfile uses Python 3.12, Linux `procps`, FastAPI, Uvicorn, Docker SDK, and Requests. Its dependencies remain unpinned as in the inspected deployment. A production lockfile and full rebuild test are follow-up work.

The application initializes the Docker client at import time. Supply its intended daemon connection and host visibility deliberately. No privileged turnkey Compose file is included.

## Public configuration

| Variable | Purpose |
| --- | --- |
| `PROMETHEUS_URL`, `PROMETHEUS_INSTANCE` | Metrics endpoint and disk target selector |
| `PROMETHEUS_JOB` | Disk-query job; defaults to core-services |
| `HOMELAB_HOST` | Output label; defaults to core-services |
| `PVE_URL` | Proxmox base URL |
| `PVE_TOKEN_ID`, `PVE_TOKEN` | Private upstream authentication; keep outside Git |
| `PVE_CA_BUNDLE` | Optional trusted CA bundle path; otherwise standard certificate verification |
| `EMBEDDING_URL` | Full embedding request URL, including the embed path |
| `QDRANT_URL`, `QDRANT_COLLECTION` | Database base URL and collection; collection defaults to homelab_knowledge |
| `AI_WORKER_LAN_HOST`, `AI_WORKER_OVERLAY_HOST` | Hosts for the two TCP reachability checks |
| `AI_WORKER_EMBEDDING_URL` | Base URL for the separate HTTP health check |

Required endpoint values fail fast when absent. The example file uses reserved domains and empty credentials; the app does not load it automatically.

CPU/memory history retains the original core-services job and first-series behavior. Proxmox node, expected VM IDs, and expected container names are still lab-specific constants. Configurable endpoints do not make this a multi-tenant service.

## Local regression checks

```text
python -m pip install -r requirements-test.txt
python -m pytest tests -q
```

Eleven tests passed during publication. External services and the Docker client are mocked; no production changes occur. Tests cover the thirteen-operation schema, invalid inputs, retrieval provenance, image metadata failure, embedding failure, partial audits, interpretation boundaries, and Proxmox certificate verification.

## Deployment verification

Run `python verify_stage.py BASE_URL` against an authorized staging environment with the intended dependencies. The verifier checks discovery, route responses, actual retrieval, pipeline health, combined-audit results, and invalid-query rejection. Use `--expected-source` to require a known document in the search results.

The updated verifier was syntax-checked; its complete staging run has not been performed against a newly deployed public copy. The existing live audit was exercised separately.

Refresh Open WebUI tool discovery after schema changes and test a fresh conversation. An old chat can retain earlier operation definitions.
