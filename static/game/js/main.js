/**
 * NxSiran Game - Main Entry Point
 * Initializes all game modules for Love Supremacy Zone
 */
(function () {
    'use strict';

    // ── Constants ──────────────────────────────────────────────
    var PIXEL_SCALE = 2.5;
    var SQUARE_WIDTH = 16;
    var GRID_WIDTH_PX = PIXEL_SCALE * SQUARE_WIDTH; // 40px
    var WORLD_SIZE = 30; // 30x30 grid
    var WORLD_PX = WORLD_SIZE * GRID_WIDTH_PX; // 1200px

    // ── DOM Ready ──────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', function () {
        var viewport = document.getElementById('game-viewport');
        var world = document.getElementById('game-world');

        if (!viewport || !world) {
            console.error('[Game] Missing viewport or world container');
            return;
        }

        // Set world size
        world.style.width = WORLD_PX + 'px';
        world.style.height = WORLD_PX + 'px';

        // Initialize modules (order matters)

        // Generate height map for 3D terrain
        var heightMap = GameTerrain.generateHeightMap(WORLD_SIZE, WORLD_SIZE, Math.random() * 10000);
        GameRenderer.setHeightMap(heightMap);

        GameRenderer.init(world, GRID_WIDTH_PX);
        GameViewport.init(viewport, world, GRID_WIDTH_PX);
        GameHUD.init();
        GameDialogue.init();
        GameEvents.init();
        GameInventory.init();
        GameAudio.init();

        // Keyboard controls
        document.addEventListener('keydown', onKeyDown);

        // Subscribe to state changes for re-rendering
        GameState.subscribe(function (state, prev, action) {
            switch (action.type) {
                case 'LOAD_STATE':
                    GameRenderer.renderFull(state);
                    GameInventory.updateUI();
                    GameHUD.updateWeatherDisplay();
                    GameHUD.updateDayDisplay();
                    GameHUD.updateWorldLayerDisplay();
                    GameHUD.updateEmotionPanel();
                    break;
                case 'TICK':
                    // Crops re-rendered by time.js
                    break;
                case 'UPDATE_WEATHER':
                    GameHUD.updateWeatherDisplay();
                    break;
                case 'UPDATE_EMOTION_VALUES':
                    // Update emotion bubbles when NPCs are nearby
                    if (window.GameNPC) GameNPC.updateEmotionBubbles();
                    break;
            }
        });

        // Load game state from server
        loadGame();

        // Start game systems
        GameTime.init();
        GameWeather.init();
        GameSync.init();

        // Random weather on load
        GameWeather.randomWeather();

        // Check heart events periodically
        setInterval(function () {
            if (window.GameEvents) GameEvents.checkEvents();
        }, 60000);

        // Update emotion bubbles periodically when near NPCs
        setInterval(function () {
            var state = GameState.getState();
            if (state.player && window.GameNPC) {
                GameNPC.updateEmotionBubbles();
            }
        }, 2000);

        console.log('[Game] Love Supremacy Zone initialized');
    });

    // ── Load Game ──────────────────────────────────────────────
    function loadGame() {
        GameState.dispatch({ type: 'SET_STATUS', status: 'loading' });

        if (window.GameAPI) {
            GameAPI.getState().then(function (data) {
                if (data) {
                    // Ensure worldview fields are present
                    var enhancedData = enhanceWorldviewData(data);
                    GameState.dispatch({ type: 'LOAD_STATE', payload: enhancedData });
                } else {
                    loadOfflineData();
                }
            }).catch(function (err) {
                console.warn('[Game] Failed to load from server, using offline data:', err);
                loadOfflineData();
            });
        } else {
            loadOfflineData();
        }
    }

    // ── Enhance Data with Worldview Fields ─────────────────────
    function enhanceWorldviewData(data) {
        // Add worldview fields if not present
        if (!data.worldLayer) {
            data.worldLayer = 'stage';
        }
        if (!data.emotionValues) {
            data.emotionValues = {
                chayewoon: { affection: -20, happiness: 10, awakening: 0 }
            };
        }
        if (!data.awakenedCharacters) {
            data.awakenedCharacters = [];
        }

        // Update NPC data with worldview info
        if (data.npc && data.npc.chayewoon) {
            data.npc.chayewoon.worldRole = 'novel_character';
            data.npc.chayewoon.novelTitle = '恋爱至上主义区域';
        }

        return data;
    }

    function loadOfflineData() {
        // Default game data for offline/demo mode with worldview integration
        var defaultData = {
            farm: { id: 1, name: '\u672A\u5B8C\u6210\u7684\u519C\u573A', money: 500, level: 1, exp: 0, gridWidth: 12, gridHeight: 8 },
            player: { x: 6, y: 4, direction: 'down', frame: 0 },
            crops: {},
            inventory: {
                'seed_tomato': { type: 'seed', name: '\u756A\u8304\u79CD\u5B50', quantity: 5, emoji: '\uD83C\uDF31' },
                'seed_corn': { type: 'seed', name: '\u7389\u7C73\u79CD\u5B50', quantity: 3, emoji: '\uD83C\uDF31' },
                'seed_strawberry': { type: 'seed', name: '\u8349\u8393\u79CD\u5B50', quantity: 2, emoji: '\uD83C\uDF31' }
            },
            cropTypes: {
                tomato: { name: '\u756A\u8304', growthTime: 180, sellPrice: 50, seedPrice: 20, emoji: '\uD83C\uDF45' },
                corn: { name: '\u7389\u7C73', growthTime: 240, sellPrice: 80, seedPrice: 30, emoji: '\uD83C\uDF3D' },
                strawberry: { name: '\u8349\u8393', growthTime: 300, sellPrice: 120, seedPrice: 50, emoji: '\uD83C\uDF53' },
                pumpkin: { name: '\u5357\u74DC', growthTime: 360, sellPrice: 150, seedPrice: 40, emoji: '\uD83C\uDF83' },
                watermelon: { name: '\u897F\u74DC', growthTime: 420, sellPrice: 200, seedPrice: 60, emoji: '\uD83C\uDF49' },
                potato: { name: '\u571F\u8C46', growthTime: 120, sellPrice: 30, seedPrice: 10, emoji: '\uD83E\uDD54' },
                carrot: { name: '\u80E1\u841D\u535C', growthTime: 150, sellPrice: 35, seedPrice: 15, emoji: '\uD83E\uDD55' },
                cabbage: { name: '\u767D\u83DC', growthTime: 180, sellPrice: 40, seedPrice: 15, emoji: '\uD83E\uDD66' }
            },
            npc: {
                chayewoon: {
                    x: 9, y: 6, direction: 'down',
                    name: '\u8F66\u5982\u4E91',
                    location: '\u7559\u767D\u533A',
                    activity: '\u601D\u8003',
                    worldRole: 'novel_character',
                    novelTitle: '\u604B\u7231\u81F3\u4E0A\u4E3B\u4E49\u533A\u57DF',
                    awakeningLevel: 0
                }
            },
            weather: 'sunny',
            season: 'spring',
            gameDay: 1,
            hearts: 0,
            relationshipStatus: 'stranger',

            // Worldview fields
            worldLayer: 'stage',
            emotionValues: {
                chayewoon: { affection: -20, happiness: 10, awakening: 0 }
            },
            awakenedCharacters: [],

            buildings: {
                house: { x: 0, y: 8, type: 'house' },
                barn: { x: 12, y: 8, type: 'barn' }
            },
            decorations: {
                tree1: { x: -1, y: 6, type: 'tree' },
                tree2: { x: 13, y: 5, type: 'tree' },
                tree3: { x: 1, y: 0, type: 'tree' },
                flower1: { x: 2, y: 9, type: 'flower_red' },
                flower2: { x: 10, y: -1, type: 'flower_yellow' },
                rock1: { x: 14, y: 7, type: 'rock' }
            },
            selectedTool: null,
            unlockedAreas: ['farm_center'],
            pendingActions: []
        };

        GameState.dispatch({ type: 'LOAD_STATE', payload: defaultData });
        GameState.dispatch({ type: 'SET_STATUS', status: 'playing' });

        // Hide loading screen
        var loading = document.getElementById('loading-screen');
        if (loading) loading.style.display = 'none';

        // Show welcome toast
        if (window.GameHUD) {
            setTimeout(function () {
                GameHUD.showToast('\uD83D\uDC96 \u6B22\u8FCE\u6765\u5230\u604B\u7231\u81F3\u4E0A\u4E3B\u4E49\u533A\u57DF\uFF01', 'special', 4000);
            }, 1000);
        }
    }

    // ── Keyboard Controls ─────────────────────────────────────
    function onKeyDown(e) {
        // Don't capture when typing in inputs
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

        switch (e.key) {
            case 'ArrowUp':
            case 'w':
            case 'W':
                e.preventDefault();
                if (window.GameActions) GameActions.movePlayer('up');
                break;
            case 'ArrowDown':
            case 's':
            case 'S':
                e.preventDefault();
                if (window.GameActions) GameActions.movePlayer('down');
                break;
            case 'ArrowLeft':
            case 'a':
            case 'A':
                e.preventDefault();
                if (window.GameActions) GameActions.movePlayer('left');
                break;
            case 'ArrowRight':
            case 'd':
            case 'D':
                e.preventDefault();
                if (window.GameActions) GameActions.movePlayer('right');
                break;
            case 'Escape':
                if (window.GameDialogue) GameDialogue.close();
                if (window.GameInventory) { GameInventory.closeShop(); GameInventory.closeInventory(); }
                if (window.GameActions) GameActions.deselectTool();
                break;
            case '1':
                if (window.GameActions) GameActions.selectTool('tool', 'watering_can');
                break;
            case '2':
                if (window.GameActions) GameActions.selectTool('harvest', null);
                break;
            case 'l':
            case 'L':
                // Debug: Switch world layer
                if (e.shiftKey) {
                    e.preventDefault();
                    var state = GameState.getState();
                    var layers = ['stage', 'shadow', 'resonance'];
                    var currentIdx = layers.indexOf(state.worldLayer || 'stage');
                    var nextLayer = layers[(currentIdx + 1) % layers.length];
                    GameState.dispatch({ type: 'SWITCH_WORLD_LAYER', payload: nextLayer });
                }
                break;
        }
    }

    // ── Export Constants ───────────────────────────────────────
    window.GameConstants = {
        PIXEL_SCALE: PIXEL_SCALE,
        SQUARE_WIDTH: SQUARE_WIDTH,
        GRID_WIDTH_PX: GRID_WIDTH_PX,
        WORLD_SIZE: WORLD_SIZE,
        WORLD_PX: WORLD_PX
    };
})();
