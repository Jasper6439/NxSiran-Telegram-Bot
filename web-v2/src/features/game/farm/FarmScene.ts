// ═══════════════════════════════════════════════════════════════════════════
// LoveSupremacy Universe - Mirror Farm Phaser Scene
// Dual-world farm with programmatic graphics (zero external assets)
// ═══════════════════════════════════════════════════════════════════════════
import Phaser from 'phaser';
import type { FarmPlot, InventoryItem } from '../../../stores/worldStore';

// ─── Constants ────────────────────────────────────────────────────────────

const GRID_COLS = 5;
const GRID_ROWS = 5;
const GROWTH_INTERVAL = 30_000; // 30 seconds per growth stage
const PLOT_SIZE = 80;
const PLOT_GAP = 8;

// ─── Theme Palettes ───────────────────────────────────────────────────────

interface WorldTheme {
  soil: number;
  soilStroke: number;
  bgTop: number;
  bgBottom: number;
  sprout: number;
  growing: number;
  mature: number;
  water: number;
  waterAlt: number;
  text: number;
  empty: number;
  emptyHover: number;
}

const SCRIPTED_THEME: WorldTheme = {
  soil: 0xc4a882,
  soilStroke: 0xb09060,
  bgTop: 0xd4edda,
  bgBottom: 0x87ceeb,
  sprout: 0x6bcf7f,
  growing: 0xf0c040,
  mature: 0xe74c3c,
  water: 0xff69b4,
  waterAlt: 0xff1493,
  text: 0x3a3a3a,
  empty: 0xe8dcc8,
  emptyHover: 0xd4c8a8,
};

const VOID_THEME: WorldTheme = {
  soil: 0x2a2a2a,
  soilStroke: 0x1a1a1a,
  bgTop: 0x1a1a1a,
  bgBottom: 0x0a0a0a,
  sprout: 0x555555,
  growing: 0x333333,
  mature: 0x8b00ff,
  water: 0xff0000,
  waterAlt: 0xcc0000,
  text: 0xaaaaaa,
  empty: 0x222222,
  emptyHover: 0x333333,
};

// ─── Types ────────────────────────────────────────────────────────────────

interface PlotCell {
  plotId: string;
  col: number;
  row: number;
  x: number;
  y: number;
  growthStage: number;
  isWatered: boolean;
  cropType: string | null;
  graphics: Phaser.GameObjects.Graphics;
  waterGraphics: Phaser.GameObjects.Graphics;
  cropGraphics: Phaser.GameObjects.Graphics;
  hitZone: Phaser.GameObjects.Zone;
}

// ─── Farm Scene ───────────────────────────────────────────────────────────

export default class FarmScene extends Phaser.Scene {
  private isAwakened = false;
  private theme: WorldTheme = SCRIPTED_THEME;
  private plots: PlotCell[] = [];
  private bgGraphics!: Phaser.GameObjects.Graphics;
  private growthTimer?: Phaser.Time.TimerEvent;
  private seedMenuOpen = false;

  // Callbacks set from React via registry
  private onAddToInventory: ((item: InventoryItem) => void) | null = null;
  private onUpdateFarmPlot: ((plotId: string, update: Partial<FarmPlot>) => void) | null = null;
  private onGetFarmPlots: (() => FarmPlot[]) | null = null;

  constructor() {
    super({ key: 'FarmScene' });
  }

  // ── Lifecycle ─────────────────────────────────────────────────────────

  create(): void {
    // Read callbacks from registry (set by React hook)
    this.onAddToInventory = this.registry.get('onAddToInventory') ?? null;
    this.onUpdateFarmPlot = this.registry.get('onUpdateFarmPlot') ?? null;
    this.onGetFarmPlots = this.registry.get('onGetFarmPlots') ?? null;
    this.isAwakened = this.registry.get('isAwakened') ?? false;
    this.theme = this.isAwakened ? VOID_THEME : SCRIPTED_THEME;

    // Background
    this.bgGraphics = this.add.graphics();
    this.drawBackground();

    // Build grid
    this.buildGrid();

    // Auto-growth timer
    this.growthTimer = this.time.addEvent({
      delay: GROWTH_INTERVAL,
      callback: this.advanceGrowth,
      callbackScope: this,
      loop: true,
    });

    // Water animation loop
    this.time.addEvent({
      delay: 600,
      callback: this.animateWater,
      callbackScope: this,
      loop: true,
    });

    // Listen for world change events from React
    this.game.events.on('worldChanged', this.handleWorldChanged, this);

    // Handle resize
    this.scale.on('resize', this.handleResize, this);
  }

