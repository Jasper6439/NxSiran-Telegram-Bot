/**
 * NxSiran Game - Weather System
 * Visual weather effects + game mechanics
 */
(function () {
    'use strict';

    var _weatherEl = null;
    var _currentEffect = null;

    function init() {
        _weatherEl = document.getElementById('weather-effects');
    }

    function setWeather(weather) {
        GameState.dispatch({ type: 'UPDATE_WEATHER', weather: weather });
        updateVisual(weather);
    }

    function updateVisual(weather) {
        if (!_weatherEl) return;

        // Remove existing effects
        _weatherEl.innerHTML = '';
        _weatherEl.className = 'weather-effects';

        switch (weather) {
            case 'rainy':
                _weatherEl.classList.add('weather-rain');
                createRainDrops();
                break;
            case 'snowy':
                _weatherEl.classList.add('weather-snow');
                createSnowflakes();
                break;
            case 'sunny':
            default:
                break;
        }
    }

    function createRainDrops() {
        if (!_weatherEl) return;
        for (var i = 0; i < 50; i++) {
            var drop = document.createElement('div');
            drop.className = 'rain-drop';
            drop.style.left = (Math.random() * 100) + '%';
            drop.style.animationDelay = (Math.random() * 2) + 's';
            drop.style.animationDuration = (0.5 + Math.random() * 0.5) + 's';
            _weatherEl.appendChild(drop);
        }
    }

    function createSnowflakes() {
        if (!_weatherEl) return;
        for (var i = 0; i < 30; i++) {
            var flake = document.createElement('div');
            flake.className = 'snow-flake';
            flake.style.left = (Math.random() * 100) + '%';
            flake.style.animationDelay = (Math.random() * 5) + 's';
            flake.style.animationDuration = (3 + Math.random() * 4) + 's';
            flake.style.fontSize = (8 + Math.random() * 12) + 'px';
            _weatherEl.appendChild(flake);
        }
    }

    function randomWeather() {
        var weathers = ['sunny', 'sunny', 'sunny', 'cloudy', 'rainy'];
        var w = weathers[Math.floor(Math.random() * weathers.length)];
        setWeather(w);
    }

    window.GameWeather = {
        init: init,
        setWeather: setWeather,
        updateVisual: updateVisual,
        randomWeather: randomWeather
    };
})();
