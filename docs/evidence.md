# Evidence and publication differences

[Home](../README.md)

## September 26 source refresh

The published application was refreshed from the inspected deployed source, replacing the earlier six-tool snapshot. Version 1.1.0 contains thirteen operations: the original diagnostics plus semantic search, AI-worker status, knowledge health, three Proxmox operations, and a combined audit.

Docker inventory now falls back to configured image information when detailed image metadata is unavailable. Schema descriptions contain routing and conservative interpretation guidance for tool-using assistants.

## Fresh read-only result

At 21:42 UTC, the existing deployed combined audit returned all seven component groups. All three expected guests and eleven expected Docker containers were running. Proxmox reads succeeded, an embedding request returned 2560 dimensions, Qdrant was green, and a semantic query returned a result.

The collection held 101 points. Direct inspection found only master knowledge (19) and operations knowledge (82). The morning expansion report's 235 points and 28/28 retrieval checks are historical; processed runbooks survived but were absent from the later index. Cause is unverified.

## Public adaptations

- Replace private endpoints, network hosts, and the upstream token identity with environment configuration.
- Retain generic host/job/collection defaults.
- Enable Proxmox certificate verification, optionally using a configured CA bundle.
- Update example configuration and staging verification for the current operation set.
- Add mocked regression tests; all eleven passed.

The live deployment was not modified. Public certificate/configuration adaptations have not been deployed or verified through a full new container rollout. The historical Dockerfile remains unpinned.

See [operations](operations.md) for test scope and [security](security.md) for known limitations.


## October 3 repository alignment

The public audit source was updated to recognize six current guests: core-services (100), Pi-hole (101), ai-worker (102), Jellyfin (103), media automation (104), and Arda (105). Regression coverage now asserts that all six are represented in the derived guest-state summary.

At the time of repository alignment, the live deployment still required separate verification. The subsequent deployment evidence is recorded below.

## October 3 live six-guest deployment

At 04:14:34 UTC on October 3 (11:14:34 p.m. America/Chicago on October 2), the running API was verified after a scoped rebuild and recreation of only `homelab-api`.

Live host source matched the previous container and compiled correctly. Both still expected guests 100–102. Neither suspected typo was present. The host change added only guests 103, 104, and 105 to `expected_guests`; it did not replace private runtime configuration with the public source.

Before deployment, the original source, actual running image, and other-container identity/start-time snapshot were preserved. The rebuilt image passed application imports, source hashing, health-function validation, the thirteen GET-only OpenAPI operations, JSON serialization, and thirteen isolated audit scenarios covering all guests running and each guest missing or stopped. The full pytest suite was not run in this deployment session.

After deployment:

- `GET /health` returned `{"status": "ok"}`.
- `GET /audit/full.json` retrieved all seven component groups.
- The derived guest summary expected six guests, with all six present and running.
- The knowledge pipeline confirmed operational semantic retrieval.
- Live host and running-container source hashes matched.
- The ten other core-services containers retained their IDs and start times.

The existing Dockerfile remains unpinned. This rebuild resolved FastAPI 0.142.2, Uvicorn 0.54.0, Docker SDK 7.2.0, and Requests 2.34.2. A dependency lock and complete verification of the separate public configuration/certificate adaptations remain follow-up work.

Rollback material is retained privately on the deployment host. No credentials, private addresses, overlay identities, or raw private configuration are published here.

## October 3 Hornburg API candidate

A separate candidate was built from the deployed private source, changing only `PVE_NODE` from `basecamp` to `hornburg`. Cached dependency layers were reused. With external Docker/Proxmox dependencies mocked and networking disabled, the candidate passed import, OpenAPI serialization, new-node selection, and host/guest/storage response-label checks.

The candidate is **prepared only**. The production API source, running container and native Proxmox node still use `basecamp`. The existing endpoint paths and operation IDs are preserved for connector compatibility. Public configuration and TLS adaptations remain separate from the deployed private source.

The operator approved the outage conditional on recovery testing, but Remote Desktop Commander's configured host-reboot restriction blocks cutover execution. See the [maintenance record](https://github.com/soonerbear22-ux/basecamp-homelab/blob/main/docs/hornburg-rename-preflight.md). A future deployment must repeat the full live six-guest/seven-component audit and semantic retrieval checks.
