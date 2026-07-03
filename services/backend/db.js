const { Pool } = require('pg');

const pool = new Pool({
  host:     process.env.DB_HOST     || 'postgres',
  port:     parseInt(process.env.DB_PORT || '5432'),
  database: process.env.DB_NAME     || 'podflow',
  user:     process.env.DB_USER     || 'podflow',
  password: process.env.DB_PASSWORD || 'podflow123',
  max: 10,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

async function connectWithRetry(retries = 15, delay = 3000) {
  for (let i = 0; i < retries; i++) {
    try {
      const c = await pool.connect();
      console.log('Connected to PostgreSQL');
      c.release();
      return pool;
    } catch (err) {
      console.log(`DB attempt ${i + 1}/${retries} failed: ${err.message}`);
      if (i < retries - 1) await new Promise(r => setTimeout(r, delay));
    }
  }
  throw new Error('Could not connect to PostgreSQL');
}

module.exports = { pool, connectWithRetry };
