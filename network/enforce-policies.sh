#!/usr/bin/env bash
# iptables enforcement matching network/Policies.yaml zero-trust intent.
# Run after podman-compose up. Re-run after container restarts (IPs change).
# Usage: sudo bash network/enforce-policies.sh

set -euo pipefail

log()  { echo "[POLICY] $*"; }
ok()   { echo "[  OK  ] $*"; }
warn() { echo "[ WARN ] $*"; }

get_ip() {
    local name=$1
    local ip

    ip=$(sudo -u "$SUDO_USER" podman inspect \
         -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' \
         "podflow_${name}_1" 2>/dev/null \
         | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' | tail -1)

    if [[ -z "$ip" ]]; then
        ip=$(sudo -u "$SUDO_USER" podman inspect \
             -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' \
             "${name}" 2>/dev/null \
             | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' | tail -1)
    fi

    echo "$ip"
}

echo ""
echo "==================================================="
echo "  PodFlow -- Zero-Trust iptables Policy Enforcement"
echo "==================================================="
echo ""

log "Detecting container IPs..."

GW_IP=$(get_ip "api-gateway")
BE_IP=$(get_ip "backend")
US_IP=$(get_ip "user-service")
HP_IP=$(get_ip "honeypot")
DS_IP=$(get_ip "data-service")
PR_IP=$(get_ip "prometheus")

printf "  %-20s %s\n" "api-gateway"   "${GW_IP:-(not found)}"
printf "  %-20s %s\n" "backend"       "${BE_IP:-(not found)}"
printf "  %-20s %s\n" "user-service"  "${US_IP:-(not found)}"
printf "  %-20s %s\n" "honeypot"      "${HP_IP:-(not found)}"
printf "  %-20s %s\n" "data-service"  "${DS_IP:-(not found)}"
printf "  %-20s %s\n" "prometheus"    "${PR_IP:-(not found)}"
echo ""

[[ -z "$GW_IP" ]] && warn "api-gateway not found -- its rules will be skipped"
[[ -z "$BE_IP" ]] && warn "backend not found -- its rules will be skipped"
[[ -z "$PR_IP" ]] && warn "prometheus not found -- its rules will be skipped"

log "Setting up PODFLOW chain..."
iptables -N PODFLOW 2>/dev/null || iptables -F PODFLOW
if ! iptables -C FORWARD -j PODFLOW 2>/dev/null; then
    iptables -I FORWARD -j PODFLOW
fi
ok "PODFLOW chain ready"

add_rule() {
    if ! iptables -C PODFLOW "$@" 2>/dev/null; then
        iptables -A PODFLOW "$@"
    fi
}

log "Applying gateway-shield policy..."
if [[ -n "$GW_IP" && -n "$BE_IP" ]]; then
    add_rule -s "$GW_IP" -d "$BE_IP" -p tcp --dport 5000 -j ACCEPT
    ok "gateway -> backend:5000 ALLOWED"
fi
if [[ -n "$GW_IP" && -n "$US_IP" ]]; then
    add_rule -s "$GW_IP" -d "$US_IP" -p tcp --dport 3000 -j ACCEPT
    ok "gateway -> user-service:3000 ALLOWED"
fi
if [[ -n "$GW_IP" && -n "$DS_IP" ]]; then
    add_rule -s "$GW_IP" -d "$DS_IP" -p tcp --dport 4000 -j ACCEPT
    ok "gateway -> data-service:4000 ALLOWED"
fi

log "Applying app-data-protection policy..."
if [[ -n "$BE_IP" ]]; then
    [[ -n "$PR_IP" ]] && { add_rule -s "$PR_IP" -d "$BE_IP" -p tcp --dport 5000 -j ACCEPT; ok "prometheus -> backend:5000 ALLOWED"; }
    add_rule -d "$BE_IP" -p tcp --dport 5000 -j DROP
    ok "backend:5000 -- all other ingress BLOCKED"
fi
if [[ -n "$US_IP" ]]; then
    [[ -n "$PR_IP" ]] && { add_rule -s "$PR_IP" -d "$US_IP" -p tcp --dport 3000 -j ACCEPT; ok "prometheus -> user-service:3000 ALLOWED"; }
    add_rule -d "$US_IP" -p tcp --dport 3000 -j DROP
    ok "user-service:3000 -- all other ingress BLOCKED"
fi

log "Applying intrusion-trap-isolation policy..."
if [[ -n "$HP_IP" ]]; then
    [[ -n "$BE_IP" ]] && { add_rule -s "$HP_IP" -d "$BE_IP" -j DROP; ok "honeypot -> backend BLOCKED"; }
    [[ -n "$GW_IP" ]] && { add_rule -s "$HP_IP" -d "$GW_IP" -j DROP; ok "honeypot -> gateway BLOCKED"; }
    [[ -n "$US_IP" ]] && { add_rule -s "$HP_IP" -d "$US_IP" -j DROP; ok "honeypot -> user-service BLOCKED"; }
    [[ -n "$DS_IP" ]] && { add_rule -s "$HP_IP" -d "$DS_IP" -j DROP; ok "honeypot -> data-service BLOCKED"; }
    [[ -n "$PR_IP" ]] && { add_rule -s "$PR_IP" -d "$HP_IP" -p tcp --dport 8888 -j ACCEPT; ok "prometheus -> honeypot:8888 ALLOWED"; }
fi

log "Applying data-service-isolation policy..."
if [[ -n "$DS_IP" ]]; then
    [[ -n "$PR_IP" ]] && { add_rule -s "$PR_IP" -d "$DS_IP" -p tcp --dport 4000 -j ACCEPT; ok "prometheus -> data-service:4000 ALLOWED"; }
    add_rule -d "$DS_IP" -p tcp --dport 4000 -j DROP
    ok "data-service:4000 -- all other ingress BLOCKED"
fi

echo ""
echo "==================================================="
ok "All policies applied"
echo ""
log "Current PODFLOW chain:"
iptables -L PODFLOW -n --line-numbers 2>/dev/null | sed 's/^/  /'
echo ""
echo "  Flush all rules : sudo iptables -F PODFLOW"
echo "  Re-run after    : podman-compose up (IPs change on restart)"
echo "==================================================="
echo ""
