import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Bot,
  Shield,
  User,
  Check,
  AlertCircle,
  Loader2,
  ChevronRight,
  Link2,
  Unlink,
  Key,
} from 'lucide-react'

// ─────────────────────────────────────────────────────────────────────────────
// 类型
// ─────────────────────────────────────────────────────────────────────────────

interface TelegramLinkStatus {
  telegram_id: string | null
  linked: boolean
}

interface CharacterBindings {
  [characterId: string]: {
    bot_token: string
    linked_at: string
  }
}

interface ToastMessage {
  type: 'success' | 'error'
  message: string
}

// ─────────────────────────────────────────────────────────────────────────────
// iOS 风格组件
// ─────────────────────────────────────────────────────────────────────────────

function Toast({ message, type, onClose }: ToastMessage & { onClose: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onClose, 3000)
    return () => clearTimeout(timer)
  }, [onClose])

  return (
    <motion.div
      initial={{ opacity: 0, y: 50 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 50 }}
      style={{
        position: 'fixed',
        bottom: 80,
        left: 16,
        right: 16,
        padding: '14px 16px',
        borderRadius: 12,
        background: type === 'success' ? 'var(--ios-green)' : 'var(--ios-red)',
        color: 'white',
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        fontSize: 14,
        fontWeight: 500,
        zIndex: 200,
        boxShadow: '0 8px 24px rgba(0,0,0,0.15)',
      }}
    >
      {type === 'success' ? <Check size={18} /> : <AlertCircle size={18} />}
      {message}
    </motion.div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 设置页
// ─────────────────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState<ToastMessage | null>(null)

  // Telegram 绑定
  const [chatId, setChatId] = useState('')
  const [telegramStatus, setTelegramStatus] = useState<TelegramLinkStatus>({
    telegram_id: null,
    linked: false,
  })

  // 角色 Bot
  const [selectedCharacter, setSelectedCharacter] = useState('')
  const [botToken, setBotToken] = useState('')
  const [characterBindings, setCharacterBindings] = useState<CharacterBindings>({})
  const [availableCharacters, setAvailableCharacters] = useState<string[]>([])

  // 管理员
  const [isAdmin, setIsAdmin] = useState(false)
  const [userRole, setUserRole] = useState('')
  const [adminUsername, setAdminUsername] = useState('')
  const [adminPassword, setAdminPassword] = useState('')

  // ── API 调用 ──────────────────────────────────────────────────────────
  const api = (path: string, options?: RequestInit) => {
    const token = localStorage.getItem('ls_token')
    return fetch(path, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
        ...options?.headers,
      },
    })
  }

  useEffect(() => {
    const loadAll = async () => {
      setLoading(true)
      try {
        const [tgRes, charRes, charsRes, meRes] = await Promise.all([
          api('/api/telegram/link'),
          api('/api/character-bindings'),
          api('/api/characters'),
          api('/api/auth/me'),
        ])

        if (tgRes.ok) {
          const data = await tgRes.json()
          setTelegramStatus(data)
          if (data.telegram_id) setChatId(data.telegram_id)
        }
        if (charRes.ok) {
          const data = await charRes.json()
          setCharacterBindings(data.bindings || {})
        }
        if (charsRes.ok) {
          const data = await charsRes.json()
          setAvailableCharacters(data.characters || [])
        }
        if (meRes.ok) {
          const data = await meRes.json()
          setUserRole(data.role || '')
          setIsAdmin(data.role === 'admin')
        }
      } catch {}
      setLoading(false)
    }
    loadAll()
  }, [])

  // ── 操作 ──────────────────────────────────────────────────────────────
  const handleLinkTelegram = async () => {
    if (!chatId.trim()) { setToast({ type: 'error', message: '请输入 Chat ID' }); return }
    setSaving(true)
    try {
      const res = await api('/api/telegram/link', { method: 'POST', body: JSON.stringify({ telegram_id: chatId }) })
      if (res.ok) {
        setTelegramStatus({ telegram_id: chatId, linked: true })
        setToast({ type: 'success', message: 'Telegram 账号绑定成功！' })
      } else {
        setToast({ type: 'error', message: (await res.json()).message || '绑定失败' })
      }
    } catch { setToast({ type: 'error', message: '网络错误' }) }
    setSaving(false)
  }

  const handleUnlinkTelegram = async () => {
    setSaving(true)
    try {
      const res = await api('/api/telegram/unlink', { method: 'POST' })
      if (res.ok) {
        setTelegramStatus({ telegram_id: null, linked: false })
        setChatId('')
        setToast({ type: 'success', message: '已解绑' })
      }
    } catch { setToast({ type: 'error', message: '网络错误' }) }
    setSaving(false)
  }

  const handleBindCharacter = async () => {
    if (!selectedCharacter) { setToast({ type: 'error', message: '请选择角色' }); return }
    if (!botToken.trim()) { setToast({ type: 'error', message: '请输入 Bot Token' }); return }
    setSaving(true)
    try {
      const res = await api('/api/bind-character', {
        method: 'POST',
        body: JSON.stringify({ character_id: selectedCharacter, bot_token: botToken }),
      })
      if (res.ok) {
        const data = await api('/api/character-bindings')
        if (data.ok) setCharacterBindings((await data.json()).bindings || {})
        setBotToken('')
        setToast({ type: 'success', message: '角色 Bot 绑定成功！' })
      } else {
        setToast({ type: 'error', message: (await res.json()).message || '绑定失败' })
      }
    } catch { setToast({ type: 'error', message: '网络错误' }) }
    setSaving(false)
  }

  if (loading) {
    return (
      <div className="ios-page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}>
          <Loader2 size={36} style={{ color: 'var(--ios-blue)' }} />
        </motion.div>
      </div>
    )
  }

  return (
    <div className="ios-page">
      <div className="ios-safe-top" />
      <div className="ios-navbar" style={{ padding: '8px 16px 4px' }}>
        <span style={{ fontSize: 17, fontWeight: 600, color: 'var(--realm-text)' }}>设置</span>
      </div>

      <div className="ios-scroll" style={{ flex: 1, padding: '0 16px 80px' }}>
        {/* Telegram 绑定 */}
        <div style={{ marginBottom: 20 }}>
          <SectionHeader icon={Bot} label="Telegram 账号绑定" color="var(--ios-blue)" />
          <div className="ios-list">
            <div className="ios-list-item" style={{ cursor: 'default' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{
                  width: 10, height: 10, borderRadius: 5,
                  background: telegramStatus.linked ? 'var(--ios-green)' : 'var(--ios-gray)',
                }} />
                <span style={{ fontSize: 14, color: 'var(--realm-text)' }}>
                  {telegramStatus.linked ? `已绑定: ${telegramStatus.telegram_id}` : '未绑定'}
                </span>
              </div>
            </div>
            <div className="ios-list-item" style={{ cursor: 'default' }}>
              <input
                value={chatId}
                onChange={(e) => setChatId(e.target.value)}
                placeholder="输入 Telegram Chat ID"
                style={{
                  flex: 1, border: 'none', outline: 'none', fontSize: 14,
                  background: 'transparent', color: 'var(--realm-text)',
                }}
              />
            </div>
            <div className="ios-list-item" style={{ gap: 8, justifyContent: 'flex-start' }}>
              <button
                className="ios-btn ios-btn-primary"
                style={{ flex: 1, padding: '8px 16px', fontSize: 14 }}
                onClick={handleLinkTelegram}
                disabled={saving}
              >
                <Link2 size={14} />
                {telegramStatus.linked ? '更新绑定' : '绑定'}
              </button>
              {telegramStatus.linked && (
                <button
                  className="ios-btn"
                  style={{ flex: 1, padding: '8px 16px', fontSize: 14, background: 'var(--ios-red)', color: 'white' }}
                  onClick={handleUnlinkTelegram}
                  disabled={saving}
                >
                  <Unlink size={14} /> 解绑
                </button>
              )}
            </div>
          </div>
        </div>

        {/* 角色 Bot 配置 */}
        <div style={{ marginBottom: 20 }}>
          <SectionHeader icon={User} label="角色 Bot 配置" color="var(--ios-purple)" />
          <div className="ios-list">
            {Object.entries(characterBindings).map(([charId, binding]) => (
              <div key={charId} className="ios-list-item" style={{ cursor: 'default' }}>
                <span style={{ fontSize: 14, color: 'var(--realm-text)', fontWeight: 500 }}>{charId}</span>
                <span style={{ fontSize: 12, color: 'var(--ios-gray)' }}>
                  {new Date(binding.linked_at).toLocaleDateString()}
                </span>
              </div>
            ))}
            <div className="ios-list-item" style={{ cursor: 'default', flexDirection: 'column', alignItems: 'stretch', gap: 8 }}>
              <select
                value={selectedCharacter}
                onChange={(e) => setSelectedCharacter(e.target.value)}
                style={{
                  padding: '8px 12px',
                  borderRadius: 8,
                  border: '0.5px solid var(--ios-separator)',
                  fontSize: 14,
                  background: 'var(--ios-bg)',
                  color: 'var(--realm-text)',
                  outline: 'none',
                }}
              >
                <option value="">选择角色</option>
                {availableCharacters.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input
                  value={botToken}
                  onChange={(e) => setBotToken(e.target.value)}
                  type="password"
                  placeholder="Bot Token"
                  style={{
                    flex: 1, padding: '8px 12px', borderRadius: 8,
                    border: '0.5px solid var(--ios-separator)', fontSize: 14,
                    background: 'var(--ios-bg)', color: 'var(--realm-text)',
                    outline: 'none',
                  }}
                />
                <button
                  className="ios-btn ios-btn-primary"
                  style={{ padding: '8px 16px', fontSize: 14, whiteSpace: 'nowrap' }}
                  onClick={handleBindCharacter}
                  disabled={saving}
                >
                  <Key size={14} /> 绑定
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* 管理员配置 */}
        {isAdmin && (
          <div style={{ marginBottom: 20 }}>
            <SectionHeader
              icon={Shield}
              label="管理员配置"
              color="var(--ios-orange)"
              badge={userRole}
            />
            <div className="ios-list">
              <div className="ios-list-item" style={{ cursor: 'default', flexDirection: 'column', alignItems: 'stretch', gap: 8 }}>
                <input
                  value={adminUsername}
                  onChange={(e) => setAdminUsername(e.target.value)}
                  placeholder="管理员用户名"
                  style={{
                    padding: '8px 12px', borderRadius: 8,
                    border: '0.5px solid var(--ios-separator)', fontSize: 14,
                    background: 'var(--ios-bg)', color: 'var(--realm-text)',
                    outline: 'none',
                  }}
                />
                <input
                  value={adminPassword}
                  onChange={(e) => setAdminPassword(e.target.value)}
                  type="password"
                  placeholder="管理员密码"
                  style={{
                    padding: '8px 12px', borderRadius: 8,
                    border: '0.5px solid var(--ios-separator)', fontSize: 14,
                    background: 'var(--ios-bg)', color: 'var(--realm-text)',
                    outline: 'none',
                  }}
                />
                <button
                  className="ios-btn ios-btn-primary"
                  style={{ width: '100%', padding: '8px', fontSize: 14 }}
                  disabled={saving}
                >
                  保存配置
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 关于 */}
        <div style={{ textAlign: 'center', padding: 20 }}>
          <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--realm-text)', marginBottom: 4 }}>
            LoveSupremacy Universe
          </p>
          <p style={{ fontSize: 12, color: 'var(--ios-gray)' }}>
            恋爱至上主义 · 双界穿梭
          </p>
        </div>
      </div>

      <AnimatePresence>
        {toast && <Toast type={toast.type} message={toast.message} onClose={() => setToast(null)} />}
      </AnimatePresence>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// iOS Section Header
// ─────────────────────────────────────────────────────────────────────────────

function SectionHeader({
  icon: Icon,
  label,
  color,
  badge,
}: {
  icon: typeof Bot
  label: string
  color: string
  badge?: string
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 4px 6px' }}>
      <Icon size={16} style={{ color }} />
      <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--realm-text)' }}>
        {label}
      </span>
      {badge && (
        <span
          style={{
            fontSize: 10,
            padding: '2px 6px',
            borderRadius: 4,
            background: 'color-mix(in srgb, var(--ios-orange) 20%, transparent)',
            color: 'var(--ios-orange)',
            fontWeight: 600,
          }}
        >
          {badge}
        </span>
      )}
    </div>
  )
}