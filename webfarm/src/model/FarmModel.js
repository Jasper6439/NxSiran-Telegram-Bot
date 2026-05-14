/**
 * FarmModel.js - 农场数据管理层
 * 
 * 职责：
 * 1. 管理作物配置表
 * 2. 管理地块状态
 * 3. 客户端计算作物生长阶段
 * 4. 本地缓存 (localStorage)
 * 5. 与服务器同步
 * 
 * 设计原则：数据驱动、客户端计算、无状态服务器
 */

class Plot {
    /**
     * 地块类
     * @param {Object} data - 地块数据
     * @param {Object} cropConfig - 作物配置
     */
    constructor(data, cropConfig = {}) {
        this.id = data.id;
        this.x = data.x;
        this.y = data.y;
        this.state = data.state || 'empty'; // empty, tilled, planted, mature
        this.cropId = data.crop_id || null;
        this.plantedAt = data.planted_at ? new Date(data.planted_at) : null;
        this.watered = data.watered || false;
        this.cropConfig = cropConfig;
    }

    /**
     * 获取作物配置
     */
    getCropConfig() {
        if (!this.cropId) return null;
        return this.cropConfig[this.cropId] || null;
    }

    /**
     * 计算生长进度 (0-1)
     * 关键逻辑：客户端根据时间计算，不依赖服务器推送
     */
    getGrowthProgress() {
        if (!this.plantedAt || !this.cropId) return 0;
        
        const config = this.getCropConfig();
        if (!config) return 0;
        
        const elapsed = (Date.now() - this.plantedAt.getTime()) / 1000; // 秒
        const progress = Math.min(elapsed / config.growth_time, 1);
        
        return progress;
    }

    /**
     * 获取当前生长阶段
     * @returns {number} 阶段索引 (0-based)
     */
    getGrowthStage() {
        if (!this.plantedAt || !this.cropId) return 0;
        
        const config = this.getCropConfig();
        if (!config) return 0;
        
        const progress = this.getGrowthProgress();
        const stageCount = config.stages || 3;
        
        // 根据进度计算阶段
        if (progress >= 1) return stageCount - 1;
        return Math.floor(progress * stageCount);
    }

    /**
     * 检查作物是否成熟
     */
    isMature() {
        return this.getGrowthProgress() >= 1;
    }

    /**
     * 获取剩余成熟时间（秒）
     */
    getRemainingTime() {
        if (!this.plantedAt || !this.cropId) return 0;
        
        const config = this.getCropConfig();
        if (!config) return 0;
        
        const elapsed = (Date.now() - this.plantedAt.getTime()) / 1000;
        const remaining = config.growth_time - elapsed;
        
        return Math.max(0, remaining);
    }

    /**
     * 获取地块状态描述
     */
    getStatusText() {
        switch (this.state) {
            case 'empty':
                return '空地';
            case 'tilled':
                return '已开垦';
            case 'planted':
                if (this.isMature()) {
                    return '可以收获！';
                }
                const remaining = Math.ceil(this.getRemainingTime());
                return `生长中 (${remaining}秒)`;
            default:
                return '未知状态';
        }
    }

    /**
     * 转换为数据对象（用于保存）
     */
    toJSON() {
        return {
            id: this.id,
            x: this.x,
            y: this.y,
            state: this.state,
            crop_id: this.cropId,
            planted_at: this.plantedAt ? this.plantedAt.toISOString() : null,
            watered: this.watered
        };
    }
}


class FarmModel {
    /**
     * 农场数据管理器
     */
    constructor() {
        this.userId = 'player_1'; // TODO: 从认证系统获取
        this.apiBase = ''; // TODO: 配置 API 地址
        
        // 数据缓存
        this.farmData = null;
        this.cropConfig = {};
        this.plots = [];
        this.inventory = { seeds: {}, crops: {} };
        this.gold = 0;
        this.level = 1;
        this.exp = 0;
        
        // 监听器
        this.listeners = [];
        
        // 加载本地缓存
        this.loadFromLocal();
    }

    /**
     * 添加数据变化监听器
     * @param {Function} callback - 回调函数
     */
    addListener(callback) {
        this.listeners.push(callback);
    }

    /**
     * 触发数据变化事件
     */
    notifyListeners(event, data) {
        this.listeners.forEach(cb => {
            try {
                cb(event, data);
            } catch (e) {
                console.error('Listener error:', e);
            }
        });
    }

    /**
     * 从 localStorage 加载缓存
     */
    loadFromLocal() {
        try {
            const saved = localStorage.getItem(`farm_${this.userId}`);
            if (saved) {
                const data = JSON.parse(saved);
                this.applyServerData(data);
            }
        } catch (e) {
            console.error('Load from localStorage failed:', e);
        }
    }

    /**
     * 保存到 localStorage
     */
    saveToLocal() {
        try {
            const data = {
                farm: {
                    gold: this.gold,
                    level: this.level,
                    exp: this.exp,
                    plots: this.plots.map(p => p.toJSON()),
                    inventory: this.inventory,
                    updated_at: new Date().toISOString()
                },
                crop_config: this.cropConfig,
                cached_at: new Date().toISOString()
            };
            localStorage.setItem(`farm_${this.userId}`, JSON.stringify(data));
        } catch (e) {
            console.error('Save to localStorage failed:', e);
        }
    }

