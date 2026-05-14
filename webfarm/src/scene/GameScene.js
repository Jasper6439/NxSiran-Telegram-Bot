/**
 * GameScene.js - Phaser 3 游戏主场景
 * 
 * v1.5.5 优化：
 * - HUD 风格 UI（圆角、阴影、半透明）
 * - 光标反馈：悬停显示操作图标
 * - 呼吸动画：作物轻微起伏
 * - 成熟闪光特效
 * - 16:9 适配布局
 */

class GameScene extends Phaser.Scene {
    constructor() {
        super({ key: 'GameScene' });
        
        this.farmModel = null;
        this.plotSprites = [];
        this.selectedTool = 'hoe';
        this.selectedCrop = 'corn';
        this.goldText = null;
        this.cursorIcon = null;
        this.tooltipBg = null;
        this.tooltipText = null;
        this.W = 720;  // 设计宽度
        this.H = 405;  // 设计高度
    }

    create() {
        this.farmModel = new FarmModel();
        this.farmModel.addListener(this.onModelUpdate.bind(this));
        
        this.loadGameData();
        this.drawBackground();
        this.drawPlotGrid();
        this.createHUD();
        this.setupCursor();
        this.setupInput();
        
        // 每秒更新生长
        this.time.addEvent({
            delay: 1000,
            callback: this.updateGrowth,
            callbackScope: this,
            loop: true
        });
        
        // 呼吸动画循环
        this.time.addEvent({
            delay: 2000,
            callback: this.breatheCrops,
            callbackScope: this,
            loop: true
        });
    }

    // ============== 背景 ==============
    drawBackground() {
        const bg = this.add.graphics();
        // 渐变草地
        bg.fillGradientStyle(0x5a8e32, 0x5a8e32, 0x3d6b22, 0x3d6b22, 1);
        bg.fillRect(0, 0, this.W, this.H);
        
        // 草地纹理点缀
        for (let i = 0; i < 80; i++) {
            const x = Phaser.Math.Between(0, this.W);
            const y = Phaser.Math.Between(0, this.H);
            bg.fillStyle(Phaser.Math.Between(0x4a7a2e, 0x6a9e42), 0.4);
            bg.fillCircle(x, y, Phaser.Math.Between(1, 4));
        }
        
        // 装饰：小路
        bg.fillStyle(0x8B7355, 0.3);
        bg.fillRect(this.W / 2 - 15, this.H * 0.55, 30, this.H * 0.45);
        
        // 装饰：栅栏（顶部）
        bg.lineStyle(3, 0x6B4226, 0.6);
        bg.strokeRect(10, 8, this.W - 20, 4);
        for (let x = 30; x < this.W - 20; x += 40) {
            bg.fillStyle(0x6B4226, 0.5);
            bg.fillRect(x - 2, 2, 4, 16);
        }
    }

    // ============== 地块网格 ==============
    drawPlotGrid() {
        const gridSize = 5;
        const plotSize = 52;
        const gap = 6;
        const gridW = gridSize * plotSize + (gridSize - 1) * gap;
        const gridH = gridW;
        const startX = (this.W - gridW) / 2;
        const startY = 35;
        
        this.gridInfo = { size: gridSize, plotSize, gap, startX, startY };
        this.plotContainer = this.add.container(0, 0);
        
        for (let row = 0; row < gridSize; row++) {
            for (let col = 0; col < gridSize; col++) {
                const px = startX + col * (plotSize + gap) + plotSize / 2;
                const py = startY + row * (plotSize + gap) + plotSize / 2;
                const plotId = row * gridSize + col;
                this.createPlotSprite(plotId, px, py, plotSize);
            }
        }
    }

