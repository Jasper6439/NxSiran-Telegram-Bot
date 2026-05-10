/**
 * NxSiran Game - 3D Terrain System
 * Height map, terrain types, and elevation-based gameplay
 */
(function () {
    'use strict';

    // Terrain types
    var TERRAIN_TYPES = {
        FLAT: 'flat',      // 平地
        HILL: 'hill',      // 丘陵
        MOUNTAIN: 'mountain', // 山地
        WATER: 'water',    // 水域
        CLIFF: 'cliff',    // 悬崖
        SLOPE: 'slope'     // 斜坡
    };

    // Height levels (in pixels for visual representation) - Enhanced range
    var HEIGHT_LEVELS = {
        WATER: -30,
        LOW: 0,
        MEDIUM: 25,
        HIGH: 50,
        MOUNTAIN: 80,
        PEAK: 110
    };

    // Generate a height map using enhanced multi-octave noise
    function generateHeightMap(width, height, seed) {
        var map = [];
        seed = seed || Math.random() * 10000;
        
        // Create multiple noise layers for more interesting terrain
        for (var y = 0; y < height; y++) {
            map[y] = [];
            for (var x = 0; x < width; x++) {
                // Normalize coordinates
                var nx = x / width - 0.5;
                var ny = y / height - 0.5;
                var distFromCenter = Math.sqrt(nx * nx + ny * ny);
                
                // Combine multiple sine waves with different frequencies for natural-looking terrain
                var elevation = 0;
                // Large features (mountains and valleys)
                elevation += Math.sin(nx * 4 + seed) * Math.cos(ny * 4 + seed * 1.3) * 0.4;
                // Medium features (hills)
                elevation += Math.sin(nx * 8 + seed * 2) * Math.cos(ny * 8 + seed * 2.5) * 0.3;
                // Small features (roughness)
                elevation += Math.sin(nx * 16 + seed * 3) * Math.cos(ny * 16 + seed * 3.7) * 0.15;
                // Fine details
                elevation += Math.sin(nx * 32 + seed * 4) * Math.cos(ny * 32 + seed * 4.2) * 0.075;
                
                // Add radial bias - create a valley or mountain range
                elevation += Math.cos(distFromCenter * 6) * 0.15;
                
                // Normalize to 0-1 range
                elevation = (elevation + 1) / 2;
                
                // Apply power curve to create more dramatic peaks and valleys
                elevation = Math.pow(elevation, 1.2);
                
                // Determine terrain type based on elevation
                var terrainType = TERRAIN_TYPES.FLAT;
                var heightLevel = HEIGHT_LEVELS.LOW;
                
                if (elevation < 0.22) {
                    terrainType = TERRAIN_TYPES.WATER;
                    heightLevel = HEIGHT_LEVELS.WATER;
                } else if (elevation < 0.35) {
                    terrainType = TERRAIN_TYPES.FLAT;
                    heightLevel = HEIGHT_LEVELS.LOW;
                } else if (elevation < 0.5) {
                    terrainType = TERRAIN_TYPES.HILL;
                    heightLevel = HEIGHT_LEVELS.MEDIUM;
                } else if (elevation < 0.7) {
                    terrainType = TERRAIN_TYPES.MOUNTAIN;
                    heightLevel = HEIGHT_LEVELS.HIGH;
                } else if (elevation < 0.85) {
                    terrainType = TERRAIN_TYPES.MOUNTAIN;
                    heightLevel = HEIGHT_LEVELS.MOUNTAIN;
                } else {
                    terrainType = TERRAIN_TYPES.MOUNTAIN;
                    heightLevel = HEIGHT_LEVELS.PEAK;
                }
                
                // Store initial cell data
                map[y][x] = {
                    x: x,
                    y: y,
                    elevation: elevation,
                    height: heightLevel,
                    type: terrainType,
                    slope: false,
                    slopeDirection: null
                };
            }
        }
        
        // Second pass: mark slopes and cliffs based on height differences
        for (var y = 0; y < height; y++) {
            for (var x = 0; x < width; x++) {
                var cell = map[y][x];
                var neighbors = getNeighbors(map, x, y);
                
                var maxHeightDiff = 0;
                var slopeDir = null;
                
                for (var dir in neighbors) {
                    var neighbor = neighbors[dir];
                    if (neighbor) {
                        var diff = Math.abs(cell.height - neighbor.height);
                        if (diff > maxHeightDiff) {
                            maxHeightDiff = diff;
                            slopeDir = dir;
                        }
                    }
                }
                
                // Mark steep transitions as slopes or cliffs
                if (maxHeightDiff >= 25) {
                    cell.slope = true;
                    cell.slopeDirection = slopeDir;
                    if (maxHeightDiff >= 50) {
                        cell.type = TERRAIN_TYPES.CLIFF;
                    } else {
                        cell.type = TERRAIN_TYPES.SLOPE;
                    }
                }
            }
        }
        
        return map;
    }

    function getNeighbors(map, x, y) {
        return {
            north: y > 0 ? map[y - 1][x] : null,
            south: y < map.length - 1 ? map[y + 1][x] : null,
            east: x < map[0].length - 1 ? map[y][x + 1] : null,
            west: x > 0 ? map[y][x - 1] : null
        };
    }

    // Get terrain info at position
    function getTerrainAt(heightMap, x, y) {
        if (y < 0 || y >= heightMap.length || x < 0 || x >= heightMap[0].length) {
            return null;
        }
        return heightMap[y][x];
    }

    // Check if position is walkable
    function isWalkable(heightMap, x, y) {
        var terrain = getTerrainAt(heightMap, x, y);
        if (!terrain) return false;
        return terrain.type !== TERRAIN_TYPES.WATER && terrain.type !== TERRAIN_TYPES.CLIFF;
    }

    // Get movement cost (affected by terrain)
    function getMovementCost(heightMap, x, y) {
        var terrain = getTerrainAt(heightMap, x, y);
        if (!terrain) return Infinity;
        
        switch (terrain.type) {
            case TERRAIN_TYPES.FLAT: return 1;
            case TERRAIN_TYPES.HILL: return 1.5;
            case TERRAIN_TYPES.SLOPE: return 2;
            case TERRAIN_TYPES.MOUNTAIN: return 3;
            case TERRAIN_TYPES.WATER: return Infinity;
            case TERRAIN_TYPES.CLIFF: return Infinity;
            default: return 1;
        }
    }

    // Get visual height offset for rendering
    function getVisualHeight(heightMap, x, y) {
        var terrain = getTerrainAt(heightMap, x, y);
        if (!terrain) return 0;
        return terrain.height;
    }

    // Check if water flows from higher to lower
    function getWaterFlowDirection(heightMap, x, y) {
        var terrain = getTerrainAt(heightMap, x, y);
        if (!terrain || terrain.type !== TERRAIN_TYPES.WATER) return null;
        
        var neighbors = getNeighbors(heightMap, x, y);
        var lowest = null;
        var lowestHeight = terrain.height;
        
        for (var dir in neighbors) {
            var neighbor = neighbors[dir];
            if (neighbor && neighbor.height < lowestHeight) {
                lowest = neighbor;
                lowestHeight = neighbor.height;
            }
        }
        
        return lowest;
    }

    // Export
    window.GameTerrain = {
        TERRAIN_TYPES: TERRAIN_TYPES,
        HEIGHT_LEVELS: HEIGHT_LEVELS,
        generateHeightMap: generateHeightMap,
        getTerrainAt: getTerrainAt,
        isWalkable: isWalkable,
        getMovementCost: getMovementCost,
        getVisualHeight: getVisualHeight,
        getWaterFlowDirection: getWaterFlowDirection
    };
})();
