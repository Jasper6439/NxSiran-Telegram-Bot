/**
 * GameScene.js - Phaser 3 游戏主场景
 * 
 * 特性：
 * 1. 移动端适配 (ScaleManager FIT 模式)
 * 2. 5x5 地块网格渲染
 * 3. 作物生长阶段显示
 * 4. 触摸/鼠标交互
 * 5. 客户端实时计算生长进度
 */

class GameScene extends Phaser.Scene {
    constructor() {
        super({ key: 'GameScene' });
        
        // 引用
        this.farmModel = null;
        this.plotSprites = [];
        this.selectedTool = 'hoe'; // hoe, seed, water
        this.selectedCrop = 'corn';
        this.uiContainer = null;
        this.goldText = null;
    }

    /**
     * 创建场景
     */
    create() {
        // 初始化农场模型
        this.farmModel = new FarmModel();
        this.farmModel.addListener(this.onModelUpdate.bind(this));
        
        // 加载数据
        this.loadGameData();
        
        // 绘制背景
        this.drawBackground();
        
        // 绘制地块网格
        this.drawPlotGrid();
        
        // 创建 UI
        this.createUI();
        
        // 设置输入
        this.setupInput();
        
        // 启动更新循环
        this.time.addEvent({
            delay: 1000,
            callback: this.updateGrowth,
            callbackScope: this,
            loop: true
        });
    }

    /**
     * 加载游戏数据
     */
    async loadGameData() {
        // 先尝试本地缓存
        if (this.farmModel.plots.length > 0) {
            this.syncPlotsToGraphics();
        }
        
        // 异步从服务器加载
        await this.farmModel.loadFromServer();
        this.syncPlotsToGraphics();
        this.updateGoldDisplay();
    }

    /**
     * 绘制背景
     */
    drawBackground() {
        // 草地背景
        const bg = this.add.graphics();
        bg.fillStyle(0x6b8e23, 1); // 草地绿
        bg.fillRect(0, 0, this.scale.width, this.scale.height);
        
        // 添加一些草地纹理
        for (let i = 0; i < 50; i++) {
            const x = Phaser.Math.Between(0, this.scale.width);
            const y = Phaser.Math.Between(0, this.scale.height);
            bg.fillStyle(0x5a7a1e, 0.3);
            bg.fillCircle(x, y, Phaser.Math.Between(2, 5));
        }
    }

    /**
     * 绘制地块网格
     */
    drawPlotGrid() {
        const gridSize = 5;
        const margin = 40; // 边距
        const spacing = Math.min(
            (this.scale.width - margin * 2) / gridSize,
            (this.scale.height - margin * 2 - 120) / gridSize // 减去底部工具栏
        );
        
        const gridWidth = spacing * gridSize;
        const gridHeight = spacing * gridSize;
        const startX = (this.scale.width - gridWidth) / 2;
        const startY = (this.scale.height - gridHeight - 100) / 2; // 居中
        
        // 存储网格信息
        this.gridInfo = {
            size: gridSize,
            spacing: spacing,
            startX: startX,
            startY: startY
        };
        
        // 创建地块容器
        this.plotContainer = this.add.container(0, 0);
        
        // 绘制每个地块
        for (let y = 0; y < gridSize; y++) {
            for (let x = 0; x < gridSize; x++) {
                const plotX = startX + x * spacing + spacing / 2;
                const plotY = startY + y * spacing + spacing / 2;
                const plotId = y * gridSize + x;
                
                this.createPlotSprite(plotId, plotX, plotY, spacing - 4);
            }
        }
    }

