const express = require("express");
const client = require("prom-client");

const app = express();
const PORT = 5000;

app.use(express.json());

client.collectDefaultMetrics();

const httpRequestsTotal = new client.Counter({
  name: "http_requests_total",
  help: "Total HTTP requests to backend service",
  labelNames: ["method", "route", "status"]
});

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

app.get("/metrics", async (req, res) => {
  res.set("Content-Type", client.register.contentType);
  res.end(await client.register.metrics());
});

app.listen(PORT, () => {
  console.log(`Backend running on port ${PORT}`);
});
