"""Read-only homelab tools exposed as OpenAPI operations."""

from datetime import datetime, timezone
import math
import os
import shutil
import subprocess
import time
from typing import Literal

import docker
from fastapi import FastAPI, Query
import requests

TOOL_ROUTING_POLICY = """
HOMELAB TOOL ROUTING POLICY:

When the user requests a broad status check, health check, audit, inspection, review, or troubleshooting of the Basecamp homelab, autonomously call all relevant live operations needed to answer the request.

For a complete Basecamp homelab audit, use the available live operations to inspect:
- Basecamp Proxmox host status
- Basecamp QEMU and LXC guests
- Basecamp storage
- core-services host status
- core-services Docker containers
- ai-worker reachability and embedding-service status
- homelab knowledge-pipeline health

Use CPU, memory, disk I/O, process, or history operations when they are relevant to evaluating current health or investigating an observed condition.

Do not ask the user which component to inspect first when the user's request already identifies the desired scope. A request to check the entire homelab is sufficient authorization to inspect all available read-only telemetry within that scope.

Do not use ask_user merely to divide a broad homelab request into smaller steps. Call the relevant read-only operations yourself and synthesize their results into one answer.

Use authoritative homelab knowledge search when documented expected state, architecture, configuration, identifiers, procedures, or comparison against documentation is needed. Do not substitute stored documentation for live telemetry when the user asks about current state.

If a requested fact cannot be established by the available operations, report it as not verified rather than asking the user to manually gather information unless that information is actually necessary to continue.
"""

INTERPRETATION_POLICY = """
LIVE DATA INTERPRETATION POLICY:

Use live tools for current state and stored homelab knowledge for documented configuration, architecture, procedures, and expected state. When live observations and documentation differ, clearly distinguish them rather than silently choosing one.

Interpret live telemetry conservatively:
- Report raw observations separately from diagnoses or recommendations.
- Do not diagnose a fault from one unusual or ambiguous metric without corroborating evidence.
- Do not recommend changing resources, configuration, storage, networking, or services solely because one metric appears unusual.
- A running container whose image tag contains 'latest' is not proof that the running image is the newest upstream image.
- Proxmox VM memory values can reflect host-side accounting and may exceed a rounded configured allocation. A value slightly above 100 percent is not by itself proof of memory exhaustion or over-allocation.
- Qdrant points_count and indexed_vectors_count describe different internal states. indexed_vectors_count of 0 does not by itself mean vectors are missing. If semantic vector queries successfully return relevant results, do not recommend reindexing solely because indexed_vectors_count is 0.
- Low storage utilization is not a reason to recommend increasing storage.
- Successful authenticated Basecamp status, guest, or storage queries demonstrate that the Proxmox API is responding to those requests.
- If a tool cannot establish a fact, explicitly say that the fact was not verified instead of inferring it.

Before recommending a corrective action, prefer additional live verification when an available tool can test the suspected problem.
"""

app = FastAPI(
    title="Homelab Live Status",
    version="1.1.0",
    description=(
        "Read-only live status, history, infrastructure telemetry, and "
        "authoritative homelab knowledge for Basecamp.\n\n"
        + TOOL_ROUTING_POLICY
        + "\n"
        + INTERPRETATION_POLICY
    ),
)
client = docker.from_env()
PROMETHEUS_URL = os.environ["PROMETHEUS_URL"].rstrip("/")
HOST = os.environ.get("HOMELAB_HOST", "core-services")
PVE_URL = os.environ["PVE_URL"].rstrip("/")
PVE_TOKEN_ID = os.environ.get("PVE_TOKEN_ID", "")
PVE_TOKEN = os.environ.get("PVE_TOKEN", "")
PVE_NODE = "hornburg"
CORE_SERVICES_JOB = os.environ.get("PROMETHEUS_JOB", "core-services")
PROMETHEUS_INSTANCE = os.environ["PROMETHEUS_INSTANCE"]
Range = Literal["1h", "6h", "12h", "24h"]
RANGE_SECONDS = {"1h": 3600, "6h": 21600, "12h": 43200, "24h": 86400}


def now():
    return datetime.now(timezone.utc).isoformat()


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}


