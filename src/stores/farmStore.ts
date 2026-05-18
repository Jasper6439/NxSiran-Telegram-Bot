import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// ─────────────────────────────────────────────────────────────────────────────
// 类型 & 常量
// ─────────────────────────────────────────────────────────────────────────────

export type CropId = 'tomato' | 'sunflower' | 'strawberry'

export interface CropDefinition {
  id: CropId
  name: string
  nameZh: string
  growTime: number   // 生长总时长（秒）
  baseYield: number   // 基础产出数量
  stages: 4           // 固定4个生长阶段（种子→发芽→开花→成熟）
}

export const CROP_DEFINITIONS: Record<CropId, CropDefinition> = {
  tomato: {
    id: 'tomato',
    name: 'tomato',
    nameZh: '番茄',
    growTime: 30,
    baseYield: 3,
    stages: 4,
  },
  sunflower: {
    id: 'sunflower',
    name: 'sunflower',
    nameZh: '向日葵',
    growTime: 60,
    baseYield: 2,
    stages: 4,
  },
  strawberry: {
    id: 'strawberry',
    name: 'strawberry',
    nameZh: '草莓',
    growTime: 45,
    baseYield: 4,
    stages: 4,
  },
}

// 单个地块
export interface FarmPlot {
  id: number                     // 0~24，对应 5x5 网格
  cropId: CropId | null          // 作物ID，null = 空地
  plantedAt: number | null       // unix ms，null = 未种植
  watered: boolean               // 是否已浇水
  stage: 0 | 1 | 2 | 3           // 生长阶段：0=种子 1=发芽 2=开花 3=成熟
}

// ─────────────────────────────────────────────────────────────────────────────
// Store
// ─────────────────────────────────────────────────────────────────────────────

interface FarmState {
  plots: FarmPlot[]   // 固定25个地块

  // ── 动作 ──────────────────────────────────────────────────────────────────
  plant: (plotId: number, cropId: CropId) => void
  water: (plotId: number) => void
  harvest: (plotId: number) => { success: boolean; cropId: CropId | null; baseYield: number }
  tickGrowth: () => void
  resetPlot: (plotId: number) => void
  getPlot: (plotId: number) => FarmPlot
  getMaturePlots: () => FarmPlot[]
}

const createEmptyPlots = (): FarmPlot[] =>
  Array.from({ length: 25 }, (_, i) => ({
    id: i,
    cropId: null,
    plantedAt: null,
    watered: false,
    stage: 0,
  }))

export const useFarmStore = create<FarmState>()(
  persist(
    (set, get) => ({
      plots: createEmptyPlots(),

      // ── plant ──────────────────────────────────────────────────────────────
      plant: (plotId, cropId) => {
        set((state) => ({
          plots: state.plots.map((p) =>
            p.id === plotId
              ? { ...p, cropId, plantedAt: Date.now(), watered: false, stage: 0 }
              : p
          ),
        }))
      },

      // ── water ─────────────────────────────────────────────────────────────
      water: (plotId) => {
        set((state) => ({
          plots: state.plots.map((p) =>
            p.id === plotId ? { ...p, watered: true } : p
          ),
        }))
      },

      // ── harvest ────────────────────────────────────────────────────────────
      harvest: (plotId) => {
        const plot = get().plots[plotId]
        if (!plot.cropId || plot.stage < 3) {
          return { success: false, cropId: null, baseYield: 0 }
        }
        const cropId = plot.cropId
        const baseYield = CROP_DEFINITIONS[cropId].baseYield

        set((state) => ({
          plots: state.plots.map((p) =>
            p.id === plotId
              ? { ...p, cropId: null, plantedAt: null, watered: false, stage: 0 }
              : p
          ),
        }))

        return { success: true, cropId, baseYield }
      },

      // ── tickGrowth ─────────────────────────────────────────────────────────
      // 由外部 game loop 每秒调用一次
      tickGrowth: () => {
        const now = Date.now()
        set((state) => ({
          plots: state.plots.map((p) => {
            if (!p.cropId || !p.plantedAt) return p
            const elapsed = (now - p.plantedAt) / 1000
            const growTime = CROP_DEFINITIONS[p.cropId].growTime
            const newStage = Math.min(3, Math.floor((elapsed / growTime) * 4)) as 0 | 1 | 2 | 3
            return { ...p, stage: newStage }
          }),
        }))
      },

      // ── resetPlot ──────────────────────────────────────────────────────────
      resetPlot: (plotId) => {
        set((state) => ({
          plots: state.plots.map((p) =>
            p.id === plotId
              ? { ...p, cropId: null, plantedAt: null, watered: false, stage: 0 }
              : p
          ),
        }))
      },

      // ── getPlot ─────────────────────────────────────────────────────────────
      getPlot: (plotId) => get().plots[plotId],

      // ── getMaturePlots ─────────────────────────────────────────────────────
      getMaturePlots: () => get().plots.filter((p) => p.cropId !== null && p.stage === 3),
    }),
    { name: 'ls-farm-state' }
  )
)

// ─────────────────────────────────────────────────────────────────────────────
// 辅助：Phaser 纹理键名生成（供 FarmScene 调用）
// ─────────────────────────────────────────────────────────────────────────────

/**
 * 生成 Phaser 纹理键名
 * 格式：{cropId}_{stage}_{mode}
 * 示例：tomato_3_script / strawberry_0_broken / empty_0_script
 */
export function getPlotTextureKey(plot: FarmPlot, mode: 'script' | 'broken'): string {
  const modeSuffix = mode
  if (!plot.cropId) return `empty_0_${modeSuffix}`
  return `${plot.cropId}_${plot.stage}_${modeSuffix}`
}

/**
 * 预生成所有需要的纹理键名（用于 Phaser preload）
 */
export function getAllTextureKeys(): string[] {
  const crops = Object.keys(CROP_DEFINITIONS) as CropId[]
  const stages = [0, 1, 2, 3] as const
  const modes = ['script', 'broken'] as const
  const keys: string[] = []

  modes.forEach((mode) => {
    keys.push(`empty_0_${mode}`)
    crops.forEach((crop) => {
      stages.forEach((stage) => {
        keys.push(`${crop}_${stage}_${mode}`)
      })
    })
  })

  return keys
}
