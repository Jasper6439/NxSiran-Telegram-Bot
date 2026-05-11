/**
 * NxSiran Game - Backend Sync (v1.2f)
 * Load/save game state, auto-save, conflict resolution
 * - 60 second periodic sync
 * - 5 second debounced save on key actions
 * - Server wins for farm data, local wins for temporary UI state
 * - Sync status indicator integration
 * - Graceful offline fallback
 */
(function () {
    'use strict';

    var SYNC_INTERVAL = 60000;   // Full state refresh every 60 seconds
    var SAVE_DEBOUNCE = 5000;    // Debounce save by 5 seconds
    var _saveTimeout = null;
    var _syncInterval = null;
    var _initialized = false;
    var _isSyncing = false;
    var _consecutiveFailures = 0;
    var MAX_CONSECUTIVE_FAILURES = 3; // After this, reduce sync frequency

    // Actions that should trigger an immediate save queue
    var SYNCABLE_ACTIONS = [
        'PLANT', 'HARVEST', 'WATER', 'BUY_SEED', 'SELL_CROP',
        'MOVE_PLAYER', 'SPEND_MONEY', 'ADD_INVENTORY_ITEM',
        'UPDATE_INVENTORY_ITEM', 'REMOVE_INVENTORY_ITEM'
    ];

    // State keys where server data wins during conflict resolution
    var SERVER_WINS_KEYS = [
        'farm', 'crops', 'inventory', 'cropTypes', 'npc',
        'hearts', 'relationshipStatus', 'emotionValues',
        'worldLayer', 'awakenedCharacters', 'buildings', 'decorations'
    ];

    // State keys where local data wins (temporary UI state)
    var LOCAL_WINS_KEYS = [
        'selectedTool', 'status', 'weatherEffects',
        'pendingActions', 'lastSave'
    ];

    function init() {
        if (_initialized) return;
        _initialized = true;
        _consecutiveFailures = 0;

        // Auto-save on state changes
        GameState.subscribe(function (state, prev, action) {
            if (SYNCABLE_ACTIONS.indexOf(action.type) !== -1) {
                scheduleSave();
            }
        });

        // Periodic full refresh
        _syncInterval = setInterval(function () {
            // Reduce frequency after repeated failures
            if (_consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
                console.log('[Sync] Skipping periodic sync after ' + _consecutiveFailures + ' failures');
                return;
            }
            loadGameState();
        }, SYNC_INTERVAL);

        // Save before leaving
        window.addEventListener('beforeunload', function () {
            saveGameState(true); // true = synchronous-like (fire and forget)
        });
        window.addEventListener('visibilitychange', function () {
            if (document.hidden) {
                saveGameState(true);
            } else {
                loadGameState();
            }
        });

        // Initial load from server
        loadGameState();

        console.log('[Sync] Backend sync initialized (interval: ' + SYNC_INTERVAL + 'ms)');
    }

    /**
     * Load full game state from server
     * Server data wins for persistent game data
     */
    function loadGameState() {
        if (!window.GameAPI || !GameAPI.isLoggedIn()) {
            return Promise.resolve();
        }

        if (_isSyncing) return Promise.resolve();
        _isSyncing = true;

        if (window.updateSyncStatus) window.updateSyncStatus('syncing');

        return GameAPI.getState().then(function (data) {
            _consecutiveFailures = 0;
            _isSyncing = false;

            if (data) {
                // Merge server state with conflict resolution
                var currentState = GameState.getState();
                var mergedData = resolveConflicts(data, currentState);
                GameState.dispatch({ type: 'LOAD_STATE', payload: mergedData });

                if (window.GameRenderer) GameRenderer.renderFull(GameState.getState());
                if (window.GameInventory) GameInventory.updateUI();
                if (window.updateSyncStatus) window.updateSyncStatus('synced');
            }
        }).catch(function (err) {
            _isSyncing = false;
            _consecutiveFailures++;
            console.warn('[Sync] Load failed (' + _consecutiveFailures + '):', err.message);

            // Still show offline data - game continues to work
            if (window.updateSyncStatus) window.updateSyncStatus('offline');

            // Show a toast on first failure
            if (_consecutiveFailures === 1 && window.GameHUD) {
                GameHUD.showToast('离线模式：数据将在恢复连接后同步', 'warning', 3000);
            }
        });
    }

    /**
     * Resolve conflicts between server and local state
     * - Server wins for farm/crops/inventory/emotions (persistent data)
     * - Local wins for UI state (selected tool, status, etc.)
     */
    function resolveConflicts(serverData, localState) {
        var merged = {};

        // Server wins for persistent game data
        for (var i = 0; i < SERVER_WINS_KEYS.length; i++) {
            var key = SERVER_WINS_KEYS[i];
            if (serverData[key] !== undefined) {
                merged[key] = serverData[key];
            }
        }

        // Local wins for temporary UI state
        for (var j = 0; j < LOCAL_WINS_KEYS.length; j++) {
            var lKey = LOCAL_WINS_KEYS[j];
            if (localState[lKey] !== undefined) {
                merged[lKey] = localState[lKey];
            }
        }

        // For other keys, prefer server data
        var allKeys = Object.keys(serverData);
        for (var k = 0; k < allKeys.length; k++) {
            var sKey = allKeys[k];
            if (merged[sKey] === undefined) {
                merged[sKey] = serverData[sKey];
            }
        }

        return merged;
    }

    function scheduleSave() {
        clearTimeout(_saveTimeout);
        _saveTimeout = setTimeout(function () {
            saveGameState(false);
        }, SAVE_DEBOUNCE);
    }

    /**
     * Save pending actions to server
     * @param {boolean} immediate - If true, skip debounce (for beforeunload)
     */
    function saveGameState(immediate) {
        var state = GameState.getState();

        // Don't save if not logged in
        if (!window.GameAPI || !GameAPI.isLoggedIn()) return;

        // Don't save if there are no pending actions
        if (!state.pendingActions || state.pendingActions.length === 0) return;

        if (_isSyncing && !immediate) return;
        _isSyncing = true;

        if (window.updateSyncStatus) window.updateSyncStatus('syncing');

        var actions = state.pendingActions.slice();

        GameAPI.sync(actions).then(function (result) {
            _consecutiveFailures = 0;
            _isSyncing = false;
            GameState.dispatch({ type: 'CLEAR_PENDING' });
            if (window.updateSyncStatus) window.updateSyncStatus('synced');
            console.log('[Sync] Saved ' + actions.length + ' actions');
        }).catch(function (err) {
            _isSyncing = false;
            _consecutiveFailures++;
            console.warn('[Sync] Save failed (' + _consecutiveFailures + '):', err.message);

            if (window.updateSyncStatus) window.updateSyncStatus('offline');

            // Keep pending actions for retry - they'll be sent on next sync
            // If too many failures, show warning
            if (_consecutiveFailures === MAX_CONSECUTIVE_FAILURES && window.GameHUD) {
                GameHUD.showToast('多次同步失败，数据将在恢复连接后自动同步', 'warning', 4000);
            }
        });
    }

    /**
     * Force an immediate sync (used by external modules)
     */
    function forceSync() {
        return loadGameState();
    }

    /**
     * Get current sync status info
     */
    function getSyncInfo() {
        return {
            initialized: _initialized,
            isSyncing: _isSyncing,
            consecutiveFailures: _consecutiveFailures,
            pendingActions: GameState.getState().pendingActions ? GameState.getState().pendingActions.length : 0
        };
    }

    function destroy() {
        _initialized = false;
        clearInterval(_syncInterval);
        clearTimeout(_saveTimeout);
        _syncInterval = null;
        _saveTimeout = null;
        _isSyncing = false;

        // Final save attempt
        if (window.GameAPI && GameAPI.isLoggedIn()) {
            saveGameState(true);
        }

        console.log('[Sync] Backend sync destroyed');
    }

    window.GameSync = {
        init: init,
        loadGameState: loadGameState,
        scheduleSave: scheduleSave,
        saveGameState: saveGameState,
        forceSync: forceSync,
        getSyncInfo: getSyncInfo,
        destroy: destroy
    };
})();
