# Evidence and publication changes

[Home](../README.md)

The source was recovered from the LocalAI/Docker System project mirror. That source remained unchanged during publication.

The migration record documents a staged FastAPI conversion and successful Open WebUI host-status tool use. A follow-up records disk I/O support, endpoint verification, schema refresh, and a successful fresh-chat disk check. Legacy tool wrappers were removed after integration.

A recorded disk snapshot indicated low utilization and no detected bottleneck at that moment. This repository does not treat a single snapshot as a benchmark or availability guarantee.

## Changes for the public copy

- Replaced the private Prometheus URL and instance with required environment variables.
- Made the host and job labels configurable while retaining the original generic defaults.
- Required an explicit staging URL in the verification script.
- Added an example environment file, ignore rules, and documentation.

The rest of the recovered application behavior is preserved. These publication changes are not represented as having been deployed to Basecamp.

## Follow-up

Pin and test dependencies, add authentication at the intended trust boundary, distinguish missing metrics from zero, review severity escalation, and test with representative device mappings. Add regression tests before changing those behaviors.
