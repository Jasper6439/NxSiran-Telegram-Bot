/**
 * NxSiran Mini App - Farm Page Module
 * HTML-based farm grid (6x4), seed shop, inventory, chat, gifts, daily, cooking, weather, events.
 */
(function () {
    'use strict';

    var farmData = null;
    var cropTypes = null;
    var selectedSeed = null;
    var autoRefreshTimer = null;

    /**
     * Initialize the farm page.
     */
    function init() {
        setupChatInput();
        setupDailyButton();
        setupRefreshButton();
    }

    /**
     * Called when the farm page is entered.
     */
    function onPageEnter() {
        if (!window.Auth || !window.Auth.isLoggedIn) return;
        loadFarm();
        startAutoRefresh();
    }

    /**
     * Called when the farm page is left.
     */
    function onPageLeave() {
        stopAutoRefresh();
    }

    // ===== Auto Refresh =====
    function startAutoRefresh() {
        stopAutoRefresh();
        autoRefreshTimer = setInterval(function () {
            var farmPage = document.getElementById('page-farm');
            if (farmPage && farmPage.classList.contains('active')) {
                loadFarm();
            } else {
                stopAutoRefresh();
            }
        }, 30000);
    }

    function stopAutoRefresh() {
        if (autoRefreshTimer) {
            clearInterval(autoRefreshTimer);
            autoRefreshTimer = null;
        }
    }

    // ===== Main Farm Load =====
    function loadFarm() {
        if (!window.Auth || !window.Auth.isLoggedIn) return;

        window.API.farm.get().then(function (data) {
            if (data.success) {
                farmData = data.farm;
                cropTypes = data.crop_types;
                renderFarm();
                renderSeedShop();
                renderInventory(data.inventory || []);
                renderGiftArea(data.inventory || []);
                updateFarmUI();
            } else {
                console.error('\u52A0\u8F7D\u519C\u573A\u5931\u8D25:', data.error);
            }
        }).catch(function (e) {
            console.error('\u519C\u573FAPI\u9519\u8BEF:', e);
        });

        // Load character location
        loadCharacterLocation();

        // Weather, events, daily, recipes
        updateWeather();
        checkHeartEvents();
        checkDailyStatus();
        loadRecipes();
    }

    // ===== Character Location =====
    function loadCharacterLocation() {
        window.API.character.location().then(function (data) {
            if (data.success) {
                var loc = data.location;
                var locText = loc ? '\uD83D\uDCCD ' + (loc.location || '\u672A\u77E5') + ' - ' + (loc.activity || '') : '\uD83D\uDCCD \u4E0D\u5728';
                var locEl = document.getElementById('character-location');
                if (locEl) locEl.textContent = locText;

                if (data.relationship) {
                    var hearts = data.relationship.hearts || 0;
                    var heartStr = '';
                    for (var i = 0; i < 10; i++) {
                        heartStr += i < hearts ? '\u2764\uFE0F' : '\u2661';
                    }
                    var heartsEl = document.getElementById('character-hearts');
                    if (heartsEl) heartsEl.textContent = heartStr;
                }
            }
        }).catch(function () { /* ignore */ });
    }

    // ===== Farm Grid Rendering =====
    function renderFarm() {
        var grid = document.getElementById('farm-grid');
        if (!grid) return;
        grid.innerHTML = '';

        for (var y = 0; y < 4; y++) {
            for (var x = 0; x < 6; x++) {
                var tile = document.createElement('div');
                tile.className = 'farm-tile';
                tile.dataset.x = x;
                tile.dataset.y = y;

                (function (tx, ty) {
                    tile.addEventListener('click', function () {
                        onTileClick(tx, ty);
                    });
                })(x, y);

                var crop = findCrop(x, y);
                if (crop) {
                    var cropInfo = getCropInfo(crop.crop_type);
                    var emoji = cropInfo ? cropInfo.emoji : '\uD83C\uDF31';
                    var stage = crop.growth_stage || 0;

                    tile.classList.add('tile-has-crop');
                    tile.classList.add('tile-crop-stage-' + stage);

                    var stageEmojis = {
                        0: '\u00B7',
                        1: '\uD83C\uDF31',
                        2: '\uD83C\uDF3F',
                        3: emoji
                    };

                    tile.textContent = stageEmojis[stage] || emoji;

                    if (crop.is_harvestable) {
                        tile.classList.add('tile-ready');
                        tile.textContent = emoji;
                    }
                } else {
                    tile.classList.add('tile-empty');
                }

                grid.appendChild(tile);
            }
        }

        updateSceneWeather();
    }

    function findCrop(x, y) {
        if (!farmData || !farmData.crops) return null;
        for (var i = 0; i < farmData.crops.length; i++) {
            if (farmData.crops[i].tile_x == x && farmData.crops[i].tile_y == y) {
                return farmData.crops[i];
            }
        }
        return null;
    }

    function getCropInfo(cropType) {
        if (!cropTypes) return null;
        for (var i = 0; i < cropTypes.length; i++) {
            if (cropTypes[i].id == cropType) return cropTypes[i];
        }
        return null;
    }

    // ===== Tile Click =====
    function onTileClick(x, y) {
        var crop = findCrop(x, y);

        if (crop && crop.is_harvestable) {
            harvestCrop(x, y);
        } else if (!crop && selectedSeed) {
            plantCrop(x, y, selectedSeed);
        } else if (!crop) {
            window.Toast.show('\u8BF7\u5148\u5728\u5546\u5E97\u9009\u62E9\u79CD\u5B50', 'info');
        }
    }

    // ===== Plant =====
    function plantCrop(x, y, cropType) {
        window.API.farm.plant(x, y, cropType).then(function (data) {
            if (data.success) {
                window.Toast.show('\u79CD\u4E0B\u4E86\uFF01', 'success');
                loadFarm();
            } else {
                window.Toast.show(data.error || '\u79CD\u690D\u5931\u8D25', 'error');
            }
        });
    }

    // ===== Harvest =====
    function harvestCrop(x, y) {
        window.API.farm.harvest(x, y).then(function (data) {
            if (data.success) {
                window.Toast.show('\u6536\u83B7 ' + (data.emoji || '') + ' ' + (data.crop_name || ''), 'success');
                loadFarm();
            } else {
                window.Toast.show(data.error || '\u6536\u83B7\u5931\u8D25', 'error');
            }
        });
    }

    // ===== Seed Shop =====
    function renderSeedShop() {
        var shop = document.getElementById('seed-shop');
        if (!shop) return;
        shop.innerHTML = '';

        if (!cropTypes) return;

        cropTypes.forEach(function (crop) {
            var item = document.createElement('div');
            item.className = 'seed-item';
            item.innerHTML =
                '<div style="font-size:1.5rem">' + crop.emoji + '</div>' +
                '<div style="font-size:0.7rem;margin-top:4px">' + crop.name + '</div>' +
                '<div style="font-size:0.7rem;color:var(--warning)">\uD83D\uDCB0' + crop.seed_price + '</div>';

            (function (cropId) {
                item.addEventListener('click', function () { buySeed(cropId); });
            })(crop.id);

            shop.appendChild(item);
        });
    }

    function buySeed(cropType) {
        window.API.farm.buySeed(cropType, 1).then(function (data) {
            if (data.success) {
                window.Toast.show('\u8D2D\u4E70\u6210\u529F\uFF01\u70B9\u51FB\u519C\u7530\u79CD\u690D', 'success');
                selectedSeed = cropType;
                loadFarm();
            } else {
                window.Toast.show(data.error || '\u8D2D\u4E70\u5931\u8D25', 'error');
            }
        });
    }

    // ===== Inventory =====
    function renderInventory(items) {
        var inv = document.getElementById('inventory');
        if (!inv) return;

        if (!items || items.length === 0) {
            inv.innerHTML = '<div style="text-align: center; color: var(--text-muted); grid-column: span 4; font-size: 0.85rem;">\u7A7A\u7A7A\u5982\u4E5F</div>';
            return;
        }

        inv.innerHTML = '';
        items.forEach(function (item) {
            var div = document.createElement('div');
            div.className = 'inventory-slot';

            var cropInfo = getCropInfo(item.item_id);
            var emoji = cropInfo ? cropInfo.emoji : '\uD83D\uDCE6';
            var name = cropInfo ? cropInfo.name : item.item_id;

            div.innerHTML =
                '<div style="font-size:1.2rem">' + emoji + '</div>' +
                '<div style="font-size:0.65rem">' + name + '</div>' +
                '<div style="font-size:0.65rem;color:var(--text-muted)">x' + item.quantity + '</div>';

            (function (itemId, qty) {
                div.addEventListener('click', function () { sellCrop(itemId, qty); });
            })(item.item_id, item.quantity);

            inv.appendChild(div);
        });
    }

    // ===== Sell =====
    function sellCrop(cropType, quantity) {
        if (!confirm('\u51FA\u552E\u8FD9\u4E2A\u4F5C\u7269\uFF1F')) return;

        window.API.farm.sell(cropType, 1).then(function (data) {
            if (data.success) {
                window.Toast.show(data.message, 'success');
                loadFarm();
            } else {
                window.Toast.show(data.error || '\u51FA\u552E\u5931\u8D25', 'error');
            }
        });
    }

    // ===== Farm UI =====
    function updateFarmUI() {
        if (farmData) {
            var nameEl = document.getElementById('farm-name');
            var moneyEl = document.getElementById('farm-money');
            if (nameEl) nameEl.textContent = farmData.farm_name || '\u6211\u7684\u519C\u573A';
            if (moneyEl) moneyEl.textContent = '\uD83D\uDCB0 ' + (farmData.money || 0);
        }
    }

    function refreshFarm() {
        window.Toast.show('\u5237\u65B0\u4E2D...', 'info');
        loadFarm();
    }

    function setupRefreshButton() {
        // The refresh button in the farm card has onclick="refreshFarm()"
        var refreshBtns = document.querySelectorAll('[onclick="refreshFarm()"]');
        refreshBtns.forEach(function (btn) {
            btn.removeAttribute('onclick');
            btn.addEventListener('click', refreshFarm);
        });
    }

    // ===== Game Chat =====
    function setupChatInput() {
        var chatInput = document.getElementById('game-chat-input');
        if (!chatInput) return;

        // Remove inline onclick from send button
        var sendBtn = chatInput.parentElement.querySelector('.btn-small');
        if (sendBtn) {
            sendBtn.removeAttribute('onclick');
            sendBtn.addEventListener('click', sendGameChat);
        }

        // Enter key
        chatInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                sendGameChat();
            }
        });
    }

    function sendGameChat() {
        var input = document.getElementById('game-chat-input');
        var message = input ? input.value.trim() : '';
        if (!message) return;

        if (input) input.value = '';

        var chatBox = document.getElementById('game-chat-box');
        if (!chatBox) return;

        var esc = window.App ? window.App.escapeHtml : function (s) { return s; };

        chatBox.innerHTML += '<div style="text-align:right;margin:4px 0;"><span style="background:var(--gradient-purple);color:white;padding:6px 12px;border-radius:12px;display:inline-block;font-size:0.85rem;">' + esc(message) + '</span></div>';
        chatBox.innerHTML += '<div id="chat-loading" style="text-align:center;color:var(--text-muted);font-size:0.8rem;">...</div>';
        chatBox.scrollTop = chatBox.scrollHeight;

        window.API.character.chat(message).then(function (data) {
            var loading = document.getElementById('chat-loading');
            if (loading) loading.remove();

            if (data.success) {
                chatBox.innerHTML += '<div style="margin:4px 0;"><span style="background:var(--card-bg);padding:6px 12px;border-radius:12px;display:inline-block;font-size:0.85rem;box-shadow:2px 2px 4px var(--shadow-color);">' + esc(data.response) + '</span></div>';
                loadCharacterLocation();
            } else {
                chatBox.innerHTML += '<div style="color:#F44336;font-size:0.8rem;">...\uFF08\u6C89\u9ED8\uFF09</div>';
            }
            chatBox.scrollTop = chatBox.scrollHeight;
        }).catch(function () {
            var loading = document.getElementById('chat-loading');
            if (loading) loading.remove();
            chatBox.innerHTML += '<div style="color:#F44336;font-size:0.8rem;">...\u7F51\u7EDC\u95EE\u9898\u3002</div>';
        });
    }

    // ===== Gift System =====
    function renderGiftArea(items) {
        var giftArea = document.getElementById('gift-area');
        if (!giftArea) return;

        if (!items || items.length === 0) {
            giftArea.innerHTML = '<div style="text-align: center; color: var(--text-muted); font-size: 0.85rem;">\u6536\u83B7\u4F5C\u7269\u540E\u53EF\u4EE5\u9001\u7ED9\u8F66\u5982\u4E91</div>';
            return;
        }

        var giftItems = items.filter(function (item) { return item.item_type === 'crop'; });

        if (giftItems.length === 0) {
            giftArea.innerHTML = '<div style="text-align: center; color: var(--text-muted); font-size: 0.85rem;">\u6CA1\u6709\u53EF\u4EE5\u9001\u7684\u4F5C\u7269</div>';
            return;
        }

        giftArea.innerHTML = '';
        giftItems.forEach(function (item) {
            var cropInfo = getCropInfo(item.item_id);
            var emoji = cropInfo ? cropInfo.emoji : '\uD83D\uDCE6';
            var name = cropInfo ? cropInfo.name : item.item_id;

            var div = document.createElement('div');
            div.className = 'seed-item';
            div.style.display = 'inline-block';
            div.style.margin = '4px';
            div.style.verticalAlign = 'top';
            div.innerHTML =
                '<div style="font-size:1.2rem">' + emoji + '</div>' +
                '<div style="font-size:0.65rem">' + name + '</div>' +
                '<div style="font-size:0.6rem;color:var(--text-muted)">x' + item.quantity + '</div>' +
                '<div style="font-size:0.6rem;color:var(--success)">\u9001\u51FA</div>';

            (function (itemType, itemId) {
                div.addEventListener('click', function () { sendGift(itemType, itemId); });
            })(item.item_type, item.item_id);

            giftArea.appendChild(div);
        });
    }

    function sendGift(itemType, itemId) {
        window.API.character.gift(itemType, itemId).then(function (data) {
            if (data.success) {
                var reactionEmoji = { love: '\uD83D\uDE0D', like: '\uD83D\uDE0A', neutral: '\uD83D\uDE10', dislike: '\uD83D\uDE15', hate: '\uD83D\uDE24' };
                var emoji = reactionEmoji[data.reaction] || '\uD83D\uDE10';
                window.Toast.show(emoji + ' ' + data.response, 'success');
                loadFarm();
            } else {
                window.Toast.show(data.error || '\u9001\u793C\u5931\u8D25', 'error');
            }
        });
    }

    // ===== Heart Events =====
    function checkHeartEvents() {
        if (!window.Auth || !window.Auth.isLoggedIn) return;

        window.API.events.heart().then(function (data) {
            var hint = document.getElementById('event-hint');
            if (data.success && data.events && data.events.length > 0) {
                if (hint) hint.style.display = 'block';
                showHeartEvent(data.events[0]);
            } else {
                if (hint) hint.style.display = 'none';
            }
        }).catch(function () { /* ignore */ });
    }

    function showHeartEvent(event) {
        var modal = document.getElementById('heart-event-modal');
        if (!modal) return;

        var esc = window.App ? window.App.escapeHtml : function (s) { return s; };

        document.getElementById('event-title').textContent = '\uD83D\uDC95 ' + (event.title || '\u5FC3\u7EA7\u4E8B\u4EF6');
        document.getElementById('event-description').textContent = event.description || '';
        document.getElementById('event-dialogue').innerHTML = '<div style="text-align:center;color:var(--text-muted);">\u52A0\u8F7D\u4E2D...</div>';
        document.getElementById('event-rewards').textContent = '';

        modal.style.display = 'flex';

        window.API.events.trigger(event.id).then(function (data) {
            if (data.success) {
                var evt = data.event;
                var dialogueHtml = '';

                if (evt.dialogue && evt.dialogue.length > 0) {
                    evt.dialogue.forEach(function (line) {
                        var isPlayer = line.speaker !== 'chayewoon';
                        var align = isPlayer ? 'right' : 'left';
                        var bgColor = isPlayer ? 'var(--gradient-purple)' : 'var(--card-bg)';
                        var textColor = isPlayer ? 'white' : 'var(--text)';
                        var name = isPlayer ? '\u5B66\u957F' : '\u8F66\u5982\u4E91';
                        dialogueHtml += '<div style="text-align:' + align + ';margin:6px 0;">';
                        dialogueHtml += '<div style="font-size:0.7rem;color:var(--text-muted);margin-bottom:2px;">' + name + '</div>';
                        dialogueHtml += '<span style="background:' + bgColor + ';color:' + textColor + ';padding:8px 12px;border-radius:12px;display:inline-block;font-size:0.85rem;max-width:80%;">' + esc(line.text) + '</span>';
                        dialogueHtml += '</div>';
                    });
                }

                document.getElementById('event-dialogue').innerHTML = dialogueHtml;

                var rewards = evt.rewards || {};
                var rewardText = [];
                if (rewards.hearts) rewardText.push('\u2764\uFE0F +' + rewards.hearts + ' \u4EB2\u5BC6\u5EA6');
                if (rewards.item) rewardText.push('\uD83C\uDF81 ' + rewards.item);
                if (rewardText.length > 0) {
                    document.getElementById('event-rewards').textContent = rewardText.join('  ');
                }

                if (data.relationship) {
                    var hearts = data.relationship.hearts || 0;
                    var heartStr = '';
                    for (var i = 0; i < 10; i++) {
                        heartStr += i < hearts ? '\u2764\uFE0F' : '\u2661';
                    }
                    var heartsEl = document.getElementById('character-hearts');
                    if (heartsEl) heartsEl.textContent = heartStr;
                }
            }
        }).catch(function () { /* ignore */ });
    }

    function closeEventModal() {
        var modal = document.getElementById('heart-event-modal');
        if (modal) modal.style.display = 'none';
    }

    // Wire up close event modal button
    document.addEventListener('DOMContentLoaded', function () {
        var closeBtns = document.querySelectorAll('[onclick="closeEventModal()"]');
        closeBtns.forEach(function (btn) {
            btn.removeAttribute('onclick');
            btn.addEventListener('click', closeEventModal);
        });
    });

    // ===== Weather System =====
    var currentWeather = 'sunny';
    var weatherEmojis = { sunny: '\u2600\uFE0F', rainy: '\uD83C\uDF27\uFE0F', cloudy: '\u2601\uFE0F', snowy: '\u2744\uFE0F', windy: '\uD83C\uDF2C\uFE0F' };
    var weatherNames = { sunny: '\u6674\u5929', rainy: '\u96E8\u5929', cloudy: '\u591A\u4E91', snowy: '\u4E0B\u96EA', windy: '\u5927\u98CE' };

    function updateWeather() {
        var hour = new Date().getHours();
        var day = new Date().getDate();
        var seed = (day * 31 + Math.floor(hour / 6)) % 100;

        if (seed < 55) currentWeather = 'sunny';
        else if (seed < 70) currentWeather = 'cloudy';
        else if (seed < 82) currentWeather = 'rainy';
        else if (seed < 90) currentWeather = 'windy';
        else currentWeather = 'rainy';

        var weatherIcon = document.getElementById('weather-icon');
        var weatherName = document.getElementById('weather-name');
        if (weatherIcon) weatherIcon.textContent = weatherEmojis[currentWeather] || '\u2600\uFE0F';
        if (weatherName) weatherName.textContent = weatherNames[currentWeather] || '\u6674\u5929';
    }

    function updateSceneWeather() {
        var scene = document.getElementById('farm-scene');
        if (!scene) return;

        scene.classList.remove('weather-rainy');

        if (currentWeather === 'rainy') {
            scene.classList.add('weather-rainy');
        }
    }

    // ===== Daily Reward =====
    function checkDailyStatus() {
        if (!window.Auth || !window.Auth.isLoggedIn) return;

        window.API.daily.check().then(function (data) {
            var btn = document.getElementById('daily-btn');
            if (data.success && data.claimed && btn) {
                btn.textContent = '\u2705 \u5DF2\u7B7E\u5230';
                btn.style.opacity = '0.5';
                btn.style.pointerEvents = 'none';
            }
        }).catch(function () { /* ignore */ });
    }

    function claimDaily() {
        window.API.daily.claim().then(function (data) {
            if (data.success) {
                window.Toast.show(data.message, 'success');
                var btn = document.getElementById('daily-btn');
                if (btn) {
                    btn.textContent = '\u2705 \u5DF2\u7B7E\u5230';
                    btn.style.opacity = '0.5';
                    btn.style.pointerEvents = 'none';
                }
                loadFarm();
            } else {
                window.Toast.show(data.message || '\u7B7E\u5230\u5931\u8D25', 'error');
            }
        });
    }

    function setupDailyButton() {
        var dailyBtn = document.getElementById('daily-btn');
        if (dailyBtn) {
            dailyBtn.removeAttribute('onclick');
            dailyBtn.addEventListener('click', claimDaily);
        }
    }

    // ===== Cooking =====
    function loadRecipes() {
        if (!window.Auth || !window.Auth.isLoggedIn) return;

        window.API.recipes.get().then(function (data) {
            if (data.success) {
                renderRecipes(data.recipes);
            }
        }).catch(function () { /* ignore */ });
    }

    function renderRecipes(recipes) {
        var list = document.getElementById('recipe-list');
        if (!list) return;

        if (!recipes || recipes.length === 0) {
            list.innerHTML = '<div style="text-align:center;color:var(--text-muted);grid-column:span 2;font-size:0.85rem;">\u6682\u65E0\u914D\u65B9</div>';
            return;
        }

        list.innerHTML = '';
        recipes.forEach(function (r) {
            var div = document.createElement('div');
            div.className = 'seed-item';
            div.style.opacity = r.can_cook ? '1' : '0.5';

            var ingText = '';
            try {
                var ings = JSON.parse(r.ingredients);
                ingText = ings.map(function (i) {
                    return getCropInfo(i.crop) ? getCropInfo(i.crop).emoji + 'x' + i.qty : i.crop;
                }).join(' ');
            } catch (e) { /* ignore */ }

            div.innerHTML =
                '<div style="font-size:1.3rem">' + r.emoji + '</div>' +
                '<div style="font-size:0.7rem;font-weight:600">' + r.name + '</div>' +
                '<div style="font-size:0.6rem;color:var(--text-muted)">' + ingText + '</div>' +
                (r.can_cook
                    ? '<div style="font-size:0.6rem;color:var(--success)">\u53EF\u70F9\u996A</div>'
                    : '<div style="font-size:0.6rem;color:#F44336">\u6750\u6599\u4E0D\u8DB3</div>');

            if (r.can_cook) {
                (function (recipeId) {
                    div.addEventListener('click', function () { cookRecipe(recipeId); });
                })(r.id);
            }

            list.appendChild(div);
        });
    }

    function cookRecipe(recipeId) {
        window.API.cook(recipeId).then(function (data) {
            if (data.success) {
                window.Toast.show(data.message, 'success');
                loadFarm();
                loadRecipes();
            } else {
                window.Toast.show(data.error || '\u70F9\u996A\u5931\u8D25', 'error');
            }
        });
    }

    // ===== Export =====
    window.FarmPage = {
        init: init,
        onPageEnter: onPageEnter,
        onPageLeave: onPageLeave,
        loadFarm: loadFarm,
        refreshFarm: refreshFarm,
        closeEventModal: closeEventModal
    };
})();