    /**
     * 创建单个地块 Sprite
     */
    createPlotSprite(plotId, x, y, size) {
        const container = this.add.container(x, y);
        
        // 地块背景
        const bg = this.add.graphics();
        bg.fillStyle(0x8B6914, 1); // 土壤色
        bg.fillRoundedRect(-size/2, -size/2, size, size, 8);
        bg.lineStyle(2, 0x6B4F0E, 1);
        bg.strokeRoundedRect(-size/2, -size/2, size, size, 8);
        
        container.add(bg);
        
        // 作物显示区域
        const cropSprite = this.add.graphics();
        cropSprite.plotId = plotId;
        container.add(cropSprite);
        
        // 进度条背景
        const progressBg = this.add.graphics();
        progressBg.fillStyle(0x000000, 0.3);
        progressBg.fillRoundedRect(-size/2 + 4, size/2 - 12, size - 8, 6, 3);
        progressBg.setVisible(false);
        container.add(progressBg);
        
        // 进度条
        const progressBar = this.add.graphics();
        progressBar.setVisible(false);
        container.add(progressBar);
        
        // 存储引用
        const plotData = {
            container,
            bg,
            cropSprite,
            progressBg,
            progressBar,
            size,
            plotId
        };
        
        this.plotSprites.push(plotData);
        
        // 使可交互
        const hitArea = this.add.rectangle(0, 0, size, size, 0x000000, 0);
        hitArea.setInteractive({ useHandCursor: true });
        container.add(hitArea);
        
        // 点击事件
        hitArea.on('pointerdown', () => this.onPlotClick(plotId));
        hitArea.on('pointerover', () => this.onPlotHover(plotId, true));
        hitArea.on('pointerout', () => this.onPlotHover(plotId, false));
        
        return plotData;
    }

    /**
     * 同步地块数据到图形
     */
    syncPlotsToGraphics() {
        this.plotSprites.forEach(ps => {
            const plot = this.farmModel.getPlot(ps.plotId);
            if (plot) {
                this.updatePlotVisual(ps, plot);
            }
        });
    }

    /**
     * 更新单个地块视觉
     */
    updatePlotVisual(ps, plot) {
        const config = plot.getCropConfig();
        
        // 清空作物图形
        ps.cropSprite.clear();
        
        // 根据状态绘制
        switch (plot.state) {
            case 'empty':
                // 空地：浅色边框
                ps.bg.clear();
                ps.bg.fillStyle(0x8B6914, 1);
                ps.bg.fillRoundedRect(-ps.size/2, -ps.size/2, ps.size, ps.size, 8);
                ps.bg.lineStyle(1, 0xA07830, 1);
                ps.bg.strokeRoundedRect(-ps.size/2, -ps.size/2, ps.size, ps.size, 8);
                ps.progressBg.setVisible(false);
                ps.progressBar.setVisible(false);
                break;
                
            case 'tilled':
                // 已开垦：深色边框
                ps.bg.clear();
                ps.bg.fillStyle(0x6B4F0E, 1);
                ps.bg.fillRoundedRect(-ps.size/2, -ps.size/2, ps.size, ps.size, 8);
                ps.bg.lineStyle(2, 0x5A3E0A, 1);
                ps.bg.strokeRoundedRect(-ps.size/2, -ps.size/2, ps.size, ps.size, 8);
                ps.progressBg.setVisible(false);
                ps.progressBar.setVisible(false);
                break;
                
            case 'planted':
                if (plot.isMature()) {
                    // 成熟：发光效果
                    ps.bg.clear();
                    ps.bg.fillStyle(0xFFD700, 1); // 金色
                    ps.bg.fillRoundedRect(-ps.size/2, -ps.size/2, ps.size, ps.size, 8);
                    ps.bg.lineStyle(3, 0xFFA500, 1);
                    ps.bg.strokeRoundedRect(-ps.size/2, -ps.size/2, ps.size, ps.size, 8);
                } else {
                    // 生长中
                    ps.bg.clear();
                    ps.bg.fillStyle(0x5A3E0A, 1); // 深土壤色
                    ps.bg.fillRoundedRect(-ps.size/2, -ps.size/2, ps.size, ps.size, 8);
                    ps.bg.lineStyle(2, 0x4A2E00, 1);
                    ps.bg.strokeRoundedRect(-ps.size/2, -ps.size/2, ps.size, ps.size, 8);
                }
                
                // 绘制作物
                this.drawCrop(ps.cropSprite, plot, ps.size);
                
                // 进度条
                if (!plot.isMature()) {
                    const progress = plot.getGrowthProgress();
                    ps.progressBg.setVisible(true);
                    ps.progressBar.setVisible(true);
                    ps.progressBar.clear();
                    ps.progressBar.fillStyle(0x4CAF50, 1);
                    ps.progressBar.fillRoundedRect(
                        -ps.size/2 + 4,
                        ps.size/2 - 12,
                        (ps.size - 8) * progress,
                        6, 3
                    );
                } else {
                    ps.progressBg.setVisible(false);
                    ps.progressBar.setVisible(false);
                }
                break;
        }
    }

