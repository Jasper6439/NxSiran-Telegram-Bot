/**
 * NxSiran Game - Authentication Module (v1.2f)
 * Login/Register overlay with Korean BL drama aesthetic
 * - Proper backend API integration
 * - Inline error messages (no alert())
 * - Offline fallback support
 * - Sync status indicator integration
 */
(function () {
    'use strict';

    var overlayEl = null;
    var currentTab = 'login';

    // ── Initialize ─────────────────────────────────────────────
    function init() {
        if (isLoggedIn()) {
            // Already logged in, hide login screen
            hideLoginScreen();
            // Update sync status
            if (window.updateSyncStatus) window.updateSyncStatus('synced');
        } else {
            // Not logged in, show login screen
            showLoginScreen();
            if (window.updateSyncStatus) window.updateSyncStatus('none');
        }
    }

    // ── Check Login State ──────────────────────────────────────
    function isLoggedIn() {
        if (window.GameAPI && typeof GameAPI.isLoggedIn === 'function') {
            return GameAPI.isLoggedIn();
        }
        return !!localStorage.getItem('game_token');
    }

    // ── Show Login Screen ──────────────────────────────────────
    function showLoginScreen() {
        // Remove existing overlay if any
        hideLoginScreen();

        currentTab = 'login';

        // Create overlay element
        overlayEl = document.createElement('div');
        overlayEl.className = 'auth-overlay auth-fade-in';
        overlayEl.innerHTML = buildOverlayHTML();
        document.body.appendChild(overlayEl);

        // Bind events
        bindEvents();
    }

    // ── Hide Login Screen ──────────────────────────────────────
    function hideLoginScreen() {
        if (!overlayEl) return;

        overlayEl.classList.remove('auth-fade-in');
        overlayEl.classList.add('auth-fade-out');

        setTimeout(function () {
            if (overlayEl && overlayEl.parentNode) {
                overlayEl.parentNode.removeChild(overlayEl);
            }
            overlayEl = null;
        }, 400);
    }

    // ── Build Overlay HTML ─────────────────────────────────────
    function buildOverlayHTML() {
        return '' +
            '<div class="auth-card">' +
                '<div class="auth-card-inner">' +
                    '<div class="auth-title-area">' +
                        '<h1 class="auth-title">\u604B\u7231\u81F3\u4E0A\u4E3B\u4E49\u533A\u57DF</h1>' +
                        '<p class="auth-subtitle">Love Supremacy Zone</p>' +
                    '</div>' +

                    '<div class="auth-tabs">' +
                        '<button class="auth-tab active" data-tab="login">\u767B\u5F55</button>' +
                        '<button class="auth-tab" data-tab="register">\u6CE8\u518C</button>' +
                    '</div>' +

                    '<div class="auth-error" id="auth-error" style="display:none;"></div>' +

                    '<div class="auth-forms">' +
                        '<!-- Login Form -->' +
                        '<form class="auth-form" id="auth-login-form">' +
                            '<div class="auth-field">' +
                                '<input type="text" class="auth-input" id="login-username" placeholder="\u7528\u6237\u540D" autocomplete="username" required>' +
                            '</div>' +
                            '<div class="auth-field">' +
                                '<input type="password" class="auth-input" id="login-password" placeholder="\u5BC6\u7801" autocomplete="current-password" required>' +
                            '</div>' +
                            '<button type="submit" class="auth-btn" id="login-btn">\u767B\u5F55</button>' +
                        '</form>' +

                        '<!-- Register Form -->' +
                        '<form class="auth-form" id="auth-register-form" style="display:none;">' +
                            '<div class="auth-field">' +
                                '<input type="text" class="auth-input" id="register-username" placeholder="\u7528\u6237\u540D" autocomplete="username" required>' +
                            '</div>' +
                            '<div class="auth-field">' +
                                '<input type="password" class="auth-input" id="register-password" placeholder="\u5BC6\u7801" autocomplete="new-password" required>' +
                            '</div>' +
                            '<div class="auth-field">' +
                                '<input type="text" class="auth-input" id="register-chatid" placeholder="Telegram Chat ID" autocomplete="off" required>' +
                            '</div>' +
                            '<button type="submit" class="auth-btn" id="register-btn">\u6CE8\u518C</button>' +
                        '</form>' +
                    '</div>' +

                    '<div class="auth-footer">' +
                        '<p class="auth-hint">\u7EFF\u8272\u7684\u5149\u8292\u7167\u4EAE\u4E86\u8FD9\u4E2A\u4E16\u754C...</p>' +
                    '</div>' +
                '</div>' +
            '</div>';
    }

    // ── Bind Events ────────────────────────────────────────────
    function bindEvents() {
        if (!overlayEl) return;

        // Tab switching
        var tabs = overlayEl.querySelectorAll('.auth-tab');
        for (var i = 0; i < tabs.length; i++) {
            tabs[i].addEventListener('click', function () {
                switchTab(this.getAttribute('data-tab'));
            });
        }

        // Login form submit
        var loginForm = overlayEl.querySelector('#auth-login-form');
        if (loginForm) {
            loginForm.addEventListener('submit', function (e) {
                e.preventDefault();
                var username = overlayEl.querySelector('#login-username').value.trim();
                var password = overlayEl.querySelector('#login-password').value;
                if (username && password) {
                    handleLogin(username, password);
                } else {
                    showError('\u8BF7\u586B\u5199\u7528\u6237\u540D\u548C\u5BC6\u7801');
                }
            });
        }

        // Register form submit
        var registerForm = overlayEl.querySelector('#auth-register-form');
        if (registerForm) {
            registerForm.addEventListener('submit', function (e) {
                e.preventDefault();
                var username = overlayEl.querySelector('#register-username').value.trim();
                var password = overlayEl.querySelector('#register-password').value;
                var chatId = overlayEl.querySelector('#register-chatid').value.trim();
                if (username && password && chatId) {
                    handleRegister(username, password, chatId);
                } else {
                    showError('\u8BF7\u586B\u5199\u6240\u6709\u5B57\u6BB5');
                }
            });
        }
    }

    // ── Switch Tab ─────────────────────────────────────────────
    function switchTab(tab) {
        currentTab = tab;

        if (!overlayEl) return;

        // Update tab buttons
        var tabs = overlayEl.querySelectorAll('.auth-tab');
        for (var i = 0; i < tabs.length; i++) {
            if (tabs[i].getAttribute('data-tab') === tab) {
                tabs[i].classList.add('active');
            } else {
                tabs[i].classList.remove('active');
            }
        }

        // Update forms
        var loginForm = overlayEl.querySelector('#auth-login-form');
        var registerForm = overlayEl.querySelector('#auth-register-form');

        if (tab === 'login') {
            if (loginForm) loginForm.style.display = 'block';
            if (registerForm) registerForm.style.display = 'none';
        } else {
            if (loginForm) loginForm.style.display = 'none';
            if (registerForm) registerForm.style.display = 'block';
        }

        // Clear error
        hideError();
    }

    // ── Handle Login ───────────────────────────────────────────
    function handleLogin(username, password) {
        if (!window.GameAPI) {
            showError('\u7CFB\u7EDF\u672A\u5C31\u7EEA\uFF0C\u8BF7\u7A0D\u540E\u518D\u8BD5');
            return;
        }

        var loginBtn = overlayEl.querySelector('#login-btn');
        if (loginBtn) {
            loginBtn.disabled = true;
            loginBtn.textContent = '\u767B\u5F55\u4E2D...';
        }

        // Update sync status to syncing
        if (window.updateSyncStatus) window.updateSyncStatus('syncing');

        GameAPI.login(username, password).then(function (data) {
            if (data && data.token) {
                GameAPI.setToken(data.token);
                if (window.updateSyncStatus) window.updateSyncStatus('synced');
                hideLoginScreen();

                // Trigger game load (which will sync state from server)
                if (window.loadGame) {
                    window.loadGame();
                }

                // Initialize sync module after successful login
                if (window.GameSync) {
                    GameSync.init();
                }
            } else {
                showError('\u767B\u5F55\u5931\u8D25\uFF0C\u672A\u83B7\u53D6\u5230 token');
                resetButton(loginBtn, '\u767B\u5F55');
                if (window.updateSyncStatus) window.updateSyncStatus('offline');
            }
        }).catch(function (err) {
            var msg = err.message || '\u7528\u6237\u540D\u6216\u5BC6\u7801\u9519\u8BEF';
            // Map common error messages to Chinese
            if (msg.indexOf('Failed to fetch') !== -1 || msg.indexOf('网络') !== -1) {
                msg = '\u7F51\u7EDC\u8FDE\u63A5\u5931\u8D25\uFF0C\u8BF7\u68C0\u67E5\u7F51\u7EDC\u540E\u91CD\u8BD5';
            } else if (msg.indexOf('超时') !== -1) {
                msg = '\u8BF7\u6C42\u8D85\u65F6\uFF0C\u8BF7\u7A0D\u540E\u518D\u8BD5';
            } else if (msg.indexOf('用户名或密码') !== -1) {
                msg = '\u7528\u6237\u540D\u6216\u5BC6\u7801\u9519\u8BEF';
            }
            showError('\u767B\u5F55\u5931\u8D25\uFF1A' + msg);
            resetButton(loginBtn, '\u767B\u5F55');
            if (window.updateSyncStatus) window.updateSyncStatus('offline');
        });
    }

    // ── Handle Register ────────────────────────────────────────
    function handleRegister(username, password, chatId) {
        if (!window.GameAPI) {
            showError('\u7CFB\u7EDF\u672A\u5C31\u7EEA\uFF0C\u8BF7\u7A0D\u540E\u518D\u8BD5');
            return;
        }

        var registerBtn = overlayEl.querySelector('#register-btn');
        if (registerBtn) {
            registerBtn.disabled = true;
            registerBtn.textContent = '\u6CE8\u518C\u4E2D...';
        }

        // Update sync status to syncing
        if (window.updateSyncStatus) window.updateSyncStatus('syncing');

        GameAPI.register(username, password, chatId).then(function (data) {
            if (data && data.token) {
                GameAPI.setToken(data.token);
                if (window.updateSyncStatus) window.updateSyncStatus('synced');
                hideLoginScreen();

                // Trigger game load (which will sync state from server)
                if (window.loadGame) {
                    window.loadGame();
                }

                // Initialize sync module after successful registration
                if (window.GameSync) {
                    GameSync.init();
                }
            } else {
                showError('\u6CE8\u518C\u5931\u8D25\uFF0C\u672A\u83B7\u53D6\u5230 token');
                resetButton(registerBtn, '\u6CE8\u518C');
                if (window.updateSyncStatus) window.updateSyncStatus('offline');
            }
        }).catch(function (err) {
            var msg = err.message || '\u8BF7\u68C0\u67E5\u4FE1\u606F\u662F\u5426\u6B63\u786E';
            // Map common error messages to Chinese
            if (msg.indexOf('Failed to fetch') !== -1 || msg.indexOf('网络') !== -1) {
                msg = '\u7F51\u7EDC\u8FDE\u63A5\u5931\u8D25\uFF0C\u8BF7\u68C0\u67E5\u7F51\u7EDC\u540E\u91CD\u8BD5';
            } else if (msg.indexOf('超时') !== -1) {
                msg = '\u8BF7\u6C42\u8D85\u65F6\uFF0C\u8BF7\u7A0D\u540E\u518D\u8BD5';
            }
            showError('\u6CE8\u518C\u5931\u8D25\uFF1A' + msg);
            resetButton(registerBtn, '\u6CE8\u518C');
            if (window.updateSyncStatus) window.updateSyncStatus('offline');
        });
    }

    // ── Handle Logout ──────────────────────────────────────────
    function handleLogout() {
        // Stop sync before logout
        if (window.GameSync) {
            GameSync.destroy();
        }

        if (window.GameAPI) {
            GameAPI.logout();
        }

        // Update sync status
        if (window.updateSyncStatus) window.updateSyncStatus('none');

        // Show login screen
        showLoginScreen();

        // Reload page to reset game state
        setTimeout(function () {
            window.location.reload();
        }, 500);
    }

    // ── Show Error ─────────────────────────────────────────────
    function showError(msg) {
        if (!overlayEl) return;
        var errorEl = overlayEl.querySelector('#auth-error');
        if (errorEl) {
            errorEl.textContent = msg;
            errorEl.style.display = 'block';
        }
    }

    // ── Hide Error ─────────────────────────────────────────────
    function hideError() {
        if (!overlayEl) return;
        var errorEl = overlayEl.querySelector('#auth-error');
        if (errorEl) {
            errorEl.style.display = 'none';
            errorEl.textContent = '';
        }
    }

    // ── Reset Button ───────────────────────────────────────────
    function resetButton(btn, text) {
        if (btn) {
            btn.disabled = false;
            btn.textContent = text;
        }
    }

    // ── Export ─────────────────────────────────────────────────
    window.GameAuth = {
        init: init,
        showLoginScreen: showLoginScreen,
        hideLoginScreen: hideLoginScreen,
        handleLogin: handleLogin,
        handleRegister: handleRegister,
        handleLogout: handleLogout,
        isLoggedIn: isLoggedIn
    };
})();
