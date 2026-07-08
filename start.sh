#!/usr/bin/env bash
# Usage:
#   bash start.sh              build and start
#   bash start.sh --no-build   start without rebuilding images
#   bash start.sh --down       stop everything

set -e

CY='\033[0;36m'
GR='\033[0;32m'
YL='\033[1;33m'
BL='\033[0;34m'
WH='\033[1;37m'
DM='\033[2m'
RD='\033[0;31m'
NC='\033[0m'
BD='\033[1m'

print_logo() {
  echo -e "${CY}"
  cat << 'LOGO'
  ██████╗  ██████╗ ██████╗ ███████╗██╗      ██████╗ ██╗    ██╗
  ██╔══██╗██╔═══██╗██╔══██╗██╔════╝██║     ██╔═══██╗██║    ██║
  ██████╔╝██║   ██║██║  ██║█████╗  ██║     ██║   ██║██║ █╗ ██║
  ██╔═══╝ ██║   ██║██║  ██║██╔══╝  ██║     ██║   ██║██║███╗██║
  ██║     ╚██████╔╝██████╔╝██║     ███████╗╚██████╔╝╚███╔███╔╝
  ╚═╝      ╚═════╝ ╚═════╝ ╚═╝     ╚══════╝ ╚═════╝  ╚══╝╚══╝
LOGO
  echo -e "${NC}"
  echo -e "${DM}  Advanced Containerized Microservices Platform  |  v3.0  |  Podman${NC}"
  echo ""
}

# ── Stop ────────────────────────────────────────────────────
if [[ "$1" == "--down" ]]; then
  echo -e "${YL}  Stopping PodFlow...${NC}"
  podman-compose down
  echo -e "${GR}  All services stopped.${NC}"
  exit 0
fi

# ── Generate certs if missing ────────────────────────────────
if [[ ! -f certs/server.crt ]]; then
  echo -e "${YL}  TLS certificates not found. Generating...${NC}"
  bash certs/generate-certs.sh
  echo ""
fi

# ── Start compose ────────────────────────────────────────────
if [[ "$1" == "--no-build" ]]; then
  echo -e "${YL}  Starting services (no rebuild)...${NC}"
  podman-compose up -d 2>&1
else
  echo -e "${YL}  Building and starting services...${NC}"
  echo -e "${DM}  This may take a few minutes on first run.${NC}"
  echo ""
  podman-compose up --build -d 2>&1
fi

# ── Logo appears here — just before service status ───────────
clear
print_logo

echo -e "${YL}  Waiting for services to become ready...${NC}"
echo ""

# ── Per-service health wait ──────────────────────────────────
wait_for() {
  local url=$1
  local max=40
  local count=0
  while ! curl -sf "$url" > /dev/null 2>&1; do
    sleep 1
    count=$((count + 1))
    [[ $count -ge $max ]] && return 1
  done
  return 0
}

check_svc() {
  local name=$1
  local url=$2
  if wait_for "$url"; then
    printf "  ${GR}%-12s${NC} %s\n" "ONLINE" "$name"
  else
    printf "  ${RD}%-12s${NC} %s\n" "TIMEOUT" "$name"
  fi
}

check_svc "API Gateway"    "http://localhost:8080/health"
check_svc "Backend"        "http://localhost:5000/health"
check_svc "User Service"   "http://localhost:5000/users"
check_svc "Data Service"   "http://localhost:4000/health"
check_svc "Honeypot"       "http://localhost:8888/health"
check_svc "Prometheus"     "http://localhost:9090/-/healthy"
check_svc "Alertmanager"   "http://localhost:9093/-/healthy"
check_svc "Grafana"        "http://localhost:3000/api/health"

# ── URL table ────────────────────────────────────────────────
echo ""
echo -e "${CY}  ╔═══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CY}  ║${NC}                    ${BD}${WH}PodFlow is ready${NC}                                  ${CY}║${NC}"
echo -e "${CY}  ╠═══════════════════════════════════════════════════════════════════╣${NC}"
echo -e "${CY}  ║${NC}                                                                   ${CY}║${NC}"
printf "${CY}  ║${NC}   ${GR}%-24s${NC}  ${BL}%-40s${NC} ${CY}║${NC}\n"  "Web Dashboard"        "http://localhost:8080"
printf "${CY}  ║${NC}   ${GR}%-24s${NC}  ${BL}%-40s${NC} ${CY}║${NC}\n"  "Honeypot Dashboard"   "http://localhost:8888/honeypot-dashboard"
printf "${CY}  ║${NC}   ${GR}%-24s${NC}  ${BL}%-40s${NC} ${CY}║${NC}\n"  "Grafana"              "http://localhost:3000  (admin / admin)"
printf "${CY}  ║${NC}   ${GR}%-24s${NC}  ${BL}%-40s${NC} ${CY}║${NC}\n"  "Prometheus"           "http://localhost:9090"
printf "${CY}  ║${NC}   ${GR}%-24s${NC}  ${BL}%-40s${NC} ${CY}║${NC}\n"  "Alertmanager"         "http://localhost:9093"
printf "${CY}  ║${NC}   ${GR}%-24s${NC}  ${BL}%-40s${NC} ${CY}║${NC}\n"  "API (HTTPS)"          "https://localhost:8443"
echo -e "${CY}  ║${NC}                                                                   ${CY}║${NC}"
echo -e "${CY}  ╠═══════════════════════════════════════════════════════════════════╣${NC}"
echo -e "${CY}  ║${NC}                                                                   ${CY}║${NC}"
printf "${CY}  ║${NC}   ${DM}%-24s${NC}  ${DM}%-40s${NC} ${CY}║${NC}\n"  "Start orchestrator"   "python3 scripts/orchestrator.py"
printf "${CY}  ║${NC}   ${DM}%-24s${NC}  ${DM}%-40s${NC} ${CY}║${NC}\n"  "Run load test"        "python3 scripts/load_test.py 60"
printf "${CY}  ║${NC}   ${DM}%-24s${NC}  ${DM}%-40s${NC} ${CY}║${NC}\n"  "Follow logs"          "podman-compose logs -f"
printf "${CY}  ║${NC}   ${DM}%-24s${NC}  ${DM}%-40s${NC} ${CY}║${NC}\n"  "Stop"                 "bash start.sh --down"
echo -e "${CY}  ║${NC}                                                                   ${CY}║${NC}"
echo -e "${CY}  ╚═══════════════════════════════════════════════════════════════════╝${NC}"
echo ""
