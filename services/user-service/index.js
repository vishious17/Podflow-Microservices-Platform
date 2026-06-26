const express = require('express');
const client = require('prom-client');

const app = express();
const PORT = 3000;

// Collect default Node.js metrics
client.collectDefaultMetrics();

// HTTP request counter
const httpRequestsTotal = new client.Counter({
  name: 'http_requests_total',
  help: 'Total number of HTTP requests',
  labelNames: ['method', 'route', 'status']
});

app.use(express.json());

// Health check (used by monitoring / healing)
app.get('/health', (req, res) => {
  httpRequestsTotal.inc({ method: 'GET', route: '/health', status: 200 });
  res.status(200).json({ status: 'user-service healthy' });
});

// Sample internal endpoint
app.get('/users', (req, res) => {
  httpRequestsTotal.inc({ method: 'GET', route: '/users', status: 200 });
  res.json({
    service: 'user-service',
    users: ['alice', 'bob', 'charlie'],
    timestamp: new Date().toISOString()
  });
});

// Metrics endpoint for Prometheus
app.get('/metrics', async (req, res) => {
  res.set('Content-Type', client.register.contentType);
  res.end(await client.register.metrics());
});

app.listen(PORT, () => {
  console.log(`User-service running on port ${PORT}`);
});
