const express = require("express");
const client = require("prom-client");

client.collectDefaultMetrics();

const register = client.register;


const app = express();
const PORT = process.env.PORT || 5000;

app.use(express.json());

/* ---------------- PROMETHEUS METRICS SETUP ---------------- */

// Collect default Node.js metrics (CPU, memory, event loop, etc.)
client.collectDefaultMetrics();

// HTTP request counter
const httpRequestsTotal = new client.Counter({
  name: "http_requests_total",
  help: "Total number of HTTP requests to user service",
  labelNames: ["method", "route", "status"]
});

/* ---------------- APPLICATION ROUTES ---------------- */

// Health check
app.get("/health", (req, res) => {
  httpRequestsTotal.inc({
    method: req.method,
    route: "/health",
    status: 200
  });

  res.json({ status: "UP", service: "user-service" });
});

// Example protected API
app.get("/users", (req, res) => {
  httpRequestsTotal.inc({
    method: req.method,
    route: "/users",
    status: 200
  });

  res.json({
    users: [
      { id: 1, name: "Alice" },
      { id: 2, name: "Bob" }
    ]
  });
});

/* ---------------- METRICS ENDPOINT ---------------- */

app.get("/metrics", async (req, res) => {
  res.set("Content-Type", register.contentType);
  res.end(await register.metrics());
});

/* ---------------- START SERVER ---------------- */

app.listen(PORT, () => {
  console.log(`User Service running on port ${PORT}`);
});
