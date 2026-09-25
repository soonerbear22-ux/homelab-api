# Security and known limitations

[Home](../README.md)

## Trust boundary

The application has no built-in authentication. Restrict access with an authenticated gateway and network policy before using it beyond a controlled lab. Do not expose it directly to the public Internet.

Docker socket access is privileged even if the socket is mounted read-only. GET-only FastAPI routes do not constrain what a compromised process could do through the Docker client. Host process and filesystem visibility also deserve explicit review.

Responses reveal container names, images, process information, and operational metrics. Treat those responses as private even though this source snapshot is public.

## Data-quality limitations

- Some missing or non-finite Prometheus values become zero, which can resemble healthy inactivity.
- A health response proves the API process responds; it does not prove Docker or Prometheus health.
- Process, root filesystem, and device views depend on the container's namespaces and mounts.
- Disk bottleneck labels are heuristics, not validated diagnostic guarantees. Severity escalation ordering should be reviewed.
- Dependencies are unpinned and need testing before reproducible release use.
- Import-time Docker initialization means the daemon connection is a startup dependency.
- Metric selectors use deployment-controlled labels; configuration is trusted input.

These are documented limitations of the recovered implementation, not claims that remediation is deployed.

## Publication policy

No private addresses, tailnet names, credentials, live configuration, or raw operational exports belong in this repository. Keep environment values outside version control.
