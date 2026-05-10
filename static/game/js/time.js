/**
 * NxSiran Game - Time System
 * Game day/night cycle, seasons, crop growth timing
 */
(function () {
    'use strict';

    var _gameTickInterval = null;
    var TICK_MS = 1000; // 1 second per tick

    function init() {
        // Start game tick
        _gameTickInterval = setInterval(tick, TICK_MS);
    }

    function tick() {
        var state = GameState.getState();
        if (state.status !== 'playing') return;

        // Update crop growth
        GameState.dispatch({ type: 'TICK' });

        // Re-render crops that changed
        if (window.GameRenderer) {
            GameRenderer.renderCrops(GameState.getState().crops);
        }
    }

    function getGameTime() {
        var state = GameState.getState();
        return {
            day: state.gameDay,
            season: state.season,
            weather: state.weather
        };
    }

    function advanceDay() {
        var state = GameState.getState();
        var seasons = ['spring', 'summer', 'autumn', 'winter'];
        var seasonIdx = seasons.indexOf(state.season);
        var newDay = state.gameDay + 1;

        // Season changes every 7 days
        if (newDay % 28 === 0) {
            seasonIdx = (seasonIdx + 1) % 4;
            GameState.dispatch({ type: 'LOAD_STATE', payload: { season: seasons[seasonIdx] } });
        }

        GameState.dispatch({ type: 'LOAD_STATE', payload: { gameDay: newDay } });
    }

    function destroy() {
        clearInterval(_gameTickInterval);
    }

    window.GameTime = {
        init: init,
        tick: tick,
        getGameTime: getGameTime,
        advanceDay: advanceDay,
        destroy: destroy
    };
})();
