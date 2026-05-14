/**
 * GameScene.js - Phaser 3 游戏主场景
 * 
 * v1.5.6 矢量扁平插画风升级
 * 
 * 视觉规范：
 * - 莫兰迪色系
 * - 圆润化造型，无描边
 * - 伪3D光影（顶光）
 * - 柔和投影
 * - 几何角色
 */

/* ==================== 莫兰迪色系色彩系统 ==================== */
const C = {
    // 背景色系
    sky:        0xB8E0D2,  // 天空浅绿
    grass:      0x95D5B2,  // 草地绿
    grassDark:  0x74C69D,  // 草地暗
    grassLight: 0xB7E4C7,  // 草地亮
    
    // 土系
    soil:       0xDDB892,  // 土壤（蛋糕底层）
    soilMid:    0xC9A67A, // 土壤中层
    soilDark:   0xB08968, // 土壤暗面
    
    // 作物色系
    tomato:     0xE07A5F,  // 番茄红（莫兰迪红）
    tomatoDark: 0xC85A3E, // 番茄暗
    carrot:    0xF4A261, // 胡萝卜橙
    carrotDark:0xE07A5F, // 胡萝卜暗
    corn:      0xE9C46A,  // 玉米黄
    cornDark:  0xD4A84B, // 玉米暗
    wheat:     0xF0E6D3,  // 小麦米色
    wheatDark: 0xD9CEBD, // 小麦暗
    leaf:      0x74C69D,  // 叶子绿
    leafDark:  0x52B788, // 叶子暗
    
    // UI 色系
    hudBg:      0xFFFFFF,  // HUD 白色
    hudShadow:  0x457B9D, // HUD 阴影（蓝灰）
    gold:       0xF4A261, // 金币橙
    accent:     0xE07A5F, // 强调色（珊瑚红）
    text:       0x264653,  // 深青色文字
    textLight:  0x5C7A8A, // 浅色文字
    
    // 角色色系
    skin:       0xF5D6C6,  // 皮肤色
    cloth:      0xA8DADC,  // 衣服蓝
    clothDark:  0x89C2D9, // 衣服暗
    hair:       0x6B4423, // 头发棕
};

class GameScene extends Phaser.Scene {
    constructor() {
        super({ key: 'GameScene' });
        
        this.farmModel = null;
        this.plots = [];
        this.selectedTool = 'hoe';
        this.selectedCrop = 'corn';
        
        // 尺寸常量（基于 360x640）
        this.W = 360;
        this.H = 640;
        
        // 角色动画
        this.charX = this.W / 2;
        this.charY = 0; // 稍后计算
        this.charTween = null;
    }

    create() {
        this.farmModel = new FarmModel();
        this.farmModel.addListener(this.onModelUpdate.bind(this));
        
        this.drawSky();
        this.drawClouds();
        this.drawHills();
        this.drawGround();
        this.drawFence();
        this.drawPlots();
        this.drawCharacter();
        this.createHUD();
        this.createCursor();
        
        this.loadGameData();
        
        // 动画循环
        this.time.addEvent({ delay: 100, callback: this.updateCrops, callbackScope: this, loop: true });
    }

    /* ==================== 背景绘制 ==================== */
    drawSky() {
        const sky = this.add.graphics();
        sky.fillGradientStyle(C.sky, C.sky, C.grass, C.grass, 1);
        sky.fillRect(0, 0, this.W, this.H);
    }
    
    drawClouds() {
        const drawCloud = (cx, cy, scale = 1) => {
            const cloud = this.add.graphics();
            const w = 80 * scale;
            const h = 30 * scale;
            
            // 柔和投影
            cloud.fillStyle(C.sky, 0.3);
            cloud.fillEllipse(cx, cy + 4, w * 1.1, h * 0.7);
            
            // 主体（白色无描边）
            cloud.fillStyle(0xFFFFFF, 0.9);
            cloud.fillEllipse(cx, cy, w * 0.6, h * 0.6);
            cloud.fillEllipse(cx - w * 0.25, cy + 2, w * 0.5, h * 0.5);
            cloud.fillEllipse(cx + w * 0.3, cy + 3, w * 0.45, h * 0.45);
        };
        
        drawCloud(60, 60, 0.8);
        drawCloud(280, 90, 1.0);
        drawCloud(180, 40, 0.6);
    }
    
