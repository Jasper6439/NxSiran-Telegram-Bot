/**
 * NxSiran Game - Inventory System
 * Manages player items, toolbar UI, shop panel
 */
(function () {
    'use strict';

    var _toolbarEl = null;
    var _shopPanelEl = null;
    var _inventoryPanelEl = null;

    // ── Initialize ─────────────────────────────────────────────
    function init() {
        _toolbarEl = document.getElementById('toolbar');
        _shopPanelEl = document.getElementById('shop-panel');
        _inventoryPanelEl = document.getElementById('inventory-panel');
        updateUI();
    }

    // ── Update UI ──────────────────────────────────────────────
    function updateUI() {
        updateToolbar();
        updateHUD();
    }

    function updateToolbar() {
        if (!_toolbarEl) return;
        var state = GameState.getState();
        var html = '';

        // Tools
        html += '<div class="toolbar-item' + (state.selectedTool && state.selectedTool.type === 'tool' && state.selectedTool.item === 'watering_can' ? ' selected' : '') + '" onclick="GameActions.selectTool(\'tool\', \'watering_can\')">';
        html += '<div class="toolbar-icon">\uD83D\uDCA7</div>';
        html += '<div class="toolbar-label">\u6D47\u6C34</div>';
        html += '</div>';

        // Seeds from inventory
        var invKeys = Object.keys(state.inventory);
        for (var i = 0; i < invKeys.length; i++) {
            var key = invKeys[i];
            var item = state.inventory[key];
            if (item.type === 'seed' && item.quantity > 0) {
                var cropType = key.replace('seed_', '');
                var isSelected = state.selectedTool && state.selectedTool.type === 'seed' && state.selectedTool.item === cropType;
                html += '<div class="toolbar-item' + (isSelected ? ' selected' : '') + '" onclick="GameActions.selectTool(\'seed\', \'' + cropType + '\')">';
                html += '<div class="toolbar-icon">' + (GameState.getCropEmoji(cropType) || '\uD83C\uDF31') + '</div>';
                html += '<div class="toolbar-label">' + item.quantity + '</div>';
                html += '</div>';
            }
        }

        // Harvest mode
        html += '<div class="toolbar-item' + (state.selectedTool && state.selectedTool.type === 'harvest' ? ' selected' : '') + '" onclick="GameActions.selectTool(\'harvest\', null)">';
        html += '<div class="toolbar-icon">\uD83E\uDDF1</div>';
        html += '<div class="toolbar-label">\u6536\u83B7</div>';
        html += '</div>';

        _toolbarEl.innerHTML = html;
    }

    function updateHUD() {
        var state = GameState.getState();
        var moneyEl = document.getElementById('hud-money');
        var heartsEl = document.getElementById('hud-hearts');
        if (moneyEl) moneyEl.textContent = state.farm.money;
        if (heartsEl) heartsEl.textContent = state.hearts;
    }

    // ── Shop Panel ─────────────────────────────────────────────
    function openShop() {
        if (!_shopPanelEl) return;
        var state = GameState.getState();
        var cropTypes = state.cropTypes;
        var html = '<div class="panel-header"><h3>\uD83D\uDED2 \u79CD\u5B50\u5546\u5E97</h3><button class="panel-close" onclick="GameInventory.closeShop()">\u2715</button></div>';
        html += '<div class="shop-grid">';

        var ctKeys = Object.keys(cropTypes);
        for (var i = 0; i < ctKeys.length; i++) {
            var id = ctKeys[i];
            var ct = cropTypes[id];
            html += '<div class="shop-item">';
            html += '<div class="shop-item-icon">' + (ct.emoji || '\uD83C\uDF31') + '</div>';
            html += '<div class="shop-item-info">';
            html += '<div class="shop-item-name">' + ct.name + '</div>';
            html += '<div class="shop-item-price">\uD83D\uDCB0 ' + ct.seedPrice + '</div>';
            html += '</div>';
            html += '<button class="shop-buy-btn" onclick="GameInventory.buySeed(\'' + id + '\')">+1</button>';
            html += '</div>';
        }

        html += '</div>';
        _shopPanelEl.innerHTML = html;
        _shopPanelEl.classList.add('open');
    }

    function closeShop() {
        if (_shopPanelEl) _shopPanelEl.classList.remove('open');
    }

    function buySeed(cropType) {
        var state = GameState.getState();
        var ct = state.cropTypes[cropType];
        if (!ct) return;

        if (state.farm.money < ct.seedPrice) {
            if (window.GameHUD) GameHUD.showToast('\u91D1\u5E01\u4E0D\u8DB3', 'warning');
            return;
        }

        GameState.dispatch({
            type: 'BUY_SEED',
            cropType: cropType,
            quantity: 1,
            cost: ct.seedPrice
        });

        if (window.GameAPI) {
            GameAPI.buySeed(cropType, 1).catch(function () {});
        }

        updateUI();
        if (window.GameHUD) GameHUD.showToast('\u8D2D\u4E70\u4E86 ' + ct.name + ' \u79CD\u5B50', 'success');
    }

    // ── Inventory Panel ────────────────────────────────────────
    function openInventory() {
        if (!_inventoryPanelEl) return;
        var state = GameState.getState();
        var html = '<div class="panel-header"><h3>\uD83D\uDCBC \u6211\u7684\u80CC\u5305</h3><button class="panel-close" onclick="GameInventory.closeInventory()">\u2715</button></div>';
        html += '<div class="inventory-grid">';

        var invKeys = Object.keys(state.inventory);
        var hasItems = false;
        for (var i = 0; i < invKeys.length; i++) {
            var key = invKeys[i];
            var item = state.inventory[key];
            if (item.quantity > 0) {
                hasItems = true;
                var canSell = item.type === 'crop';
                html += '<div class="inv-item">';
                html += '<div class="inv-item-icon">' + (item.emoji || '\uD83D\uDCE6') + '</div>';
                html += '<div class="inv-item-info">';
                html += '<div class="inv-item-name">' + item.name + '</div>';
                html += '<div class="inv-item-qty">x' + item.quantity + '</div>';
                html += '</div>';
                if (canSell) {
                    var cropType = key.replace('crop_', '');
                    var sellPrice = state.cropTypes[cropType] ? state.cropTypes[cropType].sellPrice : 10;
                    html += '<button class="inv-sell-btn" onclick="GameInventory.sellCrop(\'' + cropType + '\')">\u5356 ' + sellPrice + '\uD83D\uDCB0</button>';
                }
                html += '</div>';
            }
        }

        if (!hasItems) {
            html += '<div class="empty-inventory">\u80CC\u5305\u7A7A\u7A7A\u5982\u4E5F</div>';
        }

        html += '</div>';
        _inventoryPanelEl.innerHTML = html;
        _inventoryPanelEl.classList.add('open');
    }

    function closeInventory() {
        if (_inventoryPanelEl) _inventoryPanelEl.classList.remove('open');
    }

    function sellCrop(cropType) {
        var state = GameState.getState();
        var cropKey = 'crop_' + cropType;
        var item = state.inventory[cropKey];
        if (!item || item.quantity <= 0) return;

        var ct = state.cropTypes[cropType];
        var sellPrice = ct ? ct.sellPrice : 10;

        GameState.dispatch({
            type: 'SELL_CROP',
            cropType: cropType,
            quantity: 1,
            earned: sellPrice
        });

        if (window.GameAPI) {
            GameAPI.sellCrop(cropType, 1).catch(function () {});
        }

        updateUI();
        openInventory(); // refresh panel
        if (window.GameHUD) GameHUD.showToast('\u5356\u51FA ' + GameState.getCropName(cropType) + ' \u83B7\u5F97 ' + sellPrice + ' \u91D1\u5E01', 'success');
    }

    // ── Export ─────────────────────────────────────────────────
    window.GameInventory = {
        init: init,
        updateUI: updateUI,
        updateToolbar: updateToolbar,
        updateHUD: updateHUD,
        openShop: openShop,
        closeShop: closeShop,
        buySeed: buySeed,
        openInventory: openInventory,
        closeInventory: closeInventory,
        sellCrop: sellCrop
    };
})();
