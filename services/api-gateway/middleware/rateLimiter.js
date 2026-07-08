const rateLimit = require('express-rate-limit');

// Strict limiter for auth endpoints — prevents brute force
const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 10,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Too many authentication attempts, try again in 15 minutes' }
});

// General limiter for all other API routes
const apiLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 100,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Too many requests, try again later' }
});

module.exports = { authLimiter, apiLimiter };
