/**
 * NxSiran Game - API Wrapper (v1.2f)
 * Central API interface for game backend communication
 * Extended for Love Supremacy Zone worldview
 * - 5 second timeout on all requests
 * - 401 auto-logout and redirect to login
 * - Network error graceful fallback
 * - Sync status indicator integration
 */
(function () {
    'use strict';

    var API_BASE = window.GAME_API_BASE || '';
    var API_TIMEOUT = 5000; // 5 seconds

    /**
     * Core request wrapper with timeout, error handling, and auth
     * @param {string} method - HTTP method
     * @param {string} path - API path
     * @param {object} data - Request body (optional)
     * @param {object} options - Extra options (skipAuth, skipTimeout)
     * @returns {Promise} Response data or throws on error
     */
    function request(method, path, data, options) {
        options = options || {};
        var opts = {
            method: method,
            headers: { 'Content-Type': 'application/json' }
        };

        // Attach Bearer token if available
        if (!options.skipAuth) {
            var token = localStorage.getItem('game_token');
            if (token) {
                opts.headers['Authorization'] = 'Bearer ' + token;
            }
        }

        if (data) opts.body = JSON.stringify(data);

        // Build fetch with AbortController for timeout
        var controller = new AbortController();
        var signal = controller.signal;
        opts.signal = signal;

        var timeoutId = null;
        if (!options.skipTimeout) {
            timeoutId = setTimeout(function () {
                controller.abort();
            }, API_TIMEOUT);
        }

        return fetch(API_BASE + path, opts)
            .then(function (res) {
                if (timeoutId) clearTimeout(timeoutId);

                // Handle 401 Unauthorized - clear token and show login
                if (res.status === 401) {
                    localStorage.removeItem('game_token');
                    if (window.updateSyncStatus) window.updateSyncStatus('none');
                    if (window.GameAuth) {
                        GameAuth.showLoginScreen();
                    }
                    throw new Error('登录已过期，请重新登录');
                }

                // Handle other HTTP errors
                if (res.status >= 500) {
                    throw new Error('服务器错误，请稍后再试');
                }

                return res.json();
            })
            .then(function (json) {
                if (!json.success) {
                    var errMsg = json.error || '请求失败';
                    throw new Error(errMsg);
                }
                return json;
            })
            .catch(function (err) {
                if (timeoutId) clearTimeout(timeoutId);

                // AbortError means timeout
                if (err.name === 'AbortError') {
                    throw new Error('网络超时，请检查网络连接');
                }

                // TypeError usually means network error (offline)
                if (err instanceof TypeError) {
                    if (window.updateSyncStatus) window.updateSyncStatus('offline');
                    throw new Error('网络连接失败，已切换到离线模式');
                }

                // Re-throw other errors (already have user-friendly messages)
                throw err;
            });
    }

    // ── Core Game APIs ─────────────────────────────────────────
    function getState() {
        return request('GET', '/api/game/state');
    }

    function plant(x, y, cropType) {
        return request('POST', '/api/game/plant', { x: x, y: y, crop_type: cropType });
    }

    function harvest(x, y) {
        return request('POST', '/api/game/harvest', { x: x, y: y });
    }

    function water(x, y) {
        return request('POST', '/api/game/water', { x: x, y: y });
    }

    function buySeed(cropType, quantity) {
        return request('POST', '/api/game/buy-seed', { crop_type: cropType, quantity: quantity || 1 });
    }

    function sellCrop(cropType, quantity) {
        return request('POST', '/api/game/sell', { crop_type: cropType, quantity: quantity || 1 });
    }

    function chat(npcId, message) {
        return request('POST', '/api/game/chat', { character_id: npcId, message: message });
    }

    function checkHeartEvents() {
        return request('GET', '/api/game/events/heart');
    }

    function triggerHeartEvent(eventId) {
        return request('POST', '/api/game/events/trigger', { event_id: eventId });
    }

    function move(x, y) {
        return request('POST', '/api/game/move', { x: x, y: y });
    }

    function sync(actions) {
        return request('POST', '/api/game/sync', { actions: actions });
    }

    // ── Worldview APIs (Love Supremacy Zone) ───────────────────

    /**
     * Get emotion values for a character
     * @param {string} characterId - Character ID
     * @returns {Promise} Emotion values (affection, happiness, awakening)
     */
    function getEmotionValues(characterId) {
        return request('GET', '/api/game/emotions/' + characterId);
    }

    /**
     * Check awakening conditions for a character
     * @param {string} characterId - Character ID
     * @returns {Promise} Awakening check result
     */
    function checkAwakening(characterId) {
        return request('GET', '/api/game/awakening/' + characterId);
    }

    /**
     * Trigger awakening event for a character
     * @param {string} characterId - Character ID
     * @returns {Promise} Awakening trigger result
     */
    function triggerAwakening(characterId) {
        return request('POST', '/api/game/awakening/' + characterId + '/trigger');
    }

    /**
     * Get current world state
     * @returns {Promise} World state including layer and available transitions
     */
    function getWorldState() {
        return request('GET', '/api/game/world/state');
    }

    /**
     * Switch world layer
     * @param {string} targetLayer - Target layer (stage/shadow/resonance)
     * @returns {Promise} Switch result
     */
    function switchWorldLayer(targetLayer) {
        return request('POST', '/api/game/world/switch', { target_layer: targetLayer });
    }

    /**
     * Get all awakened characters
     * @returns {Promise} List of awakened characters
     */
    function getAwakenedCharacters() {
        return request('GET', '/api/game/awakening/characters');
    }

    // ── Media Generation APIs (v0.3) ───────────────────────────

    /**
     * Generate AI selfie
     * @returns {Promise} Selfie image URL
     */
    function generateSelfie() {
        return request('POST', '/api/game/generate/selfie', {});
    }

    /**
     * Generate sticker by mood
     * @param {string} mood - Mood type (害羞/生气/开心/难过/想你/吃醋/撒娇)
     * @returns {Promise} Sticker image URL
     */
    function generateSticker(mood) {
        return request('POST', '/api/game/generate/sticker', { mood: mood });
    }

    /**
     * Generate scene image
     * @param {string} scene - Scene type (天台/房间/学校/田径场/街道/咖啡厅/日落)
     * @returns {Promise} Scene image URL
     */
    function generateScene(scene) {
        return request('POST', '/api/game/generate/scene', { scene: scene });
    }

    /**
     * Text to speech
     * @param {string} text - Text to convert (max 300 chars)
     * @returns {Promise} Audio URL and duration
     */
    function tts(text) {
        return request('POST', '/api/game/tts', { text: text });
    }

    // ── Auth APIs (v0.4) ────────────────────────────────────────

    /**
     * Register a new user
     * @param {string} username
     * @param {string} password
     * @param {string} chatId - Telegram Chat ID
     * @returns {Promise} Registration result with token
     */
    function register(username, password, chatId) {
        return request('POST', '/api/register', {
            username: username,
            password: password,
            chat_id: chatId
        });
    }

    /**
     * Login with username and password
     * @param {string} username
     * @param {string} password
     * @returns {Promise} Login result with token
     */
    function login(username, password) {
        return request('POST', '/api/login', {
            username: username,
            password: password
        });
    }

    /**
     * Logout - clear token from localStorage
     * @returns {boolean} true
     */
    function logout() {
        localStorage.removeItem('game_token');
        return true;
    }

    /**
     * Get current token from localStorage
     * @returns {string|null} Token or null
     */
    function getToken() {
        return localStorage.getItem('game_token') || null;
    }

    /**
     * Save token to localStorage
     * @param {string} token
     */
    function setToken(token) {
        localStorage.setItem('game_token', token);
    }

    /**
     * Check if user is logged in
     * @returns {boolean}
     */
    function isLoggedIn() {
        var token = localStorage.getItem('game_token');
        return !!token;
    }

    // ── Export ─────────────────────────────────────────────────
    window.GameAPI = {
        // Core APIs
        getState: getState,
        plant: plant,
        harvest: harvest,
        water: water,
        buySeed: buySeed,
        sellCrop: sellCrop,
        chat: chat,
        checkHeartEvents: checkHeartEvents,
        triggerHeartEvent: triggerHeartEvent,
        move: move,
        sync: sync,

        // Worldview APIs
        getEmotionValues: getEmotionValues,
        checkAwakening: checkAwakening,
        triggerAwakening: triggerAwakening,
        getWorldState: getWorldState,
        switchWorldLayer: switchWorldLayer,
        getAwakenedCharacters: getAwakenedCharacters,

        // Media APIs (v0.3)
        generateSelfie: generateSelfie,
        generateSticker: generateSticker,
        generateScene: generateScene,
        tts: tts,

        // Auth APIs (v0.4)
        register: register,
        login: login,
        logout: logout,
        getToken: getToken,
        setToken: setToken,
        isLoggedIn: isLoggedIn,

        // Utility (v1.2f)
        request: request
    };
})();
