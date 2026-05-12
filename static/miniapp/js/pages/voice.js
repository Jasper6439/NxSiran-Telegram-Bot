/**
 * NxSiran Mini App - Voice Page Module
 * v1.4.7.3 - 声音克隆语料上传
 */
(function () {
    'use strict';

    var currentCharacterId = 'chayewoon';

    /**
     * Initialize the voice page.
     */
    function init() {
        setupUploadArea();
    }

    /**
     * Called when the voice page is entered.
     */
    function onPageEnter() {
        loadStatus();
    }

    /**
     * Update the character ID.
     */
    function setCharacterId(characterId) {
        currentCharacterId = characterId || 'chayewoon';
    }

    // ===== Setup Upload Area =====
    function setupUploadArea() {
        var uploadArea = document.getElementById('voice-upload-area');
        var fileInput = document.getElementById('voice-file-input');

        if (!uploadArea || !fileInput) return;

        // Click to upload
        uploadArea.addEventListener('click', function () {
            fileInput.click();
        });

        // File selected
        fileInput.addEventListener('change', function (e) {
            var files = e.target.files;
            if (files.length > 0) {
                uploadFiles(files);
            }
        });

        // Drag and drop
        uploadArea.addEventListener('dragover', function (e) {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', function (e) {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
        });

        uploadArea.addEventListener('drop', function (e) {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            var files = e.dataTransfer.files;
            if (files.length > 0) {
                uploadFiles(files);
            }
        });
    }

    // ===== Upload Files =====
    function uploadFiles(files) {
        var uploadArea = document.getElementById('voice-upload-area');
        uploadArea.classList.add('uploading');

        var uploadPromises = [];
        for (var i = 0; i < files.length; i++) {
            uploadPromises.push(uploadSingleFile(files[i]));
        }

        Promise.all(uploadPromises).then(function (results) {
            var successCount = results.filter(function (r) { return r.success; }).length;
            if (successCount > 0) {
                window.Toast.show('上传成功 ' + successCount + ' 个文件', 'success');
                loadStatus();
            }
            uploadArea.classList.remove('uploading');
        }).catch(function (error) {
            console.error('Upload error:', error);
            window.Toast.show('上传失败', 'error');
            uploadArea.classList.remove('uploading');
        });
    }

    function uploadSingleFile(file) {
        return new Promise(function (resolve, reject) {
            var formData = new FormData();
            formData.append('audio', file);
            formData.append('character_id', currentCharacterId);

            fetch('/api/upload-voice-sample', {
                method: 'POST',
                body: formData
            })
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    resolve(data);
                })
                .catch(function (error) {
                    reject(error);
                });
        });
    }

    // ===== Load Status =====
    function loadStatus() {
        fetch('/api/voice-samples?character_id=' + currentCharacterId)
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.success) {
                    updateUI(data);
                } else {
                    window.Toast.show('加载状态失败', 'error');
                }
            })
            .catch(function (error) {
                console.error('Load status error:', error);
                window.Toast.show('加载状态失败', 'error');
            });
    }

    // ===== Update UI =====
    function updateUI(data) {
        var countEl = document.getElementById('voice-count');
        var badgeEl = document.getElementById('voice-samples-count');
        var trainedEl = document.getElementById('voice-trained');
        var trainBtn = document.getElementById('voice-train-btn');
        var listEl = document.getElementById('voice-samples-list');

        if (countEl) countEl.textContent = data.samples_count;
        if (badgeEl) badgeEl.textContent = data.samples_count + '/' + data.min_required;
        if (trainedEl) trainedEl.textContent = data.trained ? '已训练' : '未训练';

        // Enable/disable train button
        if (trainBtn) {
            trainBtn.disabled = !data.ready_to_train;
            if (data.trained) {
                trainBtn.textContent = '重新训练';
            } else {
                trainBtn.textContent = '开始训练';
            }
        }

        // Update samples list
        if (listEl && data.samples && data.samples.length > 0) {
            listEl.innerHTML = data.samples.map(function (sample) {
                return '<div class="voice-sample-item">' +
                    '<span class="sample-name">' + sample + '</span>' +
                    '<button class="btn-icon" onclick="VoicePage.deleteSample(\'' + sample + '\')">' +
                    '<svg viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>' +
                    '</button>' +
                    '</div>';
            }).join('');
        } else if (listEl) {
            listEl.innerHTML = '<div class="empty-state"><div class="empty-state-text">还没有上传语料</div></div>';
        }
    }

    // ===== Delete Sample =====
    function deleteSample(filename) {
        if (!confirm('确定要删除这个语料吗？')) return;

        fetch('/api/delete-voice-sample', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: filename,
                character_id: currentCharacterId
            })
        })
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.success) {
                    window.Toast.show('已删除', 'success');
                    loadStatus();
                } else {
                    window.Toast.show('删除失败', 'error');
                }
            })
            .catch(function (error) {
                console.error('Delete error:', error);
                window.Toast.show('删除失败', 'error');
            });
    }

    // ===== Start Training =====
    function startTraining() {
        var trainBtn = document.getElementById('voice-train-btn');
        if (trainBtn) {
            trainBtn.disabled = true;
            trainBtn.textContent = '启动中...';
        }

        fetch('/api/start-voice-training', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ character_id: currentCharacterId })
        })
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.success) {
                    window.Toast.show('训练已启动，预计30分钟完成', 'success');
                    if (trainBtn) {
                        trainBtn.textContent = '训练中...';
                    }
                } else {
                    window.Toast.show(data.error || '启动失败', 'error');
                    if (trainBtn) {
                        trainBtn.disabled = false;
                        trainBtn.textContent = '开始训练';
                    }
                }
            })
            .catch(function (error) {
                console.error('Start training error:', error);
                window.Toast.show('启动失败', 'error');
                if (trainBtn) {
                    trainBtn.disabled = false;
                    trainBtn.textContent = '开始训练';
                }
            });
    }

    // ===== Export =====
    window.VoicePage = {
        init: init,
        onPageEnter: onPageEnter,
        loadStatus: loadStatus,
        deleteSample: deleteSample,
        startTraining: startTraining,
        setCharacterId: setCharacterId
    };
})();