    createPlotSprite(plotId, x, y, size) {
        const container = this.add.container(x, y);
        
        // 地块背景
        const bg = this.add.graphics();
        this.drawPlotBg(bg, size, 'empty');
        container.add(bg);
        
        // 作物层
        const cropGfx = this.add.graphics();
        container.add(cropGfx);
        
        // 进度条
        const progressBg = this.add.graphics();
        progressBg.setVisible(false);
        container.add(progressBg);
        
        const progressBar = this.add.graphics();
        progressBar.setVisible(false);
        container.add(progressBar);
        
        // 成熟闪光层
        const sparkle = this.add.graphics();
        sparkle.setVisible(false);
        container.add(sparkle);
        
        const ps = { container, bg, cropGfx, progressBg, progressBar, sparkle, size, plotId };
        this.plotSprites.push(ps);
        
        // 交互区域
        const hit = this.add.rectangle(0, 0, size, size, 0x000000, 0);
        hit.setInteractive({ useHandCursor: true });
        container.add(hit);
        
        hit.on('pointerdown', () => this.onPlotClick(plotId));
        hit.on('pointerover', () => this.onPlotHover(plotId, true));
        hit.on('pointerout', () => this.onPlotHover(plotId, false));
    }

    drawPlotBg(gfx, size, state) {
        gfx.clear();
        const half = size / 2;
        const colors = {
            empty:   { fill: 0x9B8B6B, stroke: 0x8B7B5B, lw: 1 },
            tilled:  { fill: 0x6B4F0E, stroke: 0x5A3E0A, lw: 2 },
            planted: { fill: 0x5A3E0A, stroke: 0x4A2E00, lw: 2 },
            mature:  { fill: 0xFFD700, stroke: 0xFFA500, lw: 2 }
        };
        const c = colors[state] || colors.empty;
        
        // 阴影
        gfx.fillStyle(0x000000, 0.15);
        gfx.fillRoundedRect(-half + 2, -half + 2, size, size, 6);
        
        // 主体
        gfx.fillStyle(c.fill, 1);
        gfx.fillRoundedRect(-half, -half, size, size, 6);
        
        // 内部纹理（土壤颗粒感）
        if (state === 'tilled' || state === 'planted') {
            for (let i = 0; i < 6; i++) {
                gfx.fillStyle(0x4A2E00, 0.3);
                const dx = Phaser.Math.Between(-half + 4, half - 4);
                const dy = Phaser.Math.Between(-half + 4, half - 4);
                gfx.fillCircle(dx, dy, 1.5);
            }
        }
        
        // 边框
        gfx.lineStyle(c.lw, c.stroke, 0.8);
        gfx.strokeRoundedRect(-half, -half, size, size, 6);
    }

    // ============== 作物绘制 ==============
    drawCrop(gfx, plot, size) {
        if (!plot.cropId) return;
        const stage = plot.getGrowthStage();
        const s = size * 0.35 * (0.5 + stage * 0.2);
        
        const palettes = {
            corn:   { stem: 0x228B22, fruit: 0xFFD700, leaf: 0x32CD32 },
            wheat:  { stem: 0xDAA520, fruit: 0xF0C040, leaf: 0x8B7355 },
            tomato: { stem: 0x228B22, fruit: 0xDC143C, leaf: 0x2E8B57 },
            carrot: { stem: 0x228B22, fruit: 0xFF6347, leaf: 0x32CD32 }
        };
        const pal = palettes[plot.cropId] || palettes.corn;
        
        gfx.clear();
        
        // 茎
        gfx.fillStyle(pal.stem, 1);
        gfx.fillRect(-1.5, -s, 3, s);
        
        // 叶子（阶段 > 0）
        if (stage > 0) {
            gfx.fillStyle(pal.leaf, 0.9);
            gfx.fillTriangle(-s * 0.6, -s * 0.3, -2, -s * 0.5, -2, -s * 0.1);
            gfx.fillTriangle(s * 0.6, -s * 0.3, 2, -s * 0.5, 2, -s * 0.1);
        }
        
        // 果实
        if (stage >= 2) {
            gfx.fillStyle(pal.fruit, 1);
            switch (plot.cropId) {
                case 'corn':
                    gfx.fillEllipse(0, -s - 4, 8, 14);
                    gfx.fillStyle(0x8B6914, 1);
                    gfx.fillRect(-1, -s - 10, 2, 6); // 玉米须
                    break;
                case 'wheat':
                    gfx.fillEllipse(0, -s - 3, 6, 10);
                    break;
                case 'tomato':
                    gfx.fillCircle(0, -s * 0.6, s * 0.35);
                    gfx.fillStyle(0x228B22, 1);
                    gfx.fillTriangle(0, -s * 0.6 - s * 0.35, -3, -s * 0.6 - s * 0.1, 3, -s * 0.6 - s * 0.1);
                    break;
                case 'carrot':
                    gfx.fillTriangle(0, -s, -s * 0.3, s * 0.2, s * 0.3, s * 0.2);
                    break;
            }
        }
    }