@app.get("/docker/status.json", operation_id="get_docker_status", summary="Get current Docker container status")
def docker_status():
    """List all containers on core-services with name, state, and image."""
    containers = []

    for container in client.containers.list(all=True):
        image_name = None
        image_error = None

        try:
            tags = container.image.tags
            image_name = ", ".join(tags) if tags else container.image.short_id
        except Exception as exc:
            image_error = str(exc)

            # Fall back to image information already present in container attrs.
            try:
                image_name = container.attrs.get("Config", {}).get("Image")
            except Exception:
                image_name = None

            if not image_name:
                image_name = "unavailable"

        item = {
            "name": container.name,
            "status": container.status,
            "image": image_name,
        }

        if image_error:
            item["image_metadata_warning"] = image_error

        containers.append(item)

    return {
        "timestamp": now(),
        "host": HOST,
        "container_count": len(containers),
        "containers": containers,
    }

@app.get("/host/status.json", operation_id="get_host_status", summary="Get current host resource status")
def host_status():
    """Get uptime, load, RAM, swap, and disk usage on core-services."""
    disk = shutil.disk_usage("/")
    with open("/proc/uptime") as f:
        uptime_seconds = float(f.read().split()[0])
    with open("/proc/loadavg") as f:
        load = f.read().split()
    with open("/proc/meminfo") as f:
        meminfo = {key: int(value.strip().split()[0]) for key, value in (line.split(":", 1) for line in f)}
    mem_total = meminfo["MemTotal"]
    mem_available = meminfo["MemAvailable"]
    mem_used = mem_total - mem_available
    swap_total = meminfo["SwapTotal"]
    swap_used = swap_total - meminfo["SwapFree"]
    return {
        "timestamp": now(), "host": HOST, "uptime_seconds": uptime_seconds,
        "load_average": {"1_min": float(load[0]), "5_min": float(load[1]), "15_min": float(load[2])},
        "memory": {
            "total_gb": round(mem_total / 1024**2, 2),
            "used_gb": round(mem_used / 1024**2, 2),
            "available_gb": round(mem_available / 1024**2, 2),
            "used_percent": round(mem_used / mem_total * 100, 1),
        },
        "swap": {"total_gb": round(swap_total / 1024**2, 2), "used_gb": round(swap_used / 1024**2, 2)},
        "disk": {
            "total_gb": round(disk.total / 1024**3, 2),
            "used_gb": round(disk.used / 1024**3, 2),
            "free_gb": round(disk.free / 1024**3, 2),
            "used_percent": round(disk.used / disk.total * 100, 1),
        },
    }


@app.get("/processes/top.json", operation_id="get_top_processes", summary="Get top processes by memory use")
def top_processes():
    """List the ten processes using the most memory on core-services."""
    result = subprocess.run(
        ["ps", "-eo", "pid,ppid,%mem,%cpu,comm", "--sort=-%mem"],
        capture_output=True, text=True, check=True,
    )
    processes = []
    for line in result.stdout.strip().splitlines()[1:11]:
        parts = line.split(None, 4)
        if len(parts) == 5:
            pid, ppid, mem_percent, cpu_percent, command = parts
            processes.append({
                "pid": int(pid), "ppid": int(ppid), "command": command,
                "memory_percent": float(mem_percent), "cpu_percent": float(cpu_percent),
            })
    return {"timestamp": now(), "host": HOST, "sort": "memory_percent_desc", "processes": processes}


def query_prometheus_range(query, range_value):
    range_seconds = RANGE_SECONDS[range_value]
    end_time = int(time.time())
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query_range",
        params={"query": query, "start": end_time - range_seconds, "end": end_time,
                "step": max(30, range_seconds // 120)},
        timeout=10,
    )
    response.raise_for_status()
    return response.json().get("data", {}).get("result", [])


def query_prometheus(query):
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": query},
        timeout=10,
    )
    response.raise_for_status()
    return response.json().get("data", {}).get("result", [])


def prometheus_value(query, default=0.0):
    results = query_prometheus(query)
    if not results:
        return default
    value = float(results[0]["value"][1])
    return value if math.isfinite(value) else default


def resolve_disk(path):
    filesystems = query_prometheus(
        f'node_filesystem_size_bytes{{job="{CORE_SERVICES_JOB}",instance="{PROMETHEUS_INSTANCE}"}}'
    )
    candidates = []
    normalized_path = os.path.normpath(path if path.startswith("/") else f"/{path}")
    for result in filesystems:
        metric = result.get("metric", {})
        mountpoint = metric.get("mountpoint", "")
        device_path = metric.get("device", "")
        if not mountpoint or not device_path.startswith("/dev/"):
            continue
        if normalized_path == mountpoint or normalized_path.startswith(mountpoint.rstrip("/") + "/"):
            candidates.append((len(mountpoint), mountpoint, device_path))
    if not candidates:
        raise ValueError(f"No disk-backed filesystem contains {normalized_path}")
    _, mountpoint, device_path = max(candidates)
    device_name = os.path.basename(device_path)
    if device_path.startswith("/dev/mapper/"):
        mapper_name = device_name
        for block_path in sorted(os.listdir("/sys/class/block")):
            name_path = f"/sys/class/block/{block_path}/dm/name"
            try:
                with open(name_path) as f:
                    if f.read().strip() == mapper_name:
                        device_name = block_path
                        break
            except (FileNotFoundError, PermissionError):
                continue
    return normalized_path, mountpoint, device_path, device_name