  update(): void {
    // Lightweight - animations handled by timers
  }

  shutdown(): void {
    this.game.events.off('worldChanged', this.handleWorldChanged, this);
    this.scale.off('resize', this.handleResize, this);
    this.growthTimer?.destroy();
  }

  // ── World Switching ───────────────────────────────────────────────────

  private handleWorldChanged(): void {
    this.isAwakened = this.registry.get('isAwakened') ?? false;
    this.theme = this.isAwakened ? VOID_THEME : SCRIPTED_THEME;
    this.drawBackground();
    this.rebuildAllPlots();
  }

  private handleResize(): void {
    this.drawBackground();
    this.repositionGrid();
    this.rebuildAllPlots();
  }

  // ── Background ────────────────────────────────────────────────────────

  private drawBackground(): void {
    const g = this.bgGraphics;
    g.clear();
    const w = this.scale.width;
    const h = this.scale.height;

    // Gradient fill using horizontal strips
    const steps = 32;
    for (let i = 0; i < steps; i++) {
      const t = i / steps;
      const color = Phaser.Display.Color.Interpolate.ColorWithColor(
        Phaser.Display.Color.IntegerToColor(this.theme.bgTop),
        Phaser.Display.Color.IntegerToColor(this.theme.bgBottom),
        steps,
        i
      );
      const c = Phaser.Display.Color.GetColor(color.r, color.g, color.b);
      g.fillStyle(c, 1);
      g.fillRect(0, Math.floor(h * t), w, Math.ceil(h / steps) + 1);
    }
  }

  // ── Grid ──────────────────────────────────────────────────────────────

  private buildGrid(): void {
    const farmPlots = this.onGetFarmPlots?.() ?? [];
    const totalW = GRID_COLS * (PLOT_SIZE + PLOT_GAP) - PLOT_GAP;
    const totalH = GRID_ROWS * (PLOT_SIZE + PLOT_GAP) - PLOT_GAP;
    const offsetX = (this.scale.width - totalW) / 2;
    const offsetY = (this.scale.height - totalH) / 2 + 20;

    for (let row = 0; row < GRID_ROWS; row++) {
      for (let col = 0; col < GRID_COLS; col++) {
        const idx = row * GRID_COLS + col;
        const plotId = farmPlots[idx]?.plot_id ?? `plot_${idx}`;
        const x = offsetX + col * (PLOT_SIZE + PLOT_GAP);
        const y = offsetY + row * (PLOT_SIZE + PLOT_GAP);

        const graphics = this.add.graphics();
        const waterGraphics = this.add.graphics();
        const cropGraphics = this.add.graphics();

        const hitZone = this.add.zone(x + PLOT_SIZE / 2, y + PLOT_SIZE / 2, PLOT_SIZE, PLOT_SIZE)
          .setInteractive({ useHandCursor: true });

        const plotData = farmPlots[idx];
        const cell: PlotCell = {
          plotId,
          col,
          row,
          x,
          y,
          growthStage: plotData?.growth_stage ?? 0,
          isWatered: plotData?.is_watered ?? false,
          cropType: plotData?.crop_type ?? null,
          graphics,
          waterGraphics,
          cropGraphics,
          hitZone,
        };

        hitZone.on('pointerdown', () => this.onPlotClick(idx));
        hitZone.on('pointerover', () => this.onPlotHover(idx, true));
        hitZone.on('pointerout', () => this.onPlotHover(idx, false));

        this.plots.push(cell);
        this.drawPlot(idx);
      }
    }
  }

  private repositionGrid(): void {
    const totalW = GRID_COLS * (PLOT_SIZE + PLOT_GAP) - PLOT_GAP;
    const totalH = GRID_ROWS * (PLOT_SIZE + PLOT_GAP) - PLOT_GAP;
    const offsetX = (this.scale.width - totalW) / 2;
    const offsetY = (this.scale.height - totalH) / 2 + 20;

    for (const cell of this.plots) {
      cell.x = offsetX + cell.col * (PLOT_SIZE + PLOT_GAP);
      cell.y = offsetY + cell.row * (PLOT_SIZE + PLOT_GAP);
      cell.hitZone.setPosition(cell.x + PLOT_SIZE / 2, cell.y + PLOT_SIZE / 2);
    }
  }

  private rebuildAllPlots(): void {
    for (let i = 0; i < this.plots.length; i++) {
      this.drawPlot(i);
    }
  }

  // ── Plot Drawing ──────────────────────────────────────────────────────

