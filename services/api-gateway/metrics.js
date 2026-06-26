const client = require('prom-client');

client.collectDefaultMetrics();

const httpRequestCounter = new client.Counter({
  name: 'gateway_http_requests_total',
  help: 'Total HTTP requests received by API Gateway',
  labelNames: ['method', 'route', 'status']
});

module.exports = {
  client,
  httpRequestCounter
};
