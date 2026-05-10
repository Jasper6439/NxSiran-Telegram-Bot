/**
 * NxSiran Mini App - Settings Page Module
 * Handles config loading/saving, character selection, about section.
 */
(function () {
    'use strict';

    /**
     * Initialize the settings page.
     */
    function init() {
        setupConfigForm();
        setupLogoutButton();
    }

    /**
     * Called when the settings page is entered.
     */
    function onPageEnter() {
        loadConfig();
        loadCharacters();
    }

    // ===== Load Config =====
    function loadConfig() {
        if (!window.Auth || !window.Auth.isLoggedIn) return;

        window.API.config.get().then(function (result) {
            if (result.success) {
                var cfg = result.config;
                var chatidEl = document.getElementById('cfg-chatid');
                var aibaseEl = document.getElementById('cfg-aibase');
                var publicurlEl = document.getElementById('cfg-publicurl');
                if (chatidEl) chatidEl.value = cfg.chat_id || '';
                if (aibaseEl) aibaseEl.value = cfg.ai_api_base || '';
                if (publicurlEl) publicurlEl.value = cfg.public_url || '';
            }
        }).catch(function (e) {
            console.error('\u52A0\u8F7D\u914D\u7F6E\u5931\u8D25', e);
        });
    }

    // ===== Save Config =====
    function setupConfigForm() {
        var saveBtn = document.querySelector('#admin-config-area .btn-primary');
        if (saveBtn) {
            // Remove inline onclick
            saveBtn.removeAttribute('onclick');
            saveBtn.addEventListener('click', saveConfig);
        }
    }

    function saveConfig() {
        var data = {};
        var token = document.getElementById('cfg-token');
        var chatid = document.getElementById('cfg-chatid');
        var aikey = document.getElementById('cfg-aikey');
        var aibase = document.getElementById('cfg-aibase');
        var publicurl = document.getElementById('cfg-publicurl');
        var newpass = document.getElementById('cfg-newpass');

        if (token && token.value) data.telegram_token = token.value;
        if (chatid && chatid.value) data.chat_id = chatid.value;
        if (aikey && aikey.value) data.ai_api_key = aikey.value;
        if (aibase && aibase.value) data.ai_api_base = aibase.value;
        if (publicurl && publicurl.value) data.public_url = publicurl.value;
        if (newpass && newpass.value) data.admin_password = newpass.value;

        if (Object.keys(data).length === 0) {
            window.Toast.show('\u6CA1\u6709\u8981\u4FDD\u5B58\u7684\u4FEE\u6539', 'info');
            return;
        }

        window.API.config.set(data).then(function (result) {
            if (result.success) {
                window.Toast.show(result.message || '\u914D\u7F6E\u5DF2\u4FDD\u5B58', 'success');
                if (token) token.value = '';
                if (aikey) aikey.value = '';
                if (newpass) newpass.value = '';
                if (publicurl && publicurl.value) {
                    window.Toast.show('\u670D\u52A1\u5668\u5730\u5740\u5DF2\u66F4\u65B0\uFF0C\u8BF7\u5237\u65B0 Mini App \u751F\u6548', 'success');
                }
            } else {
                window.Toast.show(result.error || '\u4FDD\u5B58\u5931\u8D25', 'error');
            }
        }).catch(function () {
            window.Toast.show('\u4FDD\u5B58\u5931\u8D25', 'error');
        });
    }

    // ===== Logout =====
    function setupLogoutButton() {
        var logoutBtn = document.getElementById('admin-config-area');
        if (!logoutBtn) return;

        var btn = logoutBtn.querySelector('.btn-clay-outline');
        if (btn) {
            btn.removeAttribute('onclick');
            btn.addEventListener('click', function () {
                if (window.Auth) window.Auth.logout();
                if (window.App) window.App.updateLoginUI(false);
            });
        }
    }

    // ===== Character System =====
    function loadCharacters() {
        var listDiv = document.getElementById('character-list');
        if (!listDiv) return;

        listDiv.innerHTML = '<div class="character-loading">\u52A0\u8F7D\u4E2D...</div>';

        window.API.characters.list().then(function (data) {
            if (!data.success) throw new Error(data.error);

            var characters = data.characters || [];
            var current = data.current;

            // Update global character ID
            if (window.GalleryPage) {
                window.GalleryPage.setCharacterId(current || '');
            }

            if (characters.length === 0) {
                listDiv.innerHTML = '<div class="character-loading">\u6682\u65E0\u53EF\u7528\u89D2\u8272</div>';
                return;
            }

            var esc = window.App ? window.App.escapeHtml : function (s) { return s; };
            var html = '';

            characters.forEach(function (char) {
                var isActive = char.id === current;
                var initial = char.name ? char.name.charAt(0) : '?';

                html += '<div class="character-item' + (isActive ? ' active' : '') + '" data-char-id="' + esc(char.id) + '">';
                html += '  <div class="character-avatar" style="background: ' + (char.theme_color || 'var(--gradient-purple)') + '">' + initial + '</div>';
                html += '  <div class="character-info">';
                html += '    <div class="character-name">' + esc(char.name) + '</div>';
                html += '    <div class="character-source">' + esc(char.source || '\u81EA\u5B9A\u4E49\u89D2\u8272') + '</div>';
                html += '  </div>';
                if (isActive) {
                    html += '  <svg class="character-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>';
                }
                html += '</div>';
            });

            listDiv.innerHTML = html;

            // Bind click events
            listDiv.querySelectorAll('.character-item').forEach(function (item) {
                item.addEventListener('click', function () {
                    var charId = this.getAttribute('data-char-id');
                    switchCharacter(charId);
                });
            });
        }).catch(function (error) {
            console.error('Load characters error:', error);
            listDiv.innerHTML = '<div class="character-loading">\u52A0\u8F7D\u5931\u8D25\uFF0C\u8BF7\u7A0D\u540E\u91CD\u8BD5</div>' +
                '<button class="btn-secondary" style="margin-top:8px" onclick="SettingsPage.loadCharacters()">\u91CD\u8BD5</button>';
        });
    }

    function switchCharacter(characterId) {
        window.API.characters.switch(characterId).then(function (result) {
            if (result.success) {
                window.Toast.show('\u5DF2\u5207\u6362\u5230: ' + (result.character && result.character.name ? result.character.name : characterId), 'success');
                loadCharacters();
            } else {
                window.Toast.show(result.error || '\u5207\u6362\u5931\u8D25', 'error');
            }
        }).catch(function () {
            window.Toast.show('\u5207\u6362\u5931\u8D25', 'error');
        });
    }

    // ===== Export =====
    window.SettingsPage = {
        init: init,
        onPageEnter: onPageEnter,
        loadConfig: loadConfig,
        loadCharacters: loadCharacters
    };
})();