def history(query, range_value, metric):
    results = query_prometheus_range(query, range_value)
    values = results[0].get("values", []) if results else []
    points = [{
        "timestamp": datetime.fromtimestamp(float(timestamp), tz=timezone.utc).isoformat(),
        metric: round(float(value), 2),
    } for timestamp, value in values]
    return {"host": HOST, "range": range_value, "metric": metric, "points": points}


@app.get("/history/memory.json", operation_id="get_memory_history", summary="Get memory usage history")
def memory_history(range: Range = Query(default="1h", description="History window: 1h, 6h, 12h, or 24h")):
    """Get memory used percentage over the requested time window from Prometheus."""
    query = '(1 - node_memory_MemAvailable_bytes{job="core-services"} / node_memory_MemTotal_bytes{job="core-services"}) * 100'
    return history(query, range, "memory_used_percent")


@app.get("/history/cpu.json", operation_id="get_cpu_history", summary="Get CPU usage history")
def cpu_history(range: Range = Query(default="1h", description="History window: 1h, 6h, 12h, or 24h")):
    """Get CPU used percentage over the requested time window from Prometheus."""
    query = '100 - (avg by (instance) (rate(node_cpu_seconds_total{job="core-services",mode="idle"}[5m])) * 100)'
    return history(query, range, "cpu_used_percent")


@app.get("/disk/io.json", operation_id="get_disk_io_status", summary="Get current disk I/O and bottleneck status")
def disk_io_status(path: str = Query(default="/", description="Host path to inspect, such as /home or /")):
    """Resolve a host path to its disk and report current throughput, IOPS, utilization, latency, queue depth, and bottleneck status."""
    normalized_path, mountpoint, device_path, device = resolve_disk(path)
    selector = f'job="{CORE_SERVICES_JOB}",instance="{PROMETHEUS_INSTANCE}",device="{device}"'

    read_bps = prometheus_value(f'rate(node_disk_read_bytes_total{{{selector}}}[5m])')
    write_bps = prometheus_value(f'rate(node_disk_written_bytes_total{{{selector}}}[5m])')
    read_iops = prometheus_value(f'rate(node_disk_reads_completed_total{{{selector}}}[5m])')
    write_iops = prometheus_value(f'rate(node_disk_writes_completed_total{{{selector}}}[5m])')
    utilization = prometheus_value(f'rate(node_disk_io_time_seconds_total{{{selector}}}[5m]) * 100')
    queue_depth = prometheus_value(f'rate(node_disk_io_time_weighted_seconds_total{{{selector}}}[5m])')
    io_in_progress = prometheus_value(f'node_disk_io_now{{{selector}}}')
    read_latency = prometheus_value(
        f'rate(node_disk_read_time_seconds_total{{{selector}}}[5m]) / rate(node_disk_reads_completed_total{{{selector}}}[5m]) * 1000'
    ) if read_iops > 0 else 0.0
    write_latency = prometheus_value(
        f'rate(node_disk_write_time_seconds_total{{{selector}}}[5m]) / rate(node_disk_writes_completed_total{{{selector}}}[5m]) * 1000'
    ) if write_iops > 0 else 0.0

    reasons = []
    severity = "none"
    if utilization >= 90:
        severity = "critical"
        reasons.append(f"disk utilization is {utilization:.1f}%")
    elif utilization >= 70:
        severity = "warning"
        reasons.append(f"disk utilization is elevated at {utilization:.1f}%")
    if max(read_latency, write_latency) >= 100:
        severity = "critical" if severity == "none" else severity
        reasons.append(f"I/O latency reached {max(read_latency, write_latency):.1f} ms")
    elif max(read_latency, write_latency) >= 25:
        severity = "warning" if severity == "none" else severity
        reasons.append(f"I/O latency is elevated at {max(read_latency, write_latency):.1f} ms")
    if queue_depth >= 2:
        severity = "warning" if severity == "none" else severity
        reasons.append(f"average queue depth is {queue_depth:.2f}")

    return {
        "timestamp": now(),
        "host": HOST,
        "requested_path": normalized_path,
        "mountpoint": mountpoint,
        "filesystem_device": device_path,
        "metrics_device": device,
        "window": "5m",
        "read_bytes_per_second": round(read_bps, 2),
        "write_bytes_per_second": round(write_bps, 2),
        "read_iops": round(read_iops, 2),
        "write_iops": round(write_iops, 2),
        "utilization_percent": round(utilization, 2),
        "read_latency_ms": round(read_latency, 2),
        "write_latency_ms": round(write_latency, 2),
        "average_queue_depth": round(queue_depth, 3),
        "io_in_progress": round(io_in_progress, 2),
        "bottleneck_detected": bool(reasons),
        "severity": severity,
        "reasons": reasons,
        "assessment": "Potential disk I/O bottleneck detected." if reasons else "No disk I/O bottleneck detected in the current 5-minute window.",
    }

