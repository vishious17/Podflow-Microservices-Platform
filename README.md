# PodFlow — Containerized Microservices Platform

A self-healing, auto-scaling microservices platform built with Podman,
demonstrating production-grade patterns without Kubernetes.

## Architecture

```
Internet -> api-gateway:8080
               -> /api/users/*    -> user-service:3000  (PostgreSQL CRUD)
               -> /api/data/*     -> backend:5000        (PostgreSQL CRUD)
               -> /api/logs/*     -> data-service:4000   (analytics)
               -> logs all requests to data-service (async)

postgres:5432  <- shared database (users, data_entries, request_logs)
honeypot:8888  <- HTTP + SSH traps, SQLite intrusion log, live dashboard
prometheus:9090 <- scrapes all 7 services every 5s
grafana:3000   <- provisioned dashboard, auto-loaded on startup
orchestrator   <- runs on host, heals + scales containers every 10s
```

## Services

| Service      | Port | Description                        |
|--------------|------|------------------------------------|
| api-gateway  | 8080 | Single entry point, proxies all routes |
| user-service | 3000 | User register/login/CRUD (PostgreSQL) |
| backend      | 5000 | Data entries CRUD (PostgreSQL) |
| data-service | 4000 | Request logging + analytics |
| honeypot     | 8888 | HTTP/SSH traps, intrusion dashboard |
| prometheus   | 9090 | Metrics scraping |
| grafana      | 3000 | Dashboards |
| postgres     | 5432 | Shared database |

## Prerequisites

- Podman
- podman-compose
- Python 3

## Setup and Run

```bash
bash setup.sh
podman-compose up --build
```

In a second terminal:
```bash
python3 scripts/orchestrator.py
```

After compose is up, apply iptables policies:
```bash
sudo bash network/enforce-policies.sh
```

## API Reference

### Users (via gateway)

```
POST /api/users/register   { "name": "...", "email": "...", "password": "..." }
POST /api/users/login      { "email": "...", "password": "..." }
GET  /api/users
GET  /api/users/:id
PUT  /api/users/:id        { "name": "...", "email": "..." }
DELETE /api/users/:id
```

### Data Entries (via gateway)

```
GET    /api/data
POST   /api/data           { "title": "...", "content": "...", "author_id": 1 }
GET    /api/data/:id
PUT    /api/data/:id       { "title": "...", "content": "..." }
DELETE /api/data/:id
```

### Analytics (via gateway)

```
GET /api/analytics
GET /api/logs?service=api-gateway&limit=50
```

### Honeypot

```
GET  /honeypot-dashboard   Live intrusion dashboard
GET  /intrusions           JSON list of all intrusions
GET  /admin                Fake admin panel (trap)
GET  /phpmyadmin           Fake phpMyAdmin (trap)
GET  /.env                 Fake env file (trap)
GET  /shell                Fake web terminal (trap)
```

## Load Testing (triggers auto-scaling)

```bash
python3 scripts/load_test.py 60
```

Or manually spike CPU inside the backend container:
```bash
podman exec podflow_backend_1 sh -c "while true; do echo 1 > /dev/null; done"
```

Watch the orchestrator output for CPU readings and scale events.

## Monitoring

- Prometheus: http://localhost:9090/targets
- Grafana:    http://localhost:3000  (admin/admin)
- Honeypot:  http://localhost:8888/honeypot-dashboard

## Network Isolation

Two bridge networks provide the primary isolation:
- `public_net` + `service_net`: api-gateway only (dual-homed)
- `service_net`: all internal services
- `honeypot_net` (internal: true): honeypot fully isolated

`network/Policies.yaml` contains the equivalent Calico NetworkPolicy
specification for deployment to a Kubernetes cluster with Calico CNI.
`network/enforce-policies.sh` applies iptables rules on bare-metal Linux
(bypassed in WSL2 due to rootless Podman's userspace networking).

## Project Structure

```
Podflow/
├── db/
│   └── init.sql
├── services/
│   ├── api-gateway/
│   ├── user-service/
│   ├── backend/
│   ├── data-service/
│   └── honeypot/
├── monitoring/
│   ├── prometheus/
│   └── grafana/
├── network/
│   ├── Policies.yaml
│   └── enforce-policies.sh
├── scripts/
│   ├── orchestrator.py
│   └── load_test.py
├── podman-compose.yml
└── setup.sh
```
