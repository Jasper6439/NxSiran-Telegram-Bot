/**
 * NxSiran Game - Settings Panel (v1.0)
 * Game settings with persistent localStorage storage
 */
(function () {
    'use strict';

    var VERSION = 'v1.0.0';
    var STORAGE_PREFIX = 'game_settings_';
    var panelEl = null;
    var backdropEl = null;
    var isOpen = false;

    // ── Default Settings ────────────────────────────────────────
    var DEFAULTS = {
        bgm_volume: 70,
        sfx_volume: 80,
        dark_theme: false,
        notifications: true
    };

    // ── Initialize ──────────────────────────────────────────────
    function init() {
        // Ensure default settings exist
        Object.keys(DEFAULTS).forEach(function (key) {
            if (loadSetting(key) === null) {
                saveSetting(key, DEFAULTS[key]);
            }
        });

        // v1.2c: Apply saved dark mode preference on load
        if (loadSetting('dark_theme') === true) {
            applyTheme(true);
        }

        createSettingsPanel();
        console.log('[Settings] Initialized');
    }

    // ── Create Settings Panel DOM ───────────────────────────────
    function createSettingsPanel() {
        // Backdrop
        backdropEl = document.createElement('div');
        backdropEl.className = 'settings-backdrop';
        backdropEl.addEventListener('click', function () {
            closeSettings();
        });

        // Panel
        panelEl = document.createElement('div');
        panelEl.className = 'settings-panel';
        panelEl.innerHTML =
            '<div class="settings-header">' +
            '<h3>设置</h3>' +
            '<button class="settings-close-btn" title="关闭">\u2715</button>' +
            '</div>' +
            '<div class="settings-body">' +

            // Audio section
            '<div class="settings-section">' +
            '<div class="settings-section-title">音频</div>' +
            '<div class="settings-row">' +
            '<span class="settings-label">\uD83D\uDD0A BGM 音量</span>' +
            '<div class="settings-control">' +
            '<input type="range" class="settings-slider" id="setting-bgm-volume" min="0" max="100" value="' + loadSetting('bgm_volume', 70) + '">' +
            '<span class="settings-slider-value" id="bgm-volume-value">' + loadSetting('bgm_volume', 70) + '%</span>' +
            '</div>' +
            '</div>' +
            '<div class="settings-row">' +
            '<span class="settings-label">\uD83D\uDD14 音效音量</span>' +
            '<div class="settings-control">' +
            '<input type="range" class="settings-slider" id="setting-sfx-volume" min="0" max="100" value="' + loadSetting('sfx_volume', 80) + '">' +
            '<span class="settings-slider-value" id="sfx-volume-value">' + loadSetting('sfx_volume', 80) + '%</span>' +
            '</div>' +
            '</div>' +
            '</div>' +

            // Display section
            '<div class="settings-section">' +
            '<div class="settings-section-title">显示</div>' +
            '<div class="settings-row">' +
            '<span class="settings-label">\uD83C\uDF19 暗色主题</span>' +
            '<div class="settings-control">' +
            '<label class="settings-toggle">' +
            '<input type="checkbox" id="setting-dark-theme" ' + (loadSetting('dark_theme', false) ? 'checked' : '') + '>' +
            '<span class="settings-toggle-slider"></span>' +
            '</label>' +
            '</div>' +
            '</div>' +
            '<div class="settings-row">' +
            '<span class="settings-label">\uD83D\uDCF1 通知</span>' +
            '<div class="settings-control">' +
            '<label class="settings-toggle">' +
            '<input type="checkbox" id="setting-notifications" ' + (loadSetting('notifications', true) ? 'checked' : '') + '>' +
            '<span class="settings-toggle-slider"></span>' +
            '</label>' +
            '</div>' +
            '</div>' +
            '</div>' +

            // Data section
            '<div class="settings-section">' +
            '<div class="settings-section-title">数据</div>' +
            '<div class="settings-row">' +
            '<span class="settings-label">\uD83D\uDDD1\uFE0F 清除存档</span>' +
            '<div class="settings-control">' +
            '<button class="settings-btn settings-btn-danger" id="setting-reset-data">清除</button>' +
            '</div>' +
            '</div>' +
            '</div>' +

            // About section
            '<div class="settings-section">' +
            '<div class="settings-section-title">关于</div>' +
            '<div class="settings-row">' +
            '<span class="settings-label">\u2139\uFE0F 版本</span>' +
            '<span class="settings-version">' + VERSION + '</span>' +
            '</div>' +
            '<div class="settings-row">' +
            '<span class="settings-label">\uD83C\uDFE0 游戏名称</span>' +
            '<span class="settings-version">恋爱至上主义区域</span>' +
            '</div>' +
            '</div>' +

            '</div>';

        // Bind events
        bindSettingsEvents();

        document.body.appendChild(backdropEl);
        document.body.appendChild(panelEl);
    }

    // ── Bind Settings Events ────────────────────────────────────
    function bindSettingsEvents() {
        // Close button
        var closeBtn = panelEl.querySelector('.settings-close-btn');
        closeBtn.addEventListener('click', function () {
            closeSettings();
        });

        // BGM volume slider
        var bgmSlider = panelEl.querySelector('#setting-bgm-volume');
        var bgmValue = panelEl.querySelector('#bgm-volume-value');
        bgmSlider.addEventListener('input', function () {
            var val = parseInt(this.value, 10);
            bgmValue.textContent = val + '%';
            saveSetting('bgm_volume', val);
            applyBGMVolume(val);
        });

        // SFX volume slider
        var sfxSlider = panelEl.querySelector('#setting-sfx-volume');
        var sfxValue = panelEl.querySelector('#sfx-volume-value');
        sfxSlider.addEventListener('input', function () {
            var val = parseInt(this.value, 10);
            sfxValue.textContent = val + '%';
            saveSetting('sfx_volume', val);
            applySFXVolume(val);
        });

        // Dark theme toggle
        var darkThemeToggle = panelEl.querySelector('#setting-dark-theme');
        darkThemeToggle.addEventListener('change', function () {
            saveSetting('dark_theme', this.checked);
            applyTheme(this.checked);
        });

        // Notifications toggle
        var notifToggle = panelEl.querySelector('#setting-notifications');
        notifToggle.addEventListener('change', function () {
            saveSetting('notifications', this.checked);
        });

        // Reset data button
        var resetBtn = panelEl.querySelector('#setting-reset-data');
        resetBtn.addEventListener('click', function () {
            handleResetData(resetBtn);
        });
    }

    // ── Apply BGM Volume ────────────────────────────────────────
    function applyBGMVolume(value) {
        if (window.GameAudio && typeof GameAudio.setBGMVolume === 'function') {
            GameAudio.setBGMVolume(value / 100);
        }
    }

    // ── Apply SFX Volume ────────────────────────────────────────
    function applySFXVolume(value) {
        if (window.GameAudio && typeof GameAudio.setSFXVolume === 'function') {
            GameAudio.setSFXVolume(value / 100);
        }
    }

    // ── Apply Theme ─────────────────────────────────────────────
    function applyTheme(isDark) {
        document.body.classList.toggle('dark-mode', isDark);
        document.body.classList.toggle('theme-dark', isDark);
        document.body.classList.toggle('theme-light', !isDark);
    }

    // ── Handle Reset Data (double confirmation) ─────────────────
    function handleResetData(btn) {
        if (btn.dataset.confirmState === 'second') {
            // Second confirmation - actually reset
            resetAllData();
            btn.textContent = '清除';
            btn.dataset.confirmState = '';
            btn.classList.remove('settings-btn-confirm');
            closeSettings();
            return;
        }

        if (btn.dataset.confirmState === 'first') {
            // Move to second confirmation
            btn.textContent = '再次点击确认';
            btn.dataset.confirmState = 'second';
            btn.classList.add('settings-btn-confirm');

            // Reset back after 3 seconds if not confirmed
            setTimeout(function () {
                if (btn.dataset.confirmState === 'second') {
                    btn.textContent = '清除';
                    btn.dataset.confirmState = '';
                    btn.classList.remove('settings-btn-confirm');
                }
            }, 3000);
            return;
        }

        // First click
        btn.textContent = '确定要清除？';
        btn.dataset.confirmState = 'first';
        btn.classList.add('settings-btn-confirm');

        // Reset back after 3 seconds
        setTimeout(function () {
            if (btn.dataset.confirmState === 'first') {
                btn.textContent = '清除';
                btn.dataset.confirmState = '';
                btn.classList.remove('settings-btn-confirm');
            }
        }, 3000);
    }

    // ── Open Settings ───────────────────────────────────────────
    function openSettings() {
        if (!panelEl) return;

        // v1.2a: Close other panels via panel manager
        if (window.GamePanels) GamePanels.open('settings');

        isOpen = true;
        backdropEl.classList.add('settings-backdrop-visible');
        panelEl.classList.add('settings-panel-open');
    }

    // ── Close Settings ──────────────────────────────────────────
    function closeSettings() {
        if (!panelEl) return;

        // v1.2a: Unregister from panel manager
        if (window.GamePanels) GamePanels.close('settings');

        isOpen = false;
        backdropEl.classList.remove('settings-backdrop-visible');
        panelEl.classList.remove('settings-panel-open');
    }

    // ── Save Setting ────────────────────────────────────────────
    function saveSetting(key, value) {
        try {
            localStorage.setItem(STORAGE_PREFIX + key, JSON.stringify(value));
        } catch (e) {
            console.warn('[Settings] Failed to save setting:', key);
        }
    }

    // ── Load Setting ────────────────────────────────────────────
    function loadSetting(key, defaultVal) {
        try {
            var stored = localStorage.getItem(STORAGE_PREFIX + key);
            if (stored === null) return defaultVal !== undefined ? defaultVal : null;
            return JSON.parse(stored);
        } catch (e) {
            return defaultVal !== undefined ? defaultVal : null;
        }
    }

    // ── Reset All Data ──────────────────────────────────────────
    function resetAllData() {
        try {
            // Clear all game-related localStorage
            var keysToRemove = [];
            for (var i = 0; i < localStorage.length; i++) {
                var key = localStorage.key(i);
                if (key.indexOf('game_') === 0 || key.indexOf('gameSettings') === 0) {
                    keysToRemove.push(key);
                }
            }
            keysToRemove.forEach(function (key) {
                localStorage.removeItem(key);
            });
            console.log('[Settings] All game data cleared');

            // Reload the page to reset game state
            setTimeout(function () {
                window.location.reload();
            }, 500);
        } catch (e) {
            console.warn('[Settings] Failed to reset data:', e);
        }
    }

    // ── Get Version ─────────────────────────────────────────────
    function getVersion() {
        return VERSION;
    }

    // ── Export ──────────────────────────────────────────────────
    window.GameSettings = {
        init: init,
        openSettings: openSettings,
        closeSettings: closeSettings,
        saveSetting: saveSetting,
        loadSetting: loadSetting,
        resetAllData: resetAllData,
        getVersion: getVersion
    };
})();