    drawHills() {
        // 远景山丘
        const hill = this.add.graphics();
        
        // 第一层山丘（更远，更淡）
        hill.fillStyle(C.grassLight, 0.6);
        hill.fillEllipse(this.W * 0.2, this.H * 0.42, 200, 80);
        hill.fillEllipse(this.W * 0.8, this.H * 0.40, 180, 70);
        
        // 第二层山丘
        hill.fillStyle(C.grassDark, 0.7);
        hill.fillEllipse(this.W * 0.5, this.H * 0.45, 250, 60);
        hill.fillEllipse(this.W * 0.15, this.H * 0.44, 160, 50);
        hill.fillEllipse(this.W * 0.85, this.H * 0.43, 140, 45);
    }
    
    drawGround() {
        // 主地面（圆角矩形，像一块大蛋糕）
        const ground = this.add.graphics();
        
        // 柔和投影
        ground.fillStyle(C.grassDark, 0.25);
        ground.fillRoundedRect(8, this.H * 0.42 + 4, this.W - 16, this.H * 0.58 - 4, 24);
        
        // 地面主体
        ground.fillStyle(C.grass, 1);
        ground.fillRoundedRect(8, this.H * 0.42, this.W - 16, this.H * 0.58 - 8, 24);
        
        // 顶部受光面
        ground.fillStyle(C.grassLight, 0.5);
        ground.fillRoundedRect(12, this.H * 0.42, this.W - 24, 8, 4);
    }
    
    drawFence() {
        const fenceY = this.H * 0.42 - 4;
        const fence = this.add.graphics();
        
        fence.fillStyle(C.soilMid, 0.8);
        
        // 栅栏木板（无描边，圆润）
        for (let x = 20; x < this.W - 20; x += 35) {
            // 木板主体
            fence.fillStyle(C.corn, 0.9);
            fence.fillRoundedRect(x - 6, fenceY - 24, 12, 24, 3);
            // 木板顶部高光
            fence.fillStyle(C.cornDark, 0.3);
            fence.fillRoundedRect(x - 5, fenceY - 23, 10, 4, 2);
        }
        
        // 横杆
        fence.fillStyle(C.corn, 0.8);
        fence.fillRoundedRect(15, fenceY - 18, this.W - 30, 5, 2);
        fence.fillRoundedRect(15, fenceY - 8, this.W - 30, 4, 2);
    }

    /* ==================== 土地绘制（圆角土丘） ==================== */
    drawPlots() {
        const gridStartY = this.H * 0.46;
        const gridStartX = 30;
        const plotSize = 54;
        const gap = 10;
        const cols = 4;
        
        this.plotSize = plotSize;
        this.gridStartX = gridStartX;
        this.gridStartY = gridStartY;
        this.plotGap = gap;
        this.cols = cols;
        
        for (let i = 0; i < 16; i++) {
            const col = i % cols;
            const row = Math.floor(i / cols);
            const x = gridStartX + col * (plotSize + gap) + plotSize / 2;
            const y = gridStartY + row * (plotSize + gap) + plotSize / 2;
            
            this.createPlot(i, x, y, plotSize);
        }
    }
    
    createPlot(id, x, y, size) {
        const container = this.add.container(x, y);
        
        // 土丘层
        const mound = this.add.graphics();
        container.add(mound);
        
        // 作物容器
        const crop = this.add.graphics();
        container.add(crop);
        
        // 闪光层（成熟）
        const sparkle = this.add.graphics();
        sparkle.setVisible(false);
        container.add(sparkle);
        
        const plotData = { id, mound, crop, sparkle, size, x, y };
        this.plots.push(plotData);
        
        // 交互
        const hit = this.add.rectangle(0, 0, size - 4, size - 4, 0x000000, 0);
        hit.setInteractive({ useHandCursor: true });
        container.add(hit);
        
        hit.on('pointerdown', () => this.onPlotClick(id));
        hit.on('pointerover', () => this.onPlotHover(id, true));
        hit.on('pointerout', () => this.onPlotHover(id, false));
    }
    
