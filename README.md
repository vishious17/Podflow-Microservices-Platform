<div align="center">

```
  ██████╗  ██████╗ ██████╗ ███████╗██╗      ██████╗ ██╗    ██╗
  ██╔══██╗██╔═══██╗██╔══██╗██╔════╝██║     ██╔═══██╗██║    ██║
  ██████╔╝██║   ██║██║  ██║█████╗  ██║     ██║   ██║██║ █╗ ██║
  ██╔═══╝ ██║   ██║██║  ██║██╔══╝  ██║     ██║   ██║██║███╗██║
  ██║     ╚██████╔╝██████╔╝██║     ███████╗╚██████╔╝╚███╔███╔╝
  ╚═╝      ╚═════╝ ╚═════╝ ╚═╝     ╚══════╝ ╚═════╝  ╚══╝╚══╝
```

**Advanced Containerized Microservices Platform**

[![Podman](https://img.shields.io/badge/Runtime-Podman-892CA0?style=flat-square&logo=podman)](https://podman.io)
[![Node.js](https://img.shields.io/badge/Node.js-18-339933?style=flat-square&logo=nodedotjs)](https://nodejs.org)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?style=flat-square&logo=postgresql)](https://postgresql.org)
[![Prometheus](https://img.shields.io/badge/Prometheus-Monitoring-E6522C?style=flat-square&logo=prometheus)](https://prometheus.io)
[![Grafana](https://img.shields.io/badge/Grafana-Dashboards-F46800?style=flat-square&logo=grafana)](https://grafana.com)

*Self-healing · Auto-scaling · Zero-trust networking · Real-time observability · Intrusion detection*

</div>

---

## What is PodFlow?

PodFlow is a production-grade microservices platform built entirely on open-source tools. It demonstrates the core patterns used in real-world distributed systems — without requiring Kubernetes. Everything runs on **Podman**, a daemonless, rootless container runtime.

The platform solves five real problems with monolithic architectures:

| Problem | PodFlow's Solution |
|---|---|
| One failure takes everything down | Each service runs in an isolated container |
| Cannot scale individual components | CPU-based auto-scaling with network-alias load balancing |
| No visibility into system health | Prometheus + Grafana full observability stack |
| Security is an afterthought | Honeypot intrusion detection + network isolation |
| Manual recovery from crashes | Self-healing orchestrator with 3-strike restart logic |

---

## Architecture

```
Internet
    |
    | HTTPS :8443  /  HTTP :8080
    v
+------------------+
|   api-gateway    |  Node.js · Express · JWT · Rate Limiting
|   (public_net    |
|   + service_net) |
+------------------+
    |        |        |
    v        v        v
+--------+ +--------+ +--------------+
|  user  | |backend | | data-service |
|service | |        | |              |
| :3000  | | :5000  | |    :4000     |
| (Node) | | (Node) | |   (Python)   |
+--------+ +--------+ +--------------+
    |           |            |
    +-----+-----+------------+
          |
          v
    +----------+
    | postgres |   PostgreSQL 15
    |  :5432   |   3 tables: users, data_entries, request_logs
    +----------+

+------------+      +------------+      +--------------+
| honeypot   |      | prometheus |      |   grafana    |
| :8888/2222 |      |   :9090    |      |    :3000     |
| (Python)   |      | scrapes 7  |      | 9-panel dash |
| honeypot   |      | targets    |      | provisioned  |
|    _net    |      | every 5s   |      | as code      |
+------------+      +------+-----+      +--------------+
                           |
                    +------v--------+
                    | alertmanager  |
                    |    :9093      |
                    | 5 alert rules |
                    | webhook ->    |
                    | data-service  |
                    +---------------+

scripts/orchestrator.py   (runs on host)
  - Polls 4 services every 10s
  - 3-strike failure -> auto restart
  - CPU > 70% -> scale up backend (max 3 replicas)
  - CPU < 30% -> graceful scale down
  - IST timestamps throughout
```

---

## Network Isolation

```
public_net    --  api-gateway only (internet-facing)
service_net   --  all internal services (private)
honeypot_net  --  honeypot only (internal: true, no external routing)
```

The honeypot runs on a completely isolated network. Even if fully compromised, it cannot reach any internal service — there is no network path.

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Container Runtime | Podman (rootless) | Daemonless containers, no root daemon |
| Orchestration | podman-compose | Multi-service lifecycle management |
| API Gateway | Node.js, Express | JWT auth, rate limiting, HTTPS, proxying |
| User Service | Node.js, Express, bcryptjs | User CRUD, password hashing |
| Backend | Node.js, Express | Data entries CRUD with PostgreSQL |
| Data Service | Python, Flask, psycopg2 | Request logging, analytics, alert webhook |
| Honeypot | Python, Flask, SQLite | Intrusion detection and live capture |
| Database | PostgreSQL 15 | Persistent storage, 3-table schema |
| Metrics | Prometheus | Pull-based scraping, 5 alert rules |
| Dashboards | Grafana | 9-panel provisioned-as-code dashboard |
| Alerting | Alertmanager | Webhook routing to data-service |
| Security | JWT, express-rate-limit, express-validator | Auth, brute-force protection, input sanitisation |
| TLS | OpenSSL self-signed | HTTPS on port 8443 |
| Networking | Podman bridge networks | 3-network zero-trust segmentation |

---

## Prerequisites

- **Podman** — [podman.io](https://podman.io)
- **podman-compose** — `pip3 install podman-compose`
- **Python 3.11+** — for the orchestrator
- **WSL2** (Windows) or native Linux

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/vishious17/Podflow.git
cd Podflow

# 2. Generate TLS certificates (one time only)
bash certs/generate-certs.sh

# 3. Start everything
bash start.sh
```

The startup script builds images, starts all containers in detached mode, waits for each service to become healthy, then prints the full URL table.

```bash
# Start without rebuilding images (faster on subsequent runs)
bash start.sh --no-build

# Stop everything cleanly
bash start.sh --down
```

---

## Daily Workflow

Open three terminals after `bash start.sh`:

```bash
# Terminal 1 — Self-healing and auto-scaling daemon
python3 scripts/orchestrator.py

# Terminal 2 — Follow all container logs
podman-compose logs -f

# Terminal 3 — Testing and debugging
curl http://localhost:8080/health
```

---

## Service URLs

| Service | URL | Notes |
|---|---|---|
| Web Dashboard | http://localhost:8080 | Register an account via the UI |
| API (HTTPS) | https://localhost:8443 | Use -k with curl for self-signed cert |
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | Targets, metrics explorer |
| Alertmanager | http://localhost:9093 | Active alerts and silences |
| Honeypot Dashboard | http://localhost:8888/honeypot-dashboard | Live intrusion log |

---

## API Reference

All routes except register and login require a `Bearer` JWT token in the `Authorization` header. Tokens expire after 24 hours.

### Authentication

```bash
# Register
curl -X POST http://localhost:8080/api/users/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Vishal","email":"vishal@podflow.io","password":"podflow123"}'

# Login — copy the token from the response
curl -X POST http://localhost:8080/api/users/login \
  -H "Content-Type: application/json" \
  -d '{"email":"vishal@podflow.io","password":"podflow123"}'

export TOKEN="paste-your-token-here"
```

### Users

```bash
curl http://localhost:8080/api/users                    -H "Authorization: Bearer $TOKEN"
curl http://localhost:8080/api/users/1                  -H "Authorization: Bearer $TOKEN"
curl -X PUT  http://localhost:8080/api/users/1          -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" -d '{"name":"New Name"}'
curl -X DELETE http://localhost:8080/api/users/1        -H "Authorization: Bearer $TOKEN"
```

### Data Entries

```bash
curl http://localhost:8080/api/data                     -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8080/api/data             -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"title":"My Entry","content":"Some content","author_id":1}'
curl -X PUT  http://localhost:8080/api/data/1           -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" -d '{"title":"Updated Title"}'
curl -X DELETE http://localhost:8080/api/data/1         -H "Authorization: Bearer $TOKEN"
```

### Analytics and Logs

```bash
curl http://localhost:8080/api/analytics                -H "Authorization: Bearer $TOKEN"
curl http://localhost:8080/api/logs                     -H "Authorization: Bearer $TOKEN"
curl http://localhost:8080/api/logs?service=api-gateway -H "Authorization: Bearer $TOKEN"
```

---

## Demonstrating Key Features

### Self-Healing

```bash
# Simulate a crash
podman stop podflow_backend_1

# Orchestrator detects failure within 10s
# After 3 consecutive failed health checks (~30s), restarts automatically
# Watch Terminal 1 for:
# [dd-mm-yyyy] backend   : exited  | HTTP: skip
# [dd-mm-yyyy] [backend] Not running (status: exited). Restarting.
# [dd-mm-yyyy] Restarted: podflow_backend_1
```

### Auto-Scaling

```bash
# Spike CPU inside the backend container (run all three)
podman exec podflow_backend_1 sh -c "while true; do echo 1 > /dev/null; done" &
podman exec podflow_backend_1 sh -c "while true; do echo 1 > /dev/null; done" &
podman exec podflow_backend_1 sh -c "while true; do echo 1 > /dev/null; done" &

# Watch orchestrator scale to 3 replicas as CPU crosses 70%
# Watch containers appear live:
watch -n 2 podman ps --format "{{.Names}} | {{.Status}}"

# Kill the load and watch scale-down after cooldown:
podman exec podflow_backend_1 sh -c "pkill -f 'echo 1'" 2>/dev/null; true
```

### Intrusion Detection

```bash
# HTTP traps — each hit is logged with IP, geolocation, and credentials
curl -X POST http://localhost:8888/admin -d "username=admin&password=secret"
curl http://localhost:8888/.env
curl http://localhost:8888/phpmyadmin
curl http://localhost:8888/shell          # fake interactive terminal

# SSH trap — sends real OpenSSH banner
nc localhost 2222                         # type anything, then Ctrl+C

# View captured intrusions
open http://localhost:8888/honeypot-dashboard
```

### Alertmanager Demo

```bash
# Trigger ServiceDown alert
podman stop podflow_backend_1

# Timeline from stop to alert:
#   0s  — container stops
#   5s  — Prometheus fails to scrape (up == 0)
#   35s — rule transitions PENDING -> FIRING
#   60s — Alertmanager POSTs to data-service /alerts

# Watch it arrive in data-service:
podman-compose logs -f data-service
# [ALERT] FIRING | ServiceDown | severity=critical | Service backend is unreachable

# View in Alertmanager UI:
open http://localhost:9093

# Resolve by restarting:
podman start podflow_backend_1
```

### Load Testing

```bash
# 50 concurrent threads for 60 seconds
python3 scripts/load_test.py 60

# Watch Grafana panels update live:
# - CPU Usage spikes across services
# - Gateway Requests Total climbs rapidly
# - Data Service Logs Received increases
# open http://localhost:3000
```

### Running Tests

```bash
# User service — 16 tests
cd services/user-service && npm install && npm test

# Backend — 12 tests
cd services/backend && npm install && npm test

# Data service — 7 tests
cd services/data-service
pip3 install pytest flask prometheus-client psycopg2-binary --break-system-packages
python3 -m pytest tests/ -v
```

---

## Alert Rules

| Alert | Fires When | Sustained For |
|---|---|---|
| ServiceDown | Any Prometheus scrape target is unreachable | 30 seconds |
| HighGatewayErrorRate | More than 5% of gateway requests return 5xx | 2 minutes |
| HoneypotIntrusionSpike | Intrusion rate exceeds 0.5 per second | 1 minute |
| HighMemoryUsage | Any service exceeds 512 MB resident memory | 5 minutes |
| LoginAttemptSpike | Honeypot login attempts exceed 0.2 per second | 1 minute |

All alerts route via Alertmanager to `data-service /alerts` as a webhook, where they are printed to logs and counted as a Prometheus metric (`data_service_alerts_total`).

---

## Database Schema

```sql
-- Owned by user-service
CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Owned by backend
CREATE TABLE data_entries (
    id         SERIAL PRIMARY KEY,
    title      VARCHAR(255) NOT NULL,
    content    TEXT,
    author_id  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Owned by data-service
CREATE TABLE request_logs (
    id          SERIAL PRIMARY KEY,
    service     VARCHAR(100) NOT NULL,
    method      VARCHAR(10)  NOT NULL,
    route       VARCHAR(255) NOT NULL,
    status      INTEGER      NOT NULL,
    source_ip   VARCHAR(50),
    duration_ms INTEGER,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Security Model

```
Layer 1 — Network segmentation (enforced by Podman bridge networks)
  public_net + service_net split: only gateway reaches the internet
  honeypot_net with internal:true: honeypot is fully isolated

Layer 2 — Application security (enforced at runtime)
  JWT HS256 tokens, 24h expiry, verified in gateway middleware
  bcrypt cost factor 10 for all password storage
  express-validator on every write endpoint
  Rate limiting: 10 auth / 100 API requests per IP per 15 minutes

Layer 3 — Policy specification (Calico CRD syntax)
  network/Policies.yaml defines default-deny with per-tier allow rules
  Directly deployable to Kubernetes + Calico CNI
  Current enforcement: layers 1 and 2 above

Layer 4 — Deception layer (active)
  Honeypot captures: IP, geolocation, credentials, shell commands
  Traps: SSH port 2222, /admin, /phpmyadmin, /.env, /shell, /wp-admin
  All events stored in SQLite, exposed on live dashboard
```

---

## Project Structure

```
Podflow/
├── certs/
│   └── generate-certs.sh              Self-signed TLS cert generator
├── db/
│   └── init.sql                       PostgreSQL schema and indexes
├── services/
│   ├── api-gateway/
│   │   ├── middleware/
│   │   │   ├── auth.js                JWT verification middleware
│   │   │   └── rateLimiter.js         Rate limiting configuration
│   │   ├── public/
│   │   │   └── index.html             Web dashboard (single-page app)
│   │   ├── index.js                   Gateway routes and HTTPS server
│   │   ├── package.json
│   │   └── Dockerfile
│   ├── user-service/
│   │   ├── __tests__/users.test.js    16 Jest tests
│   │   ├── index.js                   User CRUD with JWT generation
│   │   ├── db.js                      PostgreSQL connection pool
│   │   ├── validators.js              express-validator rules
│   │   ├── package.json
│   │   └── Dockerfile
│   ├── backend/
│   │   ├── __tests__/data.test.js     12 Jest tests
│   │   ├── index.js                   Data entries CRUD
│   │   ├── db.js                      PostgreSQL connection pool
│   │   ├── validators.js              express-validator rules
│   │   ├── package.json
│   │   └── Dockerfile
│   ├── data-service/
│   │   ├── tests/test_app.py          7 pytest tests
│   │   ├── app.py                     Logging, analytics, alert webhook
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── honeypot/
│       ├── honeypot.py                SSH trap, HTTP traps, dashboard
│       └── Dockerfile
├── monitoring/
│   ├── prometheus/
│   │   ├── prometheus.yml             Scrape config, 7 targets, 5s interval
│   │   └── alert_rules.yml            5 Prometheus alert rules
│   ├── alertmanager/
│   │   └── alertmanager.yml           Webhook routing configuration
│   └── grafana/
│       ├── datasource.yml             Prometheus datasource (provisioned)
│       ├── dashboards.yaml            File provider config (provisioned)
│       └── dashboards/
│           └── podflow.json           9-panel system dashboard
├── network/
│   ├── Policies.yaml                  Calico zero-trust policy spec
│   └── enforce-policies.sh            iptables enforcement script
├── scripts/
│   ├── orchestrator.py                Self-healing and auto-scaling daemon
│   └── load_test.py                   50-thread concurrent load tester
├── podman-compose.yml                 Complete platform definition
├── start.sh                           Startup script with ASCII banner
└── README.md                          This file
```

---

## Known Limitations

**iptables bypass in WSL2** — The `enforce-policies.sh` script applies iptables rules correctly but they are bypassed by rootless Podman's userspace networking in WSL2. Real enforcement is the network-level isolation (layers 1 and 2 of the security model). The Calico YAML is the policy specification for a Kubernetes deployment.

**Auto-scaling trigger requires artificial load** — The backend serves lightweight JSON responses and rarely reaches 70% CPU naturally. Use the CPU stress commands or load test script to demonstrate scaling.

**No JWT token refresh** — Tokens expire after 24 hours with no refresh mechanism. Re-login required after expiry.

**Single PostgreSQL instance** — No replication. PostgreSQL downtime affects all three dependent services simultaneously.

**data-service under extreme load** — The ThreadedConnectionPool (`maxconn=10`) can exhaust under heavy concurrent logging. Resolved by increasing `maxconn` or implementing an in-memory queue with batch inserts.

---

## Acknowledgements

Built with Podman, Node.js, Python, PostgreSQL, Prometheus, Grafana, and Alertmanager.
All open-source. All free.

---

<div align="center">

Built by **Vishal** — [github.com/vishious17/Podflow](https://github.com/vishious17/Podflow)

</div>