  private drawPlot(idx: number): void {
    const cell = this.plots[idx];
    if (!cell) return;
    const { x, y, graphics, waterGraphics, cropGraphics, growthStage, isWatered, cropType } = cell;
    const t = this.theme;

    // Soil
    graphics.clear();
    const fillColor = cropType ? t.soil : t.empty;
    graphics.fillStyle(fillColor, 1);
    graphics.lineStyle(2, t.soilStroke, 1);

    if (this.isAwakened) {
      // Jagged edges for void soil
      this.drawJaggedRect(graphics, x, y, PLOT_SIZE, PLOT_SIZE, 4);
    } else {
      // Rounded corners for scripted soil
      graphics.fillRoundedRect(x, y, PLOT_SIZE, PLOT_SIZE, 8);
      graphics.strokeRoundedRect(x, y, PLOT_SIZE, PLOT_SIZE, 8);
    }

    // Crop
    cropGraphics.clear();
    if (cropType && growthStage > 0) {
      this.drawCrop(cropGraphics, x + PLOT_SIZE / 2, y + PLOT_SIZE / 2, growthStage);
    }

    // Water indicator
    waterGraphics.clear();
    if (isWatered && cropType) {
      this.drawWaterDroplet(waterGraphics, x + PLOT_SIZE - 14, y + 10);
    }
  }

  private drawJaggedRect(g: Phaser.GameObjects.Graphics, x: number, y: number, w: number, h: number, jag: number): void {
    g.beginPath();
    g.moveTo(x + jag + Math.random() * 2, y);
    g.lineTo(x + w - jag - Math.random() * 2, y);
    g.lineTo(x + w, y + jag + Math.random() * 2);
    g.lineTo(x + w, y + h - jag - Math.random() * 2);
    g.lineTo(x + w - jag - Math.random() * 2, y + h);
    g.lineTo(x + jag + Math.random() * 2, y + h);
    g.lineTo(x, y + h - jag - Math.random() * 2);
    g.lineTo(x, y + jag + Math.random() * 2);
    g.closePath();
    g.fillPath();
    g.strokePath();
  }

  private drawCrop(g: Phaser.GameObjects.Graphics, cx: number, cy: number, stage: number): void {
    const t = this.theme;

    if (stage === 1) {
      // Sprout: small stem + leaf
      g.fillStyle(t.sprout, 1);
      g.fillRect(cx - 2, cy + 8, 4, -18);
      g.fillCircle(cx + 6, cy - 6, 6);
      g.fillCircle(cx - 5, cy - 2, 5);
    } else if (stage === 2) {
      // Growing: taller stem + multiple leaves
      g.fillStyle(t.sprout, 1);
      g.fillRect(cx - 2, cy + 12, 4, -26);
      g.fillCircle(cx + 8, cy - 10, 7);
      g.fillCircle(cx - 7, cy - 4, 6);
      g.fillCircle(cx + 3, cy - 16, 5);
      // Flower bud
      g.fillStyle(t.growing, 1);
      g.fillCircle(cx, cy - 22, 6);
    } else if (stage >= 3) {
      // Mature: full plant with fruit/crystal
      g.fillStyle(t.sprout, 1);
      g.fillRect(cx - 3, cy + 14, 6, -30);
      g.fillCircle(cx + 10, cy - 12, 8);
      g.fillCircle(cx - 9, cy - 6, 7);
      g.fillCircle(cx + 4, cy - 20, 6);
      // Fruit / Crystal
      g.fillStyle(t.mature, 1);
      if (this.isAwakened) {
        // Crystal shape (diamond)
        g.fillTriangle(cx, cy - 34, cx - 8, cy - 24, cx + 8, cy - 24);
        g.fillTriangle(cx, cy - 14, cx - 8, cy - 24, cx + 8, cy - 24);
        // Glow
        g.lineStyle(1, t.mature, 0.4);
        g.strokeCircle(cx, cy - 24, 14);
      } else {
        // Round fruit
        g.fillCircle(cx, cy - 26, 10);
        g.fillStyle(0xffffff, 0.3);
        g.fillCircle(cx - 3, cy - 29, 3);
      }
    }
  }

  private drawWaterDroplet(g: Phaser.GameObjects.Graphics, x: number, y: number): void {
    const t = this.theme;
    g.fillStyle(t.water, 0.8);
    // Teardrop shape
    g.beginPath();
    g.moveTo(x, y - 6);
    g.lineTo(x + 5, y + 2);
    g.lineTo(x + 3, y + 5);
    g.lineTo(x - 3, y + 5);
    g.lineTo(x - 5, y + 2);
    g.closePath();
    g.fillPath();
  }

  // ── Water Animation ───────────────────────────────────────────────────

