#!/usr/bin/env python3

import subprocess
import json
import time
import requests
from datetime import datetime

# ==========================================
# CONFIGURATION
# ==========================================
CHECK_INTERVAL    = 10   # seconds between check cycles
FAILURE_THRESHOLD = 3    # consecutive health check failures before restart
REQUEST_TIMEOUT   = 3    # seconds for HTTP health check timeout

# Scaling Configuration
CPU_THRESHOLD      = 70.0  # Scale up backend if average CPU > 70%
SCALE_DOWN_THRESHOLD = 30.0  # Scale down backend if average CPU < 30%
MIN_REPLICAS       = 1
MAX_REPLICAS       = 3
COOLDOWN           = 30    # seconds to wait between scaling events

last_scale_time = 0.0

# ==========================================
# UTILITY & DETECTION FUNCTIONS
# ==========================================
def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

def detect_project_prefix():
    """
    Detect the podman-compose project prefix dynamically.
    Looks for any running api-gateway container and gets its prefix.
    """
    try:
        result = subprocess.run(
            ["podman", "ps", "--format", "json"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            # Handle list output or line-by-line JSON
            output = result.stdout.strip()
            try:
                containers = json.loads(output)
            except json.JSONDecodeError:
                containers = []
                for line in output.splitlines():
                    if line.strip():
                        containers.append(json.loads(line))

            for c in containers:
                names = c.get("Names", [])
                if names:
                    name = names[0]
                    if "_api-gateway_" in name:
                        prefix = name.split("_api-gateway_")[0]
                        return prefix
    except Exception as e:
        log(f"Warning during project prefix detection: {e}")
    return "podflow"  # default fallback

# Dynamically set prefix
PROJECT_PREFIX = detect_project_prefix()
log(f"Detected project prefix: '{PROJECT_PREFIX}'")

# Services to monitor (Container Name -> Local Healthcheck URL or None)
# For user-service, it does not expose ports, so we only monitor running status (None URL)
# For backend, it exposes port 5000, and we check /users endpoint (no default /health endpoint)
SERVICES = {
    f"{PROJECT_PREFIX}_api-gateway_1":  "http://localhost:8080/health",
    f"{PROJECT_PREFIX}_backend_1":      "http://localhost:5000/users",
    f"{PROJECT_PREFIX}_honeypot_1":     "http://localhost:8888/health",
    f"{PROJECT_PREFIX}_user-service_1": None,
}

# Track HTTP failure counts per container
failure_counts = {name: 0 for name in SERVICES}

def get_container_status(name):
    """Returns the container status string (e.g. running, exited, stopped, stopping, created, dead)."""
    try:
        result = subprocess.run(
            ["podman", "inspect", "-f", "{{.State.Status}}", name],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return "unknown"
        return result.stdout.strip().lower()
    except Exception:
        return "unknown"

def is_container_running(name):
    """Checks if the container exists and is running."""
    return get_container_status(name) in ["running", "healthy"]

def is_app_healthy(url):
    """Checks HTTP endpoint, returns True if status 200 is returned."""
    if not url:
        return True  # If no URL, we assume healthy as long as container is running
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        return response.status_code == 200
    except requests.RequestException:
        return False

def restart_container(name):
    """Restarts or starts the container depending on its status."""
    if not is_container_running(name):
        log(f"🔄 Starting stopped container: {name}...")
        result = subprocess.run(
            ["podman", "start", name],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            log(f"✅ {name} started successfully.")
            return
        else:
            log(f"⚠️ Failed to start {name}, trying restart: {result.stderr.strip()}")
            
    log(f"🔄 Restarting container: {name}...")
    result = subprocess.run(
        ["podman", "restart", name],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        log(f"✅ {name} restarted successfully.")
    else:
        log(f"❌ Failed to restart {name}: {result.stderr.strip()}")

def get_backend_containers():
    """Returns a list of all active backend containers (main + scaled)."""
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
            containers = []
            for line in output.splitlines():
                if line.strip():
                    containers.append(json.loads(line))

        backend_prefix = f"{PROJECT_PREFIX}_backend"
        return [
            c["Names"][0] for c in containers
            if c.get("Names") and c["Names"][0].startswith(backend_prefix)
        ]
    except Exception as e:
        log(f"Error getting backend containers: {e}")
        return []

def get_cpu_usage(container_names):
    """Calculates the average CPU usage across the given containers."""
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
            stats = []
            for line in output.splitlines():
                if line.strip():
                    stats.append(json.loads(line))

        cpu_values = []
        for s in stats:
            raw = s.get("cpu_percent", s.get("CPUPerc", "0%"))
            try:
                val = float(str(raw).replace("%", "").strip())
                cpu_values.append(val)
            except ValueError:
                pass
        
        if cpu_values:
            return sum(cpu_values) / len(cpu_values)
    except Exception as e:
        log(f"Error getting CPU stats: {e}")
    return 0.0

def get_container_network(container_name):
    """Inspects container to find its active podman network."""
    try:
        result = subprocess.run(
            ["podman", "inspect", "-f", "{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}", container_name],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return f"{PROJECT_PREFIX}_service_net"

def get_container_image(container_name):
    """Inspects container to find its image name/ID."""
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
    """Starts a new scaled replica of the backend container."""
    new_name = f"{PROJECT_PREFIX}_backend_scale_{current_count}"
    network = get_container_network(base_container)
    image = get_container_image(base_container)
    
    log(f"⬆️ Scaling UP → launching replica: {new_name}")
    # Run container attached to the same network and with alias 'backend' so load balancing works
    cmd = [
        "podman", "run", "-d",
        "--name", new_name,
        "--network", network,
        "--network-alias", "backend",
        image
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        log(f"   ✅ {new_name} started successfully.")
    else:
        log(f"   ❌ Failed to scale up: {result.stderr.strip()}")

def scale_down(containers):
    """Removes the newest scaled replica of the backend."""
    # Find all scaled replicas (excluding the main backend_1)
    extras = [c for c in containers if "_scale_" in c]
    if not extras:
        log("   No extra replicas to remove.")
        return

    # Sort to remove the latest one
    extras.sort()
    target = extras[-1]
    
    log(f"⬇️ Scaling DOWN → removing replica: {target}")
    result = subprocess.run(
        ["podman", "rm", "-f", target],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        log(f"   ✅ {target} removed successfully.")
    else:
        log(f"   ❌ Failed to remove {target}: {result.stderr.strip()}")

# ==========================================
# MAIN CONTROL LOOP
# ==========================================
def run_orchestrator():
    global last_scale_time
    log("🧠 PodFlow Unified Orchestrator Started")
    log(f"   Monitoring: {list(SERVICES.keys())}")
    log(f"   Scaling target: {PROJECT_PREFIX}_backend")
    print("-" * 60, flush=True)

    while True:
        # ----------------- PART 1: AUTO-HEALING -----------------
        for container_name, health_url in SERVICES.items():
            short = container_name.replace(f"{PROJECT_PREFIX}_", "").replace("_1", "")

            # Step 1: Check container status
            status = get_container_status(container_name)
            if status == "stopping":
                log(f"⏳ [{short}] Container is currently stopping. Skipping health check.")
                continue
            elif status not in ["running", "healthy"]:
                log(f"❌ [{short}] Container is NOT running (Status: '{status}').")
                restart_container(container_name)
                failure_counts[container_name] = 0
                continue

            # Step 2: Check application health endpoint (if defined)
            if health_url:
                if not is_app_healthy(health_url):
                    failure_counts[container_name] += 1
                    log(f"⚠️  [{short}] Health check failed ({failure_counts[container_name]}/{FAILURE_THRESHOLD})")

                    if failure_counts[container_name] >= FAILURE_THRESHOLD:
                        log(f"🚨 [{short}] Failure threshold reached!")
                        restart_container(container_name)
                        failure_counts[container_name] = 0
                else:
                    # Reset failure count on success
                    if failure_counts[container_name] > 0:
                        log(f"✅ [{short}] Recovered to healthy state.")
                    failure_counts[container_name] = 0

        # ----------------- PART 2: AUTO-SCALING -----------------
        backend_containers = get_backend_containers()
        replica_count = len(backend_containers)
        
        # Ensure we have a base container to inspect settings from
        base_container = f"{PROJECT_PREFIX}_backend_1"
        
        if replica_count > 0:
            avg_cpu = get_cpu_usage(backend_containers)
            log(f"Backend Replicas: {replica_count} | Avg CPU: {avg_cpu:.2f}%")
            
            now = time.time()
            cooldown_active = (now - last_scale_time) < COOLDOWN
            
            if cooldown_active:
                remaining = int(COOLDOWN - (now - last_scale_time))
                log(f"   ⏳ Scaling cooldown active ({remaining}s remaining)")
            else:
                if avg_cpu > CPU_THRESHOLD and replica_count < MAX_REPLICAS:
                    scale_up(replica_count, base_container)
                    last_scale_time = now
                elif avg_cpu < SCALE_DOWN_THRESHOLD and replica_count > MIN_REPLICAS:
                    scale_down(backend_containers)
                    last_scale_time = now
        else:
            log("⚠️ No backend containers detected for scaling.")

        print("-" * 60, flush=True)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    run_orchestrator()
