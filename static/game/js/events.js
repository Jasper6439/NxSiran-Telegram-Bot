/**
 * NxSiran Game - Heart Events System
 */
(function () {
    'use strict';

    var _eventModalEl = null;

    function init() {
        _eventModalEl = document.getElementById('event-modal');
    }

    function checkEvents() {
        if (!window.GameAPI) return;
        GameAPI.checkHeartEvents().then(function (data) {
            if (data && data.events && data.events.length > 0) {
                if (window.GameHUD) GameHUD.showEventHint(true);
            }
        }).catch(function () {});
    }

    function triggerEvent(eventId) {
        if (!window.GameAPI) return;
        GameAPI.triggerHeartEvent(eventId).then(function (data) {
            if (data && data.event) {
                showEventModal(data.event);
            }
        }).catch(function () {});
    }

    function showEventModal(event) {
        if (!_eventModalEl) return;
        var html = '<div class="event-modal-content">';
        html += '<h3>' + (event.title || '\u5FC3\u7EA7\u4E8B\u4EF6') + '</h3>';
        html += '<p class="event-desc">' + (event.description || '') + '</p>';

        if (event.dialogue && event.dialogue.length > 0) {
            html += '<div class="event-dialogue">';
            for (var i = 0; i < event.dialogue.length; i++) {
                var line = event.dialogue[i];
                html += '<div class="event-line">';
                html += '<span class="event-speaker">' + (line.speaker || '') + ':</span> ';
                html += '<span class="event-text">' + (line.text || '') + '</span>';
                html += '</div>';
            }
            html += '</div>';
        }

        html += '<button class="btn-event-close" onclick="GameEvents.closeModal()">\u7EE7\u7EED</button>';
        html += '</div>';
        _eventModalEl.innerHTML = html;
        _eventModalEl.classList.add('open');
    }

    function closeModal() {
        if (_eventModalEl) _eventModalEl.classList.remove('open');
    }

    window.GameEvents = {
        init: init,
        checkEvents: checkEvents,
        triggerEvent: triggerEvent,
        showEventModal: showEventModal,
        closeModal: closeModal
    };
})();
