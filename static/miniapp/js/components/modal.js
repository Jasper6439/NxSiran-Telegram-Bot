/**
 * NxSiran Mini App - Modal / Bottom Sheet System
 * Provides modal dialogs and bottom sheets with drag-to-dismiss.
 */
(function () {
    'use strict';

    var overlay = null;
    var currentModal = null;
    var isDragging = false;
    var startY = 0;
    var currentY = 0;
    var modalContent = null;

    function getOrCreateOverlay() {
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'modal-overlay';
            overlay.style.cssText = 'display:none;position:fixed;inset:0;z-index:500;' +
                'background:rgba(0,0,0,0.5);align-items:center;justify-content:center;' +
                'backdrop-filter:blur(4px);transition:opacity 0.3s ease;';
            overlay.addEventListener('click', function (e) {
                if (e.target === overlay) {
                    closeModal();
                }
            });
            document.body.appendChild(overlay);
        }
        return overlay;
    }

    /**
     * Show a modal or bottom sheet.
     * @param {string|HTMLElement} content - HTML string or DOM element.
     * @param {object} options - { title, closable, fullScreen, bottomSheet }
     */
    function showModal(content, options) {
        options = options || {};
        var ov = getOrCreateOverlay();

        // Remove previous modal content
        if (modalContent && modalContent.parentNode) {
            modalContent.parentNode.removeChild(modalContent);
        }

        modalContent = document.createElement('div');
        modalContent.style.cssText = 'background:var(--card);border-radius:24px;padding:24px;' +
            'max-width:400px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,0.3);' +
            'animation:pageSlideIn 0.3s ease;position:relative;overflow:hidden;';

        if (options.fullScreen) {
            modalContent.style.maxWidth = '100%';
            modalContent.style.width = '100%';
            modalContent.style.height = '100%';
            modalContent.style.borderRadius = '0';
            modalContent.style.maxHeight = '100vh';
        }

        if (options.bottomSheet) {
            modalContent.style.position = 'fixed';
            modalContent.style.bottom = '0';
            modalContent.style.left = '0';
            modalContent.style.right = '0';
            modalContent.style.width = '100%';
            modalContent.style.maxWidth = '100%';
            modalContent.style.borderRadius = '24px 24px 0 0';
            modalContent.style.transform = 'translateY(100%)';
            modalContent.style.transition = 'transform 0.35s cubic-bezier(0.4, 0, 0.2, 1)';
            ov.style.alignItems = 'flex-end';
        } else {
            ov.style.alignItems = 'center';
        }

        // Title
        if (options.title) {
            var titleEl = document.createElement('div');
            titleEl.style.cssText = 'font-size:1.1rem;font-weight:700;color:var(--text);margin-bottom:16px;' +
                'display:flex;align-items:center;justify-content:space-between;';
            titleEl.innerHTML = '<span>' + options.title + '</span>';

            if (options.closable !== false) {
                var closeBtn = document.createElement('button');
                closeBtn.innerHTML = '&times;';
                closeBtn.style.cssText = 'width:32px;height:32px;border:none;background:var(--gradient-card);' +
                    'border-radius:50%;font-size:1.2rem;cursor:pointer;color:var(--text);' +
                    'display:flex;align-items:center;justify-content:center;box-shadow:var(--clay-outer-sm);';
                closeBtn.addEventListener('click', closeModal);
                titleEl.appendChild(closeBtn);
            }

            modalContent.appendChild(titleEl);
        }

        // Content
        if (typeof content === 'string') {
            var contentDiv = document.createElement('div');
            contentDiv.innerHTML = content;
            modalContent.appendChild(contentDiv);
        } else if (content instanceof HTMLElement) {
            modalContent.appendChild(content);
        }

        ov.appendChild(modalContent);
        ov.style.display = 'flex';

        // Animate in
        requestAnimationFrame(function () {
            ov.style.opacity = '1';
            if (options.bottomSheet) {
                modalContent.style.transform = 'translateY(0)';
            }
        });

        // Drag-to-dismiss for bottom sheets
        if (options.bottomSheet) {
            setupDragDismiss(modalContent);
        }

        currentModal = modalContent;
    }

    function setupDragDismiss(el) {
        var handle = document.createElement('div');
        handle.style.cssText = 'width:40px;height:4px;background:var(--text-muted);border-radius:4px;' +
            'margin:0 auto 16px;opacity:0.5;cursor:grab;';
        el.insertBefore(handle, el.firstChild);

        var startY = 0;
        var currentY = 0;
        var dragging = false;

        function onStart(e) {
            dragging = true;
            startY = e.touches ? e.touches[0].clientY : e.clientY;
            el.style.transition = 'none';
        }

        function onMove(e) {
            if (!dragging) return;
            currentY = (e.touches ? e.touches[0].clientY : e.clientY) - startY;
            if (currentY > 0) {
                el.style.transform = 'translateY(' + currentY + 'px)';
            }
        }

        function onEnd() {
            if (!dragging) return;
            dragging = false;
            el.style.transition = 'transform 0.35s cubic-bezier(0.4, 0, 0.2, 1)';
            if (currentY > 100) {
                closeModal();
            } else {
                el.style.transform = 'translateY(0)';
            }
            currentY = 0;
        }

        handle.addEventListener('mousedown', onStart);
        handle.addEventListener('touchstart', onStart, { passive: true });
        document.addEventListener('mousemove', onMove);
        document.addEventListener('touchmove', onMove, { passive: true });
        document.addEventListener('mouseup', onEnd);
        document.addEventListener('touchend', onEnd);
    }

    function closeModal() {
        var ov = getOrCreateOverlay();
        ov.style.opacity = '0';

        if (modalContent) {
            if (modalContent.style.transform !== undefined && modalContent.style.transform.indexOf('translateY(0)') !== -1) {
                modalContent.style.transform = 'translateY(100%)';
            } else {
                modalContent.style.opacity = '0';
            }
        }

        setTimeout(function () {
            ov.style.display = 'none';
            if (modalContent && modalContent.parentNode) {
                modalContent.parentNode.removeChild(modalContent);
            }
            modalContent = null;
            currentModal = null;
        }, 350);
    }

    // ===== Export =====
    window.Modal = {
        show: showModal,
        close: closeModal
    };
})();
