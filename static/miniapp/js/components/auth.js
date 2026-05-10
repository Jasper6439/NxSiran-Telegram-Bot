/**
 * NxSiran Mini App - Authentication Module
 * Handles login, register, token storage, auto-login, and logout.
 */
(function () {
    'use strict';

    var _isLoggedIn = false;
    var _isAdmin = false;
    var _username = '';

    // Callbacks
    var onLoginCallbacks = [];
    var onLogoutCallbacks = [];

    /**
     * Register callbacks for login/logout events.
     */
    function onLogin(callback) {
        onLoginCallbacks.push(callback);
    }

    function onLogout(callback) {
        onLogoutCallbacks.push(callback);
    }

    function fireLogin() {
        onLoginCallbacks.forEach(function (cb) {
            try { cb(_username, _isAdmin); } catch (e) { /* ignore */ }
        });
    }

    function fireLogout() {
        onLogoutCallbacks.forEach(function (cb) {
            try { cb(); } catch (e) { /* ignore */ }
        });
    }

    /**
     * Log in a user.
     * @returns {Promise}
     */
    function login(username, password) {
        return window.API.auth.login(username, password).then(function (result) {
            if (result.success) {
                _isLoggedIn = true;
                _isAdmin = result.is_admin || false;
                _username = result.username || username;
                window.API._setToken(result.token || '');
                localStorage.setItem('username', _username);
                localStorage.setItem('is_admin', _isAdmin ? '1' : '0');
                fireLogin();
            }
            return result;
        });
    }

    /**
     * Register a new user.
     * @returns {Promise}
     */
    function register(username, password, chatId) {
        return window.API.auth.register(username, password, chatId).then(function (result) {
            if (result.success) {
                _isLoggedIn = true;
                _isAdmin = result.is_admin || false;
                _username = result.username || username;
                window.API._setToken(result.token || '');
                localStorage.setItem('username', _username);
                localStorage.setItem('is_admin', _isAdmin ? '1' : '0');
                fireLogin();
            }
            return result;
        });
    }

    /**
     * Log out the current user.
     */
    function logout() {
        _isLoggedIn = false;
        _isAdmin = false;
        _username = '';
        window.API._clearToken();
        localStorage.removeItem('username');
        localStorage.removeItem('is_admin');
        fireLogout();
    }

    /**
     * Check for auto-login from stored token.
     * Validates the token with the server.
     * @returns {Promise<boolean>}
     */
    function checkAutoLogin() {
        var savedToken = localStorage.getItem('auth_token');
        var savedUsername = localStorage.getItem('username');
        var savedAdmin = localStorage.getItem('is_admin');

        if (!savedToken || !savedUsername) {
            return Promise.resolve(false);
        }

        _isAdmin = savedAdmin === '1';
        _username = savedUsername;

        return window.API.stats.get()
            .then(function () {
                _isLoggedIn = true;
                fireLogin();
                return true;
            })
            .catch(function () {
                // Token invalid, clear local storage
                window.API._clearToken();
                localStorage.removeItem('username');
                localStorage.removeItem('is_admin');
                _isAdmin = false;
                _username = '';
                return false;
            });
    }

    /**
     * Show the login form.
     */
    function showLoginForm() {
        var loginForm = document.getElementById('login-form');
        var registerForm = document.getElementById('register-form');
        var authTitle = document.getElementById('auth-title');
        if (loginForm) loginForm.style.display = 'block';
        if (registerForm) registerForm.style.display = 'none';
        if (authTitle) authTitle.textContent = '\u7528\u6237\u767B\u5F55';
    }

    /**
     * Show the register form.
     */
    function showRegisterForm() {
        var loginForm = document.getElementById('login-form');
        var registerForm = document.getElementById('register-form');
        var authTitle = document.getElementById('auth-title');
        if (loginForm) loginForm.style.display = 'none';
        if (registerForm) registerForm.style.display = 'block';
        if (authTitle) authTitle.textContent = '\u7528\u6237\u6CE8\u518C';
    }

    // ===== Getters =====
    Object.defineProperties(this, {
        isLoggedIn: {
            get: function () { return _isLoggedIn; },
            configurable: true
        },
        isAdmin: {
            get: function () { return _isAdmin; },
            configurable: true
        },
        username: {
            get: function () { return _username; },
            configurable: true
        }
    });

    // ===== Export =====
    window.Auth = {
        login: login,
        register: register,
        logout: logout,
        checkAutoLogin: checkAutoLogin,
        showLoginForm: showLoginForm,
        showRegisterForm: showRegisterForm,
        onLogin: onLogin,
        onLogout: onLogout,
        get isLoggedIn() { return _isLoggedIn; },
        get isAdmin() { return _isAdmin; },
        get username() { return _username; }
    };
})();