    drawMound(gfx, state, isHover = false) {
        gfx.clear();
        const s = this.plotSize;
        const half = s / 2;
        
        // 伪3D土丘（顶光：下侧和右侧暗）
        if (state === 'empty') {
            // 草地土丘
            // 投影
            gfx.fillStyle(C.grassDark, 0.3);
            gfx.fillEllipse(2, half - 4, s - 8, 16);
            // 土丘主体
            gfx.fillStyle(isHover ? C.grassLight : C.grass, 1);
            gfx.fillEllipse(0, 0, s - 4, s - 8);
            // 顶部高光
            gfx.fillStyle(0xFFFFFF, 0.2);
            gfx.fillEllipse(-4, -4, s * 0.4, s * 0.25);
            
        } else if (state === 'tilled') {
            // 泥土土丘
            // 投影
            gfx.fillStyle(C.soilDark, 0.35);
            gfx.fillEllipse(2, half - 4, s - 8, 16);
            // 土丘主体
            gfx.fillStyle(isHover ? C.soil : C.soilMid, 1);
            gfx.fillEllipse(0, 0, s - 4, s - 8);
            // 高光
            gfx.fillStyle(C.soil, 0.4);
            gfx.fillEllipse(-4, -4, s * 0.4, s * 0.25);
            // 泥土纹理
            gfx.fillStyle(C.soilDark, 0.15);
            gfx.fillCircle(-6, 2, 3);
            gfx.fillCircle(4, 4, 2);
            gfx.fillCircle(8, -2, 2.5);
            
        } else if (state === 'planted' || state === 'mature') {
            // 作物土丘
            // 投影
            gfx.fillStyle(C.soilDark, 0.4);
            gfx.fillEllipse(2, half - 4, s - 8, 16);
            // 土丘主体
            gfx.fillStyle(state === 'mature' ? C.corn : C.soilMid, 1);
            gfx.fillEllipse(0, 0, s - 4, s - 8);
            // 高光
            gfx.fillStyle(state === 'mature' ? C.corn : C.soil, 0.5);
            gfx.fillEllipse(-4, -4, s * 0.4, s * 0.25);
        }
    }
    
