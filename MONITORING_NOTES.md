# Monitoring & Observability

## Scope
This document covers monitoring implemented by the team
without overlapping networking or security work.

## Implemented
- Prometheus-compatible metrics added to:
  - API Gateway
  - Backend/User Service
- Default Node.js process metrics enabled
- HTTP request counters exposed

## Metrics Exposed
- http_requests_total
- gateway_http_requests_total
- process_cpu_seconds_total
- process_resident_memory_bytes

## Access
- Metrics are available internally via `/metrics`
- Designed for Prometheus scraping

## Next Steps
- Add Prometheus container
- Configure scrape targets
- Build Grafana dashboards

## Ownership
Monitoring and observability layer
