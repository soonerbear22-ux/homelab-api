# Configuration and validation

[Home](../README.md)

## Runtime prerequisites

Python 3.12, Linux, a reachable Docker daemon, `procps`, and Prometheus with the expected Node Exporter metrics. The recovered Dockerfile installs FastAPI, Uvicorn, Docker SDK, and Requests. Dependencies are not pinned in this historical snapshot; a tested lockfile remains follow-up work.

Supply these environment variables explicitly:

| Variable | Meaning |
| --- | --- |
| `PROMETHEUS_URL` | Required Prometheus base URL |
| `PROMETHEUS_INSTANCE` | Required target instance label |
| `PROMETHEUS_JOB` | Job label; defaults to core-services |
| `HOMELAB_HOST` | Output label; defaults to core-services |

`.env.example` contains reserved example domains. Copy values into your deployment mechanism; the application does not load an environment file automatically.

The server uses Uvicorn on port 8091. Host visibility, Docker access, network restrictions, and authentication must be configured separately. No privileged turnkey Compose file is supplied.

## Staging verification

Run `python verify_stage.py BASE_URL` against an authorized staging deployment. The script checks exactly six schema operations, GET-only discovery, successful JSON responses, history points, disk resolution, and rejection of an invalid history range.

The script expects the original `core-services` output label and a populated metric history. Change that assertion if intentionally adapting the host label. It does not test authorization, recovery, all error cases, or every disk heuristic.

After a schema change, refresh the Open WebUI connection and test in a fresh chat. The original disk-tool rollout encountered stale discovery in an existing conversation.

## Publication validation

Public files are syntax-checked and screened for private addresses. The staging script is retained as historical verification tooling; a new live deployment is not part of this publication task.
