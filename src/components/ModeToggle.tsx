import { useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useGameStore } from '../stores'

/**
 * 双界穿梭开关组件
 * - 始终可点击，随时切换剧本/崩坏模式
 * - 切换时：Framer Motion 快速动画 + DOM 数据瞬变（0ms）
 */
export default function ModeToggle() {
  const worldMode = useGameStore((s) => s.worldMode)
  const awakeningLevel = useGameStore((s) => s.awakeningLevel)
  const toggleWorldMode = useGameStore((s) => s.toggleWorldMode)

  // 初始化时同步 DOM 属性
  useEffect(() => {
    document.body.setAttribute('data-world-mode', worldMode)
  }, [worldMode])

  return (
    <button
      className="mode-toggle"
      onClick={toggleWorldMode}
      aria-label={`当前模式：${worldMode === 'script' ? '剧本' : '崩坏'}，点击切换`}
      title={`觉醒值 ${awakeningLevel} | 点击切换剧本/崩坏模式`}
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={worldMode}
          initial={{ opacity: 0, scale: 0.7, rotate: -15 }}
          animate={{ opacity: 1, scale: 1, rotate: 0 }}
          exit={{ opacity: 0, scale: 0.7, rotate: 15 }}
          transition={{ duration: 0.15, ease: 'easeOut' }}
          style={{ display: 'inline-block', lineHeight: 1 }}
        >
          {worldMode === 'script' ? '🌸' : '⚫'}
        </motion.span>
      </AnimatePresence>
      <span>{worldMode === 'script' ? '剧本' : '崩坏'}</span>
    </button>
  )
}