  private animateWater(): void {
    const t = this.theme;
    for (const cell of this.plots) {
      if (!cell.isWatered || !cell.cropType) continue;

      if (this.isAwakened) {
        // Void: red glitch lines
        cell.waterGraphics.clear();
        cell.waterGraphics.lineStyle(1, t.water, 0.5 + Math.random() * 0.5);
        const lx = cell.x + Math.random() * PLOT_SIZE;
        const ly = cell.y + Math.random() * PLOT_SIZE;
        cell.waterGraphics.lineBetween(lx, ly, lx + 10 + Math.random() * 20, ly + Math.random() * 4);
      } else {
        // Scripted: pink sparkles
        cell.waterGraphics.clear();
        cell.waterGraphics.fillStyle(t.water, 0.4 + Math.random() * 0.4);
        const sx = cell.x + 5 + Math.random() * (PLOT_SIZE - 10);
        const sy = cell.y + 5 + Math.random() * (PLOT_SIZE - 10);
        cell.waterGraphics.fillCircle(sx, sy, 1 + Math.random() * 2);
      }
    }
  }

  // ── Growth ────────────────────────────────────────────────────────────

  private advanceGrowth(): void {
    for (let i = 0; i < this.plots.length; i++) {
      const cell = this.plots[i];
      if (cell.cropType && cell.growthStage < 3 && cell.isWatered) {
        cell.growthStage++;
        this.onUpdateFarmPlot?.(cell.plotId, { growth_stage: cell.growthStage });
        this.drawPlot(i);
      }
    }
  }

  // ── Interaction ───────────────────────────────────────────────────────

  private onPlotHover(idx: number, isOver: boolean): void {
    const cell = this.plots[idx];
    if (!cell || cell.cropType) return;
    const t = this.theme;
    cell.graphics.clear();
    cell.graphics.fillStyle(isOver ? t.emptyHover : t.empty, 1);
    cell.graphics.lineStyle(2, t.soilStroke, 1);
    if (this.isAwakened) {
      this.drawJaggedRect(cell.graphics, cell.x, cell.y, PLOT_SIZE, PLOT_SIZE, 4);
    } else {
      cell.graphics.fillRoundedRect(cell.x, cell.y, PLOT_SIZE, PLOT_SIZE, 8);
      cell.graphics.strokeRoundedRect(cell.x, cell.y, PLOT_SIZE, PLOT_SIZE, 8);
    }
    // "+" indicator on hover
    if (isOver) {
      cell.graphics.fillStyle(t.text, 0.4);
      cell.graphics.fillCircle(cell.x + PLOT_SIZE / 2, cell.y + PLOT_SIZE / 2, 14);
      cell.graphics.lineStyle(2, t.text, 0.7);
      cell.graphics.lineBetween(cell.x + PLOT_SIZE / 2 - 6, cell.y + PLOT_SIZE / 2, cell.x + PLOT_SIZE / 2 + 6, cell.y + PLOT_SIZE / 2);
      cell.graphics.lineBetween(cell.x + PLOT_SIZE / 2, cell.y + PLOT_SIZE / 2 - 6, cell.x + PLOT_SIZE / 2, cell.y + PLOT_SIZE / 2 + 6);
    }
  }

  private onPlotClick(idx: number): void {
    const cell = this.plots[idx];
    if (!cell) return;

    if (this.seedMenuOpen) return;

    if (!cell.cropType) {
      // Empty plot -> show seed selection
      this.showSeedMenu(idx);
    } else if (cell.growthStage >= 3) {
      // Mature -> harvest
      this.harvestPlot(idx);
    } else if (!cell.isWatered) {
      // Growing -> water
      this.waterPlot(idx);
    }
    // If watered but not mature, do nothing (waiting for growth)
  }

