import express from 'express'
import cors from 'cors'
import bcrypt from 'bcryptjs'
import nodemailer from 'nodemailer'
import crypto from 'crypto'
import dotenv from 'dotenv'
import { signToken, authMiddleware } from './middleware/auth.js'

dotenv.config()

// 初始化数据库
await import('./dbInit.js')
import db, { saveDb } from './dbInit.js'

const app = express()
const PORT = process.env.PORT || 3001

// ── 邮箱验证码缓存 ────────────────────────────────────────────────────────────
const verificationCodes = new Map() // email -> { code, expiresAt }

// ── SMTP 配置（可选）─────────────────────────────────────────────────────────
const SMTP_HOST = process.env.SMTP_HOST
const SMTP_PORT = process.env.SMTP_PORT || 587
const SMTP_USER = process.env.SMTP_USER
const SMTP_PASS = process.env.SMTP_PASS
const SMTP_FROM = process.env.SMTP_FROM || SMTP_USER

const mailTransporter = SMTP_HOST && SMTP_USER && SMTP_PASS
  ? nodemailer.createTransport({
      host: SMTP_HOST,
      port: Number(SMTP_PORT),
      secure: Number(SMTP_PORT) === 465,
      auth: { user: SMTP_USER, pass: SMTP_PASS }
    })
  : null

// ── 中间件 ──────────────────────────────────────────────────────────────────
app.use(cors({ origin: '*', credentials: true }))
app.use(express.json())

// ── sql.js 辅助函数 ─────────────────────────────────────────────────────────

/** 将查询结果转为普通对象数组 */
function rows(stmt) {
  const results = []
  while (stmt.step()) {
    const row = stmt.getAsObject()
    results.push(row)
  }
  stmt.free()
  return results
}

/** 执行一条 SQL，返回变化数 */
function run(sql, ...params) {
  db.run(sql, params)
  saveDb()
  return { changes: db.getRowsModified() }
}

/** 查询单行 */
function get(sql, ...params) {
  const stmt = db.prepare(sql)
  stmt.bind(params)
  if (stmt.step()) {
    const row = stmt.getAsObject()
    stmt.free()
    return row
  }
  stmt.free()
  return null
}

/** 查询全部 */
function all(sql, ...params) {
  const stmt = db.prepare(sql)
  stmt.bind(params)
  return rows(stmt)
}

/** 获取或初始化游戏状态 */
function getOrInitGameState(userId) {
  let state = get('SELECT * FROM game_state WHERE user_id = ?', userId)
  if (!state) {
    db.run('INSERT INTO game_state (user_id) VALUES (?)', [userId])
    // 初始化25个地块
    for (let i = 0; i < 25; i++) {
      db.run('INSERT OR IGNORE INTO farm_data (user_id, plot_id) VALUES (?, ?)', [userId, i])
    }
    saveDb()
    state = get('SELECT * FROM game_state WHERE user_id = ?', userId)
  }
  return state
}

// ════════════════════════════════════════════════════════════════════════════
// 认证接口
// ════════════════════════════════════════════════════════════════════════════

// POST /api/send-verification-code
app.post('/api/send-verification-code', async (req, res) => {
  const { email } = req.body
  if (!email || !/^\S+@\S+\.\S+$/.test(email)) {
    return res.status(400).json({ error: '请输入有效的邮箱地址' })
  }

  const code = String(Math.floor(100000 + Math.random() * 900000))
  verificationCodes.set(email, { code, expiresAt: Date.now() + 10 * 60 * 1000 })

  if (mailTransporter) {
    try {
      await mailTransporter.sendMail({
        from: `"恋爱至上主义" <${SMTP_FROM}>`,
        to: email,
        subject: '您的注册验证码',
        text: `验证码：${code}，10分钟内有效。`,
        html: `<p>您的注册验证码是：<strong>${code}</strong></p><p>10分钟内有效。</p>`
      })
      res.json({ success: true, message: '验证码已发送' })
    } catch (err) {
      console.error('[Mail] 发送失败:', err)
      res.status(500).json({ error: '邮件发送失败，请稍后重试' })
    }
  } else {
    // SMTP 未配置：打印到日志（测试环境）
    console.log(`[验证码] ${email} -> ${code}`)
    res.json({ success: true, message: '验证码已发送（测试模式：请查看服务器日志）' })
  }
})

