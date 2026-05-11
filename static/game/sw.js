const CACHE_NAME = 'nxsiran-game-v1.2';
const ASSETS = [
  '/static/game/',
  '/static/game/index.html',
  '/static/game/css/game.css',
  '/static/game/js/auth.js',
  '/static/game/js/api.js',
  '/static/game/js/state.js',
  '/static/game/js/main.js',
  '/static/game/js/renderer.js',
  '/static/game/js/inventory.js',
  '/static/game/js/dialogue.js',
  '/static/game/js/story_data.js',
  '/static/game/js/story.js',
  '/static/game/js/quests.js',
  '/static/game/js/events_seasonal.js',
  '/static/game/js/schedule.js',
  '/static/game/js/audio.js',
  '/static/game/js/tutorial.js',
  '/static/game/js/settings.js',
  '/static/game/js/weather.js',
  '/static/game/js/time.js',
  '/static/game/js/sync.js',
  '/static/game/js/emotion.js',
  '/static/game/js/npc.js',
  '/static/game/manifest.json',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
  ));
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  if (e.request.url.includes('/api/')) return; // Don't cache API calls
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request).then(response => {
      if (response.status === 200) {
        const clone = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(e.request, clone));
      }
      return response;
    }).catch(() => caches.match('/static/game/index.html')))
  );
});
