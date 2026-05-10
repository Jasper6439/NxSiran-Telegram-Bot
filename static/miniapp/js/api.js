/**
 * NxSiran Mini App - API Wrapper Module
 * Provides a centralized API client with authentication and error handling.
 */
(function () {
    'use strict';

    // ===== API Base URL Detection =====
    var API_BASE = '__API_BASE__';

    // ===== Auth Token =====
    function getToken() {
        return localStorage.getItem('auth_token') || '';
    }

    function setToken(token) {
        localStorage.setItem('auth_token', token);
    }

    function clearToken() {
        localStorage.removeItem('auth_token');
    }

    // ===== Auth Headers =====
    function authHeaders() {
        var headers = {};
        var token = getToken();
        if (token) {
            headers['Authorization'] = 'Bearer ' + token;
        }
        return headers;
    }

    // ===== Core Request Method =====
    function request(method, path, options) {
        options = options || {};
        var url = API_BASE + path;
        var headers = Object.assign({}, authHeaders(), options.headers || {});

        var fetchOptions = {
            method: method,
            headers: headers
        };

        if (options.body) {
            if (options.body instanceof FormData) {
                fetchOptions.body = options.body;
                // Don't set Content-Type for FormData; browser sets boundary automatically
            } else {
                headers['Content-Type'] = 'application/json';
                fetchOptions.body = JSON.stringify(options.body);
            }
        }

        return fetch(url, fetchOptions)
            .then(function (response) {
                // Get text first to handle BOM and other issues
                return response.text().then(function (text) {
                    // Strip UTF-8 BOM if present (EF BB BF or \uFEFF)
                    var cleanText = text.replace(/^\uFEFF/, '').replace(/^\xEF\xBB\xBF/, '');
                    
                    // Try to parse JSON
                    var data;
                    try {
                        data = JSON.parse(cleanText);
                    } catch (parseError) {
                        console.error('[API] JSON parse error:', parseError.message);
                        console.error('[API] Response preview:', cleanText.substring(0, 100));
                        
                        // Return a friendly error object instead of throwing
                        return {
                            success: false,
                            error: '服务器响应格式错误，请稍后重试',
                            _parseError: true,
                            _rawPreview: cleanText.substring(0, 100)
                        };
                    }
                    
                    // Check HTTP status
                    if (!response.ok) {
                        var errMsg = (data && (data.error || data.message)) || '请求失败 (' + response.status + ')';
                        throw new Error(errMsg);
                    }
                    
                    return data;
                });
            })
            .catch(function (error) {
                // Don't show toast for parse errors (already handled)
                if (error.message && error.message.indexOf('服务器响应格式错误') !== -1) {
                    throw error;
                }
                
                // Show toast on API errors
                if (window.Toast && window.Toast.show) {
                    window.Toast.show(error.message || '网络错误', 'error');
                }
                throw error;
            });
    }

    // ===== Namespaced API Methods =====
    var API = {
        _base: API_BASE,
        _getToken: getToken,
        _setToken: setToken,
        _clearToken: clearToken,
        _authHeaders: authHeaders,
        _request: request,

        auth: {
            login: function (username, password) {
                return request('POST', '/api/login', {
                    body: { username: username, password: password }
                });
            },
            register: function (username, password, chatId) {
                return request('POST', '/api/register', {
                    body: { username: username, password: password, chat_id: chatId }
                });
            }
        },

        farm: {
            get: function () {
                return request('GET', '/api/game/farm');
            },
            plant: function (x, y, type) {
                return request('POST', '/api/game/plant', {
                    body: { x: x, y: y, crop_type: type }
                });
            },
            harvest: function (x, y) {
                return request('POST', '/api/game/harvest', {
                    body: { x: x, y: y }
                });
            },
            sell: function (type, qty) {
                return request('POST', '/api/game/sell', {
                    body: { crop_type: type, quantity: qty || 1 }
                });
            },
            buySeed: function (type, qty) {
                return request('POST', '/api/game/buy-seed', {
                    body: { crop_type: type, quantity: qty || 1 }
                });
            }
        },

        character: {
            location: function () {
                return request('GET', '/api/game/character/location');
            },
            relationship: function () {
                return request('GET', '/api/game/relationship');
            },
            chat: function (message) {
                return request('POST', '/api/game/chat', {
                    body: { message: message }
                });
            },
            gift: function (type, id) {
                return request('POST', '/api/game/gift', {
                    body: { item_type: type, item_id: id }
                });
            }
        },

        events: {
            heart: function () {
                return request('GET', '/api/game/events/heart');
            },
            trigger: function (id) {
                return request('POST', '/api/game/events/trigger', {
                    body: { event_id: id }
                });
            }
        },

        recipes: {
            get: function () {
                return request('GET', '/api/game/recipes');
            }
        },

        cook: function (recipeId) {
            return request('POST', '/api/game/cook', {
                body: { recipe_id: recipeId }
            });
        },

        daily: {
            check: function () {
                return request('GET', '/api/game/daily/check');
            },
            claim: function () {
                return request('POST', '/api/game/daily/claim');
            }
        },

        quota: {
            get: function () {
                return request('GET', '/api/quota');
            }
        },

        skills: {
            list: function (characterId) {
                var query = characterId ? '?character_id=' + characterId : '';
                return request('GET', '/api/skills' + query);
            },
            toggle: function (id, enabled, characterId) {
                return request('POST', '/api/skills/toggle', {
                    body: { skill_id: id, enabled: enabled, character_id: characterId || '' }
                });
            },
            install: function (name) {
                return request('POST', '/api/skills/install', {
                    body: { skill_name: name }
                });
            },
            uninstall: function (id) {
                return request('POST', '/api/skills/uninstall', {
                    body: { skill_id: id }
                });
            }
        },

        config: {
            get: function () {
                return request('GET', '/api/config');
            },
            set: function (data) {
                return request('POST', '/api/config', {
                    body: data
                });
            }
        },

        selfies: {
            list: function (characterId) {
                var query = characterId ? '?character_id=' + characterId : '';
                return request('GET', '/api/selfies' + query);
            },
            upload: function (formData) {
                return request('POST', '/api/upload-selfies', {
                    body: formData
                });
            },
            uploadJSON: function (photos) {
                return request('POST', '/api/upload-selfies', {
                    body: { photos: photos }
                });
            },
            delete: function (filename) {
                return request('POST', '/api/delete-selfie', {
                    body: { filename: filename }
                });
            }
        },

        stats: {
            get: function () {
                return request('GET', '/api/stats');
            }
        },

        characters: {
            list: function () {
                return request('GET', '/api/characters');
            },
            switch: function (characterId) {
                return request('POST', '/api/characters/switch', {
                    body: { character_id: characterId }
                });
            }
        },

        chatlog: {
            analyze: function (content, partner) {
                return request('POST', '/api/analyze-chatlog', {
                    body: { content: content, partner: partner }
                });
            }
        },

        video: {
            analyze: function (formData) {
                return request('POST', '/api/analyze-video', {
                    body: formData
                });
            }
        }
    };

    // ===== Export =====
    window.API = API;
})();
