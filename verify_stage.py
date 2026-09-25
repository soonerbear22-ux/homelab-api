import requests
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: python verify_stage.py BASE_URL")
base = sys.argv[1].rstrip("/")
schema = requests.get(f"{base}/openapi.json", timeout=5).json()
expected = {
    "/docker/status.json": "get_docker_status",
    "/host/status.json": "get_host_status",
    "/processes/top.json": "get_top_processes",
    "/history/memory.json": "get_memory_history",
    "/history/cpu.json": "get_cpu_history",
    "/disk/io.json": "get_disk_io_status",
}
assert set(schema["paths"]) == set(expected), schema["paths"].keys()
for path, operation_id in expected.items():
    operation = schema["paths"][path]
    assert set(operation) == {"get"}, operation
    assert operation["get"]["operationId"] == operation_id, operation
    response = requests.get(f"{base}{path}", timeout=15)
    response.raise_for_status()
    payload = response.json()
    assert payload["host"] == "core-services", payload
    if path.startswith("/history/"):
        assert payload["range"] == "1h" and payload["points"], payload
    if path == "/disk/io.json":
        assert payload["metrics_device"] and "bottleneck_detected" in payload, payload
    print(f"OK {path}: {operation_id}")
assert requests.get(f"{base}/history/cpu.json?range=bad", timeout=5).status_code == 422
print("OK invalid range rejected")
