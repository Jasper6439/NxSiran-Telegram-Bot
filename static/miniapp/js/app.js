/**
 * NxSiran Mini App - Application Entry Point
 * Handles initialization, routing, dark mode, Telegram WebApp integration.
 */
(function () {
    'use strict';

    var currentPage = 'home';
    var pageTitles = {
        home: '\u8F66\u5982\u4E91',
        gallery: '\u7167\u7247\u76F8\u518C',
        quota: '\u989D\u5EA6\u76D1\u63A7',
        settings: '\u8BBE\u7F6E',
        skills: '\u6280\u80FD\u7BA1\u7406',
        game: '\u8F66\u5982\u4E91\u7269\u8BED',
        farm: '\u519C\u573A'
    };

    // Page lifecycle callbacks
    var pageEnterCallbacks = {};
    var pageLeaveCallbacks = {};

    /**
     * Register a callback for when a page is entered.
     * @param {string} pageName
     * @param {function} callback
     */
    function onPageEnter(pageName, callback) {
        if (!pageEnterCallbacks[pageName]) pageEnterCallbacks[pageName] = [];
        pageEnterCallbacks[pageName].push(callback);
    }

    /**
     * Register a callback for when a page is left.
     * @param {string} pageName
     * @param {function} callback
     */
    function onPageLeave(pageName, callback) {
        if (!pageLeaveCallbacks[pageName]) pageLeaveCallbacks[pageName] = [];
        pageLeaveCallbacks[pageName].push(callback);
    }

    /**
     * Navigate to a page.
     * @param {string} pageName - The page to navigate to.
     */
    function navigate(pageName) {
        var previousPage = currentPage;

        // Fire leave callbacks for previous page
        if (pageLeaveCallbacks[previousPage]) {
            pageLeaveCallbacks[previousPage].forEach(function (cb) {
                try { cb(); } catch (e) { console.error('Page leave error:', e); }
            });
        }

        // Hide all pages
        document.querySelectorAll('.page').forEach(function (p) {
            p.classList.remove('active');
        });

        // Show target page
        var page = document.getElementById('page-' + pageName);
        if (page) {
            page.classList.add('active');
        }

        // Update header title
        var headerTitle = pageTitles[pageName] || '\u8F66\u5982\u4E91';
        var headerH1 = document.querySelector('.header h1');
        if (headerH1) headerH1.textContent = headerTitle;

        // Show/hide header for game page
        var header = document.querySelector('.header');
        if (header) {
            header.style.display = (pageName === 'game') ? 'none' : '';
        }

        // Update navigation active state
        if (window.Navigation) {
            window.Navigation.setActive(pageName);
        }

        currentPage = pageName;

        // Fire enter callbacks for new page
        if (pageEnterCallbacks[pageName]) {
            pageEnterCallbacks[pageName].forEach(function (cb) {
                try { cb(); } catch (e) { console.error('Page enter error:', e); }
            });
        }
    }

    /**
     * Get the current page name.
     * @returns {string}
     */
    function getCurrentPage() {
        return currentPage;
    }

    /**
     * Initialize Telegram WebApp integration.
     */
    function initTelegram() {
        var tg = window.Telegram && window.Telegram.WebApp;
        if (!tg) return;

        tg.ready();
        tg.expand();

        try { tg.setHeaderColor('#7B2D8E'); } catch (e) { /* ignore */ }
        try { tg.setBackgroundColor('#EDE7F6'); } catch (e) { /* ignore */ }

        // Back button handling
        if (tg.BackButton) {
            tg.BackButton.onClick(function () {
                if (currentPage !== 'home') {
                    navigate('home');
                } else {
                    tg.close();
                }
            });

            // Show back button when not on home
            onPageEnter('*', function () {
                if (currentPage !== 'home') {
                    try { tg.BackButton.show(); } catch (e) { /* ignore */ }
                } else {
                    try { tg.BackButton.hide(); } catch (e) { /* ignore */ }
                }
            });
        }

        // Theme handling
        if (tg.colorScheme) {
            if (tg.colorScheme === 'dark') {
                document.documentElement.setAttribute('data-theme', 'dark');
            }
        }

        tg.onEvent('themeChanged', function () {
            if (tg.colorScheme === 'dark') {
                document.documentElement.setAttribute('data-theme', 'dark');
            } else {
                document.documentElement.removeAttribute('data-theme');
            }
        });
    }

    /**
     * Detect and apply dark mode.
     */
    function initDarkMode() {
        var saved = localStorage.getItem('dark_mode');
        if (saved === 'true' || (!saved && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
            document.documentElement.setAttribute('data-theme', 'dark');
        }
    }

    /**
     * Toggle dark mode.
     */
    function toggleDarkMode() {
        var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        if (isDark) {
            document.documentElement.removeAttribute('data-theme');
            localStorage.setItem('dark_mode', 'false');
        } else {
            document.documentElement.setAttribute('data-theme', 'dark');
            localStorage.setItem('dark_mode', 'true');
        }
    }

    /**
     * Global error handler.
     */
    function initErrorHandler() {
        window.addEventListener('error', function (event) {
            console.error('Global error:', event.error);
        });

        window.addEventListener('unhandledrejection', function (event) {
            console.error('Unhandled rejection:', event.reason);
        });
    }

    /**
     * Utility: escape HTML entities.
     */
    function escapeHtml(str) {
        if (!str) return '';
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    /**
     * Utility: escape for JS strings.
     */
    function escapeJs(str) {
        if (!str) return '';
        return str.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"');
    }

    /**
     * Utility: format bytes.
     */
    function formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        var k = 1024;
        var sizes = ['B', 'KB', 'MB', 'GB'];
        var i = Math.floor(Math.log(bytes) / Math.log(k));
        i = Math.min(i, sizes.length - 1);
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    // ===== DOMContentLoaded Initialization =====
    document.addEventListener('DOMContentLoaded', function () {
        // Initialize core systems
        initErrorHandler();
        initDarkMode();
        initTelegram();

        // Initialize navigation
        if (window.Navigation) {
            window.Navigation.init();
        }

        // Initialize auth
        if (window.Auth) {
            window.Auth.checkAutoLogin().then(function (loggedIn) {
                if (loggedIn) {
                    if (window.Toast) {
                        window.Toast.show('\u6B22\u8FCE\u56DE\u6765 ' + window.Auth.username, 'success');
                    }
                    // Update UI for logged-in state
                    updateLoginUI(true);
                }
            });
        }

        // Register auth callbacks
        if (window.Auth) {
            window.Auth.onLogin(function (username, isAdmin) {
                updateLoginUI(true);
                if (window.Toast) {
                    window.Toast.show('\u767B\u5F55\u6210\u529F\uFF01\u6B22\u8FCE ' + username, 'success');
                }
            });

            window.Auth.onLogout(function () {
                updateLoginUI(false);
                if (window.Toast) {
                    window.Toast.show('\u5DF2\u9000\u51FA\u767B\u5F55', 'info');
                }
            });
        }

        // Initialize page modules
        if (window.HomePage) window.HomePage.init();
        if (window.FarmPage) window.FarmPage.init();
        if (window.GalleryPage) window.GalleryPage.init();
        if (window.SettingsPage) window.SettingsPage.init();
        if (window.SkillsPage) window.SkillsPage.init();
        if (window.QuotaPage) window.QuotaPage.init();

        // Wire up inline onclick handlers that reference switchPage
        window.switchPage = navigate;

        // Register page enter callbacks
        onPageEnter('home', function () {
            if (window.HomePage) window.HomePage.onPageEnter();
        });
        onPageEnter('farm', function () {
            if (window.FarmPage) window.FarmPage.onPageEnter();
        });
        onPageEnter('gallery', function () {
            if (window.GalleryPage) window.GalleryPage.onPageEnter();
        });
        onPageEnter('settings', function () {
            if (window.SettingsPage) window.SettingsPage.onPageEnter();
        });
        onPageEnter('skills', function () {
            if (window.SkillsPage) window.SkillsPage.onPageEnter();
        });
        onPageEnter('quota', function () {
            if (window.QuotaPage) window.QuotaPage.onPageEnter();
        });
        onPageEnter('game', function () {
            if (typeof initGameIfNeeded === 'function') initGameIfNeeded();
        });

        // Leave callbacks for cleanup
        onPageLeave('farm', function () {
            if (window.FarmPage) window.FarmPage.onPageLeave();
        });
    });

    function updateLoginUI(loggedIn) {
        var authCard = document.getElementById('auth-card');
        var welcomeBanner = document.getElementById('welcome-banner');
        var configArea = document.getElementById('config-area');

        if (loggedIn) {
            if (authCard) authCard.style.display = 'none';
            if (welcomeBanner) welcomeBanner.style.display = '';
            if (configArea) configArea.style.display = 'block';

            // Update admin UI
            if (window.Auth && window.Auth.isAdmin) {
                var adminArea = document.getElementById('admin-config-area');
                var statusText = document.getElementById('login-status-text');
                if (adminArea) adminArea.style.display = 'block';
                if (statusText) statusText.textContent = '\u5DF2\u767B\u5F55\u4E3A\u7BA1\u7406\u5458';
            } else {
                var adminArea2 = document.getElementById('admin-config-area');
                var statusText2 = document.getElementById('login-status-text');
                if (adminArea2) adminArea2.style.display = 'none';
                if (statusText2) statusText2.textContent = '\u5DF2\u767B\u5F55';
            }

            // Load stats
            if (window.HomePage) window.HomePage.loadStats();
        } else {
            if (authCard) authCard.style.display = 'block';
            if (welcomeBanner) welcomeBanner.style.display = 'none';
            if (configArea) configArea.style.display = 'none';

            // Clear form fields
            var fields = ['login-username', 'login-password', 'reg-username', 'reg-password', 'reg-chatid'];
            fields.forEach(function (id) {
                var el = document.getElementById(id);
                if (el) el.value = '';
            });

            // Show login form
            if (window.Auth) window.Auth.showLoginForm();
        }
    }

    // ===== Export =====
    window.App = {
        navigate: navigate,
        getCurrentPage: getCurrentPage,
        onPageEnter: onPageEnter,
        onPageLeave: onPageLeave,
        toggleDarkMode: toggleDarkMode,
        escapeHtml: escapeHtml,
        escapeJs: escapeJs,
        formatBytes: formatBytes,
        updateLoginUI: updateLoginUI
    };
})();