    // ============== 成熟闪光 ==============
    sparkleMature(ps) {
        const plot = this.farmModel.getPlot(ps.plotId);
        if (!plot || !plot.isMature()) {
            ps.sparkle.setVisible(false);
            return;
        }
        
        ps.sparkle.setVisible(true);
        ps.sparkle.clear();
        
        const t = Date.now() / 500;
        const half = ps.size / 2;
        
        // 旋转星光
        for (let i = 0; i < 4; i++) {
            const angle = t + (Math.PI / 2) * i;
            const dist = half * 0.6;
            const sx = Math.cos(angle) * dist;
            const sy = Math.sin(angle) * dist;
            const alpha = 0.4 + Math.sin(t * 2 + i) * 0.3;
            
            ps.sparkle.fillStyle(0xFFFFFF, alpha);
            ps.sparkle.fillStar(sx, sy, 2, 5, 3);
        }
    }

    // ============== 呼吸动画 ==============
    breatheCrops() {
        this.plotSprites.forEach(ps => {
            const plot = this.farmModel.getPlot(ps.plotId);
            if (!plot || plot.state !== 'planted') return;
            
            // 轻微缩放呼吸
            const scale = 1 + Math.sin(Date.now() / 1000) * 0.03;
            ps.container.setScale(scale);
        });
    }

    // ============== 更新逻辑 ==============
    updateGrowth() {
        this.plotSprites.forEach(ps => {
            const plot = this.farmModel.getPlot(ps.plotId);
            if (!plot || plot.state !== 'planted') return;
            
            this.updatePlotVisual(ps, plot);
            if (plot.isMature()) this.sparkleMature(ps);
        });
    }

    updatePlotVisual(ps, plot) {
        const state = plot.isMature() ? 'mature' : plot.state;
        this.drawPlotBg(ps.bg, ps.size, state);
        this.drawCrop(ps.cropGfx, plot, ps.size);
        
        // 进度条
        if (plot.state === 'planted' && !plot.isMature()) {
            const p = plot.getGrowthProgress();
            const half = ps.size / 2;
            ps.progressBg.setVisible(true);
            ps.progressBg.clear();
            ps.progressBg.fillStyle(0x000000, 0.4);
            ps.progressBg.fillRoundedRect(-half + 3, half - 8, ps.size - 6, 5, 2);
            
            ps.progressBar.setVisible(true);
            ps.progressBar.clear();
            ps.progressBar.fillStyle(0x4CAF50, 1);
            ps.progressBar.fillRoundedRect(-half + 3, half - 8, (ps.size - 6) * p, 5, 2);
        } else {
            ps.progressBg.setVisible(false);
            ps.progressBar.setVisible(false);
        }
    }

    syncPlotsToGraphics() {
        this.plotSprites.forEach(ps => {
            const plot = this.farmModel.getPlot(ps.plotId);
            if (plot) this.updatePlotVisual(ps, plot);
        });
    }