    drawCrop(gfx, plot) {
        gfx.clear();
        if (!plot.cropId) return;
        
        const stage = plot.getGrowthStage();
        const progress = plot.getGrowthProgress();
        const size = this.plotSize;
        const baseScale = 0.3 + progress * 0.7; // 生长动画：从小到大
        
        const s = size * baseScale * 0.5;
        
        const palettes = {
            corn:    { main: C.corn,    dark: C.cornDark,  leaf: C.leaf },
            wheat:   { main: C.wheat,   dark: C.wheatDark, leaf: C.leafDark },
            tomato:  { main: C.tomato,   dark: C.tomatoDark,leaf: C.leaf },
            carrot:  { main: C.carrot,   dark: C.carrotDark,leaf: C.leafDark }
        };
        const pal = palettes[plot.cropId] || palettes.corn;
        
        const cx = 0;
        const cy = -s * 0.5;
        
        if (plot.cropId === 'corn') {
            // 玉米：茎 + 叶子 + 果实
            // 茎
            gfx.fillStyle(C.leaf, 1);
            gfx.fillRect(cx - 2, cy, 4, s * 1.2);
            // 叶子
            if (stage >= 1) {
                gfx.fillStyle(C.leafDark, 1);
                gfx.fillEllipse(cx - s * 0.5, cy + s * 0.3, s * 0.4, s * 0.2);
                gfx.fillEllipse(cx + s * 0.5, cy + s * 0.3, s * 0.4, s * 0.2);
            }
            // 果实
            if (stage >= 2) {
                gfx.fillStyle(pal.main, 1);
                gfx.fillEllipse(cx, cy - s * 0.2, s * 0.35, s * 0.6);
                gfx.fillStyle(pal.dark, 0.5);
                gfx.fillEllipse(cx - 2, cy - s * 0.2, s * 0.1, s * 0.4);
            }
            
        } else if (plot.cropId === 'wheat') {
            // 小麦：麦穗
            gfx.fillStyle(C.leaf, 1);
            gfx.fillRect(cx - 1.5, cy, 3, s * 1.2);
            if (stage >= 1) {
                gfx.fillStyle(pal.main, 1);
                gfx.fillEllipse(cx, cy - s * 0.3, s * 0.25, s * 0.4);
                gfx.fillStyle(pal.dark, 0.3);
                gfx.fillEllipse(cx - 1, cy - s * 0.3, s * 0.1, s * 0.3);
            }
            
        } else if (plot.cropId === 'tomato') {
            // 番茄：茎 + 叶子 + 果实
            gfx.fillStyle(C.leaf, 1);
            gfx.fillRect(cx - 1.5, cy, 3, s);
            if (stage >= 1) {
                gfx.fillStyle(C.leafDark, 1);
                gfx.fillEllipse(cx - s * 0.4, cy + s * 0.2, s * 0.35, s * 0.18);
                gfx.fillEllipse(cx + s * 0.4, cy + s * 0.2, s * 0.35, s * 0.18);
            }
            if (stage >= 2) {
                gfx.fillStyle(pal.main, 1);
                gfx.fillCircle(cx, cy - s * 0.3, s * 0.35);
                // 高光
                gfx.fillStyle(0xFFFFFF, 0.3);
                gfx.fillCircle(cx - s * 0.1, cy - s * 0.4, s * 0.1);
            }
            
        } else if (plot.cropId === 'carrot') {
            // 胡萝卜：叶子 + 根
            gfx.fillStyle(C.leaf, 1);
            gfx.fillTriangle(cx, cy - s * 0.6, cx - s * 0.3, cy, cx + s * 0.3, cy);
            gfx.fillTriangle(cx, cy - s * 0.4, cx - s * 0.15, cy + s * 0.1, cx + s * 0.15, cy + s * 0.1);
            if (stage >= 1) {
                gfx.fillStyle(pal.main, 1);
                gfx.fillTriangle(cx, cy + s * 0.2, cx - s * 0.25, cy - s * 0.2, cx + s * 0.25, cy - s * 0.2);
                // 纹理
                gfx.fillStyle(pal.dark, 0.2);
                gfx.fillCircle(cx, cy, 2);
            }
        }
    }
    
    drawSparkle(gfx) {
        gfx.clear();
        const t = Date.now() / 400;
        const colors = [0xFFFFFF, C.corn, 0xFFFFFF];
        
        for (let i = 0; i < 4; i++) {
            const angle = t + (Math.PI / 2) * i;
            const dist = this.plotSize * 0.35;
            const sx = Math.cos(angle) * dist;
            const sy = Math.sin(angle) * dist - this.plotSize * 0.2;
            const alpha = 0.4 + Math.sin(t * 2 + i) * 0.3;
            const size = 3 + Math.sin(t + i) * 1;
            
            gfx.fillStyle(colors[i % 2], alpha);
            gfx.fillCircle(sx, sy, size);
        }
    }
    
    updateCrops() {
        this.plots.forEach(p => {
            const plot = this.farmModel.getPlot(p.id);
            if (!plot) return;
            
            const state = plot.isMature() ? 'mature' : plot.state;
            this.drawMound(p.mound, state);
            this.drawCrop(p.crop, plot);
            
            if (plot.isMature()) {
                p.sparkle.setVisible(true);
                this.drawSparkle(p.sparkle);
            } else {
                p.sparkle.setVisible(false);
            }
        });
    }
    
    syncPlots() {
        this.updateCrops();
    }

