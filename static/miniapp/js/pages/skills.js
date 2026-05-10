/**
 * NxSiran Mini App - Skills Page Module
 * Loads skills list, toggle on/off, install/uninstall skills.
 */
(function () {
    'use strict';

    /**
     * Initialize the skills page.
     */
    function init() {
        setupInstallInput();
    }

    /**
     * Called when the skills page is entered.
     */
    function onPageEnter() {
        loadSkills();
    }

    // ===== Load Skills =====
    function loadSkills() {
        var listDiv = document.getElementById('skills-list');
        var loadingDiv = document.getElementById('skills-loading');
        if (!listDiv) return;

        if (loadingDiv) loadingDiv.classList.add('active');
        listDiv.innerHTML = '';

        var characterId = '';
        // Try to get current character ID from settings
        var charItems = document.querySelectorAll('.character-item.active');
        if (charItems.length > 0) {
            characterId = charItems[0].getAttribute('data-char-id') || '';
        }

        window.API.skills.list(characterId).then(function (data) {
            var skills = data.skills || [];

            if (skills.length === 0) {
                listDiv.innerHTML = '<div class="skills-empty">' +
                    '<div class="skills-empty-icon">' +
                    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>' +
                    '</div>' +
                    '<div class="skills-empty-text">\u8FD8\u6CA1\u6709\u5B89\u88C5\u4EFB\u4F55\u6280\u80FD</div></div>';
                return;
            }

            // Group by category
            var grouped = {};
            skills.forEach(function (skill) {
                var cat = skill.category || '\u5176\u4ED6';
                if (!grouped[cat]) grouped[cat] = [];
                grouped[cat].push(skill);
            });

            var esc = window.App ? window.App.escapeHtml : function (s) { return s; };
            var escJs = window.App ? window.App.escapeJs : function (s) { return s; };
            var isAdmin = window.Auth && window.Auth.isAdmin;

            var html = '';
            var categories = Object.keys(grouped).sort();
            categories.forEach(function (cat) {
                html += '<div class="skill-category-title">' + esc(cat) + '</div>';
                grouped[cat].forEach(function (skill) {
                    var skillId = skill.id || skill.name || '';
                    var skillName = skill.name || '\u672A\u77E5\u6280\u80FD';
                    var skillDesc = skill.description || skill.desc || '';
                    var skillVersion = skill.version ? 'v' + skill.version : '';
                    var enabled = skill.enabled !== false;

                    html += '<div class="skill-card">';
                    html += '  <div class="skill-card-header">';
                    html += '    <div class="skill-card-info">';
                    html += '      <div class="skill-card-name">';
                    html += '        ' + esc(skillName);
                    if (skillVersion) {
                        html += '        <span class="skill-version">' + esc(skillVersion) + '</span>';
                    }
                    html += '      </div>';
                    if (skillDesc) {
                        html += '    <div class="skill-card-desc" title="' + esc(skillDesc) + '">' + esc(skillDesc) + '</div>';
                    }
                    html += '    </div>';
                    html += '    <div class="skill-card-actions">';
                    if (isAdmin) {
                        html += '      <label class="toggle">';
                        html += '        <input type="checkbox" data-skill-id="' + escJs(skillId) + '"' + (enabled ? ' checked' : '') + '>';
                        html += '        <span class="toggle-track"></span>';
                        html += '      </label>';
                        html += '      <button class="btn-danger" data-skill-id="' + escJs(skillId) + '">\u5378\u8F7D</button>';
                    } else {
                        html += '      <span style="font-size:0.8rem;color:' + (enabled ? 'var(--success)' : 'var(--text-muted)') + '">' + (enabled ? '\u5DF2\u542F\u7528' : '\u5DF2\u7981\u7528') + '</span>';
                    }
                    html += '    </div>';
                    html += '  </div>';
                    html += '</div>';
                });
            });

            listDiv.innerHTML = html;

            // Bind toggle events
            listDiv.querySelectorAll('.toggle input').forEach(function (input) {
                input.addEventListener('change', function () {
                    var skillId = this.getAttribute('data-skill-id');
                    toggleSkill(skillId, this.checked);
                });
            });

            // Bind uninstall events
            listDiv.querySelectorAll('.btn-danger').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var skillId = this.getAttribute('data-skill-id');
                    uninstallSkill(skillId);
                });
            });
        }).catch(function (error) {
            console.error('Load skills error:', error);
            var esc = window.App ? window.App.escapeHtml : function (s) { return s; };
            // Don't show technical error to user
            var userMessage = '\u52A0\u8F7D\u5931\u8D25\uFF0C\u8BF7\u7A0D\u540E\u91CD\u8BD5';
            if (error.message && error.message.indexOf('\u670D\u52A1\u5668\u54CD\u5E94\u683C\u5F0F\u9519\u8BEF') !== -1) {
                userMessage = '\u670D\u52A1\u5668\u54CD\u5E94\u5F02\u5E38\uFF0C\u8BF7\u7A0D\u540E\u91CD\u8BD5';
            }
            listDiv.innerHTML = '<div class="skills-empty">' +
                '<div class="skills-empty-icon">' +
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>' +
                '</div>' +
                '<div class="skills-empty-text">' + userMessage + '</div>' +
                '<button class="btn-secondary" style="margin-top:12px" onclick="SkillsPage.loadSkills()">\u91CD\u8BD5</button>' +
                '</div>';
        }).finally(function () {
            if (loadingDiv) loadingDiv.classList.remove('active');
        });
    }

    // ===== Toggle Skill =====
    function toggleSkill(skillId, enabled) {
        var characterId = '';
        var charItems = document.querySelectorAll('.character-item.active');
        if (charItems.length > 0) {
            characterId = charItems[0].getAttribute('data-char-id') || '';
        }

        window.API.skills.toggle(skillId, enabled, characterId).then(function (result) {
            if (result.success) {
                window.Toast.show(enabled ? '\u5DF2\u542F\u7528' : '\u5DF2\u7981\u7528', 'success');
            } else {
                window.Toast.show(result.error || '\u64CD\u4F5C\u5931\u8D25', 'error');
                loadSkills();
            }
        }).catch(function () {
            window.Toast.show('\u64CD\u4F5C\u5931\u8D25', 'error');
            loadSkills();
        });
    }

    // ===== Install Skill =====
    function setupInstallInput() {
        var input = document.getElementById('skill-name-input');
        var btn = document.getElementById('install-skill-btn');
        if (!input || !btn) return;

        // Remove inline onclick
        btn.removeAttribute('onclick');
        btn.addEventListener('click', installSkillFromInput);

        // Enter key
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                installSkillFromInput();
            }
        });
    }

    function installSkillFromInput() {
        var input = document.getElementById('skill-name-input');
        var btn = document.getElementById('install-skill-btn');
        if (!input || !btn) return;

        var skillName = input.value.trim();
        if (!skillName) {
            window.Toast.show('\u8BF7\u8F93\u5165\u6280\u80FD\u540D\u79F0', 'error');
            return;
        }

        btn.disabled = true;
        btn.textContent = '\u5B89\u88C5\u4E2D...';

        window.API.skills.install(skillName).then(function (result) {
            if (result.success) {
                window.Toast.show('\u5DF2\u5B89\u88C5: ' + skillName, 'success');
                input.value = '';
                loadSkills();
            } else {
                window.Toast.show(result.error || '\u5B89\u88C5\u5931\u8D25', 'error');
            }
        }).catch(function () {
            window.Toast.show('\u5B89\u88C5\u5931\u8D25\uFF0C\u8BF7\u68C0\u67E5\u7F51\u7EDC', 'error');
        }).finally(function () {
            btn.disabled = false;
            btn.textContent = '\u5B89\u88C5';
        });
    }

    // ===== Uninstall Skill =====
    function uninstallSkill(skillId) {
        if (!confirm('\u786E\u5B9A\u8981\u5378\u8F7D\u8FD9\u4E2A\u6280\u80FD\u5417\uFF1F')) return;

        window.API.skills.uninstall(skillId).then(function (result) {
            if (result.success) {
                window.Toast.show('\u5DF2\u5378\u8F7D', 'success');
                loadSkills();
            } else {
                window.Toast.show(result.error || '\u5378\u8F7D\u5931\u8D25', 'error');
            }
        }).catch(function () {
            window.Toast.show('\u5378\u8F7D\u5931\u8D25', 'error');
        });
    }

    // ===== Export =====
    window.SkillsPage = {
        init: init,
        onPageEnter: onPageEnter,
        loadSkills: loadSkills
    };
})();
