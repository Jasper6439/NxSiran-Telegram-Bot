/**
 * NxSiran Mini App - Toast Notification System
 * Provides non-intrusive toast notifications with auto-dismiss and stacking.
 */
(function () {
    'use strict';

    var container = null;
    var MAX_TOASTS = 5;

    function getContainer() {
        if (!container) {
            container = document.getElementById('toast-container');
        }
        return container;
    }

    /**
     * Show a toast notification.
     * @param {string} message - The message to display.
     * @param {string} type - One of 'success', 'error', 'warning', 'info'.
     * @param {number} duration - Auto-dismiss duration in ms (default 3000).
     */
    function showToast(message, type, duration) {
        type = type || 'info';
        duration = duration || 3000;

        var cont = getContainer();
        if (!cont) return;

        // Limit stack size
        var existing = cont.querySelectorAll('.toast');
        if (existing.length >= MAX_TOASTS) {
            var oldest = existing[0];
            if (oldest.parentNode) oldest.parentNode.removeChild(oldest);
        }

        var toast = document.createElement('div');
        toast.className = 'toast ' + type;
        toast.textContent = message;

        // Progress bar
        var progress = document.createElement('div');
        progress.style.cssText = 'position:absolute;bottom:0;left:0;height:3px;border-radius:0 0 18px 18px;' +
            'background:rgba(0,0,0,0.1);transition:width ' + duration + 'ms linear;width:100%;';
        toast.style.position = 'relative';
        toast.style.overflow = 'hidden';
        toast.appendChild(progress);

        // Trigger animation
        requestAnimationFrame(function () {
            progress.style.width = '0%';
        });

        cont.appendChild(toast);

        // Auto dismiss
        var timer = setTimeout(function () {
            dismissToast(toast);
        }, duration);

        // Allow manual dismiss on click
        toast.addEventListener('click', function () {
            clearTimeout(timer);
            dismissToast(toast);
        });
    }

    function dismissToast(toast) {
        if (!toast || !toast.parentNode) return;
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-16px) scale(0.95)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(function () {
            if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, 300);
    }

    // ===== Export =====
    window.Toast = {
        show: showToast,
        dismiss: dismissToast
    };
})();
