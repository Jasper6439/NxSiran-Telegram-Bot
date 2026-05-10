/**
 * NxSiran Mini App - Bottom Navigation Component
 * Handles tab switching, active states, badges, and haptic feedback.
 */
(function () {
    'use strict';

    var currentPage = 'home';

    /**
     * Initialize the navigation component.
     */
    function init() {
        var navItems = document.querySelectorAll('.tab-item');
        navItems.forEach(function (item) {
            item.addEventListener('click', function () {
                var page = this.getAttribute('data-page');
                if (page) {
                    switchTab(page);
                }
            });
        });
    }

    /**
     * Switch the active tab.
     * @param {string} pageName - The page name to switch to.
     */
    function switchTab(pageName) {
        currentPage = pageName;

        // Update active states
        document.querySelectorAll('.tab-item').forEach(function (n) {
            n.classList.remove('active');
        });
        var activeBtn = document.querySelector('.tab-item[data-page="' + pageName + '"]');
        if (activeBtn) {
            activeBtn.classList.add('active');
        }

        // Haptic feedback
        triggerHaptic();
    }

    /**
     * Set the active tab programmatically (without triggering page switch).
     * @param {string} pageName
     */
    function setActive(pageName) {
        currentPage = pageName;
        document.querySelectorAll('.tab-item').forEach(function (n) {
            n.classList.remove('active');
        });
        var activeBtn = document.querySelector('.tab-item[data-page="' + pageName + '"]');
        if (activeBtn) {
            activeBtn.classList.add('active');
        }
    }

    /**
     * Update badge count on a tab.
     * @param {string} pageName - The tab page name.
     * @param {number} count - Badge count (0 to remove).
     */
    function updateBadge(pageName, count) {
        var navBtn = document.querySelector('.tab-item[data-page="' + pageName + '"]');
        if (!navBtn) return;

        var existingBadge = navBtn.querySelector('.tab-badge');
        if (existingBadge) {
            existingBadge.parentNode.removeChild(existingBadge);
        }

        if (count > 0) {
            var badge = document.createElement('span');
            badge.className = 'tab-badge';
            badge.textContent = count > 99 ? '99+' : count;
            badge.style.cssText = 'position:absolute;top:2px;right:6px;min-width:16px;height:16px;' +
                'background:var(--error);color:#fff;border-radius:8px;font-size:0.6rem;' +
                'font-weight:700;display:flex;align-items:center;justify-content:center;' +
                'padding:0 4px;box-shadow:0 2px 4px rgba(0,0,0,0.2);';
            navBtn.appendChild(badge);
        }
    }

    /**
     * Trigger haptic feedback if available (Telegram WebApp).
     */
    function triggerHaptic() {
        try {
            var tg = window.Telegram && window.Telegram.WebApp;
            if (tg && tg.HapticFeedback) {
                tg.HapticFeedback.selectionChanged();
            }
        } catch (e) {
            // Haptic not available
        }
    }

    /**
     * Get the current active page name.
     * @returns {string}
     */
    function getCurrentPage() {
        return currentPage;
    }

    // ===== Export =====
    window.Navigation = {
        init: init,
        switchTab: switchTab,
        setActive: setActive,
        updateBadge: updateBadge,
        getCurrentPage: getCurrentPage
    };
})();
