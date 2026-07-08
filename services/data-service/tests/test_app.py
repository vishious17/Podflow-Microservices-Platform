import json
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    """Flask test client with mocked connection pool."""
    mock_conn   = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = lambda s: s
    mock_cursor.__exit__  = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor

    mock_pool = MagicMock()
    mock_pool.getconn.return_value = mock_conn
    mock_pool.putconn = MagicMock()

    with patch('app.init_pool'), patch('app.connection_pool', mock_pool):
        import app as flask_app
        flask_app.app.config['TESTING'] = True
        with flask_app.app.test_client() as c:
            yield c, mock_cursor, mock_conn


def test_health(client):
    c, _, _ = client
    res  = c.get('/health')
    data = json.loads(res.data)
    assert res.status_code == 200
    assert data['status'] == 'UP'
    assert data['service'] == 'data-service'


def test_metrics_endpoint(client):
    c, _, _ = client
    res = c.get('/metrics')
    assert res.status_code == 200
    assert b'data_service' in res.data


def test_receive_log_success(client):
    c, mock_cursor, mock_conn = client
    mock_cursor.execute = MagicMock()
    mock_conn.commit    = MagicMock()

    res = c.post('/logs',
        data=json.dumps({
            'service': 'api-gateway', 'method': 'GET',
            'route': '/api/users', 'status': 200, 'duration_ms': 45
        }),
        content_type='application/json'
    )
    assert res.status_code == 201
    data = json.loads(res.data)
    assert data['message'] == 'logged'


def test_receive_log_missing_body(client):
    c, mock_cursor, mock_conn = client
    mock_cursor.execute = MagicMock()
    mock_conn.commit    = MagicMock()

    # Should still succeed — all fields have defaults
    res = c.post('/logs', data='{}', content_type='application/json')
    assert res.status_code == 201


def test_receive_alert(client):
    c, _, _ = client
    payload = {
        'alerts': [{
            'status': 'firing',
            'labels': {'alertname': 'ServiceDown', 'severity': 'critical'},
            'annotations': {'summary': 'Test service is down'}
        }]
    }
    res  = c.post('/alerts', data=json.dumps(payload), content_type='application/json')
    data = json.loads(res.data)
    assert res.status_code == 200
    assert data['received'] == 1


def test_receive_alert_empty_body(client):
    c, _, _ = client
    res  = c.post('/alerts', data='{}', content_type='application/json')
    data = json.loads(res.data)
    assert res.status_code == 200
    assert data['received'] == 0


def test_get_logs(client):
    c, mock_cursor, _ = client
    mock_cursor.fetchall.return_value = [
        {'id': 1, 'service': 'api-gateway', 'method': 'GET',
         'route': '/api/users', 'status': 200, 'created_at': '2024-01-01'}
    ]
    res  = c.get('/logs')
    data = json.loads(res.data)
    assert res.status_code == 200
    assert 'logs' in data
    assert 'total' in data