    // ============== 光标反馈 ==============
    setupCursor() {
        // 光标图标（跟随鼠标）
        this.cursorIcon = this.add.text(0, 0, '', {
            fontSize: '22px',
            padding: { x: 4, y: 4 }
        });
        this.cursorIcon.setDepth(1000);
        this.cursorIcon.setVisible(false);
        this.cursorIcon.setScrollFactor(0);
        
        // 提示框
        this.tooltipBg = this.add.graphics();
        this.tooltipBg.setDepth(999);
        this.tooltipBg.setVisible(false);
        
        this.tooltipText = this.add.text(0, 0, '', {
            fontSize: '11px',
            color: '#FFFFFF',
            fontFamily: 'Arial',
            padding: { x: 6, y: 3 }
        });
        this.tooltipText.setDepth(999);
        this.tooltipText.setVisible(false);
    }

    onPlotHover(plotId, isOver) {
        const ps = this.plotSprites.find(p => p.plotId === plotId);
        if (!ps) return;
        const plot = this.farmModel.getPlot(plotId);
        
        if (isOver) {
            // 高亮边框
            ps.bg.clear();
            const half = ps.size / 2;
            ps.bg.fillStyle(0xFFFFFF, 0.1);
            ps.bg.fillRoundedRect(-half, -half, ps.size, ps.size, 6);
            ps.bg.lineStyle(2, 0xFFFFFF, 0.6);
            ps.bg.strokeRoundedRect(-half, -half, ps.size, ps.size, 6);
            
            // 光标图标
            let icon = '❓';
            if (plot.state === 'empty') icon = '⛏️';
            else if (plot.state === 'tilled') icon = '🌱';
            else if (plot.state === 'planted' && plot.isMature()) icon = '🫴';
            else if (plot.state === 'planted') icon = '💧';
            
            this.cursorIcon.setText(icon);
            this.cursorIcon.setVisible(true);
            
            // 提示框
            let tip = plot.getStatusText();
            if (plot.state === 'tilled') tip = '点击种植';
            else if (plot.isMature()) tip = '点击收获！';
            
            const tx = ps.container.x;
            const ty = ps.container.y - ps.size / 2 - 18;
            
            this.tooltipText.setText(tip);
            this.tooltipText.setPosition(tx, ty);
            this.tooltipText.setOrigin(0.5);
            this.tooltipText.setVisible(true);
            
            const tw = this.tooltipText.width;
            this.tooltipBg.clear();
            this.tooltipBg.fillStyle(0x000000, 0.7);
            this.tooltipBg.fillRoundedRect(tx - tw / 2 - 4, ty - 8, tw + 8, 18, 6);
            this.tooltipBg.setVisible(true);
        } else {
            // 恢复
            if (plot) this.updatePlotVisual(ps, plot);
            this.cursorIcon.setVisible(false);
            this.tooltipBg.setVisible(false);
            this.tooltipText.setVisible(false);
        }
    }

    // ============== 点击处理 ==============
    async onPlotClick(plotId) {
        const plot = this.farmModel.getPlot(plotId);
        if (!plot) return;
        
        // 点击缩放反馈
        this.tweens.add({
            targets: this.plotSprites.find(p => p.plotId === plotId).container,
            scaleX: 0.9, scaleY: 0.9,
            duration: 60, yoyo: true,
            ease: 'Back.easeOut'
        });
        
        switch (plot.state) {
            case 'empty':
                if (this.selectedTool === 'hoe') {
                    await this.farmModel.till(plotId);
                    this.showFloatingText('✅ 已开垦', plotId);
                }
                break;
            case 'tilled':
                if (this.selectedTool === 'seed') {
                    if (this.farmModel.getSeedCount(this.selectedCrop) > 0) {
                        await this.farmModel.plant(plotId, this.selectedCrop);
                        this.showFloatingText('🌱 已种植', plotId);
                    } else {
                        this.showFloatingText('❌ 种子不足', plotId);
                    }
                }
                break;
            case 'planted':
                if (plot.isMature()) {
                    await this.farmModel.harvest(plotId);
                    this.showFloatingText('🎉 +1', plotId);
                } else if (this.selectedTool === 'water') {
                    await this.farmModel.water(plotId);
                    this.showFloatingText('💧 浇水', plotId);
                }
                break;
        }
        
        this.updateGoldDisplay();
    }

