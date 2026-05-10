/**
 * NxSiran Game - Backend Sync
 * Load/save game state, auto-save, conflict resolution
 */
(function () {
    'use strict';

    var SYNC_INTERVAL = 30000;
    var SAVE_DEBOUNCE = 5000;
    var _saveTimeout = null;
    var _syncInterval = null;

    function init() {
        // Auto-save on state changes
        GameState.subscribe(function (state, prev, action) {
            if (action.type === 'PLANT' || action.type === 'HARVEST' || action.type === 'WATER' ||
                action.type === 'BUY_SEED' || action.type === 'SELL_CROP' || action.type === 'MOVE_PLAYER') {
                scheduleSave();
            }
        });

        // Periodic full refresh
        _syncInterval = setInterval(loadGameState, SYNC_INTERVAL);

        // Save before leaving
        window.addEventListener('beforeunload', function () {
            saveGameState();
        });
        window.addEventListener('visibilitychange', function () {
            if (document.hidden) saveGameState();
            else loadGameState();
        });
    }

    function loadGameState() {
        if (!window.GameAPI) return Promise.resolve();
        return GameAPI.getState().then(function (data) {
            if (data) {
                GameState.dispatch({ type: 'LOAD_STATE', payload: data });
                if (window.GameRenderer) GameRenderer.renderFull(GameState.getState());
                if (window.GameInventory) GameInventory.updateUI();
            }
        }).catch(function (err) {
            console.error('[Sync] Load failed:', err);
        });
    }

    function scheduleSave() {
        clearTimeout(_saveTimeout);
        _saveTimeout = setTimeout(saveGameState, SAVE_DEBOUNCE);
    }

    function saveGameState() {
        var state = GameState.getState();
        if (!state.pendingActions || state.pendingActions.length === 0) return;
        if (!window.GameAPI) return;

        var actions = state.pendingActions.slice();
        GameAPI.sync(actions).then(function () {
            GameState.dispatch({ type: 'CLEAR_PENDING' });
        }).catch(function (err) {
            console.error('[Sync] Save failed:', err);
        });
    }

    function destroy() {
        clearInterval(_syncInterval);
        clearTimeout(_saveTimeout);
    }

    window.GameSync = {
        init: init,
        loadGameState: loadGameState,
        scheduleSave: scheduleSave,
        saveGameState: saveGameState,
        destroy: destroy
    };
})();
