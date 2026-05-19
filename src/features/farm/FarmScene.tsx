import { useEffect, useRef, useState } from 'react'
import Phaser from 'phaser'
import { useGameStore, useFarmStore, useInventoryStore, CROP_DEFINITIONS, type CropId } from '../../stores'
import { farmApi } from '../../api/gameApi'
import { motion, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'

// ─────────────────────────────────────────────────────────────────────────────
// 阶段四核心：Phaser 农场场景
// 单场景订阅 worldMode，setTexture() 瞬切，无 tween
// ─────────────────────────────────────────────────────────────────────────────

// 纹理键名生成规则
function textureKey(cropId: string | null, stage: number, mode: string): string {
  return cropId ? `${cropId}_${stage}_${mode}` : `empty_${mode}`
}

// ─────────────────────────────────────────────────────────────────────────────
// Phaser 游戏配置
// ─────────────────────────────────────────────────────────────────────────────
const GRID = 5
const CELL = 72   // 每个地块像素尺寸
const GAP = 6     // 地块间距
const COLS = GRID
const PADDING = 20
const WIDTH = COLS * CELL + (COLS - 1) * GAP + PADDING * 2
const HEIGHT = GRID * CELL + (GRID - 1) * GAP + PADDING * 2

class FarmPhaserScene extends Phaser.Scene {
  plotSprites: Phaser.GameObjects.Rectangle[] = []
  cropSprites: Phaser.GameObjects.Sprite[] = []
  worldMode: 'script' | 'broken' = 'script'
  plots: ReturnType<typeof useFarmStore.getState>['plots'] = []
  onPlotClick?: (plotId: number) => void

  constructor() {
    super({ key: 'FarmScene' })
  }

  // ── 预生成程序化贴图（无需外部图片资源）─────────────────────────────────
  createTextures() {
    const crops = ['tomato', 'sunflower', 'strawberry']
    const modes = ['script', 'broken']

    modes.forEach((mode) => {
      const isScript = mode === 'script'
      const soilColor = isScript ? 0x8b7355 : 0x555555
      const bgColor = isScript ? 0xfff5ee : 0x2a2a2a

      // 空地块
      const emptyKey = `empty_${mode}`
      if (!this.textures.exists(emptyKey)) {
        const g = this.make.graphics({ x: 0, y: 0 })
        g.fillStyle(bgColor)
        g.fillRoundedRect(0, 0, CELL, CELL, 8)
        g.fillStyle(soilColor)
        g.fillRoundedRect(4, 4, CELL - 8, CELL - 8, 6)
        g.generateTexture(emptyKey, CELL, CELL)
        g.destroy()
      }

      // 作物各阶段
      crops.forEach((crop) => {
        for (let stage = 0; stage <= 3; stage++) {
          const key = `${crop}_${stage}_${mode}`
          if (!this.textures.exists(key)) {
            const g = this.make.graphics({ x: 0, y: 0 })
            g.fillStyle(bgColor)
            g.fillRoundedRect(0, 0, CELL, CELL, 8)
            g.fillStyle(soilColor)
            g.fillRoundedRect(4, 4, CELL - 8, CELL - 8, 6)

            // 阶段颜色
            const stageColors: Record<number, number> = {
              0: isScript ? 0x6b5344 : 0x333333,   // 种子
              1: isScript ? 0x7cb342 : 0x444444,   // 幼苗
              2: isScript ? 0x4caf50 : 0x555555,   // 开花
              3: isScript ? 0xf44336 : 0x888888,   // 成熟
            }
            const cx = CELL / 2, cy = CELL / 2
            g.fillStyle(stageColors[stage])

            // 阶段0-2：圆形标记；阶段3：加粗
            if (stage < 3) {
              g.fillCircle(cx, cy + 6, 10)
            } else {
              g.fillCircle(cx, cy + 4, 16)
              if (isScript) {
                g.fillStyle(0xffffff, 0.3)
                g.fillCircle(cx - 4, cy, 4)
              }
            }

            g.generateTexture(key, CELL, CELL)
            g.destroy()
          }
        }
      })
    })
  }

  create() {
    this.createTextures()
    this.buildGrid()

    // 订阅 worldMode 变化
    const unsubscribe = useGameStore.subscribe((state) => {
      const newMode = state.worldMode as 'script' | 'broken'
      if (newMode !== this.worldMode) {
        this.worldMode = newMode
        this.applyModeVisuals()
      }
    })
    this.worldMode = useGameStore.getState().worldMode

    this.events.on('shutdown', unsubscribe)
  }

  // ── 构建 5x5 地块网格 ───────────────────────────────────────────────────────
  buildGrid() {
    this.plotSprites = []
    this.cropSprites = []

    for (let i = 0; i < GRID * GRID; i++) {
      const col = i % GRID
      const row = Math.floor(i / GRID)
      const x = PADDING + col * (CELL + GAP) + CELL / 2
      const y = PADDING + row * (CELL + GAP) + CELL / 2

      // 地块背景（可点击）
      const bg = this.add.rectangle(x, y, CELL, CELL, 0xffffff)
        .setOrigin(0.5)
        .setInteractive({ useHandCursor: true })
        .on('pointerdown', () => {
          if (this.onPlotClick) this.onPlotClick(i)
        })

      // 作物精灵
      const sprite = this.add.sprite(x, y, 'empty_script').setOrigin(0.5)

      this.plotSprites.push(bg)
      this.cropSprites.push(sprite)
    }

    this.syncPlots()
  }

  // ── 同步地块数据到 Phaser 渲染 ─────────────────────────────────────────────
  syncPlots() {
    const plots = useFarmStore.getState().plots
    this.plots = plots

    plots.forEach((plot, i) => {
      const key = textureKey(plot.cropId, plot.stage, this.worldMode)
      this.cropSprites[i]?.setTexture(key)

      // 高亮浇水状态
      if (plot.watered) {
        this.plotSprites[i]?.setStrokeStyle(2, 0x55efc4)
      } else {
        this.plotSprites[i]?.setStrokeStyle(0)
      }
    })
  }

  // ── 模式切换：全量重绘（瞬切）──────────────────────────────────────────────
  applyModeVisuals() {
    // 重绘所有作物贴图
    this.plots.forEach((plot, i) => {
      const key = textureKey(plot.cropId, plot.stage, this.worldMode)
      this.cropSprites[i]?.setTexture(key)
    })
  }

  // ── 每帧更新（用于动画等） ─────────────────────────────────────────────────
  update() {
    // 可扩展：阶段3作物呼吸动画等
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// React 包装组件
// ─────────────────────────────────────────────────────────────────────────────
type PlantMenuState = {
  visible: boolean
  plotId: number | null
  x: number
  y: number
}

type HarvestResult = {
  visible: boolean
  itemName: string
  emoji: string
  quantity: number
}

export default function FarmScene() {
  const gameRef = useRef<Phaser.Game | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const worldMode = useGameStore((s) => s.worldMode)
  const plots = useFarmStore((s) => s.plots)
  const plant = useFarmStore((s) => s.plant)
  const water = useFarmStore((s) => s.water)
  const harvest = useFarmStore((s) => s.harvest)
  const addItem = useInventoryStore((s) => s.addItem)
  const [plantMenu, setPlantMenu] = useState<PlantMenuState>({ visible: false, plotId: null, x: 0, y: 0 })
  const [harvestResult, setHarvestResult] = useState<HarvestResult>({ visible: false, itemName: '', emoji: '', quantity: 0 })
  const [selectedCrop, setSelectedCrop] = useState<CropId>('tomato')

  // ── 初始化 Phaser ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || gameRef.current) return

    const config: Phaser.Types.Core.GameConfig = {
      type: Phaser.AUTO,
      width: WIDTH,
      height: HEIGHT,
      parent: containerRef.current,
      backgroundColor: worldMode === 'script' ? '#fff5ee' : '#2a2a2a',
      scene: [FarmPhaserScene],
      scale: {
        mode: Phaser.Scale.FIT,
        autoCenter: Phaser.Scale.CENTER_BOTH,
      },
    }

    gameRef.current = new Phaser.Game(config)

    // 注入 plotClick 回调
    const scene = gameRef.current.scene.getScene('FarmScene') as FarmPhaserScene
    scene.onPlotClick = (plotId) => handlePlotClick(plotId)

    return () => {
      gameRef.current?.destroy(true)
      gameRef.current = null
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── 世界模式切换：通知 Phaser ─────────────────────────────────────────────
  useEffect(() => {
    const scene = gameRef.current?.scene.getScene('FarmScene') as FarmPhaserScene | undefined
    if (scene) {
      scene.worldMode = worldMode
      scene.applyModeVisuals()
      // 更新 Phaser 背景色
      gameRef.current?.children[0]?.setBackgroundColor(
        worldMode === 'script' ? '#fff5ee' : '#2a2a2a'
      )
    }
  }, [worldMode])

  // ── 地块点击处理 ──────────────────────────────────────────────────────────
  const handlePlotClick = (plotId: number) => {
    const plot = plots[plotId]
    if (!plot.cropId) {
      // 空地 → 显示种植菜单
      setPlantMenu({ visible: true, plotId, x: plotId % GRID, y: Math.floor(plotId / GRID) })
    } else if (plot.stage === 3) {
      // 成熟 → 收获
      doHarvest(plotId)
    } else if (!plot.watered) {
      // 未浇水 → 浇水
      water(plotId)
      farmApi.action({ action: 'water', plotId }).catch(() => {})
    }
  }

  // ── 种植 ──────────────────────────────────────────────────────────────────
  const doPlant = (cropId: CropId) => {
    if (plantMenu.plotId === null) return
    plant(plantMenu.plotId, cropId)
    farmApi.action({ action: 'plant', plotId: plantMenu.plotId, cropType: cropId }).catch(() => {})
    setPlantMenu({ visible: false, plotId: null, x: 0, y: 0 })
  }

  // ── 收获 ──────────────────────────────────────────────────────────────────
  const doHarvest = (plotId: number) => {
    const result = harvest(plotId)
    if (!result.success) return

    // 发放物品（自动按当前 worldMode 发放）
    addItem(result.cropId!, result.baseYield)
    const { cropToItem } = useInventoryStore.getState()
    // 获取物品名用于显示
    const itemDef = worldMode === 'script'
      ? { tomato: '🍅 爱心番茄', sunflower: '🌻 向阳精华', strawberry: '🍓 甜蜜草莓' }[result.cropId!]
      : { tomato: '💀 崩坏种子', sunflower: '⚫ 虚空精华', strawberry: '🖥️ 乱码碎片' }[result.cropId!]

    const emoji = itemDef?.split(' ')[0] || '✨'
    const name = itemDef?.split(' ').slice(1).join(' ') || '物品'

    setHarvestResult({ visible: true, itemName: name, emoji, quantity: result.baseYield })

    // 通知后端（添加到背包）
    const itemId = worldMode === 'script'
      ? { tomato: 'love_tomato', sunflower: 'sun_essence', strawberry: 'sweet_berry' }[result.cropId!]
      : { tomato: 'corrupted_seed', sunflower: 'void_essence', strawberry: 'glitch_shard' }[result.cropId!]
    inventoryApi.add(itemId, result.baseYield, worldMode).catch(() => {})

    // 通知 Phaser 刷新
    const scene = gameRef.current?.scene.getScene('FarmScene') as FarmPhaserScene | undefined
    if (scene) scene.syncPlots()

    // 3秒后关闭弹窗
    setTimeout(() => setHarvestResult((r) => ({ ...r, visible: false })), 3000)
  }

  // ── 实时同步地块数据到 Phaser ─────────────────────────────────────────────
  useEffect(() => {
    const scene = gameRef.current?.scene.getScene('FarmScene') as Phaser.Scene & { syncPlots: () => void } | undefined
    if (scene?.syncPlots) scene.syncPlots()
  }, [plots])

  const isScript = worldMode === 'script'
  const crops = Object.keys(CROP_DEFINITIONS) as CropId[]

  return (
    <div className="flex flex-col items-center gap-4 relative">
      {/* 农场标题 */}
      <div className="text-center">
        <h2 className="text-xl font-bold mb-1" style={{ color: 'var(--realm-text)' }}>
          {isScript ? '🌸 梦幻农场' : '⚫ 崩坏农场'}
        </h2>
        <p style={{ fontSize: 12, opacity: 0.6 }}>点击空地种植，点击成熟作物收获</p>
      </div>

      {/* Phaser 画布容器 */}
      <div
        ref={containerRef}
        className="rounded-2xl overflow-hidden shadow-xl"
        style={{
          border: '2px solid var(--card-border)',
          backgroundColor: isScript ? '#fff5ee' : '#2a2a2a',
        }}
      />

      {/* 种植菜单弹窗 */}
      <AnimatePresence>
        {plantMenu.visible && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10 p-4 rounded-2xl shadow-2xl"
            style={{
              backgroundColor: 'var(--card-bg)',
              border: '2px solid var(--card-border)',
              minWidth: 220,
            }}
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-bold" style={{ color: 'var(--realm-text)' }}>
                <Sprout size={16} className="inline mr-1" />
                选择作物
              </h3>
              <button onClick={() => setPlantMenu((p) => ({ ...p, visible: false }))}>
                <X size={18} style={{ color: 'var(--realm-text)', opacity: 0.5 }} />
              </button>
            </div>
            <div className="space-y-2">
              {crops.map((cropId) => {
                const def = CROP_DEFINITIONS[cropId]
                return (
                  <button
                    key={cropId}
                    onClick={() => doPlant(cropId)}
                    className="w-full flex items-center gap-3 p-3 rounded-xl transition-all hover:scale-102"
                    style={{ backgroundColor: 'var(--farm-bg)', border: '1px solid var(--farm-grid-line)' }}
                  >
                    <div
                      className="w-10 h-10 rounded-lg flex items-center justify-center text-lg"
                      style={{ backgroundColor: isScript ? '#f44336' : '#555' }}
                    >
                      {cropId === 'tomato' ? '🍅' : cropId === 'sunflower' ? '🌻' : '🍓'}
                    </div>
                    <div className="text-left">
                      <div className="font-medium text-sm" style={{ color: 'var(--realm-text)' }}>
                        {def.nameZh}
                      </div>
                      <div style={{ fontSize: 11, opacity: 0.5 }}>
                        生长: {def.growTime}秒 · 产出 ×{def.baseYield}
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 收获结果弹窗 */}
      <AnimatePresence>
        {harvestResult.visible && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="fixed bottom-24 left-1/2 -translate-x-1/2 z-20 px-6 py-4 rounded-2xl shadow-2xl text-center"
            style={{
              backgroundColor: 'var(--card-bg)',
              border: '2px solid var(--realm-accent)',
              backdropFilter: 'blur(12px)',
            }}
          >
            <div className="text-3xl mb-1">{harvestResult.emoji}</div>
            <div className="font-bold" style={{ color: 'var(--realm-text)' }}>
              收获 {harvestResult.itemName} ×{harvestResult.quantity}
            </div>
            <div style={{ fontSize: 11, opacity: 0.5, marginTop: 2 }}>
              已放入背包
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
