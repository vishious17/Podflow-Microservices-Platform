const express = require('express');
const axios   = require('axios');
const https   = require('https');
const http    = require('http');
const fs      = require('fs');
const path    = require('path');
const client  = require('prom-client');

const { verifyToken }             = require('./middleware/auth');
const { authLimiter, apiLimiter } = require('./middleware/rateLimiter');

const app     = express();
const PORT     = process.env.PORT     || 8080;
const PORT_TLS = process.env.PORT_TLS || 8443;

const USER_SERVICE_URL = process.env.USER_SERVICE_URL || 'http://user-service:3000';
const BACKEND_URL      = process.env.BACKEND_URL      || 'http://backend:5000';
const DATA_SERVICE_URL = process.env.DATA_SERVICE_URL || 'http://data-service:4000';

app.use(express.json());
client.collectDefaultMetrics();

const gatewayRequests = new client.Counter({
  name: 'gateway_http_requests_total',
  help: 'Total HTTP requests through API Gateway',
  labelNames: ['method', 'route', 'status']
});

function logRequest(service, method, route, status, sourceIp, durationMs) {
  axios.post(`${DATA_SERVICE_URL}/logs`, {
    service, method, route, status,
    source_ip: sourceIp, duration_ms: durationMs
  }).catch(() => {});
}

// Serve the web dashboard at /
app.use(express.static(path.join(__dirname, 'public')));

// Log + count every API request (skip static files)
app.use('/api', (req, res, next) => {
  const start = Date.now();
  res.on('finish', () => {
    const duration = Date.now() - start;
    gatewayRequests.inc({ method: req.method, route: req.path, status: res.statusCode });
    logRequest('api-gateway', req.method, req.path, res.statusCode, req.ip, duration);
  });
  next();
});

// Rate limiting
app.use('/api/users/login',    authLimiter);
app.use('/api/users/register', authLimiter);
app.use('/api/',               apiLimiter);

// JWT verification
app.use('/api', verifyToken);

app.get('/health', (req, res) =>
  res.json({ status: 'UP', service: 'api-gateway' })
);

async function proxy(req, res, targetUrl, label) {
  try {
    const response = await axios({
      method:  req.method,
      url:     `${targetUrl}${req.url}`,
      data:    req.body,
      params:  req.query,
      headers: {
        'Content-Type': 'application/json',
        ...(req.user
          ? { 'X-User-Id': req.user.userId, 'X-User-Email': req.user.email }
          : {})
      },
      timeout: 10000
    });
    res.status(response.status).json(response.data);
  } catch (err) {
    const status = err.response?.status || 503;
    const data   = err.response?.data   || { error: `${label} unavailable` };
    res.status(status).json(data);
  }
}

app.use('/api/users', (req, res) => {
  req.url = '/users' + (req.path === '/' ? '' : req.path);
  proxy(req, res, USER_SERVICE_URL, 'user-service');
});

app.use('/api/data', (req, res) => {
  req.url = '/data' + (req.path === '/' ? '' : req.path);
  proxy(req, res, BACKEND_URL, 'backend');
});

app.use('/api/logs', (req, res) => {
  req.url = req.path === '/' ? '/logs' : req.path;
  proxy(req, res, DATA_SERVICE_URL, 'data-service');
});

app.use('/api/analytics', (req, res) => {
  req.url = '/analytics';
  proxy(req, res, DATA_SERVICE_URL, 'data-service');
});

app.get('/metrics', async (req, res) => {
  res.set('Content-Type', client.register.contentType);
  res.end(await client.register.metrics());
});

// HTTP on 8080 for internal health checks and Prometheus
http.createServer(app).listen(PORT, () =>
  console.log(`API Gateway HTTP  on port ${PORT}`)
);

// HTTPS on 8443 — graceful fallback if certs missing
try {
  const sslOptions = {
    key:  fs.readFileSync('/certs/server.key'),
    cert: fs.readFileSync('/certs/server.crt'),
  };
  https.createServer(sslOptions, app).listen(PORT_TLS, () =>
    console.log(`API Gateway HTTPS on port ${PORT_TLS}`)
  );
} catch {
  console.log('TLS certs not found — HTTPS disabled. Run: bash certs/generate-certs.sh');
}

module.exports = app;
