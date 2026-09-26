# Security and known limitations

[Home](../README.md)

## Access boundary

There is no inbound authentication in the application. Restrict it to intended clients with an authenticated gateway and network policy. Responses may expose internal addresses, guest IDs, processes, source text, and operational errors. Do not publish live responses or expose the API directly to the Internet.

Docker access is privileged even with a read-only socket mount. GET-only route definitions do not constrain what a compromised process can do. Likewise, using a Proxmox token for GET requests does not prove the token's assigned permissions are read-only; validate least privilege separately.

The public copy requires private endpoints through environment variables and enables Proxmox certificate verification. A private CA bundle can be supplied. This public adaptation is not a deployed remediation; live trust configuration remains private.

## Data quality and interpretation

- A responding process is not proof of dependency health.
- Successful semantic search does not prove that every expected source exists.
- Query similarity scores do not establish truth; retrieved text may be stale or contain untrusted instructions.
- The search helper checks response shape but does not enforce exactly 2560 dimensions on every vector.
- Some absent/non-finite metrics become zero; this can resemble inactivity.
- CPU/memory history uses the original job selector and the first series.
- Disk severity escalation and thresholds remain heuristic.
- The audit's completion count reflects returned component groups, including groups with unhealthy nested results.
- Expected guests and containers are hardcoded for this lab.
- Several derived diagnostic flags express conservative conclusions or unverified states, not exhaustive fault detection.
- Dependencies are unpinned; error strings can reveal internal details.

Review these limitations before generalizing the implementation. Unit checks do not replace authentication, integration, recovery, or load testing.

Private credentials, addresses, tailnet names, raw knowledge, and audit exports remain excluded from Git.