  private showSeedMenu(idx: number): void {
    this.seedMenuOpen = true;

    // Create a DOM element for the seed menu
    const menuContainer = document.createElement('div');
    menuContainer.style.cssText = `
      position: fixed;
      left: 50%;
      top: 50%;
      transform: translate(-50%, -50%);
      z-index: 10000;
      display: flex;
      flex-direction: column;
      gap: 8px;
      padding: 16px;
      border-radius: 12px;
      background: ${this.isAwakened ? '#1a1a1a' : '#fdfbf7'};
      border: 2px solid ${this.isAwakened ? '#555' : '#c4a882'};
      box-shadow: 0 8px 32px rgba(0,0,0,0.3);
      font-family: system-ui, sans-serif;
    `;

    const title = document.createElement('div');
    title.textContent = this.isAwakened ? 'Select Seed' : 'Select Seed';
    title.style.cssText = `
      font-size: 14px;
      font-weight: 600;
      color: ${this.isAwakened ? '#aaa' : '#3a3a3a'};
      text-align: center;
      margin-bottom: 4px;
    `;
    menuContainer.appendChild(title);

    const seedTypes = this.isAwakened
      ? [{ id: 'void_seed', label: 'Void Seed', color: '#8b00ff' }]
      : [{ id: 'tomato_seed', label: 'Tomato Seed', color: '#e74c3c' }];

    for (const seed of seedTypes) {
      const btn = document.createElement('button');
      btn.textContent = seed.label;
      btn.style.cssText = `
        padding: 10px 24px;
        border: none;
        border-radius: 8px;
        background: ${seed.color};
        color: white;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: opacity 0.2s;
      `;
      btn.addEventListener('mouseenter', () => { btn.style.opacity = '0.8'; });
      btn.addEventListener('mouseleave', () => { btn.style.opacity = '1'; });
      btn.addEventListener('click', () => {
        this.plantSeed(idx, seed.id);
        document.body.removeChild(menuContainer);
        this.seedMenuOpen = false;
      });
      menuContainer.appendChild(btn);
    }

    // Cancel button
    const cancelBtn = document.createElement('button');
    cancelBtn.textContent = 'Cancel';
    cancelBtn.style.cssText = `
      padding: 8px 24px;
      border: 1px solid ${this.isAwakened ? '#555' : '#ccc'};
      border-radius: 8px;
      background: transparent;
      color: ${this.isAwakened ? '#aaa' : '#666'};
      font-size: 13px;
      cursor: pointer;
      margin-top: 4px;
    `;
    cancelBtn.addEventListener('click', () => {
      document.body.removeChild(menuContainer);
      this.seedMenuOpen = false;
    });
    menuContainer.appendChild(cancelBtn);

    // Click outside to close
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;z-index:9999;';
    overlay.addEventListener('click', () => {
      if (document.body.contains(menuContainer)) {
        document.body.removeChild(menuContainer);
      }
      if (document.body.contains(overlay)) {
        document.body.removeChild(overlay);
      }
      this.seedMenuOpen = false;
    });

    document.body.appendChild(overlay);
    document.body.appendChild(menuContainer);
  }

  private plantSeed(idx: number, cropType: string): void {
    const cell = this.plots[idx];
    if (!cell) return;

    cell.cropType = cropType;
    cell.growthStage = 0;
    cell.isWatered = false;

    this.onUpdateFarmPlot?.(cell.plotId, {
      crop_type: cropType,
      growth_stage: 0,
      is_watered: false,
      planted_at: new Date().toISOString(),
    });

    this.drawPlot(idx);
  }

  private waterPlot(idx: number): void {
    const cell = this.plots[idx];
    if (!cell || !cell.cropType) return;

    cell.isWatered = true;
    this.onUpdateFarmPlot?.(cell.plotId, { is_watered: true });
    this.drawPlot(idx);
  }

  private harvestPlot(idx: number): void {
    const cell = this.plots[idx];
    if (!cell || cell.growthStage < 3) return;

    const item: InventoryItem = this.isAwakened
      ? { item_type: 'material', item_id: 'awakening_fragment', quantity: 1, quality: 80 }
      : { item_type: 'gift', item_id: 'perfect_tomato', quantity: 1, quality: 90 };

    this.onAddToInventory?.(item);

    // Reset plot
    cell.cropType = null;
    cell.growthStage = 0;
    cell.isWatered = false;

    this.onUpdateFarmPlot?.(cell.plotId, {
      crop_type: null,
      growth_stage: 0,
      is_watered: false,
      planted_at: null,
    });

    this.drawPlot(idx);

    // Show harvest feedback
    this.showHarvestFeedback(cell.x + PLOT_SIZE / 2, cell.y + PLOT_SIZE / 2, item);
  }

  private showHarvestFeedback(x: number, y: number, _item: InventoryItem): void {
    const t = this.theme;
    const label = this.isAwakened ? '+1 Fragment' : '+1 Tomato';

    const text = this.add.text(x, y - 20, label, {
      fontSize: '16px',
      fontFamily: 'system-ui, sans-serif',
      color: Phaser.Display.Color.IntegerToColor(t.mature).rgba,
      fontStyle: 'bold',
    }).setOrigin(0.5);

    // Float up and fade
    this.tweens.add({
      targets: text,
      y: y - 60,
      alpha: 0,
      duration: 1200,
      ease: 'Power2',
      onComplete: () => text.destroy(),
    });
  }
}
