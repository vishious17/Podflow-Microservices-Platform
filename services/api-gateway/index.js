const express = require("express");
const axios = require("axios");
const client = require("prom-client");

const app = express();
const PORT = 8080;
const USER_SERVICE_URL = process.env.BACKEND_URL || "http://backend:5000";

app.use(express.json());

/* -------- PROMETHEUS METRICS -------- */
client.collectDefaultMetrics();

const gatewayRequestsTotal = new client.Counter({
  name: "gateway_http_requests_total",
  help: "Total HTTP requests received by API Gateway",
  labelNames: ["method", "route", "status"]
});

/* -------- ROUTES -------- */

app.get("/health", (req, res) => {
  gatewayRequestsTotal.inc({
    method: req.method,
    route: "/health",
    status: 200
  });
  res.json({ status: "API Gateway is healthy" });
});

app.get("/api/users", async (req, res) => {
  try {
    const response = await axios.get(`${USER_SERVICE_URL}/users`);

    gatewayRequestsTotal.inc({
      method: req.method,
      route: "/api/users",
      status: response.status
    });

    res.status(response.status).json(response.data);
  } catch (err) {
    gatewayRequestsTotal.inc({
      method: req.method,
      route: "/api/users",
      status: 500
    });

    res.status(500).json({ error: "Backend unavailable" });
  }
});

app.get("/metrics", async (req, res) => {
  res.set("Content-Type", client.register.contentType);
  res.end(await client.register.metrics());
});

/* -------- START -------- */

app.listen(PORT, () => {
  console.log(`API Gateway running on port ${PORT}`);
});
