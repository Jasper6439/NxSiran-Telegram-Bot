# 双界穿梭 — 架构设计文档 v1.0

> 基于《LoveSupremacy Universe》项目需求：剧本模式/崩坏模式全局无缝切换，农场双形态适配

---

## 一、核心理念

**双界穿梭**：玩家在"剧本世界"（唯美）与"崩坏世界"（黑白造梦西游风）之间可以随时切换，不丢失进度，农场/背包数据按模式隔离。

- **剧本模式（Script Mode）**：唯美、彩色、马卡龙色系，产出"礼物"道具
- **崩坏模式（Broken Mode）**：黑白、噪点纸张纹理、高对比度，产出"战斗素材"道具
- **切换时机**：觉醒值 ≥ 100 解锁切换，之后随时可切换；觉醒值 < 100 时强制为剧本模式

---

## 二、Zustand Store 完整设计

### 2.1 Store 文件结构

```
src/stores/
├── gameStore.ts          # 游戏核心状态（awakening、worldMode、currentScene）
├── farmStore.ts          # 农场状态（5x5 地块、作物、浇水状态）
├── inventoryStore.ts     # 背包状态（按模式隔离的物品）
└── index.ts              # 统一导出 + 持久化配置
```

### 2.2 gameStore.ts — 游戏核心

```typescript
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// 模式枚举
export type WorldMode = 'script' | 'broken'

// 场景枚举
export type GameScene = 'chat' | 'farm' | 'action'

interface GameState {
  // ── 核心变量 ──
  worldMode: WorldMode          // 当前界域：'script' | 'broken'
  awakeningLevel: number         // 觉醒值：0~∞，≥100 解锁切换
  currentScene: GameScene       // 当前场景
  isModeLocked: boolean         // 切换是否被锁定（<100觉醒值时 true）

  // ── 动作 ──
  setWorldMode: (mode: WorldMode) => void
  toggleWorldMode: () => void   // 便捷切换
  addAwakening: (delta: number) => void
  setScene: (scene: GameScene) => void
  checkAndUnlockMode: () => void // 检查觉醒值，决定是否解锁切换
}

// 自动锁定逻辑：当 awakeningLevel < 100 时强制 script 模式
export const useGameStore = create<GameState>()(
  persist(
    (set, get) => ({
      worldMode: 'script',
      awakeningLevel: 0,
      currentScene: 'chat',
      isModeLocked: true,

      setWorldMode: (mode) => {
        const { isModeLocked } = get()
        if (isModeLocked) {
          console.warn('[GameStore] 切换已锁定，觉醒值需达到100')
          return
        }
        set({ worldMode: mode })
      },

      toggleWorldMode: () => {
        const { worldMode, isModeLocked } = get()
        if (isModeLocked) return
        set({ worldMode: worldMode === 'script' ? 'broken' : 'script' })
      },

      addAwakening: (delta) => {
        set((state) => {
          const newLevel = Math.max(0, state.awakeningLevel + delta)
          return {
            awakeningLevel: newLevel,
            isModeLocked: newLevel < 100,
            // 强制切回剧本模式如果觉醒值不够
            worldMode: newLevel < 100 ? 'script' : state.worldMode,
          }
        })
      },

      setScene: (scene) => set({ currentScene: scene }),

      checkAndUnlockMode: () => {
        const { awakeningLevel } = get()
        if (awakeningLevel >= 100) {
          set({ isModeLocked: false })
        }
      },
    }),
    {
      name: 'ls-game-state',        // localStorage key
      // 只持久化这些字段，避免污染
      partialize: (state) => ({
        worldMode: state.worldMode,
        awakeningLevel: state.awakeningLevel,
      }),
    }
  )
)
```

### 2.3 farmStore.ts — 农场状态（与模式无关的地块数据）