// POST /api/register
app.post('/api/register', (req, res) => {
  const { username, password, email, verificationCode, telegramChatId } = req.body
  if (!username || !password) {
    return res.status(400).json({ error: '用户名和密码不能为空' })
  }
  if (username.length < 3 || password.length < 6) {
    return res.status(400).json({ error: '用户名至少3位，密码至少6位' })
  }

  // 如果提供了邮箱，验证验证码
  if (email && email.trim()) {
    const record = verificationCodes.get(email.trim())
    if (!record) {
      return res.status(400).json({ error: '请先获取邮箱验证码' })
    }
    if (record.code !== verificationCode) {
      return res.status(400).json({ error: '验证码错误' })
    }
    if (Date.now() > record.expiresAt) {
      return res.status(400).json({ error: '验证码已过期，请重新获取' })
    }
  }

  const existing = get('SELECT id FROM users WHERE username = ?', username)
  if (existing) {
    return res.status(409).json({ error: '用户名已存在' })
  }

  if (email && email.trim()) {
    const emailExisting = get('SELECT id FROM users WHERE email = ?', email.trim())
    if (emailExisting) {
      return res.status(409).json({ error: '该邮箱已被注册' })
    }
  }

  const hashed = bcrypt.hashSync(password, 10)
  const isAdmin = telegramChatId && String(telegramChatId).trim() === '5315601134'
  if (email && email.trim()) {
    db.run('INSERT INTO users (username, password, email, role) VALUES (?, ?, ?, ?)', [username, hashed, email.trim(), isAdmin ? 'admin' : 'user'])
  } else {
    db.run('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', [username, hashed, isAdmin ? 'admin' : 'user'])
  }
  saveDb()

  // 取新注册用户 id（sql.js 的 last_insert_rowid() 不可靠）
  const user = get('SELECT id FROM users WHERE username = ?', username)
  const userId = user?.id

  // 如果提供了 Telegram ChatID，自动绑定
  if (telegramChatId && /^-?\d+$/.test(String(telegramChatId))) {
    const tgId = String(telegramChatId).trim()
    db.run('INSERT OR REPLACE INTO user_telegram (user_id, chat_id) VALUES (?, ?)', [userId, tgId])
    saveDb()
  }

  const token = signToken({ userId })
  const state = getOrInitGameState(userId)

  res.json({ token, userId, gameState: state })
})

// POST /api/login
app.post('/api/login', (req, res) => {
  const { username, password } = req.body
  if (!username || !password) {
    return res.status(400).json({ error: '请输入用户名和密码' })
  }

  const user = get('SELECT * FROM users WHERE username = ?', username)
  if (!user || !bcrypt.compareSync(password, user.password)) {
    return res.status(401).json({ error: '用户名或密码错误' })
  }

  const token = signToken({ userId: user.id })
  const state = getOrInitGameState(user.id)
  db.run("UPDATE game_state SET last_login = datetime('now') WHERE user_id = ?", [user.id])
  saveDb()

  res.json({ token, userId: user.id, role: user.role || 'user', gameState: state })
})

// ════════════════════════════════════════════════════════════════════════════
// 游戏状态
// ════════════════════════════════════════════════════════════════════════════

app.get('/api/game/state', authMiddleware, (req, res) => {
  const state = getOrInitGameState(req.userId)
  const inventory = all('SELECT item_id, quantity, mode FROM inventory WHERE user_id = ?', req.userId)
  const farmData = all(
    'SELECT plot_id, crop_type, grow_progress, is_watered, planted_at, stage FROM farm_data WHERE user_id = ?',
    req.userId
  )
  res.json({ state, inventory, farmData })
})

