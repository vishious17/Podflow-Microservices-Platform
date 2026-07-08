from flask import Flask, request, jsonify, Response
from prometheus_client import Counter, generate_latest
from psycopg2 import pool as pg_pool
import psycopg2.extras
import os
import time

app = Flask(__name__)

LOGS_RECEIVED   = Counter('data_service_logs_total', 'Log entries received', ['service', 'status'])
ANALYTICS_HITS  = Counter('data_service_analytics_requests_total', 'Analytics endpoint hits')
ALERTS_RECEIVED = Counter('data_service_alerts_total', 'Alertmanager alerts received',
                          ['alertname', 'status', 'severity'])

connection_pool = None


def init_pool():
    global connection_pool
    for attempt in range(15):
        try:
            connection_pool = pg_pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=10,
                host=os.environ.get('DB_HOST', 'postgres'),
                port=os.environ.get('DB_PORT', 5432),
                dbname=os.environ.get('DB_NAME', 'podflow'),
                user=os.environ.get('DB_USER', 'podflow'),
                password=os.environ.get('DB_PASSWORD', 'podflow123')
            )
            print('Connection pool initialized (min=2, max=10)')
            return
        except Exception as e:
            print(f'Pool init attempt {attempt + 1}/15 failed: {e}')
            time.sleep(3)
    raise RuntimeError('Could not initialize connection pool')


def get_db():
    return connection_pool.getconn()


def put_db(conn):
    connection_pool.putconn(conn)


@app.route('/logs', methods=['POST'])
def receive_log():
    data        = request.get_json(silent=True) or {}
    service     = data.get('service', 'unknown')
    method      = data.get('method', 'GET')
    route       = data.get('route', '/')
    status      = data.get('status', 200)
    source_ip   = data.get('source_ip')
    duration_ms = data.get('duration_ms')

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO request_logs (service, method, route, status, source_ip, duration_ms)'
            ' VALUES (%s,%s,%s,%s,%s,%s)',
            (service, method, route, status, source_ip, duration_ms)
        )
        conn.commit()
        cur.close()
        LOGS_RECEIVED.labels(service=service, status=str(status)).inc()
        return jsonify({'message': 'logged'}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        put_db(conn)


@app.route('/logs', methods=['GET'])
def get_logs():
    limit   = request.args.get('limit', 100)
    service = request.args.get('service')
    conn    = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if service:
            cur.execute(
                'SELECT * FROM request_logs WHERE service = %s ORDER BY created_at DESC LIMIT %s',
                (service, limit)
            )
        else:
            cur.execute('SELECT * FROM request_logs ORDER BY created_at DESC LIMIT %s', (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return jsonify({'logs': rows, 'total': len(rows)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        put_db(conn)


@app.route('/analytics', methods=['GET'])
def get_analytics():
    ANALYTICS_HITS.inc()
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute('SELECT COUNT(*) AS total FROM request_logs')
        total = cur.fetchone()['total']

        cur.execute('SELECT service, COUNT(*) AS count FROM request_logs GROUP BY service ORDER BY count DESC')
        by_service = [dict(r) for r in cur.fetchall()]

        cur.execute('SELECT status, COUNT(*) AS count FROM request_logs GROUP BY status ORDER BY status')
        by_status = [dict(r) for r in cur.fetchall()]

        cur.execute('''
            SELECT service,
                   ROUND(AVG(duration_ms)) AS avg_ms,
                   MIN(duration_ms) AS min_ms,
                   MAX(duration_ms) AS max_ms
            FROM request_logs WHERE duration_ms IS NOT NULL GROUP BY service
        ''')
        latency = [dict(r) for r in cur.fetchall()]

        cur.execute(
            'SELECT route, COUNT(*) AS count FROM request_logs GROUP BY route ORDER BY count DESC LIMIT 10'
        )
        top_routes = [dict(r) for r in cur.fetchall()]

        cur.execute('''
            SELECT DATE_TRUNC(\'hour\', created_at) AS hour, COUNT(*) AS count
            FROM request_logs WHERE created_at > NOW() - INTERVAL \'24 hours\'
            GROUP BY hour ORDER BY hour
        ''')
        by_hour = [dict(r) for r in cur.fetchall()]

        cur.close()
        return jsonify({
            'total_requests':    total,
            'by_service':        by_service,
            'by_status':         by_status,
            'latency_ms':        latency,
            'top_routes':        top_routes,
            'requests_last_24h': by_hour,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        put_db(conn)


@app.route('/alerts', methods=['POST'])
def receive_alert():
    """Webhook endpoint for Alertmanager notifications."""
    data   = request.get_json(silent=True) or {}
    alerts = data.get('alerts', [])
    for alert in alerts:
        status   = alert.get('status', 'unknown')
        name     = alert.get('labels', {}).get('alertname', 'unknown')
        severity = alert.get('labels', {}).get('severity', 'unknown')
        summary  = alert.get('annotations', {}).get('summary', '')
        print(f"[ALERT] {status.upper()} | {name} | severity={severity} | {summary}")
        ALERTS_RECEIVED.labels(alertname=name, status=status, severity=severity).inc()
    return jsonify({'received': len(alerts)}), 200


@app.route('/health')
def health():
    return jsonify({'status': 'UP', 'service': 'data-service'}), 200


@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype='text/plain; version=0.0.4; charset=utf-8')


if __name__ == '__main__':
    init_pool()
    print('Data Service starting on port 4000')
    app.run(host='0.0.0.0', port=4000, threaded=True)
