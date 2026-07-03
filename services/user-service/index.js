const express = require('express');
const bcrypt  = require('bcryptjs');
const client  = require('prom-client');
const { pool, connectWithRetry } = require('./db');

const app  = express();
const PORT = 3000;

app.use(express.json());
client.collectDefaultMetrics();

const httpRequests = new client.Counter({
  name: 'http_requests_total',
  help: 'Total HTTP requests to user-service',
  labelNames: ['method', 'route', 'status']
});

const track = (method, route, status) =>
  httpRequests.inc({ method, route, status });

app.post('/users/register', async (req, res) => {
  const { name, email, password } = req.body;
  if (!name || !email || !password) {
    track('POST', '/users/register', 400);
    return res.status(400).json({ error: 'name, email and password required' });
  }
  try {
    const hash   = await bcrypt.hash(password, 10);
    const result = await pool.query(
      'INSERT INTO users (name, email, password_hash) VALUES ($1, $2, $3) RETURNING id, name, email, created_at',
      [name, email, hash]
    );
    track('POST', '/users/register', 201);
    res.status(201).json({ message: 'User registered', user: result.rows[0] });
  } catch (err) {
    if (err.code === '23505') {
      track('POST', '/users/register', 409);
      return res.status(409).json({ error: 'Email already registered' });
    }
    track('POST', '/users/register', 500);
    res.status(500).json({ error: 'Registration failed' });
  }
});

app.post('/users/login', async (req, res) => {
  const { email, password } = req.body;
  if (!email || !password) {
    track('POST', '/users/login', 400);
    return res.status(400).json({ error: 'email and password required' });
  }
  try {
    const result = await pool.query('SELECT * FROM users WHERE email = $1', [email]);
    if (result.rows.length === 0) {
      track('POST', '/users/login', 401);
      return res.status(401).json({ error: 'Invalid credentials' });
    }
    const user  = result.rows[0];
    const valid = await bcrypt.compare(password, user.password_hash);
    if (!valid) {
      track('POST', '/users/login', 401);
      return res.status(401).json({ error: 'Invalid credentials' });
    }
    track('POST', '/users/login', 200);
    res.json({ message: 'Login successful', user: { id: user.id, name: user.name, email: user.email } });
  } catch (err) {
    track('POST', '/users/login', 500);
    res.status(500).json({ error: 'Login failed' });
  }
});

app.get('/users', async (req, res) => {
  try {
    const result = await pool.query(
      'SELECT id, name, email, created_at FROM users ORDER BY created_at DESC'
    );
    track('GET', '/users', 200);
    res.json({ users: result.rows, total: result.rowCount });
  } catch (err) {
    track('GET', '/users', 500);
    res.status(500).json({ error: 'Failed to fetch users' });
  }
});

app.get('/users/:id', async (req, res) => {
  try {
    const result = await pool.query(
      'SELECT id, name, email, created_at FROM users WHERE id = $1',
      [req.params.id]
    );
    if (result.rows.length === 0) {
      track('GET', '/users/:id', 404);
      return res.status(404).json({ error: 'User not found' });
    }
    track('GET', '/users/:id', 200);
    res.json(result.rows[0]);
  } catch (err) {
    track('GET', '/users/:id', 500);
    res.status(500).json({ error: 'Failed to fetch user' });
  }
});

app.put('/users/:id', async (req, res) => {
  const { name, email } = req.body;
  if (!name && !email) {
    track('PUT', '/users/:id', 400);
    return res.status(400).json({ error: 'Provide name or email to update' });
  }
  try {
    const result = await pool.query(
      `UPDATE users SET name = COALESCE($1, name), email = COALESCE($2, email), updated_at = NOW()
       WHERE id = $3 RETURNING id, name, email, updated_at`,
      [name || null, email || null, req.params.id]
    );
    if (result.rows.length === 0) {
      track('PUT', '/users/:id', 404);
      return res.status(404).json({ error: 'User not found' });
    }
    track('PUT', '/users/:id', 200);
    res.json({ message: 'User updated', user: result.rows[0] });
  } catch (err) {
    track('PUT', '/users/:id', 500);
    res.status(500).json({ error: 'Failed to update user' });
  }
});

app.delete('/users/:id', async (req, res) => {
  try {
    const result = await pool.query(
      'DELETE FROM users WHERE id = $1 RETURNING id', [req.params.id]
    );
    if (result.rows.length === 0) {
      track('DELETE', '/users/:id', 404);
      return res.status(404).json({ error: 'User not found' });
    }
    track('DELETE', '/users/:id', 200);
    res.json({ message: 'User deleted', id: result.rows[0].id });
  } catch (err) {
    track('DELETE', '/users/:id', 500);
    res.status(500).json({ error: 'Failed to delete user' });
  }
});

app.get('/health', (req, res) => {
  track('GET', '/health', 200);
  res.json({ status: 'UP', service: 'user-service' });
});

app.get('/metrics', async (req, res) => {
  res.set('Content-Type', client.register.contentType);
  res.end(await client.register.metrics());
});

connectWithRetry()
  .then(() => app.listen(PORT, () => console.log(`User Service running on port ${PORT}`)))
  .catch(err => { console.error(err.message); process.exit(1); });