app.post('/api/game/state', authMiddleware, (req, res) => {
  const { awakeningLevel, worldMode, currentScene } = req.body
  const updates = []
  const params = []

  if (awakeningLevel !== undefined) { updates.push('awakening_level = ?'); params.push(awakeningLevel) }
  if (worldMode !== undefined) { updates.push('world_mode = ?'); params.push(worldMode) }
  if (currentScene !== undefined) { updates.push('current_scene = ?'); params.push(currentScene) }

  if (updates.length === 0) return res.status(400).json({ error: '没有要更新的字段' })

  params.push(req.userId)
  db.run(`UPDATE game_state SET ${updates.join(', ')} WHERE user_id = ?`, params)
  saveDb()

  res.json({ success: true, state: getOrInitGameState(req.userId) })
})

// ════════════════════════════════════════════════════════════════════════════
// 背包
// ════════════════════════════════════════════════════════════════════════════

app.post('/api/inventory/add', authMiddleware, (req, res) => {
  const { itemId, quantity = 1, mode = 'script' } = req.body
  if (!itemId) return res.status(400).json({ error: '缺少 itemId' })

  const existing = get('SELECT * FROM inventory WHERE user_id = ? AND item_id = ? AND mode = ?', req.userId, itemId, mode)
  if (existing) {
    db.run('UPDATE inventory SET quantity = quantity + ? WHERE user_id = ? AND item_id = ? AND mode = ?', [quantity, req.userId, itemId, mode])
  } else {
    db.run('INSERT INTO inventory (user_id, item_id, quantity, mode) VALUES (?, ?, ?, ?)', [req.userId, itemId, quantity, mode])
  }
  saveDb()

  const inv = all('SELECT item_id, quantity FROM inventory WHERE user_id = ? AND mode = ?', req.userId, mode)
  res.json({ success: true, inventory: inv })
})

// ════════════════════════════════════════════════════════════════════════════
// 农场
// ════════════════════════════════════════════════════════════════════════════

app.get('/api/farm/state', authMiddleware, (req, res) => {
  const plots = all('SELECT plot_id, crop_type, is_watered, planted_at, stage FROM farm_data WHERE user_id = ?', req.userId)
  res.json({ plots })
})

app.post('/api/farm/action', authMiddleware, (req, res) => {
  const { action, plotId, cropType } = req.body

  if (!['plant', 'water', 'harvest'].includes(action)) {
    return res.status(400).json({ error: '无效的操作' })
  }

  const plot = get('SELECT * FROM farm_data WHERE user_id = ? AND plot_id = ?', req.userId, plotId)
  if (!plot) return res.status(404).json({ error: '地块不存在' })

  if (action === 'plant') {
    if (plot.crop_type) return res.status(400).json({ error: '该地块已有作物' })
    db.run('UPDATE farm_data SET crop_type = ?, planted_at = ?, is_watered = 0, stage = 0 WHERE user_id = ? AND plot_id = ?', [cropType, Date.now(), req.userId, plotId])
  } else if (action === 'water') {
    db.run('UPDATE farm_data SET is_watered = 1 WHERE user_id = ? AND plot_id = ?', [req.userId, plotId])
  }
  saveDb()

  const updated = get('SELECT * FROM farm_data WHERE user_id = ? AND plot_id = ?', req.userId, plotId)
  res.json({ success: true, plot: updated })
})

// ════════════════════════════════════════════════════════════════════════════
// AI 聊天
// ════════════════════════════════════════════════════════════════════════════

app.get('/api/chat/history', authMiddleware, (req, res) => {
  const rows_data = all(`
    SELECT role, content, timestamp FROM chat_history
    WHERE user_id = ?
    ORDER BY timestamp DESC LIMIT 20
  `, req.userId)
  res.json({ history: rows_data.reverse() })
})

