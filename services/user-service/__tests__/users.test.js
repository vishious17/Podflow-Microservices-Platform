const request = require('supertest');
const bcrypt  = require('bcryptjs');

// Mock prom-client before importing app to avoid duplicate metric errors
jest.mock('prom-client', () => ({
  collectDefaultMetrics: jest.fn(),
  Counter: jest.fn().mockImplementation(() => ({ inc: jest.fn() })),
  register: {
    contentType: 'text/plain',
    metrics: jest.fn().mockResolvedValue('')
  }
}));

// Mock database pool
jest.mock('../db', () => ({
  pool: { query: jest.fn() },
  connectWithRetry: jest.fn().mockResolvedValue({})
}));

const { pool } = require('../db');
const app      = require('../index');

beforeEach(() => jest.clearAllMocks());

describe('POST /users/register', () => {
  it('returns 400 when body is empty', async () => {
    const res = await request(app).post('/users/register').send({});
    expect(res.status).toBe(400);
    expect(res.body).toHaveProperty('errors');
  });

  it('returns 400 for invalid email', async () => {
    const res = await request(app).post('/users/register')
      .send({ name: 'Test', email: 'not-an-email', password: 'password123' });
    expect(res.status).toBe(400);
  });

  it('returns 400 when password is too short', async () => {
    const res = await request(app).post('/users/register')
      .send({ name: 'Test', email: 'test@test.com', password: 'short' });
    expect(res.status).toBe(400);
  });

  it('returns 201 and user object on success', async () => {
    pool.query.mockResolvedValueOnce({
      rows: [{ id: 1, name: 'Test User', email: 'test@test.com', created_at: new Date() }]
    });
    const res = await request(app).post('/users/register')
      .send({ name: 'Test User', email: 'test@test.com', password: 'password123' });
    expect(res.status).toBe(201);
    expect(res.body.user).toHaveProperty('id');
    expect(res.body.user).not.toHaveProperty('password_hash');
  });

  it('returns 409 when email already exists', async () => {
    pool.query.mockRejectedValueOnce({ code: '23505' });
    const res = await request(app).post('/users/register')
      .send({ name: 'Test', email: 'existing@test.com', password: 'password123' });
    expect(res.status).toBe(409);
  });
});

describe('POST /users/login', () => {
  it('returns 400 when body is empty', async () => {
    const res = await request(app).post('/users/login').send({});
    expect(res.status).toBe(400);
  });

  it('returns 401 when user does not exist', async () => {
    pool.query.mockResolvedValueOnce({ rows: [] });
    const res = await request(app).post('/users/login')
      .send({ email: 'nobody@test.com', password: 'password123' });
    expect(res.status).toBe(401);
  });

  it('returns 401 for wrong password', async () => {
    const hash = await bcrypt.hash('correctpassword', 10);
    pool.query.mockResolvedValueOnce({
      rows: [{ id: 1, name: 'Test', email: 'test@test.com', password_hash: hash }]
    });
    const res = await request(app).post('/users/login')
      .send({ email: 'test@test.com', password: 'wrongpassword' });
    expect(res.status).toBe(401);
  });

  it('returns 200 with token on successful login', async () => {
    const hash = await bcrypt.hash('password123', 10);
    pool.query.mockResolvedValueOnce({
      rows: [{ id: 1, name: 'Test', email: 'test@test.com', password_hash: hash }]
    });
    const res = await request(app).post('/users/login')
      .send({ email: 'test@test.com', password: 'password123' });
    expect(res.status).toBe(200);
    expect(res.body).toHaveProperty('token');
    expect(res.body.user).not.toHaveProperty('password_hash');
  });
});

describe('GET /users', () => {
  it('returns list of users', async () => {
    pool.query.mockResolvedValueOnce({
      rows: [{ id: 1, name: 'Alice', email: 'alice@test.com', created_at: new Date() }],
      rowCount: 1
    });
    const res = await request(app).get('/users');
    expect(res.status).toBe(200);
    expect(Array.isArray(res.body.users)).toBe(true);
    expect(res.body.total).toBe(1);
  });

  it('returns 500 on database error', async () => {
    pool.query.mockRejectedValueOnce(new Error('DB error'));
    const res = await request(app).get('/users');
    expect(res.status).toBe(500);
  });
});

describe('GET /users/:id', () => {
  it('returns 404 when user does not exist', async () => {
    pool.query.mockResolvedValueOnce({ rows: [] });
    const res = await request(app).get('/users/999');
    expect(res.status).toBe(404);
  });

  it('returns user when found', async () => {
    pool.query.mockResolvedValueOnce({
      rows: [{ id: 1, name: 'Alice', email: 'alice@test.com', created_at: new Date() }]
    });
    const res = await request(app).get('/users/1');
    expect(res.status).toBe(200);
    expect(res.body.id).toBe(1);
  });
});

describe('PUT /users/:id', () => {
  it('returns 400 when no fields provided', async () => {
    const res = await request(app).put('/users/1').send({});
    expect(res.status).toBe(400);
  });

  it('returns 404 when user does not exist', async () => {
    pool.query.mockResolvedValueOnce({ rows: [] });
    const res = await request(app).put('/users/999').send({ name: 'New Name' });
    expect(res.status).toBe(404);
  });

  it('updates user successfully', async () => {
    pool.query.mockResolvedValueOnce({
      rows: [{ id: 1, name: 'New Name', email: 'test@test.com', updated_at: new Date() }]
    });
    const res = await request(app).put('/users/1').send({ name: 'New Name' });
    expect(res.status).toBe(200);
    expect(res.body.user.name).toBe('New Name');
  });
});

describe('DELETE /users/:id', () => {
  it('returns 404 when user does not exist', async () => {
    pool.query.mockResolvedValueOnce({ rows: [] });
    const res = await request(app).delete('/users/999');
    expect(res.status).toBe(404);
  });

  it('deletes user successfully', async () => {
    pool.query.mockResolvedValueOnce({ rows: [{ id: 1 }] });
    const res = await request(app).delete('/users/1');
    expect(res.status).toBe(200);
    expect(res.body.id).toBe(1);
  });
});

describe('GET /health', () => {
  it('returns UP status', async () => {
    const res = await request(app).get('/health');
    expect(res.status).toBe(200);
    expect(res.body.status).toBe('UP');
  });
});
