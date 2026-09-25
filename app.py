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

app = FastAPI(title="Homelab Live Status", version="1.0.0", description="Read-only status and history for core-services.")
client = docker.from_env()
PROMETHEUS_URL = os.environ["PROMETHEUS_URL"].rstrip("/")
HOST = os.environ.get("HOMELAB_HOST", "core-services")
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
        containers.append({
            "name": container.name,
            "status": container.status,
            "image": ", ".join(container.image.tags) or container.image.short_id,
        })
    return {"timestamp": now(), "host": HOST, "containers": containers}


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