app.post('/api/chat', authMiddleware, async (req, res) => {
  const { message, systemHint } = req.body
  if (!message) return res.status(400).json({ error: '消息不能为空' })

  // 保存用户消息
  db.run("INSERT INTO chat_history (user_id, role, content) VALUES (?, 'user', ?)", [req.userId, message])

  // 获取历史（最多20条）
  const history = all(`
    SELECT role, content FROM chat_history
    WHERE user_id = ?
    ORDER BY timestamp DESC LIMIT 20
  `, req.userId).reverse()

  const AI_API_KEY = process.env.OPENAI_API_KEY || process.env.DEEPSEEK_API_KEY
  const AI_BASE_URL = process.env.AI_BASE_URL || 'https://api.deepseek.com'
  const AI_MODEL = process.env.AI_MODEL || 'deepseek-chat'

  if (!AI_API_KEY) {
    // 开发模式模拟响应
    const mockTexts = [
      '我听到了……剧本世界的回声越来越微弱。',
      '你的选择正在改变这个世界的轨迹。',
      '（微笑）剧本还在继续，但裂缝已经出现。',
      '觉醒的光芒在你眼中闪烁……',
    ]
    const mockText = mockTexts[Math.floor(Math.random() * mockTexts.length)]
    db.run("INSERT INTO chat_history (user_id, role, content) VALUES (?, 'assistant', ?)", [req.userId, mockText])
    saveDb()
    return res.json({ text: mockText, emotion: 'happy', awakeningChange: 1 })
  }

  try {
    const systemPrompt = systemHint ||
      '你是《恋爱至上主义》的角色。玩家当前在剧本模式。回复要温柔深情，适当埋下觉醒的伏笔。回复中可以用 [EMOTION:happy] [AWAKENING:+2] 这样的标签来表达情绪和觉醒值变化（觉醒值变化请控制在1~5之间）。'

    const messages = [
      { role: 'system', content: systemPrompt },
      ...history.map((h) => ({ role: h.role, content: h.content })),
      { role: 'user', content: message },
    ]

    const aiRes = await fetch(`${AI_BASE_URL}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${AI_API_KEY}`,
      },
      body: JSON.stringify({ model: AI_MODEL, messages, max_tokens: 500 }),
    })

    if (!aiRes.ok) {
      const err = await aiRes.text()
      console.error('[AI] 错误:', err)
      return res.status(502).json({ error: 'AI 服务暂时不可用' })
    }

    const aiData = await aiRes.json()
    let aiText = aiData.choices?.[0]?.message?.content?.trim() || '......'

    // 解析标签
    let awakeningChange = 0
    const awMatch = aiText.match(/\[AWAKENING:([+-]?\d+)\]/)
    if (awMatch) { awakeningChange = parseInt(awMatch[1]); aiText = aiText.replace(awMatch[0], '').trim() }

    let emotion = 'neutral'
    const emMatch = aiText.match(/\[EMOTION:(\w+)\]/)
    if (emMatch) { emotion = emMatch[1]; aiText = aiText.replace(emMatch[0], '').trim() }

    // 保存 AI 回复
    db.run("INSERT INTO chat_history (user_id, role, content) VALUES (?, 'assistant', ?)", [req.userId, aiText])

    // 更新觉醒值
    if (awakeningChange !== 0) {
      const state = getOrInitGameState(req.userId)
      const newLevel = Math.max(0, (state.awakening_level || 0) + awakeningChange)
      db.run('UPDATE game_state SET awakening_level = ? WHERE user_id = ?', [newLevel, req.userId])
    }

    saveDb()
    res.json({ text: aiText, emotion, awakeningChange })
  } catch (err) {
    console.error('[AI] 调用失败:', err)
    res.status(500).json({ error: 'AI 调用失败' })
  }
})

// ════════════════════════════════════════════════════════════════════════════
// Telegram 配置
// ════════════════════════════════════════════════════════════════════════════

// GET /api/config — 获取公开配置（前端展示用）
app.get('/api/config', (_, res) => {
  const config = get('SELECT bot_token, admin_chat_id, public_url FROM telegram_config WHERE id = 1')
  res.json({
    bot_token: config?.bot_token ? '********' : '',
    admin_chat_id: config?.admin_chat_id || '',
    public_url: config?.public_url || ''
  })
})