# ----- Homelab semantic knowledge search -----

EMBEDDING_URL = os.environ["EMBEDDING_URL"]
QDRANT_URL = os.environ["QDRANT_URL"].rstrip("/")
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "homelab_knowledge")


def embed_text(text):
    """Generate a 2560-dimensional embedding using Qwen3-Embedding-4B on ai-worker."""
    response = requests.post(
        EMBEDDING_URL,
        json={"inputs": text},
        timeout=30,
    )
    response.raise_for_status()
    vectors = response.json()
    if not vectors or not isinstance(vectors[0], list):
        raise ValueError("Embedding service returned an unexpected response")
    return vectors[0]


@app.get(
    "/knowledge/search.json",
    operation_id="search_homelab_knowledge",
    summary="Search the authoritative Basecamp homelab knowledge base",
    description=(
        "AUTHORITATIVE STORED KNOWLEDGE SEARCH FOR THE BASECAMP HOMELAB. "
        "Use this operation whenever the user asks about their Basecamp homelab, "
        "including Basecamp, core-services, ai-worker, Proxmox VMs or LXCs, "
        "VM and container IDs, LAN or Tailscale addresses, GPUs, Docker services, "
        "ports, storage, networking, Pi-hole, monitoring, AI infrastructure, "
        "knowledge infrastructure, configuration, architecture, operational "
        "procedures, or troubleshooting documentation. "
        "Prefer this operation over generic knowledge-file retrieval for questions "
        "about the Basecamp homelab. This search uses the production semantic "
        "knowledge system backed by Qdrant and Qwen3-Embedding-4B. "
        "Pass the user's complete natural-language question as the query. "
        "Do not guess missing homelab facts when this operation can retrieve them."
    ),
)
def search_homelab_knowledge(
    query: str = Query(
        description=(
            "The user's complete natural-language question about the Basecamp "
            "homelab. Preserve important names and requested details. For example: "
            "'What is ai-worker's VM ID, LAN IP, Tailscale IP, GPU, and purpose?'"
        )
    ),
    limit: int = Query(
        default=5,
        ge=1,
        le=10,
        description=(
            "Maximum number of relevant Basecamp knowledge chunks to return. "
            "Use multiple results when the question asks for several facts."
        ),
    ),
):
    """Retrieve authoritative stored documentation about the user's Basecamp homelab."""
    vector = embed_text(query)

    response = requests.post(
        f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/query",
        json={
            "query": vector,
            "limit": limit,
            "with_payload": True,
        },
        timeout=10,
    )
    response.raise_for_status()

    points = response.json().get("result", {}).get("points", [])

    results = []
    for point in points:
        payload = point.get("payload", {})
        results.append({
            "score": round(float(point.get("score", 0)), 4),
            "text": payload.get("text"),
            "source": payload.get("source"),
            "section": payload.get("section"),
            "file_type": payload.get("file_type"),
            "chunk": payload.get("chunk"),
            "total_chunks": payload.get("total_chunks"),
            "point_id": point.get("id"),
        })

    return {
        "timestamp": now(),
        "query": query,
        "collection": QDRANT_COLLECTION,
        "results": results,
    }

# ----- AI-worker live status -----

AI_WORKER_LAN = os.environ["AI_WORKER_LAN_HOST"]
AI_WORKER_TAILSCALE = os.environ["AI_WORKER_OVERLAY_HOST"]
AI_WORKER_EMBEDDING_URL = os.environ["AI_WORKER_EMBEDDING_URL"].rstrip("/")


