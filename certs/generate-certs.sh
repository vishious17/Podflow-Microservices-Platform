#!/usr/bin/env bash
# Generates a self-signed TLS certificate for the api-gateway HTTPS server.
# Run once before starting the platform.
# Usage: bash certs/generate-certs.sh

set -e

CERT_DIR="$(dirname "$0")"

if [[ -f "$CERT_DIR/server.crt" && -f "$CERT_DIR/server.key" ]]; then
    echo "Certificates already exist in $CERT_DIR — skipping generation."
    echo "Delete server.crt and server.key to regenerate."
    exit 0
fi

if ! command -v openssl >/dev/null 2>&1; then
    echo "openssl not found. Install it with: sudo apt-get install openssl"
    exit 1
fi

openssl req -x509 \
    -newkey rsa:4096 \
    -keyout "$CERT_DIR/server.key" \
    -out    "$CERT_DIR/server.crt" \
    -days   365 \
    -nodes \
    -subj   "/C=IN/ST=Karnataka/L=Mysuru/O=PodFlow/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

chmod 600 "$CERT_DIR/server.key"

echo ""
echo "Certificates generated:"
echo "  $CERT_DIR/server.crt  (public certificate)"
echo "  $CERT_DIR/server.key  (private key, keep secret)"
echo ""
echo "HTTPS will be available on port 8443 after podman-compose up --build"
echo "Browsers will show a security warning — this is expected for self-signed certs."
echo "Accept the warning or use: curl -k https://localhost:8443/health"