```typescript
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// 作物配置表（模式无关的基础数据）
export const CROP_DEFINITIONS = {
  tomato: {
    id: 'tomato',
    growTime: 30,         // 秒
    baseYield: 3,
  },
  sunflower: {
    id: 'sunflower',
    growTime: 60,
    baseYield: 2,
  },
  strawberry: {
    id: 'strawberry',
    growTime: 45,
    baseYield: 4,
  },
} as const

export type CropId = keyof typeof CROP_DEFINITIONS

// 单个地块
export interface FarmPlot {
  id: number               // 0~24，对应 5x5 网格位置
  cropId: CropId | null    // 作物ID，null = 空地
  plantedAt: number | null // unix timestamp，null = 未种植
  watered: boolean
  stage: number            // 生长阶段 0~3
}

interface FarmState {
  plots: FarmPlot[]         // 固定25个地块，初始化时填充

  // ── 动作 ──
  plant: (plotId: number, cropId: CropId) => void
  water: (plotId: number) => void
  harvest: (plotId: number) => void   // 收获 → 触发 addHarvestedItem
  tickGrowth: () => void              // 每秒调用，根据时间推进生长阶段
  getPlotState: (plotId: number) => FarmPlot
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

      plant: (plotId, cropId) => {
        set((state) => ({
          plots: state.plots.map((p) =>
            p.id === plotId
              ? { ...p, cropId, plantedAt: Date.now(), watered: false, stage: 0 }
              : p
          ),
        }))
      },

      water: (plotId) => {
        set((state) => ({
          plots: state.plots.map((p) =>
            p.id === plotId ? { ...p, watered: true } : p
          ),
        }))
      },

      harvest: (plotId) => {
        const plot = get().plots[plotId]
        if (!plot.cropId || plot.stage < 3) return false

        // 清空地块（等待重新种植）
        set((state) => ({
          plots: state.plots.map((p) =>
            p.id === plotId
              ? { ...p, cropId: null, plantedAt: null, watered: false, stage: 0 }
              : p
          ),
        }))
        return true  // 返回 true 通知调用方发放物品
      },

      tickGrowth: () => {
        const now = Date.now()
        set((state) => ({
          plots: state.plots.map((p) => {
            if (!p.cropId || !p.plantedAt) return p
            const elapsed = (now - p.plantedAt) / 1000
            const growTime = CROP_DEFINITIONS[p.cropId].growTime
            const newStage = Math.min(3, Math.floor((elapsed / growTime) * 4))
            return { ...p, stage: newStage }
          }),
        }))
      },

      getPlotState: (plotId) => get().plots[plotId],
    }),
    { name: 'ls-farm-state' }
  )
)
```

### 2.4 inventoryStore.ts — 背包状态（按模式隔离）

```typescript
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { useGameStore } from './gameStore'

// ── 物品定义（模式决定产出类型）─────────────────────────────────────────────

// 剧本模式物品（礼物系）
export const SCRIPT_ITEMS = {
  love_tomato:    { id: 'love_tomato',    name: '爱心番茄',     type: 'gift', emoji: '🍅' },
  sun_essence:    { id: 'sun_essence',    name: '向阳精华',     type: 'gift', emoji: '🌻' },
  sweet_berry:    { id: 'sweet_berry',    name: '甜蜜草莓',     type: 'gift', emoji: '🍓' },
} as const

// 崩坏模式物品（战斗素材系）
export const BROKEN_ITEMS = {
  corrupted_seed:  { id: 'corrupted_seed',  name: '崩坏种子',   type: 'combat', emoji: '💀' },
  void_essence:    { id: 'void_essence',    name: '虚空精华',   type: 'combat', emoji: '⚫' },
  glitch_shard:    { id: 'glitch_shard',    name: '乱码碎片',   type: 'combat', emoji: '🖥️' },
} as const

export type ScriptItemId = keyof typeof SCRIPT_ITEMS
export type BrokenItemId = keyof typeof BROKEN_ITEMS

// 作物ID → 物品ID 的映射（按模式）
const CROP_TO_ITEM: Record<string, { script: ScriptItemId; broken: BrokenItemId }> = {
  tomato:     { script: 'love_tomato',    broken: 'corrupted_seed' },
  sunflower:  { script: 'sun_essence',    broken: 'void_essence'  },
  strawberry: { script: 'sweet_berry',    broken: 'glitch_shard'  },
}

// ── 物品接口 ──
export interface InventoryItem {
  itemId: string
  quantity: number
}

interface InventoryState {
  scriptInventory: InventoryItem[]
  brokenInventory: InventoryItem[]

  // ── 动作 ──
  addItem: (cropId: CropId, quantity?: number) => void   // 自动根据当前模式发放
  useItem: (itemId: string, quantity?: number) => void
  getCurrentInventory: () => InventoryItem[]
  getItemCount: (itemId: string) => number
}

// 查找物品在背包中的索引（-1 = 不存在）
const findIndex = (inv: InventoryItem[], itemId: string) =>
  inv.findIndex((i) => i.itemId === itemId)

export const useInventoryStore = create<InventoryState>()(
  persist(
    (set, get) => ({
      scriptInventory: [],
      brokenInventory: [],

      addItem: (cropId, quantity = 1) => {
        const worldMode = useGameStore.getState().worldMode
        const mapping = CROP_TO_ITEM[cropId]
        if (!mapping) return

        const itemId = worldMode === 'script' ? mapping.script : mapping.broken
        const inventoryKey = worldMode === 'script' ? 'scriptInventory' : 'brokenInventory'

        set((state) => {
          const inv = [...state[inventoryKey]]
          const idx = findIndex(inv, itemId)
          if (idx >= 0) {
            inv[idx] = { ...inv[idx], quantity: inv[idx].quantity + quantity }
          } else {
            inv.push({ itemId, quantity })
          }
          return { [inventoryKey]: inv }
        })
      },

      useItem: (itemId, quantity = 1) => {
        const worldMode = useGameStore.getState().worldMode
        const inventoryKey = worldMode === 'script' ? 'scriptInventory' : 'brokenInventory'

        set((state) => {
          const inv = [...state[inventoryKey]]
          const idx = findIndex(inv, itemId)
          if (idx < 0) return state
          const newQty = inv[idx].quantity - quantity
          if (newQty <= 0) inv.splice(idx, 1)
          else inv[idx] = { ...inv[idx], quantity: newQty }
          return { [inventoryKey]: inv }
        })
      },

      getCurrentInventory: () => {
        const worldMode = useGameStore.getState().worldMode
        return get()[worldMode === 'script' ? 'scriptInventory' : 'brokenInventory']
      },

      getItemCount: (itemId) => {
        const inv = get().getCurrentInventory()
        return inv.find((i) => i.itemId === itemId)?.quantity ?? 0
      },
    }),
    { name: 'ls-inventory-state' }
  )
)
```