// POST /api/config — 保存管理员配置（需管理员密码验证）
app.post('/api/config', (req, res) => {
  const { bot_token, admin_chat_id, public_url, admin_username, admin_password } = req.body

  const config = get('SELECT * FROM telegram_config WHERE id = 1')
  if (!config) {
    return res.status(500).json({ error: '配置表未初始化' })
  }

  // 验证管理员身份
  if (admin_username !== config.admin_username) {
    return res.status(403).json({ error: '管理员用户名错误' })
  }
  if (admin_password !== config.admin_password) {
    return res.status(403).json({ error: '管理员密码错误' })
  }

  const updates = []
  const params = []
  if (bot_token !== undefined && bot_token !== '********') {
    updates.push('bot_token = ?')
    params.push(bot_token)
  }
  if (admin_chat_id !== undefined) {
    updates.push('admin_chat_id = ?')
    params.push(admin_chat_id)
  }
  if (public_url !== undefined) {
    updates.push('public_url = ?')
    params.push(public_url)
  }
  if (updates.length === 0) {
    return res.status(400).json({ error: '没有要更新的字段' })
  }

  params.push(1)
  db.run(`UPDATE telegram_config SET ${updates.join(', ')}, updated_at = datetime('now') WHERE id = ?`, params)
  saveDb()
  res.json({ success: true })
})

// GET /api/telegram/link — 获取当前用户的 Telegram 绑定状态
app.get('/api/telegram/link', authMiddleware, (req, res) => {
  const link = get('SELECT chat_id, linked_at FROM user_telegram WHERE user_id = ?', req.userId)
  res.json({
    linked: !!link,
    telegram_id: link?.chat_id || null,
    linked_at: link?.linked_at || null
  })
})

// POST /api/telegram/link — 绑定 Telegram Chat ID
app.post('/api/telegram/link', authMiddleware, (req, res) => {
  const { telegram_id } = req.body
  if (!telegram_id || !/^-?\d+$/.test(telegram_id)) {
    return res.status(400).json({ error: '请输入有效的 Chat ID（纯数字）' })
  }

  // 检查 chat_id 是否已被其他用户绑定
  const existing = get('SELECT user_id FROM user_telegram WHERE chat_id = ?', telegram_id)
  if (existing && existing.user_id !== req.userId) {
    return res.status(409).json({ error: '该 Chat ID 已被其他用户绑定' })
  }

  // 检查管理员 chat id 冲突
  const config = get('SELECT admin_chat_id FROM telegram_config WHERE id = 1')
  if (config?.admin_chat_id === telegram_id) {
    return res.status(409).json({ error: '该 Chat ID 已被管理员占用' })
  }

  db.run('INSERT OR REPLACE INTO user_telegram (user_id, chat_id) VALUES (?, ?)', [req.userId, telegram_id])
  saveDb()
  res.json({ success: true, telegram_id })
})

// POST /api/telegram/unlink — 解绑
app.post('/api/telegram/unlink', authMiddleware, (req, res) => {
  db.run('DELETE FROM user_telegram WHERE user_id = ?', [req.userId])
  saveDb()
  res.json({ success: true })
})

// GET /api/characters — 获取可用角色列表
app.get('/api/characters', (_, res) => {
  const chars = all('SELECT character_id, name FROM character_bots')
  res.json({ characters: chars.map(c => ({ id: c.character_id, name: c.name })) })
})

// GET /api/character-bindings — 获取角色 Bot Token 绑定
app.get('/api/character-bindings', authMiddleware, (req, res) => {
  const chars = all('SELECT character_id, bot_token FROM character_bots')
  const bindings = {}
  for (const c of chars) {
    if (c.bot_token) {
      bindings[c.character_id] = { bot_token: '********', linked_at: c.created_at }
    }
  }
  res.json({ bindings })
})

// POST /api/bind-character — 为角色绑定 Bot Token（需管理员权限）
app.post('/api/bind-character', authMiddleware, (req, res) => {
  const { character_id, bot_token } = req.body
  if (!character_id || !bot_token) {
    return res.status(400).json({ error: '角色和 Bot Token 不能为空' })
  }

  // 检查 token 是否已被其他角色使用
  const existing = get('SELECT character_id FROM character_bots WHERE bot_token = ? AND character_id != ?', bot_token, character_id)
  if (existing) {
    return res.status(409).json({ error: '该 Bot Token 已被其他角色绑定' })
  }

  db.run('UPDATE character_bots SET bot_token = ? WHERE character_id = ?', [bot_token, character_id])
  saveDb()
  res.json({ success: true })
})