    /* ==================== 几何角色 ==================== */
    drawCharacter() {
        // 角色位置：底部中央
        this.charY = this.H - 120;
        
        const char = this.add.container(this.charX, this.charY);
        this.character = char;
        
        // 身体（胶囊形）
        const body = this.add.graphics();
        body.fillStyle(C.cloth, 1);
        body.fillRoundedRect(-16, -10, 32, 40, 16);
        // 身体阴影面
        body.fillStyle(C.clothDark, 0.4);
        body.fillRoundedRect(4, -6, 10, 32, 8);
        char.add(body);
        
        // 头（圆形）
        const head = this.add.graphics();
        head.fillStyle(C.skin, 1);
        head.fillCircle(0, -28, 18);
        // 头发
        head.fillStyle(C.hair, 1);
        head.fillEllipse(0, -40, 22, 14);
        // 眼睛
        head.fillStyle(C.text, 1);
        head.fillCircle(-6, -30, 3);
        head.fillCircle(6, -30, 3);
        // 腮红
        head.fillStyle(C.tomato, 0.2);
        head.fillCircle(-12, -24, 4);
        head.fillCircle(12, -24, 4);
        char.add(head);
        
        // 腿（两个小椭圆）
        const legs = this.add.graphics();
        legs.fillStyle(C.skin, 1);
        legs.fillEllipse(-8, 32, 10, 8);
        legs.fillEllipse(8, 32, 10, 8);
        char.add(legs);
        
        // 阴影
        const shadow = this.add.graphics();
        shadow.fillStyle(0x000000, 0.1);
        shadow.fillEllipse(0, 40, 40, 10);
        char.add(shadow);
        
        // 呼吸/站立动画
        this.tweens.add({
            targets: char,
            y: this.charY - 3,
            duration: 1200,
            yoyo: true,
            repeat: -1,
            ease: 'Sine.easeInOut'
        });
        
        // 轻微左右摇摆
        this.tweens.add({
            targets: char,
            angle: 2,
            duration: 2000,
            yoyo: true,
            repeat: -1,
            ease: 'Sine.easeInOut'
        });
    }

    /* ==================== HUD 界面 ==================== */
    createHUD() {
        const hud = this.add.container(0, 0);
        hud.setScrollFactor(0);
        hud.setDepth(100);
        
        // === 顶部金币栏 ===
        this.createGoldBar(hud);
        
        // === 底部工具栏 ===
        this.createToolbar(hud);
    }
    
    createGoldBar(parent) {
        const bx = this.W / 2;
        const by = 28;
        
        // 玻璃拟态背景
        const bg = this.add.graphics();
        bg.fillStyle(C.hudBg, 0.85);
        bg.fillRoundedRect(bx - 70, by - 20, 140, 40, 20);
        // 投影
        bg.fillStyle(C.hudShadow, 0.08);
        bg.fillRoundedRect(bx - 68, by - 18, 136, 20, 10);
        parent.add(bg);
        
        // 金币图标
        const coin = this.add.graphics();
        coin.fillStyle(C.gold, 1);
        coin.fillCircle(0, 0, 12);
        coin.fillStyle(0xFFFFFF, 0.3);
        coin.fillCircle(-3, -3, 4);
        coin.x = bx - 48;
        coin.y = by;
        parent.add(coin);
        
        // 金币文字
        this.goldText = this.add.text(bx - 28, by, '100', {
            fontFamily: 'Nunito',
            fontSize: '18px',
            fontStyle: 'bold',
            color: '#264653'
        });
        this.goldText.setOrigin(0, 0.5);
        parent.add(this.goldText);
    }
    
