/**
 * NxSiran Game - Daily Tasks & Achievement System v0.6
 * Daily quests that reset at midnight (KST UTC+9), persistent achievements.
 * Depends on: GameState (state.js), GameHUD (hud.js)
 */
(function () {
    'use strict';

    // ── localStorage Keys ──────────────────────────────────────
    var STORAGE_DAILY_TASKS = 'game_daily_tasks';
    var STORAGE_DAILY_DATE  = 'game_daily_date';
    var STORAGE_ACHIEVEMENTS = 'game_achievements';
    var STORAGE_STATS        = 'game_stats';

    // ── Daily Task Pool ─────────────────────────────────────────
    var DAILY_TASK_POOL = [
        { id: 'water_3',   name: '\u6D47\u704C3\u6B21',   desc: '\u7ED9\u4F5C\u7269\u6D47\u6C343\u6B21',       type: 'water',     target: 3,   reward: { money: 50,  exp: 10 } },
        { id: 'harvest_2', name: '\u6536\u83B72\u6B21',   desc: '\u6536\u83B7\u6210\u719F\u7684\u4F5C\u72692\u6B21', type: 'harvest',   target: 2,   reward: { money: 80,  exp: 15 } },
        { id: 'plant_2',   name: '\u79CD\u690D2\u6B21',   desc: '\u79CD\u690D\u65B0\u4F5C\u72692\u6B21',       type: 'plant',     target: 2,   reward: { money: 30,  exp: 10 } },
        { id: 'chat_3',    name: '\u5BF9\u8BDD3\u6B21',   desc: '\u4E0E\u8F66\u5982\u4E91\u5BF9\u8BDD3\u6B21',   type: 'chat',      target: 3,   reward: { money: 60,  exp: 20, affection: 1 } },
        { id: 'sell_500',  name: '\u51FA\u552E500\u91D1',  desc: '\u51FA\u552E\u4F5C\u7269\u8D5A\u53D6500\u91D1', type: 'sell',      target: 500, reward: { money: 100, exp: 25 } },
        { id: 'buy_seeds', name: '\u8D2D\u4E70\u79CD\u5B50', desc: '\u8D2D\u4E70\u4EFB\u610F\u79CD\u5B50',       type: 'buy_seed',  target: 1,   reward: { money: 40,  exp: 10 } },
        { id: 'selfie_1',  name: '\u81EA\u62CD1\u6B21',   desc: '\u8BF7\u6C42\u8F66\u5982\u4E91\u81EA\u62CD1\u6B21', type: 'selfie', target: 1,   reward: { money: 30,  exp: 15 } },
        { id: 'story_1',   name: '\u9605\u8BFB\u5267\u60C5', desc: '\u63A8\u8FDB1\u4E2A\u5267\u60C5\u573A\u666F',   type: 'story',     target: 1,   reward: { money: 50,  exp: 20 } }
    ];

    var DAILY_TASK_COUNT = 4; // pick 4 per day

    // ── Achievement Definitions ─────────────────────────────────
    var ACHIEVEMENTS = [
        // Farming
        { id: 'first_plant',    name: '\u521D\u6B21\u64AD\u79CD',   desc: '\u7B2C\u4E00\u6B21\u79CD\u690D\u4F5C\u7269',   icon: '\uD83C\uDF31', condition: function (p) { return p.totalPlants >= 1; } },
        { id: 'green_thumb',    name: '\u7EFF\u8272\u62C7\u6307',   desc: '\u7D2F\u8BA1\u79CD\u690D50\u6B21',           icon: '\uD83C\uDF3F', condition: function (p) { return p.totalPlants >= 50; } },
        { id: 'harvest_king',   name: '\u4E30\u6536\u4E4B\u738B',   desc: '\u7D2F\u8BA1\u6536\u83B7100\u6B21',          icon: '\uD83D\uDC51', condition: function (p) { return p.totalHarvests >= 100; } },
        { id: 'rich_farmer',    name: '\u5BCC\u7532\u4E00\u65B9',   desc: '\u7D2F\u8BA1\u8D5A\u53D610000\u91D1',         icon: '\uD83D\uDCB0', condition: function (p) { return p.totalEarned >= 10000; } },

        // Relationship
        { id: 'first_chat',     name: '\u521D\u6B21\u5BF9\u8BDD',   desc: '\u7B2C\u4E00\u6B21\u4E0E\u8F66\u5982\u4E91\u5BF9\u8BDD', icon: '\uD83D\uDCAC', condition: function (p) { return p.totalChats >= 1; } },
        { id: 'close_friend',   name: '\u4EB2\u5BC6\u670B\u53CB',   desc: '\u597D\u611F\u5EA6\u8FBE\u523050',            icon: '\uD83E\uDD1D', condition: function (p) { return p.maxAffection >= 50; } },
        { id: 'heart_3',        name: '\u5FC3\u52A8\u65F6\u523B',   desc: '\u5FC3\u7EA7\u8FBE\u52303',                icon: '\uD83D\uDC97', condition: function (p) { return p.maxHearts >= 3; } },

        // Story
        { id: 'story_ch1',      name: '\u547D\u8FD0\u7684\u76F8\u9047', desc: '\u5B8C\u6210\u7B2C\u4E00\u7AE0',          icon: '\uD83D\uDCD6', condition: function (p) { return p.completedChapters.indexOf('ch1') !== -1; } },
        { id: 'story_ch2',      name: '\u661F\u7A7A\u4E4B\u4E0B',   desc: '\u5B8C\u6210\u7B2C\u4E8C\u7AE0',            icon: '\uD83C\uDF1F', condition: function (p) { return p.completedChapters.indexOf('ch2') !== -1; } },
        { id: 'story_ch3',      name: '\u96E8\u4E2D\u6F2B\u6B65',   desc: '\u5B8C\u6210\u7B2C\u4E09\u7AE0',            icon: '\u2602\uFE0F', condition: function (p) { return p.completedChapters.indexOf('ch3') !== -1; } },

        // Special
        { id: 'selfie_collector', name: '\u81EA\u62CD\u6536\u85CF\u5BB6', desc: '\u6536\u96C610\u5F20\u81EA\u62CD',       icon: '\uD83D\uDCF8', condition: function (p) { return p.totalSelfies >= 10; } },
        { id: 'early_bird',     name: '\u65E9\u8D77\u9E1F\u513F',   desc: '\u8FDE\u7EED3\u5929\u7B7E\u5230',            icon: '\uD83D\uDC26', condition: function (p) { return p.consecutiveLogins >= 3; } }
    ];

    // ── Internal State ──────────────────────────────────────────
    var _dailyTasks   = [];   // today's selected tasks with progress
    var _dailyDate    = '';   // 'YYYY-MM-DD' in KST
    var _unlockedIds  = [];   // unlocked achievement ids
    var _stats        = null; // cumulative player stats
    var _countdownTimer = null;
    var _panelEl      = null;
    var _isOpen       = false;

    // ── Default Stats ───────────────────────────────────────────
    function defaultStats() {
        return {
            totalPlants: 0,
            totalHarvests: 0,
            totalEarned: 0,
            totalChats: 0,
            totalSelfies: 0,
            maxAffection: 0,
            maxHearts: 0,
            completedChapters: [],
            consecutiveLogins: 0,
            lastLoginDate: ''
        };
    }

    // ── KST Date Helpers ────────────────────────────────────────
    function getKSTDate() {
        var now = new Date();
        // Convert to KST (UTC+9)
        var utc = now.getTime() + now.getTimezoneOffset() * 60000;
        var kst = new Date(utc + 9 * 3600000);
        return kst;
    }

    function getKSTDateString() {
        var d = getKSTDate();
        var y = d.getFullYear();
        var m = ('0' + (d.getMonth() + 1)).slice(-2);
        var day = ('0' + d.getDate()).slice(-2);
        return y + '-' + m + '-' + day;
    }

    function getKSTMidnightTimestamp() {
        var kst = getKSTDate();
        // Next midnight KST
        var midnight = new Date(kst.getFullYear(), kst.getMonth(), kst.getDate() + 1, 0, 0, 0, 0);
        // Convert back to local timestamp
        var localOffset = new Date().getTimezoneOffset() * 60000;
        return midnight.getTime() - 9 * 3600000 - localOffset;
    }

    // ── Persistence ─────────────────────────────────────────────
    function save() {
        try {
            localStorage.setItem(STORAGE_DAILY_TASKS, JSON.stringify(_dailyTasks));
            localStorage.setItem(STORAGE_DAILY_DATE, _dailyDate);
            localStorage.setItem(STORAGE_ACHIEVEMENTS, JSON.stringify(_unlockedIds));
            localStorage.setItem(STORAGE_STATS, JSON.stringify(_stats));
        } catch (e) {
            console.warn('[Quests] Failed to save:', e);
        }
    }

    function load() {
        try {
            var tasks = localStorage.getItem(STORAGE_DAILY_TASKS);
            var date  = localStorage.getItem(STORAGE_DAILY_DATE);
            var achs  = localStorage.getItem(STORAGE_ACHIEVEMENTS);
            var stats = localStorage.getItem(STORAGE_STATS);

            if (tasks) _dailyTasks = JSON.parse(tasks);
            if (date)  _dailyDate  = date;
            if (achs)  _unlockedIds = JSON.parse(achs);
            if (stats) _stats = JSON.parse(stats);
        } catch (e) {
            console.warn('[Quests] Failed to load:', e);
        }

        if (!_stats) _stats = defaultStats();
        if (!_unlockedIds) _unlockedIds = [];
    }

    // ── Shuffle Helper ──────────────────────────────────────────
    function shuffleArray(arr) {
        var a = arr.slice();
        for (var i = a.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var tmp = a[i];
            a[i] = a[j];
            a[j] = tmp;
        }
        return a;
    }

    // ── Generate Daily Tasks ────────────────────────────────────
    function generateDailyTasks() {
        var shuffled = shuffleArray(DAILY_TASK_POOL);
        var selected = shuffled.slice(0, DAILY_TASK_COUNT);
        var tasks = [];
        for (var i = 0; i < selected.length; i++) {
            tasks.push({
                id: selected[i].id,
                name: selected[i].name,
                desc: selected[i].desc,
                type: selected[i].type,
                target: selected[i].target,
                reward: selected[i].reward,
                progress: 0,
                completed: false,
                claimed: false
            });
        }
        return tasks;
    }

    // ── Initialize ──────────────────────────────────────────────
    function init() {
        load();

        var today = getKSTDateString();

        // Check if we need to reset daily tasks
        if (_dailyDate !== today) {
            _dailyTasks = generateDailyTasks();
            _dailyDate = today;

            // Track consecutive logins
            if (_stats.lastLoginDate) {
                var kst = getKSTDate();
                var yesterday = new Date(kst.getFullYear(), kst.getMonth(), kst.getDate() - 1);
                var yStr = yesterday.getFullYear() + '-' + ('0' + (yesterday.getMonth() + 1)).slice(-2) + '-' + ('0' + yesterday.getDate()).slice(-2);
                if (_stats.lastLoginDate === yStr) {
                    _stats.consecutiveLogins = (_stats.consecutiveLogins || 0) + 1;
                } else {
                    _stats.consecutiveLogins = 1;
                }
            } else {
                _stats.consecutiveLogins = 1;
            }
            _stats.lastLoginDate = today;

            save();
            console.log('[Quests] New daily tasks generated. Consecutive logins:', _stats.consecutiveLogins);
        }

        // Check achievements on init
        checkAchievements();

        // Create quest panel DOM
        createPanel();

        // Subscribe to game state changes for stat tracking
        subscribeToGameActions();

        console.log('[Quests] System initialized. Tasks today:', _dailyTasks.length, '| Achievements unlocked:', _unlockedIds.length);
    }

    // ── Daily Task Functions ────────────────────────────────────
    function getDailyTasks() {
        return _dailyTasks;
    }

    function progressTask(type, amount) {
        amount = amount || 1;
        var changed = false;

        for (var i = 0; i < _dailyTasks.length; i++) {
            var task = _dailyTasks[i];
            if (task.type === type && !task.completed) {
                task.progress = Math.min(task.progress + amount, task.target);
                if (task.progress >= task.target) {
                    task.completed = true;
                }
                changed = true;
            }
        }

        if (changed) {
            save();
            if (_isOpen) renderPanel();
        }

        return changed;
    }

    function claimTaskReward(taskId) {
        for (var i = 0; i < _dailyTasks.length; i++) {
            var task = _dailyTasks[i];
            if (task.id === taskId && task.completed && !task.claimed) {
                task.claimed = true;

                // Dispatch rewards to GameState
                if (window.GameState) {
                    var state = GameState.getState();
                    if (task.reward.money) {
                        GameState.dispatch({ type: 'UPDATE_MONEY', amount: state.farm.money + task.reward.money });
                    }
                    if (task.reward.exp) {
                        // Update farm exp
                        var newExp = (state.farm.exp || 0) + task.reward.exp;
                        var newLevel = state.farm.level || 1;
                        // Level up every 100 exp
                        while (newExp >= newLevel * 100) {
                            newExp -= newLevel * 100;
                            newLevel++;
                        }
                        state.farm.exp = newExp;
                        state.farm.level = newLevel;
                        GameState.dispatch({ type: 'LOAD_STATE', payload: { farm: state.farm } });
                    }
                    if (task.reward.affection && window.GameState.updateEmotionValues) {
                        GameState.updateEmotionValues('chayewoon', { affection: task.reward.affection });
                    }
                }

                // Show toast
                if (window.GameHUD) {
                    var rewardText = '';
                    if (task.reward.money) rewardText += ' \uD83D\uDCB0+' + task.reward.money;
                    if (task.reward.exp) rewardText += ' \u2B50+' + task.reward.exp;
                    if (task.reward.affection) rewardText += ' \u2764\uFE0F+' + task.reward.affection;
                    GameHUD.showToast('\u4EFB\u52A1\u5B8C\u6210\uFF01' + rewardText, 'success', 3000);
                }

                // v0.9: Play level up SFX on task reward claim
                if (window.GameAudio) {
                    GameAudio.playLevelUp();
                }

                // v1.2e: Haptic feedback on task reward claim
                if (window.GameMiniApp) GameMiniApp.hapticFeedback('success');

                save();
                if (_isOpen) renderPanel();
                return true;
            }
        }
        return false;
    }

    function isAllCompleted() {
        for (var i = 0; i < _dailyTasks.length; i++) {
            if (!_dailyTasks[i].claimed) return false;
        }
        return true;
    }

    function getResetCountdown() {
        var midnight = getKSTMidnightTimestamp();
        var now = Date.now();
        var remaining = Math.max(0, Math.floor((midnight - now) / 1000));
        return remaining;
    }

    function formatCountdown(seconds) {
        var h = Math.floor(seconds / 3600);
        var m = Math.floor((seconds % 3600) / 60);
        var s = seconds % 60;
        return ('0' + h).slice(-2) + ':' + ('0' + m).slice(-2) + ':' + ('0' + s).slice(-2);
    }

    // ── Achievement Functions ───────────────────────────────────
    function getAchievements() {
        var result = [];
        for (var i = 0; i < ACHIEVEMENTS.length; i++) {
            var ach = ACHIEVEMENTS[i];
            result.push({
                id: ach.id,
                name: ach.name,
                desc: ach.desc,
                icon: ach.icon,
                unlocked: _unlockedIds.indexOf(ach.id) !== -1
            });
        }
        return result;
    }

    function checkAchievements() {
        var newlyUnlocked = [];
        for (var i = 0; i < ACHIEVEMENTS.length; i++) {
            var ach = ACHIEVEMENTS[i];
            if (_unlockedIds.indexOf(ach.id) === -1) {
                try {
                    if (ach.condition(_stats)) {
                        _unlockedIds.push(ach.id);
                        newlyUnlocked.push(ach);
                    }
                } catch (e) {
                    console.warn('[Quests] Achievement condition error for', ach.id, e);
                }
            }
        }

        if (newlyUnlocked.length > 0) {
            save();
            // Show toast for each new achievement
            for (var j = 0; j < newlyUnlocked.length; j++) {
                showAchievementToast(newlyUnlocked[j]);
            }
        }

        return newlyUnlocked;
    }

    function showAchievementToast(ach) {
        if (!window.GameHUD) return;

        // v0.9: Play achievement SFX
        if (window.GameAudio) {
            GameAudio.playAchievement();
        }

        // Create a special achievement toast
        var container = document.getElementById('toast-container');
        if (!container) return;

        var toast = document.createElement('div');
        toast.className = 'achievement-toast';
        toast.innerHTML =
            '<span class="achievement-icon">' + ach.icon + '</span>' +
            '<span class="achievement-toast-text">' +
            '<span class="achievement-toast-label">\u6210\u5C31\u89E3\u9501</span>' +
            '<span class="achievement-toast-name">' + ach.name + '</span>' +
            '</span>';
        container.appendChild(toast);

        setTimeout(function () {
            toast.classList.add('achievement-toast-exit');
            setTimeout(function () { toast.remove(); }, 500);
        }, 4000);
    }

    function getUnlockedCount() {
        return _unlockedIds.length;
    }

    function getStats() {
        return _stats;
    }

    function updateStat(key, value) {
        if (!_stats.hasOwnProperty(key)) {
            console.warn('[Quests] Unknown stat key:', key);
            return;
        }

        var oldValue = _stats[key];

        if (typeof oldValue === 'number') {
            // Cumulative: only increase
            _stats[key] = Math.max(oldValue, oldValue + value);
        } else if (Array.isArray(oldValue)) {
            // For arrays like completedChapters, add if not present
            if (oldValue.indexOf(value) === -1) {
                oldValue.push(value);
            }
            _stats[key] = oldValue;
        }

        // Track max values
        if (key === 'maxAffection') {
            _stats.maxAffection = Math.max(_stats.maxAffection || 0, value);
        }
        if (key === 'maxHearts') {
            _stats.maxHearts = Math.max(_stats.maxHearts || 0, value);
        }

        save();
    }

    // ── Subscribe to Game Actions for Stat Tracking ─────────────
    function subscribeToGameActions() {
        if (!window.GameState) return;

        GameState.subscribe(function (state, prev, action) {
            switch (action.type) {
                case 'PLANT':
                    updateStat('totalPlants', 1);
                    progressTask('plant', 1);
                    checkAchievements();
                    break;

                case 'HARVEST':
                    updateStat('totalHarvests', 1);
                    progressTask('harvest', 1);
                    checkAchievements();
                    break;

                case 'WATER':
                    progressTask('water', 1);
                    break;

                case 'BUY_SEED':
                    progressTask('buy_seed', 1);
                    checkAchievements();
                    break;

                case 'SELL_CROP':
                    updateStat('totalEarned', action.earned || 0);
                    progressTask('sell', action.earned || 0);
                    checkAchievements();
                    break;

                case 'UPDATE_HEARTS':
                    if (action.hearts) {
                        updateStat('maxHearts', action.hearts);
                    }
                    checkAchievements();
                    break;

                case 'UPDATE_EMOTION_VALUES':
                    // Track max affection
                    if (action.characterId === 'chayewoon' && action.deltas && action.deltas.affection) {
                        var currentAffection = (state.emotionValues && state.emotionValues.chayewoon && state.emotionValues.chayewoon.affection) || 0;
                        updateStat('maxAffection', currentAffection);
                        checkAchievements();
                    }
                    break;
            }
        });

        // Also subscribe to dialogue events for chat tracking
        if (window.GameDialogue) {
            var origOpen = GameDialogue.open;
            if (origOpen) {
                // We track chats via a custom event approach
            }
        }
    }

    /**
     * Call this when player chats with NPC, takes selfie, or progresses story.
     * These actions are not directly in GameState reducer, so modules should call:
     *   GameQuests.onAction('chat', 1);
     *   GameQuests.onAction('selfie', 1);
     *   GameQuests.onAction('story', 1);
     */
    function onAction(type, amount) {
        amount = amount || 1;

        switch (type) {
            case 'chat':
                updateStat('totalChats', amount);
                progressTask('chat', amount);
                break;
            case 'selfie':
                updateStat('totalSelfies', amount);
                progressTask('selfie', amount);
                break;
            case 'story':
                progressTask('story', amount);
                break;
            default:
                progressTask(type, amount);
                break;
        }

        checkAchievements();
    }

    /**
     * Call this when a story chapter is completed
     */
    function onChapterComplete(chapterId) {
        updateStat('completedChapters', chapterId);
        checkAchievements();
    }

    // ── UI: Quest Panel ─────────────────────────────────────────
    function createPanel() {
        // Create panel element
        _panelEl = document.createElement('div');
        _panelEl.id = 'quest-panel';
        _panelEl.className = 'quest-panel';
        document.body.appendChild(_panelEl);
    }

    function openPanel() {
        if (!_panelEl) createPanel();

        // v1.2a: Close other panels via panel manager
        if (window.GamePanels) GamePanels.open('quests');

        _isOpen = true;
        renderPanel();
        _panelEl.classList.add('open');

        // Start countdown timer
        startCountdown();
    }

    function closePanel() {
        // v1.2a: Unregister from panel manager
        if (window.GamePanels) GamePanels.close('quests');
        _isOpen = false;
        if (_panelEl) _panelEl.classList.remove('open');
        stopCountdown();
    }

    function togglePanel() {
        if (_isOpen) {
            closePanel();
        } else {
            openPanel();
        }
    }

    function renderPanel() {
        if (!_panelEl) return;

        var html = '';

        // Header
        html += '<div class="quest-panel-header">';
        html += '<div class="quest-panel-title">\uD83D\uDCCB \u6BCF\u65E5\u4EFB\u52A1</div>';
        html += '<button class="quest-close-btn" onclick="GameQuests.closePanel()">&times;</button>';
        html += '</div>';

        // Countdown
        html += '<div class="quest-countdown">';
        html += '<span class="quest-countdown-label">\u91CD\u7F6E\u5012\u8BA1\u65F6</span>';
        html += '<span class="quest-countdown-time" id="quest-countdown-time">' + formatCountdown(getResetCountdown()) + '</span>';
        html += '</div>';

        // Task list
        html += '<div class="quest-task-list">';
        for (var i = 0; i < _dailyTasks.length; i++) {
            var task = _dailyTasks[i];
            var pct = Math.min(100, Math.floor((task.progress / task.target) * 100));
            var taskClass = 'quest-task';
            if (task.claimed) taskClass += ' claimed';
            else if (task.completed) taskClass += ' completed';

            html += '<div class="' + taskClass + '" data-task-id="' + task.id + '">';
            html += '<div class="quest-task-header">';
            html += '<span class="quest-task-name">' + task.name + '</span>';
            html += '<span class="quest-task-progress-text">' + task.progress + '/' + task.target + '</span>';
            html += '</div>';
            html += '<div class="quest-task-desc">' + task.desc + '</div>';

            // Progress bar
            html += '<div class="quest-progress">';
            html += '<div class="quest-progress-fill" style="width:' + pct + '%"></div>';
            html += '</div>';

            // Reward
            html += '<div class="quest-reward">';
            if (task.reward.money) html += '<span class="quest-reward-item">\uD83D\uDCB0 ' + task.reward.money + '</span>';
            if (task.reward.exp) html += '<span class="quest-reward-item">\u2B50 ' + task.reward.exp + '</span>';
            if (task.reward.affection) html += '<span class="quest-reward-item">\u2764\uFE0F ' + task.reward.affection + '</span>';
            html += '</div>';

            // Claim button
            if (task.completed && !task.claimed) {
                html += '<button class="quest-claim-btn" onclick="GameQuests.claimTaskReward(\'' + task.id + '\')">\u9886\u53D6\u5956\u52B1</button>';
            } else if (task.claimed) {
                html += '<span class="quest-claimed-label">\u2714 \u5DF2\u9886\u53D6</span>';
            }

            html += '</div>';
        }
        html += '</div>';

        // Achievement section
        html += '<div class="quest-achievement-header">';
        html += '<span>\uD83C\uDFC6 \u6210\u5C31 (' + _unlockedIds.length + '/' + ACHIEVEMENTS.length + ')</span>';
        html += '</div>';

        html += '<div class="quest-achievement-list">';
        for (var j = 0; j < ACHIEVEMENTS.length; j++) {
            var ach = ACHIEVEMENTS[j];
            var isUnlocked = _unlockedIds.indexOf(ach.id) !== -1;
            var achClass = 'quest-achievement-item';
            if (isUnlocked) achClass += ' unlocked';

            html += '<div class="' + achClass + '" title="' + ach.desc + '">';
            html += '<span class="quest-achievement-icon' + (isUnlocked ? '' : ' locked') + '">' + (isUnlocked ? ach.icon : '\uD83D\uDD12') + '</span>';
            html += '<span class="quest-achievement-name">' + ach.name + '</span>';
            html += '</div>';
        }
        html += '</div>';

        _panelEl.innerHTML = html;
    }

    // ── Countdown Timer ─────────────────────────────────────────
    function startCountdown() {
        stopCountdown();
        updateCountdownDisplay();
        _countdownTimer = setInterval(updateCountdownDisplay, 1000);
    }

    function stopCountdown() {
        if (_countdownTimer) {
            clearInterval(_countdownTimer);
            _countdownTimer = null;
        }
    }

    function updateCountdownDisplay() {
        var el = document.getElementById('quest-countdown-time');
        if (el) {
            el.textContent = formatCountdown(getResetCountdown());
        }
    }

    // ── Export ──────────────────────────────────────────────────
    window.GameQuests = {
        init: init,
        // Daily tasks
        getDailyTasks: getDailyTasks,
        progressTask: progressTask,
        claimTaskReward: claimTaskReward,
        isAllCompleted: isAllCompleted,
        getResetCountdown: getResetCountdown,
        // Achievements
        getAchievements: getAchievements,
        checkAchievements: checkAchievements,
        getUnlockedCount: getUnlockedCount,
        getStats: getStats,
        updateStat: updateStat,
        // Action hooks (for modules to call)
        onAction: onAction,
        onChapterComplete: onChapterComplete,
        // UI
        openPanel: openPanel,
        closePanel: closePanel,
        togglePanel: togglePanel,
        // Persistence
        save: save,
        load: load
    };
})();
