/**
 * NxSiran Game - DOM Renderer V3
 * 3D Isometric RPG style renderer
 */
(function () {
    'use strict';

    var GRID_WIDTH_PX = 48;
    var GRID_HEIGHT_PX = 48;
    var _worldContainer = null;
    var _entityCache = {};
    var _viewportRect = { left: 0, top: 0, width: 0, height: 0 };
    var _animationFrame = 0;
    var _animationInterval = null;

    // ── Asset paths (V3 - 3D Isometric RPG style) ─────────────
    var ASSETS = {
        tiles: {
            grass: '/static/game/assets/v3/grass_tile.jpg',
            soil: '/static/game/assets/v3/soil_tile.jpg'
        },
        crops: {
            tomato: '/static/game/assets/v3/tomato_growth.jpg',
            corn: '/static/game/assets/v3/corn_growth.jpg',
            strawberry: '/static/game/assets/v3/strawberry_growth.jpg',
            pumpkin: '/static/game/assets/v3/pumpkin_growth.jpg',
            watermelon: '/static/game/assets/v3/watermelon_growth.jpg',
            potato: '/static/game/assets/v3/potato_growth.jpg',
            carrot: '/static/game/assets/v3/carrot_growth.jpg',
            cabbage: '/static/game/assets/v3/cabbage_growth.jpg'
        },
        characters: {
            player: '/static/game/assets/v3/player_char.jpg',
            chayewoon: '/static/game/assets/v3/npc_chayewoon.jpg'
        },
        buildings: {
            house: '/static/game/assets/v3/farmhouse.jpg',
            barn: '/static/game/assets/v3/barn.jpg',
            well: '/static/game/assets/v3/stone_well.jpg',
            shipping: '/static/game/assets/v3/shipping_bin.jpg'
        },
        decorations: {
            tree: '/static/game/assets/v3/oak_tree.jpg',
            fence: '/static/game/assets/v3/wood_fence.jpg',
            flowers: '/static/game/assets/v3/flower_decoration.jpg'
        }
    };

    // Sprite animation configuration
    var SPRITE_CONFIG = {
        player: { frames: 4, directions: ['down', 'left', 'right', 'up'], frameWidth: 64, frameHeight: 64 },
        chayewoon: { frames: 4, directions: ['down', 'left', 'right', 'up'], frameWidth: 64, frameHeight: 64 }
    };
    
    // Track which characters are moving
    var _movingCharacters = {};

    // ── Initialize ─────────────────────────────────────────────
    function init(container, gridWidthPx) {
        _worldContainer = container;
        GRID_WIDTH_PX = gridWidthPx || 40;
        startAnimationLoop();
    }

    // ── Animation Loop ─────────────────────────────────────────
    function startAnimationLoop() {
        if (_animationInterval) return;
        _animationInterval = setInterval(function() {
            _animationFrame = (_animationFrame + 1) % 4;
            updateSpriteAnimations();
        }, 200); // 5 frames per second for smoother animation
    }

    function updateSpriteAnimations() {
        // Update all character sprites to show next frame
        var characters = document.querySelectorAll('.entity-character');
        characters.forEach(function(el) {
            var charId = el.id.replace('entity-', '');
            var direction = el.dataset.direction || 'down';
            var isMoving = _movingCharacters[charId];
            
            if (isMoving) {
                // Play walking animation
                updateSpriteFrame(el, direction, _animationFrame);
                el.classList.add('walking');
            } else {
                // Show idle frame (first frame)
                updateSpriteFrame(el, direction, 0);
                el.classList.remove('walking');
            }
        });
    }
    
    function setCharacterMoving(charId, moving) {
        _movingCharacters[charId] = moving;
        // Clear moving state after 300ms of no movement
        if (moving) {
            setTimeout(function() {
                if (_movingCharacters[charId] === 'timeout_' + Date.now()) return;
                _movingCharacters[charId] = false;
            }, 300);
        }
    }

    function updateSpriteFrame(el, direction, frame) {
        var config = SPRITE_CONFIG[el.dataset.characterType];
        if (!config) return;

        var dirIndex = config.directions.indexOf(direction);
        if (dirIndex === -1) dirIndex = 0;

        // Calculate background position for sprite sheet
        var x = -(frame * config.frameWidth);
        var y = -(dirIndex * config.frameHeight);

        el.style.backgroundPosition = x + 'px ' + y + 'px';
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
            _worldContainer.appendChild(el);
            _entityCache[id] = el;
        }

        // Position using CSS calc() for center-based coordinates
        // Apply height offset for 3D elevation
        var heightOffset = options.height || 0;
        var left = 'calc(50% + ' + (gridX * GRID_WIDTH_PX) + 'px)';
        var top = 'calc(50% + ' + (gridY * GRID_HEIGHT_PX - heightOffset) + 'px)';

        el.style.left = left;
        el.style.top = top;
        el.style.width = (options.width || GRID_WIDTH_PX) + 'px';
        el.style.height = (options.height || GRID_WIDTH_PX) + 'px';
        
        // Store height for depth sorting
        el.dataset.height = heightOffset;
        el.style.zIndex = options.zIndex || 1;

        // Apply custom class
        if (options.className) {
            el.className = 'game-entity entity-' + type + ' ' + options.className;
        }

        // Set background image
        if (options.src || options.sprite) {
            var src = options.sprite || options.src;
            if (el.dataset.currentSrc !== src) {
                el.style.backgroundImage = 'url(' + src + ')';
                el.style.backgroundSize = options.bgSize || 'cover';
                el.style.backgroundRepeat = 'no-repeat';
                el.dataset.currentSrc = src;

                // Setup sprite animation for characters
                if (type === 'character' && options.characterType) {
                    el.dataset.characterType = options.characterType;
                    el.dataset.direction = options.direction || 'down';
                    var config = SPRITE_CONFIG[options.characterType];
                    if (config) {
                        el.style.width = config.frameWidth + 'px';
                        el.style.height = config.frameHeight + 'px';
                        updateSpriteFrame(el, el.dataset.direction, 0);
                    }
                }
            }

            // Update direction if changed
            if (type === 'character' && options.direction && el.dataset.direction !== options.direction) {
                el.dataset.direction = options.direction;
                updateSpriteFrame(el, options.direction, _animationFrame);
            }
        }

        // Visibility
        if (options.visible === false) {
            el.style.display = 'none';
        } else {
            el.style.display = 'block';
        }

        return el;
    }

    // ── Render Ground Tiles with Height Map ───────────────────
    var _heightMap = null;
    
    function setHeightMap(heightMap) {
        _heightMap = heightMap;
    }
    
    function renderGround(width, height) {
        // Sort tiles by height for proper depth rendering (painter's algorithm)
        var tilesToRender = [];
        
        for (var y = 0; y < height; y++) {
            for (var x = 0; x < width; x++) {
                var terrain = _heightMap ? GameTerrain.getTerrainAt(_heightMap, x, y) : null;
                var tileType = 'grass';
                var tileHeight = 0;
                var zOffset = 0;
                
                if (terrain) {
                    // Use terrain type from height map
                    switch (terrain.type) {
                        case GameTerrain.TERRAIN_TYPES.WATER:
                            tileType = 'water';
                            tileHeight = terrain.height;
                            break;
                        case GameTerrain.TERRAIN_TYPES.FLAT:
                        case GameTerrain.TERRAIN_TYPES.HILL:
                            tileType = 'grass';
                            tileHeight = terrain.height;
                            break;
                        case GameTerrain.TERRAIN_TYPES.MOUNTAIN:
                            tileType = 'mountain';
                            tileHeight = terrain.height;
                            break;
                        case GameTerrain.TERRAIN_TYPES.SLOPE:
                        case GameTerrain.TERRAIN_TYPES.CLIFF:
                            tileType = 'slope';
                            tileHeight = terrain.height;
                            break;
                    }
                    zOffset = terrain.height;
                } else {
                    // Fallback: farm area in center
                    var cx = x - Math.floor(width / 2);
                    var cy = y - Math.floor(height / 2);
                    if (Math.abs(cx) <= 5 && Math.abs(cy) <= 3) {
                        tileType = 'soil';
                    }
                }
                
                tilesToRender.push({
                    x: x,
                    y: y,
                    type: tileType,
                    height: tileHeight,
                    zOffset: zOffset
                });
            }
        }
        
        // Sort by Y then X for proper depth (back-to-front rendering)
        tilesToRender.sort(function(a, b) {
            if (a.y !== b.y) return a.y - b.y;
            return a.x - b.x;
        });
        
        // Render tiles
        tilesToRender.forEach(function(tile) {
            var src = ASSETS.tiles[tile.type] || ASSETS.tiles.grass;
            var el = updateEntity('tile_' + tile.x + '_' + tile.y, 'tile', tile.x, tile.y, {
                src: src,
                zIndex: tile.y * 100 + tile.x, // Depth sorting
                className: 'ground-tile tile-' + tile.type + ' height-' + tile.height,
                height: tile.height
            });
            
            // Apply 3D elevation effect
            if (el) {
                applyElevationEffect(el, tile.height, tile.type);
            }
        });
    }
    
    function applyElevationEffect(el, height, type) {
        // Store height for CSS custom property
        el.style.setProperty('--ty', -height + 'px');
        
        // Apply CSS transform for 3D elevation with enhanced perspective
        var translateY = -height * 1.3; // Amplify height difference
        var translateZ = Math.abs(height);
        var scale = 1 + (height / 400); // Slight scale increase for higher tiles
        
        // Different styling based on terrain type
        switch(type) {
            case 'water':
                el.style.transform = 'translateY(30px) scale(0.92) translateZ(-10px)';
                el.style.filter = 'hue-rotate(180deg) saturate(1.8) brightness(0.85)';
                break;
            case 'mountain':
                el.style.transform = 'translateY(' + translateY + 'px) translateZ(' + translateZ + 'px) scale(' + scale + ')';
                el.style.filter = 'sepia(0.2) contrast(1.15) brightness(' + (1 + height/150) + ')';
                break;
            case 'cliff':
                el.style.transform = 'translateY(' + translateY + 'px) translateZ(' + translateZ + 'px)';
                el.style.filter = 'contrast(1.2) brightness(' + (1 + height/200) + ')';
                // Add cliff edge effect
                el.style.borderTop = '3px solid rgba(255,255,255,0.4)';
                break;
            case 'slope':
                el.style.transform = 'translateY(' + (translateY * 0.7) + 'px) translateZ(' + (translateZ * 0.5) + 'px)';
                el.style.filter = 'brightness(' + (1 + height/300) + ')';
                break;
            default:
                el.style.transform = 'translateY(' + translateY + 'px) translateZ(' + translateZ + 'px) scale(' + scale + ')';
                // Adjust brightness based on height (higher = lighter, like sunlight)
                var brightness = 1 + (height / 200);
                el.style.filter = 'brightness(' + brightness + ')';
        }
        
        // Add height-based shadow
        if (height > 10) {
            var shadowBlur = height * 0.8;
            var shadowOffset = height * 0.4;
            el.style.boxShadow = '0 ' + shadowOffset + 'px ' + shadowBlur + 'px rgba(0,0,0,' + (0.2 + height/300) + ')';
        }
        
        // Store height data for depth sorting
        el.dataset.elevation = height;
    }
    
    // ── Add Ground Details ──────────────────────────────────────
    function addGroundDetail(x, y, type) {
        var detailId = 'detail_' + x + '_' + y + '_' + type;
        var offsetX = ((x * 7) % 20) - 10;
        var offsetY = ((y * 11) % 20) - 10;
        
        var el = _entityCache[detailId];
        if (!el) {
            el = document.createElement('div');
            el.className = 'ground-detail detail-' + type;
            el.id = 'entity-' + detailId;
            el.style.position = 'absolute';
            el.style.pointerEvents = 'none';
            _worldContainer.appendChild(el);
            _entityCache[detailId] = el;
        }
        
        el.style.left = 'calc(50% + ' + (x * GRID_WIDTH_PX + offsetX) + 'px)';
        el.style.top = 'calc(50% + ' + (y * GRID_HEIGHT_PX + offsetY) + 'px)';
        el.style.zIndex = 1;
    }

    // ── Render Crops ───────────────────────────────────────────
    function renderCrops(crops) {
        for (var key in crops) {
            if (!crops.hasOwnProperty(key)) continue;
            var crop = crops[key];
            var stage = crop.stage || 0;
            var maxStage = 3; // 0-3 for seed, sprout, growing, mature
            var stageName = ['seed', 'sprout', 'growing', 'mature'][Math.min(stage, maxStage)];

            // Use growth sprite sheet - show appropriate stage section
            var spriteSrc = ASSETS.crops[crop.type];
            if (spriteSrc) {
                updateEntity('crop_' + key, 'crop', crop.x, crop.y, {
                    sprite: spriteSrc,
                    bgSize: '400% 100%', // 4 stages horizontally
                    zIndex: 2,
                    className: 'crop-stage-' + stage
                });

                // Set background position based on stage
                var el = _entityCache['crop_' + key];
                if (el) {
                    var bgX = -(stage * 25) + '%';
                    el.style.backgroundPosition = bgX + ' 0';
                }
            }
        }
    }

    // ── Render Player ──────────────────────────────────────────
    var _lastPlayerPos = { x: 0, y: 0 };
    function renderPlayer(player) {
        // Check if player moved
        if (_lastPlayerPos.x !== player.x || _lastPlayerPos.y !== player.y) {
            setCharacterMoving('player', true);
            _lastPlayerPos = { x: player.x, y: player.y };
        }
        
        updateEntity('player', 'character', player.x, player.y, {
            sprite: ASSETS.characters.player,
            characterType: 'player',
            direction: player.direction || 'down',
            zIndex: 10,
            className: 'player'
        });
    }

    // ── Render NPCs ────────────────────────────────────────────
    function renderNPCs(npc) {
        for (var key in npc) {
            if (!npc.hasOwnProperty(key)) continue;
            var n = npc[key];
            updateEntity('npc_' + key, 'character', n.x, n.y, {
                sprite: ASSETS.characters[key] || ASSETS.characters.chayewoon,
                characterType: key,
                direction: n.direction || 'down',
                zIndex: 10,
                className: 'npc'
            });
        }
    }

    // ── Render Buildings ───────────────────────────────────────
    function renderBuildings(buildings) {
        for (var key in buildings) {
            if (!buildings.hasOwnProperty(key)) continue;
            var b = buildings[key];
            var src = ASSETS.buildings[b.type];
            if (src) {
                updateEntity('building_' + key, 'building', b.x, b.y, {
                    src: src,
                    zIndex: 5,
                    width: 80,
                    height: 80,
                    className: 'building-' + b.type
                });
            }
        }
    }

    // ── Render Decorations ────────────────────────────────────
    function renderDecorations(decorations) {
        for (var key in decorations) {
            if (!decorations.hasOwnProperty(key)) continue;
            var d = decorations[key];
            var src = ASSETS.decorations[d.type];
            if (src) {
                updateEntity('deco_' + key, 'decoration', d.x, d.y, {
                    src: src,
                    zIndex: 3,
                    className: 'decoration-' + d.type
                });
            }
        }
    }

    // ── Full Render ────────────────────────────────────────────
    function renderFull(state) {
        clearAll();
        var farm = state.farm || {};
        renderGround(farm.gridWidth || 12, farm.gridHeight || 8);
        renderDecorations(state.decorations || {});
        renderBuildings(state.buildings || {});
        renderCrops(state.crops || {});
        renderNPCs(state.npc || {});
        if (state.player) renderPlayer(state.player);
    }

    // ── Clear All Entities ─────────────────────────────────────
    function clearAll() {
        for (var id in _entityCache) {
            if (_entityCache.hasOwnProperty(id)) {
                var el = _entityCache[id];
                if (el && el.parentNode) {
                    el.parentNode.removeChild(el);
                }
            }
        }
        _entityCache = {};
    }

    // ── Set Viewport Rect for Culling ──────────────────────────
    function setViewportRect(rect) {
        _viewportRect = rect;
    }

    // ── Update Viewport (for viewport.js compatibility) ────────
    function updateViewport(rect) {
        setViewportRect(rect);
    }

    // ── Update All Visibility (for viewport.js compatibility) ──
    function updateAllVisibility() {
        // Update visibility of all entities based on viewport
        // For now, just ensure all entities are visible
        for (var id in _entityCache) {
            if (_entityCache.hasOwnProperty(id)) {
                var el = _entityCache[id];
                if (el) {
                    el.style.display = 'block';
                }
            }
        }
    }

    // ── Get Height Map ─────────────────────────────────────────
    function getHeightMap() {
        return _heightMap;
    }

    // ── Export ─────────────────────────────────────────────────
    window.GameRenderer = {
        init: init,
        renderFull: renderFull,
        renderCrops: renderCrops,
        renderPlayer: renderPlayer,
        updateEntity: updateEntity,
        clearAll: clearAll,
        setViewportRect: setViewportRect,
        updateViewport: updateViewport,
        updateAllVisibility: updateAllVisibility,
        setCharacterMoving: setCharacterMoving,
        setHeightMap: setHeightMap,
        getHeightMap: getHeightMap,
        ASSETS: ASSETS
    };
})();
