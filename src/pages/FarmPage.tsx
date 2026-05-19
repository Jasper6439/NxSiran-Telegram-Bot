import { useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import { Sprout, Info } from 'lucide-react'
import { useGameStore, useFarmStore } from '../stores'
import FarmScene from '../features/farm/FarmScene'

// ─────────────────────────────────────────────────────────────────────────────
// 农场页
// ─────────────────────────────────────────────────────────────────────────────

export default function FarmPage() {
  const worldMode = useGameStore((s) => s.worldMode)
  const matureCount = useFarmStore((s) => s.plots.filter(p => p.cropId && p.stage === 3).length)
  const plantedCount = useFarmStore((s) => s.plots.filter(p => p.cropId !== null).length)

  return (
    <div className="ios-page">
      {/* ── Navigation ──────────────────────────────────────────────── */}
      <div className="ios-safe-top" />
      <div className="ios-navbar" style={{ padding: '8px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Sprout size={18} style={{ color: 'var(--ios-green)' }} />
          <span style={{ fontSize: 17, fontWeight: 600, color: 'var(--realm-text)' }}>
            农场
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <motion.div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              padding: '4px 10px',
              borderRadius: 20,
              background: 'var(--ios-gray5)',
              fontSize: 12,
              color: 'var(--realm-text)',
            }}
            whileTap={{ scale: 0.95 }}
          >
            <Sprout size={12} />
            <span>{plantedCount}</span>
            {matureCount > 0 && (
              <>
                <span style={{ color: 'var(--ios-gray)', margin: '0 2px' }}>·</span>
                <span style={{ color: 'var(--ios-green)' }}>🌾{matureCount}</span>
              </>
            )}
          </motion.div>
          <motion.div
            style={{
              width: 24,
              height: 24,
              borderRadius: 12,
              background: 'var(--ios-gray5)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
            }}
            whileTap={{ scale: 0.85 }}
            title="在农场种植作物，收获后可烹饪食物送给角色增加好感度"
          >
            <Info size={14} style={{ color: 'var(--ios-gray)' }} />
          </motion.div>
        </div>
      </div>

      {/* ── Phaser 农场场景 ────────────────────────────────────────── */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '0 16px 16px',
        }}
      >
        <div
          className="ios-widget-glass"
          style={{
            width: '100%',
            maxWidth: 420,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 8,
          }}
        >
          <FarmScene />
        </div>
      </div>

      {/* ── 底部提示 ────────────────────────────────────────────────── */}
      <div
        style={{
          padding: '0 16px 12px',
          textAlign: 'center',
          fontSize: 12,
          color: 'var(--ios-gray)',
          lineHeight: 1.5,
        }}
      >
        种植 → 收获食材 → 烹饪食物 → 赠送角色增加好感度
      </div>
    </div>
  )
}