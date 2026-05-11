/**
 * NxSiran Game - Main Entry Point (v1.2f)
 * Initializes all game modules for Love Supremacy Zone
 */
(function () {
    'use strict';

    // ── Sync Status Indicator (v1.2f) ──────────────────────────
    function updateSyncStatus(status) {
        var indicator = document.getElementById('sync-indicator');
        if (!indicator) {
            indicator = document.createElement('span');
            indicator.id = 'sync-indicator';
            indicator.style.cssText = 'width:8px;height:8px;border-radius:50%;display:inline-block;margin-left:8px;';
            var hudRight = document.querySelector('.hud-right');
            if (hudRight) hudRight.appendChild(indicator);
        }
        var colors = { synced: '#30D158', syncing: '#FF9F0A', offline: '#FF3B30', none: '#AEAEB2' };
        indicator.style.backgroundColor = colors[status] || colors.none;
    }
    window.updateSyncStatus = updateSyncStatus;

    // ── Panel Manager (v1.2a) ──────────────────────────────────
    // Ensures only one panel is open at a time
    window.GamePanels = {
        _openPanels: new Set(),
        _registry: {},

        register: function (panelId, closeFn) {
            this._registry[panelId] = closeFn;
        },

        open: function (panelId) {
            // Close all other panels first
            var self = this;
            this._openPanels.forEach(function (openId) {
                if (openId !== panelId && self._registry[openId]) {
                    self._registry[openId]();
                }
            });
            this._openPanels.clear();
            this._openPanels.add(panelId);
        },

        close: function (panelId) {
            this._openPanels.delete(panelId);
        },

        closeAll: function () {
            var self = this;
            this._openPanels.forEach(function (openId) {
                if (self._registry[openId]) {
                    self._registry[openId]();
                }
            });
            this._openPanels.clear();
        },

        isOpen: function (panelId) {
            return this._openPanels.has(panelId);
        }
    };

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

        // Initialize Telegram MiniApp integration (v1.2e)
        if (window.GameMiniApp) GameMiniApp.init();

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

        // Initialize story engine (v0.5)
        if (window.GameStory) {
            GameStory.init();
        }

        // Initialize quests & achievements system (v0.6)
        if (window.GameQuests) {
            GameQuests.init();
        }

        // Initialize seasonal & weather events system (v0.8)
        if (window.GameSeasonalEvents) {
            GameSeasonalEvents.init();
        }

        // Initialize character schedule system (v0.8)
        if (window.GameSchedule) {
            GameSchedule.init();
        }

        // Initialize settings panel (v1.0)
        if (window.GameSettings) {
            GameSettings.init();
        }

        // Add logout button to HUD
        addLogoutButton();

        // Add audio toggle button to HUD (v0.9)
        addAudioButton();

        // Add settings button to HUD (v1.0)
        addSettingsButton();

        // Start BGM if not muted (v0.9)
        if (window.GameAudio && !GameAudio.isMuted()) {
            // Delay BGM start to allow user interaction for AudioContext
            var bgmStarted = false;
            var startBGMOnInteraction = function () {
                if (!bgmStarted && window.GameAudio) {
                    bgmStarted = true;
                    GameAudio.playBGM('main');
                }
                document.removeEventListener('click', startBGMOnInteraction);
                document.removeEventListener('touchstart', startBGMOnInteraction);
            };
            document.addEventListener('click', startBGMOnInteraction);
            document.addEventListener('touchstart', startBGMOnInteraction);
        }

        // Update audio button UI state (v0.9)
        if (window.GameAudio) {
            GameAudio.updateAudioButtonUI();
        }

        // Add story button to action buttons (v0.5)
        addStoryButton();

        // Add quests button to action buttons (v0.6)
        addQuestsButton();

        // Initialize auth module
        if (window.GameAuth) {
            GameAuth.init();
        }

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
                    // v0.8: Update schedule indicator on state load
                    if (window.GameSchedule) GameSchedule.updateScheduleDisplay();
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
                case 'UPDATE_NPC':
                    // v0.8: Update schedule indicator when NPC state changes
                    if (window.GameSchedule) GameSchedule.updateScheduleDisplay();
                    break;
            }
        });

        // Load game state from server
        loadGame();

        // Start game systems
        GameTime.init();
        GameWeather.init();

        // Only init sync if user is already logged in
        // (if not logged in, sync will be initialized after login in auth.js)
        if (window.GameSync && window.GameAPI && GameAPI.isLoggedIn()) {
            GameSync.init();
        }

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

    // ── Add Logout Button ──────────────────────────────────────
    function addLogoutButton() {
        var hud = document.getElementById('game-hud');
        if (!hud) return;

        var logoutBtn = document.createElement('button');
        logoutBtn.className = 'auth-logout-btn';
        logoutBtn.title = '\u767B\u51FA';
        logoutBtn.textContent = '\uD83D\uDEAA';
        logoutBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (window.GameAuth) {
                GameAuth.handleLogout();
            }
        });

        hud.appendChild(logoutBtn);
    }

    // ── Add Audio Toggle Button (v0.9) ─────────────────────────
    function addAudioButton() {
        var hud = document.getElementById('game-hud');
        if (!hud) return;

        var audioBtn = document.createElement('button');
        audioBtn.id = 'audio-toggle-btn';
        audioBtn.className = 'audio-btn';
        audioBtn.title = '\u97F3\u9891\u5F00\u5173';
        audioBtn.textContent = window.GameAudio && GameAudio.isMuted() ? '\uD83D\uDD07' : '\uD83D\uDD0A';
        audioBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (window.GameAudio) {
                var muted = GameAudio.toggleMute();
                if (muted) {
                    GameAudio.stopBGM();
                } else {
                    GameAudio.playBGM('main');
                }
            }
        });

        // Insert before logout button
        var logoutBtn = hud.querySelector('.auth-logout-btn');
        if (logoutBtn) {
            hud.insertBefore(audioBtn, logoutBtn);
        } else {
            hud.appendChild(audioBtn);
        }
    }

    // ── Add Settings Button (v1.0) ─────────────────────────────
    function addSettingsButton() {
        var hud = document.getElementById('game-hud');
        if (!hud) return;

        var settingsBtn = document.createElement('button');
        settingsBtn.id = 'settings-toggle-btn';
        settingsBtn.className = 'settings-hud-btn';
        settingsBtn.title = '\u8BBE\u7F6E';
        settingsBtn.textContent = '\u2699\uFE0F';
        settingsBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (window.GameSettings) {
                GameSettings.openSettings();
            }
        });

        // Insert before audio button
        var audioBtn = hud.querySelector('#audio-toggle-btn');
        if (audioBtn) {
            hud.insertBefore(settingsBtn, audioBtn);
        } else {
            var logoutBtn = hud.querySelector('.auth-logout-btn');
            if (logoutBtn) {
                hud.insertBefore(settingsBtn, logoutBtn);
            } else {
                hud.appendChild(settingsBtn);
            }
        }
    }

    // ── Add Story Button (v0.5) ───────────────────────────────
    function addStoryButton() {
        var actionBtns = document.getElementById('action-buttons');
        if (!actionBtns) return;

        var storyBtn = document.createElement('button');
        storyBtn.className = 'action-fab';
        storyBtn.title = '\u5267\u60C5';
        storyBtn.textContent = '\uD83D\uDCD6';
        storyBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (window.GameStory) {
                GameStory.openChapterSelect();
            }
        });

        // Insert before shop button
        actionBtns.insertBefore(storyBtn, actionBtns.firstChild);
    }

    // ── Add Quests Button (v0.6) ──────────────────────────────
    function addQuestsButton() {
        var actionBtns = document.getElementById('action-buttons');
        if (!actionBtns) return;

        var questsBtn = document.createElement('button');
        questsBtn.className = 'action-fab quest-btn';
        questsBtn.title = '\u6BCF\u65E5\u4EFB\u52A1';
        questsBtn.textContent = '\uD83D\uDCCB';
        questsBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (window.GameQuests) {
                GameQuests.togglePanel();
            }
        });

        // Insert before shop button
        actionBtns.insertBefore(questsBtn, actionBtns.firstChild);
    }

    // ── Load Game ──────────────────────────────────────────────
    function loadGame() {
        GameState.dispatch({ type: 'SET_STATUS', status: 'loading' });

        // Check if user is logged in before attempting server load
        var loggedIn = false;
        if (window.GameAuth && typeof GameAuth.isLoggedIn === 'function') {
            loggedIn = GameAuth.isLoggedIn();
        } else if (window.GameAPI && typeof GameAPI.isLoggedIn === 'function') {
            loggedIn = GameAPI.isLoggedIn();
        }

        if (!loggedIn) {
            // Not logged in, use offline data only
            console.log('[Game] User not logged in, using offline data');
            if (window.updateSyncStatus) window.updateSyncStatus('none');
            loadOfflineData();
            return;
        }

        if (window.GameAPI) {
            if (window.updateSyncStatus) window.updateSyncStatus('syncing');
            GameAPI.getState().then(function (data) {
                if (data) {
                    // Ensure worldview fields are present
                    var enhancedData = enhanceWorldviewData(data);
                    GameState.dispatch({ type: 'LOAD_STATE', payload: enhancedData });
                    if (window.updateSyncStatus) window.updateSyncStatus('synced');
                } else {
                    loadOfflineData();
                }
            }).catch(function (err) {
                console.warn('[Game] Failed to load from server, using offline data:', err);
                if (window.updateSyncStatus) window.updateSyncStatus('offline');
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
            gameHour: 8,
            gameMinute: 0,
            weatherEffects: {},
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

        // Initialize tutorial for new players (v1.0)
        if (window.GameTutorial) {
            GameTutorial.init();
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
