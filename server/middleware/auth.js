import jwt from 'jsonwebtoken'

const JWT_SECRET = process.env.JWT_SECRET || 'love-supremacy-secret-key-2024'

/**
 * JWT 鉴权中间件
 * 从 Authorization: Bearer <token> 提取 userId，写入 req.userId
 */
export function authMiddleware(req, res, next) {
  const authHeader = req.headers['authorization']
  const token = authHeader && authHeader.split(' ')[1]

  if (!token) {
    return res.status(401).json({ error: '未提供认证令牌' })
  }

  try {
    const decoded = jwt.verify(token, JWT_SECRET)
    req.userId = decoded.userId
    next()
  } catch {
    return res.status(403).json({ error: '令牌无效或已过期' })
  }
}

/** 生成 JWT */
export function signToken(userId) {
  return jwt.sign({ userId }, JWT_SECRET, { expiresIn: '7d' })
}

export { JWT_SECRET }
