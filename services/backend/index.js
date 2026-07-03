const express = require('express');
const client  = require('prom-client');
const { pool, connectWithRetry } = require('./db');

const app  = express();
const PORT = 5000;

app.use(express.json());
client.collectDefaultMetrics();

const httpRequests = new client.Counter({
  name: 'http_requests_total',
  help: 'Total HTTP requests to backend service',
  labelNames: ['method', 'route', 'status']
});

const track = (method, route, status) =>
  httpRequests.inc({ method, route, status });

app.get('/data', async (req, res) => {
  try {
    const result = await pool.query(`
      SELECT d.id, d.title, d.content, d.created_at,
             u.name AS author_name, u.email AS author_email
      FROM data_entries d
      LEFT JOIN users u ON d.author_id = u.id
      ORDER BY d.created_at DESC
    `);
    track('GET', '/data', 200);
    res.json({ entries: result.rows, total: result.rowCount });
  } catch (err) {
    track('GET', '/data', 500);
    res.status(500).json({ error: 'Failed to fetch entries' });
  }
});

app.post('/data', async (req, res) => {
  const { title, content, author_id } = req.body;
  if (!title) {
    track('POST', '/data', 400);
    return res.status(400).json({ error: 'title is required' });
  }
  try {
    const result = await pool.query(
      'INSERT INTO data_entries (title, content, author_id) VALUES ($1, $2, $3) RETURNING *',
      [title, content || null, author_id || null]
    );
    track('POST', '/data', 201);
    res.status(201).json({ message: 'Entry created', entry: result.rows[0] });
  } catch (err) {
    track('POST', '/data', 500);
    res.status(500).json({ error: 'Failed to create entry' });
  }
});

app.get('/data/:id', async (req, res) => {
  try {
    const result = await pool.query(
      'SELECT d.*, u.name AS author_name FROM data_entries d LEFT JOIN users u ON d.author_id = u.id WHERE d.id = $1',
      [req.params.id]
    );
    if (result.rows.length === 0) {
      track('GET', '/data/:id', 404);
      return res.status(404).json({ error: 'Entry not found' });
    }
    track('GET', '/data/:id', 200);
    res.json(result.rows[0]);
  } catch (err) {
    track('GET', '/data/:id', 500);
    res.status(500).json({ error: 'Failed to fetch entry' });
  }
});

app.put('/data/:id', async (req, res) => {
  const { title, content } = req.body;
  try {
    const result = await pool.query(
      'UPDATE data_entries SET title = COALESCE($1, title), content = COALESCE($2, content) WHERE id = $3 RETURNING *',
      [title || null, content || null, req.params.id]
    );
    if (result.rows.length === 0) {
      track('PUT', '/data/:id', 404);
      return res.status(404).json({ error: 'Entry not found' });
    }
    track('PUT', '/data/:id', 200);
    res.json({ message: 'Entry updated', entry: result.rows[0] });
  } catch (err) {
    track('PUT', '/data/:id', 500);
    res.status(500).json({ error: 'Failed to update entry' });
  }
});

app.delete('/data/:id', async (req, res) => {
  try {
    const result = await pool.query(
      'DELETE FROM data_entries WHERE id = $1 RETURNING id', [req.params.id]
    );
    if (result.rows.length === 0) {
      track('DELETE', '/data/:id', 404);
      return res.status(404).json({ error: 'Entry not found' });
    }
    track('DELETE', '/data/:id', 200);
    res.json({ message: 'Entry deleted', id: result.rows[0].id });
  } catch (err) {
    track('DELETE', '/data/:id', 500);
    res.status(500).json({ error: 'Failed to delete entry' });
  }
});

// Kept for orchestrator health check compatibility
app.get('/users', async (req, res) => {
  try {
    const result = await pool.query('SELECT COUNT(*) AS count FROM users');
    track('GET', '/users', 200);
    res.json({ status: 'UP', user_count: parseInt(result.rows[0].count) });
  } catch (err) {
    track('GET', '/users', 500);
    res.status(500).json({ error: 'Database unavailable' });
  }
});

app.get('/health', (req, res) => {
  track('GET', '/health', 200);
  res.json({ status: 'UP', service: 'backend' });
});

app.get('/metrics', async (req, res) => {
  res.set('Content-Type', client.register.contentType);
  res.end(await client.register.metrics());
});

connectWithRetry()
  .then(() => app.listen(PORT, () => console.log(`Backend Service running on port ${PORT}`)))
  .catch(err => { console.error(err.message); process.exit(1); });