### 2.5 跨文件联动：harvest → addItem

在 FarmScene 的 Phaser 逻辑中，收获时调用：

```typescript
// FarmScene.ts (Phaser)
import { useFarmStore } from '@/stores/farmStore'
import { useInventoryStore } from '@/stores/inventoryStore'
import { useGameStore } from '@/stores/gameStore'

// 在收获逻辑中：
const harvested = farmStore.getState().harvest(plotId)
if (harvested) {
  const cropId = plot.cropId  // 记录作物ID后再清空
  inventoryStore.getState().addItem(cropId, cropDef.baseYield)
}
```

---

## 三、Phaser FarmScene 双形态渲染设计

### 3.1 架构原则

**单一场景 + 模式感知渲染**：不创建两个独立的 FarmScene，而是让 FarmScene 订阅 `worldMode`，模式切换时立即重新渲染受影响的元素。

```typescript
// FarmScene.ts
import Phaser from 'phaser'
import { useGameStore } from '@/stores/gameStore'

export class FarmScene extends Phaser.Scene {
  private plotSprites: Phaser.GameObjects.Sprite[] = []
  private worldMode: WorldMode = 'script'
  private unsubscribe?: () => void

  constructor() {
    super({ key: 'FarmScene' })
  }

  create() {
    // ── 订阅模式切换（Zustand） ──
    this.unsubscribe = useGameStore.subscribe((state) => {
      const newMode = state.worldMode
      if (newMode !== this.worldMode) {
        this.worldMode = newMode
        this.applyModeVisuals()
      }
    })
    this.worldMode = useGameStore.getState().worldMode

    this.buildGrid()
    this.buildUI()
  }

  // ── 核心：模式切换时全量重绘 ─────────────────────────────────────────────
  private applyModeVisuals() {
    const isScript = this.worldMode === 'script'

    // 1. 背景滤镜（CSS 同步）
    const cam = this.cameras.main
    if (isScript) {
      cam.clearFX()                               // 移除黑白滤镜
    } else {
      // 崩坏模式：黑白 + 高对比度
      cam.setBackgroundColor(0x1a1a1a)
      cam.setFXGradient(0, 0, 0, 0) // 预留自定义 shader
    }

    // 2. 重绘所有地块贴图（瞬间切换，无动画）
    this.plotSprites.forEach((sprite, idx) => {
      const plot = useFarmStore.getState().plots[idx]
      const textureKey = this.getPlotTextureKey(plot, isScript)
      sprite.setTexture(textureKey)
    })

    // 3. 更新 UI 文字颜色
    this.updateUIText()

    // 4. 触发全局 CSS 切换（通过 DOM 事件）
    document.body.setAttribute('data-world-mode', this.worldMode)
  }

  // ── 贴图键名规则 ─────────────────────────────────────────────────────────
  // 格式：{cropId}_{stage}_{mode}
  // 示例：tomato_0_script / tomato_3_broken / empty_0_script / empty_0_broken
  private getPlotTextureKey(plot: FarmPlot, isScript: boolean): string {
    const mode = isScript ? 'script' : 'broken'
    if (!plot.cropId) return `empty_0_${mode}`
    return `${plot.cropId}_${plot.stage}_${mode}`
  }

  // ── 预加载：两种模式的贴图都要加载 ───────────────────────────────────────
  preload() {
    const modeAssets = this.getAllTextureKeys()
    modeAssets.forEach(({ key, url }) => {
      if (!this.textures.exists(key)) {
        this.load.image(key, url)
      }
    })
  }

  // ── 预生成策略（避免运行时加载卡顿）───────────────────────────────────────
  // 对于彩色/黑白双版本的作物贴图，建议：
  // - 在 preload 阶段同时加载两套
  // - 运行时直接 setTexture() 切换，零延迟
  private getAllTextureKeys(): { key: string; url: string }[] {
    const crops = ['tomato', 'sunflower', 'strawberry']
    const stages = [0, 1, 2, 3]
    const modes = ['script', 'broken']
    const keys: { key: string; url: string }[] = []

    modes.forEach((mode) => {
      keys.push({ key: `empty_0_${mode}`, url: `/assets/farm/empty_${mode}.png` })
      crops.forEach((crop) => {
        stages.forEach((stage) => {
          keys.push({
            key: `${crop}_${stage}_${mode}`,
            url: `/assets/farm/${crop}_${stage}_${mode}.png`,
          })
        })
      })
    })
    return keys
  }
}
```