    /**
     * 应用服务器数据
     */
    applyServerData(data) {
        if (!data || !data.farm) return;

        this.farmData = data.farm;
        this.cropConfig = data.crop_config || {};
        this.gold = data.farm.gold || 0;
        this.level = data.farm.level || 1;
        this.exp = data.farm.exp || 0;
        this.inventory = data.farm.inventory || { seeds: {}, crops: {} };

        // 解析地块
        this.plots = (data.farm.plots || []).map(
            plotData => new Plot(plotData, this.cropConfig)
        );

        // 触发更新
        this.notifyListeners('data_loaded', this);
    }

    /**
     * 获取地块
     */
    getPlot(plotId) {
        return this.plots.find(p => p.id === plotId);
    }

    /**
     * 获取所有地块
     */
    getAllPlots() {
        return this.plots;
    }

    /**
     * 获取背包中的种子数量
     */
    getSeedCount(cropId) {
        return this.inventory.seeds?.[cropId] || 0;
    }

    /**
     * 获取背包中的作物数量
     */
    getCropCount(cropId) {
        return this.inventory.crops?.[cropId] || 0;
    }

    /**
     * 获取作物图标 Key
     */
    getCropTextureKey(cropId, stage = 0) {
        // 格式：crop_stage (如: corn_0, corn_1, corn_2)
        return `${cropId}_${stage}`;
    }

    /**
     * 更新地块状态
     */
    updatePlot(plotId, updates) {
        const plot = this.getPlot(plotId);
        if (!plot) return;

        Object.assign(plot, updates);
        this.saveToLocal();
        this.notifyListeners('plot_updated', plot);
    }

    /**
     * 更新金币
     */
    updateGold(delta) {
        this.gold += delta;
        this.saveToLocal();
        this.notifyListeners('gold_changed', { gold: this.gold, delta });
    }

    // ============== API 操作 ==============

    /**
     * 从服务器加载数据
     * 策略：先显示缓存，再异步更新
     */
    async loadFromServer() {
        try {
            // 1. 先显示缓存（同步）
            if (this.plots.length === 0) {
                console.log('FarmModel: No cached data, waiting for server...');
            }

            // 2. 异步请求服务器（同步本地缓存）
            const response = await fetch(`${this.apiBase}/api/farm?user_id=${this.userId}`);
            const result = await response.json();

            if (result.success) {
                this.applyServerData(result.data);
                this.saveToLocal();
                return true;
            } else {
                console.error('Load from server failed:', result.error);
                return false;
            }
        } catch (e) {
            console.error('Network error:', e);
            // 网络错误时使用缓存
            return false;
        }
    }

    /**
     * 执行动作
     */
    async performAction(action, params = {}) {
        try {
            const response = await fetch(`${this.apiBase}/api/action`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    user_id: this.userId,
                    action,
                    ...params
                })
            });

            const result = await response.json();

            if (result.success) {
                // 更新本地数据
                this.applyServerData({
                    farm: result.farm,
                    crop_config: result.crop_config
                });
                this.saveToLocal();
                this.notifyListeners('action_success', { action, result });
                return result;
            } else {
                this.notifyListeners('action_failed', { action, error: result.error });
                return result;
            }
        } catch (e) {
            console.error('Action failed:', e);
            return { success: false, error: '网络错误' };
        }
    }

    /**
     * 开垦土地
     */
    async till(plotId) {
        // 乐观更新
        const plot = this.getPlot(plotId);
        if (plot) {
            plot.state = 'tilled';
            this.notifyListeners('plot_updated', plot);
        }
        
        return this.performAction('till', { plot_id: plotId });
    }

    /**
     * 种植作物
     */
    async plant(plotId, cropId) {
        // 乐观更新
        const plot = this.getPlot(plotId);
        if (plot) {
            plot.state = 'planted';
            plot.cropId = cropId;
            plot.plantedAt = new Date();
            this.notifyListeners('plot_updated', plot);
        }
        
        return this.performAction('plant', { plot_id: plotId, crop_id: cropId });
    }

    /**
     * 收获作物
     */
    async harvest(plotId) {
        return this.performAction('harvest', { plot_id: plotId });
    }

    /**
     * 浇水
     */
    async water(plotId) {
        const plot = this.getPlot(plotId);
        if (plot) {
            plot.watered = true;
            this.notifyListeners('plot_updated', plot);
        }
        
        return this.performAction('water', { plot_id: plotId });
    }

    /**
     * 购买种子
     */
    async buySeed(cropId, count = 1) {
        return this.performAction('buy_seed', { crop_id: cropId, count });
    }

    /**
     * 出售作物
     */
    async sellCrop(cropId, count = 1) {
        return this.performAction('sell_crop', { crop_id: cropId, count });
    }
}


// 导出
window.FarmModel = FarmModel;
window.Plot = Plot;
