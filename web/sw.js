/* Minimal service worker:
 *   - Precaches the app shell + convictions data
 *   - Runtime cache for OSM tiles (cache-first)
 *   - Network-first for convictions.json so deployed updates show up
 */

const VERSION = "v2";
const SHELL_CACHE = `shell-${VERSION}`;
const TILE_CACHE = "tiles";

const SHELL_ASSETS = [
  "./",
  "index.html",
  "style.css",
  "app.js",
  "manifest.json",
  "icon-192.png",
  "icon-512.png",
  "apple-touch-icon.png",
  "favicon-32.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(SHELL_ASSETS)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k.startsWith("shell-") && k !== SHELL_CACHE)
          .map((k) => caches.delete(k)),
      ),
    ),
  );
  self.clients.claim();
});

function isTileRequest(url) {
  return /tile\.openstreetmap\.org/.test(url.host);
}

function isConvictionsRequest(url) {
  return url.pathname.endsWith("/convictions.json") || url.pathname === "convictions.json";
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  if (isTileRequest(url)) {
    event.respondWith(
      caches.open(TILE_CACHE).then(async (cache) => {
        const cached = await cache.match(req);
        if (cached) return cached;
        try {
          const fresh = await fetch(req);
          if (fresh.ok) cache.put(req, fresh.clone());
          return fresh;
        } catch {
          return cached || Response.error();
        }
      }),
    );
    return;
  }

  if (isConvictionsRequest(url)) {
    event.respondWith(
      (async () => {
        try {
          const fresh = await fetch(req);
          if (fresh.ok) {
            const cache = await caches.open(SHELL_CACHE);
            cache.put(req, fresh.clone());
          }
          return fresh;
        } catch {
          const cached = await caches.match(req);
          return cached || Response.error();
        }
      })(),
    );
    return;
  }

  if (url.origin === self.location.origin) {
    event.respondWith(
      caches.match(req).then((cached) => cached || fetch(req)),
    );
  }
});