def tcp_reachable(host, port, timeout=3):
    """Return whether a TCP endpoint is reachable without authenticating."""
    import socket

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@app.get(
    "/ai-worker/status.json",
    operation_id="get_ai_worker_status",
    summary="Get current AI-worker reachability and embedding-service status",
)
def ai_worker_status():
    """Check AI-worker LAN/Tailscale reachability and its embedding service."""

    embedding_ok = False
    embedding_status_code = None
    embedding_error = None

    try:
        response = requests.get(
            f"{AI_WORKER_EMBEDDING_URL}/health",
            timeout=5,
        )
        embedding_status_code = response.status_code
        embedding_ok = response.ok
    except requests.RequestException as exc:
        embedding_error = str(exc)

    return {
        "timestamp": now(),
        "host": "ai-worker",
        "lan_ip": AI_WORKER_LAN,
        "tailscale_ip": AI_WORKER_TAILSCALE,
        "lan_ssh_reachable": tcp_reachable(AI_WORKER_LAN, 22),
        "tailscale_ssh_reachable": tcp_reachable(AI_WORKER_TAILSCALE, 22),
        "embedding_service": {
            "url": AI_WORKER_EMBEDDING_URL,
            "reachable": embedding_ok,
            "http_status": embedding_status_code,
            "error": embedding_error,
        },
    }


# ----- Knowledge-pipeline live health -----

@app.get(
    "/knowledge/health.json",
    operation_id="get_knowledge_pipeline_health",
    summary="Get current homelab knowledge-pipeline health",
)
def knowledge_pipeline_health():
    """Check embedding generation, Qdrant collection state, and semantic search."""

    checks = {}
    overall_ok = True

    # Embedding dependency
    try:
        vector = embed_text("homelab knowledge pipeline health check")
        checks["embedding"] = {
            "ok": True,
            "dimensions": len(vector),
        }
    except Exception as exc:
        overall_ok = False
        checks["embedding"] = {
            "ok": False,
            "error": str(exc),
        }
        vector = None

    # Qdrant collection
    try:
        response = requests.get(
            f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}",
            timeout=5,
        )
        response.raise_for_status()
        result = response.json().get("result", {})

        qdrant_ok = result.get("status") == "green"

        checks["qdrant"] = {
            "ok": qdrant_ok,
            "status": result.get("status"),
            "points_count": result.get("points_count"),
            "indexed_vectors_count": result.get("indexed_vectors_count"),
        }

        if not qdrant_ok:
            overall_ok = False

    except Exception as exc:
        overall_ok = False
        checks["qdrant"] = {
            "ok": False,
            "error": str(exc),
        }

    # Actual vector query
    if vector is not None:
        try:
            response = requests.post(
                f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/query",
                json={
                    "query": vector,
                    "limit": 1,
                    "with_payload": True,
                },
                timeout=10,
            )
            response.raise_for_status()

            points = response.json().get("result", {}).get("points", [])

            checks["semantic_query"] = {
                "ok": bool(points),
                "results_returned": len(points),
                "top_source": (
                    points[0].get("payload", {}).get("source")
                    if points else None
                ),
                "top_section": (
                    points[0].get("payload", {}).get("section")
                    if points else None
                ),
            }

            if not points:
                overall_ok = False

        except Exception as exc:
            overall_ok = False
            checks["semantic_query"] = {
                "ok": False,
                "error": str(exc),
            }

    else:
        overall_ok = False
        checks["semantic_query"] = {
            "ok": False,
            "error": "Skipped because embedding generation failed",
        }

    return {
        "timestamp": now(),
        "pipeline": "homelab_knowledge",
        "healthy": overall_ok,
        "checks": checks,
    }

# ----- Proxmox live infrastructure -----

def proxmox_get(path, params=None):
    """Perform an authenticated read-only GET request to the Basecamp Proxmox API."""
    if not PVE_TOKEN:
        raise RuntimeError("PVE_TOKEN is not configured")

    response = requests.get(
        f"{PVE_URL}/api2/json/{path.lstrip('/')}",
        headers={
            "Authorization": f"PVEAPIToken={PVE_TOKEN_ID}={PVE_TOKEN}"
        },
        params=params,
        verify=os.environ.get("PVE_CA_BUNDLE") or True,
        timeout=10,
    )
    response.raise_for_status()
    return response.json().get("data")


