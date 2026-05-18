import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { CropId } from './farmStore'
import { useGameStore } from './gameStore'

// ─────────────────────────────────────────────────────────────────────────────
// 物品定义
// ─────────────────────────────────────────────────────────────────────────────

// 剧本模式物品（礼物系）
export const SCRIPT_ITEMS = {
  love_tomato:     { id: 'love_tomato',     name: '爱心番茄',   emoji: '🍅', type: 'gift'   as const },
  sun_essence:     { id: 'sun_essence',     name: '向阳精华',   emoji: '🌻', type: 'gift'   as const },
  sweet_berry:     { id: 'sweet_berry',     name: '甜蜜草莓',   emoji: '🍓', type: 'gift'   as const },
} as const

// 崩坏模式物品（战斗素材系）
export const BROKEN_ITEMS = {
  corrupted_seed:   { id: 'corrupted_seed',  name: '崩坏种子',   emoji: '💀', type: 'combat' as const },
  void_essence:     { id: 'void_essence',    name: '虚空精华',   emoji: '⚫', type: 'combat' as const },
  glitch_shard:     { id: 'glitch_shard',    name: '乱码碎片',   emoji: '🖥️', type: 'combat' as const },
} as const

export type ScriptItemId = keyof typeof SCRIPT_ITEMS
export type BrokenItemId = keyof typeof BROKEN_ITEMS

export type AnyItemId = ScriptItemId | BrokenItemId

export type ItemDef = (typeof SCRIPT_ITEMS)[ScriptItemId] | (typeof BROKEN_ITEMS)[BrokenItemId]

// ─────────────────────────────────────────────────────────────────────────────
// 作物 → 物品映射（按模式）
// ─────────────────────────────────────────────────────────────────────────────

const CROP_TO_ITEM: Record<CropId, { script: ScriptItemId; broken: BrokenItemId }> = {
  tomato:     { script: 'love_tomato',    broken: 'corrupted_seed' },
  sunflower:  { script: 'sun_essence',   broken: 'void_essence'   },
  strawberry: { script: 'sweet_berry',   broken: 'glitch_shard'   },
}

/** 根据作物ID和当前模式获取对应物品ID */
export function cropToItem(cropId: CropId): { script: ScriptItemId; broken: BrokenItemId } {
  return CROP_TO_ITEM[cropId]
}

// ─────────────────────────────────────────────────────────────────────────────
// 类型
// ─────────────────────────────────────────────────────────────────────────────

export interface InventoryItem {
  itemId: string
  quantity: number
}

interface InventoryState {
  scriptInventory: InventoryItem[]
  brokenInventory: InventoryItem[]

  // ── 动作 ──────────────────────────────────────────────────────────────────
  /** 根据当前 worldMode 自动发放对应物品 */
  addItem: (cropId: CropId, quantity?: number) => void
  /** 消耗物品 */
  useItem: (itemId: string, quantity?: number) => void
  /** 获取当前模式对应的背包 */
  getCurrentInventory: () => InventoryItem[]
  /** 获取指定物品数量 */
  getItemCount: (itemId: string) => number
  /** 获取物品定义 */
  getItemDef: (itemId: string) => ItemDef | undefined
  /** 清空背包（调试用） */
  clearInventory: () => void
}

// ─────────────────────────────────────────────────────────────────────────────
// Store
// ─────────────────────────────────────────────────────────────────────────────

const findIdx = (inv: InventoryItem[], itemId: string) =>
  inv.findIndex((i) => i.itemId === itemId)

export const useInventoryStore = create<InventoryState>()(
  persist(
    (set, get) => ({
      scriptInventory: [],
      brokenInventory: [],

      // ── addItem ─────────────────────────────────────────────────────────────
      addItem: (cropId, quantity = 1) => {
        const worldMode = useGameStore.getState().worldMode
        const mapping = CROP_TO_ITEM[cropId]
        if (!mapping) {
          console.warn(`[InventoryStore] 未知的作物ID: ${cropId}`)
          return
        }

        const itemId = worldMode === 'script' ? mapping.script : mapping.broken
        const invKey = worldMode === 'script' ? 'scriptInventory' : 'brokenInventory'

        set((state) => {
          const inv = [...state[invKey]] as InventoryItem[]
          const idx = findIdx(inv, itemId)
          if (idx >= 0) {
            inv[idx] = { ...inv[idx], quantity: inv[idx].quantity + quantity }
          } else {
            inv.push({ itemId, quantity })
          }
          return { [invKey]: inv }
        })
      },

      // ── useItem ─────────────────────────────────────────────────────────────
      useItem: (itemId, quantity = 1) => {
        const worldMode = useGameStore.getState().worldMode
        const invKey = worldMode === 'script' ? 'scriptInventory' : 'brokenInventory'

        set((state) => {
          const inv = [...state[invKey]] as InventoryItem[]
          const idx = findIdx(inv, itemId)
          if (idx < 0) return state
          const newQty = inv[idx].quantity - quantity
          if (newQty <= 0) {
            inv.splice(idx, 1)
          } else {
            inv[idx] = { ...inv[idx], quantity: newQty }
          }
          return { [invKey]: inv }
        })
      },

      // ── getCurrentInventory ─────────────────────────────────────────────────
      getCurrentInventory: () => {
        const worldMode = useGameStore.getState().worldMode
        return get()[worldMode === 'script' ? 'scriptInventory' : 'brokenInventory']
      },

      // ── getItemCount ────────────────────────────────────────────────────────
      getItemCount: (itemId) => {
        const inv = get().getCurrentInventory()
        return inv.find((i) => i.itemId === itemId)?.quantity ?? 0
      },

      // ── getItemDef ──────────────────────────────────────────────────────────
      getItemDef: (itemId) => {
        if (itemId in SCRIPT_ITEMS) return (SCRIPT_ITEMS as Record<string, ItemDef>)[itemId]
        if (itemId in BROKEN_ITEMS) return (BROKEN_ITEMS as Record<string, ItemDef>)[itemId]
        return undefined
      },

      // ── clearInventory ───────────────────────────────────────────────────────
      clearInventory: () => set({ scriptInventory: [], brokenInventory: [] }),
    }),
    { name: 'ls-inventory-state' }
  )
)
