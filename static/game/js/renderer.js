/**
 * NxSiran Game - DOM Renderer
 * Renders game entities as positioned <div> elements using CSS calc()
 * Inspired by Sunflower Land's MapPlacement component
 */
(function () {
    'use strict';

    var GRID_WIDTH_PX = 40; // Will be set by main.js
    var _worldContainer = null;
    var _entityCache = {};
    var _viewportRect = { left: 0, top: 0, width: 0, height: 0 };

    // ── Asset paths ────────────────────────────────────────────
    var ASSETS = {
        tiles: {
            grass: '/static/game/assets/tiles/tiles_grass.jpg',
            earth: '/static/game/assets/tiles/tiles_earth.jpg',
            tilled: '/static/game/assets/tiles/tiles_tilled.jpg',
            watered: '/static/game/assets/tiles/tiles_watered.jpg',
            fence: '/static/game/assets/tiles/tiles_fence.jpg',
            pond: '/static/game/assets/tiles/tiles_pond.jpg'
        },
        crops: {
            tomato:    { seed: '/static/game/assets/crops/crops_tomato_seed.jpg', sprout: '/static/game/assets/crops/crops_tomato_sprout.jpg', growing: '/static/game/assets/crops/crops_tomato_growing.jpg', mature: '/static/game/assets/crops/crops_tomato_mature.jpg' },
            corn:      { seed: '/static/game/assets/crops/crops_corn_seed.jpg', sprout: '/static/game/assets/crops/crops_corn_sprout.jpg', growing: '/static/game/assets/crops/crops_corn_growing.jpg', mature: '/static/game/assets/crops/crops_corn_mature.jpg' },
            strawberry:{ seed: '/static/game/assets/crops/crops_strawberry_seed.jpg', sprout: '/static/game/assets/crops/crops_strawberry_sprout.jpg', growing: '/static/game/assets/crops/crops_strawberry_growing.jpg', mature: '/static/game/assets/crops/crops_strawberry_mature.jpg' },
            pumpkin:   { seed: '/static/game/assets/crops/crops_pumpkin_seed.jpg', sprout: '/static/game/assets/crops/crops_pumpkin_sprout.jpg', growing: '/static/game/assets/crops/crops_pumpkin_growing.jpg', mature: '/static/game/assets/crops/crops_pumpkin_mature.jpg' },
            watermelon:{ seed: '/static/game/assets/crops/crops_watermelon_seed.jpg', sprout: '/static/game/assets/crops/crops_watermelon_sprout.jpg', growing: '/static/game/assets/crops/crops_watermelon_growing.jpg', mature: '/static/game/assets/crops/crops_watermelon_mature.jpg' },
            potato:    { seed: '/static/game/assets/crops/crops_potato_seed.jpg', sprout: '/static/game/assets/crops/crops_potato_sprout.jpg', growing: '/static/game/assets/crops/crops_potato_growing.jpg', mature: '/static/game/assets/crops/crops_potato_mature.jpg' },
            carrot:    { seed: '/static/game/assets/crops/crops_carrot_seed.jpg', sprout: '/static/game/assets/crops/crops_carrot_sprout.jpg', growing: '/static/game/assets/crops/crops_carrot_growing.jpg', mature: '/static/game/assets/crops/crops_carrot_mature.jpg' },
            cabbage:   { seed: '/static/game/assets/crops/crops_cabbage_seed.jpg', sprout: '/static/game/assets/crops/crops_cabbage_sprout.jpg', growing: '/static/game/assets/crops/crops_cabbage_growing.jpg', mature: '/static/game/assets/crops/crops_cabbage_mature.jpg' }
        },
        characters: {
            player: {
                down: '/static/game/assets/characters/crops_player_down.jpg',
                up: '/static/game/assets/characters/crops_player_up.jpg',
                left: '/static/game/assets/characters/crops_player_left.jpg',
                right: '/static/game/assets/characters/crops_player_right.jpg'
            },
            chayewoon: {
                down: '/static/game/assets/characters/crops_chayewoon_down.jpg',
                up: '/static/game/assets/characters/crops_chayewoon_up.jpg',
                left: '/static/game/assets/characters/crops_chayewoon_left.jpg',
                right: '/static/game/assets/characters/crops_chayewoon_right.jpg'
            }
        },
        buildings: {
            house: '/static/game/assets/buildings/buildings_house.jpg',
            barn: '/static/game/assets/buildings/buildings_barn.jpg',
            greenhouse: '/static/game/assets/buildings/buildings_greenhouse.jpg',
            well: '/static/game/assets/buildings/buildings_well.jpg',
            shipping: '/static/game/assets/buildings/buildings_shipping.jpg'
        },
        decorations: {
            tree: '/static/game/assets/decorations/decorations_tree.jpg',
            flower_red: '/static/game/assets/decorations/decorations_flower_red.jpg',
            flower_yellow: '/static/game/assets/decorations/decorations_flower_yellow.jpg',
            rock: '/static/game/assets/decorations/decorations_rock.jpg',
            bush: '/static/game/assets/decorations/decorations_bush.jpg'
        }
    };

    // ── Initialize ─────────────────────────────────────────────
    function init(container, gridWidthPx) {
        _worldContainer = container;
        GRID_WIDTH_PX = gridWidthPx || 40;
    }

    // ── Create / Update Entity ─────────────────────────────────
    function updateEntity(id, type, gridX, gridY, options) {
        options = options || {};
        var el = _entityCache[id];

        if (!el) {
            el = document.createElement('div');
            el.className = 'game-entity entity-' + type;
            el.id = 'entity-' + id;
            el.style.position = 'absolute';
            el.style.imageRendering = 'pixelated';
            el.style.willChange = 'transform';
            el.style.contain = 'layout style paint';
            el.style.transition = 'left 0.15s ease, top 0.15s ease';
            _worldContainer.appendChild(el);
            _entityCache[id] = el;
        }

        // Position: origin at container center, y-axis inverted
        el.style.left = 'calc(50% + ' + (gridX * GRID_WIDTH_PX) + 'px)';
        el.style.top = 'calc(50% - ' + (gridY * GRID_WIDTH_PX) + 'px)';

        // Size
        var w = options.width || 1;
        var h = options.height || 1;
        el.style.width = (w * GRID_WIDTH_PX) + 'px';
        el.style.height = (h * GRID_WIDTH_PX) + 'px';

        // Z-index (y-sort: higher y = in front)
        el.style.zIndex = options.zIndex !== undefined ? options.zIndex : (gridY * 10);

        // Content
        if (options.content !== undefined) {
            el.innerHTML = options.content;
        } else if (options.src) {
            el.style.backgroundImage = 'url(' + options.src + ')';
            el.style.backgroundSize = 'cover';
            el.style.backgroundPosition = 'center';
        }

        // Classes
        if (options.className) {
            el.className = 'game-entity entity-' + type + ' ' + options.className;
        }

        // Data attributes
        if (options.data) {
            var dataKeys = Object.keys(options.data);
            for (var i = 0; i < dataKeys.length; i++) {
                el.setAttribute('data-' + dataKeys[i], options.data[dataKeys[i]]);
            }
        }

        // Click handler
        if (options.onClick) {
            el.onclick = options.onClick;
            el.style.cursor = 'pointer';
        }

        // Viewport culling
        updateVisibility(el, gridX, gridY);

        return el;
    }

    // ── Remove Entity ──────────────────────────────────────────
    function removeEntity(id) {
        var el = _entityCache[id];
        if (el) {
            el.remove();
            delete _entityCache[id];
        }
    }

    // ── Remove All Entities ────────────────────────────────────
    function clearAll() {
        var keys = Object.keys(_entityCache);
        for (var i = 0; i < keys.length; i++) {
            _entityCache[keys[i]].remove();
        }
        _entityCache = {};
    }

    // ── Render Ground Tiles ────────────────────────────────────
    function renderGround(width, height) {
        for (var y = 0; y < height; y++) {
            for (var x = 0; x < width; x++) {
                var tileType = 'grass';
                // Farm area in center
                var cx = x - Math.floor(width / 2);
                var cy = y - Math.floor(height / 2);
                if (Math.abs(cx) <= 5 && Math.abs(cy) <= 3) {
                    tileType = 'tilled';
                }
                var src = ASSETS.tiles[tileType] || ASSETS.tiles.grass;
                updateEntity('tile_' + x + '_' + y, 'tile', x, y, {
                    src: src,
                    zIndex: 0,
                    className: 'ground-tile'
                });
            }
        }
    }

    // ── Render Crops ───────────────────────────────────────────
    function renderCrops(crops) {
        var keys = Object.keys(crops);
        for (var i = 0; i < keys.length; i++) {
            var key = keys[i];
            var crop = crops[key];
            var parts = key.split(',');
            var x = parseInt(parts[0], 10);
            var y = parseInt(parts[1], 10);
            var stageName = GameState.CROP_STAGES[crop.growthStage] || 'seed';
            var cropAssets = ASSETS.crops[crop.type];
            var src = cropAssets ? cropAssets[stageName] : null;

            var className = 'crop-entity';
            if (crop.harvestable) className += ' harvestable';
            if (crop.waterLevel > 0) className += ' watered';

            updateEntity('crop_' + key, 'crop', x, y, {
                src: src,
                zIndex: y * 10 + 1,
                className: className,
                data: { type: crop.type, stage: stageName, harvestable: crop.harvestable ? '1' : '0' },
                onClick: function (cx, cy, cr) {
                    return function () {
                        if (window.GameActions) GameActions.handleTileClick(cx, cy);
                    };
                }(x, y, crop)
            });
        }
    }

    // ── Render Player ──────────────────────────────────────────
    function renderPlayer(player) {
        var charAssets = ASSETS.characters.player;
        var src = charAssets[player.direction] || charAssets.down;
        updateEntity('player', 'player', player.x, player.y, {
            src: src,
            zIndex: player.y * 10 + 5,
            className: 'player-entity'
        });
    }

    // ── Render NPC ─────────────────────────────────────────────
    function renderNPCs(npcs) {
        var keys = Object.keys(npcs);
        for (var i = 0; i < keys.length; i++) {
            var id = keys[i];
            var npc = npcs[id];
            var charAssets = ASSETS.characters[id];
            var src = charAssets ? (charAssets[npc.direction] || charAssets.down) : null;

            updateEntity('npc_' + id, 'npc', npc.x, npc.y, {
                src: src,
                zIndex: npc.y * 10 + 5,
                className: 'npc-entity',
                data: { id: id, name: npc.name || id },
                onClick: function (npcId) {
                    return function () {
                        if (window.GameDialogue) GameDialogue.openNPCDialog(npcId);
                    };
                }(id)
            });

            // NPC name label
            updateEntity('npc_label_' + id, 'npc_label', npc.x, npc.y + 1, {
                content: '<span class="npc-name">' + (npc.name || id) + '</span>',
                zIndex: npc.y * 10 + 6,
                className: 'npc-label'
            });
        }
    }

    // ── Render Buildings ───────────────────────────────────────
    function renderBuildings(buildings) {
        var keys = Object.keys(buildings);
        for (var i = 0; i < keys.length; i++) {
            var id = keys[i];
            var b = buildings[id];
            var src = ASSETS.buildings[b.type];
            if (src) {
                updateEntity('building_' + id, 'building', b.x, b.y, {
                    src: src,
                    width: 2, height: 2,
                    zIndex: (b.y + 1) * 10
                });
            }
        }
    }

    // ── Render Decorations ─────────────────────────────────────
    function renderDecorations(decorations) {
        var keys = Object.keys(decorations);
        for (var i = 0; i < keys.length; i++) {
            var id = keys[i];
            var d = decorations[id];
            var src = ASSETS.decorations[d.type];
            if (src) {
                updateEntity('deco_' + id, 'decoration', d.x, d.y, {
                    src: src,
                    zIndex: (d.y + 1) * 10
                });
            }
        }
    }

    // ── Full Render ────────────────────────────────────────────
    function renderFull(state) {
        clearAll();
        renderGround(state.farm.gridWidth || 20, state.farm.gridHeight || 14);
        renderBuildings(state.buildings || {});
        renderDecorations(state.decorations || {});
        renderCrops(state.crops || {});
        renderNPCs(state.npc || {});
        renderPlayer(state.player || { x: 0, y: 0, direction: 'down' });
    }

    // ── Viewport Culling ───────────────────────────────────────
    function updateViewport(rect) {
        _viewportRect = rect;
    }

    function updateVisibility(el, gridX, gridY) {
        if (!_viewportRect.width) return;
        var px = gridX * GRID_WIDTH_PX;
        var py = gridY * GRID_WIDTH_PX;
        var margin = GRID_WIDTH_PX * 2;
        var visible = (
            px > _viewportRect.scrollLeft - margin &&
            px < _viewportRect.scrollLeft + _viewportRect.width + margin &&
            py > _viewportRect.scrollTop - margin &&
            py < _viewportRect.scrollTop + _viewportRect.height + margin
        );
        el.style.display = visible ? '' : 'none';
    }

    function updateAllVisibility() {
        var keys = Object.keys(_entityCache);
        for (var i = 0; i < keys.length; i++) {
            var el = _entityCache[keys[i]];
            // Parse position from style
            var left = el.style.left || '';
            var top = el.style.top || '';
            // Simple visibility check using bounding rect
            var rect = el.getBoundingClientRect();
            var viewRect = _viewportRect;
            if (viewRect.width) {
                var visible = (
                    rect.right > 0 && rect.left < (viewRect.width || window.innerWidth) &&
                    rect.bottom > 0 && rect.top < (viewRect.height || window.innerHeight)
                );
                el.style.display = visible ? '' : 'none';
            }
        }
    }

    // ── Export ─────────────────────────────────────────────────
    window.GameRenderer = {
        ASSETS: ASSETS,
        GRID_WIDTH_PX: GRID_WIDTH_PX,
        init: init,
        updateEntity: updateEntity,
        removeEntity: removeEntity,
        clearAll: clearAll,
        renderGround: renderGround,
        renderCrops: renderCrops,
        renderPlayer: renderPlayer,
        renderNPCs: renderNPCs,
        renderBuildings: renderBuildings,
        renderDecorations: renderDecorations,
        renderFull: renderFull,
        updateViewport: updateViewport,
        updateAllVisibility: updateAllVisibility
    };
})();
