import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { MessageCircle, Swords, Sparkles } from 'lucide-react'
import { useGameStore } from '../stores'
import { gameApi } from '../api/gameApi'
import ModeToggle from '../components/ModeToggle'
import ChatInterface from '../features/chat/ChatInterface'

// ─────────────────────────────────────────────────────────────────────────────
// 药丸选项
// ─────────────────────────────────────────────────────────────────────────────

type GameMode = 'chat' | 'action'

const PILLS: { id: GameMode; label: string; icon: typeof MessageCircle }[] = [
  { id: 'chat',   label: '剧本区',   icon: MessageCircle },
  { id: 'action', label: '崩坏区',   icon: Swords },
]

// ─────────────────────────────────────────────────────────────────────────────
// 崩坏区占位（空区域，待 Phaser 横板战斗实现）
// ─────────────────────────────────────────────────────────────────────────────

function ActionZone() {
  const awakeningLevel = useGameStore((s) => s.awakeningLevel)
  const worldMode = useGameStore((s) => s.worldMode)
  const isUnlocked = awakeningLevel >= 100

  if (!isUnlocked) {
    return (
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 40,
          gap: 16,
        }}
      >
        <div
          style={{
            width: 80,
            height: 80,
            borderRadius: 20,
            background: worldMode === 'broken'
              ? 'rgba(100,100,100,0.15)'
              : 'rgba(248,165,194,0.12)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Sparkles size={36} style={{ opacity: 0.3, color: 'var(--realm-text)' }} />
        </div>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: 'var(--realm-text)', margin: 0 }}>
          崩坏战斗区
        </h2>
        <p style={{ fontSize: 14, color: 'var(--ios-gray)', textAlign: 'center', lineHeight: 1.5 }}>
          觉醒值达到 100 后解锁
          <br />
          在这里拯救被困在小说中的角色，让他觉醒独立人格
        </p>
        <div className="awakening-bar" style={{ width: 200, height: 6 }}>
          <div
            className="awakening-fill"
            style={{ width: `${Math.min(100, (awakeningLevel / 100) * 100)}%` }}
          />
        </div>
        <span style={{ fontSize: 12, color: 'var(--ios-gray)' }}>
          {awakeningLevel} / 100
        </span>
      </div>
    )
  }

  // 已解锁——空白区域，留待 Phaser 横板游戏填充
  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 40,
        gap: 12,
        background: worldMode === 'broken'
          ? 'rgba(0,0,0,0.3)'
          : 'rgba(248,165,194,0.04)',
      }}
    >
      <Swords size={48} style={{ opacity: 0.2, color: 'var(--realm-text)' }} />
      <p style={{ fontSize: 14, color: 'var(--ios-gray)' }}>
        崩坏区 — 横版动作游戏（开发中）
      </p>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 游戏页
// ─────────────────────────────────────────────────────────────────────────────

export default function GamePage() {
  const navigate = useNavigate()
  const worldMode = useGameStore((s) => s.worldMode)
  const awakeningLevel = useGameStore((s) => s.awakeningLevel)
  const setWorldMode = useGameStore((s) => s.setWorldMode)
  const addAwakening = useGameStore((s) => s.addAwakening)
  const [activeMode, setActiveMode] = useState<GameMode>('chat')

  // 从后端加载
  useEffect(() => {
    const token = localStorage.getItem('ls_token')
    if (!token) { navigate('/login'); return }
    gameApi.getState()
      .then(({ data }) => {
        const { state } = data
        if (state) {
          setWorldMode((state as any).world_mode === 'broken' ? 'broken' : 'script')
        }
      })
      .catch(() => {})
  }, [])

  // 同步 worldMode 到 DOM
  useEffect(() => {
    document.body.setAttribute('data-world-mode', worldMode)
  }, [worldMode])

  // 调试按键 D → +10 觉醒
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'd' || e.key === 'D') addAwakening(10)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [addAwakening])

  return (
    <div className="ios-page" style={{ display: 'flex', flexDirection: 'column' }}>
      {/* ── Navigation Bar ──────────────────────────────────────────── */}
      <div className="ios-safe-top" />
      <div className="ios-navbar" style={{ padding: '8px 16px 4px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 17, fontWeight: 600, color: 'var(--realm-text)' }}>
            游戏
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* 觉醒值 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Sparkles size={14} style={{ color: worldMode === 'broken' ? 'var(--ios-gray)' : 'var(--realm-accent)' }} />
            <span style={{ fontSize: 12, color: 'var(--ios-gray)' }}>{awakeningLevel}</span>
          </div>
          <ModeToggle />
        </div>
      </div>

      {/* ── 药丸切换器 ──────────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'center', padding: '4px 16px 10px' }}>
        <div className="ios-pill-group">
          {PILLS.map((pill) => {
            const Icon = pill.icon
            return (
              <button
                key={pill.id}
                className={`ios-pill ${activeMode === pill.id ? 'active' : ''}`}
                onClick={() => setActiveMode(pill.id)}
                style={{ display: 'flex', alignItems: 'center', gap: 6 }}
              >
                <Icon size={14} />
                {pill.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* ── 内容 ────────────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <AnimatePresence mode="wait">
          {activeMode === 'chat' && (
            <motion.div
              key="chat"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
              style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
            >
              <ChatInterface />
            </motion.div>
          )}

          {activeMode === 'action' && (
            <motion.div
              key="action"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
              style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
            >
              <ActionZone />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}