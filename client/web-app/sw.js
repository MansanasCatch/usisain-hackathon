const CACHE_NAME = "usisain-cache-v1";

const PRECACHE_ASSETS = [
  "/app/",
  "/app/dashboard/",
  "/app/dashboard/dashboard.js",
  "/app/shared/styles.css",
  "/app/shared/api_client.js",
  "/app/shared/sse_client.js",
  "/app/shared/tts_player.js",
  "/app/shared/chart.umd.min.js",
  "/app/manifest.json",
  "/app/icons/icon-192.png",
  "/app/icons/icon-512.png",
  "/app/icons/icon-512-maskable.png"
];

// Install Event: open cache and populate with static assets
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log("[Service Worker] Precaching static resources");
        // Use cache.addAll to store the static resources
        return cache.addAll(PRECACHE_ASSETS);
      })
      .then(() => self.skipWaiting())
  );
});

// Activate Event: clear out old caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log("[Service Worker] Removing old cache:", cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch Event: handle routing strategies based on request type
self.addEventListener("fetch", (event) => {
  // Only intercept HTTP/HTTPS schemes (ignore chrome-extension, etc.)
  if (!event.request.url.startsWith("http")) return;

  const url = new URL(event.request.url);

  // 1. API Endpoints (Network First, fall back to Cache when offline)
  if (url.pathname.includes("/api/")) {
    // Only cache GET API responses (skip POST switches, uploads, etc.)
    if (event.request.method !== "GET") {
      event.respondWith(fetch(event.request));
      return;
    }

    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.status === 200) {
            const responseClone = response.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(event.request, responseClone);
            });
          }
          return response;
        })
        .catch(() => {
          console.log("[Service Worker] Serving cached API response for:", url.pathname);
          return caches.match(event.request);
        })
    );
    return;
  }

  // 2. Static Assets & Pages (Stale-While-Revalidate strategy)
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      const fetchPromise = fetch(event.request)
        .then((networkResponse) => {
          if (networkResponse.status === 200 && event.request.method === "GET") {
            const responseClone = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(event.request, responseClone);
            });
          }
          return networkResponse;
        })
        .catch((err) => {
          console.log("[Service Worker] Network fetch failed in stale-while-revalidate:", err);
        });

      return cachedResponse || fetchPromise;
    })
  );
});