    /**
     * 绘制作物
     */
    drawCrop(graphics, plot, size) {
        if (!plot.cropId) return;
        
        const stage = plot.getGrowthStage();
        const cropSize = size * 0.4 * (0.5 + stage * 0.25); // 阶段越高越大
        
        // 颜色映射
        const colors = {
            corn: { seed: 0x90EE90, grow: 0x228B22, mature: 0xFFD700 },
            wheat: { seed: 0x90EE90, grow: 0xDAA520, mature: 0xFFD700 },
            tomato: { seed: 0x90EE90, grow: 0xFF6347, mature: 0xDC143C },
            carrot: { seed: 0x90EE90, grow: 0xFFA500, mature: 0xFF4500 }
        };
        
        const color = colors[plot.cropId] || colors.corn;
        const currentColor = stage === 0 ? color.seed : 
                           stage === 1 ? color.grow : color.mature;
        
        // 绘制茎/作物
        graphics.fillStyle(currentColor, 1);
        
        switch (plot.cropId) {
            case 'corn':
                // 玉米：向上的茎
                graphics.fillRect(-2, -cropSize, 4, cropSize);
                if (stage > 0) {
                    graphics.fillEllipse(0, -cropSize - 5, 8, 12);
                }
                break;
                
            case 'wheat':
                // 小麦：麦穗
                graphics.fillRect(-1, -cropSize, 2, cropSize);
                if (stage > 0) {
                    graphics.fillEllipse(0, -cropSize - 3, 6, 8);
                }
                break;
                
            case 'tomato':
                // 番茄：圆球
                graphics.fillCircle(0, -cropSize/2, cropSize/2);
                break;
                
            case 'carrot':
                // 胡萝卜：三角形
                graphics.fillTriangle(
                    0, -cropSize,
                    -cropSize/2, cropSize/3,
                    cropSize/2, cropSize/3
                );
                break;
        }
        
        // 叶子
        if (stage > 0) {
            graphics.fillStyle(0x228B22, 1);
            graphics.fillEllipse(-cropSize/2, -cropSize/4, cropSize/3, cropSize/4);
            graphics.fillEllipse(cropSize/2, -cropSize/4, cropSize/3, cropSize/4);
        }
    }

    /**
     * 更新生长状态
     * 每秒调用，更新所有生长中的作物
     */
    updateGrowth() {
        this.plotSprites.forEach(ps => {
            const plot = this.farmModel.getPlot(ps.plotId);
            if (plot && plot.state === 'planted' && !plot.isMature()) {
                this.updatePlotVisual(ps, plot);
            }
        });
    }

    /**
     * 地块点击处理
     */
    async onPlotClick(plotId) {
        const plot = this.farmModel.getPlot(plotId);
        if (!plot) return;
        
        // 视觉效果：点击反馈
        this.tweens.add({
            targets: this.plotContainer.list.find(c => c.plotId === plotId),
            scaleX: 0.95,
            scaleY: 0.95,
            duration: 50,
            yoyo: true
        });
        
        // 根据当前工具和地块状态处理
        switch (plot.state) {
            case 'empty':
                // 空地 -> 开垦
                if (this.selectedTool === 'hoe') {
                    await this.farmModel.till(plotId);
                }
                break;
                
            case 'tilled':
                // 已开垦 -> 种植
                if (this.selectedTool === 'seed') {
                    if (this.farmModel.getSeedCount(this.selectedCrop) > 0) {
                        await this.farmModel.plant(plotId, this.selectedCrop);
                    } else {
                        this.showMessage('种子不足！');
                    }
                }
                break;
                
            case 'planted':
                if (plot.isMature()) {
                    // 成熟 -> 收获
                    await this.farmModel.harvest(plotId);
                    this.showMessage('收获成功！');
                } else {
                    // 未成熟 -> 浇水
                    if (this.selectedTool === 'water') {
                        await this.farmModel.water(plotId);
                        this.showMessage('浇水成功！');
                    }
                }
                break;
        }
        
        this.updateGoldDisplay();
    }