@app.get(
    "/basecamp/status.json",
    operation_id="get_basecamp_status",
    summary="Get current Basecamp Proxmox host status",
)
def basecamp_status():
    """Get live status and resource usage for the Basecamp Proxmox host."""

    nodes = proxmox_get("nodes") or []

    node = next(
        (item for item in nodes if item.get("node") == PVE_NODE),
        None,
    )

    if node is None:
        raise RuntimeError(f"Proxmox node {PVE_NODE!r} was not found")

    maxmem = node.get("maxmem", 0) or 0
    mem = node.get("mem", 0) or 0
    maxdisk = node.get("maxdisk", 0) or 0
    disk = node.get("disk", 0) or 0

    return {
        "timestamp": now(),
        "host": PVE_NODE,
        "status": node.get("status"),
        "uptime_seconds": node.get("uptime"),
        "cpu": {
            "used_percent": round((node.get("cpu", 0) or 0) * 100, 2),
            "cores": node.get("maxcpu"),
        },
        "memory": {
            "used_gb": round(mem / 1024**3, 2),
            "total_gb": round(maxmem / 1024**3, 2),
            "used_percent": round(mem / maxmem * 100, 1) if maxmem else None,
        },
        "root_storage": {
            "used_gb": round(disk / 1024**3, 2),
            "total_gb": round(maxdisk / 1024**3, 2),
            "used_percent": round(disk / maxdisk * 100, 1) if maxdisk else None,
        },
    }


@app.get(
    "/basecamp/guests.json",
    operation_id="get_basecamp_guests",
    summary="Get current Basecamp virtual machines and containers",
)
def basecamp_guests():
    """List live QEMU VMs and LXC containers reported by Basecamp Proxmox."""

    resources = proxmox_get(
        "cluster/resources",
        params={"type": "vm"},
    ) or []

    guests = []

    for item in sorted(resources, key=lambda x: x.get("vmid", 0)):
        maxmem = item.get("maxmem", 0) or 0
        mem = item.get("mem", 0) or 0
        maxdisk = item.get("maxdisk", 0) or 0
        disk = item.get("disk", 0) or 0

        guests.append({
            "vmid": item.get("vmid"),
            "name": item.get("name"),
            "type": item.get("type"),
            "node": item.get("node"),
            "status": item.get("status"),
            "uptime_seconds": item.get("uptime"),
            "cpu": {
                "used_percent": round((item.get("cpu", 0) or 0) * 100, 2),
                "allocated_cores": item.get("maxcpu"),
            },
            "memory": {
                "used_gb": round(mem / 1024**3, 2),
                "allocated_gb": round(maxmem / 1024**3, 2),
                "used_percent": (
                    round(mem / maxmem * 100, 1)
                    if maxmem else None
                ),
            },
            "disk": {
                "used_gb": round(disk / 1024**3, 2),
                "allocated_gb": round(maxdisk / 1024**3, 2),
            },
        })

    return {
        "timestamp": now(),
        "host": PVE_NODE,
        "guest_count": len(guests),
        "guests": guests,
    }


@app.get(
    "/basecamp/storage.json",
    operation_id="get_basecamp_storage",
    summary="Get current Basecamp Proxmox storage status",
)
def basecamp_storage():
    """List live Proxmox storage pools available on Basecamp."""

    resources = proxmox_get(
        "cluster/resources",
        params={"type": "storage"},
    ) or []

    storage = []

    for item in sorted(resources, key=lambda x: x.get("storage", "")):
        total = item.get("maxdisk", 0) or 0
        used = item.get("disk", 0) or 0

        storage.append({
            "storage": item.get("storage"),
            "node": item.get("node"),
            "status": item.get("status"),
            "used_gb": round(used / 1024**3, 2),
            "total_gb": round(total / 1024**3, 2),
            "free_gb": round((total - used) / 1024**3, 2),
            "used_percent": round(used / total * 100, 1) if total else None,
        })

    return {
        "timestamp": now(),
        "host": PVE_NODE,
        "storage_count": len(storage),
        "storage": storage,
    }


# ----- Comprehensive Basecamp live audit -----

