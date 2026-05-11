// 恋爱至上主义区域 (Love Supremacy Zone) - 游戏状态管理
/**
 * NxSiran Game - State Machine
 * Reducer + Publish/Subscribe pattern (inspired by Sunflower Land)
 */
(function () {
    'use strict';

    // ── Constants ──────────────────────────────────────────────
    var CROP_STAGES = ['seed', 'sprout', 'growing', 'mature'];
    var CROP_GROWTH_TIMES = {
        tomato: 180, corn: 240, strawberry: 300, pumpkin: 360,
        watermelon: 420, potato: 120, carrot: 150, cabbage: 180
    };

    // ── Initial State ──────────────────────────────────────────
    var INITIAL_STATE = {
        status: 'loading',       // loading | playing | paused | error
        farm: {
            id: 0, name: '\u6211\u7684\u519C\u573A', money: 500,
            level: 1, exp: 0, gridWidth: 12, gridHeight: 8
        },
        player: { x: 0, y: 0, direction: 'down', frame: 0 },
        crops: {},               // { "x,y": { type, plantedAt, growthStage, waterLevel, harvestable } }
        inventory: {},           // { "seed_tomato": { type, name, quantity, emoji } }
        cropTypes: {},           // { "tomato": { name, growthTime, sellPrice, seedPrice, emoji } }
        npc: {},                 // { "chayewoon": { x, y, direction, name, location, activity } }
        weather: 'sunny',
        season: 'spring',
        gameDay: 1,
        gameHour: 8,
        gameMinute: 0,
        weatherEffects: {},
        hearts: 0,
        relationshipStatus: 'stranger',
        selectedTool: null,      // { type: 'seed'|'tool'|'harvest', item: 'tomato' }
        unlockedAreas: ['farm_center'],
        buildings: {},           // { "house": { x, y, type } }
        decorations: {},         // { "tree_1": { x, y, type } }
        lastSave: null,
        pendingActions: [],      // unsynced actions
        // 世界观相关状态
        worldLayer: 'stage',     // 当前世界层: stage(舞台)/shadow(阴影)/resonance(共鸣)
        emotionValues: {         // 角色情感值
            chayewoon: { affection: -20, happiness: 10, awakening: 0 }
        },
        awakenedCharacters: []   // 已觉醒角色ID列表
    };

    // ── State ──────────────────────────────────────────────────
    var _state = deepClone(INITIAL_STATE);
    var _listeners = new Set();
    var _history = [];

    // ── Reducer ────────────────────────────────────────────────
    function processEvent(state, action) {
        var s = deepClone(state);

        switch (action.type) {
            case 'LOAD_STATE':
                // Merge server state
                var keys = Object.keys(action.payload);
                for (var i = 0; i < keys.length; i++) {
                    var k = keys[i];
                    if (typeof action.payload[k] === 'object' && !Array.isArray(action.payload[k]) && action.payload[k] !== null) {
                        s[k] = deepClone(action.payload[k]);
                    } else {
                        s[k] = action.payload[k];
                    }
                }
                s.status = 'playing';
                break;

            case 'SELECT_TOOL':
                s.selectedTool = action.payload;
                break;

            case 'DESELECT_TOOL':
                s.selectedTool = null;
                break;

            case 'PLANT': {
                var key = action.x + ',' + action.y;
                if (s.crops[key]) break; // already planted
                s.crops[key] = {
                    type: action.cropType,
                    plantedAt: Date.now(),
                    growthStage: 0,
                    waterLevel: 0,
                    harvestable: false
                };
                // Remove seed from inventory
                var seedKey = 'seed_' + action.cropType;
                if (s.inventory[seedKey]) {
                    s.inventory[seedKey].quantity -= 1;
                    if (s.inventory[seedKey].quantity <= 0) delete s.inventory[seedKey];
                }
                s.pendingActions.push({ type: 'plant', x: action.x, y: action.y, cropType: action.cropType, ts: Date.now() });
                // v1.2e: Haptic feedback on plant
                if (window.GameMiniApp) GameMiniApp.hapticFeedback('light');
                break;
            }

            case 'HARVEST': {
                var hKey = action.x + ',' + action.y;
                var crop = s.crops[hKey];
                if (!crop || !crop.harvestable) break;
                // Add to inventory
                var cropKey = 'crop_' + crop.type;
                if (!s.inventory[cropKey]) {
                    s.inventory[cropKey] = { type: 'crop', name: getCropName(crop.type), quantity: 0, emoji: getCropEmoji(crop.type) };
                }
                s.inventory[cropKey].quantity += 1;
                delete s.crops[hKey];
                s.pendingActions.push({ type: 'harvest', x: action.x, y: action.y, cropType: crop.type, ts: Date.now() });
                // v1.2e: Haptic feedback on harvest
                if (window.GameMiniApp) GameMiniApp.hapticFeedback('light');
                break;
            }

            case 'WATER': {
                var wKey = action.x + ',' + action.y;
                var wCrop = s.crops[wKey];
                if (!wCrop) break;
                wCrop.waterLevel = Math.min(wCrop.waterLevel + 1, 3);
                s.pendingActions.push({ type: 'water', x: action.x, y: action.y, ts: Date.now() });
                // v1.2e: Haptic feedback on water
                if (window.GameMiniApp) GameMiniApp.hapticFeedback('light');
                break;
            }

            case 'MOVE_PLAYER':
                s.player.x = action.x;
                s.player.y = action.y;
                if (action.direction) s.player.direction = action.direction;
                break;

            case 'TICK': {
                // Advance game time: 1 tick = 1 game minute
                var newMinute = (s.gameMinute || 0) + 1;
                var newHour = s.gameHour || 8;
                if (newMinute >= 60) {
                    newMinute = 0;
                    newHour = (newHour + 1) % 24;
                    // Advance day when hour wraps to 0
                    if (newHour === 0) {
                        s.gameDay = (s.gameDay || 1) + 1;
                        // Season changes every 28 days
                        var seasons = ['spring', 'summer', 'autumn', 'winter'];
                        var seasonIdx = seasons.indexOf(s.season);
                        if (s.gameDay % 28 === 0) {
                            s.season = seasons[(seasonIdx + 1) % 4];
                        }
                    }
                }
                s.gameMinute = newMinute;
                s.gameHour = newHour;

                // Update crop growth with weather multiplier
                var now = Date.now();
                var cropKeys = Object.keys(s.crops);
                var weatherMultiplier = 1.0;
                if (s.weatherEffects && typeof s.weatherEffects.cropGrowthMultiplier === 'number') {
                    weatherMultiplier = s.weatherEffects.cropGrowthMultiplier;
                }
                for (var c = 0; c < cropKeys.length; c++) {
                    var cr = s.crops[cropKeys[c]];
                    var growthTime = (CROP_GROWTH_TIMES[cr.type] || 180) * 1000;
                    var elapsed = now - cr.plantedAt;
                    // Water speeds up growth by 50%
                    var speedMultiplier = 1 + (cr.waterLevel * 0.25);
                    // Apply weather effect
                    speedMultiplier *= weatherMultiplier;
                    var effectiveElapsed = elapsed * speedMultiplier;
                    var newStage = 0;
                    if (effectiveElapsed >= growthTime) newStage = 3;
                    else if (effectiveElapsed >= growthTime * 0.6) newStage = 2;
                    else if (effectiveElapsed >= growthTime * 0.2) newStage = 1;
                    cr.growthStage = newStage;
                    cr.harvestable = (newStage === 3);
                }
                break;
            }

            case 'UPDATE_MONEY':
                s.farm.money = action.amount;
                break;

            case 'UPDATE_HEARTS':
                s.hearts = action.hearts;
                if (action.status) s.relationshipStatus = action.status;
                break;

            case 'UPDATE_NPC':
                s.npc[action.payload.id] = action.payload;
                break;

            case 'UPDATE_WEATHER':
                s.weather = action.weather;
                // Apply weather effects if seasonal events module is available
                if (window.GameSeasonalEvents) {
                    var wEffect = GameSeasonalEvents.getWeatherEffect(action.weather);
                    s.weatherEffects = wEffect;
                }
                break;

            case 'SET_STATUS':
                s.status = action.status;
                break;

            case 'BUY_SEED': {
                var bSeedKey = 'seed_' + action.cropType;
                if (!s.inventory[bSeedKey]) {
                    s.inventory[bSeedKey] = { type: 'seed', name: getCropName(action.cropType) + '\u79CD\u5B50', quantity: 0, emoji: '\uD83C\uDF31' };
                }
                s.inventory[bSeedKey].quantity += action.quantity;
                s.farm.money -= action.cost;
                s.pendingActions.push({ type: 'buy_seed', cropType: action.cropType, quantity: action.quantity, cost: action.cost, ts: Date.now() });
                break;
            }

            case 'SELL_CROP': {
                var scKey = 'crop_' + action.cropType;
                if (s.inventory[scKey]) {
                    s.inventory[scKey].quantity -= action.quantity;
                    if (s.inventory[scKey].quantity <= 0) delete s.inventory[scKey];
                }
                s.farm.money += action.earned;
                s.pendingActions.push({ type: 'sell', cropType: action.cropType, quantity: action.quantity, earned: action.earned, ts: Date.now() });
                break;
            }

            case 'CLEAR_PENDING':
                s.pendingActions = [];
                s.lastSave = Date.now();
                break;

            case 'ERROR':
                s.status = 'error';
                s.error = action.message;
                break;

            case 'SWITCH_WORLD_LAYER':
                // 切换世界层: stage/shadow/resonance
                if (['stage', 'shadow', 'resonance'].indexOf(action.layer) !== -1) {
                    s.worldLayer = action.layer;
                }
                break;

            case 'UPDATE_EMOTION_VALUES':
                // 更新角色情感值
                if (action.characterId && s.emotionValues[action.characterId]) {
                    var emotions = s.emotionValues[action.characterId];
                    if (action.deltas) {
                        if (typeof action.deltas.affection === 'number') {
                            emotions.affection += action.deltas.affection;
                        }
                        if (typeof action.deltas.happiness === 'number') {
                            emotions.happiness += action.deltas.happiness;
                        }
                        if (typeof action.deltas.awakening === 'number') {
                            emotions.awakening += action.deltas.awakening;
                        }
                    }
                }
                break;

            case 'TRIGGER_AWAKENING':
                // 触发角色觉醒
                if (action.characterId) {
                    var idx = s.awakenedCharacters.indexOf(action.characterId);
                    if (idx === -1) {
                        s.awakenedCharacters.push(action.characterId);
                    }
                    // 设置觉醒状态为100
                    if (s.emotionValues[action.characterId]) {
                        s.emotionValues[action.characterId].awakening = 100;
                    }
                }
                break;

            // ── v0.7 Gift & Shop System ─────────────────────────
            case 'SPEND_MONEY':
                s.farm.money -= action.amount;
                s.pendingActions.push({ type: 'spend_money', amount: action.amount, ts: Date.now() });
                break;

            case 'ADD_INVENTORY_ITEM':
                if (action.key && action.item) {
                    s.inventory[action.key] = deepClone(action.item);
                    s.pendingActions.push({ type: 'add_inventory', key: action.key, item: action.item, ts: Date.now() });
                }
                break;

            case 'UPDATE_INVENTORY_ITEM':
                if (action.key && s.inventory[action.key] && action.updates) {
                    var uKeys = Object.keys(action.updates);
                    for (var u = 0; u < uKeys.length; u++) {
                        s.inventory[action.key][uKeys[u]] = action.updates[uKeys[u]];
                    }
                    s.pendingActions.push({ type: 'update_inventory', key: action.key, updates: action.updates, ts: Date.now() });
                }
                break;

            case 'REMOVE_INVENTORY_ITEM':
                if (action.key && s.inventory[action.key]) {
                    delete s.inventory[action.key];
                    s.pendingActions.push({ type: 'remove_inventory', key: action.key, ts: Date.now() });
                }
                break;

            case 'STAT_INCREMENT':
                if (!s.stats) s.stats = {};
                if (!s.stats[action.stat]) s.stats[action.stat] = 0;
                s.stats[action.stat] += action.amount || 1;
                break;
        }

        return s;
    }

    // ── Dispatch ───────────────────────────────────────────────
    function dispatch(action) {
        var prev = _state;
        _state = processEvent(_state, action);
        _history.push(action);

        // Notify listeners
        _listeners.forEach(function (fn) {
            try { fn(_state, prev, action); } catch (e) { console.error('[State] Listener error:', e); }
        });
    }

    // ── Subscribe ──────────────────────────────────────────────
    function subscribe(fn) {
        _listeners.add(fn);
        return function () { _listeners.delete(fn); };
    }

    // ── Getters ────────────────────────────────────────────────
    function getState() { return _state; }
    function getCropAt(x, y) { return _state.crops[x + ',' + y] || null; }
    function getSelectedTool() { return _state.selectedTool; }
    function getStatus() { return _state.status; }

    // ── Worldview Getters ──────────────────────────────────────
    function getEmotionValues(characterId) {
        return _state.emotionValues[characterId] || null;
    }

    function getWorldLayer() {
        return _state.worldLayer;
    }

    function isCharacterAwakened(characterId) {
        return _state.awakenedCharacters.indexOf(characterId) !== -1;
    }

    // ── Helpers ────────────────────────────────────────────────
    function getCropName(type) {
        var ct = _state.cropTypes[type];
        return ct ? ct.name : type;
    }

    function getCropEmoji(type) {
        var ct = _state.cropTypes[type];
        return ct ? ct.emoji : '\uD83C\uDF31';
    }

    function deepClone(obj) {
        if (obj === null || typeof obj !== 'object') return obj;
        try { return JSON.parse(JSON.stringify(obj)); } catch (e) { return obj; }
    }

    // ── Worldview Helpers ──────────────────────────────────────
    function updateEmotionValues(characterId, deltas) {
        dispatch({
            type: 'UPDATE_EMOTION_VALUES',
            characterId: characterId,
            deltas: deltas
        });
    }

    function switchWorldLayer(layer) {
        dispatch({
            type: 'SWITCH_WORLD_LAYER',
            layer: layer
        });
    }

    // ── Export ─────────────────────────────────────────────────
    window.GameState = {
        INITIAL_STATE: INITIAL_STATE,
        CROP_STAGES: CROP_STAGES,
        CROP_GROWTH_TIMES: CROP_GROWTH_TIMES,
        dispatch: dispatch,
        subscribe: subscribe,
        getState: getState,
        getCropAt: getCropAt,
        getSelectedTool: getSelectedTool,
        getStatus: getStatus,
        getCropName: getCropName,
        getCropEmoji: getCropEmoji,
        deepClone: deepClone,
        // 世界观相关方法
        getEmotionValues: getEmotionValues,
        updateEmotionValues: updateEmotionValues,
        getWorldLayer: getWorldLayer,
        switchWorldLayer: switchWorldLayer,
        isCharacterAwakened: isCharacterAwakened
    };
})();