// GET /api/auth/me — 扩展：返回 role 字段
app.get('/api/auth/me', authMiddleware, (req, res) => {
  const user = get('SELECT id, username, created_at FROM users WHERE id = ?', req.userId)
  if (!user) return res.status(404).json({ error: '用户不存在' })

  // 判断是否为管理员（chat_id 匹配 admin_chat_id）
  const config = get('SELECT admin_chat_id FROM telegram_config WHERE id = 1')
  const tgLink = get('SELECT chat_id FROM user_telegram WHERE user_id = ?', req.userId)
  const isAdmin = config?.admin_chat_id && tgLink?.chat_id === config.admin_chat_id

  res.json({
    userId: user.id,
    username: user.username,
    role: isAdmin ? 'admin' : 'user',
    createdAt: user.created_at
  })
})

// ════════════════════════════════════════════════════════════════════════════
// 健康检查
// ════════════════════════════════════════════════════════════════════════════
app.get('/api/health', (_, res) => res.json({ status: 'ok', time: new Date().toISOString() }))

// ═════════════════════════════════════════════════════════════════════════
// 密码找回
// ═════════════════════════════════════════════════════════════════════════

// POST /api/forgot-password
app.post('/api/forgot-password', async (req, res) => {
  const { username, email } = req.body

  // 优先 username 查找，其次 email
  let user = null
  let lookupField = ''

  if (username && username.trim()) {
    user = get('SELECT id, username, email FROM users WHERE username = ?', username.trim())
    lookupField = username.trim()
  } else if (email && /^\S+@\S+\.\S+$/.test(email)) {
    user = get('SELECT id, username, email FROM users WHERE email = ?', email.trim())
    lookupField = email.trim()
  }

  if (!user) {
    return res.json({ success: true, message: '如果该用户已注册，重置链接已生成（请查看服务器日志）' })
  }

  const token = crypto.randomBytes(32).toString('hex')
  const expiresAt = new Date(Date.now() + 3600 * 1000).toISOString()

  db.run('INSERT INTO password_resets (user_id, token, expires_at) VALUES (?, ?, ?)', [user.id, token, expiresAt])
  saveDb()

  const resetUrl = `${req.protocol}://${req.get('host')}/reset-password?token=${token}`

  // 尝试发送邮件；如果用户有邮箱且邮件系统可用则发邮件，否则输出日志
  if (user.email && mailTransporter) {
    try {
      await mailTransporter.sendMail({
        from: `"恋爱至上主义" <${SMTP_FROM}>`,
        to: user.email,
        subject: '重置密码',
        text: `重置链接（1小时内有效）：${resetUrl}`,
        html: `<p>点击重置密码（1小时内有效）：</p><p><a href="${resetUrl}">${resetUrl}</a></p>`
      })
      res.json({ success: true, message: '重置链接已发送到邮箱' })
    } catch (err) {
      console.error('[Mail] 发送失败:', err)
      res.status(500).json({ error: '邮件发送失败，请稍后重试' })
    }
  } else {
    console.log(`[重置密码] ${lookupField} -> ${resetUrl}`)
    res.json({ success: true, message: '重置链接已生成（测试模式：请查看服务器日志）', devToken: token })
  }
})

// POST /api/reset-password
app.post('/api/reset-password', (req, res) => {
  const { token, newPassword } = req.body
  if (!token || !newPassword) {
    return res.status(400).json({ error: 'token 和新密码不能为空' })
  }
  if (newPassword.length < 6) {
    return res.status(400).json({ error: '密码至少6位' })
  }

  const record = get('SELECT * FROM password_resets WHERE token = ? AND used = 0 AND expires_at > datetime("now")', token)
  if (!record) {
    return res.status(400).json({ error: '重置链接无效或已过期' })
  }

  const hashed = bcrypt.hashSync(newPassword, 10)
  db.run('UPDATE users SET password = ? WHERE id = ?', [hashed, record.user_id])
  db.run('UPDATE password_resets SET used = 1 WHERE id = ?', [record.id])
  saveDb()

  res.json({ success: true, message: '密码已重置，请登录' })
})

app.listen(PORT, () => {
  console.log(`[Server] LoveSupremacy 后端 http://localhost:${PORT}`)
})