@app.get(
    "/audit/full.json",
    operation_id="get_full_homelab_audit",
    summary="Run a comprehensive live audit of the entire Basecamp homelab",
    description=(
        "COMPREHENSIVE LIVE HOMELAB AUDIT. Use this operation when the user asks "
        "to check, audit, inspect, review, or report on the entire Basecamp homelab "
        "or multiple major homelab components at once. It gathers live state for "
        "Basecamp Proxmox, all Proxmox guests, Proxmox storage, core-services host, "
        "Docker containers, ai-worker, and the knowledge pipeline in one operation. "
        "For broad audit requests, use this operation directly instead of asking "
        "the user which component to inspect first. Do not ask for clarification "
        "when the user's request already clearly covers the whole homelab. "
        "INTERPRETATION REQUIREMENTS: Treat returned values as observations, not "
        "automatic diagnoses. Do not label an unusual value as a fault without "
        "corroborating evidence. Proxmox VM memory slightly above 100 percent may "
        "reflect host-side accounting or rounded allocation and is not by itself "
        "evidence of memory exhaustion, overcommit, swapping, or a runaway process. "
        "Qdrant indexed_vectors_count of 0 is not by itself evidence that vectors "
        "are missing, indexing failed, or reindexing is required. If the same audit "
        "shows a successful semantic vector query returning relevant results, treat "
        "that as evidence that semantic retrieval is operational. Never claim that "
        "queries will return empty results when the live semantic query succeeded. "
        "Do not invent remediation commands, URLs, API endpoints, container names, "
        "SSH targets, or procedures that were not established by live tool output "
        "or authoritative homelab knowledge. In particular, do not assume a Proxmox "
        "VM is a Docker container. If corrective action appears warranted, first use "
        "an available live tool or authoritative knowledge search to verify the "
        "suspected problem and the correct procedure. If verification is unavailable, "
        "state what remains unverified instead of guessing."
    ),
)
def full_homelab_audit():
    """Collect live telemetry and derive conservative, evidence-based audit facts."""

    checks = {}

    audit_functions = {
        "basecamp": basecamp_status,
        "proxmox_guests": basecamp_guests,
        "proxmox_storage": basecamp_storage,
        "core_services_host": host_status,
        "docker": docker_status,
        "ai_worker": ai_worker_status,
        "knowledge_pipeline": knowledge_pipeline_health,
    }

    for name, function in audit_functions.items():
        try:
            checks[name] = {
                "retrieved": True,
                "data": function(),
            }
        except Exception as exc:
            checks[name] = {
                "retrieved": False,
                "error": str(exc),
            }

    retrieved = sum(
        1 for result in checks.values()
        if result.get("retrieved") is True
    )

    def check_data(name):
        result = checks.get(name, {})
        if result.get("retrieved") is True:
            return result.get("data") or {}
        return {}

    derived_facts = {}

    # ----- Proxmox API / Basecamp -----
    proxmox_checks = [
        checks.get("basecamp", {}).get("retrieved") is True,
        checks.get("proxmox_guests", {}).get("retrieved") is True,
        checks.get("proxmox_storage", {}).get("retrieved") is True,
    ]

    derived_facts["proxmox"] = {
        "authenticated_api_responded": any(proxmox_checks),
        "all_primary_proxmox_checks_succeeded": all(proxmox_checks),
    }

    # ----- Guest state -----
    guests_data = check_data("proxmox_guests")
    guests = guests_data.get("guests", [])

    expected_guests = {
        100: "core-services",
        101: "pihole",
        102: "ai-worker",
        103: "jellyfin",
        104: "media-automation",
        105: "arda",
    }

    guest_by_vmid = {
        guest.get("vmid"): guest
        for guest in guests
        if guest.get("vmid") is not None
    }

    guest_state = {}

    for vmid, expected_name in expected_guests.items():
        guest = guest_by_vmid.get(vmid)
        guest_state[str(vmid)] = {
            "expected_name": expected_name,
            "present": guest is not None,
            "reported_name": guest.get("name") if guest else None,
            "running": guest.get("status") == "running" if guest else False,
        }

    derived_facts["guests"] = {
        "expected_guest_count": len(expected_guests),
        "all_expected_guests_present": all(
            vmid in guest_by_vmid for vmid in expected_guests
        ),
        "all_expected_guests_running": all(
            guest_by_vmid.get(vmid, {}).get("status") == "running"
            for vmid in expected_guests
        ),
        "guest_state": guest_state,
    }

    # ----- ai-worker memory interpretation -----
    ai_guest = guest_by_vmid.get(102, {})
    ai_memory = ai_guest.get("memory", {})
    ai_memory_percent = ai_memory.get("used_percent")

    slightly_above = (
        isinstance(ai_memory_percent, (int, float))
        and 100 < ai_memory_percent <= 105
    )

    derived_facts["ai_worker_memory"] = {
        "reported_used_percent": ai_memory_percent,
        "slightly_above_reported_allocation": slightly_above,
        "memory_exhaustion_state": "not_established",
        "guest_swap_state": "unverified",
        "runaway_process_state": "unverified",
        "interpretation": (
            "A slightly-above-100-percent Proxmox memory reading is an observation "
            "only. Current audit evidence does not establish guest memory exhaustion, "
            "swap activity, overcommit, or a runaway process."
            if slightly_above
            else
            "No special memory interpretation was derived from the current reading."
        ),
    }

    # ----- Storage -----
    storage_data = check_data("proxmox_storage")
    storage_items = storage_data.get("storage", [])

    derived_facts["storage"] = {
        "all_reported_pools_available": (
            bool(storage_items)
            and all(item.get("status") == "available" for item in storage_items)
        ),
        "storage_pressure_confirmed": False,
    }

    # ----- Docker -----
    docker_data = check_data("docker")
    containers = docker_data.get("containers", [])

    expected_containers = {
        "homelab-api",
        "qdrant",
        "homepage",
        "open-webui",
        "open-terminal",
        "beszel",
        "beszel-agent",
        "prometheus",
        "node-exporter",
        "grafana",
        "uptime-kuma",
    }

    container_by_name = {
        item.get("name"): item
        for item in containers
        if item.get("name")
    }

    missing_expected = sorted(
        expected_containers - set(container_by_name)
    )

    unexpected = sorted(
        set(container_by_name) - expected_containers
    )

    stopped_expected = sorted(
        name
        for name in expected_containers
        if name in container_by_name
        and container_by_name[name].get("status") != "running"
    )

    derived_facts["docker"] = {
        "expected_container_count": len(expected_containers),
        "reported_container_count": len(containers),
        "all_expected_containers_present": not missing_expected,
        "all_expected_containers_running": (
            not missing_expected and not stopped_expected
        ),
        "missing_expected_containers": missing_expected,
        "stopped_expected_containers": stopped_expected,
        "unexpected_containers": unexpected,
        "upstream_image_currency": "unverified",
        "interpretation": (
            "Image tags such as latest or main identify configured tags only. "
            "This audit does not verify whether the running image is the newest "
            "version available upstream."
        ),
    }

    # ----- ai-worker service reachability -----
    ai_worker_data = check_data("ai_worker")
    embedding_service = ai_worker_data.get("embedding_service", {})

    derived_facts["ai_worker_service"] = {
        "lan_ssh_reachable": ai_worker_data.get("lan_ssh_reachable"),
        "tailscale_ssh_reachable": ai_worker_data.get("tailscale_ssh_reachable"),
        "embedding_http_lan_state": (
            "verified_reachable"
            if embedding_service.get("reachable") is True
            else "not_verified_reachable"
        ),
        "embedding_http_lan_status": embedding_service.get("http_status"),
        "embedding_http_tailscale_state": "unverified",
    }

    # ----- Knowledge pipeline -----
    knowledge_data = check_data("knowledge_pipeline")
    knowledge_checks = knowledge_data.get("checks", {})

    embedding_check = knowledge_checks.get("embedding", {})
    qdrant_check = knowledge_checks.get("qdrant", {})
    semantic_check = knowledge_checks.get("semantic_query", {})

    semantic_operational = (
        semantic_check.get("ok") is True
        and (semantic_check.get("results_returned") or 0) > 0
    )

    qdrant_green = (
        qdrant_check.get("ok") is True
        and qdrant_check.get("status") == "green"
    )

    embedding_operational = embedding_check.get("ok") is True

    current_pipeline_operational = (
        embedding_operational
        and qdrant_green
        and semantic_operational
    )

    derived_facts["knowledge_pipeline"] = {
        "pipeline_health_reported": knowledge_data.get("healthy"),
        "embedding_operational": embedding_operational,
        "embedding_dimensions": embedding_check.get("dimensions"),
        "qdrant_green": qdrant_green,
        "points_count": qdrant_check.get("points_count"),
        "indexed_vectors_count_observed": qdrant_check.get(
            "indexed_vectors_count"
        ),
        "semantic_retrieval_operational": semantic_operational,
        "semantic_results_returned": semantic_check.get("results_returned"),
        "current_pipeline_operational": current_pipeline_operational,
        "vector_loss_state": "not_established",
        "indexing_failure_state": "not_established",
        "reindex_requirement_state": "not_established",
        "fallback_retrieval_state": "not_established",
        "older_snapshot_usage_state": "not_established",
        "interpretation": (
            "The current live audit successfully generated an embedding, observed "
            "Qdrant in green state, and completed a semantic vector query that "
            "returned a result. indexed_vectors_count=0 alone does not establish "
            "vector loss, indexing failure, fallback retrieval, old-snapshot usage, "
            "or a need to reindex."
            if current_pipeline_operational
            else
            "One or more live knowledge-pipeline checks did not establish normal "
            "end-to-end operation."
        ),
    }

    return {
        "timestamp": now(),
        "audit": "basecamp_full_live_audit",
        "components_requested": len(audit_functions),
        "components_retrieved": retrieved,
        "complete": retrieved == len(audit_functions),
        "derived_facts": derived_facts,
        "checks": checks,
        "interpretation": (
            "Use derived_facts for conclusions when available. Raw checks remain "
            "included for transparency. Do not replace deterministic derived facts "
            "with speculative explanations."
        ),
    }