    createToolbar(parent) {
        const tools = [
            { id: 'hoe',   icon: '⛏️', label: '开垦' },
            { id: 'seed',  icon: '🌱', label: '种植' },
            { id: 'water', icon: '💧', label: '浇水' }
        ];
        
        const bx = this.W / 2;
        const by = this.H - 40;
        const btnW = 75;
        const totalW = tools.length * btnW + (tools.length - 1) * 12;
        const startX = bx - totalW / 2;
        
        // 玻璃拟态背景
        const bg = this.add.graphics();
        bg.fillStyle(C.hudBg, 0.88);
        bg.fillRoundedRect(startX - 12, by - 36, totalW + 24, 72, 24);
        // 顶部高光
        bg.fillStyle(0xFFFFFF, 0.5);
        bg.fillRoundedRect(startX - 8, by - 32, totalW + 16, 20, 12);
        // 柔和阴影
        bg.fillStyle(C.hudShadow, 0.06);
        bg.fillRoundedRect(startX - 10, by + 4, totalW + 20, 24, 12);
        parent.add(bg);
        
        this.toolBtns = [];
        
        tools.forEach((tool, i) => {
            const tx = startX + btnW / 2 + i * (btnW + 12);
            const btn = this.createToolBtn(tx, by, tool, i === 0);
            parent.add(btn);
            this.toolBtns.push(btn);
        });
        
        // 种子选择器
        this.createSeedSelector(parent);
    }
    
    createToolBtn(x, y, tool, selected) {
        const container = this.add.container(x, y);
        
        // 按钮背景
        const bg = this.add.graphics();
        const r = 26;
        if (selected) {
            bg.fillStyle(C.leaf, 0.25);
            bg.fillCircle(0, 0, r + 4);
            bg.fillStyle(C.leaf, 1);
            bg.fillCircle(0, 0, r);
        } else {
            bg.fillStyle(C.hudShadow, 0.08);
            bg.fillCircle(0, 0, r);
        }
        container.add(bg);
        
        // 图标
        const icon = this.add.text(0, -2, tool.icon, { fontSize: '22px' });
        icon.setOrigin(0.5);
        container.add(icon);
        
        // 标签
        const label = this.add.text(0, r + 8, tool.label, {
            fontFamily: 'Nunito',
            fontSize: '10px',
            fontStyle: 'bold',
            color: selected ? '#264653' : '#5C7A8A'
        });
        label.setOrigin(0.5);
        container.add(label);
        
        // 交互
        const hit = this.add.circle(0, 0, r, 0x000000, 0);
        hit.setInteractive({ useHandCursor: true });
        container.add(hit);
        hit.on('pointerdown', () => this.selectTool(tool.id));
        
        container.bg = bg;
        container.icon = icon;
        container.label = label;
        container.isSelected = selected;
        container.toolId = tool.id;
        
        return container;
    }
    
    createSeedSelector(parent) {
        const seeds = [
            { id: 'corn',   icon: '🌽' },
            { id: 'wheat',  icon: '🌾' },
            { id: 'tomato', icon: '🍅' },
            { id: 'carrot', icon: '🥕' }
        ];
        
        const bx = this.W / 2;
        const by = this.H - 90;
        
        this.seedSelector = this.add.container(bx, by);
        this.seedSelector.setVisible(false);
        this.seedSelector.setScale(0.8);
        this.seedSelector.setAlpha(0);
        parent.add(this.seedSelector);
        
        const totalW = seeds.length * 50 + (seeds.length - 1) * 8;
        
        // 弹窗背景
        const bg = this.add.graphics();
        bg.fillStyle(C.hudBg, 0.92);
        bg.fillRoundedRect(-totalW / 2 - 12, -28, totalW + 24, 56, 16);
        // 高光
        bg.fillStyle(0xFFFFFF, 0.4);
        bg.fillRoundedRect(-totalW / 2 - 8, -24, totalW + 16, 24, 12);
        // 小三角
        bg.fillStyle(C.hudBg, 0.95);
        bg.fillTriangle(-6, 28, 6, 28, 0, 36);
        this.seedSelector.add(bg);
        
        this.seedBtns = [];
        seeds.forEach((seed, i) => {
            const sx = -totalW / 2 + 25 + i * 58;
            const btn = this.add.container(sx, 0);
            
            const btnBg = this.add.graphics();
            btnBg.fillStyle(C.hudShadow, 0.06);
            btnBg.fillRoundedRect(-20, -20, 40, 40, 12);
            btn.add(btnBg);
            
            const icon = this.add.text(0, -2, seed.icon, { fontSize: '24px' });
            icon.setOrigin(0.5);
            btn.add(icon);
            
            const count = this.add.text(0, 14, 'x2', {
                fontFamily: 'Nunito',
                fontSize: '9px',
                fontStyle: 'bold',
                color: '#5C7A8A'
            });
            count.setOrigin(0.5);
            btn.add(count);
            
            const hit = this.add.rectangle(0, 0, 40, 40, 0x000000, 0);
            hit.setInteractive({ useHandCursor: true });
            btn.add(hit);
            hit.on('pointerdown', () => this.selectSeed(seed.id));
            
            btn.bg = btnBg;
            btn.icon = icon;
            this.seedBtns.push(btn);
            this.seedSelector.add(btn);
        });
    }
    
