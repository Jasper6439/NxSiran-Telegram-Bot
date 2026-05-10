/**
 * NxSiran Game - NPC System
 * NPC positioning, proximity detection, interaction, emotion display
 * v0.3: Added expression system
 */
(function () {
    'use strict';

    var PROXIMITY_RANGE = 2; // tiles
    var _emotionBubbles = {};
    var _expressionOverlays = {};  // v0.3: 表情覆盖层

    // v0.3: 表情映射
    var EXPRESSION_EMOJIS = {
        'default': '',
        'happy': '😊',
        'shy': '😳',
        'angry': '😤',
        'sad': '😢',
        'love': '💕',
        'thinking': '🤔',
        'surprised': '😲'
    };

    // ── Initialize NPCs ────────────────────────────────────────
    function init(npcs) {
        if (!npcs) npcs = {};
        var keys = Object.keys(npcs);
        for (var i = 0; i < keys.length; i++) {
            GameState.dispatch({ type: 'UPDATE_NPC', payload: npcs[keys[i]] });
        }
    }

    // ── Check Proximity ────────────────────────────────────────
    function checkProximity(playerX, playerY) {
        var state = GameState.getState();
        var npcKeys = Object.keys(state.npc);
        for (var i = 0; i < npcKeys.length; i++) {
            var npc = state.npc[npcKeys[i]];
            var dist = Math.abs(playerX - npc.x) + Math.abs(playerY - npc.y);
            if (dist <= PROXIMITY_RANGE) {
                showBubble(npcKeys[i], npc);
                showEmotionBubble(npcKeys[i], npc);
            } else {
                hideBubble(npcKeys[i]);
                hideEmotionBubble(npcKeys[i]);
            }
        }
    }

    // ── Bubble ─────────────────────────────────────────────────
    function showBubble(npcId, npc) {
        var bubble = document.getElementById('bubble-' + npcId);
        if (bubble) {
            bubble.style.display = '';
            bubble.textContent = '\uD83D\uDCAC ' + (npc.name || npcId);
        }
    }

    function hideBubble(npcId) {
        var bubble = document.getElementById('bubble-' + npcId);
        if (bubble) bubble.style.display = 'none';
    }

    // ── Emotion Bubble (Worldview Feature) ─────────────────────
    function showEmotionBubble(npcId, npc) {
        var state = GameState.getState();
        var emotions = state.emotionValues && state.emotionValues[npcId];
        if (!emotions) return;

        var bubble = document.getElementById('emotion-bubble-' + npcId);
        if (!bubble) {
            bubble = document.createElement('div');
            bubble.id = 'emotion-bubble-' + npcId;
            bubble.className = 'emotion-bubble';
            document.getElementById('game-world').appendChild(bubble);
        }

        // Position above NPC
        var GRID_WIDTH_PX = window.GameConstants ? GameConstants.GRID_WIDTH_PX : 40;
        bubble.style.left = (npc.x * GRID_WIDTH_PX + 10) + 'px';
        bubble.style.top = ((npc.y - 1) * GRID_WIDTH_PX - 10) + 'px';
        bubble.style.display = 'block';

        // Get awakening stage
        var awakeningStage = getAwakeningStage(emotions.awakening || 0);
        var stageEmoji = awakeningStage.emoji;

        // Format emotion values
        var affection = emotions.affection || 0;
        var happiness = emotions.happiness || 0;
        var awakening = emotions.awakening || 0;

        // v0.3: 获取当前表情
        var expression = npc.expression || 'default';
        var expressionEmoji = EXPRESSION_EMOJIS[expression] || '';

        bubble.innerHTML =
            '<div class="emotion-bubble-header">' + stageEmoji + ' ' + (npc.name || npcId) + ' ' + expressionEmoji + '</div>' +
            '<div class="emotion-bubble-stats">' +
            '<span class="stat-affection" title="好感度">\u2764\uFE0F ' + affection + '</span>' +
            '<span class="stat-happiness" title="幸福度">\u2728 ' + happiness + '</span>' +
            '<span class="stat-awakening" title="觉醒度">\uD83D\uDD2E ' + awakening + '%</span>' +
            '</div>';

        _emotionBubbles[npcId] = bubble;
    }

    function hideEmotionBubble(npcId) {
        var bubble = document.getElementById('emotion-bubble-' + npcId);
        if (bubble) bubble.style.display = 'none';
    }

    // ── v0.3: Expression System ────────────────────────────────
    
    /**
     * 根据情感值推断表情
     */
    function inferExpression(emotions) {
        if (!emotions) return 'default';
        
        var affection = emotions.affection || 0;
        var happiness = emotions.happiness || 0;
        var awakening = emotions.awakening || 0;
        
        // 高好感 + 高幸福 = 开心/爱意
        if (affection > 50 && happiness > 60) return 'love';
        if (happiness > 70) return 'happy';
        
        // 低幸福 = 难过
        if (happiness < 30) return 'sad';
        
        // 负好感 = 生气
        if (affection < -10) return 'angry';
        
        // 高觉醒 = 思考
        if (awakening > 50) return 'thinking';
        
        // 中等好感 = 害羞
        if (affection > 20 && affection < 50) return 'shy';
        
        return 'default';
    }

    /**
     * 设置 NPC 表情
     */
    function setExpression(npcId, expression) {
        var state = GameState.getState();
        var npc = state.npc[npcId];
        if (!npc) return;

        // 更新状态
        npc.expression = expression;
        GameState.dispatch({ type: 'UPDATE_NPC', payload: npc });

        // 更新视觉
        updateExpressionOverlay(npcId, npc);
        
        // 更新情感气泡
        showEmotionBubble(npcId, npc);
    }

    /**
     * 更新表情覆盖层
     */
    function updateExpressionOverlay(npcId, npc) {
        var GRID_WIDTH_PX = window.GameConstants ? GameConstants.GRID_WIDTH_PX : 40;
        var expression = npc.expression || 'default';
        var emoji = EXPRESSION_EMOJIS[expression];
        
        if (!emoji) {
            // 移除覆盖层
            var existing = _expressionOverlays[npcId];
            if (existing) {
                existing.remove();
                delete _expressionOverlays[npcId];
            }
            return;
        }

        // 创建或更新覆盖层
        var overlay = _expressionOverlays[npcId];
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'npc-expression-overlay';
            document.getElementById('game-world').appendChild(overlay);
            _expressionOverlays[npcId] = overlay;
        }

        overlay.textContent = emoji;
        overlay.style.left = (npc.x * GRID_WIDTH_PX + GRID_WIDTH_PX / 2 - 12) + 'px';
        overlay.style.top = (npc.y * GRID_WIDTH_PX - 20) + 'px';
        overlay.style.display = 'block';
    }

    /**
     * 根据对话内容设置表情
     */
    function setExpressionFromText(npcId, text) {
        var expression = 'default';
        
        if (text.indexOf('开心') !== -1 || text.indexOf('高兴') !== -1 || text.indexOf('哈哈') !== -1) {
            expression = 'happy';
        } else if (text.indexOf('害羞') !== -1 || text.indexOf('脸红') !== -1 || text.indexOf('不好意思') !== -1) {
            expression = 'shy';
        } else if (text.indexOf('生气') !== -1 || text.indexOf('哼') !== -1 || text.indexOf('讨厌') !== -1) {
            expression = 'angry';
        } else if (text.indexOf('难过') !== -1 || text.indexOf('伤心') !== -1 || text.indexOf('哭') !== -1) {
            expression = 'sad';
        } else if (text.indexOf('想你') !== -1 || text.indexOf('喜欢') !== -1 || text.indexOf('爱') !== -1) {
            expression = 'love';
        } else if (text.indexOf('嗯') !== -1 || text.indexOf('...' !== -1)) {
            expression = 'thinking';
        }
        
        setExpression(npcId, expression);
        
        // 3秒后恢复默认
        setTimeout(function () {
            var state = GameState.getState();
            var emotions = state.emotionValues && state.emotionValues[npcId];
            if (emotions) {
                setExpression(npcId, inferExpression(emotions));
            } else {
                setExpression(npcId, 'default');
            }
        }, 3000);
    }

    // ── Awakening Stage Helper ─────────────────────────────────
    function getAwakeningStage(awakeningValue) {
        if (awakeningValue >= 100) {
            return { stage: 5, name: '完成', emoji: '\uD83C\uDF1F' };
        } else if (awakeningValue >= 80) {
            return { stage: 4, name: '共鸣', emoji: '\u2728' };
        } else if (awakeningValue >= 50) {
            return { stage: 3, name: '觉醒', emoji: '\uD83D\uDD2E' };
        } else if (awakeningValue >= 20) {
            return { stage: 2, name: '触动', emoji: '\uD83D\uDCA1' };
        } else {
            return { stage: 1, name: '困局', emoji: '\uD83D\uDD12' };
        }
    }

    // ── Update All Emotion Bubbles ────────────────────────────
    function updateEmotionBubbles() {
        var state = GameState.getState();
        var player = state.player;
        if (!player) return;

        var npcKeys = Object.keys(state.npc);
        for (var i = 0; i < npcKeys.length; i++) {
            var npcId = npcKeys[i];
            var npc = state.npc[npcId];
            var dist = Math.abs(player.x - npc.x) + Math.abs(player.y - npc.y);

            if (dist <= PROXIMITY_RANGE) {
                showEmotionBubble(npcId, npc);
            } else {
                hideEmotionBubble(npcId);
            }
        }
    }

    // ── Export ─────────────────────────────────────────────────
    window.GameNPC = {
        init: init,
        checkProximity: checkProximity,
        showEmotionBubble: showEmotionBubble,
        hideEmotionBubble: hideEmotionBubble,
        updateEmotionBubbles: updateEmotionBubbles,
        getAwakeningStage: getAwakeningStage,
        PROXIMITY_RANGE: PROXIMITY_RANGE,
        // v0.3: Expression System
        setExpression: setExpression,
        setExpressionFromText: setExpressionFromText,
        inferExpression: inferExpression,
        EXPRESSION_EMOJIS: EXPRESSION_EMOJIS
    };
})();
