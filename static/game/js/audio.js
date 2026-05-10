/**
 * NxSiran Game - Audio Manager
 * Simple Web Audio API wrapper for game sounds
 */
(function () {
    'use strict';

    var _ctx = null;
    var _enabled = true;
    var _volume = 0.3;

    function init() {
        try {
            _ctx = new (window.AudioContext || window.webkitAudioContext)();
        } catch (e) {
            console.warn('[Audio] Web Audio not supported');
        }
    }

    function getContext() {
        if (!_ctx) init();
        if (_ctx && _ctx.state === 'suspended') {
            _ctx.resume();
        }
        return _ctx;
    }

    function playTone(frequency, duration, type) {
        if (!_enabled) return;
        var ctx = getContext();
        if (!ctx) return;

        var osc = ctx.createOscillator();
        var gain = ctx.createGain();
        osc.type = type || 'sine';
        osc.frequency.value = frequency;
        gain.gain.value = _volume;
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + duration);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + duration);
    }

    function playPlant() { playTone(440, 0.15, 'sine'); setTimeout(function () { playTone(554, 0.15, 'sine'); }, 100); }
    function playHarvest() { playTone(523, 0.1, 'sine'); setTimeout(function () { playTone(659, 0.1, 'sine'); }, 80); setTimeout(function () { playTone(784, 0.2, 'sine'); }, 160); }
    function playWater() { playTone(300, 0.2, 'sine'); }
    function playBuy() { playTone(600, 0.1, 'square'); setTimeout(function () { playTone(800, 0.15, 'square'); }, 100); }
    function playSell() { playTone(800, 0.1, 'square'); setTimeout(function () { playTone(600, 0.15, 'square'); }, 100); }
    function playError() { playTone(200, 0.3, 'sawtooth'); }
    function playClick() { playTone(1000, 0.05, 'sine'); }

    function setEnabled(enabled) { _enabled = enabled; }
    function setVolume(v) { _volume = Math.max(0, Math.min(1, v)); }
    function isEnabled() { return _enabled; }

    window.GameAudio = {
        init: init,
        playTone: playTone,
        playPlant: playPlant,
        playHarvest: playHarvest,
        playWater: playWater,
        playBuy: playBuy,
        playSell: playSell,
        playError: playError,
        playClick: playClick,
        setEnabled: setEnabled,
        setVolume: setVolume,
        isEnabled: isEnabled
    };
})();