    /**
     * 地块悬停效果
     */
    onPlotHover(plotId, isOver) {
        const ps = this.plotSprites.find(p => p.plotId === plotId);
        if (!ps) return;
        
        const plot = this.farmModel.getPlot(plotId);
        
        // 高亮边框
        ps.bg.clear();
        if (isOver) {
            // 悬停：高亮边框
            ps.bg.fillStyle(plot.state === 'empty' ? 0x8B6914 : 
                           plot.state === 'tilled' ? 0x6B4F0E : 0x5A3E0A, 1);
            ps.bg.fillRoundedRect(-ps.size/2, -ps.size/2, ps.size, ps.size, 8);
            ps.bg.lineStyle(3, 0xFFFFFF, 0.8);
            ps.bg.strokeRoundedRect(-ps.size/2, -ps.size/2, ps.size, ps.size, 8);
        } else {
            // 恢复默认
            this.updatePlotVisual(ps, plot);
        }
        
        // 显示提示
        if (isOver && plot) {
            this.showTooltip(plot);
        } else {
            this.hideTooltip();
        }
    }

    /**
     * 创建 UI
     */
    createUI() {
        // 金币显示
        const goldBg = this.add.graphics();
        goldBg.fillStyle(0x000000, 0.5);
        goldBg.fillRoundedRect(this.scale.width/2 - 80, 15, 160, 36, 18);
        
        const coinIcon = this.add.text(this.scale.width/2 - 55, 23, '💰', { fontSize: '20px' });
        
        this.goldText = this.add.text(this.scale.width/2 - 30, 23, '100', {
            fontSize: '20px',
            fontFamily: 'Arial',
            color: '#FFD700',
            fontStyle: 'bold'
        });
        
        // 底部工具栏
        this.createToolbar();
    }

    /**
     * 创建工具栏
     */
    createToolbar() {
        const toolbarY = this.scale.height - 70;
        
        // 工具栏背景
        const toolbarBg = this.add.graphics();
        toolbarBg.fillStyle(0x000000, 0.7);
        toolbarBg.fillRoundedRect(20, toolbarY, this.scale.width - 40, 55, 12);
        
        // 工具按钮
        const tools = [
            { id: 'hoe', icon: '⛏️', label: '锄头' },
            { id: 'seed', icon: '🌱', label: '种子' },
            { id: 'water', icon: '💧', label: '浇水' }
        ];
        
        this.toolButtons = [];
        
        tools.forEach((tool, index) => {
            const x = 50 + index * 80;
            const btn = this.createToolButton(x, toolbarY + 28, tool, index === 0);
            this.toolButtons.push(btn);
        });
        
        // 种子选择器（当选择种子工具时显示）
        this.createSeedSelector(toolbarY);
    }

    /**
     * 创建工具按钮
     */
    createToolButton(x, y, tool, isSelected = false) {
        const container = this.add.container(x, y);
        
        // 按钮背景
        const bg = this.add.graphics();
        bg.fillStyle(isSelected ? 0x6B8E23 : 0x333333, 1);
        bg.fillRoundedRect(-30, -22, 60, 44, 10);
        container.add(bg);
        
        // 图标
        const icon = this.add.text(0, -8, tool.icon, { fontSize: '24px' });
        icon.setOrigin(0.5);
        container.add(icon);
        
        // 标签
        const label = this.add.text(0, 12, tool.label, {
            fontSize: '10px',
            color: '#FFFFFF'
        });
        label.setOrigin(0.5);
        container.add(label);
        
        // 使可点击
        const hitArea = this.add.rectangle(0, 0, 60, 44, 0x000000, 0);
        hitArea.setInteractive({ useHandCursor: true });
        container.add(hitArea);
        
        hitArea.on('pointerdown', () => {
            this.selectTool(tool.id);
        });
        
        // 存储引用
        container.toolData = tool;
        container.bg = bg;
        container.isSelected = isSelected;
        
        return container;
    }

    /**
     * 选择工具
     */
    selectTool(toolId) {
        this.selectedTool = toolId;
        
        // 更新按钮状态
        this.toolButtons.forEach(btn => {
            const isSelected = btn.toolData.id === toolId;
            btn.isSelected = isSelected;
            btn.bg.clear();
            btn.bg.fillStyle(isSelected ? 0x6B8E23 : 0x333333, 1);
            btn.bg.fillRoundedRect(-30, -22, 60, 44, 10);
        });
        
        // 显示/隐藏种子选择器
        if (this.seedSelector) {
            this.seedSelector.setVisible(toolId === 'seed');
        }
    }

