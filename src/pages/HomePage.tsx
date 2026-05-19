import { motion } from 'framer-motion'
import {
  Heart,
  Sparkles,
  MessageCircle,
  Sprout,
  ChevronRight,
  Moon,
  Sun,
} from 'lucide-react'
import { useGameStore, useFarmStore } from '../stores'

// ─────────────────────────────────────────────────────────────────────────────
// Widget 定义
// ─────────────────────────────────────────────────────────────────────────────

interface WidgetProps {
  children: React.ReactNode
  className?: string
  style?: React.CSSProperties
  onClick?: () => void
}

function Widget({ children, className = '', style, onClick }: WidgetProps) {
  return (
    <motion.div
      className={`ios-widget-glass ${className}`}
      style={style}
      onClick={onClick}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
    >
      {children}
    </motion.div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 首页
// ─────────────────────────────────────────────────────────────────────────────

export default function HomePage() {
  const worldMode = useGameStore((s) => s.worldMode)
  const awakeningLevel = useGameStore((s) => s.awakeningLevel)
  const toggleWorldMode = useGameStore((s) => s.toggleWorldMode)
  const farmPlots = useFarmStore((s) => s.plots)

  const matureCount = farmPlots.filter((p) => p.cropId && p.stage === 3).length
  const plantedCount = farmPlots.filter((p) => p.cropId !== null).length

  return (
    <div className="ios-page">
      {/* ── Large Title ──────────────────────────────────────────────── */}
      <div className="ios-safe-top" />
      <h1 className="ios-nav-large-title" style={{ color: 'var(--realm-text)' }}>
        恋爱至上主义
      </h1>
      <p style={{ padding: '0 16px', fontSize: 14, color: 'var(--ios-gray)', marginBottom: 12 }}>
        欢迎回来，继续你的故事
      </p>

      {/* ── Widget 网格 ──────────────────────────────────────────────── */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 12,
          padding: '0 16px 16px',
        }}
      >
        {/* 觉醒状态 Widget */}
        <Widget style={{ gridColumn: '1 / -1' }}>
          <div style={{ padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Sparkles size={18} style={{ color: worldMode === 'broken' ? 'var(--ios-gray)' : 'var(--realm-accent)' }} />
                <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--realm-text)' }}>觉醒进度</span>
              </div>
              <span style={{ fontSize: 13, color: 'var(--ios-gray)' }}>
                {awakeningLevel} / 100
              </span>
            </div>
            <div
              className="awakening-bar"
              style={{ width: '100%', height: 6, marginBottom: 8 }}
            >
              <div
                className="awakening-fill"
                style={{ width: `${Math.min(100, (awakeningLevel / 100) * 100)}%` }}
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 12, color: 'var(--ios-gray)' }}>
                {awakeningLevel >= 100 ? '✨ 觉醒圆满 — 双界穿梭已解锁' : '💫 探索故事以提升觉醒值'}
              </span>
              <div
                className="mode-toggle"
                onClick={toggleWorldMode}
                style={{ cursor: 'pointer', padding: '4px 10px', fontSize: 12 }}
              >
                {worldMode === 'script' ? <Sun size={12} /> : <Moon size={12} />}
                <span>{worldMode === 'script' ? '剧本' : '崩坏'}</span>
              </div>
            </div>
          </div>
        </Widget>

        {/* 最近聊天 Widget */}
        <Widget onClick={() => window.location.href = '/game'}>
          <div style={{ padding: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
              <MessageCircle size={16} style={{ color: 'var(--ios-blue)' }} />
              <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--realm-text)' }}>剧本区</span>
            </div>
            <div
              className="ios-avatar"
              style={{
                width: 40,
                height: 40,
                background: 'linear-gradient(135deg, var(--realm-accent), var(--realm-secondary))',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 20,
                marginBottom: 8,
              }}
            >
              ☁️
            </div>
            <p style={{ fontSize: 13, color: 'var(--ios-gray)', lineHeight: 1.4 }}>
              车如云在等你
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 8 }}>
              <span style={{ fontSize: 12, color: 'var(--ios-blue)' }}>继续聊天</span>
              <ChevronRight size={12} style={{ color: 'var(--ios-blue)' }} />
            </div>
          </div>
        </Widget>

        {/* 农场摘要 Widget */}
        <Widget onClick={() => window.location.href = '/farm'}>
          <div style={{ padding: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
              <Sprout size={16} style={{ color: 'var(--ios-green)' }} />
              <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--realm-text)' }}>农场</span>
            </div>
            <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--realm-text)', marginBottom: 4 }}>
              {plantedCount}
            </div>
            <p style={{ fontSize: 12, color: 'var(--ios-gray)' }}>
              {matureCount > 0
                ? `🌾 ${matureCount} 个地块已成熟待收获`
                : '🌱 耕作等待你的照料'}
            </p>
          </div>
        </Widget>

        {/* 双界状态 Widget */}
        <Widget style={{ gridColumn: '1 / -1' }}>
          <div style={{ padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <Heart size={16} style={{ color: 'var(--realm-accent)' }} />
              <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--realm-text)' }}>双界之隙</span>
            </div>
            <div style={{ display: 'flex', gap: 12 }}>
              {[
                { mode: 'script', label: '剧本模式', desc: '唯美恋爱物语', color: 'var(--realm-accent)', active: worldMode === 'script' },
                { mode: 'broken', label: '崩坏模式', desc: '觉醒反抗之路', color: 'var(--ios-gray)', active: worldMode === 'broken' },
              ].map((item) => (
                <div
                  key={item.mode}
                  style={{
                    flex: 1,
                    padding: 12,
                    borderRadius: 10,
                    background: item.active
                      ? `color-mix(in srgb, ${item.color} 12%, transparent)`
                      : 'transparent',
                    border: `0.5px solid ${item.active ? item.color : 'var(--ios-separator)'}`,
                  }}
                >
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--realm-text)', marginBottom: 2 }}>
                    {item.label}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--ios-gray)' }}>{item.desc}</div>
                </div>
              ))}
            </div>
          </div>
        </Widget>
      </div>
    </div>
  )
}