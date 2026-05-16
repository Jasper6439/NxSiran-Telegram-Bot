// ═══════════════════════════════════════════════════════════════════════════
// 恋爱至上主义区域 v1.8 - 双域世界状态管理
// 剧本区（彩色/强制扮演）↔ 空白区（黑白/真实自我）
// ═══════════════════════════════════════════════════════════════════════════
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// ─── 类型定义 ─────────────────────────────────────────────────────────────
export type WorldState = 'SCRIPTED' | 'VOID';

export interface WorldStoreState {
  // 世界状态
  currentWorld: WorldState;
  awakeningLevel: number; // 0-100
  isTransitioning: boolean;

  // 操作
  shiftWorld: (target: WorldState) => void;
  setAwakeningLevel: (level: number) => void;
  boostAwakening: (amount: number) => void;
  setTransitioning: (val: boolean) => void;

  // 计算属性
  getScriptGrayscale: () => string;
  getScriptContrast: () => string;
  getVoidGrayscale: () => string;
  getVoidColorOpacity: () => string;
}

// ─── Store ────────────────────────────────────────────────────────────────
export const useWorldStore = create<WorldStoreState>()(
  persist(
    (set, get) => ({
      currentWorld: 'SCRIPTED',
      awakeningLevel: 0,
      isTransitioning: false,

      shiftWorld: (target) => {
        const current = get().currentWorld;
        if (current === target) return;

        set({ isTransitioning: true });

        // 过渡动画后切换
        setTimeout(() => {
          set({ currentWorld: target, isTransitioning: false });
        }, 800);
      },

      setAwakeningLevel: (level) => {
        set({ awakeningLevel: Math.max(0, Math.min(100, level)) });
      },

      boostAwakening: (amount) => {
        const current = get().awakeningLevel;
        set({ awakeningLevel: Math.max(0, Math.min(100, current + amount)) });
      },

      setTransitioning: (val) => {
        set({ isTransitioning: val });
      },

      // 剧本区：觉醒度越高越灰暗
      getScriptGrayscale: () => {
        const level = get().awakeningLevel;
        return `${Math.min(level * 0.8, 80)}%`;
      },

      getScriptContrast: () => {
        const level = get().awakeningLevel;
        return `${1 + level * 0.01}`;
      },

      // 空白区：觉醒度越高越绚烂
      getVoidGrayscale: () => {
        const level = get().awakeningLevel;
        return `${Math.max(0, 100 - level * 1.2)}%`;
      },

      getVoidColorOpacity: () => {
        const level = get().awakeningLevel;
        return `${Math.min(1, level / 80)}`;
      },
    }),
    {
      name: 'lovesupremacy-world-storage',
      partialize: (state) => ({
        currentWorld: state.currentWorld,
        awakeningLevel: state.awakeningLevel,
      }),
    }
  )
);