    /**
     * 创建种子选择器
     */
    createSeedSelector(toolbarY) {
        this.seedSelector = this.add.container(this.scale.width / 2, toolbarY - 20);
        this.seedSelector.setVisible(false);
        
        const seeds = ['corn', 'wheat', 'tomato', 'carrot'];
        const icons = { corn: '🌽', wheat: '🌾', tomato: '🍅', carrot: '🥕' };
        
        seeds.forEach((seed, index) => {
            const x = (index - 1.5) * 50;
            const count = this.farmModel.getSeedCount(seed);
            
            const btn = this.add.container(x, 0);
            
            // 背景
            const bg = this.add.graphics();
            bg.fillStyle(count > 0 ? 0x333333 : 0x222222, 1);
            bg.fillCircle(0, 0, 22);
            btn.add(bg);
            
            // 图标
            const icon = this.add.text(0, -2, icons[seed], { fontSize: '24px' });
            icon.setOrigin(0.5);
            btn.add(icon);
            
            // 数量
            const countText = this.add.text(15, 10, `x${count}`, {
                fontSize: '10px',
                color: '#FFFFFF',
                backgroundColor: '#000000'
            });
            countText.setOrigin(0.5);
            btn.add(countText);
            
            // 点击
            const hitArea = this.add.circle(0, 0, 22, 0x000000, 0);
            hitArea.setInteractive({ useHandCursor: true });
            btn.add(hitArea);
            
            hitArea.on('pointerdown', () => {
                this.selectSeed(seed);
            });
            
            this.seedSelector.add(btn);
        });
    }

    /**
     * 选择种子
     */
    selectSeed(cropId) {
        this.selectedCrop = cropId;
        
        // 更新选择器高亮
        const seeds = ['corn', 'wheat', 'tomato', 'carrot'];
        this.seedSelector.each((btn, index) => {
            const isSelected = seeds[index] === cropId;
            btn.list[0].clear(); // 清除背景
            btn.list[0].fillStyle(isSelected ? 0x4CAF50 : 0x333333, 1);
            btn.list[0].fillCircle(0, 0, 22);
        });
    }

    /**
     * 更新金币显示
     */
    updateGoldDisplay() {
        if (this.goldText) {
            this.goldText.setText(String(this.farmModel.gold));
        }
    }

    /**
     * 显示消息
     */
    showMessage(text) {
        const msg = this.add.text(this.scale.width / 2, this.scale.height / 2, text, {
            fontSize: '24px',
            color: '#FFFFFF',
            backgroundColor: '#4CAF50',
            padding: { x: 20, y: 10 }
        });
        msg.setOrigin(0.5);
        msg.setAlpha(0);
        
        this.tweens.add({
            targets: msg,
            alpha: 1,
            y: msg.y - 30,
            duration: 300,
            onComplete: () => {
                this.tweens.add({
                    targets: msg,
                    alpha: 0,
                    delay: 1000,
                    onComplete: () => msg.destroy()
                });
            }
        });
    }

    /**
     * 显示提示
     */
    showTooltip(plot) {
        // TODO: 实现提示框
    }

    /**
     * 隐藏提示
     */
    hideTooltip() {
        // TODO: 隐藏提示框
    }

    /**
     * 数据更新回调
     */
    onModelUpdate(event, data) {
        switch (event) {
            case 'data_loaded':
                this.syncPlotsToGraphics();
                this.updateGoldDisplay();
                break;
            case 'plot_updated':
                const ps = this.plotSprites.find(p => p.plotId === data.id);
                if (ps) {
                    this.updatePlotVisual(ps, data);
                }
                break;
            case 'gold_changed':
                this.updateGoldDisplay();
                break;
        }
    }

    /**
     * 设置输入
     */
    setupInput() {
        // ESC 键返回
        this.input.keyboard.on('keydown-ESC', () => {
            // 关闭游戏或返回
            console.log('ESC pressed');
        });
    }
}


// 导出
window.GameScene = GameScene;
