(function() {
    var isMiniApp = false;
    var tg = null;

    function init() {
        // Check if running inside Telegram
        if (window.Telegram && window.Telegram.WebApp) {
            tg = window.Telegram.WebApp;
            isMiniApp = true;
            tg.ready();
            tg.expand();
            applyTheme();
            setupBackButton();
            setupMainButton();
            console.log('[MiniApp] Telegram WebApp detected');
        } else {
            console.log('[MiniApp] Not running in Telegram');
        }
    }

    function applyTheme() {
        if (!tg) return;
        var themeParams = tg.themeParams;
        if (themeParams.bg_color) {
            document.documentElement.style.setProperty('--game-bg', themeParams.bg_color);
        }
        if (themeParams.text_color) {
            document.documentElement.style.setProperty('--game-text', themeParams.text_color);
        }
        if (themeParams.hint_color) {
            document.documentElement.style.setProperty('--game-text-secondary', themeParams.hint_color);
        }
        // Apply Telegram's color scheme
        if (tg.colorScheme === 'dark') {
            document.body.classList.add('dark-mode');
        }
    }

    function setupBackButton() {
        if (!tg) return;
        if (tg.BackButton) {
            tg.BackButton.show();
            tg.BackButton.onClick(function() {
                // Close any open panel
                if (window.GamePanels) GamePanels.closeAll();
                else tg.close();
            });
        }
    }

    function setupMainButton() {
        if (!tg || !tg.MainButton) return;
        // Main button can be used for contextual actions
        // Initially hidden
        tg.MainButton.hide();
    }

    function hapticFeedback(type) {
        if (!tg || !tg.HapticFeedback) return;
        switch(type) {
            case 'light': tg.HapticFeedback.impactOccurred('light'); break;
            case 'medium': tg.HapticFeedback.impactOccurred('medium'); break;
            case 'heavy': tg.HapticFeedback.impactOccurred('heavy'); break;
            case 'success': tg.HapticFeedback.notificationOccurred('success'); break;
            case 'error': tg.HapticFeedback.notificationOccurred('error'); break;
            case 'select': tg.HapticFeedback.selectionChanged(); break;
        }
    }

    function isAvailable() { return isMiniApp; }
    function getWebApp() { return tg; }

    window.GameMiniApp = {
        init: init,
        isAvailable: isAvailable,
        getWebApp: getWebApp,
        hapticFeedback: hapticFeedback,
        applyTheme: applyTheme
    };
})();
