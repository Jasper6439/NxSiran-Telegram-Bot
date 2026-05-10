/**
 * NxSiran Game - API Wrapper
 * Central API interface for game backend communication
 * Extended for Love Supremacy Zone worldview
 */
(function () {
    'use strict';

    var API_BASE = window.GAME_API_BASE || '';

    function request(method, path, data) {
        var opts = {
            method: method,
            headers: { 'Content-Type': 'application/json' }
        };
        if (data) opts.body = JSON.stringify(data);

        return fetch(API_BASE + path, opts)
            .then(function (res) { return res.json(); })
            .then(function (json) {
                if (!json.success) throw new Error(json.error || 'API Error');
                return json;
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
        tts: tts
    };
})();
