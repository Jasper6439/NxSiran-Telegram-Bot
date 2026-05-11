/**
 * NxSiran Game - Inventory System
 * Manages player items, toolbar UI, shop panel
 * v0.7 - Enhanced Shop & Gift System
 */
(function () {
    'use strict';

    var _toolbarEl = null;
    var _shopPanelEl = null;
    var _inventoryPanelEl = null;
    var _lastShopTab = 'seeds'; // remember last selected shop tab

    // ── Gift Items Data ─────────────────────────────────────────
    var GIFT_ITEMS = {
        'coffee': { name: '美式咖啡', emoji: '☕', price: 100, affection: 3, desc: '车如云训练后最需要的' },
        'bandaid': { name: '创可贴', emoji: '🩹', price: 50, affection: 2, desc: '田径部必备' },
        'cake': { name: '草莓蛋糕', emoji: '🍰', price: 200, affection: 5, happiness: 3, desc: '他似乎不讨厌甜食' },
        'book': { name: '推理小说', emoji: '📚', price: 150, affection: 4, desc: '天台独处时的伴侣' },
        'headphones': { name: '运动耳机', emoji: '🎧', price: 500, affection: 8, desc: '他丢了好几个了' },
        'raincoat': { name: '透明雨衣', emoji: '🧥', price: 300, affection: 6, desc: '梅雨季的关心' },
        'energy_drink': { name: '运动饮料', emoji: '🥤', price: 80, affection: 2, desc: '训练后的补给' },
        'photo_frame': { name: '相框', emoji: '🖼️', price: 400, affection: 7, desc: '放一张两人的合照' }
    };

    // ── Decoration Items Data ───────────────────────────────────
    var DECOR_ITEMS = {
        'flower_pot': { name: '小花盆', emoji: '🪴', price: 300, desc: '放在窗台上的绿植' },
        'lamp': { name: '星星灯串', emoji: '✨', price: 500, desc: '天台浪漫氛围' },
        'cushion': { name: '靠垫', emoji: '🛋️', price: 200, desc: '柔软的休息时光' }
    };

    // ── Gift Reactions Data ─────────────────────────────────────
    var GIFT_REACTIONS = {
        'coffee': [
            '...（接过咖啡，喝了一口）...还行。',
            '...你又来了。（但杯子已经空了）',
            '...训练后喝这个...谢谢。（小声）'
        ],
        'bandaid': [
            '...这点伤不算什么。',
            '...你随身带着这个？（贴上了）',
            '...多管闲事。（但没撕下来）'
        ],
        'cake': [
            '...我不吃甜的...（但拿起了叉子）',
            '...（看了一眼）...草莓的？...嗯。',
            '...太甜了。（但吃完了）'
        ],
        'book': [
            '...推理？...你看过这个作者？',
            '...（翻了两页）...还行。',
            '...天台上看...谢了。'
        ],
        'headphones': [
            '...你又买了？（接过去戴上了）',
            '...这个音质...不错。',
            '...丢了好几个了...别再买了。（但收下了）'
        ],
        'raincoat': [
            '...我不怕雨。',
            '...（梅雨天穿着）...还行。',
            '...你操心得太多了。'
        ],
        'energy_drink': [
            '...训练后喝这个...嗯。',
            '...又是这个牌子。（喝完了）',
            '...补给了。'
        ],
        'photo_frame': [
            '...合照？（看了很久）...什么时候拍的。',
            '...放在天台...（沉默了一会儿）',
            '......嗯。（转过身去）'
        ]
    };

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

    // ── Shop Panel (Enhanced with Tabs) ────────────────────────
    function openShop() {
        if (!_shopPanelEl) return;

        // v1.2a: Close other panels via panel manager
        if (window.GamePanels) GamePanels.open('shop');

        // v0.9: Switch BGM to shop track
        if (window.GameAudio) {
            GameAudio.playBGM('shop');
        }

        var state = GameState.getState();
        var tab = _lastShopTab || 'seeds';

        var html = '<div class="panel-header"><h3>\uD83D\uDED2 \u5546\u5E97</h3><button class="panel-close" onclick="GameInventory.closeShop()">\u2715</button></div>';

        // Tab bar
        html += '<div class="shop-tabs">';
        html += '<button class="shop-tab' + (tab === 'seeds' ? ' active' : '') + '" onclick="GameInventory.switchShopTab(\'seeds\')">\uD83C\uDF31 \u79CD\u5B50</button>';
        html += '<button class="shop-tab' + (tab === 'gifts' ? ' active' : '') + '" onclick="GameInventory.switchShopTab(\'gifts\')">\uD83C\uDF81 \u793C\u7269</button>';
        html += '<button class="shop-tab' + (tab === 'decor' ? ' active' : '') + '" onclick="GameInventory.switchShopTab(\'decor\')">\u2728 \u88C5\u9970</button>';
        html += '</div>';

        // Tab content container
        html += '<div class="shop-tab-content" id="shop-tab-content"></div>';

        _shopPanelEl.innerHTML = html;
        _shopPanelEl.classList.add('open');

        // Render the active tab
        renderShopTab(tab);
    }

    function switchShopTab(tab) {
        _lastShopTab = tab;
        // Update tab button active states
        var tabs = _shopPanelEl.querySelectorAll('.shop-tab');
        for (var i = 0; i < tabs.length; i++) {
            tabs[i].classList.remove('active');
        }
        // Find the clicked tab and activate it
        var tabNames = ['seeds', 'gifts', 'decor'];
        for (var j = 0; j < tabNames.length; j++) {
            if (tabNames[j] === tab && tabs[j]) {
                tabs[j].classList.add('active');
            }
        }
        renderShopTab(tab);
    }

    function renderShopTab(tab) {
        var contentEl = document.getElementById('shop-tab-content');
        if (!contentEl) return;
        var state = GameState.getState();
        var html = '';

        if (tab === 'seeds') {
            html += '<div class="shop-grid">';
            var cropTypes = state.cropTypes;
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
        } else if (tab === 'gifts') {
            html += '<div class="shop-grid shop-grid-gifts">';
            var giftKeys = Object.keys(GIFT_ITEMS);
            for (var g = 0; g < giftKeys.length; g++) {
                var gId = giftKeys[g];
                var gift = GIFT_ITEMS[gId];
                html += '<div class="shop-item gift-shop-item">';
                html += '<div class="shop-item-icon">' + gift.emoji + '</div>';
                html += '<div class="shop-item-info">';
                html += '<div class="shop-item-name">' + gift.name + '</div>';
                html += '<div class="shop-item-desc">' + gift.desc + '</div>';
                html += '<div class="shop-item-price">\uD83D\uDCB0 ' + gift.price + ' <span class="gift-affection-hint">\uD83D\uDC95+' + gift.affection + '</span></div>';
                html += '</div>';
                html += '<button class="shop-buy-btn gift-buy-btn" onclick="GameInventory.buyGift(\'' + gId + '\')">+1</button>';
                html += '</div>';
            }
            html += '</div>';
        } else if (tab === 'decor') {
            html += '<div class="shop-grid">';
            var decorKeys = Object.keys(DECOR_ITEMS);
            for (var d = 0; d < decorKeys.length; d++) {
                var dId = decorKeys[d];
                var decor = DECOR_ITEMS[dId];
                html += '<div class="shop-item">';
                html += '<div class="shop-item-icon">' + decor.emoji + '</div>';
                html += '<div class="shop-item-info">';
                html += '<div class="shop-item-name">' + decor.name + '</div>';
                html += '<div class="shop-item-desc">' + decor.desc + '</div>';
                html += '<div class="shop-item-price">\uD83D\uDCB0 ' + decor.price + '</div>';
                html += '</div>';
                html += '<button class="shop-buy-btn" onclick="GameInventory.buyDecor(\'' + dId + '\')">+1</button>';
                html += '</div>';
            }
            html += '</div>';
        }

        contentEl.innerHTML = html;
    }

    function closeShop() {
        // v1.2a: Unregister from panel manager
        if (window.GamePanels) GamePanels.close('shop');
        // v0.9: Switch BGM back to previous track
        if (window.GameAudio) {
            GameAudio.playPreviousBGM();
        }
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

    // ── Buy Gift ────────────────────────────────────────────────
    function buyGift(giftId) {
        var gift = GIFT_ITEMS[giftId];
        if (!gift) return;

        var state = GameState.getState();
        if (state.farm.money < gift.price) {
            if (window.GameHUD) GameHUD.showToast('\u91D1\u5E01\u4E0D\u8DB3', 'warning');
            return;
        }

        // Deduct money
        GameState.dispatch({
            type: 'SPEND_MONEY',
            amount: gift.price
        });

        // Add gift to inventory
        var invKey = 'gift_' + giftId;
        var existing = state.inventory[invKey];
        if (existing) {
            GameState.dispatch({
                type: 'UPDATE_INVENTORY_ITEM',
                key: invKey,
                updates: { quantity: existing.quantity + 1 }
            });
        } else {
            GameState.dispatch({
                type: 'ADD_INVENTORY_ITEM',
                key: invKey,
                item: {
                    type: 'gift',
                    name: gift.name,
                    quantity: 1,
                    emoji: gift.emoji,
                    giftId: giftId
                }
            });
        }

        if (window.GameAPI) {
            GameAPI.buyItem('gift', giftId, 1).catch(function () {});
        }

        updateUI();
        renderShopTab('gifts'); // refresh shop display
        if (window.GameHUD) GameHUD.showToast('\u8D2D\u4E70\u4E86 ' + gift.emoji + ' ' + gift.name, 'success');
    }

    // ── Buy Decoration ──────────────────────────────────────────
    function buyDecor(decorId) {
        var decor = DECOR_ITEMS[decorId];
        if (!decor) return;

        var state = GameState.getState();
        if (state.farm.money < decor.price) {
            if (window.GameHUD) GameHUD.showToast('\u91D1\u5E01\u4E0D\u8DB3', 'warning');
            return;
        }

        // Deduct money
        GameState.dispatch({
            type: 'SPEND_MONEY',
            amount: decor.price
        });

        // Add decoration to inventory
        var invKey = 'decor_' + decorId;
        var existing = state.inventory[invKey];
        if (existing) {
            GameState.dispatch({
                type: 'UPDATE_INVENTORY_ITEM',
                key: invKey,
                updates: { quantity: existing.quantity + 1 }
            });
        } else {
            GameState.dispatch({
                type: 'ADD_INVENTORY_ITEM',
                key: invKey,
                item: {
                    type: 'decor',
                    name: decor.name,
                    quantity: 1,
                    emoji: decor.emoji,
                    decorId: decorId
                }
            });
        }

        if (window.GameAPI) {
            GameAPI.buyItem('decor', decorId, 1).catch(function () {});
        }

        updateUI();
        renderShopTab('decor'); // refresh shop display
        if (window.GameHUD) GameHUD.showToast('\u8D2D\u4E70\u4E86 ' + decor.emoji + ' ' + decor.name, 'success');
    }

    // ── Inventory Panel (Enhanced with Tabs) ────────────────────
    function openInventory() {
        if (!_inventoryPanelEl) return;

        // v1.2a: Close other panels via panel manager
        if (window.GamePanels) GamePanels.open('inventory');

        var state = GameState.getState();

        var html = '<div class="panel-header"><h3>\uD83D\uDCBC \u6211\u7684\u80CC\u5305</h3><button class="panel-close" onclick="GameInventory.closeInventory()">\u2715</button></div>';

        // Inventory tabs
        html += '<div class="shop-tabs">';
        html += '<button class="shop-tab active" id="inv-tab-all" onclick="GameInventory.switchInvTab(\'all\')">\uD83D\uDCE6 \u5168\u90E8</button>';
        html += '<button class="shop-tab" id="inv-tab-gifts" onclick="GameInventory.switchInvTab(\'gifts\')">\uD83C\uDF81 \u793C\u7269</button>';
        html += '</div>';

        html += '<div class="inventory-grid" id="inv-tab-content"></div>';

        _inventoryPanelEl.innerHTML = html;
        _inventoryPanelEl.classList.add('open');

        renderInvTab('all');
    }

    function switchInvTab(tab) {
        var allTab = document.getElementById('inv-tab-all');
        var giftsTab = document.getElementById('inv-tab-gifts');
        if (allTab) allTab.classList.toggle('active', tab === 'all');
        if (giftsTab) giftsTab.classList.toggle('active', tab === 'gifts');
        renderInvTab(tab);
    }

    function renderInvTab(tab) {
        var contentEl = document.getElementById('inv-tab-content');
        if (!contentEl) return;
        var state = GameState.getState();
        var html = '';

        var invKeys = Object.keys(state.inventory);
        var hasItems = false;

        for (var i = 0; i < invKeys.length; i++) {
            var key = invKeys[i];
            var item = state.inventory[key];

            // Filter by tab
            if (tab === 'gifts' && item.type !== 'gift') continue;

            if (item.quantity > 0) {
                hasItems = true;

                if (item.type === 'gift') {
                    // Gift item with "give" button
                    html += '<div class="inv-item gift-item">';
                    html += '<div class="inv-item-icon">' + (item.emoji || '\uD83D\uDCE6') + '</div>';
                    html += '<div class="inv-item-info">';
                    html += '<div class="inv-item-name">' + item.name + '</div>';
                    html += '<div class="inv-item-qty">x' + item.quantity + '</div>';
                    html += '</div>';
                    html += '<button class="gift-item-btn" onclick="GameInventory.giveGift(\'' + (item.giftId || key.replace('gift_', '')) + '\')">\uD83C\uDF81 \u9001\u7ED9\u5982\u4E91</button>';
                    html += '</div>';
                } else {
                    // Existing crop/seed item display
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
        }

        if (!hasItems) {
            if (tab === 'gifts') {
                html += '<div class="empty-inventory">\u8FD8\u6CA1\u6709\u793C\u7269\uFF0C\u53BB\u5546\u5E97\u770B\u770B\u5427\uFF01</div>';
            } else {
                html += '<div class="empty-inventory">\u80CC\u5305\u7A7A\u7A7A\u5982\u4E5F</div>';
            }
        }

        contentEl.innerHTML = html;
    }

    function closeInventory() {
        // v1.2a: Unregister from panel manager
        if (window.GamePanels) GamePanels.close('inventory');
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

    // ── Gift Panel ──────────────────────────────────────────────
    function openGiftPanel() {
        if (!_inventoryPanelEl) return;
        var state = GameState.getState();

        var html = '<div class="panel-header"><h3>\uD83C\uDF81 \u9001\u793C\u7269\u7ED9\u5982\u4E91</h3><button class="panel-close" onclick="GameInventory.closeInventory()">\u2715</button></div>';
        html += '<div class="gift-panel">';

        var invKeys = Object.keys(state.inventory);
        var hasGifts = false;

        for (var i = 0; i < invKeys.length; i++) {
            var key = invKeys[i];
            var item = state.inventory[key];
            if (item.type === 'gift' && item.quantity > 0) {
                hasGifts = true;
                var giftId = item.giftId || key.replace('gift_', '');
                var giftData = GIFT_ITEMS[giftId];
                html += '<div class="gift-item">';
                html += '<div class="gift-item-icon">' + (item.emoji || '\uD83C\uDF81') + '</div>';
                html += '<div class="gift-item-info">';
                html += '<div class="gift-item-name">' + item.name + '</div>';
                html += '<div class="gift-item-qty">x' + item.quantity + '</div>';
                if (giftData) {
                    html += '<div class="gift-item-desc">' + giftData.desc + '</div>';
                    html += '<div class="gift-item-effect">\uD83D\uDC95+' + giftData.affection + (giftData.happiness ? ' \uD83D\uDE04+' + giftData.happiness : '') + '</div>';
                }
                html += '</div>';
                html += '<button class="gift-item-btn" onclick="GameInventory.giveGift(\'' + giftId + '\')">\u9001\u51FA</button>';
                html += '</div>';
            }
        }

        if (!hasGifts) {
            html += '<div class="empty-inventory">\u8FD8\u6CA1\u6709\u793C\u7269\uFF0C\u53BB\u5546\u5E97\u4E70\u4E00\u4E9B\u5427\uFF01</div>';
        }

        html += '</div>';
        _inventoryPanelEl.innerHTML = html;
        _inventoryPanelEl.classList.add('open');
    }

    // ── Give Gift ───────────────────────────────────────────────
    function giveGift(giftId) {
        var state = GameState.getState();
        var gift = GIFT_ITEMS[giftId];
        if (!gift) return;

        var invKey = 'gift_' + giftId;
        var item = state.inventory[invKey];
        if (!item || item.quantity <= 0) {
            if (window.GameHUD) GameHUD.showToast('\u6CA1\u6709\u8FD9\u4E2A\u793C\u7269', 'warning');
            return;
        }

        // Remove 1 from inventory
        if (item.quantity <= 1) {
            GameState.dispatch({
                type: 'REMOVE_INVENTORY_ITEM',
                key: invKey
            });
        } else {
            GameState.dispatch({
                type: 'UPDATE_INVENTORY_ITEM',
                key: invKey,
                updates: { quantity: item.quantity - 1 }
            });
        }

        // Apply affection/happiness effects (using deltas format)
        var deltas = {};
        if (gift.affection) {
            deltas.affection = gift.affection;
        }
        if (gift.happiness) {
            deltas.happiness = gift.happiness;
        }

        if (Object.keys(deltas).length > 0) {
            GameState.dispatch({
                type: 'UPDATE_EMOTION_VALUES',
                characterId: 'chayewoon',
                deltas: deltas
            });
        }

        // Track gift stat for achievements
        GameState.dispatch({
            type: 'STAT_INCREMENT',
            stat: 'gifts_given',
            amount: 1
        });

        // Notify quests system
        if (window.GameQuests) {
            GameQuests.onAction('gift', 1);
        }

        // v0.9: Play gift SFX
        if (window.GameAudio) {
            GameAudio.playGift();
        }

        // Show floating effect animation
        showGiftEffect(gift);

        // v1.2e: Haptic feedback on gift give
        if (window.GameMiniApp) GameMiniApp.hapticFeedback('success');

        // Show reaction dialogue
        var reactions = GIFT_REACTIONS[giftId];
        var reaction = '';
        if (reactions && reactions.length > 0) {
            reaction = reactions[Math.floor(Math.random() * reactions.length)];
        } else {
            reaction = '...（默默收下了）';
        }
        showGiftReaction(gift.emoji + ' ' + gift.name, reaction);

        // Update emotion panel
        if (window.GameHUD && typeof GameHUD.updateEmotionPanel === 'function') {
            GameHUD.updateEmotionPanel();
        }

        // Update UI
        updateUI();

        // Refresh the currently open panel
        if (_inventoryPanelEl && _inventoryPanelEl.classList.contains('open')) {
            // Check if gift panel or inventory is showing by looking at content
            var giftPanel = _inventoryPanelEl.querySelector('.gift-panel');
            if (giftPanel) {
                openGiftPanel(); // refresh gift panel
            } else {
                renderInvTab('all'); // refresh inventory
            }
        }
    }

    // ── Gift Reaction Display ───────────────────────────────────
    function showGiftEffect(gift) {
        // Create floating "+N 💕" animation
        var effectEl = document.createElement('div');
        effectEl.className = 'gift-effect';
        var effectText = '';
        if (gift.affection) effectText += '+' + gift.affection + ' \uD83D\uDC95';
        if (gift.happiness) effectText += ' +' + gift.happiness + ' \uD83D\uDE04';
        effectEl.textContent = effectText;

        // Position near center of screen
        effectEl.style.left = '50%';
        effectEl.style.top = '40%';
        effectEl.style.transform = 'translateX(-50%)';

        document.body.appendChild(effectEl);

        // Remove after animation completes
        setTimeout(function () {
            if (effectEl.parentNode) {
                effectEl.parentNode.removeChild(effectEl);
            }
        }, 1500);
    }

    function showGiftReaction(itemName, reaction) {
        // Create reaction bubble overlay
        var overlay = document.createElement('div');
        overlay.className = 'gift-reaction-overlay';
        overlay.innerHTML =
            '<div class="gift-reaction">' +
            '<div class="gift-reaction-item">' + itemName + '</div>' +
            '<div class="gift-reaction-text">' + reaction + '</div>' +
            '<button class="gift-reaction-close" onclick="this.closest(\'.gift-reaction-overlay\').remove()">\u786E\u5B9A</button>' +
            '</div>';

        document.body.appendChild(overlay);

        // Auto-dismiss after 5 seconds
        setTimeout(function () {
            if (overlay.parentNode) {
                overlay.style.opacity = '0';
                setTimeout(function () {
                    if (overlay.parentNode) {
                        overlay.parentNode.removeChild(overlay);
                    }
                }, 300);
            }
        }, 5000);
    }

    // ── Export ─────────────────────────────────────────────────
    window.GameInventory = {
        init: init,
        updateUI: updateUI,
        updateToolbar: updateToolbar,
        updateHUD: updateHUD,
        openShop: openShop,
        closeShop: closeShop,
        switchShopTab: switchShopTab,
        buySeed: buySeed,
        buyGift: buyGift,
        buyDecor: buyDecor,
        openInventory: openInventory,
        closeInventory: closeInventory,
        switchInvTab: switchInvTab,
        sellCrop: sellCrop,
        openGiftPanel: openGiftPanel,
        giveGift: giveGift
    };
})();
