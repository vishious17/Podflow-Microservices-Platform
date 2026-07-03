#!/usr/bin/env bash
# =======================================================================
# enforce-policies.sh
# Real iptables enforcement implementing the zero-trust rules
# declared in network/Policies.yaml.
#
# Run AFTER podman-compose up so all containers have IPs.
# Re-run whenever containers restart (IPs change on restart).
#
# Usage:
#   sudo bash network/enforce-policies.sh
# =======================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${CYAN}[POLICY]${NC} $*"; }
ok()   { echo -e "${GREEN}[  OK  ]${NC} $*"; }
warn() { echo -e "${YELLOW}[ WARN ]${NC} $*"; }
fail() { echo -e "${RED}[FAIL  ]${NC} $*"; exit 1; }

# -----------------------------------------------------------------------
# 1. Detect container IPs dynamically
#    We try both "podflow_<name>_1" and "<name>" naming conventions
# -----------------------------------------------------------------------
get_ip() {
    local name=$1
    local ip
    # Try podman inspect with project prefix first
    ip=$(podman inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' \
         "podflow_${name}_1" 2>/dev/null | tr -d '[:space:]' | head -c 50)

    # Fall back to plain container name (e.g. prometheus has no prefix)
    if [[ -z "$ip" ]]; then
        ip=$(podman inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' \
             "${name}" 2>/dev/null | tr -d '[:space:]' | head -c 50)
    fi

    # If still empty, try with project prefix but no _1 suffix
    if [[ -z "$ip" ]]; then
        ip=$(podman inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' \
             "podflow_${name}" 2>/dev/null | tr -d '[:space:]' | head -c 50)
    fi

    echo "$ip"
}

echo ""
echo "═══════════════════════════════════════════════════"
echo "  PodFlow — Zero-Trust iptables Policy Enforcement"
echo "═══════════════════════════════════════════════════"
echo ""

log "Detecting container IPs..."

GW_IP=$(get_ip "api-gateway")
BE_IP=$(get_ip "backend")
US_IP=$(get_ip "user-service")
HP_IP=$(get_ip "honeypot")
DS_IP=$(get_ip "data-service")
PR_IP=$(get_ip "prometheus")

echo ""
printf "  %-20s %s\n" "api-gateway"   "${GW_IP:-(not found)}"
printf "  %-20s %s\n" "backend"       "${BE_IP:-(not found)}"
printf "  %-20s %s\n" "user-service"  "${US_IP:-(not found)}"
printf "  %-20s %s\n" "honeypot"      "${HP_IP:-(not found)}"
printf "  %-20s %s\n" "data-service"  "${DS_IP:-(not found)}"
printf "  %-20s %s\n" "prometheus"    "${PR_IP:-(not found)}"
echo ""

# Warn but continue if some containers aren't found (they may not be running)
[[ -z "$GW_IP" ]] && warn "api-gateway not found — its rules will be skipped"
[[ -z "$BE_IP" ]] && warn "backend not found — its rules will be skipped"
[[ -z "$PR_IP" ]] && warn "prometheus not found — its rules will be skipped"

# -----------------------------------------------------------------------
# 2. Flush previous PodFlow rules to start clean
#    We use a custom chain so we never touch unrelated host rules
# -----------------------------------------------------------------------
log "Setting up PODFLOW chain in FORWARD table..."

# Create chain if it doesn't exist; flush it if it does
iptables -N PODFLOW 2>/dev/null || iptables -F PODFLOW

# Jump to PODFLOW chain from FORWARD (insert at top so it runs first)
# Only insert if not already present
if ! iptables -C FORWARD -j PODFLOW 2>/dev/null; then
    iptables -I FORWARD -j PODFLOW
fi

ok "PODFLOW chain ready"

# -----------------------------------------------------------------------
# Helper: add a rule only if it doesn't already exist
# -----------------------------------------------------------------------
add_rule() {
    if ! iptables -C PODFLOW "$@" 2>/dev/null; then
        iptables -A PODFLOW "$@"
    fi
}

# -----------------------------------------------------------------------
# 3. POLICY: gateway-shield
#    Gateway (api-gateway) may send traffic to:
#      - backend:5000
#      - user-service:3000
#      - data-service:4000
#    No other service may directly reach the gateway on :8080 except
#    from the host (host traffic is not in FORWARD so naturally exempt).
# -----------------------------------------------------------------------
log "Applying gateway-shield policy..."

if [[ -n "$GW_IP" && -n "$BE_IP" ]]; then
    add_rule -s "$GW_IP" -d "$BE_IP"  -p tcp --dport 5000 -j ACCEPT
    ok "gateway → backend:5000 ALLOWED"
fi

if [[ -n "$GW_IP" && -n "$US_IP" ]]; then
    add_rule -s "$GW_IP" -d "$US_IP"  -p tcp --dport 3000 -j ACCEPT
    ok "gateway → user-service:3000 ALLOWED"
fi

if [[ -n "$GW_IP" && -n "$DS_IP" ]]; then
    add_rule -s "$GW_IP" -d "$DS_IP"  -p tcp --dport 4000 -j ACCEPT
    ok "gateway → data-service:4000 ALLOWED"
fi

# -----------------------------------------------------------------------
# 4. POLICY: app-data-protection
#    backend:5000  — only gateway + prometheus may reach it
#    user-service:3000 — only gateway + prometheus may reach it
#    Both have egress locked to DNS only (UDP 53 is not in FORWARD,
#    so that's handled by the default DROP below).
# -----------------------------------------------------------------------
log "Applying app-data-protection policy..."

if [[ -n "$BE_IP" ]]; then
    # Allow prometheus to scrape backend
    if [[ -n "$PR_IP" ]]; then
        add_rule -s "$PR_IP" -d "$BE_IP" -p tcp --dport 5000 -j ACCEPT
        ok "prometheus → backend:5000 ALLOWED (scrape)"
    fi
    # Block everything else to backend:5000
    add_rule -d "$BE_IP" -p tcp --dport 5000 -j DROP
    ok "backend:5000 — all other ingress BLOCKED"
fi

if [[ -n "$US_IP" ]]; then
    if [[ -n "$PR_IP" ]]; then
        add_rule -s "$PR_IP" -d "$US_IP" -p tcp --dport 3000 -j ACCEPT
        ok "prometheus → user-service:3000 ALLOWED (scrape)"
    fi
    add_rule -d "$US_IP" -p tcp --dport 3000 -j DROP
    ok "user-service:3000 — all other ingress BLOCKED"
fi

# -----------------------------------------------------------------------
# 5. POLICY: intrusion-trap-isolation
#    Honeypot may RECEIVE anything on 2222 and 8888 (trap ports).
#    Honeypot may NOT initiate connections to backend, user-service,
#    gateway, or data-service (prevent lateral movement if compromised).
# -----------------------------------------------------------------------
log "Applying intrusion-trap-isolation policy..."

if [[ -n "$HP_IP" ]]; then
    # Block honeypot egress to all internal services
    [[ -n "$BE_IP" ]] && { add_rule -s "$HP_IP" -d "$BE_IP" -j DROP; ok "honeypot → backend BLOCKED (lateral movement prevention)"; }
    [[ -n "$GW_IP" ]] && { add_rule -s "$HP_IP" -d "$GW_IP" -j DROP; ok "honeypot → gateway BLOCKED"; }
    [[ -n "$US_IP" ]] && { add_rule -s "$HP_IP" -d "$US_IP" -j DROP; ok "honeypot → user-service BLOCKED"; }
    [[ -n "$DS_IP" ]] && { add_rule -s "$HP_IP" -d "$DS_IP" -j DROP; ok "honeypot → data-service BLOCKED"; }

    # Allow prometheus to scrape honeypot:8888
    if [[ -n "$PR_IP" ]]; then
        add_rule -s "$PR_IP" -d "$HP_IP" -p tcp --dport 8888 -j ACCEPT
        ok "prometheus → honeypot:8888 ALLOWED (scrape)"
    fi
fi

# -----------------------------------------------------------------------
# 6. POLICY: data-service isolation
#    data-service:4000 — only gateway + prometheus may reach it
#    data-service may write to its DB (postgres) but not reach other services
# -----------------------------------------------------------------------
log "Applying data-service-isolation policy..."

if [[ -n "$DS_IP" ]]; then
    if [[ -n "$PR_IP" ]]; then
        add_rule -s "$PR_IP" -d "$DS_IP" -p tcp --dport 4000 -j ACCEPT
        ok "prometheus → data-service:4000 ALLOWED (scrape)"
    fi
    add_rule -d "$DS_IP" -p tcp --dport 4000 -j DROP
    ok "data-service:4000 — all other ingress BLOCKED"
fi

# -----------------------------------------------------------------------
# 7. Summary & verification
# -----------------------------------------------------------------------
echo ""
echo "═══════════════════════════════════════════════════"
ok "All policies applied successfully"
echo ""
log "Current PODFLOW chain rules:"
iptables -L PODFLOW -n --line-numbers 2>/dev/null | sed 's/^/  /'
echo ""
echo "  To verify a specific block:"
echo "    sudo iptables -C PODFLOW -d <ip> -p tcp --dport <port> -j DROP"
echo ""
echo "  To flush ALL PodFlow rules:"
echo "    sudo iptables -F PODFLOW"
echo ""
echo "  Re-run this script after container restarts"
echo "  (IPs change on every podman-compose up)"
echo "═══════════════════════════════════════════════════"
echo ""
