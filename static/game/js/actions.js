/**
 * NxSiran Game - Actions Handler
 * Selected-item-then-click interaction pattern (Sunflower Land style)
 */
(function () {
    'use strict';
    
    // ── Visual Feedback Effects ─────────────────────────────────
    function showPlantEffect(x, y) {
        showParticleEffect(x, y, '#4ade80', 5, 'seed');
        showFloatingText(x, y, '🌱', '#4ade80');
    }
    
    function showWaterEffect(x, y) {
        showParticleEffect(x, y, '#60a5fa', 8, 'water');
        showFloatingText(x, y, '💧', '#60a5fa');
    }
    
    function showHarvestEffect(x, y, cropType) {
        showParticleEffect(x, y, '#fbbf24', 12, 'harvest');
        var emoji = getEmojiForCrop(cropType);
        showFloatingText(x, y, emoji, '#fbbf24');
    }
    
    function showParticleEffect(x, y, color, count, type) {
        var world = document.getElementById('game-world');
        if (!world) return;
        
        var centerX = world.offsetWidth / 2 + x * 40;
        var centerY = world.offsetHeight / 2 - y * 40;
        
        for (var i = 0; i < count; i++) {
            var particle = document.createElement('div');
            particle.className = 'particle particle-' + type;
            particle.style.cssText = 'position:absolute;left:' + centerX + 'px;top:' + centerY + 'px;background:' + color + ';';
            world.appendChild(particle);
            
            // Animate and remove
            var angle = (i / count) * Math.PI * 2;
            var distance = 30 + Math.random() * 20;
            var targetX = centerX + Math.cos(angle) * distance;
            var targetY = centerY + Math.sin(angle) * distance - 20;
            
            setTimeout(function(p, tx, ty) {
                p.style.transition = 'all 0.5s ease-out';
                p.style.left = tx + 'px';
                p.style.top = ty + 'px';
                p.style.opacity = '0';
                setTimeout(function() { p.remove(); }, 500);
            }, 10, particle, targetX, targetY);
        }
    }
    
    function showFloatingText(x, y, text, color) {
        var world = document.getElementById('game-world');
        if (!world) return;
        
        var centerX = world.offsetWidth / 2 + x * 40;
        var centerY = world.offsetHeight / 2 - y * 40;
        
        var floater = document.createElement('div');
        floater.className = 'floating-text';
        floater.style.cssText = 'position:absolute;left:' + centerX + 'px;top:' + centerY + 'px;color:' + color + ';';
        floater.textContent = text;
        world.appendChild(floater);
        
        setTimeout(function() {
            floater.style.transition = 'all 0.8s ease-out';
            floater.style.top = (centerY - 40) + 'px';
            floater.style.opacity = '0';
            setTimeout(function() { floater.remove(); }, 800);
        }, 10);
    }
    
    function getEmojiForCrop(cropType) {
        var emojis = {
            tomato: '🍅', corn: '🌽', strawberry: '🍓', pumpkin: '🎃',
            watermelon: '🍉', potato: '🥔', carrot: '🥕', cabbage: '🥬'
        };
        return emojis[cropType] || '🌾';
    }

    // ── Handle Tile Click ─────────────────────────────────────
    function handleTileClick(gridX, gridY) {
        var state = GameState.getState();
        var tool = state.selectedTool;

        if (!tool) {
            // No tool selected - check if there's a harvestable crop
            var crop = GameState.getCropAt(gridX, gridY);
            if (crop && crop.harvestable) {
                doHarvest(gridX, gridY, crop);
            }
            return;
        }

        switch (tool.type) {
            case 'seed':
                doPlant(gridX, gridY, tool.item);
                break;
            case 'tool':
                if (tool.item === 'watering_can') {
                    doWater(gridX, gridY);
                } else if (tool.item === 'hoe') {
                    doTill(gridX, gridY);
                }
                break;
            case 'harvest':
                doHarvest(gridX, gridY);
                break;
        }
    }

    // ── Plant ──────────────────────────────────────────────────
    function doPlant(x, y, cropType) {
        var state = GameState.getState();

        // Check if tile is occupied
        if (GameState.getCropAt(x, y)) {
            if (window.GameHUD) GameHUD.showToast('\u8FD9\u4E2A\u4F4D\u7F6E\u5DF2\u7ECF\u6709\u4F5C\u7269\u4E86', 'warning');
            return;
        }

        // Check if in farm area (center of the grid)
        var halfW = Math.floor((GameState.getState().farm.gridWidth || 12) / 2);
        var halfH = Math.floor((GameState.getState().farm.gridHeight || 8) / 2);
        var cx = x - halfW;
        var cy = y - halfH;
        if (Math.abs(cx) > 5 || Math.abs(cy) > 3) {
            if (window.GameHUD) GameHUD.showToast('\u53EA\u80FD\u5728\u519C\u7530\u533A\u57DF\u79CD\u690D', 'warning');
            return;
        }

        // Check inventory for seeds
        var seedKey = 'seed_' + cropType;
        if (!state.inventory[seedKey] || state.inventory[seedKey].quantity <= 0) {
            if (window.GameHUD) GameHUD.showToast('\u6CA1\u6709\u8DB3\u591F\u7684\u79CD\u5B50', 'warning');
            return;
        }

        GameState.dispatch({ type: 'PLANT', x: x, y: y, cropType: cropType });
        
        // Visual feedback
        showPlantEffect(x, y);

        // API call (fire and forget)
        if (window.GameAPI) {
            GameAPI.plant(x, y, cropType).catch(function () {});
        }

        // Re-render the crop
        if (window.GameRenderer) {
            var newCrop = GameState.getCropAt(x, y);
            if (newCrop) {
                var stageName = GameState.CROP_STAGES[newCrop.growthStage] || 'seed';
                var cropAssets = GameRenderer.ASSETS.crops[cropType];
                var src = cropAssets ? cropAssets[stageName] : null;
                GameRenderer.updateEntity('crop_' + x + ',' + y, 'crop', x, y, {
                    src: src,
                    zIndex: y * 10 + 1,
                    className: 'crop-entity',
                    data: { type: cropType, stage: stageName, harvestable: '0' },
                    onClick: (function (cx, cy) {
                        return function () { handleTileClick(cx, cy); };
                    })(x, y)
                });
            }
        }

        if (window.GameHUD) GameHUD.showToast('\u79CD\u4E0B\u4E86 ' + GameState.getCropName(cropType), 'success');
        if (window.GameInventory) GameInventory.updateUI();
    }

    // ── Harvest ────────────────────────────────────────────────
    function doHarvest(x, y, crop) {
        if (!crop) crop = GameState.getCropAt(x, y);
        if (!crop || !crop.harvestable) {
            if (window.GameHUD) GameHUD.showToast('\u8FD9\u91CC\u6CA1\u6709\u53EF\u6536\u83B7\u7684\u4F5C\u7269', 'warning');
            return;
        }

        var cropName = GameState.getCropName(crop.type);
        var cropEmoji = GameState.getCropEmoji(crop.type);

        GameState.dispatch({ type: 'HARVEST', x: x, y: y });
        
        // Visual feedback
        showHarvestEffect(x, y, crop.type);

        // Remove entity
        if (window.GameRenderer) {
            GameRenderer.removeEntity('crop_' + x + ',' + y);
        }

        // API call
        if (window.GameAPI) {
            GameAPI.harvest(x, y).catch(function () {});
        }

        if (window.GameHUD) GameHUD.showToast(cropEmoji + ' \u6536\u83B7\u4E86 ' + cropName, 'success');
        if (window.GameInventory) GameInventory.updateUI();
    }

    // ── Water ──────────────────────────────────────────────────
    function doWater(x, y) {
        var crop = GameState.getCropAt(x, y);
        if (!crop) {
            if (window.GameHUD) GameHUD.showToast('\u8FD9\u91CC\u6CA1\u6709\u4F5C\u7269', 'warning');
            return;
        }
        if (crop.harvestable) {
            if (window.GameHUD) GameHUD.showToast('\u5DF2\u7ECF\u6210\u719F\u4E86\uFF0C\u53EF\u4EE5\u6536\u83B7', 'info');
            return;
        }

        GameState.dispatch({ type: 'WATER', x: x, y: y });
        
        // Visual feedback
        showWaterEffect(x, y);

        if (window.GameAPI) {
            GameAPI.water(x, y).catch(function () {});
        }

        // Update visual
        if (window.GameRenderer) {
            var el = document.getElementById('entity-crop_' + x + ',' + y);
            if (el) el.classList.add('watered');
        }

        if (window.GameHUD) GameHUD.showToast('\u6D47\u6C34\u5B8C\u6210 \uD83D\uDCA7', 'success');
    }

    // ── Till (placeholder) ─────────────────────────────────────
    function doTill(x, y) {
        if (window.GameHUD) GameHUD.showToast('\u8015\u5730\u529F\u80FD\u5F00\u53D1\u4E2D...', 'info');
    }

    // ── Select Tool ────────────────────────────────────────────
    function selectTool(type, item) {
        GameState.dispatch({ type: 'SELECT_TOOL', payload: { type: type, item: item } });
        if (window.GameHUD) GameHUD.updateToolbar();
    }

    function deselectTool() {
        GameState.dispatch({ type: 'DESELECT_TOOL' });
        if (window.GameHUD) GameHUD.updateToolbar();
    }

    // ── Move Player ───────────────────────────────────────────
    function movePlayer(direction) {
        var state = GameState.getState();
        var dx = 0, dy = 0;
        switch (direction) {
            case 'up': dy = 1; break;
            case 'down': dy = -1; break;
            case 'left': dx = -1; break;
            case 'right': dx = 1; break;
        }
        var nx = state.player.x + dx;
        var ny = state.player.y + dy;

        // Boundary check
        if (Math.abs(nx) > 15 || Math.abs(ny) > 15) return;

        // Terrain-based movement check
        var heightMap = window.GameRenderer ? GameRenderer.getHeightMap ? GameRenderer.getHeightMap() : null : null;
        if (!heightMap && window.GameTerrain) {
            // Try to get height map from terrain module if available in state
            heightMap = state.heightMap;
        }
        
        if (heightMap && window.GameTerrain) {
            // Check if target tile is walkable
            if (!GameTerrain.isWalkable(heightMap, nx, ny)) {
                var terrain = GameTerrain.getTerrainAt(heightMap, nx, ny);
                var terrainName = terrain ? getTerrainName(terrain.type) : '未知地形';
                if (window.GameHUD) GameHUD.showToast('无法移动到' + terrainName + ' 🚫', 'warning');
                return;
            }
            
            // Get movement cost and apply delay based on terrain
            var moveCost = GameTerrain.getMovementCost(heightMap, nx, ny);
            if (moveCost > 1.5) {
                // Show terrain info on slower movement
                var terrain = GameTerrain.getTerrainAt(heightMap, nx, ny);
                if (terrain && moveCost >= 3) {
                    if (window.GameHUD) GameHUD.showToast('正在攀爬' + getTerrainName(terrain.type) + '... 🏔️', 'info');
                }
            }
        }

        // Collision check
        var occupied = window.GameViewport ? GameViewport.buildOccupiedGrid(state) : {};
        // Don't block on crops (can walk through)
        var bKeys = Object.keys(state.buildings || {});
        for (var i = 0; i < bKeys.length; i++) {
            var b = state.buildings[bKeys[i]];
            var bw = b.width || 2, bh = b.height || 2;
            for (var bx = 0; bx < bw; bx++) {
                for (var by = 0; by < bh; by++) {
                    occupied[(b.x + bx) + ',' + (b.y + by)] = 'building';
                }
            }
        }
        if (occupied[nx + ',' + ny] === 'building') return;

        GameState.dispatch({ type: 'MOVE_PLAYER', x: nx, y: ny, direction: direction });

        if (window.GameRenderer) {
            GameRenderer.renderPlayer(GameState.getState().player);
        }

        // Check proximity to NPC
        if (window.GameNPC) GameNPC.checkProximity(nx, ny);
        
        // Check for terrain-based discoveries
        checkTerrainDiscovery(nx, ny);
    }
    
    // Get terrain name in Chinese
    function getTerrainName(type) {
        var names = {
            'flat': '平地',
            'hill': '丘陵',
            'mountain': '山地',
            'water': '水域',
            'cliff': '悬崖',
            'slope': '斜坡'
        };
        return names[type] || type;
    }
    
    // Check for terrain-based discoveries
    function checkTerrainDiscovery(x, y) {
        var heightMap = window.GameRenderer && GameRenderer.getHeightMap ? GameRenderer.getHeightMap() : null;
        if (!heightMap || !window.GameTerrain) return;
        
        var terrain = GameTerrain.getTerrainAt(heightMap, x, y);
        if (!terrain) return;
        
        // Discovery: High altitude locations
        if (terrain.height >= 80 && !window._discoveredPeak) {
            window._discoveredPeak = true;
            if (window.GameHUD) {
                GameHUD.showToast('🏔️ 发现: 山顶! 从这里可以俯瞰整个农场', 'success');
            }
        }
        
        // Discovery: Water source
        if (terrain.type === 'water' && !window._discoveredWater) {
            window._discoveredWater = true;
            if (window.GameHUD) {
                GameHUD.showToast('💧 发现: 水源! 可以用来灌溉作物', 'info');
            }
        }
    }

    // ── Export ─────────────────────────────────────────────────
    window.GameActions = {
        handleTileClick: handleTileClick,
        selectTool: selectTool,
        deselectTool: deselectTool,
        movePlayer: movePlayer,
        doPlant: doPlant,
        doHarvest: doHarvest,
        doWater: doWater
    };
})();