### 3.2 CSS 全局样式切换（剧本 ↔ 崩坏）

```css
/* src/index.css — 双界全局样式 */

[data-world-mode="script"] {
  --bg-color: #fdf6f0;
  --text-color: #5c4033;
  --accent-color: #f8a5c2;
  --farm-grid-bg: #fff5ee;
  --farm-soil: #8b7355;
  --crop-highlight: #ff69b4;
  filter: none;
}

[data-world-mode="broken"] {
  --bg-color: #1a1a1a;
  --text-color: #e0e0e0;
  --accent-color: #888;
  --farm-grid-bg: #2a2a2a;
  --farm-soil: #555;
  --crop-highlight: #fff;
  /* 整体黑白滤镜 + 纸张噪点纹理 */
  filter: grayscale(100%) contrast(1.2);
  background-image:
    repeating-linear-gradient(
      0deg,
      transparent,
      transparent 2px,
      rgba(255,255,255,0.03) 2px,
      rgba(255,255,255,0.03) 4px
    );
}

/* 过渡动画：0ms（瞬切）—— 无缝切换要求 */
body,
.farm-container,
.plot-sprite {
  transition: none !important;
}
```

### 3.3 作物贴图命名规范（美术资源）

```
public/assets/farm/
├── empty_script.png          # 空地-剧本模式（彩色草地）
├── empty_broken.png          # 空地-崩坏模式（黑白灰土地）
├── tomato_0_script.png       # 番茄-阶段0（种子）-剧本
├── tomato_0_broken.png       # 番茄-阶段0-崩坏（黑白种子）
├── tomato_1_script.png       # 番茄-阶段1（发芽）
├── tomato_1_broken.png
├── tomato_2_script.png       # 番茄-阶段2（开花）
├── tomato_2_broken.png
├── tomato_3_script.png       # 番茄-阶段3（成熟，红色果实）
├── tomato_3_broken.png       # 番茄-阶段3-崩坏（黑色/灰色果实）
├── sunflower_0~3_script.png
├── sunflower_0~3_broken.png
├── strawberry_0~3_script.png
└── strawberry_0~3_broken.png
```

> **切换时 Phaser 直接 `sprite.setTexture(key)`，无 tween，无等待，用户感知到的是瞬切。**