    selectTool(toolId) {
        this.selectedTool = toolId;
        
        this.toolBtns.forEach(btn => {
            const sel = btn.toolId === toolId;
            btn.isSelected = sel;
            const r = 26;
            btn.bg.clear();
            if (sel) {
                btn.bg.fillStyle(C.leaf, 0.25);
                btn.bg.fillCircle(0, 0, r + 4);
                btn.bg.fillStyle(C.leaf, 1);
                btn.bg.fillCircle(0, 0, r);
            } else {
                btn.bg.fillStyle(C.hudShadow, 0.08);
                btn.bg.fillCircle(0, 0, r);
            }
            btn.label.setColor(sel ? '#264653' : '#5C7A8A');
        });
        
        if (this.seedSelector) {
            if (toolId === 'seed') {
                this.seedSelector.setVisible(true);
                this.tweens.add({
                    targets: this.seedSelector,
                    scaleX: 1, scaleY: 1, alpha: 1,
                    duration: 250, ease: 'Back.easeOut'
                });
            } else {
                this.tweens.add({
                    targets: this.seedSelector,
                    scaleX: 0.8, scaleY: 0.8, alpha: 0,
                    duration: 150,
                    onComplete: () => this.seedSelector.setVisible(false)
                });
            }
        }
    }
    
    selectSeed(cropId) {
        this.selectedCrop = cropId;
        
        this.seedBtns.forEach(btn => {
            const sel = btn.seedId === cropId;
            btn.bg.clear();
            btn.bg.fillStyle(sel ? C.leaf : C.hudShadow, sel ? 0.25 : 0.06);
            btn.bg.fillRoundedRect(-20, -20, 40, 40, 12);
        });
    }

    /* ==================== 光标反馈 ==================== */
    createCursor() {
        this.cursorIcon = this.add.text(0, 0, '', { fontSize: '20px' });
        this.cursorIcon.setDepth(200);
        this.cursorIcon.setVisible(false);
        
        this.cursorTip = this.add.graphics();
        this.cursorTip.setDepth(199);
        this.cursorTip.setVisible(false);
        
        this.cursorText = this.add.text(0, 0, '', {
            fontFamily: 'Nunito',
            fontSize: '11px',
            fontStyle: 'bold',
            color: '#FFFFFF'
        });
        this.cursorText.setDepth(200);
        this.cursorText.setVisible(false);
    }
    