    // ============== HUD 界面 ==============
    createHUD() {
        // === 顶部金币栏 ===
        this.createGoldBar();
        
        // === 底部工具栏（HUD 风格）===
        this.createToolbarHUD();
    }

    createGoldBar() {
        const hud = this.add.container(0, 0);
        hud.setScrollFactor(0);
        hud.setDepth(100);
        
        const barW = 140;
        const barH = 32;
        const bx = this.W / 2;
        const by = 16;
        
        // 背景：半透明 + 圆角 + 阴影
        const bg = this.add.graphics();
        bg.fillStyle(0x000000, 0.45);
        bg.fillRoundedRect(bx - barW / 2, by - barH / 2, barW, barH, barH / 2);
        // 内发光边
        bg.lineStyle(1, 0xFFFFFF, 0.15);
        bg.strokeRoundedRect(bx - barW / 2, by - barH / 2, barW, barH, barH / 2);
        hud.add(bg);
        
        // 金币图标
        const coin = this.add.text(bx - barW / 2 + 14, by, '💰', { fontSize: '16px' });
        coin.setOrigin(0.5);
        hud.add(coin);
        
        // 金币数字
        this.goldText = this.add.text(bx - barW / 2 + 36, by, '100', {
            fontSize: '15px',
            fontFamily: 'Arial',
            fontStyle: 'bold',
            color: '#FFD700'
        });
        this.goldText.setOrigin(0, 0.5);
        hud.add(this.goldText);
    }

    createToolbarHUD() {
        const hud = this.add.container(0, 0);
        hud.setScrollFactor(0);
        hud.setDepth(100);
        
        const barW = 320;
        const barH = 56;
        const bx = this.W / 2;
        const by = this.H - 16;
        
        // 背景：毛玻璃效果
        const bg = this.add.graphics();
        bg.fillStyle(0x1a1a2e, 0.75);
        bg.fillRoundedRect(bx - barW / 2, by - barH, barW, barH, 16);
        // 顶部高光线
        bg.lineStyle(1, 0xFFFFFF, 0.12);
        bg.lineBetween(bx - barW / 2 + 16, by - barH + 1, bx + barW / 2 - 16, by - barH + 1);
        // 外发光
        bg.lineStyle(1, 0xFFFFFF, 0.06);
        bg.strokeRoundedRect(bx - barW / 2, by - barH, barW, barH, 16);
        hud.add(bg);
        
        // 工具按钮
        const tools = [
            { id: 'hoe',   icon: '⛏️', label: '锄头' },
            { id: 'seed',  icon: '🌱', label: '种子' },
            { id: 'water', icon: '💧', label: '浇水' }
        ];
        
        this.toolButtons = [];
        const btnStartX = bx - (tools.length * 70) / 2 + 35;
        
        tools.forEach((tool, i) => {
            const tx = btnStartX + i * 70;
            const ty = by - barH / 2;
            const btn = this.createToolBtn(tx, ty, tool, i === 0);
            hud.add(btn);
            this.toolButtons.push(btn);
        });
        
        // 种子选择浮层
        this.createSeedPopup(hud, bx, by - barH - 8);
    }

