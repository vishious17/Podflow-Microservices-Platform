const jwt = require('jsonwebtoken');

const JWT_SECRET = process.env.JWT_SECRET || 'podflow-dev-secret-change-in-production';

// Express strips the /api mount prefix before middleware sees req.path
// so these paths are relative to the mount point, not the full URL
const PUBLIC = [
  { method: 'POST', path: '/users/register' },
  { method: 'POST', path: '/users/login' },
];

function isPublic(req) {
  return PUBLIC.some(r => {
    if (r.method && r.method !== req.method) return false;
    return req.path === r.path || req.path.startsWith(r.path + '/');
  });
}

function verifyToken(req, res, next) {
  if (isPublic(req)) return next();

  const header = req.headers.authorization;
  if (!header || !header.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Authentication required' });
  }

  try {
    req.user = jwt.verify(header.split(' ')[1], JWT_SECRET);
    next();
  } catch (err) {
    const msg = err.name === 'TokenExpiredError' ? 'Token expired' : 'Invalid token';
    res.status(401).json({ error: msg });
  }
}

module.exports = { verifyToken, JWT_SECRET };
