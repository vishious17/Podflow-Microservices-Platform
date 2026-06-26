const express = require("express");
const axios = require("axios");
const client = require("prom-client");

client.collectDefaultMetrics();

const register = client.register;


const app = express();
const PORT = 8080;

// Backend service DNS name (from podman-compose network)
const USER_SERVICE_URL = process.env.USER_SERVICE_URL || "http://user-service:5000";

app.use(express.json());

/* ---------------- PROMETHEUS METRICS SETUP ---------------- */

// Collect default Node.js metrics
client.collectDefaultMetrics();

// Gateway request counter
const gatewayRequestsTotal = new client.Counter({
  name: "gateway_http_requests_total",
  help: "Total HTTP requests received by API Gateway",
  labelNames: ["method", "route", "status"]
});

/* ---------------- APPLICATION ROUTES ---------------- */

// Health check
app.get("/health", (req, res) => {
  gatewayRequestsTotal.inc({
    method: req.method,
    route: "/health",
    status: 200
  });

  res.json({ status: "UP", service: "api-gateway" });
});

/* ---------------- API PROXY ---------------- */

// Forward requests to user-service
app.use("/api/users", async (req, res) => {
  try {
    const response = await axios({
      method: req.method,
      url: `${USER_SERVICE_URL}/users`,
      data: req.body
    });

    gatewayRequestsTotal.inc({
      method: req.method,
      route: "/api/users",
      status: response.status
    });

    res.status(response.status).json(response.data);
  } catch (error) {
    gatewayRequestsTotal.inc({
      method: req.method,
      route: "/api/users",
      status: 500
    });

    res.status(500).json({
      error: "User service unavailable"
    });
  }
});

/* ---------------- METRICS ENDPOINT ---------------- */

app.get("/metrics", async (req, res) => {
  res.set("Content-Type", register.contentType);
  res.end(await register.metrics());
});

/* ---------------- START SERVER ---------------- */

app.listen(PORT, () => {
  console.log(`API Gateway running on port ${PORT}`);
});
