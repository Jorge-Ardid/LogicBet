const CACHE = "logicbet-v3";
const SHELL = [
  "/", "/static/js/app.js", "/static/js/views.js", "/static/css/app.css",
  "/static/manifest.json", "/static/icons/icon-192.png", "/static/icons/icon-512.png"
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET") return;
  if (url.pathname.startsWith("/api/")) {
    e.respondWith(
      fetch(e.request).catch(() =>
        new Response(JSON.stringify({ error: "offline" }), {
          status: 503, headers: { "Content-Type": "application/json" }
        })
      )
    );
    return;
  }
  /* будь-яка навігація (/ , /bet/...) — завжди свіжа з мережі, кеш лише offline-fallback */
  if (e.request.mode === "navigate") {
    e.respondWith(
      fetch(e.request)
        .then((resp) => {
          const clone = resp.clone();
          caches.open(CACHE).then((c) => c.put("/", clone));
          return resp;
        })
        .catch(() => caches.match("/"))
    );
    return;
  }
  e.respondWith(
    caches.match(e.request).then((hit) =>
      hit || fetch(e.request).then((resp) => {
        if (resp.ok && url.origin === self.location.origin) {
          const clone = resp.clone();
          caches.open(CACHE).then((c) => c.put(e.request, clone));
        }
        return resp;
      })
    )
  );
});
