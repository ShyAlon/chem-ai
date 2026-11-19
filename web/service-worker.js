const cacheName = 'homechem-' + __BUILD_ID__;
const shell = __APP_SHELL__;

self.addEventListener('install', event => {
  event.waitUntil(caches.open(cacheName).then(cache => cache.addAll(shell)));
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(
    keys.filter(key => key.startsWith('homechem-') && key !== cacheName).map(key => caches.delete(key)),
  )));
});

self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (url.pathname === '/api/catalog') {
    event.respondWith(caches.open(cacheName).then(async cache => {
      try {
        const response = await fetch(request);
        if (response.ok) await cache.put(request, response.clone());
        return response;
      } catch {
        return await cache.match(request) || new Response('Catalog unavailable', { status: 503 });
      }
    }));
    return;
  }
  if (url.pathname.startsWith('/api/') || url.pathname === '/mcp') return;
  if (request.mode === 'navigate') {
    event.respondWith(caches.open(cacheName).then(cache => cache.match('/')).then(saved => saved || fetch(request)));
  } else if (shell.includes(url.pathname)) {
    event.respondWith(caches.open(cacheName).then(cache => cache.match(url.pathname, { ignoreVary: true })).then(saved => saved || fetch(request)));
  }
});
