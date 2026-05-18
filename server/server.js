import express from 'express'
import cors from 'cors'
import bcrypt from 'bcryptjs'
import { signToken, authMiddleware } from './middleware/auth.js'

// 初始化数据库
await import('./dbInit.js')
import db, { saveDb } from './dbInit.js'

const app = express()
const PORT = process.env.PORT || 3001

// ── 中间件 ──────────────────────────────────────────────────────────────────
app.use(cors({ origin: 'http://localhost:5173', credentials: true }))
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
    db.run('INSERT INTO game_state (user_id) VALUES (?)', userId)
    // 初始化25个地块
    for (let i = 0; i < 25; i++) {
      db.run('INSERT OR IGNORE INTO farm_data (user_id, plot_id) VALUES (?, ?)', userId, i)
    }
    saveDb()
    state = get('SELECT * FROM game_state WHERE user_id = ?', userId)
  }
  return state
}

// ════════════════════════════════════════════════════════════════════════════
// 认证接口
// ════════════════════════════════════════════════════════════════════════════

// POST /api/register
app.post('/api/register', (req, res) => {
  const { username, password } = req.body
  if (!username || !password) {
    return res.status(400).json({ error: '用户名和密码不能为空' })
  }
  if (username.length < 3 || password.length < 6) {
    return res.status(400).json({ error: '用户名至少3位，密码至少6位' })
  }

  const existing = get('SELECT id FROM users WHERE username = ?', username)
  if (existing) {
    return res.status(409).json({ error: '用户名已存在' })
  }

  const hashed = bcrypt.hashSync(password, 10)
  db.run('INSERT INTO users (username, password) VALUES (?, ?)', username, hashed)
  saveDb()

  // 取 lastInsertRowid（sql.js 用 last_id）
  const user = get('SELECT last_insert_rowid() as id')
  const userId = user?.id

  const token = signToken(userId)
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

  const token = signToken(user.id)
  const state = getOrInitGameState(user.id)
  db.run("UPDATE game_state SET last_login = datetime('now') WHERE user_id = ?", user.id)
  saveDb()

  res.json({ token, userId: user.id, gameState: state })
})

// GET /api/auth/me
app.get('/api/auth/me', authMiddleware, (req, res) => {
  const user = get('SELECT id, username, created_at FROM users WHERE id = ?', req.userId)
  if (!user) return res.status(404).json({ error: '用户不存在' })
  res.json({ userId: user.id, username: user.username, createdAt: user.created_at })
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
  db.run(`UPDATE game_state SET ${updates.join(', ')} WHERE user_id = ?`, ...params)
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
    db.run('UPDATE inventory SET quantity = quantity + ? WHERE user_id = ? AND item_id = ? AND mode = ?', quantity, req.userId, itemId, mode)
  } else {
    db.run('INSERT INTO inventory (user_id, item_id, quantity, mode) VALUES (?, ?, ?, ?)', req.userId, itemId, quantity, mode)
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
    db.run('UPDATE farm_data SET crop_type = ?, planted_at = ?, is_watered = 0, stage = 0 WHERE user_id = ? AND plot_id = ?', cropType, Date.now(), req.userId, plotId)
  } else if (action === 'water') {
    db.run('UPDATE farm_data SET is_watered = 1 WHERE user_id = ? AND plot_id = ?', req.userId, plotId)
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
  db.run("INSERT INTO chat_history (user_id, role, content) VALUES (?, 'user', ?)", req.userId, message)

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
    db.run("INSERT INTO chat_history (user_id, role, content) VALUES (?, 'assistant', ?)", req.userId, mockText)
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
    db.run("INSERT INTO chat_history (user_id, role, content) VALUES (?, 'assistant', ?)", req.userId, aiText)

    // 更新觉醒值
    if (awakeningChange !== 0) {
      const state = getOrInitGameState(req.userId)
      const newLevel = Math.max(0, (state.awakening_level || 0) + awakeningChange)
      db.run('UPDATE game_state SET awakening_level = ? WHERE user_id = ?', newLevel, req.userId)
    }

    saveDb()
    res.json({ text: aiText, emotion, awakeningChange })
  } catch (err) {
    console.error('[AI] 调用失败:', err)
    res.status(500).json({ error: 'AI 调用失败' })
  }
})

// ════════════════════════════════════════════════════════════════════════════
// 健康检查
// ════════════════════════════════════════════════════════════════════════════
app.get('/api/health', (_, res) => res.json({ status: 'ok', time: new Date().toISOString() }))

app.listen(PORT, () => {
  console.log(`[Server] LoveSupremacy 后端 http://localhost:${PORT}`)
})
