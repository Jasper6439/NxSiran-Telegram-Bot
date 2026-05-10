/**
 * NxSiran Game - Viewport (Drag-to-scroll) + Grid System
 * Touch and mouse drag scrolling, coordinate conversion, collision detection
 */
(function () {
    'use strict';

    var GRID_WIDTH_PX = 40;
    var _viewport = null;
    var _worldContainer = null;
    var _isDragging = false;
    var _hasMoved = false;
    var _startX = 0, _startY = 0;
    var _scrollLeft = 0, _scrollTop = 0;
    var _lastTouchDist = 0;
    var _scale = 1;

    // ── Initialize ─────────────────────────────────────────────
    function init(viewport, worldContainer, gridWidthPx) {
        _viewport = viewport;
        _worldContainer = worldContainer;
        GRID_WIDTH_PX = gridWidthPx || 40;

        // Touch events
        _viewport.addEventListener('touchstart', onTouchStart, { passive: false });
        _viewport.addEventListener('touchmove', onTouchMove, { passive: false });
        _viewport.addEventListener('touchend', onTouchEnd);

        // Mouse events
        _viewport.addEventListener('mousedown', onMouseDown);
        _viewport.addEventListener('mousemove', onMouseMove);
        _viewport.addEventListener('mouseup', onMouseUp);
        _viewport.addEventListener('mouseleave', onMouseUp);

        // Scroll events for visibility culling
        _viewport.addEventListener('scroll', onScroll, { passive: true });

        // Prevent context menu on long press
        _viewport.addEventListener('contextmenu', function (e) { e.preventDefault(); });

        // Scroll to player position after initial render
        setTimeout(scrollToPlayer, 500);
    }

    // ── Touch Handlers ─────────────────────────────────────────
    function onTouchStart(e) {
        if (e.touches.length === 1) {
            _isDragging = true;
            _hasMoved = false;
            _startX = e.touches[0].clientX;
            _startY = e.touches[0].clientY;
            _scrollLeft = _viewport.scrollLeft;
            _scrollTop = _viewport.scrollTop;
        } else if (e.touches.length === 2) {
            // Pinch zoom
            _lastTouchDist = getTouchDist(e.touches);
        }
    }

    function onTouchMove(e) {
        if (e.touches.length === 2) {
            e.preventDefault();
            var dist = getTouchDist(e.touches);
            var delta = dist / _lastTouchDist;
            _lastTouchDist = dist;
            setScale(_scale * delta);
            return;
        }

        if (!_isDragging || e.touches.length !== 1) return;
        e.preventDefault();

        var dx = e.touches[0].clientX - _startX;
        var dy = e.touches[0].clientY - _startY;

        if (Math.abs(dx) > 5 || Math.abs(dy) > 5) _hasMoved = true;

        _viewport.scrollLeft = _scrollLeft - dx;
        _viewport.scrollTop = _scrollTop - dy;
    }

    function onTouchEnd(e) {
        if (!_isDragging) return;
        _isDragging = false;

        // If didn't move, it's a tap - handle tile click
        if (!_hasMoved && e.changedTouches.length === 1) {
            var touch = e.changedTouches[0];
            handleTap(touch.clientX, touch.clientY);
        }
    }

    // ── Mouse Handlers ─────────────────────────────────────────
    function onMouseDown(e) {
        if (e.button !== 0) return; // left click only
        _isDragging = true;
        _hasMoved = false;
        _startX = e.clientX;
        _startY = e.clientY;
        _scrollLeft = _viewport.scrollLeft;
        _scrollTop = _viewport.scrollTop;
        _viewport.style.cursor = 'grabbing';
    }

    function onMouseMove(e) {
        if (!_isDragging) return;
        var dx = e.clientX - _startX;
        var dy = e.clientY - _startY;

        if (Math.abs(dx) > 3 || Math.abs(dy) > 3) _hasMoved = true;

        _viewport.scrollLeft = _scrollLeft - dx;
        _viewport.scrollTop = _scrollTop - dy;
    }

    function onMouseUp(e) {
        if (!_isDragging) return;
        _isDragging = false;
        _viewport.style.cursor = 'grab';

        if (!_hasMoved) {
            handleTap(e.clientX, e.clientY);
        }
    }

    // ── Tap Handler ────────────────────────────────────────────
    function handleTap(clientX, clientY) {
        var grid = screenToGrid(clientX, clientY);
        if (grid && window.GameActions) {
            GameActions.handleTileClick(grid.x, grid.y);
        }
    }

    // ── Scroll Handler ─────────────────────────────────────────
    function onScroll() {
        if (window.GameRenderer) {
            GameRenderer.updateViewport({
                scrollLeft: _viewport.scrollLeft,
                scrollTop: _viewport.scrollTop,
                width: _viewport.clientWidth,
                height: _viewport.clientHeight
            });
            GameRenderer.updateAllVisibility();
        }
    }

    // ── Coordinate Conversion ──────────────────────────────────
    function screenToGrid(screenX, screenY) {
        if (!_viewport || !_worldContainer) return null;

        var vpRect = _viewport.getBoundingClientRect();
        var worldRect = _worldContainer.getBoundingClientRect();

        // Screen position relative to viewport
        var relX = screenX - vpRect.left + _viewport.scrollLeft;
        var relY = screenY - vpRect.top + _viewport.scrollTop;

        // World center in pixels
        var centerX = _worldContainer.offsetWidth / 2;
        var centerY = _worldContainer.offsetHeight / 2;

        // Convert to grid coordinates (y-axis inverted)
        var gridX = Math.round((relX - centerX) / GRID_WIDTH_PX);
        var gridY = Math.round(-(relY - centerY) / GRID_WIDTH_PX);

        return { x: gridX, y: gridY };
    }

    function gridToScreen(gridX, gridY) {
        if (!_viewport || !_worldContainer) return null;

        var centerX = _worldContainer.offsetWidth / 2;
        var centerY = _worldContainer.offsetHeight / 2;

        var px = centerX + gridX * GRID_WIDTH_PX;
        var py = centerY - gridY * GRID_WIDTH_PX;

        return {
            x: px - _viewport.scrollLeft,
            y: py - _viewport.scrollTop
        };
    }

    // ── Scroll To ──────────────────────────────────────────────
    function scrollToPosition(gridX, gridY) {
        if (!_viewport || !_worldContainer) return;

        var centerX = _worldContainer.offsetWidth / 2;
        var centerY = _worldContainer.offsetHeight / 2;

        var targetX = centerX + gridX * GRID_WIDTH_PX - _viewport.clientWidth / 2;
        var targetY = centerY - gridY * GRID_WIDTH_PX - _viewport.clientHeight / 2;

        _viewport.scrollTo({
            left: targetX,
            top: targetY,
            behavior: 'smooth'
        });
    }

    function scrollToPlayer() {
        var state = window.GameState ? GameState.getState() : null;
        if (state && state.player) {
            scrollToPosition(state.player.x, state.player.y);
        }
    }

    // ── Zoom ───────────────────────────────────────────────────
    function setScale(newScale) {
        _scale = Math.max(0.5, Math.min(1.5, newScale));
        if (_worldContainer) {
            _worldContainer.style.transform = 'scale(' + _scale + ')';
            _worldContainer.style.transformOrigin = 'center center';
        }
    }

    function getScale() { return _scale; }

    // ── Collision Detection ────────────────────────────────────
    function detectCollision(occupiedGrid, x, y, w, h) {
        w = w || 1;
        h = h || 1;
        for (var dx = 0; dx < w; dx++) {
            for (var dy = 0; dy < h; dy++) {
                if (occupiedGrid[(x + dx) + ',' + (y + dy)]) return true;
            }
        }
        return false;
    }

    function buildOccupiedGrid(state) {
        var grid = {};
        // Crops
        var cropKeys = Object.keys(state.crops || {});
        for (var i = 0; i < cropKeys.length; i++) {
            grid[cropKeys[i]] = 'crop';
        }
        // Buildings
        var bKeys = Object.keys(state.buildings || {});
        for (var j = 0; j < bKeys.length; j++) {
            var b = state.buildings[bKeys[j]];
            var bw = b.width || 2;
            var bh = b.height || 2;
            for (var bx = 0; bx < bw; bx++) {
                for (var by = 0; by < bh; by++) {
                    grid[(b.x + bx) + ',' + (b.y + by)] = 'building';
                }
            }
        }
        // Decorations
        var dKeys = Object.keys(state.decorations || {});
        for (var k = 0; k < dKeys.length; k++) {
            var d = state.decorations[dKeys[k]];
            grid[d.x + ',' + d.y] = 'decoration';
        }
        return grid;
    }

    // ── Helpers ────────────────────────────────────────────────
    function getTouchDist(touches) {
        var dx = touches[0].clientX - touches[1].clientX;
        var dy = touches[0].clientY - touches[1].clientY;
        return Math.sqrt(dx * dx + dy * dy);
    }

    // ── Export ─────────────────────────────────────────────────
    window.GameViewport = {
        init: init,
        screenToGrid: screenToGrid,
        gridToScreen: gridToScreen,
        scrollToPosition: scrollToPosition,
        scrollToPlayer: scrollToPlayer,
        setScale: setScale,
        getScale: getScale,
        detectCollision: detectCollision,
        buildOccupiedGrid: buildOccupiedGrid
    };
})();
