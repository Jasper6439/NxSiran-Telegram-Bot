// ─────────────────────────────────────────────────────────────────────────────
// 统一导出 + 初始化
// ─────────────────────────────────────────────────────────────────────────────

export { useGameStore, getWorldMode } from './gameStore'
export type { WorldMode, GameScene, GameState } from './gameStore'

export { useFarmStore, CROP_DEFINITIONS } from './farmStore'
export type { CropId, FarmPlot, CropDefinition } from './farmStore'
export { getPlotTextureKey, getAllTextureKeys } from './farmStore'

export { useInventoryStore, SCRIPT_ITEMS, BROKEN_ITEMS, cropToItem } from './inventoryStore'
export type {
  InventoryItem,
  ScriptItemId,
  BrokenItemId,
  AnyItemId,
  ItemDef,
} from './inventoryStore'
