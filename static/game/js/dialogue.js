/**
 * NxSiran Game - Dialogue System
 * NPC dialogue with typewriter effect and emotion panel integration
 * v0.3: Added media support (selfie, sticker, TTS)
 */
(function () {
    'use strict';

    var _dialogueEl = null;
    var _isOpen = false;
    var _currentNPC = null;
    var _typewriterTimer = null;
    var _emotionPanelEl = null;
    var _lastReply = '';  // v0.3: 保存最后一条回复用于 TTS

    function init() {
        _dialogueEl = document.getElementById('dialogue-box');
    }

    function openNPCDialog(npcId) {
        var state = GameState.getState();
        var npc = state.npc[npcId];
        if (!npc) return;

        _currentNPC = npcId;
        _isOpen = true;

        if (!_dialogueEl) return;
        _dialogueEl.classList.add('open');

        // Get emotion values for this NPC
        var emotions = state.emotionValues && state.emotionValues[npcId] || { affection: 0, happiness: 0, awakening: 0 };
        var awakeningStage = getAwakeningStage(emotions.awakening);

        _dialogueEl.innerHTML =
            '<div class="dialogue-header">' +
            '<span class="npc-name">' + (npc.name || npcId) + '</span>' +
            '<span class="awakening-badge" title="觉醒阶段: ' + awakeningStage.name + '">' + awakeningStage.emoji + ' ' + awakeningStage.name + '</span>' +
            '<div class="dialogue-actions">' +
            '<button class="dialogue-action-btn" onclick="GameDialogue.requestSelfie()" title="要自拍">📷</button>' +
            '<button class="dialogue-action-btn" onclick="GameDialogue.playLastTTS()" title="播放语音">🔊</button>' +
            '</div>' +
            '</div>' +
            '<div class="dialogue-emotion-panel" id="dialogue-emotion-panel">' +
            renderEmotionBars(emotions) +
            '</div>' +
            '<div class="dialogue-content" id="dialogue-text">\u2026</div>' +
            '<div class="dialogue-input-row">' +
            '<input type="text" id="dialogue-input" placeholder="\u8BF4\u70B9\u4EC0\u4E48..." />' +
            '<button id="dialogue-send" onclick="GameDialogue.send()">\u53D1\u9001</button>' +
            '</div>';

        // Focus input
        setTimeout(function () {
            var input = document.getElementById('dialogue-input');
            if (input) input.focus();
        }, 100);

        // Enter key
        var inputEl = document.getElementById('dialogue-input');
        if (inputEl) {
            inputEl.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') send();
            });
        }

        // Store emotion panel reference
        _emotionPanelEl = document.getElementById('dialogue-emotion-panel');
    }

    // ── Render Emotion Bars ───────────────────────────────────
    function renderEmotionBars(emotions) {
        var affection = emotions.affection || 0;
        var happiness = emotions.happiness || 0;
        var awakening = emotions.awakening || 0;

        return '<div class="emotion-bars">' +
            '<div class="emotion-bar-row">' +
            '<span class="emotion-label">\u2764\uFE0F \u597D\u611F\u5EA6</span>' +
            '<div class="emotion-bar"><div class="emotion-fill affection-fill" style="width:' + Math.max(0, Math.min(100, affection + 50)) + '%"></div></div>' +
            '<span class="emotion-value">' + affection + '</span>' +
            '</div>' +
            '<div class="emotion-bar-row">' +
            '<span class="emotion-label">\u2728 \u5E78\u798F\u5EA6</span>' +
            '<div class="emotion-bar"><div class="emotion-fill happiness-fill" style="width:' + Math.max(0, Math.min(100, happiness + 50)) + '%"></div></div>' +
            '<span class="emotion-value">' + happiness + '</span>' +
            '</div>' +
            '<div class="emotion-bar-row">' +
            '<span class="emotion-label">\uD83D\uDD2E \u89C9\u9192\u5EA6</span>' +
            '<div class="emotion-bar"><div class="emotion-fill awakening-fill" style="width:' + awakening + '%"></div></div>' +
            '<span class="emotion-value">' + awakening + '%</span>' +
            '</div>' +
            '</div>';
    }

    // ── Update Emotion Panel ──────────────────────────────────
    function updateEmotionPanel() {
        if (!_emotionPanelEl || !_isOpen || !_currentNPC) return;

        var state = GameState.getState();
        var emotions = state.emotionValues && state.emotionValues[_currentNPC] || { affection: 0, happiness: 0, awakening: 0 };

        _emotionPanelEl.innerHTML = renderEmotionBars(emotions);

        // Update awakening badge in header
        var awakeningStage = getAwakeningStage(emotions.awakening);
        var badge = _dialogueEl.querySelector('.awakening-badge');
        if (badge) {
            badge.textContent = awakeningStage.emoji + ' ' + awakeningStage.name;
            badge.title = '觉醒阶段: ' + awakeningStage.name;
        }
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

    function send() {
        var input = document.getElementById('dialogue-input');
        if (!input || !input.value.trim()) return;

        var message = input.value.trim();
        input.value = '';

        var textEl = document.getElementById('dialogue-text');
        if (textEl) {
            textEl.innerHTML += '<div class="dialogue-msg player-msg">\u5B8C\u6210\u8005: ' + escapeHtml(message) + '</div>';
            textEl.innerHTML += '<div class="dialogue-msg npc-msg" id="npc-reply">\u2026</div>';
            textEl.scrollTop = textEl.scrollHeight;
        }

        // Call API (v0.2 - 使用新的对话引擎)
        if (window.GameAPI) {
            GameAPI.chat(_currentNPC, message).then(function (data) {
                if (data && data.response) {
                    _lastReply = data.response;  // v0.3: 保存回复用于 TTS
                    typeText('npc-reply', data.response);

                    // v0.3: 检测情绪并发送表情包
                    detectAndSendSticker(data.response);

                    // v0.3: 更新 NPC 表情
                    if (window.GameNPC) {
                        GameNPC.setExpressionFromText(_currentNPC, data.response);
                    }

                    // v0.3: 显示对话选项
                    if (data.has_options && data.options && data.options.length > 0) {
                        showDialogueOptions(data.options);
                    }

                    // 更新情感值 (v0.2)
                    if (data.emotion_changes) {
                        var currentEmotions = GameState.getState().emotionValues &&
                            GameState.getState().emotionValues[_currentNPC] || { affection: 0, happiness: 0, awakening: 0 };
                        currentEmotions.affection = Math.round((currentEmotions.affection || 0) + (data.emotion_changes.affection || 0));
                        currentEmotions.happiness = Math.round((currentEmotions.happiness || 0) + (data.emotion_changes.happiness || 0));
                        currentEmotions.awakening = Math.round((currentEmotions.awakening || 0) + (data.emotion_changes.awakening || 0));

                        GameState.dispatch({
                            type: 'UPDATE_EMOTION_VALUES',
                            payload: { npcId: _currentNPC, values: currentEmotions }
                        });
                        updateEmotionPanel();

                        // 显示情感变化提示
                        showEmotionChangeToast(data.emotion_changes);
                    }

                    // 检查觉醒事件 (v0.2)
                    if (data.awakening_triggered) {
                        showAwakeningEvent(data.awakening_triggered);
                    }
                } else {
                    var replyEl = document.getElementById('npc-reply');
                    if (replyEl) replyEl.textContent = '\u2026';
                }
            }).catch(function () {
                var replyEl = document.getElementById('npc-reply');
                if (replyEl) replyEl.textContent = '\u2026\uFF08\u7F51\u7EDC\u9519\u8BEF\uFF09';
            });
        }
    }

    // ── Show Awakening Notification ───────────────────────────
    // ── Show Awakening Event (v0.2) ───────────────────────────
    function showAwakeningEvent(event) {
        if (!event) return;

        var textEl = document.getElementById('dialogue-text');
        if (!textEl) return;

        // 插入觉醒事件卡片
        var eventHtml =
            '<div class="awakening-event-card">' +
            '<div class="awakening-event-header">' +
            event.stage_emoji + ' ' + event.title +
            '</div>' +
            '<div class="awakening-event-desc">' + event.description + '</div>' +
            '<div class="awakening-event-dialogue">' +
            event.dialogue.replace(/\n/g, '<br>') +
            '</div>' +
            '</div>';

        textEl.innerHTML += eventHtml;
        textEl.scrollTop = textEl.scrollHeight;

        // 显示全局通知
        if (window.GameHUD) {
            GameHUD.showToast(
                event.stage_emoji + ' ' + (event.stage_name || '') + ' — ' + event.title,
                'special', 6000
            );
        }
    }

    // ── Show Emotion Change Toast ─────────────────────────────
    function showEmotionChangeToast(changes) {
        if (!changes) return;
        var parts = [];
        if (changes.affection && changes.affection !== 0) {
            parts.push('\u2764\uFE0F' + (changes.affection > 0 ? '+' : '') + changes.affection);
        }
        if (changes.happiness && changes.happiness !== 0) {
            parts.push('\u2728' + (changes.happiness > 0 ? '+' : '') + changes.happiness);
        }
        if (changes.awakening && changes.awakening > 0) {
            parts.push('\uD83D\uDD2E+' + changes.awakening);
        }
        if (parts.length > 0 && window.GameHUD) {
            GameHUD.showToast(parts.join('  '), 'info', 3000);
        }
    }

    function showAwakeningNotification(stage) {
        var stageNames = {
            2: '\u89E6\u52A8',
            3: '\u89C9\u9192',
            4: '\u5171\u9E23',
            5: '\u5B8C\u6210'
        };
        var stageEmojis = {
            2: '\uD83D\uDCA1',
            3: '\uD83D\uDD2E',
            4: '\u2728',
            5: '\uD83C\uDF1F'
        };

        if (window.GameHUD) {
            GameHUD.showToast(
                stageEmojis[stage] + ' ' + (_currentNPC || 'NPC') + ' \u8FDB\u5165\u3010' + stageNames[stage] + '\u3011\u9636\u6BB5\uFF01',
                'special',
                5000
            );
        }
    }

    function typeText(elementId, text) {
        clearTimeout(_typewriterTimer);
        var el = document.getElementById(elementId);
        if (!el) return;

        var idx = 0;
        el.textContent = '';
        function typeChar() {
            if (idx < text.length) {
                el.textContent += text[idx];
                idx++;
                _typewriterTimer = setTimeout(typeChar, 30);
            }
        }
        typeChar();
    }

    function close() {
        _isOpen = false;
        _currentNPC = null;
        _emotionPanelEl = null;
        clearTimeout(_typewriterTimer);
        if (_dialogueEl) _dialogueEl.classList.remove('open');
    }

    function escapeHtml(str) {
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    // ── Subscribe to emotion updates ──────────────────────────
    if (window.GameState) {
        GameState.subscribe(function (state, prev, action) {
            if (action.type === 'UPDATE_EMOTION_VALUES' && _isOpen && _currentNPC) {
                updateEmotionPanel();
            }
        });
    }

    // ── v0.3 Media Functions ──────────────────────────────────

    /**
     * 请求 NPC 发送自拍
     */
    function requestSelfie() {
        if (!window.GameAPI || !_isOpen) return;

        var textEl = document.getElementById('dialogue-text');
        if (textEl) {
            textEl.innerHTML += '<div class="dialogue-msg player-msg">完成者: 给我发张自拍？</div>';
            textEl.innerHTML += '<div class="dialogue-msg npc-msg" id="selfie-loading">正在拍照...</div>';
            textEl.scrollTop = textEl.scrollHeight;
        }

        GameAPI.generateSelfie().then(function (data) {
            var loadingEl = document.getElementById('selfie-loading');
            if (loadingEl && data && data.url) {
                loadingEl.innerHTML = 
                    '<div class="media-message">' +
                    '<img src="' + data.url + '" class="selfie-image" onload="this.parentElement.scrollIntoView()" />' +
                    '<span class="media-caption">...给你看看。</span>' +
                    '</div>';
            }
        }).catch(function (err) {
            var loadingEl = document.getElementById('selfie-loading');
            if (loadingEl) loadingEl.textContent = '...算了。';
        });
    }

    /**
     * 根据情绪生成表情包
     */
    function sendSticker(mood) {
        if (!window.GameAPI || !_isOpen) return;

        GameAPI.generateSticker(mood || '默认').then(function (data) {
            if (data && data.url) {
                var textEl = document.getElementById('dialogue-text');
                if (textEl) {
                    textEl.innerHTML += 
                        '<div class="dialogue-msg npc-msg">' +
                        '<img src="' + data.url + '" class="sticker-image" />' +
                        '</div>';
                    textEl.scrollTop = textEl.scrollHeight;
                }
            }
        });
    }

    /**
     * 播放最后一条回复的语音
     */
    function playLastTTS() {
        if (!window.GameAPI || !_lastReply) {
            if (window.GameHUD) GameHUD.showToast('没有可播放的消息', 'info');
            return;
        }

        GameAPI.tts(_lastReply).then(function (data) {
            if (data && data.audio_url) {
                var audio = new Audio(data.audio_url);
                audio.play();
            }
        }).catch(function (err) {
            if (window.GameHUD) GameHUD.showToast('语音生成失败', 'error');
        });
    }

    /**
     * 检测情绪并发送表情包
     */
    function detectAndSendSticker(text) {
        var moodKeywords = {
            '害羞': ['害羞', '脸红', '不好意思', '可爱'],
            '生气': ['生气', '哼', '讨厌', '烦'],
            '开心': ['开心', '高兴', '哈哈', '好棒', '笑'],
            '难过': ['难过', '伤心', '哭', '委屈'],
            '想你': ['想你', '想你了', '好想你', 'miss'],
            '吃醋': ['吃醋', '嫉妒', '谁', '别人'],
            '撒娇': ['撒娇', '哥哥', '前辈', '抱抱', '陪我']
        };

        for (var mood in moodKeywords) {
            var keywords = moodKeywords[mood];
            for (var i = 0; i < keywords.length; i++) {
                if (text.indexOf(keywords[i]) !== -1) {
                    sendSticker(mood);
                    return;
                }
            }
        }
    }

    /**
     * 显示对话选项（v0.3）
     */
    function showDialogueOptions(options) {
        var textEl = document.getElementById('dialogue-text');
        if (!textEl) return;

        var optionsHtml = '<div class="dialogue-options">';
        for (var i = 0; i < options.length; i++) {
            var opt = options[i];
            var effectText = '';
            if (opt.effects) {
                var effects = [];
                if (opt.effects.affection) effects.push('❤️' + (opt.effects.affection > 0 ? '+' : '') + opt.effects.affection);
                if (opt.effects.happiness) effects.push('✨' + (opt.effects.happiness > 0 ? '+' : '') + opt.effects.happiness);
                if (opt.effects.awakening) effects.push('🔮' + (opt.effects.awakening > 0 ? '+' : '') + opt.effects.awakening);
                if (effects.length > 0) effectText = ' <span class="option-effect">' + effects.join(' ') + '</span>';
            }
            optionsHtml += 
                '<button class="dialogue-option-btn" onclick="GameDialogue.selectOption(\'' + 
                opt.id + '\', \'' + escapeHtml(opt.text).replace(/'/g, "\\'") + '\', ' + 
                JSON.stringify(opt.effects || {}) + ')">' +
                '<span class="option-id">' + opt.id + '.</span> ' +
                '<span class="option-text">' + opt.text + '</span>' +
                effectText +
                '</button>';
        }
        optionsHtml += '</div>';

        textEl.innerHTML += optionsHtml;
        textEl.scrollTop = textEl.scrollHeight;
    }

    /**
     * 选择对话选项（v0.3）
     */
    function selectOption(optionId, optionText, effects) {
        var textEl = document.getElementById('dialogue-text');
        if (textEl) {
            // 移除选项按钮
            var optionsEl = textEl.querySelector('.dialogue-options');
            if (optionsEl) optionsEl.remove();

            // 显示玩家选择
            textEl.innerHTML += '<div class="dialogue-msg player-msg">完成者: ' + escapeHtml(optionText) + '</div>';
            textEl.scrollTop = textEl.scrollHeight;
        }

        // 应用效果
        if (effects && Object.keys(effects).length > 0) {
            var currentEmotions = GameState.getState().emotionValues &&
                GameState.getState().emotionValues[_currentNPC] || { affection: 0, happiness: 0, awakening: 0 };
            
            for (var key in effects) {
                currentEmotions[key] = Math.round((currentEmotions[key] || 0) + effects[key]);
            }

            GameState.dispatch({
                type: 'UPDATE_EMOTION_VALUES',
                payload: { npcId: _currentNPC, values: currentEmotions }
            });
            updateEmotionPanel();

            // 显示效果提示
            var parts = [];
            if (effects.affection) parts.push('❤️' + (effects.affection > 0 ? '+' : '') + effects.affection);
            if (effects.happiness) parts.push('✨' + (effects.happiness > 0 ? '+' : '') + effects.happiness);
            if (effects.awakening) parts.push('🔮' + (effects.awakening > 0 ? '+' : '') + effects.awakening);
            if (parts.length > 0 && window.GameHUD) {
                GameHUD.showToast(parts.join('  '), 'success', 3000);
            }
        }

        // 发送选项作为消息，获取 NPC 回复
        if (window.GameAPI) {
            textEl.innerHTML += '<div class="dialogue-msg npc-msg" id="npc-option-reply">…</div>';
            
            GameAPI.chat(_currentNPC, optionText).then(function (data) {
                var replyEl = document.getElementById('npc-option-reply');
                if (replyEl && data && data.response) {
                    _lastReply = data.response;
                    replyEl.textContent = data.response;
                    textEl.scrollTop = textEl.scrollHeight;

                    // 检测情绪
                    detectAndSendSticker(data.response);

                    // 更新情感值
                    if (data.emotion_changes) {
                        var emotions = GameState.getState().emotionValues &&
                            GameState.getState().emotionValues[_currentNPC] || { affection: 0, happiness: 0, awakening: 0 };
                        emotions.affection = Math.round((emotions.affection || 0) + (data.emotion_changes.affection || 0));
                        emotions.happiness = Math.round((emotions.happiness || 0) + (data.emotion_changes.happiness || 0));
                        emotions.awakening = Math.round((emotions.awakening || 0) + (data.emotion_changes.awakening || 0));
                        GameState.dispatch({
                            type: 'UPDATE_EMOTION_VALUES',
                            payload: { npcId: _currentNPC, values: emotions }
                        });
                        updateEmotionPanel();
                        showEmotionChangeToast(data.emotion_changes);
                    }

                    // 检查觉醒事件
                    if (data.awakening_triggered) {
                        showAwakeningEvent(data.awakening_triggered);
                    }
                }
            });
        }
    }

    window.GameDialogue = {
        init: init,
        openNPCDialog: openNPCDialog,
        send: send,
        close: close,
        updateEmotionPanel: updateEmotionPanel,
        // v0.3 Media APIs
        requestSelfie: requestSelfie,
        sendSticker: sendSticker,
        playLastTTS: playLastTTS,
        // v0.3 Dialogue Options
        selectOption: selectOption
    };
})();
