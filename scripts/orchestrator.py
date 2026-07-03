#!/usr/bin/env python3

import subprocess
import json
import time
import requests
from datetime import datetime

CHECK_INTERVAL       = 10
FAILURE_THRESHOLD    = 3
REQUEST_TIMEOUT      = 3
CPU_THRESHOLD        = 70.0
SCALE_DOWN_THRESHOLD = 30.0
MIN_REPLICAS         = 1
MAX_REPLICAS         = 3
COOLDOWN             = 30

last_scale_time = 0.0


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def detect_project_prefix():
    try:
        result = subprocess.run(
            ["podman", "ps", "--format", "json"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            output = result.stdout.strip()
            try:
                containers = json.loads(output)
            except json.JSONDecodeError:
                containers = [json.loads(l) for l in output.splitlines() if l.strip()]
            for c in containers:
                names = c.get("Names", [])
                if names and "_api-gateway_" in names[0]:
                    return names[0].split("_api-gateway_")[0]
    except Exception as e:
        log(f"Warning during prefix detection: {e}")
    return "podflow"


PROJECT_PREFIX = detect_project_prefix()
log(f"Detected project prefix: '{PROJECT_PREFIX}'")

SERVICES = {
    f"{PROJECT_PREFIX}_api-gateway_1":  "http://localhost:8080/health",
    f"{PROJECT_PREFIX}_backend_1":      "http://localhost:5000/users",
    f"{PROJECT_PREFIX}_user-service_1": None,
    f"{PROJECT_PREFIX}_data-service_1": "http://localhost:4000/health",
    f"{PROJECT_PREFIX}_honeypot_1":     "http://localhost:8888/health",
}

failure_counts = {name: 0 for name in SERVICES}


def get_container_status(name):
    try:
        result = subprocess.run(
            ["podman", "inspect", "-f", "{{.State.Status}}", name],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip().lower() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def is_container_running(name):
    return get_container_status(name) in ["running", "healthy"]


def is_app_healthy(url):
    if not url:
        return True
    try:
        return requests.get(url, timeout=REQUEST_TIMEOUT).status_code == 200
    except requests.RequestException:
        return False


def restart_container(name):
    if not is_container_running(name):
        log(f"Starting stopped container: {name}")
        result = subprocess.run(["podman", "start", name], capture_output=True, text=True)
        if result.returncode == 0:
            log(f"Started: {name}")
            return
        log(f"Start failed, trying restart: {result.stderr.strip()}")
    log(f"Restarting: {name}")
    result = subprocess.run(["podman", "restart", name], capture_output=True, text=True)
    if result.returncode == 0:
        log(f"Restarted: {name}")
    else:
        log(f"Restart failed: {result.stderr.strip()}")


def get_backend_containers():
    try:
        result = subprocess.run(
            ["podman", "ps", "--format", "json"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        output = result.stdout.strip()
        try:
            containers = json.loads(output)
        except json.JSONDecodeError:
            containers = [json.loads(l) for l in output.splitlines() if l.strip()]
        prefix = f"{PROJECT_PREFIX}_backend"
        return [c["Names"][0] for c in containers
                if c.get("Names") and c["Names"][0].startswith(prefix)]
    except Exception as e:
        log(f"Error getting backend containers: {e}")
        return []


def get_cpu_usage(container_names):
    if not container_names:
        return 0.0
    try:
        result = subprocess.run(
            ["podman", "stats", "--no-stream", "--format", "json"] + container_names,
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0 or not result.stdout.strip():
            return 0.0
        output = result.stdout.strip()
        try:
            stats = json.loads(output)
            if not isinstance(stats, list):
                stats = [stats]
        except json.JSONDecodeError:
            stats = [json.loads(l) for l in output.splitlines() if l.strip()]
        cpu_values = []
        for s in stats:
            raw = s.get("cpu_percent", s.get("CPUPerc", "0%"))
            try:
                cpu_values.append(float(str(raw).replace("%", "").strip()))
            except ValueError:
                pass
        return sum(cpu_values) / len(cpu_values) if cpu_values else 0.0
    except Exception as e:
        log(f"Error getting CPU stats: {e}")
    return 0.0


def get_container_network(container_name):
    try:
        result = subprocess.run(
            ["podman", "inspect", "-f",
             "{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}",
             container_name],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return f"{PROJECT_PREFIX}_service_net"


def get_container_image(container_name):
    try:
        result = subprocess.run(
            ["podman", "inspect", "-f", "{{.ImageName}}", container_name],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return f"localhost/{PROJECT_PREFIX}_backend"


def scale_up(current_count, base_container):
    new_name = f"{PROJECT_PREFIX}_backend_scale_{current_count}"
    network  = get_container_network(base_container)
    image    = get_container_image(base_container)
    log(f"Scaling up: launching {new_name}")
    cmd = ["podman", "run", "-d",
           "--name", new_name,
           "--network", network,
           "--network-alias", "backend",
           image]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        log(f"Replica started: {new_name}")
    else:
        log(f"Scale up failed: {result.stderr.strip()}")


def scale_down(containers):
    extras = sorted([c for c in containers if "_scale_" in c])
    if not extras:
        log("No replicas to remove.")
        return
    target = extras[-1]
    log(f"Scaling down: removing {target}")
    result = subprocess.run(["podman", "rm", "-f", target], capture_output=True, text=True)
    if result.returncode == 0:
        log(f"Replica removed: {target}")
    else:
        log(f"Scale down failed: {result.stderr.strip()}")


def run_orchestrator():
    global last_scale_time
    log("PodFlow Orchestrator started")
    log(f"Monitoring: {list(SERVICES.keys())}")
    print("-" * 60, flush=True)

    while True:
        for container_name, health_url in SERVICES.items():
            short  = container_name.replace(f"{PROJECT_PREFIX}_", "").replace("_1", "")
            status = get_container_status(container_name)

            if status == "stopping":
                continue
            elif status not in ["running", "healthy"]:
                log(f"[{short}] Not running (status: {status}). Restarting.")
                restart_container(container_name)
                failure_counts[container_name] = 0
                continue

            if health_url:
                if not is_app_healthy(health_url):
                    failure_counts[container_name] += 1
                    log(f"[{short}] Health check failed "
                        f"({failure_counts[container_name]}/{FAILURE_THRESHOLD})")
                    if failure_counts[container_name] >= FAILURE_THRESHOLD:
                        log(f"[{short}] Threshold reached. Restarting.")
                        restart_container(container_name)
                        failure_counts[container_name] = 0
                else:
                    if failure_counts[container_name] > 0:
                        log(f"[{short}] Recovered.")
                    failure_counts[container_name] = 0

        backend_containers = get_backend_containers()
        replica_count      = len(backend_containers)
        base_container     = f"{PROJECT_PREFIX}_backend_1"

        if replica_count > 0:
            avg_cpu = get_cpu_usage(backend_containers)
            log(f"Backend replicas: {replica_count} | Avg CPU: {avg_cpu:.2f}%")
            now            = time.time()
            cooldown_active = (now - last_scale_time) < COOLDOWN
            if cooldown_active:
                remaining = int(COOLDOWN - (now - last_scale_time))
                log(f"Cooldown active ({remaining}s remaining)")
            else:
                if avg_cpu > CPU_THRESHOLD and replica_count < MAX_REPLICAS:
                    scale_up(replica_count, base_container)
                    last_scale_time = now
                elif avg_cpu < SCALE_DOWN_THRESHOLD and replica_count > MIN_REPLICAS:
                    scale_down(backend_containers)
                    last_scale_time = now
        else:
            log("No backend containers found.")

        print("-" * 60, flush=True)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run_orchestrator()
