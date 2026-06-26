# PodFlow Honeypot
This service acts as a security trap to detect unauthorized movement within the cluster.

## Configuration
- **SSH Trap:** Port 2222
- **HTTP/Admin Trap:** Port 8888
- **Metrics:** Port 8888 (`/metrics`)

## Labels
Used by Network Policies: `podflow.service: honeypot`
