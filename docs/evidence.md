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
