from flask import Flask, request, jsonify, Response
from prometheus_client import Counter, generate_latest
import threading
import socket
import time
from datetime import datetime

app = Flask(__name__)

# Metrics
INTRUSION_ATTEMPTS = Counter('honeypot_intrusion_attempts_total', 'Total intrusion attempts', ['type', 'source_ip'])
SUSPICIOUS_REQUESTS = Counter('honeypot_suspicious_requests_total', 'Suspicious HTTP requests', ['endpoint', 'source_ip'])

def log_intrusion(intrusion_type, source, details):
    timestamp = datetime.now().isoformat()
    print(f"[{timestamp}] INTRUSION DETECTED: {intrusion_type} from {source}: {details}")

def fake_ssh_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('0.0.0.0', 2222))
    server_socket.listen(5)
    while True:
        try:
            client_socket, address = server_socket.accept()
            source_ip = address[0]
            INTRUSION_ATTEMPTS.labels(type='ssh', source_ip=source_ip).inc()
            log_intrusion('SSH', source_ip, 'Connection attempt to fake SSH')
            client_socket.send(b"SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.1\r\n")
            time.sleep(2)
            client_socket.close()
        except Exception as e:
            print(f"Error: {e}")

@app.route('/admin')
@app.route('/phpmyadmin')
@app.route('/.env')
def fake_admin():
    source_ip = request.remote_addr
    SUSPICIOUS_REQUESTS.labels(endpoint=request.path, source_ip=source_ip).inc()
    log_intrusion('HTTP', source_ip, f'Attempted access to {request.path}')
    return "<h2>Administrator Login</h2><form><input type='text'><input type='password'><button>Login</button></form>", 200

@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype='text/plain; version=0.0.4; charset=utf-8')

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'honeypot'}), 200

if __name__ == '__main__':
    threading.Thread(target=fake_ssh_server, daemon=True).start()
    app.run(host='0.0.0.0', port=8888)
