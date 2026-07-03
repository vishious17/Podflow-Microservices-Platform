#!/usr/bin/env python3

from flask import Flask, request, jsonify, Response, render_template_string
from prometheus_client import Counter, Gauge, generate_latest
import threading
import socket
import sqlite3
import requests
import json
import os
from datetime import datetime

app = Flask(__name__)

# ==========================================
# PROMETHEUS METRICS
# ==========================================
INTRUSION_ATTEMPTS = Counter(
    'honeypot_intrusion_attempts_total',
    'Total intrusion attempts',
    ['type', 'source_ip', 'country']
)
SUSPICIOUS_REQUESTS = Counter(
    'honeypot_suspicious_requests_total',
    'Suspicious HTTP requests',
    ['endpoint', 'method', 'source_ip']
)
LOGIN_ATTEMPTS = Counter(
    'honeypot_login_attempts_total',
    'Fake login form submissions captured',
    ['endpoint', 'source_ip']
)
UNIQUE_ATTACKERS = Gauge(
    'honeypot_unique_attackers_total',
    'Total unique attacker IPs seen'
)

# ==========================================
# SQLITE DATABASE
# ==========================================
DB_PATH = '/data/honeypot.db'

def init_db():
    os.makedirs('/data', exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS intrusions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            type        TEXT NOT NULL,
            source_ip   TEXT NOT NULL,
            country     TEXT,
            city        TEXT,
            isp         TEXT,
            org         TEXT,
            endpoint    TEXT,
            method      TEXT,
            username_attempted  TEXT,
            password_attempted  TEXT,
            commands    TEXT,
            user_agent  TEXT,
            headers     TEXT,
            body        TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("Database initialized at", DB_PATH)

def save_intrusion(data):
    """Save intrusion record to SQLite and update Prometheus gauges."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            INSERT INTO intrusions
            (timestamp, type, source_ip, country, city, isp, org,
             endpoint, method, username_attempted, password_attempted,
             commands, user_agent, headers, body)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            data.get('timestamp'),
            data.get('type'),
            data.get('source_ip'),
            data.get('country', 'Unknown'),
            data.get('city', 'Unknown'),
            data.get('isp', 'Unknown'),
            data.get('org', 'Unknown'),
            data.get('endpoint'),
            data.get('method'),
            data.get('username_attempted'),
            data.get('password_attempted'),
            data.get('commands'),
            data.get('user_agent'),
            data.get('headers'),
            data.get('body'),
        ))
        conn.commit()

        # Update unique attackers gauge
        c.execute('SELECT COUNT(DISTINCT source_ip) FROM intrusions')
        UNIQUE_ATTACKERS.set(c.fetchone()[0])
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] {e}")

def fetch_intrusions(limit=200):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM intrusions ORDER BY timestamp DESC LIMIT ?', (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def fetch_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM intrusions')
    total = c.fetchone()[0]
    c.execute('SELECT COUNT(DISTINCT source_ip) FROM intrusions')
    unique_ips = c.fetchone()[0]
    c.execute('SELECT COUNT(DISTINCT country) FROM intrusions')
    countries = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM intrusions WHERE type LIKE '%LOGIN%'")
    logins = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM intrusions WHERE type = 'SHELL_COMMAND'")
    shell_cmds = c.fetchone()[0]
    conn.close()
    return dict(total=total, unique_ips=unique_ips,
                countries=countries, logins=logins, shell_cmds=shell_cmds)

# ==========================================
# GEOLOCATION (ip-api.com — free, no key)
# ==========================================
_geo_cache = {}

def get_location(ip):
    """Resolve IP to geographic location. Caches results."""
    # Private/local IPs
    if (ip in ('127.0.0.1', '::1', 'localhost')
            or ip.startswith('10.')
            or ip.startswith('192.168.')
            or ip.startswith('172.')
            or ip.startswith('fd')):
        return {'country': 'Local Network', 'city': 'Internal',
                'isp': 'Internal', 'org': 'Internal'}

    if ip in _geo_cache:
        return _geo_cache[ip]

    try:
        r = requests.get(
            f'http://ip-api.com/json/{ip}?fields=status,country,city,isp,org',
            timeout=3
        )
        d = r.json()
        if d.get('status') == 'success':
            result = {
                'country': d.get('country', 'Unknown'),
                'city':    d.get('city',    'Unknown'),
                'isp':     d.get('isp',     'Unknown'),
                'org':     d.get('org',     'Unknown'),
            }
            _geo_cache[ip] = result
            return result
    except Exception:
        pass

    return {'country': 'Unknown', 'city': 'Unknown',
            'isp': 'Unknown', 'org': 'Unknown'}

# ==========================================
# CORE LOGGING FUNCTION
# ==========================================
def log_intrusion(intrusion_type, source_ip, details, extra=None):
    """Log an intrusion event: print to console, save to DB, update metrics."""
    timestamp = datetime.now().isoformat()
    geo = get_location(source_ip)

    print(f"\n{'='*65}")
    print(f"  🚨  INTRUSION [{timestamp}]")
    print(f"  Type      : {intrusion_type}")
    print(f"  IP        : {source_ip}")
    print(f"  Location  : {geo['city']}, {geo['country']}")
    print(f"  ISP       : {geo['isp']}")
    print(f"  Details   : {details}")
    if extra:
        for k, v in extra.items():
            if v:
                print(f"  {k:<10}: {v}")
    print(f"{'='*65}\n")

    record = {
        'timestamp': timestamp,
        'type':      intrusion_type,
        'source_ip': source_ip,
        **geo,
    }
    if extra:
        record.update(extra)

    save_intrusion(record)

    INTRUSION_ATTEMPTS.labels(
        type=intrusion_type,
        source_ip=source_ip,
        country=geo['country']
    ).inc()

# ==========================================
# FAKE SSH SERVER  (captures post-banner data)
# ==========================================
def handle_ssh_client(client_socket, address):
    source_ip = address[0]
    try:
        # Real OpenSSH banner — fools scanners and banner-grabbers
        client_socket.send(b"SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.6\r\n")

        # Collect anything the attacker sends (credentials, key exchange bytes, etc.)
        client_socket.settimeout(10)
        raw_chunks = []
        try:
            while True:
                chunk = client_socket.recv(1024)
                if not chunk:
                    break
                raw_chunks.append(chunk)
        except socket.timeout:
            pass

        # Try to decode what they sent as text, fall back to hex
        all_raw = b"".join(raw_chunks)
        try:
            commands = all_raw.decode('utf-8', errors='replace').strip()
        except Exception:
            commands = all_raw.hex()

        log_intrusion('SSH', source_ip, 'TCP connection to fake SSH port 2222', {
            'endpoint':   'port:2222',
            'method':     'TCP',
            'commands':   commands if commands else '(no data sent after banner)',
            'user_agent': 'SSH Client',
        })
    except Exception as e:
        print(f"[SSH ERROR] {e}")
    finally:
        client_socket.close()

def fake_ssh_server():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('0.0.0.0', 2222))
    srv.listen(10)
    print("Fake SSH server listening on port 2222")
    while True:
        try:
            client, addr = srv.accept()
            t = threading.Thread(target=handle_ssh_client,
                                 args=(client, addr), daemon=True)
            t.start()
        except Exception as e:
            print(f"[SSH ACCEPT ERROR] {e}")

# ==========================================
# HTML TEMPLATES
# ==========================================
_LOGIN_STYLE = """
body{font-family:Arial,sans-serif;background:#1a1a2e;display:flex;
     justify-content:center;align-items:center;height:100vh;margin:0}
.box{background:#16213e;padding:40px;border-radius:8px;
     border:1px solid #0f3460;width:340px}
h2{color:#e94560;text-align:center;margin-bottom:4px}
.sub{color:#888;text-align:center;font-size:12px;margin-bottom:20px}
input{width:100%;padding:11px;margin:6px 0;border:1px solid #0f3460;
      background:#0f3460;color:#fff;border-radius:4px;box-sizing:border-box}
button{width:100%;padding:12px;background:#e94560;color:#fff;border:none;
       border-radius:4px;cursor:pointer;font-size:15px;margin-top:10px}
.footer{text-align:center;color:#444;font-size:11px;margin-top:16px}
"""

def login_page(title, subtitle, action, footer, extra_fields=""):
    return f"""<!DOCTYPE html><html><head><title>{title}</title>
<style>{_LOGIN_STYLE}</style></head><body>
<div class="box">
  <h2>🔒 {title}</h2>
  <p class="sub">{subtitle}</p>
  <form method="POST" action="{action}">
    <input name="username" placeholder="Username" required>
    <input name="password" type="password" placeholder="Password" required>
    {extra_fields}
    <button type="submit">Sign In</button>
  </form>
  <div class="footer">{footer}</div>
</div></body></html>"""

SHELL_HTML = """<!DOCTYPE html>
<html><head><title>WebShell v2.1 — System Access</title>
<style>
body{background:#000;color:#0f0;font-family:'Courier New',monospace;margin:0;padding:16px}
#term{height:78vh;overflow-y:auto;border:1px solid #0f0;padding:10px;margin-bottom:8px}
#iline{display:flex;align-items:center}
#pr{color:#0f0;margin-right:5px;white-space:nowrap}
#ci{background:transparent;border:none;color:#0f0;
    font-family:'Courier New';font-size:14px;flex:1;outline:none}
.r{color:#888}.e{color:#f00}
</style></head>
<body>
<div id="term">
  <div>root@prod-server-01:~# <span class="r">WebShell v2.1.0 — connected</span></div>
  <div class="r">Session: root | Host: 10.0.0.1 | Kernel: 5.15.0-76-generic</div>
  <div id="out"></div>
</div>
<div id="iline"><span id="pr">root@prod-server-01:~# </span>
<input id="ci" autofocus></div>
<script>
const out=document.getElementById('out');
const ci=document.getElementById('ci');
const fake={
  'ls':       'bin boot dev etc home lib media mnt opt proc root run sbin srv sys tmp usr var',
  'ls -la':   'total 64\\ndrwx------ 8 root root 4096 Jun 30 09:12 .\\ndrwxr-xr-x 20 root root 4096 Jun 30 09:10 ..\\n-rw------- 1 root root 1234 Jun 30 09:12 .bash_history',
  'pwd':      '/root',
  'whoami':   'root',
  'id':       'uid=0(root) gid=0(root) groups=0(root)',
  'hostname': 'prod-server-01',
  'uname -a': 'Linux prod-server-01 5.15.0-76-generic #83-Ubuntu SMP x86_64 GNU/Linux',
  'ps aux':   'USER  PID %CPU %MEM COMMAND\\nroot    1  0.0  0.1 /sbin/init\\nnginx 445  0.2  0.4 nginx: master process',
  'cat /etc/passwd': 'root:x:0:0:root:/root:/bin/bash\\ndaemon:x:1:1:daemon:/usr/sbin/nologin',
  'cat /etc/shadow': 'Permission denied',
  'ifconfig': 'eth0: inet 10.0.0.1 netmask 255.255.255.0\\nlo: inet 127.0.0.1',
  'netstat -an': 'Active Internet connections\\ntcp 0.0.0.0:22  LISTEN\\ntcp 0.0.0.0:80  LISTEN',
  'history':  '  1  ls -la\\n  2  cat /etc/passwd\\n  3  wget http://malware.example.com/payload',
  'help':     'bash: GNU bash 5.1. Type commands and press Enter.',
  'exit':     'logout',
  'clear':    '__CLEAR__',
};
ci.addEventListener('keydown', async e=>{
  if(e.key!=='Enter') return;
  const cmd=ci.value.trim(); if(!cmd) return;
  const d=document.createElement('div');
  d.textContent='root@prod-server-01:~# '+cmd; out.appendChild(d);
  await fetch('/shell/exec',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({command:cmd})});
  const r=document.createElement('div'); r.className='r';
  const resp=fake[cmd];
  if(resp==='__CLEAR__'){out.innerHTML='';}
  else{r.style.whiteSpace='pre'; r.textContent=resp||(cmd.split(' ')[0]+': command not found'); out.appendChild(r);}
  ci.value=''; out.scrollTop=out.scrollHeight;
});
</script></body></html>"""

FAKE_ENV = """\
APP_ENV=production
DB_HOST=db.internal.corp.com
DB_PORT=5432
DB_USER=prod_admin
DB_PASSWORD=Sup3r$ecret!Prod2024
DB_NAME=production_main
SECRET_KEY=sk-prod-9f2k4j8x1m3n6p0q5r7s4t1u8v2w5x
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_DEFAULT_REGION=us-east-1
STRIPE_SECRET_KEY=sk_live_51H8Xample2024LiveKey
REDIS_URL=redis://:Pr0d!Redis2024@redis.internal:6379/0
JWT_SECRET=jwt-prod-hs256-super-secret-2024-do-not-share
SMTP_HOST=smtp.corp.com
SMTP_USER=noreply@corp.com
SMTP_PASS=Smtp!Passw0rd2024
"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html><head><title>🍯 Honeypot Dashboard</title>
<meta http-equiv="refresh" content="10">
<style>
*{box-sizing:border-box}
body{font-family:monospace;background:#0d1117;color:#c9d1d9;padding:20px;margin:0}
h1{color:#58a6ff;margin-bottom:4px}
.sub{color:#8b949e;font-size:13px;margin-bottom:20px}
.stats{display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap}
.sb{background:#161b22;border:1px solid #30363d;padding:16px 20px;
    border-radius:6px;flex:1;min-width:120px;text-align:center}
.sn{font-size:30px;font-weight:bold;color:#f85149}
.sl{color:#8b949e;font-size:11px;margin-top:4px}
table{width:100%;border-collapse:collapse;font-size:12px}
th{background:#161b22;color:#58a6ff;padding:10px 8px;
   text-align:left;border-bottom:2px solid #30363d}
td{padding:7px 8px;border-bottom:1px solid #21262d;vertical-align:top;max-width:200px;word-break:break-word}
tr:hover td{background:#161b22}
.badge{padding:2px 7px;border-radius:3px;font-size:11px;font-weight:bold}
.SSH{background:#2d1f00;color:#f0883e}
.HTTP{background:#2d0000;color:#f85149}
.SHELL{background:#1f0030;color:#d2a8ff}
.LOGIN{background:#002d1f;color:#3fb950}
.ip{color:#79c0ff;font-weight:bold}
.loc{color:#8b949e}
</style></head>
<body>
<h1>🍯 PodFlow Honeypot — Live Intrusion Dashboard</h1>
<p class="sub">Auto-refreshes every 10 seconds | All times UTC</p>
<div class="stats">
  <div class="sb"><div class="sn">{{ stats.total }}</div><div class="sl">Total Intrusions</div></div>
  <div class="sb"><div class="sn">{{ stats.unique_ips }}</div><div class="sl">Unique Attackers</div></div>
  <div class="sb"><div class="sn">{{ stats.countries }}</div><div class="sl">Countries</div></div>
  <div class="sb"><div class="sn">{{ stats.logins }}</div><div class="sl">Login Attempts</div></div>
  <div class="sb"><div class="sn">{{ stats.shell_cmds }}</div><div class="sl">Shell Commands</div></div>
</div>
<table>
  <tr>
    <th>Timestamp</th><th>Type</th><th>IP Address</th>
    <th>Location</th><th>ISP</th><th>Endpoint</th>
    <th>Username</th><th>Commands / Data</th>
  </tr>
  {% for r in rows %}
  <tr>
    <td>{{ r.timestamp[:19] }}</td>
    <td><span class="badge {{ r.type.split('_')[0] }}">{{ r.type }}</span></td>
    <td class="ip">{{ r.source_ip }}</td>
    <td class="loc">{{ r.city }}, {{ r.country }}</td>
    <td class="loc">{{ r.isp or '-' }}</td>
    <td>{{ r.endpoint or '-' }}</td>
    <td>{{ r.username_attempted or '-' }}</td>
    <td>{{ (r.commands or r.body or '-')[:120] }}</td>
  </tr>
  {% endfor %}
</table>
</body></html>"""

# ==========================================
# HTTP TRAP ROUTES
# ==========================================

def _capture(req):
    """Extract common fields from a Flask request."""
    body = req.get_data(as_text=True)
    return {
        'method':     req.method,
        'endpoint':   req.path,
        'user_agent': req.headers.get('User-Agent', 'Unknown'),
        'headers':    json.dumps(dict(req.headers), indent=None),
        'body':       body if body else None,
    }


# ---------- Admin panel ----------
@app.route('/admin', methods=['GET', 'POST'])
@app.route('/admin/login', methods=['GET', 'POST'])
def fake_admin():
    ip = request.remote_addr
    extra = _capture(request)
    SUSPICIOUS_REQUESTS.labels(endpoint=request.path,
                               method=request.method, source_ip=ip).inc()

    if request.method == 'POST':
        extra['username_attempted'] = request.form.get('username', '')
        extra['password_attempted'] = request.form.get('password', '')
        LOGIN_ATTEMPTS.labels(endpoint='/admin', source_ip=ip).inc()
        log_intrusion('HTTP_LOGIN_ATTEMPT', ip,
                      f"Admin login → user: '{extra['username_attempted']}'", extra)
        return login_page(
            'Access Denied',
            '⚠ Invalid credentials. This attempt has been logged and reported.',
            '/admin', 'Security Event ID: ' + datetime.now().strftime('%Y%m%d%H%M%S')
        ), 401

    log_intrusion('HTTP_PROBE', ip, 'Admin panel probe', extra)
    return login_page(
        'System Control Panel',
        'Authorized personnel only. All access is monitored.',
        '/admin', 'v3.1.2 © 2024 Internal Systems'
    ), 200


# ---------- phpMyAdmin ----------
@app.route('/phpmyadmin', methods=['GET', 'POST'])
@app.route('/phpmyadmin/index.php', methods=['GET', 'POST'])
def fake_phpmyadmin():
    ip = request.remote_addr
    extra = _capture(request)
    SUSPICIOUS_REQUESTS.labels(endpoint='/phpmyadmin',
                               method=request.method, source_ip=ip).inc()

    if request.method == 'POST':
        extra['username_attempted'] = request.form.get('pma_username', '')
        extra['password_attempted'] = request.form.get('pma_password', '')
        LOGIN_ATTEMPTS.labels(endpoint='/phpmyadmin', source_ip=ip).inc()
        log_intrusion('HTTP_LOGIN_ATTEMPT', ip,
                      f"phpMyAdmin login → user: '{extra['username_attempted']}'", extra)

    log_intrusion('HTTP_PROBE', ip, 'phpMyAdmin probe', extra)
    return login_page(
        'phpMyAdmin 5.2.1',
        'MySQL 8.0.32 | Database Administration',
        '/phpmyadmin',
        'phpMyAdmin | Powered by MySQL',
        '<input name="pma_username" placeholder="MySQL Username">'
        '<input name="pma_password" type="password" placeholder="MySQL Password">'
    ), 200


# ---------- .env exposure ----------
@app.route('/.env')
@app.route('/.env.local')
@app.route('/.env.production')
@app.route('/.env.backup')
def fake_env():
    ip = request.remote_addr
    extra = _capture(request)
    SUSPICIOUS_REQUESTS.labels(endpoint=request.path,
                               method='GET', source_ip=ip).inc()
    log_intrusion('HTTP_ENV_PROBE', ip,
                  f'Environment file probe: {request.path}', extra)
    return FAKE_ENV, 200, {'Content-Type': 'text/plain'}


# ---------- Fake web shell ----------
@app.route('/shell')
@app.route('/webshell')
@app.route('/cmd')
def fake_shell():
    ip = request.remote_addr
    extra = _capture(request)
    SUSPICIOUS_REQUESTS.labels(endpoint=request.path,
                               method='GET', source_ip=ip).inc()
    log_intrusion('HTTP_SHELL_ACCESS', ip,
                  f'Web shell opened: {request.path}', extra)
    return SHELL_HTML, 200


@app.route('/shell/exec', methods=['POST'])
def shell_exec():
    """Receives every command the attacker types in the fake terminal."""
    ip = request.remote_addr
    data = request.get_json(silent=True) or {}
    command = data.get('command', '').strip()

    log_intrusion('SHELL_COMMAND', ip, f'Command: {command}', {
        'endpoint':   '/shell/exec',
        'method':     'POST',
        'commands':   command,
        'user_agent': request.headers.get('User-Agent', 'Unknown'),
        'headers':    json.dumps(dict(request.headers)),
    })
    SUSPICIOUS_REQUESTS.labels(endpoint='/shell/exec',
                               method='POST', source_ip=ip).inc()
    return jsonify({'output': 'executed', 'status': 0})


# ---------- Fake WordPress ----------
@app.route('/wp-admin')
@app.route('/wp-login.php', methods=['GET', 'POST'])
def fake_wordpress():
    ip = request.remote_addr
    extra = _capture(request)
    SUSPICIOUS_REQUESTS.labels(endpoint=request.path,
                               method=request.method, source_ip=ip).inc()
    if request.method == 'POST':
        extra['username_attempted'] = request.form.get('log', '')
        extra['password_attempted'] = request.form.get('pwd', '')
        LOGIN_ATTEMPTS.labels(endpoint='/wp-admin', source_ip=ip).inc()
        log_intrusion('HTTP_LOGIN_ATTEMPT', ip,
                      f"WordPress login → user: '{extra['username_attempted']}'", extra)
    else:
        log_intrusion('HTTP_PROBE', ip, f'WordPress probe: {request.path}', extra)
    return login_page(
        'WordPress 6.5',
        'Powered by WordPress',
        '/wp-login.php',
        'WordPress 6.5 | Powered by WordPress',
        '<input name="log" placeholder="Username or Email"><input name="pwd" type="password" placeholder="Password">'
    ), 200


# ==========================================
# INTRUSION DASHBOARD  (human-readable view)
# ==========================================
@app.route('/honeypot-dashboard')
def dashboard():
    rows  = fetch_intrusions()
    stats = fetch_stats()
    return render_template_string(DASHBOARD_HTML, rows=rows, stats=stats)


@app.route('/intrusions')
def intrusions_api():
    """JSON API — useful for external tooling or Grafana JSON datasource."""
    return jsonify(fetch_intrusions(limit=500))


# ==========================================
# STANDARD ENDPOINTS
# ==========================================
@app.route('/metrics')
def metrics():
    return Response(generate_latest(),
                    mimetype='text/plain; version=0.0.4; charset=utf-8')


@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'honeypot'}), 200


# ==========================================
# STARTUP
# ==========================================
if __name__ == '__main__':
    init_db()
    threading.Thread(target=fake_ssh_server, daemon=True).start()

    print("\n🍯  PodFlow Honeypot — Enhanced Edition")
    print("─" * 50)
    print("  SSH trap          port 2222  (captures post-banner data)")
    print("  HTTP traps        /admin  /phpmyadmin  /.env  /shell  /wp-admin")
    print("  Live dashboard    http://localhost:8888/honeypot-dashboard")
    print("  JSON API          http://localhost:8888/intrusions")
    print("  Metrics           http://localhost:8888/metrics")
    print("─" * 50 + "\n")

    app.run(host='0.0.0.0', port=8888, threaded=True)
