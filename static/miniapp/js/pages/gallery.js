/**
 * NxSiran Mini App - Gallery Page Module
 * Loads selfies, displays photo grid, lightbox viewer, delete photo.
 */
(function () {
    'use strict';

    var currentModalFilename = null;
    var currentCharacterId = '';

    /**
     * Initialize the gallery page.
     */
    function init() {
        setupImageModal();
    }

    /**
     * Called when the gallery page is entered.
     */
    function onPageEnter() {
        loadGallery();
    }

    /**
     * Update the character ID for filtering.
     * @param {string} characterId
     */
    function setCharacterId(characterId) {
        currentCharacterId = characterId;
    }

    // ===== Load Gallery =====
    function loadGallery() {
        var grid = document.getElementById('gallery-grid');
        var loading = document.getElementById('gallery-loading');
        if (!grid) return;

        if (loading) loading.classList.add('active');

        window.API.selfies.list(currentCharacterId).then(function (data) {
            if (data.selfies && data.selfies.length > 0) {
                grid.innerHTML = '';
                data.selfies.forEach(function (item) {
                    var div = document.createElement('div');
                    div.className = 'photo-item';
                    div.innerHTML = '<img src="' + window.API._base + item.url + '" alt="selfie">' +
                        '<div class="photo-overlay">' +
                        '<svg viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>' +
                        '</div>';

                    // Touch: long press to view
                    var pressTimer = null;
                    div.addEventListener('touchstart', function () {
                        pressTimer = setTimeout(function () {
                            showImageModal(item.url, item.filename);
                        }, 500);
                    });
                    div.addEventListener('touchend', function () { clearTimeout(pressTimer); });
                    div.addEventListener('touchmove', function () { clearTimeout(pressTimer); });

                    // Desktop: click to view
                    div.addEventListener('click', function () {
                        showImageModal(item.url, item.filename);
                    });

                    grid.appendChild(div);
                });
            } else {
                grid.innerHTML = '<div class="empty-state">' +
                    '<div class="empty-state-icon">' +
                    '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>' +
                    '</div>' +
                    '<div class="empty-state-text">\u8FD8\u6CA1\u6709\u7167\u7247</div></div>';
            }
        }).catch(function (error) {
            console.error('Load gallery error:', error);
            window.Toast.show('\u52A0\u8F7D\u76F8\u518C\u5931\u8D25', 'error');
        }).finally(function () {
            if (loading) loading.classList.remove('active');
        });
    }

    // ===== Image Modal =====
    function setupImageModal() {
        var modal = document.getElementById('image-modal');
        var modalImg = document.getElementById('modal-image');
        var closeBtn = document.getElementById('modal-close-btn');
        var deleteBtn = document.getElementById('modal-delete-btn');

        if (!modal) return;

        if (closeBtn) {
            closeBtn.addEventListener('click', function () {
                modal.classList.remove('active');
                currentModalFilename = null;
            });
        }

        if (deleteBtn) {
            deleteBtn.addEventListener('click', function () {
                deletePhoto();
            });
        }

        modal.addEventListener('click', function (e) {
            if (e.target === modal) {
                modal.classList.remove('active');
                currentModalFilename = null;
            }
        });
    }

    function showImageModal(url, filename) {
        currentModalFilename = filename;
        var modalImg = document.getElementById('modal-image');
        var modal = document.getElementById('image-modal');
        if (modalImg) modalImg.src = window.API._base + url;
        if (modal) modal.classList.add('active');
    }

    function deletePhoto() {
        if (!currentModalFilename) return;

        window.API.selfies.delete(currentModalFilename).then(function (response) {
            window.Toast.show('\u7167\u7247\u5DF2\u5220\u9664', 'success');
            var modal = document.getElementById('image-modal');
            if (modal) modal.classList.remove('active');
            currentModalFilename = null;
            loadGallery();
            if (window.HomePage) window.HomePage.loadStats();
        }).catch(function () {
            window.Toast.show('\u5220\u9664\u5931\u8D25', 'error');
        });
    }

    // ===== Export =====
    window.GalleryPage = {
        init: init,
        onPageEnter: onPageEnter,
        loadGallery: loadGallery,
        setCharacterId: setCharacterId
    };
})();
