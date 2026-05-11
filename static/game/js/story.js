/**
 * NxSiran Game - Story Engine v0.5
 * Chapter-based story system with branching dialogue, CG triggers, and progress tracking.
 * Depends on: StoryData (story_data.js), GameState (state.js), GameNPC (npc.js), GameHUD (hud.js)
 */
(function () {
    'use strict';

    // ── Constants ──────────────────────────────────────────────
    var STORAGE_KEY = 'game_story_progress';
    var CG_BASE_URL = 'https://image.pollinations.ai/prompt/';
    var CG_WIDTH = 720;
    var CG_HEIGHT = 480;

    // ── State ──────────────────────────────────────────────────
    var _currentChapterId = null;
    var _currentSceneId = null;
    var _progress = {
        completedChapters: [],
        currentChapter: null,
        currentScene: null,
        choices: {},
        unlockedEvents: [],
        collectedCGs: []
    };
    var _isActive = false;  // story mode is showing
    var _modalEl = null;    // story modal element
    var _typewriterTimer = null;

    // ── Initialize ─────────────────────────────────────────────
    function init() {
        loadProgress();
        console.log('[Story] Engine initialized. Completed chapters:', _progress.completedChapters);
    }

    // ── Chapter Access ─────────────────────────────────────────
    function getChapters() {
        if (!window.StoryData) {
            console.error('[Story] StoryData not loaded');
            return [];
        }
        return StoryData.chapters;
    }

    function getAvailableChapters(userHearts, userAwakening) {
        var allChapters = getChapters();
        var available = [];
        for (var i = 0; i < allChapters.length; i++) {
            var ch = allChapters[i];
            var hearts = userHearts || 0;
            var awakening = userAwakening || 0;
            if (hearts >= ch.requiredHearts && awakening >= ch.requiredAwakening) {
                available.push(ch);
            }
        }
        return available;
    }

    function isChapterCompleted(chapterId) {
        return _progress.completedChapters.indexOf(chapterId) !== -1;
    }

    // ── Story Mode UI ──────────────────────────────────────────

    /**
     * Open the chapter selection screen
     */
    function openChapterSelect() {
        var state = GameState.getState();
        var hearts = state.hearts || 0;
        var awakening = (state.emotionValues && state.emotionValues.chayewoon) ?
            state.emotionValues.chayewoon.awakening || 0 : 0;

        var allChapters = getChapters();
        var html = '<div class="story-modal" id="story-modal">';

        // Header
        html += '<div class="story-modal-header">';
        html += '<span class="story-modal-title">恋爱至上主义区域</span>';
        html += '<button class="story-close-btn" onclick="GameStory.closeStory()">&times;</button>';
        html += '</div>';

        // Chapter grid
        html += '<div class="story-chapter-select">';
        for (var i = 0; i < allChapters.length; i++) {
            var ch = allChapters[i];
            var locked = hearts < ch.requiredHearts || awakening < ch.requiredAwakening;
            var completed = isChapterCompleted(ch.id);

            var cardClass = 'story-chapter-card';
            if (locked) cardClass += ' locked';
            if (completed) cardClass += ' completed';

            html += '<div class="' + cardClass + '" onclick="GameStory.' +
                (locked ? '' : 'startChapter(\'' + ch.id + '\')') + '">';

            // Chapter number
            html += '<div class="story-chapter-number">' + (i + 1) + '</div>';

            // Title
            html += '<div class="story-chapter-title">' + ch.title + '</div>';
            html += '<div class="story-chapter-subtitle">' + ch.subtitle + '</div>';

            // Status
            if (locked) {
                html += '<div class="story-chapter-locked-info">';
                html += '<span class="story-lock-icon">&#x1F512;</span>';
                if (ch.requiredHearts > 0) {
                    html += '<span>需要 ' + ch.requiredHearts + ' &#x2764;&#xFE0F;</span>';
                }
                if (ch.requiredAwakening > 0) {
                    html += '<span>需要 ' + ch.requiredAwakening + ' &#x1D52E; 觉醒</span>';
                }
                html += '</div>';
            } else if (completed) {
                html += '<div class="story-chapter-status">&#x2714;&#xFE0F; 已完成</div>';
            } else {
                html += '<div class="story-chapter-status story-status-new">&#x2728; 可游玩</div>';
            }

            html += '</div>';
        }
        html += '</div>';

        // CG Gallery link
        html += '<div class="story-gallery-link" onclick="GameStory.openCGGallery()">';
        html += '&#x1F5BC;&#xFE0F; CG 回忆画廊';
        html += '</div>';

        html += '</div>';

        // Create or reuse modal
        _modalEl = document.getElementById('story-modal');
        if (!_modalEl) {
            _modalEl = document.createElement('div');
            _modalEl.id = 'story-modal-container';
            document.body.appendChild(_modalEl);
        }
        _modalEl.innerHTML = html;
        _modalEl.style.display = 'block';
        _isActive = true;

        // v1.2a: Register with panel manager
        if (window.GamePanels) GamePanels.open('story');
    }

    /**
     * Start a chapter - show title card then first scene
     */
    function startChapter(chapterId) {
        var chapter = window.StoryData ? StoryData.getChapter(chapterId) : null;
        if (!chapter) {
            console.error('[Story] Chapter not found:', chapterId);
            return;
        }

        _currentChapterId = chapterId;
        _currentSceneId = null;
        _progress.currentChapter = chapterId;
        saveProgress();

        // v0.9: Switch BGM to story track and play chapter start SFX
        if (window.GameAudio) {
            GameAudio.playBGM('story');
            GameAudio.playChapterStart();
        }

        // Show chapter title card
        var html = '<div class="story-modal" id="story-modal">';

        // Title card
        html += '<div class="story-title-card">';
        html += '<div class="story-title-card-subtitle">' + chapter.subtitle + '</div>';
        html += '<div class="story-title-card-title">' + chapter.title + '</div>';
        html += '<div class="story-title-card-hint">点击任意处开始</div>';
        html += '</div>';

        html += '</div>';

        _modalEl = document.getElementById('story-modal-container');
        if (_modalEl) {
            _modalEl.innerHTML = html;
            // Click to advance
            _modalEl.onclick = function () {
                _modalEl.onclick = null;
                showScene(chapter.scenes[0].id);
            };
        }
    }

    /**
     * Show a specific scene
     */
    function showScene(sceneId) {
        if (!_currentChapterId) return;

        var scene = window.StoryData ?
            StoryData.getScene(_currentChapterId, sceneId) : null;
        if (!scene) {
            console.error('[Story] Scene not found:', sceneId);
            return;
        }

        _currentSceneId = sceneId;
        _progress.currentScene = sceneId;
        saveProgress();

        // Apply expression if specified
        if (scene.expression && window.GameNPC) {
            GameNPC.setExpression('chayewoon', scene.expression);
        }

        var html = '<div class="story-modal" id="story-modal">';

        // Scene header with progress
        var chapter = StoryData.getChapter(_currentChapterId);
        var sceneIndex = 0;
        for (var i = 0; i < chapter.scenes.length; i++) {
            if (chapter.scenes[i].id === sceneId) { sceneIndex = i; break; }
        }
        var progress = Math.round(((sceneIndex + 1) / chapter.scenes.length) * 100);

        html += '<div class="story-scene-header">';
        html += '<span class="story-scene-chapter">' + chapter.title + '</span>';
        html += '<button class="story-close-btn" onclick="GameStory.closeStory()">&times;</button>';
        html += '</div>';
        html += '<div class="story-progress-bar"><div class="story-progress-fill" style="width:' + progress + '%"></div></div>';

        // Scene content area
        html += '<div class="story-scene-area" id="story-scene-area">';

        switch (scene.type) {
            case 'narration':
                html += renderNarration(scene);
                break;
            case 'dialogue':
                html += renderDialogue(scene);
                break;
            case 'choice':
                html += renderChoice(scene);
                break;
            case 'cg':
                html += renderCG(scene);
                break;
            case 'event':
                html += renderEvent(scene);
                break;
            default:
                html += '<div class="story-narration">' + escapeHtml(scene.text || '') + '</div>';
        }

        html += '</div>'; // end story-scene-area
        html += '</div>'; // end story-modal

        _modalEl = document.getElementById('story-modal-container');
        if (_modalEl) {
            _modalEl.innerHTML = html;
            _modalEl.onclick = handleSceneClick;
        }
    }

    // ── Scene Renderers ────────────────────────────────────────

    function renderNarration(scene) {
        var html = '<div class="story-narration" id="story-text-content">';
        html += escapeHtml(scene.text || '');
        html += '</div>';
        html += '<div class="story-advance-hint">&#x25BC; 点击继续</div>';
        return html;
    }

    function renderDialogue(scene) {
        var speakerName = '';
        var speakerClass = 'story-speaker-system';

        switch (scene.speaker) {
            case 'chayewoon':
                speakerName = '车如云';
                speakerClass = 'story-speaker-chayewoon';
                break;
            case 'player':
                speakerName = '学长';
                speakerClass = 'story-speaker-player';
                break;
            default:
                speakerName = '';
                speakerClass = 'story-speaker-system';
        }

        var html = '<div class="story-speaker-name ' + speakerClass + '">' + speakerName + '</div>';
        html += '<div class="story-dialogue-text" id="story-text-content">';
        html += escapeHtml(scene.text || '');
        html += '</div>';
        html += '<div class="story-advance-hint">&#x25BC; 点击继续</div>';
        return html;
    }

    function renderChoice(scene) {
        var html = '<div class="story-choice-prompt">' + escapeHtml(scene.text || '') + '</div>';
        html += '<div class="story-choices">';
        for (var i = 0; i < scene.choices.length; i++) {
            var choice = scene.choices[i];
            var effectTags = '';
            if (choice.effects) {
                if (choice.effects.affection) {
                    effectTags += '<span class="story-effect-tag affection">&#x2764;&#xFE0F; ' +
                        (choice.effects.affection > 0 ? '+' : '') + choice.effects.affection + '</span>';
                }
                if (choice.effects.happiness) {
                    effectTags += '<span class="story-effect-tag happiness">&#x2728; ' +
                        (choice.effects.happiness > 0 ? '+' : '') + choice.effects.happiness + '</span>';
                }
                if (choice.effects.awakening) {
                    effectTags += '<span class="story-effect-tag awakening">&#x1D52E; +' + choice.effects.awakening + '</span>';
                }
            }
            html += '<button class="story-choice-btn" data-index="' + i + '" ' +
                'onclick="event.stopPropagation(); GameStory.handleChoice(' + i + ')">';
            html += '<span class="story-choice-text">' + escapeHtml(choice.text) + '</span>';
            if (effectTags) {
                html += '<span class="story-choice-effects">' + effectTags + '</span>';
            }
            html += '</button>';
        }
        html += '</div>';
        return html;
    }

    function renderCG(scene) {
        var encodedPrompt = encodeURIComponent(scene.prompt || '');
        var imageUrl = CG_BASE_URL + encodedPrompt + '?width=' + CG_WIDTH + '&height=' + CG_HEIGHT +
            '&nologo=true&seed=' + hashCode(scene.prompt || 'cg');

        var html = '<div class="story-cg-overlay">';
        html += '<img class="story-cg-image" src="' + imageUrl + '" alt="' +
            escapeHtml(scene.caption || 'CG') + '" onerror="this.style.display=\'none\'; this.nextElementSibling.style.display=\'block\';" />';
        html += '<div class="story-cg-placeholder" style="display:none;">&#x1F5BC;&#xFE0F; CG 加载中...</div>';
        if (scene.caption) {
            html += '<div class="story-cg-caption">' + escapeHtml(scene.caption) + '</div>';
        }
        html += '</div>';
        html += '<div class="story-advance-hint">&#x25BC; 点击继续</div>';
        return html;
    }

    function renderEvent(scene) {
        var html = '<div class="story-event-card">';
        html += '<div class="story-event-content">' + escapeHtml(scene.text || '').replace(/\n/g, '<br>') + '</div>';

        if (scene.unlockEvent) {
            html += '<div class="story-event-unlock">&#x1F525; 解锁心级事件：' + escapeHtml(scene.unlockEvent) + '</div>';
        }

        html += '<button class="story-event-close-btn" onclick="event.stopPropagation(); GameStory.closeStory()">' +
            '返回</button>';
        html += '</div>';
        return html;
    }

    // ── Scene Interaction ──────────────────────────────────────

    function handleSceneClick(e) {
        if (!e) return;
        // Don't advance if clicking a button
        if (e.target.tagName === 'BUTTON' || e.target.closest('button')) return;

        advanceToNext();
    }

    function handleChoice(choiceIndex) {
        if (!_currentChapterId || !_currentSceneId) return;

        var scene = window.StoryData ?
            StoryData.getScene(_currentChapterId, _currentSceneId) : null;
        if (!scene || scene.type !== 'choice') return;

        var choice = scene.choices[choiceIndex];
        if (!choice) return;

        // v0.9: Play choice SFX
        if (window.GameAudio) {
            GameAudio.playChoice();
        }

        // v1.2e: Haptic feedback on choice selection
        if (window.GameMiniApp) GameMiniApp.hapticFeedback('select');

        // Record choice
        if (!_progress.choices[_currentChapterId]) {
            _progress.choices[_currentChapterId] = {};
        }
        _progress.choices[_currentChapterId][_currentSceneId] = choiceIndex;
        saveProgress();

        // Apply effects to GameState
        if (choice.effects && window.GameState) {
            var state = GameState.getState();
            var emotions = state.emotionValues && state.emotionValues.chayewoon ?
                state.emotionValues.chayewoon : { affection: 0, happiness: 0, awakening: 0 };

            var changed = false;
            if (choice.effects.affection) {
                emotions.affection = (emotions.affection || 0) + choice.effects.affection;
                changed = true;
            }
            if (choice.effects.happiness) {
                emotions.happiness = (emotions.happiness || 0) + choice.effects.happiness;
                changed = true;
            }
            if (choice.effects.awakening) {
                emotions.awakening = (emotions.awakening || 0) + choice.effects.awakening;
                changed = true;
            }

            if (changed) {
                GameState.dispatch({
                    type: 'UPDATE_EMOTION_VALUES',
                    payload: { npcId: 'chayewoon', values: emotions }
                });

                // Show effect toast
                if (window.GameHUD) {
                    var parts = [];
                    if (choice.effects.affection) parts.push('\u2764\uFE0F' + (choice.effects.affection > 0 ? '+' : '') + choice.effects.affection);
                    if (choice.effects.happiness) parts.push('\u2728' + (choice.effects.happiness > 0 ? '+' : '') + choice.effects.happiness);
                    if (choice.effects.awakening) parts.push('\uD83D\uDD2E+' + choice.effects.awakening);
                    if (parts.length > 0) {
                        GameHUD.showToast(parts.join('  '), 'success', 3000);
                    }
                }
            }
        }

        // Show player choice feedback briefly, then advance
        var sceneArea = document.getElementById('story-scene-area');
        if (sceneArea) {
            sceneArea.innerHTML = '<div class="story-choice-feedback">"' + escapeHtml(choice.text) + '"</div>';
            setTimeout(function () {
                if (choice.next) {
                    showScene(choice.next);
                }
            }, 600);
        } else if (choice.next) {
            showScene(choice.next);
        }
    }

    function advanceToNext() {
        if (!_currentChapterId || !_currentSceneId) return;

        var scene = window.StoryData ?
            StoryData.getScene(_currentChapterId, _currentSceneId) : null;
        if (!scene) return;

        // Revert expression
        if (window.GameNPC && scene.expression) {
            var state = GameState.getState();
            var emotions = state.emotionValues && state.emotionValues.chayewoon;
            if (emotions) {
                GameNPC.setExpression('chayewoon', GameNPC.inferExpression(emotions));
            } else {
                GameNPC.setExpression('chayewoon', 'default');
            }
        }

        if (scene.next) {
            showScene(scene.next);
        } else {
            // End of scene chain - check if chapter is complete
            completeChapter(_currentChapterId);
        }
    }

    // ── Chapter Completion ─────────────────────────────────────

    function completeChapter(chapterId) {
        if (_progress.completedChapters.indexOf(chapterId) === -1) {
            _progress.completedChapters.push(chapterId);
        }
        _progress.currentChapter = null;
        _progress.currentScene = null;
        saveProgress();

        console.log('[Story] Chapter completed:', chapterId);
    }

    // ── CG Gallery ─────────────────────────────────────────────

    function openCGGallery() {
        var allChapters = getChapters();
        var cgList = [];

        for (var i = 0; i < allChapters.length; i++) {
            var ch = allChapters[i];
            for (var j = 0; j < ch.scenes.length; j++) {
                var scene = ch.scenes[j];
                if (scene.type === 'cg') {
                    cgList.push({
                        chapterTitle: ch.title,
                        caption: scene.caption || '',
                        prompt: scene.prompt || '',
                        collected: isChapterCompleted(ch.id)
                    });
                }
            }
        }

        var html = '<div class="story-modal" id="story-modal">';
        html += '<div class="story-modal-header">';
        html += '<span class="story-modal-title">&#x1F5BC;&#xFE0F; CG 回忆画廊</span>';
        html += '<button class="story-close-btn" onclick="GameStory.openChapterSelect()">&larr;</button>';
        html += '</div>';
        html += '<div class="story-cg-gallery">';

        if (cgList.length === 0) {
            html += '<div class="story-gallery-empty">还没有收集到任何 CG。</div>';
        } else {
            for (var k = 0; k < cgList.length; k++) {
                var cg = cgList[k];
                var encodedPrompt = encodeURIComponent(cg.prompt);
                var imageUrl = CG_BASE_URL + encodedPrompt + '?width=' + CG_WIDTH + '&height=' + CG_HEIGHT +
                    '&nologo=true&seed=' + hashCode(cg.prompt);

                html += '<div class="story-cg-gallery-item' + (cg.collected ? '' : ' locked') + '">';
                if (cg.collected) {
                    html += '<img class="story-cg-gallery-thumb" src="' + imageUrl + '" alt="' +
                        escapeHtml(cg.caption) + '" />';
                    html += '<div class="story-cg-gallery-info">';
                    html += '<span class="story-cg-gallery-caption">' + escapeHtml(cg.caption) + '</span>';
                    html += '<span class="story-cg-gallery-chapter">' + escapeHtml(cg.chapterTitle) + '</span>';
                    html += '</div>';
                } else {
                    html += '<div class="story-cg-gallery-locked">&#x1F512;</div>';
                    html += '<div class="story-cg-gallery-info">';
                    html += '<span class="story-cg-gallery-caption">???</span>';
                    html += '<span class="story-cg-gallery-chapter">' + escapeHtml(cg.chapterTitle) + '</span>';
                    html += '</div>';
                }
                html += '</div>';
            }
        }

        html += '</div>'; // gallery
        html += '</div>'; // modal

        _modalEl = document.getElementById('story-modal-container');
        if (_modalEl) {
            _modalEl.innerHTML = html;
        }
    }

    // ── Close Story ────────────────────────────────────────────

    function closeStory() {
        _isActive = false;
        _currentChapterId = null;
        _currentSceneId = null;

        // v1.2a: Unregister from panel manager
        if (window.GamePanels) GamePanels.close('story');

        // v0.9: Switch BGM back to previous track when story closes
        if (window.GameAudio) {
            GameAudio.playPreviousBGM();
        }

        // Revert NPC expression
        if (window.GameNPC) {
            var state = GameState.getState();
            var emotions = state.emotionValues && state.emotionValues.chayewoon;
            if (emotions) {
                GameNPC.setExpression('chayewoon', GameNPC.inferExpression(emotions));
            } else {
                GameNPC.setExpression('chayewoon', 'default');
            }
        }

        _modalEl = document.getElementById('story-modal-container');
        if (_modalEl) {
            _modalEl.innerHTML = '';
            _modalEl.style.display = 'none';
        }

        clearTimeout(_typewriterTimer);
    }

    // ── Progress Persistence ───────────────────────────────────

    function saveProgress() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(_progress));
        } catch (e) {
            console.warn('[Story] Failed to save progress:', e);
        }
    }

    function loadProgress() {
        try {
            var saved = localStorage.getItem(STORAGE_KEY);
            if (saved) {
                var parsed = JSON.parse(saved);
                _progress.completedChapters = parsed.completedChapters || [];
                _progress.currentChapter = parsed.currentChapter || null;
                _progress.currentScene = parsed.currentScene || null;
                _progress.choices = parsed.choices || {};
                _progress.unlockedEvents = parsed.unlockedEvents || [];
                _progress.collectedCGs = parsed.collectedCGs || [];
            }
        } catch (e) {
            console.warn('[Story] Failed to load progress:', e);
        }
    }

    function getProgress() {
        return {
            completedChapters: _progress.completedChapters.slice(),
            currentChapter: _progress.currentChapter,
            currentScene: _progress.currentScene,
            choices: JSON.parse(JSON.stringify(_progress.choices)),
            unlockedEvents: _progress.unlockedEvents.slice(),
            collectedCGs: _progress.collectedCGs.slice()
        };
    }

    function resetProgress() {
        _progress = {
            completedChapters: [],
            currentChapter: null,
            currentScene: null,
            choices: {},
            unlockedEvents: [],
            collectedCGs: []
        };
        saveProgress();
        console.log('[Story] Progress reset');
    }

    // ── Utilities ──────────────────────────────────────────────

    function escapeHtml(str) {
        if (!str) return '';
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function hashCode(str) {
        var hash = 0;
        for (var i = 0; i < str.length; i++) {
            var char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash; // Convert to 32bit integer
        }
        return Math.abs(hash);
    }

    // ── Export ─────────────────────────────────────────────────
    window.GameStory = {
        init: init,
        getChapters: getChapters,
        getAvailableChapters: getAvailableChapters,
        isChapterCompleted: isChapterCompleted,
        openChapterSelect: openChapterSelect,
        startChapter: startChapter,
        showScene: showScene,
        handleChoice: handleChoice,
        advanceToNext: advanceToNext,
        completeChapter: completeChapter,
        closeStory: closeStory,
        openCGGallery: openCGGallery,
        getProgress: getProgress,
        saveProgress: saveProgress,
        loadProgress: loadProgress,
        resetProgress: resetProgress
    };
})();