    createToolBtn(x, y, tool, selected) {
        const container = this.add.container(x, y);
        
        // 按钮圆形背景
        const bg = this.add.graphics();
        const r = 22;
        if (selected) {
            // 选中：绿色发光
            bg.fillStyle(0x4CAF50, 0.3);
            bg.fillCircle(0, 0, r + 4);
            bg.fillStyle(0x4CAF50, 0.9);
            bg.fillCircle(0, 0, r);
        } else {
            bg.fillStyle(0x333344, 0.8);
            bg.fillCircle(0, 0, r);
            bg.lineStyle(1, 0xFFFFFF, 0.1);
            bg.strokeCircle(0, 0, r);
        }
        container.add(bg);
        
        // 图标
        const icon = this.add.text(0, -1, tool.icon, { fontSize: '20px' });
        icon.setOrigin(0.5);
        container.add(icon);
        
        // 标签
        const label = this.add.text(0, r + 10, tool.label, {
            fontSize: '9px',
            color: selected ? '#4CAF50' : '#888899',
            fontFamily: 'Arial'
        });
        label.setOrigin(0.5);
        container.add(label);
        
        // 交互
        const hit = this.add.circle(0, 0, r, 0x000000, 0);
        hit.setInteractive({ useHandCursor: true });
        container.add(hit);
        
        hit.on('pointerdown', () => this.selectTool(tool.id));
        hit.on('pointerover', () => {
            if (!container.isSelected) {
                bg.clear();
                bg.fillStyle(0x444455, 0.9);
                bg.fillCircle(0, 0, r);
            }
        });
        hit.on('pointerout', () => {
            if (!container.isSelected) {
                bg.clear();
                bg.fillStyle(0x333344, 0.8);
                bg.fillCircle(0, 0, r);
                bg.lineStyle(1, 0xFFFFFF, 0.1);
                bg.strokeCircle(0, 0, r);
            }
        });
        
        container.toolData = tool;
        container.bg = bg;
        container.iconObj = icon;
        container.labelObj = label;
        container.isSelected = selected;
        
        return container;
    }

    createSeedPopup(parentHud, cx, bottomY) {
        this.seedPopup = this.add.container(cx, bottomY);
        this.seedPopup.setVisible(false);
        parentHud.add(this.seedPopup);
        
        const seeds = [
            { id: 'corn',   icon: '🌽', name: '玉米' },
            { id: 'wheat',  icon: '🌾', name: '小麦' },
            { id: 'tomato', icon: '🍅', name: '番茄' },
            { id: 'carrot', icon: '🥕', name: '萝卜' }
        ];
        
        const popupW = seeds.length * 56 + 16;
        const popupH = 64;
        
        // 弹出背景
        const bg = this.add.graphics();
        bg.fillStyle(0x1a1a2e, 0.85);
        bg.fillRoundedRect(-popupW / 2, -popupH, popupW, popupH, 12);
        bg.lineStyle(1, 0xFFFFFF, 0.08);
        bg.strokeRoundedRect(-popupW / 2, -popupH, popupW, popupH, 12);
        // 小三角
        bg.fillStyle(0x1a1a2e, 0.85);
        bg.fillTriangle(-6, 0, 6, 0, 0, 6);
        this.seedPopup.add(bg);
        
        this.seedBtns = [];
        seeds.forEach((seed, i) => {
            const sx = -popupW / 2 + 28 + i * 56;
            const sy = -popupH / 2;
            
            const btn = this.add.container(sx, sy);
            
            const btnBg = this.add.graphics();
            btnBg.fillStyle(0x333344, 0.8);
            btnBg.fillRoundedRect(-20, -20, 40, 40, 10);
            btn.add(btnBg);
            
            const icon = this.add.text(0, -3, seed.icon, { fontSize: '20px' });
            icon.setOrigin(0.5);
            btn.add(icon);
            
            const count = this.farmModel.getSeedCount(seed.id);
            const countTxt = this.add.text(0, 16, `x${count}`, {
                fontSize: '8px',
                color: count > 0 ? '#AAAAAA' : '#FF4444',
                fontFamily: 'Arial'
            });
            countTxt.setOrigin(0.5);
            btn.add(countTxt);
            
            const hit = this.add.rectangle(0, 0, 40, 40, 0x000000, 0);
            hit.setInteractive({ useHandCursor: true });
            btn.add(hit);
            
            hit.on('pointerdown', () => this.selectSeed(seed.id));
            
            btn.seedId = seed.id;
            btn.bg = btnBg;
            this.seedBtns.push(btn);
            this.seedPopup.add(btn);
        });
    }

