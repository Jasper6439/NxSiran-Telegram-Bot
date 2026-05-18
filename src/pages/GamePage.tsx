import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Heart, Home, Shovel, Sword, Settings } from 'lucide-react'
import { useGameStore, useFarmStore } from '../stores'
import { gameApi, farmApi } from '../api/gameApi'
import ModeToggle from '../components/ModeToggle'
import ChatInterface from '../features/chat/ChatInterface'
import FarmScene from '../features/farm/FarmScene'

// 导航按钮类型
type NavItem = {
  id: 'chat' | 'farm' | 'action'
  label: string
  icon: typeof Heart
  requireUnlock?: boolean
}

const NAV_ITEMS: NavItem[] = [
  { id: 'chat', label: '剧本', icon: Heart },
  { id: 'farm', label: '农场', icon: Shovel },
  { id: 'action', label: '战斗', icon: Sword, requireUnlock: true },
]

export default function GamePage() {
  const navigate = useNavigate()
  const worldMode = useGameStore((s) => s.worldMode)
  const awakeningLevel = useGameStore((s) => s.awakeningLevel)
  const isModeLocked = useGameStore((s) => s.isModeLocked)
  const currentScene = useGameStore((s) => s.currentScene)
  const setWorldMode = useGameStore((s) => s.setWorldMode)
  const setScene = useGameStore((s) => s.setScene)
  const addAwakening = useGameStore((s) => s.addAwakening)
  const tickGrowth = useFarmStore((s) => s.tickGrowth)

  // ── 初始化：从后端加载状态 ──────────────────────────────────────────────
  useEffect(() => {
    const token = localStorage.getItem('ls_token')
    if (!token) { navigate('/login'); return }

    gameApi.getState()
      .then(({ data }) => {
        const { state } = data
        // 同步到 Zustand
        if (state) {
          setWorldMode(state.world_mode === 'broken' ? 'broken' : 'script')
        }
      })
      .catch(() => {
        // 无网络时使用本地状态继续
      })
  }, [])

  // ── 同步 worldMode 到 DOM ───────────────────────────────────────────────
  useEffect(() => {
    document.body.setAttribute('data-world-mode', worldMode)
  }, [worldMode])

  // ── Farm growth tick ────────────────────────────────────────────────────
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null)
  useEffect(() => {
    tickRef.current = setInterval(() => {
      tickGrowth()
      // 同步到后端（节流：每10秒一次）
      if (Math.random() < 0.1) {
        farmApi.getState().catch(() => {})
      }
    }, 1000)
    return () => { if (tickRef.current) clearInterval(tickRef.current) }
  }, [tickGrowth])

  // ── 场景切换（同时更新后端） ───────────────────────────────────────────
  const handleNavClick = (sceneId: 'chat' | 'farm' | 'action') => {
    if (sceneId === 'action' && isModeLocked) return
    setScene(sceneId)
    gameApi.saveState({ currentScene: sceneId }).catch(() => {})
  }

  // ── 开发调试 ────────────────────────────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'd' || e.key === 'D') addAwakening(10)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [addAwakening])

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ backgroundColor: 'var(--realm-bg)', color: 'var(--realm-text)' }}
    >
      {/* ── 顶部 HUD ───────────────────────────────────────────────────── */}
      <header
        className="flex items-center justify-between px-6 py-3 border-b"
        style={{ borderColor: 'var(--card-border)', backgroundColor: 'var(--card-bg)' }}
      >
        {/* 左：标题 */}
        <div className="flex items-center gap-2">
          <span className="text-xl">💕</span>
          <span className="font-bold text-sm">恋爱至上主义</span>
        </div>

        {/* 中：觉醒进度 */}
        <div className="flex items-center gap-3">
          <span style={{ fontSize: 12, opacity: 0.7 }}>
            觉醒 {awakeningLevel}
            <span style={{ opacity: 0.5 }}>/100</span>
          </span>
          <div className="awakening-bar" style={{ width: 100, height: 8 }}>
            <div
              className="awakening-fill"
              style={{ width: `${Math.min(100, (awakeningLevel / 100) * 100)}%` }}
            />
          </div>
        </div>

        {/* 右：模式切换 + 设置 */}
        <div className="flex items-center gap-3">
          <ModeToggle />
          <button
            onClick={() => navigate('/settings')}
            className="p-2 rounded-lg hover:bg-white/10 transition-colors"
            title="设置"
          >
            <Settings size={18} />
          </button>
        </div>
      </header>

      {/* ── 主体内容 ───────────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <AnimatePresence mode="wait">
          {currentScene === 'chat' && (
            <motion.div
              key="chat"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex-1"
            >
              <ChatInterface />
            </motion.div>
          )}

          {currentScene === 'farm' && (
            <motion.div
              key="farm"
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              className="flex-1 flex items-center justify-center p-4"
            >
              <FarmScene />
            </motion.div>
          )}

          {currentScene === 'action' && (
            <motion.div
              key="action"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex-1 flex items-center justify-center"
            >
              <div className="text-center">
                <Sword size={64} className="mx-auto mb-4 opacity-30" />
                <h2 className="text-2xl font-bold mb-2">崩坏战斗区</h2>
                <p className="opacity-60">觉醒值达到 100 后解锁</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* ── 底部导航 ───────────────────────────────────────────────────── */}
      <nav
        className="flex justify-around py-3 border-t"
        style={{
          borderColor: 'var(--card-border)',
          backgroundColor: 'var(--card-bg)',
        }}
      >
        {NAV_ITEMS.map(({ id, label, icon: Icon, requireUnlock }) => {
          const locked = requireUnlock && isModeLocked
          const active = currentScene === id
          return (
            <button
              key={id}
              onClick={() => handleNavClick(id)}
              disabled={locked}
              title={locked ? `觉醒值达到100后解锁` : label}
              className={`flex flex-col items-center gap-1 px-6 py-2 rounded-xl transition-all ${
                active
                  ? 'opacity-100 scale-105'
                  : locked
                  ? 'opacity-30 cursor-not-allowed'
                  : 'opacity-60 hover:opacity-100'
              }`}
              style={active ? { color: 'var(--realm-accent)' } : undefined}
            >
              <Icon size={22} />
              <span style={{ fontSize: 11 }}>{label}</span>
              {locked && <span style={{ fontSize: 9 }}>🔒</span>}
            </button>
          )
        })}
      </nav>
    </div>
  )
}
