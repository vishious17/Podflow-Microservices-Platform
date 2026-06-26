<div align="center">

<br/>

```
██████╗  ██████╗ ██████╗ ███████╗██╗      ██████╗ ██╗    ██╗
██╔══██╗██╔═══██╗██╔══██╗██╔════╝██║     ██╔═══██╗██║    ██║
██████╔╝██║   ██║██║  ██║█████╗  ██║     ██║   ██║██║ █╗ ██║
██╔═══╝ ██║   ██║██║  ██║██╔══╝  ██║     ██║   ██║██║███╗██║
██║     ╚██████╔╝██████╔╝██║     ███████╗╚██████╔╝╚███╔███╔╝
╚═╝      ╚═════╝ ╚═════╝ ╚═╝     ╚══════╝ ╚═════╝  ╚══╝╚══╝
```

### **Production-Grade Containerized Microservices Platform**

*Zero-Trust Security · Auto-Healing · Auto-Scaling · Full Observability*

<br/>

[![Podman](https://img.shields.io/badge/Podman-892CA0?style=for-the-badge&logo=podman&logoColor=white)](https://podman.io/)
[![Node.js](https://img.shields.io/badge/Node.js-339933?style=for-the-badge&logo=nodedotjs&logoColor=white)](https://nodejs.org/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org/)
[![Prometheus](https://img.shields.io/badge/Prometheus-E6522C?style=for-the-badge&logo=prometheus&logoColor=white)](https://prometheus.io/)
[![Grafana](https://img.shields.io/badge/Grafana-F46800?style=for-the-badge&logo=grafana&logoColor=white)](https://grafana.com/)
[![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)

[![Status](https://img.shields.io/badge/Status-Active%20Development-brightgreen?style=flat-square)]()
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-blue?style=flat-square)]()

</div>

---

## 📖 Overview

**PodFlow** is a production-style microservices platform built with **Podman** and **podman-compose**, designed to demonstrate real-world container orchestration patterns. It showcases:

- 🔐 **Zero-Trust Network Segmentation** via Calico network policies
- 🔄 **Auto-Healing** that automatically restarts failed containers
- 📈 **Auto-Scaling** based on real-time CPU metrics
- 🍯 **Security Honeypot** to trap and log intrusion attempts
- 📊 **Full Observability Stack** with Prometheus & Grafana
- 🌐 **API Gateway** pattern for unified, controlled service access

> This project is ideal for anyone learning cloud-native DevOps, container security, or microservice architecture at a production quality level.

---

## 🏗️ Architecture

```
                          ┌─────────────────────────────────────────────────┐
                          │                  PUBLIC INTERNET                  │
                          └────────────────────────┬────────────────────────┘
                                                   │ :8080
                          ┌────────────────────────▼────────────────────────┐
             public_net   │              🌐 API GATEWAY                     │
                          │         Node.js · Express · Port 8080            │
                          │     Rate Limiting · Prometheus Metrics           │
                          └───────────────┬─────────────────────────────────┘
                                          │ service_net
                    ┌─────────────────────┼───────────────────────┐
                    │                     │                        │
       ┌────────────▼──────────┐  ┌───────▼──────────┐  ┌────────▼──────────┐
       │   👤 User Service    │  │  🗄️ Backend Svc  │  │  📊 Monitoring    │
       │  Node.js · Port 5000  │  │  Node.js · :5000 │  │  Prometheus :9090 │
       │  /users · /health     │  │  Internal only   │  │  Grafana :3000    │
       │  Prometheus metrics   │  │  Prometheus mtrs │  │                   │
       └───────────────────────┘  └──────────────────┘  └───────────────────┘

                    ┌──────────────────────────────────────────────────────┐
                    │    🍯 Honeypot Service  (Isolated)                    │
                    │    Python · Flask · Port 8888 (HTTP) + 2222 (SSH)    │
                    │    Logs all intrusion attempts → Prometheus metrics   │
                    └──────────────────────────────────────────────────────┘

                    ┌──────────────────────────────────────────────────────┐
                    │    🔧 Automation Script                              │
                    │    orchestrator.py ── Auto-Heal & Auto-Scale Daemon   │
                    └──────────────────────────────────────────────────────┘
```

### Network Topology

| Network | Purpose | Members |
|---------|---------|---------|
| `public_net` | External-facing traffic | API Gateway |
| `service_net` | Internal service mesh | Gateway, User-Service, Backend, Prometheus, Grafana, Honeypot |

---

## 🧩 Microservices

### 🌐 API Gateway  
> `services/api-gateway/` · Node.js + Express · **Port 8080**

The **single public entry point** for all external traffic. Proxies requests to internal services, enforces routing rules, and exposes Prometheus metrics.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Gateway health status |
| `/api/users` | GET/POST | Proxied to User Service |
| `/metrics` | GET | Prometheus scrape endpoint |

---

### 👤 User Service  
> `services/user-service/` · Node.js + Express · **Port 5000** *(internal)*

Handles user management logic. Accessible only through the API Gateway — never directly exposed to the internet.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service health check |
| `/users` | GET | Returns user list |
| `/metrics` | GET | Prometheus metrics |

---

### 🗄️ Backend Service  
> `services/backend/` · Node.js · **Port 5000** *(internal only)*

Core backend logic layer. Isolated from the public internet. Only the API Gateway and Prometheus can communicate with it, enforced by Calico network policy (`app-data-protection`).

---

### 📁 Data Service  
> `services/data-service/` · Python · *(internal)*

Lightweight Python-based data layer for internal data operations. Designed to be consumed only by other services within the `service_net` network.

---

### 🍯 Honeypot Service  
> `services/honeypot/` · Python + Flask · **Port 8888** (HTTP) + **Port 2222** (SSH)

A **deception-layer security component** that mimics vulnerable endpoints (`/admin`, `/phpmyadmin`, `/.env`) and a fake SSH server to detect and log intrusion attempts.

**How it works:**
- Exposes fake admin panels to lure attackers
- Runs a simulated SSH server on port 2222
- Every intrusion attempt is **logged with timestamp + IP**
- All events are exported as **Prometheus metrics** for Grafana dashboards

```python
# Metrics exposed by the honeypot
honeypot_intrusion_attempts_total   # SSH + HTTP attempts by source IP
honeypot_suspicious_requests_total  # Suspicious HTTP endpoint access
```

---

## 📊 Monitoring & Observability

PodFlow ships with a full observability stack out of the box.

### Prometheus
> `monitoring/prometheus/` · **Port 9090**

Scrapes metrics from all services:
- `gateway_http_requests_total` — API Gateway request volume
- `http_requests_total` — User Service request volume  
- `honeypot_intrusion_attempts_total` — Security events
- `process_cpu_seconds_total` — CPU usage per service
- `process_resident_memory_bytes` — Memory usage per service

### Grafana  
> `monitoring/grafana/` · **Port 3000**

Pre-configured dashboards and datasources for visualizing:
- Request rates per service
- CPU & memory consumption trends
- Security threat heatmaps (from honeypot metrics)

**Default credentials:** `admin / admin` *(change on first login)*

---

## 🔐 Zero-Trust Network Security

PodFlow implements **Zero-Trust segmentation** via Calico `NetworkPolicy` resources (`network/Policies.yaml`).

| Policy | Target | Effect |
|--------|--------|--------|
| `gateway-shield` | API Gateway | Allows public :8080 + Prometheus scraping; egress only to Backend |
| `app-data-protection` | Backend | Allows ingress only from Gateway + Prometheus; egress blocked |
| `intrusion-trap-isolation` | Honeypot | Allows all on :2222/:8888 + Prometheus; fully isolated egress |
| `default-security-lockout` | Global | **Deny-all** fallback for unmatched traffic |

```
    Internet ──► Gateway ──► Backend  (all other paths DENIED)
                    │
                    └──► Prometheus ◄── all services /metrics
                    
    Internet ──► Honeypot (isolated, logs everything)
```

---

## ⚙️ Auto-Healing & Auto-Scaling (`scripts/orchestrator.py`)

PodFlow runs a unified **Orchestrator** daemon that handles both auto-healing and auto-scaling:

- 🔄 **Auto-Healing**: Monitors the running containers (`api-gateway`, `backend`, `user-service`, `honeypot`). If any container crashes or fails HTTP health checks 3 times consecutively, the orchestrator automatically restarts it.
- 📈 **Auto-Scaling**: Monitors the average CPU usage of all running replicas of the `backend`. If CPU usage exceeds `70%`, it dynamically scales up a new replica (max 3) and adds it to the internal network load-balancing. If CPU usage drops below `30%`, it scales down.

---

## 🚀 Getting Started

### Prerequisites

Ensure the following are installed on your system:

```bash
# Check versions
podman --version          # >= 4.0
podman-compose --version  # >= 1.0
python3 --version         # >= 3.9
node --version            # >= 18.x
```

| Tool | Install Guide |
|------|--------------|
| Podman | [podman.io/docs/installation](https://podman.io/docs/installation) |
| podman-compose | `pip3 install podman-compose` |
| Python 3 | [python.org/downloads](https://www.python.org/downloads/) |
| Node.js 18+ | [nodejs.org/en/download](https://nodejs.org/en/download/) |

---

### 📥 Clone the Repository

```bash
git clone https://github.com/your-username/Podflow.git
cd Podflow
```

---

### 🔧 Build & Start All Services

```bash
# Build all container images and start every service
podman-compose up --build
```

This single command will:
1. Build Docker/Podman images for all microservices
2. Create the `public_net` and `service_net` bridge networks
3. Start all 6 services: API Gateway, User Service, Backend, Data Service, Prometheus, Grafana, and Honeypot
4. Attach health checks and restart policies

---

### ✅ Verify Services Are Running

```bash
# Check all running containers
podman ps

# Check compose service status
podman-compose ps
```

Expected output:

```
CONTAINER ID  IMAGE                          COMMAND   STATUS        PORTS
xxxxxxxxxxxx  localhost/podflow_api-gateway  ...       Up 2 min      0.0.0.0:8080->8080/tcp
xxxxxxxxxxxx  localhost/podflow_user-service ...       Up 2 min
xxxxxxxxxxxx  localhost/podflow_backend      ...       Up 2 min      0.0.0.0:5000->5000/tcp
xxxxxxxxxxxx  docker.io/prom/prometheus      ...       Up 2 min      0.0.0.0:9090->9090/tcp
xxxxxxxxxxxx  docker.io/grafana/grafana      ...       Up 2 min      0.0.0.0:3000->3000/tcp
xxxxxxxxxxxx  localhost/podflow_honeypot     ...       Up 2 min      0.0.0.0:8888->8888/tcp
```

---

### 🌍 Access the Platform

| Service | URL | Credentials |
|---------|-----|-------------|
| **API Gateway** | http://localhost:8080 | — |
| **API Gateway Health** | http://localhost:8080/health | — |
| **User API** | http://localhost:8080/api/users | — |
| **Prometheus** | http://localhost:9090 | — |
| **Grafana** | http://localhost:3000 | `admin / admin` |
| **Honeypot** | http://localhost:8888 | *(intentionally fake)* |

---

### 🔁 Running the Orchestration Script

Open a **separate terminal** while services are running:

```bash
# Start the unified orchestrator (handles auto-healing and auto-scaling)
python3 scripts/orchestrator.py
```

---

### 🛑 Stopping Services

```bash
# Stop and remove containers (keeps images)
podman-compose down

# Stop, remove containers AND clean volumes
podman-compose down -v

# Remove all built images too
podman-compose down --rmi all
```

---

## 🗂️ Project Structure

```
Podflow/
├── 📄 podman-compose.yml          # Orchestration definition for all services
├── 📄 setup.sh                    # One-shot environment bootstrap script
│
├── 📁 services/
│   ├── 📁 api-gateway/            # Node.js API Gateway (public entry point)
│   │   ├── app.js                 # Express routes + Prometheus metrics
│   │   ├── index.js               # Server entrypoint
│   │   ├── metrics.js             # Custom metric definitions
│   │   └── Dockerfile
│   │
│   ├── 📁 user-service/           # Node.js User Management Service
│   │   ├── app.js                 # User routes + metrics
│   │   ├── index.js
│   │   └── Dockerfile
│   │
│   ├── 📁 backend/                # Node.js Core Backend Service
│   │   ├── index.js
│   │   └── Dockerfile
│   │
│   ├── 📁 data-service/           # Python Data Layer
│   │   └── app.py
│   │
│   └── 📁 honeypot/               # Python Security Honeypot
│       ├── honeypot.py            # Fake SSH + HTTP trap server
│       ├── Dockerfile
│       └── Deployment.yaml        # K8s-style deployment spec
│
├── 📁 monitoring/
│   ├── 📁 prometheus/
│   │   └── prometheus.yml         # Scrape configs for all services
│   └── 📁 grafana/
│       ├── datasource.yml         # Prometheus datasource provisioning
│       ├── dashboards.yaml        # Dashboard auto-provisioning
│       └── 📁 dashboards/         # Pre-built Grafana dashboard JSONs
│
├── 📁 network/
│   └── Policies.yaml              # Calico Zero-Trust network policies
│
└── 📁 scripts/
    └── orchestrator.py            # Unified Auto-Heal & Auto-Scale Daemon
```

---

## 🔌 API Reference

### API Gateway — `localhost:8080`

#### `GET /health`
Returns the gateway health status.

```bash
curl http://localhost:8080/health
```
```json
{ "status": "UP", "service": "api-gateway" }
```

#### `GET /api/users`
Fetches the user list from the User Service (proxied through gateway).

```bash
curl http://localhost:8080/api/users
```
```json
{
  "users": [
    { "id": 1, "name": "Alice" },
    { "id": 2, "name": "Bob" }
  ]
}
```

#### `GET /metrics`
Prometheus-compatible metrics endpoint (for scraping).

```bash
curl http://localhost:8080/metrics
```

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Container Runtime** | Podman + podman-compose | Rootless container orchestration |
| **API Gateway** | Node.js, Express | Request routing & proxying |
| **User Service** | Node.js, Express | User management API |
| **Backend** | Node.js | Core business logic |
| **Data Service** | Python (Flask) | Data layer |
| **Security** | Python (Flask, Sockets) | Honeypot & intrusion detection |
| **Metrics** | Prometheus Client (Node + Python) | Metrics exposition |
| **Monitoring** | Prometheus | Metrics collection & alerting |
| **Dashboards** | Grafana | Visualization |
| **Network Security** | Calico CNI Policies | Zero-Trust segmentation |
| **Automation** | Python | Auto-Heal & Auto-Scale |

---

## 🤝 Contributing

Contributions are welcome! Here's how to get started:

1. **Fork** the repository
2. **Clone** your fork: `git clone https://github.com/your-username/Podflow.git`
3. **Create a branch**: `git checkout -b feature/your-feature-name`
4. **Make your changes** and commit with a clear message: `git commit -m "feat: add XYZ feature"`
5. **Push** to your fork: `git push origin feature/your-feature-name`
6. **Open a Pull Request** with a detailed description of your changes

### Commit Convention

This project follows [Conventional Commits](https://www.conventionalcommits.org/):

```
feat:     New feature
fix:      Bug fix
docs:     Documentation changes
refactor: Code refactoring
chore:    Maintenance tasks
```

---

## 🗺️ Roadmap

- [x] API Gateway with Prometheus metrics
- [x] User Service with request counters
- [x] Honeypot with SSH + HTTP traps
- [x] Prometheus + Grafana monitoring stack
- [x] Calico Zero-Trust network policies
- [x] Auto-Heal and Auto-Scale scripts
- [ ] Alertmanager integration for critical alerts
- [ ] Distributed tracing with Jaeger/Tempo
- [ ] JWT authentication at the API Gateway
- [ ] Kubernetes deployment manifests (Helm chart)
- [ ] CI/CD pipeline with GitHub Actions
- [ ] HTTPS/TLS termination at the gateway
- [ ] Rate limiting and DDoS protection layer

---

## 🙏 Acknowledgements

- [Podman](https://podman.io/) — Daemonless, rootless containers
- [Prometheus](https://prometheus.io/) — Open-source monitoring & alerting
- [Grafana](https://grafana.com/) — The open observability platform
- [Calico](https://projectcalico.docs.tigera.io/) — Zero-Trust networking for containers
- [Express.js](https://expressjs.com/) — Fast, minimalist Node.js web framework
- [Flask](https://flask.palletsprojects.com/) — Lightweight Python web framework

---

<div align="center">

**Built with ❤️ — PodFlow**

*If you found this useful, please ⭐ star the repo!*

</div>