---

## 四、物品产出差异化对照表

| 作物 | 剧本产出 | 崩坏产出 | 说明 |
|------|----------|----------|------|
| 番茄 | 🍅 爱心番茄（gift）| 💀 崩坏种子（combat）| 礼物→赠送增加好感度 |
| 向日葵 | 🌻 向阳精华（gift）| ⚫ 虚空精华（combat）| 战斗素材→ActionScene回血 |
| 草莓 | 🍓 甜蜜草莓（gift）| 🖥️ 乱码碎片（combat）| 礼物→稀有剧情触发 |

### 背包 UI 差异化展示

```tsx
// FarmHarvestModal.tsx — 收获弹窗
import { useGameStore } from '@/stores/gameStore'
import { useInventoryStore } from '@/stores/inventoryStore'
import { SCRIPT_ITEMS, BROKEN_ITEMS } from '@/stores/inventoryStore'

export const FarmHarvestModal = () => {
  const worldMode = useGameStore((s) => s.worldMode)
  const inventory = useInventoryStore((s) =>
    worldMode === 'script' ? s.scriptInventory : s.brokenInventory
  )
  const itemDefs = worldMode === 'script' ? SCRIPT_ITEMS : BROKEN_ITEMS

  return (
    <div className={`harvest-modal ${worldMode}`}>
      <h3>{worldMode === 'script' ? '🌸 收获礼物' : '⚫ 收获素材'}</h3>
      <div className="item-grid">
        {inventory.map((inv) => {
          const def = itemDefs[inv.itemId as keyof typeof itemDefs]
          return def ? (
            <div key={inv.itemId} className="item-card">
              <span className="emoji">{def.emoji}</span>
              <span className="name">{def.name}</span>
              <span className="qty">×{inv.quantity}</span>
            </div>
          ) : null
        })}
      </div>
    </div>
  )
}
```

---

## 五、模式切换 UI 设计

```tsx
// ModeToggle.tsx — 双界穿梭开关
import { useGameStore } from '@/stores/gameStore'
import { motion, AnimatePresence } from 'framer-motion'

export const ModeToggle = () => {
  const { worldMode, toggleWorldMode, isModeLocked, awakeningLevel } = useGameStore()

  if (isModeLocked) {
    return (
      <div className="mode-lock-badge" title={`觉醒值 ${awakeningLevel}/100 后解锁`}>
        🔒
      </div>
    )
  }

  return (
    <button className={`mode-toggle ${worldMode}`} onClick={toggleWorldMode}>
      <AnimatePresence mode="wait">
        <motion.span
          key={worldMode}
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.8 }}
          transition={{ duration: 0.15 }}
        >
          {worldMode === 'script' ? '🌸' : '⚫'}
        </motion.span>
      </AnimatePresence>
      <span>{worldMode === 'script' ? '剧本' : '崩坏'}</span>
    </button>
  )
}
```

---

## 六、关键设计决策总结

| 决策点 | 方案 | 理由 |
|--------|------|------|
| Store 数量 | 3个独立 store（game/farm/inventory） | 隔离关注点，避免不必要重渲染 |
| 模式状态持久化 | 仅 gameStore 持久化到 localStorage | farm/inventory 由后端管理 |
| FarmScene 渲染 | 单场景订阅模式，setTexture 瞬切 | 避免场景切换动画的卡顿 |
| 物品系统 | 同一作物ID → 不同物品ID（按模式映射表） | 逻辑清晰，不污染数据模型 |
| CSS 切换 | `data-world-mode` 属性 + CSS 变量 | 无需 React 重新渲染 DOM 节点 |
| 过渡动画 | 0ms 瞬切 | 符合"无缝切换"需求 |
| 觉醒值 < 100 | 强制 script 模式，toggle 按钮显示锁 | 符合游戏叙事逻辑 |

---

## 七、实现优先级

1. **gameStore.ts** — 先实现，因为所有其他模块依赖它
2. **CSS 双界变量系统** — 设置好 CSS 变量，UI 框架搭好
3. **ModeToggle 组件** — 可测试模式切换手感
4. **farmStore.ts** — 地块逻辑与模式无关
5. **inventoryStore.ts** — addItem 与 worldMode 联动
6. **FarmScene** — 双形态预加载 + applyModeVisuals
7. **FarmHarvestModal** — 显示差异化物
