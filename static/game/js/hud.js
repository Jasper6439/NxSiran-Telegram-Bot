/**
 * NxSiran Game - HUD (Heads-Up Display)
 * Toast messages, toolbar, status display, world layer indicator, emotion panel
 */
(function () {
    'use strict';

    var _toastContainer = null;
    var _toastQueue = [];
    var MAX_TOASTS = 3;
    var _worldLayerIndicator = null;
    var _emotionPanel = null;

    function init() {
        _toastContainer = document.getElementById('toast-container');
        initWorldLayerIndicator();
        initEmotionPanel();
    }

    // ── World Layer Indicator (Worldview Feature) ──────────────
    function initWorldLayerIndicator() {
        _worldLayerIndicator = document.getElementById('world-layer-indicator');
        if (!_worldLayerIndicator) {
            _worldLayerIndicator = document.createElement('div');
            _worldLayerIndicator.id = 'world-layer-indicator';
            _worldLayerIndicator.className = 'world-layer-indicator';
            document.body.appendChild(_worldLayerIndicator);
        }
        updateWorldLayerDisplay();
    }

    function updateWorldLayerDisplay() {
        if (!_worldLayerIndicator) return;

        var state = GameState.getState();
        var layer = state.worldLayer || 'stage';

        var layerInfo = {
            stage: { name: '剧本区', emoji: '\uD83C\uDFAD', desc: '角色遵循剧本', class: 'layer-stage' },
            shadow: { name: '留白区', emoji: '\uD83C\uDF00', desc: '自由探索空间', class: 'layer-shadow' },
            resonance: { name: '共鸣层', emoji: '\u2728', desc: '深度情感连接', class: 'layer-resonance' }
        };

        var info = layerInfo[layer] || layerInfo.stage;

        _worldLayerIndicator.className = 'world-layer-indicator ' + info.class;
        _worldLayerIndicator.innerHTML =
            '<span class="layer-emoji">' + info.emoji + '</span>' +
            '<span class="layer-name">' + info.name + '</span>' +
            '<span class="layer-desc">' + info.desc + '</span>';
    }

    // ── Emotion Panel (Worldview Feature) ─────────────────────
    function initEmotionPanel() {
        _emotionPanel = document.getElementById('emotion-panel');
        if (!_emotionPanel) {
            _emotionPanel = document.createElement('div');
            _emotionPanel.id = 'emotion-panel';
            _emotionPanel.className = 'emotion-panel';
            document.body.appendChild(_emotionPanel);
        }
        updateEmotionPanel();
    }

    function updateEmotionPanel() {
        if (!_emotionPanel) return;

        var state = GameState.getState();
        var npcId = state.currentNPC || 'chayewoon'; // Default to chayewoon
        var emotions = state.emotionValues && state.emotionValues[npcId] || { affection: 0, happiness: 0, awakening: 0 };

        var affection = emotions.affection || 0;
        var happiness = emotions.happiness || 0;
        var awakening = emotions.awakening || 0;

        // Calculate bar widths (normalize to 0-100%)
        var affectionWidth = Math.max(0, Math.min(100, (affection + 50)));
        var happinessWidth = Math.max(0, Math.min(100, (happiness + 50)));
        var awakeningWidth = Math.max(0, Math.min(100, awakening));

        _emotionPanel.innerHTML =
            '<div class="emotion-panel-header">\uD83D\uDC96 \u60C5\u611F\u72B6\u6001</div>' +
            '<div class="emotion-item">' +
            '<span class="emotion-icon">\u2764\uFE0F</span>' +
            '<span class="emotion-name">\u597D\u611F\u5EA6</span>' +
            '<div class="emotion-progress">' +
            '<div class="emotion-progress-bar affection" style="width:' + affectionWidth + '%"></div>' +
            '</div>' +
            '<span class="emotion-value">' + affection + '</span>' +
            '</div>' +
            '<div class="emotion-item">' +
            '<span class="emotion-icon">\u2728</span>' +
            '<span class="emotion-name">\u5E78\u798F\u5EA6</span>' +
            '<div class="emotion-progress">' +
            '<div class="emotion-progress-bar happiness" style="width:' + happinessWidth + '%"></div>' +
            '</div>' +
            '<span class="emotion-value">' + happiness + '</span>' +
            '</div>' +
            '<div class="emotion-item">' +
            '<span class="emotion-icon">\uD83D\uDD2E</span>' +
            '<span class="emotion-name">\u89C9\u9192\u5EA6</span>' +
            '<div class="emotion-progress">' +
            '<div class="emotion-progress-bar awakening" style="width:' + awakeningWidth + '%"></div>' +
            '</div>' +
            '<span class="emotion-value">' + awakening + '%</span>' +
            '</div>';
    }

    // ── Toast Notifications ───────────────────────────────────
    function showToast(message, type, duration) {
        type = type || 'info';
        duration = duration || 2000;

        if (!_toastContainer) return;

        var toast = document.createElement('div');
        toast.className = 'game-toast toast-' + type;
        toast.textContent = message;
        _toastContainer.appendChild(toast);

        // Limit visible toasts
        var toasts = _toastContainer.querySelectorAll('.game-toast');
        if (toasts.length > MAX_TOASTS) {
            toasts[0].remove();
        }

        setTimeout(function () {
            toast.classList.add('toast-exit');
            setTimeout(function () { toast.remove(); }, 300);
        }, duration);
    }

    function updateToolbar() {
        if (window.GameInventory) GameInventory.updateToolbar();
    }

    function showEventHint(show) {
        var hint = document.getElementById('event-hint');
        if (hint) hint.style.display = show ? '' : 'none';
    }

    function updateWeatherDisplay() {
        var state = GameState.getState();
        var icon = document.getElementById('weather-icon');
        var name = document.getElementById('weather-name');
        if (icon) {
            var icons = { sunny: '\u2600\uFE0F', rainy: '\uD83C\uDF27\uFE0F', snowy: '\uD83C\uDF28\uFE0F', cloudy: '\u2601\uFE0F' };
            icon.textContent = icons[state.weather] || '\u2600\uFE0F';
        }
        if (name) {
            var names = { sunny: '\u6674\u5929', rainy: '\u96E8\u5929', snowy: '\u96EA\u5929', cloudy: '\u591A\u4E91' };
            name.textContent = names[state.weather] || '\u6674\u5929';
        }
    }

    function updateDayDisplay() {
        var state = GameState.getState();
        var dayEl = document.getElementById('game-day');
        var seasonEl = document.getElementById('game-season');
        if (dayEl) dayEl.textContent = '\u7B2C ' + state.gameDay + ' \u5929';
        if (seasonEl) {
            var seasonNames = { spring: '\u6625', summer: '\u590F', autumn: '\u79CB', winter: '\u51AC' };
            seasonEl.textContent = seasonNames[state.season] || '\u6625';
        }
    }

    // ── Subscribe to state changes ────────────────────────────
    if (window.GameState) {
        GameState.subscribe(function (state, prev, action) {
            switch (action.type) {
                case 'SWITCH_WORLD_LAYER':
                    updateWorldLayerDisplay();
                    showToast('\u5DF2\u8FDB\u5165\u3010' + getLayerName(state.worldLayer) + '\u3011', 'info', 3000);
                    break;
                case 'UPDATE_EMOTION_VALUES':
                    updateEmotionPanel();
                    break;
                case 'LOAD_STATE':
                    updateWorldLayerDisplay();
                    updateEmotionPanel();
                    break;
            }
        });
    }

    function getLayerName(layer) {
        var names = {
            stage: '\u5267\u672C\u533A',
            shadow: '\u7559\u767D\u533A',
            resonance: '\u5171\u9E23\u5C42'
        };
        return names[layer] || layer;
    }

    window.GameHUD = {
        init: init,
        showToast: showToast,
        updateToolbar: updateToolbar,
        showEventHint: showEventHint,
        updateWeatherDisplay: updateWeatherDisplay,
        updateDayDisplay: updateDayDisplay,
        updateWorldLayerDisplay: updateWorldLayerDisplay,
        updateEmotionPanel: updateEmotionPanel
    };
})();