    onPlotHover(id, isOver) {
        const plot = this.farmModel.getPlot(id);
        if (!plot) return;
        
        // 更新土地高亮
        const p = this.plots[id];
        const state = plot.isMature() ? 'mature' : plot.state;
        this.drawMound(p.mound, state, isOver);
        
        if (isOver) {
            let icon = '👆';
            let tip = '';
            
            if (plot.state === 'empty') {
                icon = '⛏️';
                tip = '点击开垦';
            } else if (plot.state === 'tilled') {
                icon = '🌱';
                tip = '选择种子种植';
            } else if (plot.isMature()) {
                icon = '🫴';
                tip = '点击收获！';
            } else {
                icon = '💧';
                tip = '浇水加速';
            }
            
            this.cursorIcon.setText(icon);
            this.cursorIcon.setVisible(true);
            
            if (tip) {
                this.cursorText.setText(tip);
                this.cursorText.setVisible(true);
                this.cursorText.setOrigin(0.5);
                
                const tw = this.cursorText.width + 16;
                this.cursorTip.clear();
                this.cursorTip.fillStyle(0x264653, 0.85);
                this.cursorTip.fillRoundedRect(
                    this.cursorText.x - tw / 2,
                    this.cursorText.y - 8,
                    tw, 22, 8
                );
                this.cursorTip.setVisible(true);
            }
        } else {
            this.cursorIcon.setVisible(false);
            this.cursorTip.setVisible(false);
            this.cursorText.setVisible(false);
        }
    }
    
    onPlotClick(id) {
        const plot = this.farmModel.getPlot(id);
        if (!plot) return;
        
        // 点击动画
        const p = this.plots[id];
        this.tweens.add({
            targets: p,
            x: p.x + 3,
            duration: 80, yoyo: true,
            ease: 'Power2'
        });
        
        // 显示浮动文字
        const texts = {
            empty: { text: '✨ 开垦中...', color: '#95D5B2' },
            tilled: { text: '🌱 已开垦', color: '#74C69D' },
            planted: { text: '🌿 种植成功', color: '#52B788' },
            mature: { text: '🎉 收获！', color: '#F4A261' }
        };
        
        let state = plot.state;
        if (plot.state === 'planted' && plot.isMature()) state = 'mature';
        const info = texts[state] || texts.empty;
        this.showFloatingText(info.text, p.x, p.y - 20, info.color);
        
        // 处理动作
        this.handleAction(id, plot);
    }
    
    handleAction(id, plot) {
        switch (plot.state) {
            case 'empty':
                if (this.selectedTool === 'hoe') this.farmModel.till(id);
                break;
            case 'tilled':
                if (this.selectedTool === 'seed') {
                    if (this.farmModel.getSeedCount(this.selectedCrop) > 0) {
                        this.farmModel.plant(id, this.selectedCrop);
                    } else {
                        this.showFloatingText('❌ 种子不足', this.plots[id].x, this.plots[id].y, '#E07A5F');
                    }
                }
                break;
            case 'planted':
                if (plot.isMature()) {
                    this.farmModel.harvest(id);
                } else if (this.selectedTool === 'water') {
                    this.farmModel.water(id);
                }
                break;
        }
        
        this.updateGoldDisplay();
    }
    
    showFloatingText(text, x, y, color = '#FFFFFF') {
        const msg = this.add.text(x, y, text, {
            fontFamily: 'Nunito',
            fontSize: '14px',
            fontStyle: 'bold',
            color: color,
            stroke: '#FFFFFF',
            strokeThickness: 3
        });
        msg.setOrigin(0.5);
        msg.setDepth(200);
        
        this.tweens.add({
            targets: msg,
            y: y - 40,
            alpha: 0,
            duration: 1200,
            ease: 'Power2',
            onComplete: () => msg.destroy()
        });
    }

    /* ==================== 数据回调 ==================== */
    onModelUpdate(event, data) {
        switch (event) {
            case 'data_loaded':
                this.syncPlots();
                this.updateGoldDisplay();
                break;
            case 'plot_updated':
                this.updateCrops();
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
        if (this.farmModel.plots.length > 0) this.syncPlots();
        await this.farmModel.loadFromServer();
        this.syncPlots();
        this.updateGoldDisplay();
    }
    
    update() {
        // 更新光标位置
        const ptr = this.input.activePointer;
        if (this.cursorIcon.visible) {
            this.cursorIcon.setPosition(ptr.x + 15, ptr.y - 15);
            this.cursorText.setPosition(ptr.x, ptr.y - 30);
            this.cursorTip.setPosition(ptr.x, ptr.y - 30);
        }
    }
}

window.GameScene = GameScene;
