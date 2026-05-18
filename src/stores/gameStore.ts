import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// ─────────────────────────────────────────────────────────────────────────────
// 类型定义
// ─────────────────────────────────────────────────────────────────────────────

export type WorldMode = 'script' | 'broken'
export type GameScene = 'chat' | 'farm' | 'action'

export interface GameState {
  // ── 核心状态 ──────────────────────────────────────────────────────────────
  worldMode: WorldMode           // 当前界域：'script'(剧本) | 'broken'(崩坏)
  awakeningLevel: number         // 觉醒值：0~∞（不再限制切换，随时可切换）
  currentScene: GameScene        // 当前场景

  // ── 动作 ──────────────────────────────────────────────────────────────────
  /** 设置界域模式（随时可切换） */
  setWorldMode: (mode: WorldMode) => void
  /** 便捷切换（始终可用） */
  toggleWorldMode: () => void
  /** 增加觉醒值 */
  addAwakening: (delta: number) => void
  /** 切换当前场景 */
  setScene: (scene: GameScene) => void
}

// ─────────────────────────────────────────────────────────────────────────────
// Store 实现
// ─────────────────────────────────────────────────────────────────────────────

export const useGameStore = create<GameState>()(
  persist(
    (set, get) => ({
      // 初始状态
      worldMode: 'script',
      awakeningLevel: 0,
      currentScene: 'chat',

      // ── setWorldMode ──────────────────────────────────────────────────────
      setWorldMode: (mode) => {
        set({ worldMode: mode })
        // 通知 DOM 更新 CSS 变量（驱动双界样式）
        document.body.setAttribute('data-world-mode', mode)
        console.log(`[GameStore] 界域切换 → ${mode}`)
      },

      // ── toggleWorldMode ──────────────────────────────────────────────────
      toggleWorldMode: () => {
        const { worldMode } = get()
        const newMode: WorldMode = worldMode === 'script' ? 'broken' : 'script'
        set({ worldMode: newMode })
        document.body.setAttribute('data-world-mode', newMode)
        console.log(`[GameStore] 界域切换 → ${newMode}`)
      },

      // ── addAwakening ──────────────────────────────────────────────────────
      addAwakening: (delta) => {
        set((state) => ({
          awakeningLevel: Math.max(0, state.awakeningLevel + delta),
        }))
      },

      // ── setScene ──────────────────────────────────────────────────────────
      setScene: (scene) => set({ currentScene: scene }),
    }),
    {
      name: 'ls-game-state',
      partialize: (state) => ({
        worldMode: state.worldMode,
        awakeningLevel: state.awakeningLevel,
      }),
    }
  )
)

// ─────────────────────────────────────────────────────────────────────────────
// 辅助工具（组件外使用）
// ─────────────────────────────────────────────────────────────────────────────

/** 在组件外获取当前 worldMode（不触发订阅） */
export const getWorldMode = () => useGameStore.getState().worldMode