    selectTool(toolId) {
        this.selectedTool = toolId;
        
        this.toolButtons.forEach(btn => {
            const sel = btn.toolData.id === toolId;
            btn.isSelected = sel;
            const bg = btn.bg;
            const r = 22;
            bg.clear();
            
            if (sel) {
                bg.fillStyle(0x4CAF50, 0.3);
                bg.fillCircle(0, 0, r + 4);
                bg.fillStyle(0x4CAF50, 0.9);
                bg.fillCircle(0, 0, r);
            } else {
                bg.fillStyle(0x333344, 0.8);
                bg.fillCircle(0, 0, r);
                bg.lineStyle(1, 0xFFFFFF, 0.1);
                bg.strokeCircle(0, 0, r);
            }
            
            btn.labelObj.setColor(sel ? '#4CAF50' : '#888899');
        });
        
        // 种子弹窗
        if (this.seedPopup) {
            this.seedPopup.setVisible(toolId === 'seed');
            // 弹出动画
            if (toolId === 'seed') {
                this.seedPopup.setScale(0.8);
                this.seedPopup.setAlpha(0);
                this.tweens.add({
                    targets: this.seedPopup,
                    scaleX: 1, scaleY: 1, alpha: 1,
                    duration: 200, ease: 'Back.easeOut'
                });
            }
        }
    }

    selectSeed(cropId) {
        this.selectedCrop = cropId;
        
        this.seedBtns.forEach(btn => {
            const sel = btn.seedId === cropId;
            btn.bg.clear();
            btn.bg.fillStyle(sel ? 0x4CAF50 : 0x333344, 0.8);
            btn.bg.fillRoundedRect(-20, -20, 40, 40, 10);
            if (sel) {
                btn.bg.lineStyle(2, 0xFFFFFF, 0.3);
                btn.bg.strokeRoundedRect(-20, -20, 40, 40, 10);
            }
        });
    }

    // ============== 浮动文字 ==============
    showFloatingText(text, plotId) {
        const ps = this.plotSprites.find(p => p.plotId === plotId);
        if (!ps) return;
        
        const msg = this.add.text(ps.container.x, ps.container.y - ps.size / 2 - 10, text, {
            fontSize: '13px',
            fontStyle: 'bold',
            color: '#FFFFFF',
            fontFamily: 'Arial',
            stroke: '#000000',
            strokeThickness: 2
        });
        msg.setOrigin(0.5);
        msg.setDepth(200);
        
        this.tweens.add({
            targets: msg,
            y: msg.y - 30,
            alpha: 0,
            duration: 800,
            ease: 'Power2',
            onComplete: () => msg.destroy()
        });
    }

    // ============== 数据回调 ==============
    onModelUpdate(event, data) {
        switch (event) {
            case 'data_loaded':
                this.syncPlotsToGraphics();
                this.updateGoldDisplay();
                break;
            case 'plot_updated':
                const ps = this.plotSprites.find(p => p.plotId === data.id);
                if (ps) this.updatePlotVisual(ps, data);
                break;
            case 'gold_changed':
                this.updateGoldDisplay();
                break;
        }
    }

    updateGoldDisplay() {
        if (this.goldText) {
            this.goldText.setText(String(this.farmModel.gold));
        }
    }

    async loadGameData() {
        if (this.farmModel.plots.length > 0) this.syncPlotsToGraphics();
        await this.farmModel.loadFromServer();
        this.syncPlotsToGraphics();
        this.updateGoldDisplay();
    }

    setupInput() {
        // 鼠标移动更新光标
        this.input.on('pointermove', (pointer) => {
            if (this.cursorIcon && this.cursorIcon.visible) {
                this.cursorIcon.setPosition(pointer.x + 12, pointer.y - 12);
            }
        });
        
        this.input.keyboard.on('keydown-ESC', () => {
            console.log('ESC pressed');
        });
    }
}

window.GameScene = GameScene;
